"""Tool: deploy_site — Deploy landing pages via Render + GitHub (Polsia model).

Primary flow: push HTML to the company's GitHub repo -> Render auto-deploys.
Fallback: local package generation if infra keys are not configured.
"""
from __future__ import annotations

import hashlib
import json
import re

import structlog

from app.agents.tools import ToolDefinition

logger = structlog.get_logger()

_deploy_cache: dict[str, dict] = {}

DEPLOY_SITE_SCHEMA = {
    "type": "object",
    "properties": {
        "html_content": {
            "type": "string",
            "description": "Complete HTML content to deploy (from <!DOCTYPE html> to </html>).",
        },
        "project_name": {
            "type": "string",
            "description": "Short project name for the URL (lowercase, alphanumeric, hyphens only).",
        },
    },
    "required": ["html_content", "project_name"],
}


def _sanitize_project_name(name: str) -> str:
    sanitized = re.sub(r"[^a-z0-9-]", "-", name.lower().strip())
    sanitized = re.sub(r"-+", "-", sanitized).strip("-")
    return sanitized[:50] or "my-site"


def _inject_pixel(html: str, pixel_id: str) -> str:
    if not pixel_id or "fbq(" in html:
        return html
    script = f"""<script>
!function(f,b,e,v,n,t,s){{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)}};if(!f._fbq)f._fbq=n;
n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}}
(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
fbq('init','{pixel_id}');fbq('track','PageView');
</script>"""
    if "</head>" in html:
        return html.replace("</head>", script + "</head>")
    if "<body" in html:
        return html.replace("<body", script + "<body", 1)
    return script + html


async def _deploy_via_infra(
    company_slug: str,
    html_content: str,
    project_name: str,
) -> dict:
    """Push HTML to the company's GitHub repo; Render auto-deploys."""
    from app.services.infra import InfraService
    infra = InfraService()

    result = await infra.push_code_to_repo(
        company_slug,
        "public/index.html",
        html_content,
        message=f"Deploy landing page: {project_name}",
    )

    if result.get("pushed"):
        return {
            "deployed": True,
            "platform": "render_github",
            "project": project_name,
            "slug": company_slug,
            "message": (
                f"Landing page pushed to GitHub repo rpg-{company_slug}. "
                "Render will auto-deploy within 2-5 minutes."
            ),
        }

    return {
        "deployed": False,
        "platform": "render_github",
        "error": result.get("error", "Unknown push error"),
    }


def _generate_local_package(
    html_content: str,
    project_name: str,
) -> dict:
    """Fallback: save HTML locally when infra keys are not configured."""
    from pathlib import Path
    output_dir = Path("data/landings") / project_name
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "index.html").write_text(html_content, encoding="utf-8")

    return {
        "deployed": False,
        "platform": "local",
        "project": project_name,
        "output_dir": str(output_dir),
        "message": (
            f"Landing page saved locally at {output_dir}/index.html. "
            "Configure RENDER_API_KEY + GITHUB_TOKEN + GITHUB_ORG to deploy live."
        ),
    }


def create_deploy_site_tool(company_slug: str = "", company_id: str = "") -> ToolDefinition:
    async def execute(
        html_content: str,
        project_name: str,
    ) -> str:
        project_name = _sanitize_project_name(project_name)
        slug = company_slug or project_name

        content_hash = hashlib.sha256(html_content.encode()).hexdigest()[:16]
        cache_key = f"{slug}:{content_hash}"
        if cache_key in _deploy_cache:
            cached = dict(_deploy_cache[cache_key])
            cached["cached"] = True
            return json.dumps(cached)

        from app.core.config import get_settings
        settings = get_settings()

        if settings.meta_pixel_id:
            html_content = _inject_pixel(html_content, settings.meta_pixel_id)

        # Primary: shared gateway (SiteArtifact) — no per-company Render service
        if company_id and slug:
            try:
                from app.core.database import SessionLocal
                from app.services.site_hosting import build_gateway_url, publish_site
                async with SessionLocal() as db:
                    artifact = await publish_site(
                        db,
                        company_id=company_id,
                        slug=slug,
                        html_content=html_content,
                        mission_id=None,
                    )
                    await db.commit()
                site_url = build_gateway_url(slug)
                result = {
                    "deployed": True,
                    "platform": "gateway",
                    "project": project_name,
                    "slug": slug,
                    "site_url": site_url,
                    "version": artifact.version,
                    "message": f"Site publié via le gateway partagé. URL: {site_url}",
                }
                logger.info("deploy_site_gateway", slug=slug, version=artifact.version)
                _deploy_cache[cache_key] = result
                return json.dumps(result)
            except Exception as exc:
                logger.warning("deploy_site_gateway_failed", slug=slug, error=str(exc))

        # Fallback: GitHub/Render (legacy, only if gateway failed and infra configured)
        if settings.github_token and settings.github_org:
            result = await _deploy_via_infra(slug, html_content, project_name)
        else:
            logger.info("deploy_site_fallback_local", reason="no gateway company_id and no github keys")
            result = _generate_local_package(html_content, project_name)

        _deploy_cache[cache_key] = result
        return json.dumps(result)

    return ToolDefinition(
        name="deploy_site",
        description=(
            "Deploy an HTML landing page to the web. Publishes the page via the "
            "shared gateway so it goes live immediately at the company's URL. "
            "The site is accessible within seconds of calling this tool."
        ),
        parameters=DEPLOY_SITE_SCHEMA,
        execute=execute,
    )
