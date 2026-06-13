from __future__ import annotations

import json
import re
from html import escape
from typing import Any


def render_modular_site(
    *,
    company_name: str,
    business_type: str,
    company_profile_json: str,
    site_spec_json: str,
    product_image_url: str = "",
    checkout_url: str = "",
    meta_pixel_id: str = "",
    revision_request: str = "",
) -> str:
    """Render a Polsia-style modular landing page from structured context.

    The LLM is used upstream to create the company profile and site spec. This
    renderer keeps the visual system, layout, and component quality stable.
    """
    profile = _json_object(company_profile_json)
    spec = _json_object(site_spec_json)
    playbook_key = str(spec.get("playbook_key") or _fallback_playbook(business_type)).strip()
    theme = _theme_for(playbook_key, business_type)
    context = _context(
        company_name=company_name,
        business_type=business_type,
        profile=profile,
        spec=spec,
        product_image_url=product_image_url,
        checkout_url=checkout_url,
        revision_request=revision_request,
    )
    sections = _sections_for(context, theme)
    return "\n".join([
        "<!DOCTYPE html>",
        '<html lang="fr">',
        "<head>",
        '  <meta charset="UTF-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"  <title>{escape(context['brand'])} - {escape(context['hero_claim'])}</title>",
        f'  <meta name="description" content="{escape(context["positioning"][:155])}">',
        "  <style>",
        _base_css(theme),
        _visual_css(theme, context),
        "  </style>",
        _analytics_script(meta_pixel_id),
        "</head>",
        "<body>",
        *sections,
        "</body>",
        "</html>",
    ])


def _json_object(value: str) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _context(
    *,
    company_name: str,
    business_type: str,
    profile: dict[str, Any],
    spec: dict[str, Any],
    product_image_url: str,
    checkout_url: str,
    revision_request: str,
) -> dict[str, Any]:
    brand = str(profile.get("brand_name") or company_name or "Brand").strip()
    product = str(profile.get("product") or spec.get("product") or brand).strip()
    customer = str(profile.get("core_customer") or "clients").strip()
    positioning = str(profile.get("positioning") or f"{brand} aide {customer} avec {product}.").strip()
    hero_claim = str(profile.get("hero_claim") or positioning).strip()
    desired = str(profile.get("desired_outcome") or "un resultat clair et credible").strip()
    checkout = checkout_url or _cta_url(spec)
    trust_signals = _list(spec.get("trust_signals"), [])
    if not trust_signals:
        trust_signals = _list(profile.get("proof_points"), ["Paiement securise", "Offre claire", "Support humain"])
    return {
        "brand": brand,
        "business_type": business_type,
        "product": product,
        "customer": customer,
        "positioning": positioning,
        "hero_claim": hero_claim,
        "desired": desired,
        "voice": str(profile.get("voice") or spec.get("brand_vibe") or "premium, clair, specifique"),
        "cta_label": _cta_label(business_type, spec),
        "checkout_url": checkout,
        "price": _extract_price(profile, spec),
        "image_url": product_image_url,
        "usp": _list(profile.get("usp"), ["Concu pour le cas d'usage exact", "Simple a comprendre", "Credible des le premier ecran"]),
        "pain_points": _list(profile.get("pain_points"), ["Les alternatives sont trop generiques", "Le resultat attendu n'est pas assez clair"]),
        "objections": _list(profile.get("objections"), ["Est-ce fait pour moi ?", "Est-ce simple ?", "Est-ce credible ?"]),
        "proof_points": _list(profile.get("proof_points"), ["Preuves a renforcer avec donnees ou avis reels"]),
        "trust_signals": trust_signals,
        "alternatives": _list(profile.get("alternatives_to_beat"), ["solution generique", "routine actuelle"]),
        "copy_bank": _list(profile.get("copy_bank"), [positioning]),
        "unknowns": _list(profile.get("unknowns"), []),
        "sections": _list(spec.get("section_blueprint") or spec.get("sections"), []),
        "mandatory_visuals": _list(spec.get("mandatory_visuals"), []),
        "revision_request": revision_request,
    }


def _list(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned or fallback
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return fallback


def _cta_label(business_type: str, spec: dict[str, Any]) -> str:
    cta = spec.get("cta") if isinstance(spec.get("cta"), dict) else {}
    label = str(cta.get("primary_label") or "").strip()
    if label:
        return label
    if business_type == "saas":
        return "Demander une demo"
    if business_type == "app":
        return "Rejoindre l'acces anticipe"
    if business_type == "ecommerce":
        return "Commander"
    return "Prendre contact"


def _cta_url(spec: dict[str, Any]) -> str:
    cta = spec.get("cta") if isinstance(spec.get("cta"), dict) else {}
    url = str(cta.get("primary_url") or "").strip()
    return url or "https://buy.stripe.com/PLACEHOLDER"


def _extract_price(profile: dict[str, Any], spec: dict[str, Any]) -> str:
    candidates: list[Any] = []
    for source in (spec, profile):
        cta = source.get("cta") if isinstance(source.get("cta"), dict) else {}
        offer = source.get("offer") if isinstance(source.get("offer"), dict) else {}
        pricing = source.get("pricing") if isinstance(source.get("pricing"), dict) else {}
        candidates.extend([
            source.get("price"),
            source.get("pricing"),
            cta.get("price"),
            offer.get("price"),
            pricing.get("price"),
            pricing.get("amount"),
        ])
    for value in candidates:
        if isinstance(value, (int, float)) and value > 0:
            return f"{value:g} EUR"
        if isinstance(value, str):
            match = re.search(
                r"(?:€|\$|£)\s?\d+(?:[,.]\d{1,2})?|\d+(?:[,.]\d{1,2})?\s?(?:€|eur|usd|dollars?)",
                value,
                re.IGNORECASE,
            )
            if match:
                return match.group(0).replace("eur", "EUR").replace("Eur", "EUR")
    return ""


def _fallback_playbook(business_type: str) -> str:
    return {
        "saas": "saas_b2b_productivity",
        "app": "mobile_app",
        "ecommerce": "ecommerce_wellness_skincare",
    }.get(business_type, "service_local_consultant")


def _theme_for(playbook_key: str, business_type: str) -> dict[str, str]:
    themes = {
        "ecommerce_wellness_skincare": {
            "bg": "#f6f0e7", "surface": "#fffaf2", "ink": "#13251d", "muted": "#756f65",
            "primary": "#214533", "secondary": "#b98c5d", "accent": "#d86f45",
            "soft": "#e5dccd", "font_head": "Georgia, 'Times New Roman', serif",
            "font_body": "'Avenir Next', 'Helvetica Neue', sans-serif",
        },
        "ecommerce_fashion_lifestyle": {
            "bg": "#f8f4ef", "surface": "#ffffff", "ink": "#111111", "muted": "#716a62",
            "primary": "#151515", "secondary": "#8a1538", "accent": "#c9aa7b",
            "soft": "#eadfd1", "font_head": "Didot, Georgia, serif",
            "font_body": "'Avenir Next', 'Helvetica Neue', sans-serif",
        },
        "ecommerce_food_beverage": {
            "bg": "#fff7e8", "surface": "#fffdf7", "ink": "#24352d", "muted": "#7c654d",
            "primary": "#284b39", "secondary": "#d39035", "accent": "#be4e35",
            "soft": "#f0dfbd", "font_head": "Georgia, serif",
            "font_body": "'Avenir Next', 'Helvetica Neue', sans-serif",
        },
        "ecommerce_tech_gadget": {
            "bg": "#f4f7fb", "surface": "#ffffff", "ink": "#13171d", "muted": "#667085",
            "primary": "#1252c4", "secondary": "#0f172a", "accent": "#35a2ff",
            "soft": "#dde8f7", "font_head": "'Avenir Next', 'Helvetica Neue', sans-serif",
            "font_body": "'Avenir Next', 'Helvetica Neue', sans-serif",
        },
        "saas_b2b_productivity": {
            "bg": "#f6f8fb", "surface": "#ffffff", "ink": "#111827", "muted": "#667085",
            "primary": "#1d4f91", "secondary": "#10233f", "accent": "#22a06b",
            "soft": "#dbe7f5", "font_head": "'Avenir Next', 'Helvetica Neue', sans-serif",
            "font_body": "'Avenir Next', 'Helvetica Neue', sans-serif",
        },
        "saas_ai_tooling": {
            "bg": "#08111f", "surface": "#101d2f", "ink": "#f8fbff", "muted": "#a7b4c8",
            "primary": "#75d7ff", "secondary": "#9fb4ff", "accent": "#71f2b4",
            "soft": "#17263d", "font_head": "'Avenir Next', 'Helvetica Neue', sans-serif",
            "font_body": "'Avenir Next', 'Helvetica Neue', sans-serif",
        },
        "mobile_app": {
            "bg": "#f4fbff", "surface": "#ffffff", "ink": "#101828", "muted": "#667085",
            "primary": "#2167d8", "secondary": "#26314f", "accent": "#ff7657",
            "soft": "#dbeaff", "font_head": "'Avenir Next', 'Helvetica Neue', sans-serif",
            "font_body": "'Avenir Next', 'Helvetica Neue', sans-serif",
        },
        "service_local_consultant": {
            "bg": "#f8f6f1", "surface": "#ffffff", "ink": "#1e2933", "muted": "#6f665b",
            "primary": "#314256", "secondary": "#9b6a2f", "accent": "#c28a3d",
            "soft": "#e9dfd0", "font_head": "Georgia, serif",
            "font_body": "'Avenir Next', 'Helvetica Neue', sans-serif",
        },
        "creator_personal_brand": {
            "bg": "#fff8ed", "surface": "#ffffff", "ink": "#18181b", "muted": "#725f53",
            "primary": "#be123c", "secondary": "#18181b", "accent": "#f1b51c",
            "soft": "#f7dfb7", "font_head": "Georgia, serif",
            "font_body": "'Avenir Next', 'Helvetica Neue', sans-serif",
        },
    }
    return themes.get(playbook_key) or themes.get(_fallback_playbook(business_type)) or themes["ecommerce_wellness_skincare"]


def _base_css(theme: dict[str, str]) -> str:
    return f"""
    :root {{
      --bg:{theme['bg']}; --surface:{theme['surface']}; --ink:{theme['ink']}; --muted:{theme['muted']};
      --primary:{theme['primary']}; --secondary:{theme['secondary']}; --accent:{theme['accent']}; --soft:{theme['soft']};
      --head:{theme['font_head']}; --body:{theme['font_body']};
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{ margin:0; background:var(--bg); color:var(--ink); font-family:var(--body); line-height:1.6; }}
    a {{ color:inherit; text-decoration:none; }}
    .nav {{ position:sticky; top:0; z-index:20; background:color-mix(in srgb, var(--bg) 88%, transparent); backdrop-filter:blur(16px); border-bottom:1px solid color-mix(in srgb, var(--primary) 12%, transparent); }}
    .nav-inner {{ width:min(1180px, calc(100% - 40px)); margin:0 auto; min-height:72px; display:flex; align-items:center; justify-content:space-between; gap:24px; }}
    .brand {{ font-family:var(--head); font-size:22px; font-weight:700; letter-spacing:.08em; color:var(--primary); text-transform:uppercase; }}
    .nav-note {{ font-size:12px; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); }}
    .btn {{ display:inline-flex; align-items:center; justify-content:center; gap:8px; min-height:48px; padding:0 22px; border-radius:999px; background:var(--primary); color:white; font-weight:800; box-shadow:0 18px 40px color-mix(in srgb, var(--primary) 24%, transparent); transition:transform .16s ease, box-shadow .16s ease, background .16s ease; }}
    .btn:hover {{ transform:translateY(-2px); box-shadow:0 24px 54px color-mix(in srgb, var(--primary) 30%, transparent); }}
    .btn.secondary {{ background:transparent; color:var(--primary); box-shadow:none; border:1px solid color-mix(in srgb, var(--primary) 24%, transparent); }}
    .hero {{ position:relative; overflow:hidden; padding:92px 20px 72px; }}
    .hero::before {{ content:""; position:absolute; inset:-20%; background:radial-gradient(circle at 82% 12%, color-mix(in srgb, var(--accent) 20%, transparent), transparent 34%), radial-gradient(circle at 12% 78%, color-mix(in srgb, var(--primary) 12%, transparent), transparent 36%); pointer-events:none; }}
    .hero-inner, .section-inner {{ position:relative; width:min(1180px, calc(100% - 40px)); margin:0 auto; }}
    .hero-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:70px; align-items:center; }}
    .eyebrow {{ display:flex; gap:10px; align-items:center; color:var(--primary); font-size:12px; font-weight:800; letter-spacing:.18em; text-transform:uppercase; margin-bottom:18px; }}
    .eyebrow::before {{ content:""; width:28px; height:2px; background:var(--primary); }}
    h1 {{ font-family:var(--head); font-size:clamp(48px, 7vw, 88px); line-height:.98; letter-spacing:-.02em; margin:0 0 24px; max-width:780px; }}
    h2 {{ font-family:var(--head); font-size:clamp(34px, 4vw, 58px); line-height:1.04; letter-spacing:-.01em; margin:0 0 18px; }}
    h3 {{ margin:0 0 10px; font-size:20px; }}
    p {{ margin:0; }}
    .lead {{ font-size:18px; color:var(--muted); max-width:620px; }}
    .hero-actions {{ display:flex; flex-wrap:wrap; gap:14px; margin-top:32px; align-items:center; }}
    .stats {{ display:flex; gap:0; margin-top:34px; border:1px solid color-mix(in srgb, var(--primary) 16%, transparent); border-radius:24px; overflow:hidden; width:max-content; max-width:100%; background:color-mix(in srgb, var(--surface) 72%, transparent); }}
    .stat {{ min-width:112px; padding:16px 18px; border-right:1px solid color-mix(in srgb, var(--primary) 12%, transparent); }}
    .stat:last-child {{ border-right:0; }}
    .stat strong {{ display:block; font-size:24px; line-height:1; color:var(--primary); }}
    .stat span {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.1em; }}
    section.band {{ padding:76px 20px; }}
    .surface {{ background:var(--surface); }}
    .proof-card {{ padding:42px; border-radius:30px; background:var(--surface); border:1px solid color-mix(in srgb, var(--primary) 12%, transparent); box-shadow:0 30px 80px rgba(15,25,20,.08); }}
    .quote {{ font-family:var(--head); font-size:clamp(26px, 3vw, 42px); line-height:1.16; color:var(--primary); }}
    .grid-3 {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:18px; }}
    .grid-2 {{ display:grid; grid-template-columns:repeat(2, 1fr); gap:24px; }}
    .card {{ background:var(--surface); border:1px solid color-mix(in srgb, var(--primary) 12%, transparent); border-radius:24px; padding:26px; box-shadow:0 20px 60px rgba(15,25,20,.06); }}
    .card p, .muted {{ color:var(--muted); }}
    .number {{ width:42px; height:42px; display:grid; place-items:center; border-radius:999px; background:var(--primary); color:white; font-weight:900; margin-bottom:18px; }}
    .offer {{ display:grid; grid-template-columns:1.1fr .9fr; gap:28px; align-items:center; padding:44px; border-radius:34px; background:var(--primary); color:white; overflow:hidden; position:relative; }}
    .offer p {{ color:color-mix(in srgb, white 78%, transparent); }}
    .offer .btn {{ background:white; color:var(--primary); box-shadow:none; }}
    .price-pill {{ display:inline-flex; align-items:center; gap:10px; margin-top:22px; padding:10px 14px; border-radius:999px; background:color-mix(in srgb,var(--surface) 74%, transparent); border:1px solid color-mix(in srgb,var(--primary) 14%, transparent); color:var(--primary); font-weight:900; }}
    .price-pill span {{ font-size:11px; color:var(--muted); letter-spacing:.09em; text-transform:uppercase; }}
    .trust-row {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:22px; }}
    .trust-pill {{ padding:8px 12px; border-radius:999px; background:color-mix(in srgb,var(--soft) 58%, transparent); color:var(--primary); font-size:12px; font-weight:800; letter-spacing:.04em; }}
    .section-kicker {{ max-width:720px; margin-bottom:38px; }}
    .section-kicker .lead {{ margin-top:10px; }}
    .comparison {{ display:grid; grid-template-columns:1fr 1fr; gap:22px; }}
    .comparison-card {{ padding:30px; border-radius:28px; border:1px solid color-mix(in srgb,var(--primary) 12%, transparent); background:var(--surface); box-shadow:0 20px 60px rgba(15,25,20,.06); }}
    .comparison-card.dark {{ background:var(--primary); color:white; }}
    .comparison-card.dark p {{ color:color-mix(in srgb,white 78%, transparent); }}
    .offer-buy-box {{ display:grid; gap:16px; justify-items:start; }}
    .offer-price {{ font-family:var(--head); font-size:clamp(42px, 6vw, 72px); line-height:1; font-weight:800; letter-spacing:-.03em; }}
    .faq {{ display:grid; grid-template-columns:.8fr 1.2fr; gap:36px; }}
    details {{ border-bottom:1px solid color-mix(in srgb, var(--primary) 16%, transparent); padding:20px 0; }}
    summary {{ cursor:pointer; font-weight:800; }}
    footer {{ padding:36px 20px; color:var(--muted); border-top:1px solid color-mix(in srgb, var(--primary) 12%, transparent); }}
    @media (max-width: 860px) {{
      .nav-note {{ display:none; }}
      .hero {{ padding-top:64px; }}
      .hero-grid, .grid-2, .offer, .faq, .comparison {{ grid-template-columns:1fr; gap:34px; }}
      .grid-3 {{ grid-template-columns:1fr; }}
      .stats {{ width:100%; }}
      .stat {{ flex:1; min-width:0; }}
      .proof-card, .offer {{ padding:28px; border-radius:24px; }}
    }}
    """


def _visual_css(theme: dict[str, str], context: dict[str, Any]) -> str:
    return """
    .visual-wrap { min-height:520px; display:grid; place-items:center; position:relative; }
    .visual-wrap::before { content:""; position:absolute; width:82%; aspect-ratio:1; border-radius:50%; background:radial-gradient(circle, color-mix(in srgb, var(--soft) 70%, transparent), transparent 70%); }
    .product-image { position:relative; z-index:2; width:min(480px, 92%); border-radius:34px; box-shadow:0 42px 100px rgba(13,28,22,.22); object-fit:cover; aspect-ratio:4/5; background:var(--surface); }
    .product-render { position:relative; z-index:2; width:min(420px, 86%); aspect-ratio:4/5; display:grid; place-items:center; }
    .product-stage { position:relative; z-index:2; width:min(560px, 100%); display:grid; grid-template-columns:.86fr 1fr; gap:18px; align-items:center; }
    .product-stage .product-render { width:100%; }
    .product-stage .product-photo { width:100%; aspect-ratio:1; border-radius:28px; transform:rotate(3deg); }
    .product-render-premium::after { content:""; position:absolute; bottom:16%; width:54%; height:28px; border-radius:50%; background:radial-gradient(ellipse at center, rgba(15,36,25,.22), transparent 68%); filter:blur(10px); }
    .tube { width:46%; min-width:170px; aspect-ratio:1/2.65; border-radius:42px 42px 24px 24px; background:linear-gradient(130deg,#fff 0%,#f3eee5 52%,#d8c7ad 100%); box-shadow:0 34px 90px rgba(20,35,28,.28); position:relative; transform:rotate(-7deg); border:1px solid rgba(20,35,28,.08); }
    .tube::before { content:""; position:absolute; left:18%; right:18%; top:-28px; height:44px; border-radius:20px 20px 8px 8px; background:var(--primary); }
    .tube-label { position:absolute; inset:28% 12% 18%; border:1px solid color-mix(in srgb, var(--primary) 24%, transparent); border-radius:22px; display:grid; place-items:center; text-align:center; padding:16px; color:var(--primary); }
    .tube-label strong { font-family:var(--head); font-size:26px; letter-spacing:.08em; text-transform:uppercase; }
    .tube-label span { font-size:11px; text-transform:uppercase; letter-spacing:.12em; color:var(--muted); }
    .dashboard { position:relative; z-index:2; width:min(560px, 100%); border-radius:28px; background:linear-gradient(145deg,var(--surface),color-mix(in srgb,var(--soft) 42%, var(--surface))); border:1px solid color-mix(in srgb,var(--primary) 16%, transparent); box-shadow:0 36px 100px rgba(10,20,36,.22); padding:18px; }
    .dash-top { height:34px; display:flex; gap:8px; align-items:center; border-bottom:1px solid color-mix(in srgb,var(--primary) 12%, transparent); margin-bottom:18px; }
    .dot { width:10px; height:10px; border-radius:50%; background:var(--accent); }
    .dash-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
    .dash-panel { min-height:118px; border-radius:18px; background:color-mix(in srgb,var(--primary) 7%, var(--surface)); padding:16px; }
    .bar { height:9px; border-radius:99px; background:var(--primary); margin:12px 0; opacity:.72; }
    .phone { position:relative; z-index:2; width:min(310px, 78%); aspect-ratio:9/18; border-radius:42px; background:#111827; padding:14px; box-shadow:0 38px 100px rgba(10,20,36,.28); }
    .phone-screen { height:100%; border-radius:32px; background:linear-gradient(160deg,var(--surface),var(--soft)); padding:22px; display:grid; gap:14px; align-content:start; }
    .screen-card { min-height:74px; border-radius:18px; background:white; padding:14px; box-shadow:0 12px 34px rgba(10,20,36,.08); }
    @media (max-width: 860px) {
      .product-stage { grid-template-columns:1fr; max-width:360px; }
      .product-stage .product-photo { transform:none; }
    }
    """


def _sections_for(context: dict[str, Any], theme: dict[str, str]) -> list[str]:
    if context["business_type"] == "ecommerce":
        return [
            _nav(context, theme),
            _ecommerce_hero(context, theme),
            _ecommerce_proof(context, theme),
            _ecommerce_benefits(context, theme),
            _ecommerce_how(context, theme),
            _ecommerce_comparison(context, theme),
            _ecommerce_offer(context, theme),
            _faq(context, theme),
            _closing(context, theme),
        ]
    return [
        _nav(context, theme),
        _hero(context, theme),
        _proof(context, theme),
        _how_it_works(context, theme),
        _benefits(context, theme),
        _offer_or_pricing(context, theme),
        _faq(context, theme),
        _closing(context, theme),
    ]


def _nav(context: dict[str, Any], theme: dict[str, str]) -> str:
    return f"""
    <nav class="nav">
      <div class="nav-inner">
        <a class="brand" href="#top">{escape(context['brand'])}</a>
        <span class="nav-note">{escape(context['product'][:44])}</span>
        <a class="btn secondary" href="{escape(context['checkout_url'])}">{escape(context['cta_label'])}</a>
      </div>
    </nav>
    """


def _hero(context: dict[str, Any], theme: dict[str, str]) -> str:
    return f"""
    <section class="hero" id="top">
      <div class="hero-inner hero-grid">
        <div>
          <div class="eyebrow">{escape(context['customer'])}</div>
          <h1>{escape(context['hero_claim'])}</h1>
          <p class="lead">{escape(context['positioning'])}</p>
          <div class="hero-actions">
            <a class="btn" href="{escape(context['checkout_url'])}" data-rpg-checkout="true">{escape(context['cta_label'])}</a>
            <a class="btn secondary" href="#proof">Voir pourquoi</a>
          </div>
          {_stats(context)}
        </div>
        <div class="visual-wrap">
          {_visual(context)}
        </div>
      </div>
    </section>
    """


def _ecommerce_hero(context: dict[str, Any], theme: dict[str, str]) -> str:
    price = context["price"]
    price_html = f'<div class="price-pill">{escape(price)}<span>offre de lancement</span></div>' if price else ""
    return f"""
    <section class="hero ecommerce-hero" id="top">
      <div class="hero-inner hero-grid">
        <div>
          <div class="eyebrow">{escape(_ecommerce_category(context))}</div>
          <h1>{escape(context['hero_claim'])}</h1>
          <p class="lead">{escape(context['positioning'])}</p>
          {price_html}
          <div class="hero-actions">
            <a class="btn" href="{escape(context['checkout_url'])}" data-rpg-checkout="true">{escape(context['cta_label'])}</a>
            <a class="btn secondary" href="#proof">Voir la preuve</a>
          </div>
          {_stats(context)}
          {_trust_row(context)}
        </div>
        <div class="visual-wrap ecommerce-visual">
          {_product_stage(context)}
        </div>
      </div>
    </section>
    """


def _product_stage(context: dict[str, Any]) -> str:
    image = ""
    if context["image_url"]:
        image = f'<img class="product-image product-photo" src="{escape(context["image_url"])}" alt="{escape(context["product"])}">'
    return f"""
    <div class="product-stage">
      {_css_product_render(context)}
      {image}
    </div>
    """


def _css_product_render(context: dict[str, Any]) -> str:
    return f"""
    <div class="product-render product-render-premium" aria-label="{escape(context['product'])}">
      <div class="tube"><div class="tube-label"><strong>{escape(context['brand'])}</strong><span>{escape(_product_short_name(context))}</span></div></div>
    </div>
    """


def _ecommerce_proof(context: dict[str, Any], theme: dict[str, str]) -> str:
    proof = context["proof_points"][0] if context["proof_points"] else context["positioning"]
    return f"""
    <section class="band surface" id="proof">
      <div class="section-inner">
        <div class="proof-card proof-card-dark">
          <div class="eyebrow">Pourquoi ca existe</div>
          <p class="quote">{escape(proof)}</p>
          <p class="muted" style="margin-top:18px">{escape(context['alternatives'][0] if context['alternatives'] else context['positioning'])}</p>
        </div>
      </div>
    </section>
    """


def _ecommerce_benefits(context: dict[str, Any], theme: dict[str, str]) -> str:
    items = _take(context["usp"] + context["copy_bank"], 3, context["desired"])
    return f"""
    <section class="band">
      <div class="section-inner">
        <div class="section-kicker">
          <div class="eyebrow">Benefices</div>
          <h2>Ce que le produit change concretement.</h2>
          <p class="lead">{escape(context['desired'])}</p>
        </div>
        <div class="grid-3">
          {"".join(_benefit_card(item) for item in items)}
        </div>
      </div>
    </section>
    """


def _ecommerce_how(context: dict[str, Any], theme: dict[str, str]) -> str:
    return f"""
    <section class="band surface">
      <div class="section-inner">
        <div class="section-kicker">
          <div class="eyebrow">Usage</div>
          <h2>Simple a comprendre, simple a acheter.</h2>
          <p class="lead">{escape(context['product'])} est presente comme une offre claire, pas comme une promesse vague.</p>
        </div>
        <div class="grid-3">
          {_step(1, "Comprendre", context["pain_points"][0] if context["pain_points"] else context["positioning"])}
          {_step(2, "Choisir", context["usp"][0] if context["usp"] else context["desired"])}
          {_step(3, "Passer a l'action", context["cta_label"])}
        </div>
      </div>
    </section>
    """


def _ecommerce_comparison(context: dict[str, Any], theme: dict[str, str]) -> str:
    alternative = context["alternatives"][0] if context["alternatives"] else "les alternatives generiques"
    return f"""
    <section class="band">
      <div class="section-inner">
        <div class="comparison">
          <div class="comparison-card">
            <div class="eyebrow">Avant</div>
            <h3>{escape(_title_from(alternative))}</h3>
            <p class="muted">{escape(alternative)}</p>
          </div>
          <div class="comparison-card dark">
            <div class="eyebrow" style="color:white">Avec {escape(context['brand'])}</div>
            <h3>{escape(_title_from(context['desired']))}</h3>
            <p>{escape(context['desired'])}</p>
          </div>
        </div>
      </div>
    </section>
    """


def _ecommerce_offer(context: dict[str, Any], theme: dict[str, str]) -> str:
    price = context["price"] or "Offre disponible"
    return f"""
    <section class="band surface">
      <div class="section-inner">
        <div class="offer ecommerce-offer">
          <div>
            <div class="eyebrow" style="color:white">Offre</div>
            <h2>{escape(context['product'])}</h2>
            <p>{escape(context['objections'][0] if context['objections'] else context['positioning'])}</p>
            <div class="trust-row">{"".join(f'<span class="trust-pill">{escape(item[:42])}</span>' for item in context["trust_signals"][:3])}</div>
          </div>
          <div class="offer-buy-box">
            <div class="offer-price">{escape(price)}</div>
            <a class="btn" href="{escape(context['checkout_url'])}" data-rpg-checkout="true">{escape(context['cta_label'])}</a>
            <p style="margin-top:16px">Pensé pour {escape(context['customer'])}.</p>
          </div>
        </div>
      </div>
    </section>
    """


def _stats(context: dict[str, Any]) -> str:
    words = _strong_words(context["desired"])
    stat_1 = words[0] if words else "Resultat"
    stat_2 = "Cible"
    stat_3 = "Simple"
    return f"""
    <div class="stats" aria-label="Points cles">
      <div class="stat"><strong>{escape(stat_1[:10])}</strong><span>promesse</span></div>
      <div class="stat"><strong>{escape(stat_2)}</strong><span>{escape(context['customer'][:18])}</span></div>
      <div class="stat"><strong>{escape(stat_3)}</strong><span>a comprendre</span></div>
    </div>
    """


def _visual(context: dict[str, Any]) -> str:
    if context["image_url"]:
        return f'<img class="product-image" src="{escape(context["image_url"])}" alt="{escape(context["product"])}">'
    if context["business_type"] == "saas":
        return """
        <div class="dashboard" aria-label="Interface produit">
          <div class="dash-top"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>
          <div class="dash-grid">
            <div class="dash-panel"><strong>Pipeline</strong><div class="bar" style="width:82%"></div><div class="bar" style="width:54%"></div></div>
            <div class="dash-panel"><strong>Insights</strong><div class="bar" style="width:68%"></div><div class="bar" style="width:88%"></div></div>
            <div class="dash-panel"><strong>Actions</strong><div class="bar" style="width:44%"></div><div class="bar" style="width:74%"></div></div>
            <div class="dash-panel"><strong>Results</strong><div class="bar" style="width:91%"></div><div class="bar" style="width:61%"></div></div>
          </div>
        </div>
        """
    if context["business_type"] == "app":
        return """
        <div class="phone" aria-label="Mockup application mobile">
          <div class="phone-screen">
            <div class="screen-card"><strong>Today</strong><p class="muted">Plan clair en 3 etapes</p></div>
            <div class="screen-card"><strong>Progress</strong><p class="muted">Resultat visible</p></div>
            <div class="screen-card"><strong>Next</strong><p class="muted">Action simple</p></div>
          </div>
        </div>
        """
    return f"""
    <div class="product-render" aria-label="{escape(context['product'])}">
      <div class="tube"><div class="tube-label"><strong>{escape(context['brand'])}</strong><span>{escape(context['product'][:34])}</span></div></div>
    </div>
    """


def _proof(context: dict[str, Any], theme: dict[str, str]) -> str:
    proof = context["proof_points"][0] if context["proof_points"] else context["positioning"]
    return f"""
    <section class="band surface" id="proof">
      <div class="section-inner">
        <div class="proof-card">
          <div class="eyebrow">Pourquoi maintenant</div>
          <p class="quote">{escape(proof)}</p>
          <p class="muted" style="margin-top:18px">{escape(context['positioning'])}</p>
        </div>
      </div>
    </section>
    """


def _how_it_works(context: dict[str, Any], theme: dict[str, str]) -> str:
    pains = context["pain_points"][:3]
    while len(pains) < 3:
        pains.append(context["desired"])
    return f"""
    <section class="band">
      <div class="section-inner">
        <div class="eyebrow">Comment ca marche</div>
        <h2>Une page construite autour du vrai probleme.</h2>
        <div class="grid-3">
          {_step(1, "Le probleme", pains[0])}
          {_step(2, "La difference", context["usp"][0])}
          {_step(3, "Le resultat", context["desired"])}
        </div>
      </div>
    </section>
    """


def _benefits(context: dict[str, Any], theme: dict[str, str]) -> str:
    items = (context["usp"] + context["copy_bank"])[:4]
    return f"""
    <section class="band surface">
      <div class="section-inner grid-2">
        <div>
          <div class="eyebrow">Positionnement</div>
          <h2>Pas une solution generique. Une offre precise.</h2>
          <p class="lead">{escape(context['desired'])}</p>
        </div>
        <div class="grid-2">
          {"".join(_mini_card(item) for item in items)}
        </div>
      </div>
    </section>
    """


def _offer_or_pricing(context: dict[str, Any], theme: dict[str, str]) -> str:
    label = "Offre" if context["business_type"] == "ecommerce" else "Prochaine etape"
    return f"""
    <section class="band">
      <div class="section-inner">
        <div class="offer">
          <div>
            <div class="eyebrow" style="color:white">{escape(label)}</div>
            <h2>{escape(context['hero_claim'])}</h2>
            <p>{escape(context['objections'][0] if context['objections'] else context['positioning'])}</p>
          </div>
          <div>
            <a class="btn" href="{escape(context['checkout_url'])}" data-rpg-checkout="true">{escape(context['cta_label'])}</a>
            <p style="margin-top:16px">Pensé pour {escape(context['customer'])}.</p>
          </div>
        </div>
      </div>
    </section>
    """


def _faq(context: dict[str, Any], theme: dict[str, str]) -> str:
    questions = context["objections"][:3]
    while len(questions) < 3:
        questions.append("Est-ce adapte a mon cas ?")
    answers = [
        context["positioning"],
        context["usp"][0] if context["usp"] else context["desired"],
        "Les details exacts peuvent evoluer, mais la promesse et le produit restent centres sur ce besoin precis.",
    ]
    return f"""
    <section class="band surface">
      <div class="section-inner faq">
        <div>
          <div class="eyebrow">Questions</div>
          <h2>Les objections sont traitees avant le clic.</h2>
        </div>
        <div>
          {"".join(_faq_item(q, answers[i]) for i, q in enumerate(questions))}
        </div>
      </div>
    </section>
    """


def _closing(context: dict[str, Any], theme: dict[str, str]) -> str:
    return f"""
    <section class="band">
      <div class="section-inner" style="text-align:center">
        <div class="eyebrow" style="justify-content:center">Derniere etape</div>
        <h2 style="margin-left:auto;margin-right:auto;max-width:760px">{escape(context['hero_claim'])}</h2>
        <p class="lead" style="margin:0 auto 28px">{escape(context['positioning'])}</p>
        <a class="btn" href="{escape(context['checkout_url'])}" data-rpg-checkout="true">{escape(context['cta_label'])}</a>
      </div>
    </section>
    <footer><div class="section-inner">{escape(context['brand'])} - {escape(context['product'])}</div></footer>
    """


def _step(number: int, title: str, body: str) -> str:
    return f'<div class="card"><div class="number">{number}</div><h3>{escape(title)}</h3><p>{escape(body)}</p></div>'


def _benefit_card(body: str) -> str:
    title = _title_from(body)
    return f'<div class="card"><h3>{escape(title)}</h3><p>{escape(body)}</p></div>'


def _mini_card(body: str) -> str:
    title = _title_from(body)
    return f'<div class="card"><h3>{escape(title)}</h3><p>{escape(body)}</p></div>'


def _faq_item(question: str, answer: str) -> str:
    return f'<details><summary>{escape(question)}</summary><p class="muted" style="margin-top:12px">{escape(answer)}</p></details>'


def _title_from(text: str) -> str:
    words = re.findall(r"[A-Za-zÀ-ÿ0-9']+", text)
    title = " ".join(words[:4]) or "Point cle"
    return title[:52]


def _strong_words(text: str) -> list[str]:
    words = [w for w in re.findall(r"[A-Za-zÀ-ÿ0-9']+", text) if len(w) >= 5]
    return words[:3]


def _take(items: list[str], count: int, fallback: str) -> list[str]:
    cleaned = [item for item in items if item]
    while len(cleaned) < count:
        cleaned.append(fallback)
    return cleaned[:count]


def _ecommerce_category(context: dict[str, Any]) -> str:
    product = context["product"].lower()
    if any(word in product for word in ["creme", "crème", "serum", "sérum", "lotion", "skin", "soin"]):
        return "Soin premium"
    if any(word in product for word in ["drink", "boisson", "cafe", "café", "food", "snack"]):
        return "Produit gourmand"
    if any(word in product for word in ["shirt", "hoodie", "bijou", "vetement", "vêtement"]):
        return "Lifestyle"
    if any(word in product for word in ["tech", "device", "gadget", "outil"]):
        return "Produit tech"
    return "Produit premium"


def _product_short_name(context: dict[str, Any]) -> str:
    product = context["product"].strip()
    brand = context["brand"].strip()
    if product.lower().startswith(brand.lower()):
        product = product[len(brand):].strip(" -:·")
    return product[:34] or "Premium product"


def _trust_row(context: dict[str, Any]) -> str:
    items = context["trust_signals"][:3]
    if not items:
        return ""
    pills = "".join(f'<span class="trust-pill">{escape(item[:42])}</span>' for item in items)
    return f'<div class="trust-row">{pills}</div>'


def _analytics_script(meta_pixel_id: str) -> str:
    if meta_pixel_id:
        pixel = escape(meta_pixel_id)
        return f"""
  <script>
  !function(f,b,e,v,n,t,s){{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?
  n.callMethod.apply(n,arguments):n.queue.push(arguments)}};if(!f._fbq)f._fbq=n;
  n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;
  t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}}
  (window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
  fbq('init','{pixel}');fbq('track','PageView');
  </script>
        """
    return """
  <script>
  window.fbq = window.fbq || function(){ (window.fbq.q = window.fbq.q || []).push(arguments); };
  fbq('track','PageView');
  </script>
    """
