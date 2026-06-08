"""Post-mission landing page deploy — Polsia-like live site guarantee."""
from __future__ import annotations

import structlog

from app.core.config import get_settings

logger = structlog.get_logger()


def build_site_url(slug: str, render_url: str | None = None) -> str | None:
    """Prefer branded subdomain if configured, else Render URL."""
    settings = get_settings()
    if settings.site_base_domain and slug:
        return f"https://{slug}.{settings.site_base_domain.strip('.')}"
    if render_url:
        return render_url if render_url.startswith("http") else f"https://{render_url}"
    return None


async def deploy_landing_html(
    company_slug: str,
    html_content: str,
    project_name: str,
    render_service_id: str | None = None,
) -> dict:
    """Push HTML to company repo and optionally trigger Render deploy."""
    from app.agents.tools.deploy_site import _deploy_via_infra, _inject_pixel
    from app.services.infra import InfraService

    settings = get_settings()
    if settings.meta_pixel_id:
        html_content = _inject_pixel(html_content, settings.meta_pixel_id)

    result = await _deploy_via_infra(company_slug, html_content, project_name)

    if result.get("deployed") and render_service_id:
        infra = InfraService()
        deploy_result = await infra.trigger_deploy(render_service_id)
        result["deploy_triggered"] = deploy_result.get("deployed", False)

    site_url = build_site_url(company_slug)
    if site_url:
        result["site_url"] = site_url

    logger.info("landing_deployed", slug=company_slug, site_url=site_url, deployed=result.get("deployed"))
    return result
