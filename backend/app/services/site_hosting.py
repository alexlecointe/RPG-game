"""Shared site hosting service.

Replaces per-company Render deployments with a single shared gateway.
All landing pages are stored as SiteArtifact rows and served via
GET /sites/{slug} on our own backend.

URL pattern:
  - Dev / MVP:  {BACKEND_PUBLIC_URL}/sites/{slug}
  - Production: https://{slug}.rpgagent.app  (once domain is configured)
"""
from __future__ import annotations

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
