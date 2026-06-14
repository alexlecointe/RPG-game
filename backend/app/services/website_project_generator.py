from __future__ import annotations

import json
import html as html_lib
import asyncio
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.agents.base import TokenStats

logger = structlog.get_logger()

WEBSITE_ENGINEERING_TIMEOUT_S = 240


REQUIRED_PROJECT_FILES = [
    "CLAUDE.md",
    "package.json",
    "server.js",
    "render.yaml",
    "migrate.js",
    "db/index.js",
    "routes/api/email.js",
    "views/layout.ejs",
    "views/partials/nav.ejs",
    "views/partials/hero.ejs",
    "views/partials/proof.ejs",
    "views/partials/closing.ejs",
    "public/css/theme.css",
]


@dataclass
class WebsiteProject:
    html: str
    files: dict[str, str] = field(default_factory=dict)
    engine: str = "fallback_renderer"
    provider: str = ""
    model: str = ""
    token_stats: list[TokenStats] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "renderer": self.engine,
            "provider": self.provider,
            "model": self.model,
            "project_files": sorted(self.files.keys()),
            "warnings": self.warnings,
        }


async def generate_website_project(
    *,
    company_name: str,
    mission_statement: str,
    product_description: str,
    target_audience: str,
    business_type: str,
    company_profile_json: str,
    site_spec_json: str,
    product_image_url: str = "",
    checkout_url: str = "",
    meta_pixel_id: str = "",
    revision_request: str = "",
    existing_site_html: str = "",
    quality_feedback: str = "",
) -> WebsiteProject:
    """Generate a stable hybrid website mini-project, then expose publishable HTML.

    The creative strategy still comes from the AI-generated company profile and
    site spec. The critical mechanics are deterministic: project structure,
    checkout wiring, Meta Pixel, and publishable HTML. This keeps the Polsia-like
    mini-project shape while avoiding brittle giant JSON/HTML responses.
    """
    project = _render_hybrid_project(
        company_name=company_name,
        mission_statement=mission_statement,
        product_description=product_description,
        target_audience=target_audience,
        business_type=business_type,
        company_profile_json=company_profile_json,
        site_spec_json=site_spec_json,
        product_image_url=product_image_url,
        checkout_url=checkout_url,
        meta_pixel_id=meta_pixel_id,
        revision_request=revision_request,
        existing_site_html=existing_site_html,
        quality_feedback=quality_feedback,
    )
    warnings = _validate_project(project.files, project.html, meta_pixel_id=meta_pixel_id)
    if warnings:
        raise RuntimeError("website_project_validation_failed:" + ";".join(warnings))
    return project


def _render_hybrid_project(
    *,
    company_name: str,
    mission_statement: str,
    product_description: str,
    target_audience: str,
    business_type: str,
    company_profile_json: str,
    site_spec_json: str,
    product_image_url: str = "",
    checkout_url: str = "",
    meta_pixel_id: str = "",
    revision_request: str = "",
    existing_site_html: str = "",
    quality_feedback: str = "",
) -> WebsiteProject:
    profile = _json_or_text(company_profile_json)
    if not isinstance(profile, dict):
        profile = {}
    spec = _json_or_text(site_spec_json)
    if not isinstance(spec, dict):
        spec = {}

    product = str(profile.get("product") or product_description or mission_statement or company_name)
    audience = str(profile.get("core_customer") or target_audience or "early customers")
    hero_claim = str(profile.get("hero_claim") or _fallback_claim(company_name, product, audience))
    positioning = str(profile.get("positioning") or mission_statement or f"{company_name} helps {audience}.")
    vibe = str(spec.get("brand_vibe") or "premium, clear, product-led")
    playbook_label = str(spec.get("playbook_label") or business_type.replace("_", " ").title())
    visual_system = spec.get("visual_system") if isinstance(spec.get("visual_system"), dict) else {}
    palette = visual_system.get("palette") if isinstance(visual_system.get("palette"), list) else []
    colors = _normalize_palette(palette)
    cta = spec.get("cta") if isinstance(spec.get("cta"), dict) else {}
    checkout = checkout_url or str(cta.get("primary_url") or "").strip()
    cta_label = str(cta.get("primary_label") or ("Commander maintenant" if business_type == "ecommerce" else "Commencer"))
    price_label = _extract_price_label(spec, business_type)

    benefits = _string_list(profile.get("usp")) or _string_list(spec.get("copy_angles")) or [
        f"Pensé pour {audience}",
        "Une offre claire, sans friction",
        "Un résultat concret et facile à comprendre",
    ]
    pain_points = _string_list(profile.get("pain_points")) or [
        "Les alternatives génériques ne répondent pas exactement au besoin.",
        "La solution doit être simple à essayer et crédible immédiatement.",
    ]
    proof_points = _string_list(profile.get("proof_points")) or _string_list(spec.get("trust_signals")) or [
        "Approche centrée produit",
        "Promesse claire",
        "Expérience pensée mobile",
    ]
    sections = _string_list(spec.get("section_blueprint")) or _string_list(spec.get("sections")) or [
        "hero", "problème", "bénéfices", "preuve", "offre", "faq",
    ]
    image_url = product_image_url.strip()
    meta_pixel = str(meta_pixel_id or "").strip()

    html = _build_entry_html(
        company_name=company_name,
        product=product,
        audience=audience,
        hero_claim=hero_claim,
        positioning=positioning,
        vibe=vibe,
        playbook_label=playbook_label,
        business_type=business_type,
        colors=colors,
        cta_label=cta_label,
        price_label=price_label,
        checkout_url=checkout,
        product_image_url=image_url,
        benefits=benefits,
        pain_points=pain_points,
        proof_points=proof_points,
        sections=sections,
        meta_pixel_id=meta_pixel,
    )

    files = _build_project_files(
        html=html,
        company_name=company_name,
        product=product,
        hero_claim=hero_claim,
        cta_label=cta_label,
        checkout_url=checkout,
        colors=colors,
    )
    return WebsiteProject(
        html=html,
        files=files,
        engine="hybrid_scaffold_project",
        provider="backend",
        model="deterministic_scaffold",
        token_stats=[],
        warnings=[],
    )


def _build_entry_html(
    *,
    company_name: str,
    product: str,
    audience: str,
    hero_claim: str,
    positioning: str,
    vibe: str,
    playbook_label: str,
    business_type: str,
    colors: dict[str, str],
    cta_label: str,
    price_label: str,
    checkout_url: str,
    product_image_url: str,
    benefits: list[str],
    pain_points: list[str],
    proof_points: list[str],
    sections: list[str],
    meta_pixel_id: str,
) -> str:
    brand = _e(company_name)
    safe_product = _e(product)
    safe_audience = _e(audience)
    safe_claim = _e(hero_claim)
    safe_positioning = _e(positioning)
    safe_vibe = _e(vibe)
    safe_playbook = _e(playbook_label)
    checkout_href = _safe_url(checkout_url) or "#checkout"
    safe_cta = _e(cta_label)
    safe_price = _e(price_label)
    price_note = f'<p class="price-note">Prix de lancement: <strong>{safe_price}</strong></p>' if safe_price else ""
    image_html = (
        f'<img src="{_e(product_image_url)}" alt="{brand} product" loading="eager">'
        if product_image_url
        else '<div class="css-packshot"><span></span><strong>Product</strong><em>Premium formula</em></div>'
    )
    benefits_html = "\n".join(
        f"<article><span>{idx:02d}</span><h3>{_e(item)}</h3><p>{_benefit_support(item, product)}</p></article>"
        for idx, item in enumerate(benefits[:4], start=1)
    )
    pain_html = "\n".join(f"<li>{_e(item)}</li>" for item in pain_points[:4])
    proof_html = "\n".join(f"<li>{_e(item)}</li>" for item in proof_points[:5])
    sections_html = "\n".join(f"<span>{_e(item)}</span>" for item in sections[:8])
    pixel = _meta_pixel_script(meta_pixel_id)
    checkout_script = _checkout_script(meta_pixel_id)

    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{brand} — {safe_product}</title>
  <meta name="description" content="{safe_positioning}">
  {pixel}
  <style>
    :root {{
      --bg: {colors['bg']};
      --ink: {colors['ink']};
      --accent: {colors['accent']};
      --muted: {colors['muted']};
      --paper: {colors['paper']};
      --line: color-mix(in srgb, var(--ink) 16%, transparent);
      --shadow: 0 24px 80px rgba(20, 24, 28, .16);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at 10% 0%, color-mix(in srgb, var(--accent) 14%, transparent), transparent 28rem),
        linear-gradient(180deg, var(--bg), color-mix(in srgb, var(--bg) 78%, white));
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }}
    a {{ color: inherit; text-decoration: none; }}
    .page {{ overflow: hidden; }}
    .nav {{
      width: min(1120px, calc(100% - 32px));
      margin: 0 auto;
      min-height: 72px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid var(--line);
    }}
    .brand {{ font-weight: 850; letter-spacing: 0; font-size: 1.05rem; }}
    .nav small {{ color: color-mix(in srgb, var(--ink) 58%, transparent); font-weight: 700; }}
    .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 48px;
      padding: 0 22px;
      border-radius: 999px;
      background: var(--ink);
      color: var(--paper);
      font-weight: 850;
      border: 1px solid var(--ink);
      box-shadow: 0 14px 30px rgba(0,0,0,.16);
    }}
    .button.secondary {{
      background: color-mix(in srgb, var(--paper) 76%, transparent);
      color: var(--ink);
      box-shadow: none;
      border-color: var(--line);
    }}
    .hero {{
      width: min(1120px, calc(100% - 32px));
      margin: 0 auto;
      min-height: calc(100svh - 72px);
      display: grid;
      grid-template-columns: minmax(0, 1.02fr) minmax(320px, .98fr);
      gap: clamp(28px, 5vw, 72px);
      align-items: center;
      padding: clamp(42px, 7vw, 88px) 0;
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: color-mix(in srgb, var(--accent) 72%, var(--ink));
      font-size: .78rem;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: .08em;
    }}
    h1 {{
      margin: 18px 0 18px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: clamp(3rem, 8vw, 6.9rem);
      line-height: .9;
      letter-spacing: 0;
      max-width: 10ch;
    }}
    .lead {{
      max-width: 640px;
      font-size: clamp(1.08rem, 2vw, 1.34rem);
      color: color-mix(in srgb, var(--ink) 72%, transparent);
      margin: 0 0 28px;
    }}
    .hero-actions {{ display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }}
    .hero-note {{ margin-top: 18px; color: color-mix(in srgb, var(--ink) 58%, transparent); font-weight: 700; }}
    .price-note {{
      margin: 18px 0 0;
      font-size: 1.02rem;
      color: color-mix(in srgb, var(--ink) 68%, transparent);
      font-weight: 760;
    }}
    .price-note strong {{ color: var(--ink); font-size: 1.18em; }}
    .visual {{
      position: relative;
      min-height: 560px;
      border-radius: 36px;
      background:
        linear-gradient(145deg, color-mix(in srgb, var(--paper) 86%, var(--accent)), var(--paper));
      display: grid;
      place-items: center;
      box-shadow: var(--shadow);
      border: 1px solid color-mix(in srgb, var(--paper) 80%, var(--ink));
      overflow: hidden;
    }}
    .visual::before {{
      content: "";
      position: absolute;
      inset: 10%;
      border-radius: 999px;
      background: color-mix(in srgb, var(--accent) 18%, transparent);
      filter: blur(38px);
    }}
    .visual img {{
      position: relative;
      width: min(78%, 460px);
      max-height: 500px;
      object-fit: contain;
      filter: drop-shadow(0 32px 34px rgba(0,0,0,.18));
    }}
    .css-packshot {{
      position: relative;
      width: 240px;
      height: 390px;
      border-radius: 30px 30px 42px 42px;
      background: linear-gradient(90deg, #f8f4eb, #fff, #e8ded1);
      box-shadow: 0 30px 60px rgba(0,0,0,.2);
      display: grid;
      place-items: center;
      text-align: center;
      padding: 34px;
    }}
    .css-packshot span {{ position: absolute; top: -34px; width: 118px; height: 42px; background: #f1eadf; border-radius: 18px 18px 6px 6px; }}
    .css-packshot strong {{ font-size: 1.35rem; }}
    .css-packshot em {{ color: var(--accent); font-style: normal; font-weight: 800; }}
    .band {{ border-top: 1px solid var(--line); background: color-mix(in srgb, var(--paper) 58%, transparent); }}
    .inner {{ width: min(1120px, calc(100% - 32px)); margin: 0 auto; padding: clamp(54px, 7vw, 92px) 0; }}
    .section-head {{ max-width: 720px; margin-bottom: 34px; }}
    h2 {{
      font-family: Georgia, "Times New Roman", serif;
      font-size: clamp(2rem, 4.2vw, 4.2rem);
      line-height: 1;
      letter-spacing: 0;
      margin: 0 0 14px;
    }}
    .section-head p {{ margin: 0; color: color-mix(in srgb, var(--ink) 66%, transparent); font-size: 1.08rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }}
    article {{
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 24px;
      background: color-mix(in srgb, var(--paper) 82%, transparent);
      min-height: 220px;
    }}
    article span {{ color: var(--accent); font-weight: 950; }}
    article h3 {{ min-height: 72px; margin: 16px 0 10px; font-size: 1.2rem; line-height: 1.12; }}
    article p {{ margin: 0; color: color-mix(in srgb, var(--ink) 62%, transparent); }}
    .split {{ display: grid; grid-template-columns: .9fr 1.1fr; gap: clamp(24px, 5vw, 72px); align-items: start; }}
    .list {{ display: grid; gap: 12px; padding: 0; margin: 0; list-style: none; }}
    .list li {{ padding: 18px 20px; border: 1px solid var(--line); border-radius: 18px; background: color-mix(in srgb, var(--paper) 72%, transparent); font-weight: 740; }}
    .pill-row {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .pill-row span {{ border: 1px solid var(--line); border-radius: 999px; padding: 10px 14px; background: color-mix(in srgb, var(--paper) 74%, transparent); font-weight: 800; color: color-mix(in srgb, var(--ink) 70%, transparent); }}
    .offer {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 24px;
      align-items: center;
      border: 1px solid color-mix(in srgb, var(--accent) 38%, var(--line));
      border-radius: 34px;
      padding: clamp(26px, 5vw, 48px);
      background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 12%, var(--paper)), var(--paper));
      box-shadow: var(--shadow);
    }}
    .offer p {{ max-width: 680px; color: color-mix(in srgb, var(--ink) 68%, transparent); }}
    footer {{ padding: 36px 0; color: color-mix(in srgb, var(--ink) 54%, transparent); }}
    @media (max-width: 860px) {{
      .nav {{ min-height: 64px; }}
      .nav small {{ display: none; }}
      .hero, .split, .offer {{ grid-template-columns: 1fr; }}
      .hero {{ min-height: auto; padding-top: 34px; }}
      .visual {{ min-height: 420px; border-radius: 26px; }}
      .grid {{ grid-template-columns: 1fr; }}
      article {{ min-height: auto; }}
      article h3 {{ min-height: 0; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <nav class="nav">
      <div class="brand">{brand}</div>
      <small>{safe_playbook} · {safe_vibe}</small>
      <a class="button secondary" data-rpg-checkout="true" href="{_e(checkout_href)}">{safe_cta}</a>
    </nav>

    <section class="hero">
      <div>
        <div class="eyebrow">{_e(business_type)} · for {safe_audience}</div>
        <h1>{safe_claim}</h1>
        <p class="lead">{safe_positioning}</p>
        <div class="hero-actions">
          <a class="button" data-rpg-checkout="true" href="{_e(checkout_href)}">{safe_cta}</a>
          <a class="button secondary" href="#proof">Voir les preuves</a>
        </div>
        {price_note}
        <p class="hero-note">Produit: {safe_product}</p>
      </div>
      <div class="visual" aria-label="Product visual">{image_html}</div>
    </section>

    <section class="band">
      <div class="inner split">
        <div class="section-head">
          <p class="eyebrow">Pourquoi maintenant</p>
          <h2>Une page pensée pour un problème précis.</h2>
          <p>Le message, l’offre et les visuels restent centrés sur {safe_product}, pas sur un template générique.</p>
        </div>
        <ul class="list">{pain_html}</ul>
      </div>
    </section>

    <section>
      <div class="inner">
        <div class="section-head">
          <p class="eyebrow">Bénéfices</p>
          <h2>Ce que le client doit comprendre vite.</h2>
          <p>Chaque bloc relie la promesse à une raison concrète d’essayer.</p>
        </div>
        <div class="grid">{benefits_html}</div>
      </div>
    </section>

    <section class="band" id="proof">
      <div class="inner split">
        <div class="section-head">
          <p class="eyebrow">Confiance</p>
          <h2>Des signaux simples avant le clic.</h2>
          <p>Pas de fausses preuves inventées : seulement des signaux sûrs tirés du brief et du positionnement.</p>
        </div>
        <ul class="list">{proof_html}</ul>
      </div>
    </section>

    <section>
      <div class="inner">
        <div class="section-head">
          <p class="eyebrow">Architecture</p>
          <h2>Le playbook choisi guide la page.</h2>
          <p>La structure vient du type de business, puis elle est adaptée au produit.</p>
        </div>
        <div class="pill-row">{sections_html}</div>
      </div>
    </section>

    <section class="band" id="checkout">
      <div class="inner">
        <div class="offer">
          <div>
            <p class="eyebrow">Offre</p>
            <h2>{brand} est prêt à être testé.</h2>
            <p>{safe_positioning}</p>
            {price_note}
          </div>
          <a class="button" data-rpg-checkout="true" href="{_e(checkout_href)}">{safe_cta}</a>
        </div>
        <footer>{brand} · Generated by RPG Agent Company</footer>
      </div>
    </section>
  </main>
  {checkout_script}
</body>
</html>"""


def _build_project_files(
    *,
    html: str,
    company_name: str,
    product: str,
    hero_claim: str,
    cta_label: str,
    checkout_url: str,
    colors: dict[str, str],
) -> dict[str, str]:
    return {
        "CLAUDE.md": f"# {company_name}\n\nHybrid scaffold generated from business strategy.\n",
        "package.json": json.dumps({
            "scripts": {"start": "node server.js", "migrate": "node migrate.js"},
            "dependencies": {"@neondatabase/serverless": "latest", "ejs": "latest", "express": "latest"},
            "devDependencies": {},
        }, indent=2),
        "server.js": "const express = require('express');\nconst app = express();\napp.use(express.static('public'));\napp.set('view engine', 'ejs');\napp.get('/', (req, res) => res.render('layout'));\napp.listen(process.env.PORT || 3000);\n",
        "render.yaml": "services:\n  - type: web\n    name: generated-site\n    env: node\n    buildCommand: npm install\n    startCommand: npm start\n",
        "migrate.js": "console.log('No migrations required for static landing page.');\n",
        "db/index.js": "module.exports = { query: async () => ({ rows: [] }) };\n",
        "routes/api/email.js": "const router = require('express').Router();\nrouter.post('/email', (req, res) => res.json({ ok: true }));\nmodule.exports = router;\n",
        "views/layout.ejs": html,
        "views/partials/nav.ejs": f"<nav>{html_lib.escape(company_name)}</nav>\n",
        "views/partials/hero.ejs": f"<section><h1>{html_lib.escape(hero_claim)}</h1></section>\n",
        "views/partials/proof.ejs": f"<section><p>{html_lib.escape(product)}</p></section>\n",
        "views/partials/closing.ejs": f"<a data-rpg-checkout=\"true\" href=\"{html_lib.escape(checkout_url or '#checkout')}\">{html_lib.escape(cta_label)}</a>\n",
        "public/css/theme.css": f":root{{--bg:{colors['bg']};--ink:{colors['ink']};--accent:{colors['accent']};}}\n",
    }

def _format_generation_error(exc: Exception | None) -> str:
    if exc is None:
        return "unknown_error"
    if isinstance(exc, asyncio.TimeoutError):
        return f"anthropic_timeout_after_{WEBSITE_ENGINEERING_TIMEOUT_S}s"
    text = str(exc).strip()
    if text:
        return text
    return exc.__class__.__name__


def _e(value: Any) -> str:
    return html_lib.escape(str(value or ""), quote=True)


def _safe_url(value: str) -> str:
    url = (value or "").strip()
    if url.startswith(("https://", "http://", "#", "mailto:")):
        return url
    return ""


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, dict):
        return [str(v).strip() for v in value.values() if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_palette(value: list[Any]) -> dict[str, str]:
    colors = [str(v).strip() for v in value if str(v).strip().startswith("#")]
    defaults = ["#f8f3ea", "#1f2b24", "#bd7a55", "#ffffff", "#d7c8b6"]
    while len(colors) < 5:
        colors.append(defaults[len(colors)])
    return {
        "bg": colors[0],
        "ink": colors[1],
        "accent": colors[2],
        "paper": colors[3],
        "muted": colors[4],
    }


def _extract_price_label(spec: dict[str, Any], business_type: str) -> str:
    pricing = spec.get("pricing") if isinstance(spec.get("pricing"), dict) else {}
    offer = spec.get("offer") if isinstance(spec.get("offer"), dict) else {}
    candidates = [
        pricing.get("primary_price"),
        pricing.get("price"),
        pricing.get("monthly"),
        offer.get("price"),
        offer.get("amount"),
        spec.get("price"),
    ]
    for candidate in candidates:
        text = str(candidate or "").strip()
        if text and any(token in text.lower() for token in ["€", "eur", "$", "usd"]):
            return text
    if business_type == "ecommerce":
        return "29€"
    return ""


def _fallback_claim(company_name: str, product: str, audience: str) -> str:
    if product and audience:
        return f"{product} pour {audience}"
    return company_name


def _benefit_support(benefit: str, product: str) -> str:
    base = benefit.strip().rstrip(".")
    if len(base) > 110:
        base = base[:107].rstrip() + "..."
    return _e(f"{base}. Relié directement à {product}, avec un message clair et vérifiable.")


def _meta_pixel_script(meta_pixel_id: str) -> str:
    pixel = (meta_pixel_id or "").strip()
    if not pixel:
        return ""
    safe_pixel = _e(pixel)
    return f"""
  <script>
    !function(f,b,e,v,n,t,s)
    {{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?
    n.callMethod.apply(n,arguments):n.queue.push(arguments)}};
    if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
    n.queue=[];t=b.createElement(e);t.async=!0;
    t.src=v;s=b.getElementsByTagName(e)[0];
    s.parentNode.insertBefore(t,s)}}(window, document,'script',
    'https://connect.facebook.net/en_US/fbevents.js');
    fbq('init', '{safe_pixel}');
    fbq('track', 'PageView');
  </script>
  <noscript><img height="1" width="1" style="display:none" src="https://www.facebook.com/tr?id={safe_pixel}&ev=PageView&noscript=1"></noscript>"""


def _checkout_script(meta_pixel_id: str) -> str:
    if not (meta_pixel_id or "").strip():
        return """
  <script>
    document.querySelectorAll('[data-rpg-checkout="true"]').forEach((el) => {
      el.addEventListener('click', () => {});
    });
  </script>"""
    return """
  <script>
    document.querySelectorAll('[data-rpg-checkout="true"]').forEach((el) => {
      el.addEventListener('click', () => {
        if (window.fbq) {
          fbq('track', 'InitiateCheckout', { value: 0, currency: 'EUR' });
        }
      });
    });
  </script>"""


def project_manifest(project: WebsiteProject, *, site_spec_json: str) -> dict[str, Any]:
    """Small manifest safe to persist with SiteArtifact metadata."""
    try:
        spec = json.loads(site_spec_json) if site_spec_json else {}
    except Exception:
        spec = {}
    return {
        "site_spec": spec,
        "website_engineering": {
            "engine": project.engine,
            "provider": project.provider,
            "model": project.model,
            "project_files": sorted(project.files.keys()),
            "warnings": project.warnings,
        },
    }


def _system_prompt() -> str:
    return (
        "You are a senior full-stack product engineer and conversion-focused web designer. "
        "You generate code from scratch, organized like a deployable mini web app. "
        "You do not use generic AI templates. You create a precise visual direction from "
        "the business context, then code a premium landing page. "
        "You must call the submit_website_project tool with the complete project. "
        "Do not return raw JSON or markdown."
    )


def _user_prompt(
    *,
    company_name: str,
    mission_statement: str,
    product_description: str,
    target_audience: str,
    business_type: str,
    company_profile_json: str,
    site_spec_json: str,
    product_image_url: str,
    checkout_url: str,
    meta_pixel_id: str,
    revision_request: str,
    existing_site_html: str,
    quality_feedback: str,
) -> str:
    payload = {
        "company": {
            "name": company_name,
            "business_type": business_type,
            "mission_statement": mission_statement,
            "product_description": product_description,
            "target_audience": target_audience,
        },
        "company_profile_json": _json_or_text(company_profile_json),
        "site_spec_json": _json_or_text(site_spec_json),
        "assets": {
            "product_image_url": product_image_url,
            "checkout_url": checkout_url,
            "meta_pixel_id": meta_pixel_id,
        },
        "revision": {
            "request": revision_request,
            "existing_site_html_excerpt": (existing_site_html or "")[:5000],
            "quality_feedback": quality_feedback,
        },
    }
    return (
        "Build the website using a Polsia-like engineering workflow.\n"
        "Use the submit_website_project tool exactly once with:\n"
        "- files: object where keys are file paths and values are complete file contents.\n"
        "- entry_html: complete self-contained production HTML for our current gateway.\n\n"
        "Required file paths inside files:\n"
        + "\n".join(f"- {path}" for path in REQUIRED_PROJECT_FILES)
        + "\n\n"
        "Rules for the website:\n"
        "- The page must look intentionally designed for this exact business category.\n"
        "- entry_html must be a real complete page, not a stub. Target at least 7000 characters.\n"
        "- E-commerce must show product image, concrete benefits, price/offer area, trust, and checkout CTA.\n"
        "- SaaS must show UI mockup, integrations/proof, pricing, and trial/demo CTA.\n"
        "- App/mobile must show a phone mockup, screens, waitlist/store CTA.\n"
        "- Local service/consultant must show offer, proof, process, booking CTA.\n"
        "- If product_image_url is present, use it prominently and do not replace it with random stock photos.\n"
        "- If product_image_url is missing, create a premium CSS product mockup instead of using unrelated photos.\n"
        "- If meta_pixel_id is present, entry_html must include Meta Pixel fbq init + PageView in <head>.\n"
        "- If meta_pixel_id is present, primary checkout CTAs must call fbq('track', 'InitiateCheckout', {value: price, currency: 'EUR'}) before navigation.\n"
        "- Primary checkout CTAs must include data-rpg-checkout=\"true\".\n"
        "- Do not invent testimonials, certifications, medical claims, revenue numbers, or legal claims.\n"
        "- entry_html must include CSS in a <style> tag because our gateway serves one HTML artifact.\n"
        "- Include responsive mobile design, strong first viewport, visible CTA, and no empty sections.\n"
        "- Include only safe external links from provided URLs.\n"
        "- File contents can be concise but realistic: Express server, EJS partials, CSS theme, email route, migration stub.\n\n"
        "Business context JSON:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _repair_prompt(original_prompt: str, error_text: str) -> str:
    return (
        original_prompt
        + "\n\nSTRICT REPAIR REQUIRED:\n"
        + "Your previous response was rejected by validation.\n"
        + f"Validation errors: {error_text[:800]}\n"
        + "Call submit_website_project again, but fix every validation error.\n"
        + "Do not shorten entry_html. Include a complete <style> section, full body sections, "
        + "data-rpg-checkout=\"true\" on checkout CTAs, and if meta_pixel_id is present include "
        + "fbq init, PageView, and InitiateCheckout tracking.\n"
    )


def _project_tool_schema() -> dict[str, Any]:
    return {
        "name": "submit_website_project",
        "description": "Submit the complete website mini-project and publishable HTML artifact.",
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "files": {
                    "type": "object",
                    "description": "Project files keyed by relative file path.",
                    "additionalProperties": {"type": "string"},
                },
                "entry_html": {
                    "type": "string",
                    "description": "Complete self-contained production HTML for the current gateway.",
                },
            },
            "required": ["files", "entry_html"],
        },
    }


def _extract_project_payload(response) -> dict[str, Any]:
    for block in response.content:
        if getattr(block, "type", "") == "tool_use" and getattr(block, "name", "") == "submit_website_project":
            payload = getattr(block, "input", None)
            if isinstance(payload, dict):
                return payload
    text_parts = [b.text for b in response.content if hasattr(b, "text")]
    text = "\n".join(text_parts).strip()
    if text:
        logger.warning("website_project_unexpected_text_response", preview=text[:500])
    raise ValueError("website_project_tool_payload_missing")


def _normalize_files(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    files: dict[str, str] = {}
    for path, content in value.items():
        clean_path = str(path).strip().replace("\\", "/").lstrip("/")
        if not clean_path or ".." in clean_path.split("/"):
            continue
        files[clean_path] = str(content)
    return files


def _validate_project(files: dict[str, str], html: str, *, meta_pixel_id: str = "") -> list[str]:
    warnings: list[str] = []
    missing = [path for path in REQUIRED_PROJECT_FILES if path not in files]
    if missing:
        warnings.append("missing_project_files:" + ",".join(missing[:8]))
    if len(html) < 5000:
        warnings.append("entry_html_short")
    html_lower = (html or "").lower()
    if meta_pixel_id:
        pixel_id = str(meta_pixel_id).strip().lower()
        if "fbq(" not in html_lower or "facebook.net" not in html_lower:
            warnings.append("meta_pixel_script_missing")
        if pixel_id and pixel_id not in html_lower:
            warnings.append("meta_pixel_id_missing")
        if "pageview" not in html_lower:
            warnings.append("meta_pixel_pageview_missing")
        if "initiatecheckout" not in html_lower:
            warnings.append("meta_pixel_initiate_checkout_missing")
    if 'data-rpg-checkout="true"' not in html_lower and "data-rpg-checkout='true'" not in html_lower:
        warnings.append("checkout_cta_marker_missing")
    return warnings


def _json_or_text(value: str) -> Any:
    try:
        return json.loads(value) if value else {}
    except Exception:
        return value


def _token_stats_from_anthropic(response, model: str) -> TokenStats:
    usage = response.usage
    return TokenStats(
        provider="anthropic",
        model=model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.input_tokens + usage.output_tokens,
    )
