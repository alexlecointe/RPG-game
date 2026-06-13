from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.agents.base import TokenStats
from app.services.website_renderer import render_modular_site

logger = structlog.get_logger()


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
    """Generate a Polsia-style website mini-project, then expose publishable HTML.

    The hosted app still serves a single HTML artifact, but the LLM is asked to
    think and code like an engineering agent: project files, partials, routes,
    CSS, migration stub, and a final self-contained HTML entrypoint.
    """
    fallback_html = render_modular_site(
        company_name=company_name,
        business_type=business_type,
        company_profile_json=company_profile_json,
        site_spec_json=site_spec_json,
        product_image_url=product_image_url,
        checkout_url=checkout_url,
        meta_pixel_id=meta_pixel_id,
        revision_request=revision_request,
    )
    fallback = WebsiteProject(
        html=fallback_html,
        files=_fallback_project_files(company_name, fallback_html),
        engine="fallback_modular_renderer",
        warnings=["llm_project_generation_unavailable"],
    )

    from app.core.config import get_settings

    settings = get_settings()
    if not settings.openai_api_key and not settings.anthropic_api_key:
        return fallback

    # For code generation, prefer the agent-coder model when available.
    provider = "anthropic" if settings.anthropic_api_key else "openai"
    system_prompt = _system_prompt()
    user_prompt = _user_prompt(
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

    try:
        from app.agents.llm_client import call_simple

        resp = await call_simple(system_prompt, user_prompt, provider=provider, max_tokens=12000)
        parsed = _parse_json_object(resp.content)
        files = _normalize_files(parsed.get("files"))
        html = str(parsed.get("entry_html") or parsed.get("html") or "").strip()
        warnings = _validate_project(files, html)
        if not html or "<html" not in html.lower() or "</html>" not in html.lower():
            logger.warning("website_project_missing_html", company_name=company_name)
            fallback.warnings.append("llm_project_missing_entry_html")
            fallback.provider = resp.provider
            fallback.model = resp.model
            fallback.token_stats = [_token_stats(resp)]
            return fallback

        for path, content in _fallback_project_files(company_name, html).items():
            files.setdefault(path, content)

        return WebsiteProject(
            html=html,
            files=files,
            engine="llm_engineering_project",
            provider=resp.provider,
            model=resp.model,
            token_stats=[_token_stats(resp)],
            warnings=warnings,
        )
    except Exception as exc:
        logger.warning("website_project_generation_failed", error=str(exc), company_name=company_name)
        fallback.warnings.append(f"llm_project_error:{str(exc)[:120]}")
        return fallback


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
        "Return only valid JSON. No markdown fences. No commentary."
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
        "Return a JSON object with exactly these top-level keys:\n"
        "- files: object where keys are file paths and values are complete file contents.\n"
        "- entry_html: complete self-contained production HTML for our current gateway.\n\n"
        "Required file paths inside files:\n"
        + "\n".join(f"- {path}" for path in REQUIRED_PROJECT_FILES)
        + "\n\n"
        "Rules for the website:\n"
        "- The page must look intentionally designed for this exact business category.\n"
        "- E-commerce must show product image, concrete benefits, price/offer area, trust, and checkout CTA.\n"
        "- SaaS must show UI mockup, integrations/proof, pricing, and trial/demo CTA.\n"
        "- App/mobile must show a phone mockup, screens, waitlist/store CTA.\n"
        "- Local service/consultant must show offer, proof, process, booking CTA.\n"
        "- If product_image_url is present, use it prominently and do not replace it with random stock photos.\n"
        "- If product_image_url is missing, create a premium CSS product mockup instead of using unrelated photos.\n"
        "- Do not invent testimonials, certifications, medical claims, revenue numbers, or legal claims.\n"
        "- entry_html must include CSS in a <style> tag because our gateway serves one HTML artifact.\n"
        "- Include responsive mobile design, strong first viewport, visible CTA, and no empty sections.\n"
        "- Include only safe external links from provided URLs.\n"
        "- File contents can be concise but realistic: Express server, EJS partials, CSS theme, email route, migration stub.\n\n"
        "Business context JSON:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _parse_json_object(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
        if match:
            text = match.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("website_project_response_not_object")
    return parsed


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


def _validate_project(files: dict[str, str], html: str) -> list[str]:
    warnings: list[str] = []
    missing = [path for path in REQUIRED_PROJECT_FILES if path not in files]
    if missing:
        warnings.append("missing_project_files:" + ",".join(missing[:8]))
    if len(html) < 5000:
        warnings.append("entry_html_short")
    return warnings


def _fallback_project_files(company_name: str, html: str) -> dict[str, str]:
    safe_name = company_name or "Generated Site"
    return {
        "CLAUDE.md": f"# {safe_name}\n\nGenerated website project manifest.\n",
        "package.json": json.dumps({
            "scripts": {"start": "node server.js"},
            "dependencies": {"express": "^4.19.2", "ejs": "^3.1.10"},
        }, indent=2),
        "server.js": (
            "const express = require('express');\n"
            "const app = express();\n"
            "app.get('/', (_req, res) => res.send(require('fs').readFileSync('public/index.html', 'utf8')));\n"
            "app.listen(process.env.PORT || 3000);\n"
        ),
        "render.yaml": "services:\n  - type: web\n    env: node\n    startCommand: npm start\n",
        "migrate.js": "console.log('No database migration required for static landing page.');\n",
        "db/index.js": "module.exports = {};\n",
        "routes/api/email.js": "module.exports = require('express').Router();\n",
        "views/layout.ejs": html,
        "views/partials/nav.ejs": "",
        "views/partials/hero.ejs": "",
        "views/partials/proof.ejs": "",
        "views/partials/closing.ejs": "",
        "public/css/theme.css": "",
        "public/index.html": html,
    }


def _json_or_text(value: str) -> Any:
    try:
        return json.loads(value) if value else {}
    except Exception:
        return value


def _token_stats(resp) -> TokenStats:
    return TokenStats(
        provider=resp.provider,
        model=resp.model,
        input_tokens=resp.input_tokens,
        output_tokens=resp.output_tokens,
        total_tokens=resp.input_tokens + resp.output_tokens,
    )
