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
) -> "SiteArtifact":  # type: ignore[name-defined]
    """Publish a new site artifact, mark it as live, and archive old versions."""
    from app.models.entities import SiteArtifact

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
    try:
        payment_url = await _get_or_create_site_payment_link(db, artifact)
    except Exception as exc:
        await db.rollback()
        logger.exception(
            "site_checkout_prepare_failed",
            company_id=artifact.company_id,
            slug=artifact.slug,
            error=str(exc),
        )
        return artifact.html_content
    if not payment_url:
        return artifact.html_content
    return _inject_checkout_url(artifact.html_content, payment_url)


async def _get_or_create_site_payment_link(db: AsyncSession, artifact: "SiteArtifact") -> str:  # type: ignore[name-defined]
    from app.models.entities import BusinessType, Company, PaymentLink

    link_result = await db.execute(
        select(PaymentLink)
        .where(PaymentLink.company_id == artifact.company_id, PaymentLink.active == True)  # noqa: E712
        .order_by(PaymentLink.created_at.desc())
        .limit(1)
    )
    existing_link = link_result.scalar_one_or_none()
    if existing_link and existing_link.url:
        return existing_link.url

    company_result = await db.execute(
        select(Company).where(Company.id == artifact.company_id).limit(1)
    )
    company = company_result.scalar_one_or_none()
    if not company:
        return ""

    amount_cents = _extract_price_cents(artifact.html_content)
    if not amount_cents:
        logger.warning(
            "site_checkout_price_missing",
            company_id=company.id,
            slug=artifact.slug,
        )
        return ""

    if company.business_type != BusinessType.ECOMMERCE:
        logger.info(
            "site_checkout_price_detected_for_non_ecommerce",
            company_id=company.id,
            slug=artifact.slug,
            business_type=getattr(company.business_type, "value", str(company.business_type)),
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
                company_id=company.id,
                error=str(exc),
            )
            connect_account_id = ""

    product_name = _site_product_name(company.name, company.product_description)
    success_url = build_gateway_url(artifact.slug) or settings.backend_public_url or "https://example.com/merci"

    result = await _try_create_site_payment_link(
        secret_key=settings.stripe_secret_key,
        product_name=product_name,
        amount_cents=amount_cents,
        currency="eur",
        success_url=success_url,
        company_slug=company.slug or artifact.slug,
        company_id=company.id,
        slug=artifact.slug,
        connect_account_id=connect_account_id,
    )
    if not result and connect_account_id:
        logger.warning(
            "site_checkout_connect_fallback_to_platform",
            company_id=company.id,
            slug=artifact.slug,
        )
        result = await _try_create_site_payment_link(
            secret_key=settings.stripe_secret_key,
            product_name=product_name,
            amount_cents=amount_cents,
            currency="eur",
            success_url=success_url,
            company_slug=company.slug or artifact.slug,
            company_id=company.id,
            slug=artifact.slug,
            connect_account_id="",
        )

    payment_url = result.get("payment_link_url") or result.get("url") or ""
    payment_link_id = result.get("payment_link_id")
    if not payment_url or not payment_link_id:
        return ""

    try:
        db.add(PaymentLink(
            company_id=company.id,
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
            company_id=company.id,
            slug=artifact.slug,
            error=str(exc),
        )
    logger.info("site_checkout_payment_link_created", company_id=company.id, slug=artifact.slug, url=payment_url)
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
    url_json = json.dumps(payment_url)
    updated = re.sub(r"https://buy\.stripe\.com/PLACEHOLDER", payment_url, html, flags=re.IGNORECASE)
    for placeholder_pattern in (
        r"https://example\.com/(?:checkout|buy|order|preorder|pre-order)",
        r"https://www\.example\.com/(?:checkout|buy|order|preorder|pre-order)",
    ):
        updated = re.sub(placeholder_pattern, payment_url, updated, flags=re.IGNORECASE)

    cta_words = (
        r"(?:commander|commander\s+maintenant|acheter|acheter\s+maintenant|"
        r"pré[- ]?commander|pre[- ]?order|order|order\s+now|buy|buy\s+now|"
        r"checkout|panier|cart|shop)"
    )

    def _rewrite_anchor(match: re.Match[str]) -> str:
        attrs, body = match.group(1), match.group(2)
        body_text = re.sub(r"<[^>]+>", " ", body)
        if not re.search(cta_words, body_text, flags=re.IGNORECASE):
            return match.group(0)
        if re.search(r"\bhref\s*=", attrs, flags=re.IGNORECASE):
            attrs = re.sub(
                r"\bhref\s*=\s*(['\"])(.*?)\1",
                f'href="{payment_url}"',
                attrs,
                flags=re.IGNORECASE | re.DOTALL,
            )
        else:
            attrs = f'{attrs} href="{payment_url}"'
        if not re.search(r"\bdata-rpg-checkout\s*=", attrs, flags=re.IGNORECASE):
            attrs = f'{attrs} data-rpg-checkout="true"'
        return f"<a{attrs}>{body}</a>"

    updated = re.sub(r"<a\b([^>]*)>(.*?)</a>", _rewrite_anchor, updated, flags=re.IGNORECASE | re.DOTALL)

    script = f"""
<script>
(function () {{
  var checkoutUrl = {url_json};
  var words = /commander|commander\\s+maintenant|acheter|acheter\\s+maintenant|pré[- ]?commander|pre[- ]?order|order|order\\s+now|buy|buy\\s+now|checkout|panier|cart|shop/i;
  document.addEventListener('click', function (event) {{
    var target = event.target && event.target.closest ? event.target.closest('a,button,[role="button"]') : null;
    if (!target) return;
    var isCheckoutCta = target.getAttribute('data-rpg-checkout') === 'true' || words.test((target.textContent || '').trim());
    if (!isCheckoutCta) return;
    var href = target.getAttribute('href') || '';
    if (target.tagName === 'BUTTON' || !href || href === '#' || href.indexOf('javascript:') === 0 || href.charAt(0) === '/' || target.getAttribute('data-rpg-checkout') === 'true') {{
      event.preventDefault();
      window.location.href = checkoutUrl;
    }}
  }}, true);
}})();
</script>"""
    if "rpgagent-checkout-injected" in updated:
        return updated
    script = script.replace("<script>", '<script id="rpgagent-checkout-injected">', 1)
    if re.search(r"</body>", updated, flags=re.IGNORECASE):
        return re.sub(r"</body>", script + "\n</body>", updated, count=1, flags=re.IGNORECASE)
    return updated + script
