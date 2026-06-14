"""Shared site hosting service.

Replaces per-company Render deployments with a single shared gateway.
All landing pages are stored as SiteArtifact rows and served via
GET /sites/{slug} on our own backend.

URL pattern:
  - Dev / MVP:  {BACKEND_PUBLIC_URL}/sites/{slug}
  - Production: https://{slug}.rpgagent.app  (once domain is configured)
"""
from __future__ import annotations

import json
import re
from html import escape

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

logger = structlog.get_logger()


def build_gateway_url(slug: str) -> str | None:
    """Build the public URL for a company site via the shared gateway."""
    if not slug:
        return None
    settings = get_settings()
    # Custom domain (e.g. feetdry.rpgagent.app)
    if settings.site_base_domain:
        return f"https://{slug}.{settings.site_base_domain.strip('.')}"
    # Fallback: backend URL + /api/v1/sites/{slug}
    base = settings.backend_public_url.rstrip("/") if settings.backend_public_url else ""
    if base:
        return f"{base}/api/v1/sites/{slug}"
    return None


async def publish_site(
    db: AsyncSession,
    company_id: str,
    slug: str,
    html_content: str,
    mission_id: str | None = None,
    quality_score: float | None = None,
    site_spec_json: str | None = None,
) -> "SiteArtifact":  # type: ignore[name-defined]
    """Publish a new site artifact, mark it as live, and archive old versions."""
    from app.models.entities import SiteArtifact

    settings = get_settings()
    html_content = enforce_site_integrations(
        html_content,
        meta_pixel_id=settings.meta_pixel_id,
    )

    # Get current version number
    result = await db.execute(
        select(SiteArtifact)
        .where(SiteArtifact.company_id == company_id)
        .order_by(SiteArtifact.version.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    next_version = (latest.version + 1) if latest else 1

    # Archive old live versions
    if latest and latest.is_live:
        from sqlalchemy import update
        await db.execute(
            update(SiteArtifact)
            .where(SiteArtifact.company_id == company_id, SiteArtifact.is_live == True)
            .values(is_live=False)
        )

    artifact = SiteArtifact(
        company_id=company_id,
        slug=slug,
        html_content=html_content,
        site_spec_json=site_spec_json,
        version=next_version,
        is_live=True,
        mission_id=mission_id,
        quality_score=quality_score,
    )
    db.add(artifact)
    await db.flush()

    site_url = build_gateway_url(slug)
    logger.info(
        "site_published",
        company_id=company_id,
        slug=slug,
        version=next_version,
        url=site_url,
    )
    return artifact


async def get_live_artifact(db: AsyncSession, slug: str) -> "SiteArtifact | None":  # type: ignore[name-defined]
    """Fetch the current live artifact for a slug."""
    from app.models.entities import SiteArtifact
    result = await db.execute(
        select(SiteArtifact)
        .where(SiteArtifact.slug == slug, SiteArtifact.is_live == True)
        .order_by(SiteArtifact.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def prepare_site_html_for_checkout(db: AsyncSession, artifact: "SiteArtifact") -> str:  # type: ignore[name-defined]
    """Attach the latest Stripe Payment Link to purchase CTAs on hosted sites."""
    settings = get_settings()
    fallback_html = enforce_site_integrations(
        str(getattr(artifact, "html_content", "") or ""),
        meta_pixel_id=settings.meta_pixel_id,
    )
    company_id = str(getattr(artifact, "company_id", "") or "")
    slug = str(getattr(artifact, "slug", "") or "")
    try:
        payment_url = await _get_or_create_site_payment_link(db, artifact)
    except Exception as exc:
        await db.rollback()
        logger.exception(
            "site_checkout_prepare_failed",
            company_id=company_id,
            slug=slug,
            error=str(exc),
        )
        return fallback_html
    if not payment_url:
        return fallback_html
    try:
        return enforce_site_integrations(
            fallback_html,
            checkout_url=payment_url,
            meta_pixel_id=settings.meta_pixel_id,
        )
    except Exception as exc:
        logger.exception(
            "site_checkout_inject_failed",
            company_id=company_id,
            slug=slug,
            error=str(exc),
        )
        return fallback_html


async def _get_or_create_site_payment_link(db: AsyncSession, artifact: "SiteArtifact") -> str:  # type: ignore[name-defined]
    from app.models.entities import BusinessType, Company, PaymentLink

    artifact_company_id = artifact.company_id
    artifact_slug = artifact.slug
    artifact_html = artifact.html_content

    link_result = await db.execute(
        select(PaymentLink)
        .where(PaymentLink.company_id == artifact_company_id, PaymentLink.active == True)  # noqa: E712
        .order_by(PaymentLink.created_at.desc())
        .limit(1)
    )
    existing_link = link_result.scalar_one_or_none()
    if existing_link and existing_link.url:
        return existing_link.url

    company_result = await db.execute(
        select(Company).where(Company.id == artifact_company_id).limit(1)
    )
    company = company_result.scalar_one_or_none()
    if not company:
        return ""

    amount_cents = _extract_price_cents(artifact_html)
    company_id = company.id
    company_slug = company.slug or artifact_slug
    company_name = company.name
    product_description = company.product_description
    business_type = company.business_type
    if not amount_cents:
        logger.warning(
            "site_checkout_price_missing",
            company_id=company_id,
            slug=artifact_slug,
        )
        return ""

    if business_type != BusinessType.ECOMMERCE:
        logger.info(
            "site_checkout_price_detected_for_non_ecommerce",
            company_id=company_id,
            slug=artifact_slug,
            business_type=getattr(business_type, "value", str(business_type)),
        )

    settings = get_settings()
    if not settings.stripe_secret_key:
        return ""

    connect_account_id = getattr(company, "stripe_connect_account_id", None) or ""
    if connect_account_id:
        try:
            from app.services.stripe_connect import fetch_connect_status

            status = await fetch_connect_status(connect_account_id)
            if status.get("status") != "ready":
                connect_account_id = ""
        except Exception as exc:
            logger.warning(
                "site_checkout_connect_status_failed",
                company_id=company_id,
                error=str(exc),
            )
            connect_account_id = ""

    product_name = _site_product_name(company_name, product_description)
    success_url = build_gateway_url(artifact_slug) or settings.backend_public_url or "https://example.com/merci"

    result = await _try_create_site_payment_link(
        secret_key=settings.stripe_secret_key,
        product_name=product_name,
        amount_cents=amount_cents,
        currency="eur",
        success_url=success_url,
        company_slug=company_slug,
        company_id=company_id,
        slug=artifact_slug,
        connect_account_id=connect_account_id,
    )
    if not result and connect_account_id:
        logger.warning(
            "site_checkout_connect_fallback_to_platform",
            company_id=company_id,
            slug=artifact_slug,
        )
        result = await _try_create_site_payment_link(
            secret_key=settings.stripe_secret_key,
            product_name=product_name,
            amount_cents=amount_cents,
            currency="eur",
            success_url=success_url,
            company_slug=company_slug,
            company_id=company_id,
            slug=artifact_slug,
            connect_account_id="",
        )

    payment_url = result.get("payment_link_url") or result.get("url") or ""
    payment_link_id = result.get("payment_link_id")
    if not payment_url or not payment_link_id:
        return ""

    try:
        db.add(PaymentLink(
            company_id=company_id,
            stripe_payment_link_id=payment_link_id,
            url=payment_url,
            product_name=product_name,
            amount_cents=amount_cents,
            currency="eur",
            stripe_product_id=result.get("product_id"),
            stripe_price_id=result.get("price_id"),
            payout_status=result.get("payout_status", "connected" if connect_account_id else "platform_pending_connect"),
            requires_connect=bool(result.get("requires_connect", not bool(connect_account_id))),
        ))
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.warning(
            "site_checkout_payment_link_persist_failed",
            company_id=company_id,
            slug=artifact_slug,
            error=str(exc),
        )
    logger.info("site_checkout_payment_link_created", company_id=company_id, slug=artifact_slug, url=payment_url)
    return payment_url


async def _try_create_site_payment_link(
    *,
    secret_key: str,
    product_name: str,
    amount_cents: int,
    currency: str,
    success_url: str,
    company_slug: str,
    company_id: str,
    slug: str,
    connect_account_id: str,
) -> dict:
    from app.agents.tools.stripe_action import _create_payment_link

    try:
        return await _create_payment_link(
            secret_key=secret_key,
            product_name=product_name,
            amount_cents=amount_cents,
            currency=currency,
            success_url=success_url,
            company_slug=company_slug,
            connect_account_id=connect_account_id,
        )
    except Exception as exc:
        logger.warning(
            "site_checkout_payment_link_create_failed",
            company_id=company_id,
            slug=slug,
            connect=bool(connect_account_id),
            error=str(exc),
        )
        return {}


def _site_product_name(company_name: str, product_description: str | None) -> str:
    text = (product_description or "").strip()
    if text:
        sentence = re.split(r"[.\n]", text, maxsplit=1)[0].strip()
        if 3 <= len(sentence) <= 80:
            return sentence
    return company_name


def _extract_price_cents(html: str) -> int | None:
    def _to_cents(value: str) -> int | None:
        try:
            cents = int(round(float(value.replace(",", ".")) * 100))
        except ValueError:
            return None
        if 50 <= cents <= 500_000:
            return cents
        return None

    text = re.sub(r"<[^>]+>", " ", html)
    patterns = [
        r"(?:€|EUR)\s*([0-9]+(?:[,.][0-9]{1,2})?)",
        r"([0-9]+(?:[,.][0-9]{1,2})?)\s*(?:€|EUR)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            cents = _to_cents(match.group(1))
            if cents:
                return cents

    tracking_patterns = [
        r"\bvalue\s*:\s*([0-9]+(?:[,.][0-9]{1,2})?)\s*,\s*currency\s*:\s*['\"]EUR['\"]",
        r"\bcurrency\s*:\s*['\"]EUR['\"]\s*,\s*\bvalue\s*:\s*([0-9]+(?:[,.][0-9]{1,2})?)",
        r"['\"]value['\"]\s*:\s*([0-9]+(?:[,.][0-9]{1,2})?)\s*,\s*['\"]currency['\"]\s*:\s*['\"]EUR['\"]",
        r"['\"]currency['\"]\s*:\s*['\"]EUR['\"]\s*,\s*['\"]value['\"]\s*:\s*([0-9]+(?:[,.][0-9]{1,2})?)",
    ]
    for pattern in tracking_patterns:
        for match in re.finditer(pattern, html, flags=re.IGNORECASE):
            cents = _to_cents(match.group(1))
            if cents:
                return cents
    return None


def _inject_checkout_url(html: str, payment_url: str) -> str:
    updated = str(html or "")
    payment_url = str(payment_url or "").strip()
    if not payment_url:
        return updated

    url_json = json.dumps(payment_url)
    attr_url = payment_url.replace("&", "&amp;").replace('"', "&quot;")
    updated = re.sub(r"https://buy\.stripe\.com/PLACEHOLDER", payment_url, updated, flags=re.IGNORECASE)
    for placeholder_pattern in (
        r"https://example\.com/(?:checkout|buy|order|preorder|pre-order)",
        r"https://www\.example\.com/(?:checkout|buy|order|preorder|pre-order)",
    ):
        updated = re.sub(placeholder_pattern, payment_url, updated, flags=re.IGNORECASE)

    cta_words = (
        r"(?:commander|commander\s+maintenant|acheter|acheter\s+maintenant|"
        r"pré[- ]?commander|pre[- ]?order|order|order\s+now|buy|buy\s+now|"
        r"checkout|panier|cart|shop|purchase|payer|payment)"
    )

    def _rewrite_anchor(match: re.Match[str]) -> str:
        attrs, body = match.group(1), match.group(2)
        body_text = re.sub(r"<[^>]+>", " ", body)
        if not re.search(cta_words, body_text, flags=re.IGNORECASE):
            return match.group(0)
        if re.search(r"\bhref\s*=", attrs, flags=re.IGNORECASE):
            attrs = re.sub(
                r"\bhref\s*=\s*(['\"])(.*?)\1",
                f'href="{attr_url}"',
                attrs,
                flags=re.IGNORECASE | re.DOTALL,
            )
        else:
            attrs = f'{attrs} href="{attr_url}"'
        if not re.search(r"\bdata-rpg-checkout\s*=", attrs, flags=re.IGNORECASE):
            attrs = f'{attrs} data-rpg-checkout="true"'
        return f"<a{attrs}>{body}</a>"

    def _rewrite_button(match: re.Match[str]) -> str:
        attrs, body = match.group(1), match.group(2)
        body_text = re.sub(r"<[^>]+>", " ", body)
        if not re.search(cta_words, body_text, flags=re.IGNORECASE):
            return match.group(0)
        if not re.search(r"\bdata-rpg-checkout\s*=", attrs, flags=re.IGNORECASE):
            attrs = f'{attrs} data-rpg-checkout="true"'
        return f"<button{attrs}>{body}</button>"

    updated = re.sub(r"<a\b([^>]*)>(.*?)</a>", _rewrite_anchor, updated, flags=re.IGNORECASE | re.DOTALL)
    updated = re.sub(r"<button\b([^>]*)>(.*?)</button>", _rewrite_button, updated, flags=re.IGNORECASE | re.DOTALL)

    script = f"""
<script>
(function () {{
  var checkoutUrl = {url_json};
  var words = /commander|commander\\s+maintenant|acheter|acheter\\s+maintenant|pré[- ]?commander|pre[- ]?order|order|order\\s+now|buy|buy\\s+now|checkout|panier|cart|shop|purchase|payer|payment/i;
  var placeholderHref = /^(#|javascript:|\\/checkout|\\/buy|\\/order|\\/cart|\\/shop|\\/preorder|\\/pre-order|https?:\\/\\/(www\\.)?example\\.com|https?:\\/\\/buy\\.stripe\\.com\\/PLACEHOLDER)/i;

  function describe(node) {{
    if (!node || node.nodeType !== 1) return "";
    return [
      node.textContent || "",
      node.getAttribute("aria-label") || "",
      node.getAttribute("title") || "",
      node.getAttribute("class") || "",
      node.getAttribute("id") || "",
      node.getAttribute("href") || ""
    ].join(" ");
  }}

  function checkoutTarget(start) {{
    var node = start;
    var depth = 0;
    while (node && node !== document.body && node.nodeType === 1 && depth < 8) {{
      var tag = (node.tagName || "").toUpperCase();
      var href = node.getAttribute ? (node.getAttribute("href") || "") : "";
      var explicit = node.getAttribute && node.getAttribute("data-rpg-checkout") === "true";
      var looksClickable = explicit || tag === "A" || tag === "BUTTON" || node.getAttribute("role") === "button" || node.onclick || node.getAttribute("onclick");
      var looksCheckout = explicit || words.test(describe(node)) || placeholderHref.test(href);
      if (looksClickable && looksCheckout) return node;
      node = node.parentElement;
      depth += 1;
    }}
    return null;
  }}

  function go(event) {{
    var target = checkoutTarget(event.target);
    if (!target) return;
    var href = target.getAttribute("href") || "";
    var isCheckoutCta = target.getAttribute("data-rpg-checkout") === "true" || words.test(describe(target)) || placeholderHref.test(href);
    if (!isCheckoutCta) return;
    event.preventDefault();
    if (event.stopImmediatePropagation) event.stopImmediatePropagation();
    try {{
      if (window.fbq) window.fbq('track', 'InitiateCheckout', {{ currency: 'EUR' }});
    }} catch (err) {{}}
    window.location.assign(checkoutUrl);
  }}

  document.addEventListener("click", go, true);
  document.addEventListener("touchend", go, true);
}})();
</script>"""
    if "rpgagent-checkout-injected" in updated:
        return updated
    script = script.replace("<script>", '<script id="rpgagent-checkout-injected">', 1)
    if re.search(r"</body>", updated, flags=re.IGNORECASE):
        return re.sub(
            r"</body>",
            lambda _match: script + "\n</body>",
            updated,
            count=1,
            flags=re.IGNORECASE,
        )
    return updated + script


def enforce_site_integrations(
    html: str,
    *,
    checkout_url: str = "",
    meta_pixel_id: str = "",
) -> str:
    """Force critical site integrations independently of the generator.

    The builder/agent can still create the page creatively, but checkout CTA
    wiring and Meta Pixel should never rely on a prompt being remembered.
    """
    updated = sanitize_site_html(html)
    updated = _mark_checkout_ctas(updated)
    if meta_pixel_id:
        updated = _inject_meta_pixel(updated, meta_pixel_id)
    if checkout_url:
        updated = _inject_checkout_url(updated, checkout_url)
    updated = _inject_checkout_tracking(updated)
    return sanitize_site_html(updated)


def _mark_checkout_ctas(html: str) -> str:
    updated = str(html or "")
    if not updated:
        return updated
    cta_words = (
        r"(?:commander|commander\s+maintenant|acheter|acheter\s+maintenant|"
        r"pré[- ]?commander|pre[- ]?order|order|order\s+now|buy|buy\s+now|"
        r"checkout|panier|cart|shop|purchase|payer|payment|try|trial|demo)"
    )

    def _rewrite_anchor(match: re.Match[str]) -> str:
        attrs, body = match.group(1), match.group(2)
        body_text = re.sub(r"<[^>]+>", " ", body)
        href = re.search(r"\bhref\s*=\s*(['\"])(.*?)\1", attrs, flags=re.IGNORECASE | re.DOTALL)
        href_value = href.group(2) if href else ""
        looks_checkout = (
            re.search(cta_words, body_text + " " + attrs, flags=re.IGNORECASE)
            or re.search(r"(#checkout|/checkout|/buy|/order|/cart|buy\.stripe\.com)", href_value, flags=re.IGNORECASE)
        )
        if not looks_checkout:
            return match.group(0)
        if not re.search(r"\bdata-rpg-checkout\s*=", attrs, flags=re.IGNORECASE):
            attrs = f'{attrs} data-rpg-checkout="true"'
        return f"<a{attrs}>{body}</a>"

    def _rewrite_button(match: re.Match[str]) -> str:
        attrs, body = match.group(1), match.group(2)
        body_text = re.sub(r"<[^>]+>", " ", body)
        if not re.search(cta_words, body_text + " " + attrs, flags=re.IGNORECASE):
            return match.group(0)
        if not re.search(r"\bdata-rpg-checkout\s*=", attrs, flags=re.IGNORECASE):
            attrs = f'{attrs} data-rpg-checkout="true"'
        return f"<button{attrs}>{body}</button>"

    updated = re.sub(r"<a\b([^>]*)>(.*?)</a>", _rewrite_anchor, updated, flags=re.IGNORECASE | re.DOTALL)
    updated = re.sub(r"<button\b([^>]*)>(.*?)</button>", _rewrite_button, updated, flags=re.IGNORECASE | re.DOTALL)
    return updated


def _inject_meta_pixel(html: str, pixel_id: str) -> str:
    updated = str(html or "")
    pixel = str(pixel_id or "").strip()
    if not updated or not pixel:
        return updated
    lower = updated.lower()
    if "fbq(" in lower and pixel.lower() in lower and "pageview" in lower:
        return updated
    safe_pixel = escape(pixel, quote=True)
    script = f"""
<!-- Meta Pixel Code -->
<script id="rpgagent-meta-pixel">
!function(f,b,e,v,n,t,s){{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)}};if(!f._fbq)f._fbq=n;
n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}}(window, document,'script',
'https://connect.facebook.net/en_US/fbevents.js');
fbq('init', '{safe_pixel}');
fbq('track', 'PageView');
</script>
<noscript><img height="1" width="1" style="display:none" src="https://www.facebook.com/tr?id={safe_pixel}&ev=PageView&noscript=1"></noscript>
<!-- End Meta Pixel Code -->"""
    if re.search(r"</head>", updated, flags=re.IGNORECASE):
        return re.sub(
            r"</head>",
            lambda _match: script + "\n</head>",
            updated,
            count=1,
            flags=re.IGNORECASE,
        )
    return script + "\n" + updated


def _inject_checkout_tracking(html: str) -> str:
    updated = str(html or "")
    if not updated or "rpgagent-checkout-tracking" in updated:
        return updated
    script = """
<script id="rpgagent-checkout-tracking">
(function () {
  function findCheckout(node) {
    while (node && node !== document.body && node.nodeType === 1) {
      if (node.getAttribute && node.getAttribute('data-rpg-checkout') === 'true') return node;
      node = node.parentElement;
    }
    return null;
  }
  document.addEventListener('click', function (event) {
    var target = findCheckout(event.target);
    if (!target) return;
    try {
      if (window.fbq) window.fbq('track', 'InitiateCheckout', { currency: 'EUR' });
    } catch (err) {}
  }, true);
})();
</script>"""
    if re.search(r"</body>", updated, flags=re.IGNORECASE):
        return re.sub(
            r"</body>",
            lambda _match: script + "\n</body>",
            updated,
            count=1,
            flags=re.IGNORECASE,
        )
    return updated + script


def sanitize_site_html(content: str) -> str:
    """Keep only the actual HTML document from an LLM/deploy_site response."""
    html = str(content or "").strip()
    if not html:
        return ""

    fence_match = re.search(r"```(?:html)?\s*([\s\S]*?)```", html, flags=re.IGNORECASE)
    if fence_match:
        html = fence_match.group(1).strip()

    doc_match = re.search(r"<!doctype\s+html[\s\S]*?</html>", html, flags=re.IGNORECASE)
    if doc_match:
        html = doc_match.group(0).strip()
    else:
        html_match = re.search(r"<html[\s\S]*?</html>", html, flags=re.IGNORECASE)
        if html_match:
            html = html_match.group(0).strip()

    # Starlette encodes HTML responses as UTF-8; strip invalid surrogate chars
    # so a single bad model token cannot turn a live site into a 500.
    return html.encode("utf-8", errors="replace").decode("utf-8", errors="replace")


def replace_image_url_with_product_placeholder(
    html: str,
    image_url: str,
    *,
    company_name: str,
    product_description: str = "",
) -> str:
    """Remove a known-bad generated product image from an existing site HTML."""
    if not html or not image_url:
        return html
    safe_url = re.escape(image_url)
    label = escape((product_description or company_name or "Produit").strip())
    brand = escape((company_name or "Produit").strip())
    placeholder = f"""
<div class="rpg-product-placeholder" role="img" aria-label="{label}">
  <div class="rpg-product-packshot">
    <span>{brand}</span>
    <small>{label}</small>
  </div>
</div>
<style>
.rpg-product-placeholder {{
  min-height: 320px;
  display: grid;
  place-items: center;
  border-radius: 24px;
  background: radial-gradient(circle at 30% 20%, #ffffff 0, #f8f3ea 34%, #e7d8c2 100%);
  border: 1px solid rgba(38, 69, 51, 0.18);
}}
.rpg-product-packshot {{
  width: min(220px, 70%);
  aspect-ratio: 3 / 4;
  border-radius: 28px 28px 18px 18px;
  background: linear-gradient(180deg, #ffffff, #f3f0e8);
  box-shadow: 0 28px 70px rgba(18, 31, 24, 0.22);
  display: grid;
  place-items: center;
  text-align: center;
  color: #264533;
  padding: 24px;
  font-weight: 800;
}}
.rpg-product-packshot small {{
  display: block;
  margin-top: 12px;
  font-size: 0.74rem;
  font-weight: 600;
  opacity: 0.65;
}}
</style>
""".strip()
    return re.sub(
        rf"<img\b[^>]*\bsrc\s*=\s*(['\"]){safe_url}\1[^>]*>",
        placeholder,
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
