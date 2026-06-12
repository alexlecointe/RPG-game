"""Public site gateway — serves company landing pages by slug.

GET  /sites/{slug}          → HTML of the live site
GET  /sites/{slug}/status   → JSON status (for iOS polling)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.deps import DbSession
from app.services.site_hosting import build_gateway_url, get_live_artifact, prepare_site_html_for_checkout

router = APIRouter()

# Checkout links can be created lazily while serving the site, so do not let
# browsers keep an old CTA that still points to a placeholder checkout URL.
_SITE_CACHE_CONTROL = "no-store"
# Status endpoint is polled during generation; cache briefly only.
_STATUS_CACHE_MAX_AGE = 10


@router.get("/sites/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def serve_site(slug: str, db: DbSession):
    """Serve the live landing page for the given company slug."""
    artifact = await get_live_artifact(db, slug)
    if not artifact:
        return HTMLResponse(
            content=_not_found_html(slug),
            status_code=404,
            headers={"Cache-Control": "no-store"},
        )

    etag = f'"{artifact.id}-v{artifact.version}"'
    html_content = await prepare_site_html_for_checkout(db, artifact)

    return HTMLResponse(
        content=html_content,
        status_code=200,
        headers={
            "Cache-Control": _SITE_CACHE_CONTROL,
            "ETag": etag,
            "X-Site-Version": str(artifact.version),
        },
    )


@router.get("/sites/{slug}/status")
async def site_status(slug: str, db: DbSession):
    """JSON status used by the iOS app to poll site readiness."""
    artifact = await get_live_artifact(db, slug)
    if not artifact:
        return JSONResponse(
            {"live": False, "site_url": None, "version": None},
            headers={"Cache-Control": f"max-age={_STATUS_CACHE_MAX_AGE}"},
        )
    return JSONResponse(
        {
            "live": True,
            "site_url": build_gateway_url(slug),
            "version": artifact.version,
            "published_at": artifact.published_at.isoformat(),
            "quality_score": artifact.quality_score,
        },
        headers={"Cache-Control": f"max-age={_STATUS_CACHE_MAX_AGE}"},
    )


def _not_found_html(slug: str) -> str:
    import html as _html
    safe_slug = _html.escape(slug)
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Site en cours de création</title>
  <style>
    body {{
      font-family: -apple-system, sans-serif;
      background: #0a0a0a;
      color: #e0e0e0;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
    }}
    .card {{
      text-align: center;
      padding: 40px;
      border: 1px solid #333;
      border-radius: 12px;
      max-width: 400px;
    }}
    h1 {{ font-size: 1.4rem; color: #00ff88; margin-bottom: 8px; }}
    p {{ color: #888; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>&#9889; Site en cours de création</h1>
    <p>Le site <strong>{safe_slug}</strong> est en cours de génération par vos agents IA.</p>
    <p>Revenez dans quelques instants.</p>
  </div>
</body>
</html>"""
