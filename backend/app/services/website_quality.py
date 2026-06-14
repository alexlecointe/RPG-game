"""Website quality gate for generated landing pages.

This module is intentionally deterministic. The website can be creative, but
the acceptance rules must be predictable enough to debug quickly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

import structlog

from app.services.site_hosting import enforce_site_integrations, sanitize_site_html

logger = structlog.get_logger()


@dataclass
class WebsiteQualityReport:
    score: int
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.score >= 8 and not self.blocking_issues

    @property
    def blocking_issues(self) -> list[str]:
        return [issue for issue in self.issues if issue.startswith("BLOCKING:")]

    def feedback(self) -> str:
        lines = [f"Website quality score: {self.score}/10"]
        if self.issues:
            lines.append("Issues:")
            lines.extend(f"- {issue}" for issue in self.issues)
        if self.warnings:
            lines.append("Warnings:")
            lines.extend(f"- {warning}" for warning in self.warnings)
        return "\n".join(lines)


async def evaluate_website_html(
    html: str,
    *,
    product_image_url: str = "",
    checkout_url: str = "",
    meta_pixel_id: str = "",
    business_type: str = "ecommerce",
    run_browser: bool = True,
) -> WebsiteQualityReport:
    """Score a generated website and optionally render it in Playwright."""
    cleaned = sanitize_site_html(html)
    issues: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {}

    _check_html_structure(cleaned, issues, checks)
    _check_business_requirements(
        cleaned,
        issues,
        checks,
        product_image_url=product_image_url,
        checkout_url=checkout_url,
        meta_pixel_id=meta_pixel_id,
        business_type=business_type,
    )
    _check_visual_signals(cleaned, issues, warnings, checks, product_image_url=product_image_url)

    if run_browser and cleaned:
        browser_report = await _browser_quality_check(cleaned)
        checks["browser"] = browser_report
        issues.extend(browser_report.get("issues", []))
        warnings.extend(browser_report.get("warnings", []))

    score = _score_from_issues(issues, warnings, checks)
    return WebsiteQualityReport(score=score, issues=issues, warnings=warnings, checks=checks)


def repair_website_html(
    html: str,
    *,
    checkout_url: str = "",
    meta_pixel_id: str = "",
) -> str:
    """Repair mechanical integration misses without changing the creative page."""
    return enforce_site_integrations(
        html,
        checkout_url=checkout_url,
        meta_pixel_id=meta_pixel_id,
    )


def _check_html_structure(html: str, issues: list[str], checks: dict[str, Any]) -> None:
    lower = html.lower()
    checks["html_length"] = len(html)
    checks["has_doctype"] = "<!doctype" in lower
    checks["has_html"] = "<html" in lower and "</html>" in lower
    checks["has_head_body"] = "<head" in lower and "<body" in lower
    checks["has_viewport"] = "name=\"viewport\"" in lower or "name='viewport'" in lower

    if not html:
        issues.append("BLOCKING: HTML vide")
        return
    if len(html) < 4500:
        issues.append("BLOCKING: HTML trop court pour une landing page complète")
    if not checks["has_html"]:
        issues.append("BLOCKING: document HTML incomplet")
    if not checks["has_head_body"]:
        issues.append("BLOCKING: structure head/body manquante")
    if not checks["has_viewport"]:
        issues.append("BLOCKING: meta viewport manquante")


def _check_business_requirements(
    html: str,
    issues: list[str],
    checks: dict[str, Any],
    *,
    product_image_url: str,
    checkout_url: str,
    meta_pixel_id: str,
    business_type: str,
) -> None:
    lower = html.lower()
    checks["has_checkout_marker"] = 'data-rpg-checkout="true"' in lower or "data-rpg-checkout='true'" in lower
    checks["has_meta_pixel"] = not meta_pixel_id or ("fbq(" in lower and meta_pixel_id.lower() in lower)
    checks["has_pageview"] = not meta_pixel_id or "pageview" in lower
    checks["has_initiate_checkout"] = not meta_pixel_id or "initiatecheckout" in lower
    checks["has_checkout_url"] = not checkout_url or checkout_url in html

    if business_type == "ecommerce" and not checks["has_checkout_marker"]:
        issues.append("BLOCKING: aucun CTA checkout marqué data-rpg-checkout")
    if checkout_url and not checks["has_checkout_url"]:
        issues.append("BLOCKING: Stripe Payment Link absent du HTML préparé")
    if meta_pixel_id and not checks["has_meta_pixel"]:
        issues.append("BLOCKING: Meta Pixel absent ou mauvais pixel_id")
    if meta_pixel_id and not checks["has_pageview"]:
        issues.append("BLOCKING: Meta Pixel PageView absent")
    if meta_pixel_id and not checks["has_initiate_checkout"]:
        issues.append("BLOCKING: Meta Pixel InitiateCheckout absent")


def _check_visual_signals(
    html: str,
    issues: list[str],
    warnings: list[str],
    checks: dict[str, Any],
    *,
    product_image_url: str,
) -> None:
    lower = html.lower()
    first_screen = lower[:4500]
    headings = len(re.findall(r"<h[123]\b", html, flags=re.IGNORECASE))
    sections = len(re.findall(r"<section\b", html, flags=re.IGNORECASE))
    ctas = len(re.findall(r"data-rpg-checkout\s*=\s*['\"]true['\"]", html, flags=re.IGNORECASE))
    css_signals = sum(
        1
        for signal in (
            "display:grid", "display: grid", "display:flex", "display: flex",
            "border-radius", "box-shadow", "linear-gradient", "@media",
            "max-width", "gap:", "min-height", "clamp(",
        )
        if signal in lower
    )
    has_visual = any(signal in first_screen for signal in ("<img", "css-packshot", "mockup", "dashboard", "phone"))
    checks.update(
        {
            "headings": headings,
            "sections": sections,
            "checkout_ctas": ctas,
            "css_signals": css_signals,
            "hero_has_visual": has_visual,
            "product_image_in_html": not product_image_url or product_image_url in html,
        }
    )

    if headings < 4:
        issues.append("Hiérarchie éditoriale trop faible: moins de 4 titres")
    if sections < 4:
        issues.append("Page trop pauvre: moins de 4 sections")
    if ctas < 2:
        issues.append("CTA principal pas assez répété")
    if css_signals < 7:
        issues.append("Design system trop pauvre: peu de signaux CSS premium/responsive")
    if not has_visual:
        issues.append("BLOCKING: hero sans visuel produit/UI au-dessus du fold")
    if product_image_url and product_image_url not in html:
        issues.append("BLOCKING: image produit générée absente du HTML")

    generic_phrases = (
        "solution innovante",
        "transformez votre business",
        "boostez votre croissance",
        "l'avenir de",
        "révolutionnez votre",
        "revolutionnez votre",
    )
    if any(phrase in lower for phrase in generic_phrases):
        warnings.append("Copy générique détecté")


async def _browser_quality_check(html: str) -> dict[str, Any]:
    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        return {"warnings": [f"browser_quality_unavailable:playwright_import:{str(exc)[:80]}"], "issues": []}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            await page.set_content(html, wait_until="networkidle", timeout=15_000)
            metrics = await page.evaluate(
                """() => {
                  const body = document.body;
                  const h1 = document.querySelector('h1');
                  const checkout = document.querySelector('[data-rpg-checkout="true"]');
                  const visual = document.querySelector('img, .css-packshot, .mockup, .dashboard, .phone');
                  const rect = body ? body.getBoundingClientRect() : { width: 0, height: 0 };
                  return {
                    textLength: body ? body.innerText.trim().length : 0,
                    bodyWidth: rect.width,
                    bodyHeight: rect.height,
                    hasH1: !!h1,
                    hasCheckout: !!checkout,
                    hasVisual: !!visual,
                    checkoutVisible: !!checkout && checkout.getBoundingClientRect().width > 20 && checkout.getBoundingClientRect().height > 20,
                    visualVisible: !!visual && visual.getBoundingClientRect().width > 40 && visual.getBoundingClientRect().height > 40
                  };
                }"""
            )
            screenshot = await page.screenshot(type="png", full_page=False)
            await browser.close()
    except Exception as exc:
        logger.warning("website_browser_quality_failed", error=str(exc))
        return {"warnings": [f"browser_quality_unavailable:{str(exc)[:120]}"], "issues": []}

    issues: list[str] = []
    if metrics.get("textLength", 0) < 600:
        issues.append("BLOCKING: rendu navigateur quasi vide")
    if not metrics.get("hasH1"):
        issues.append("BLOCKING: rendu navigateur sans H1")
    if not metrics.get("hasCheckout") or not metrics.get("checkoutVisible"):
        issues.append("BLOCKING: CTA checkout non visible dans le navigateur")
    if not metrics.get("hasVisual") or not metrics.get("visualVisible"):
        issues.append("BLOCKING: visuel produit/UI non visible dans le navigateur")
    if len(screenshot or b"") < 3000:
        issues.append("BLOCKING: screenshot navigateur suspect ou vide")

    return {
        "issues": issues,
        "warnings": [],
        "metrics": metrics,
        "screenshot_bytes": len(screenshot or b""),
    }


def _score_from_issues(issues: list[str], warnings: list[str], checks: dict[str, Any]) -> int:
    score = 10
    score -= 3 * len([issue for issue in issues if issue.startswith("BLOCKING:")])
    score -= len([issue for issue in issues if not issue.startswith("BLOCKING:")])
    score -= min(2, len(warnings))

    css_signals = int(checks.get("css_signals") or 0)
    sections = int(checks.get("sections") or 0)
    headings = int(checks.get("headings") or 0)
    if css_signals >= 9 and sections >= 5 and headings >= 5:
        score += 1
    return max(0, min(10, score))
