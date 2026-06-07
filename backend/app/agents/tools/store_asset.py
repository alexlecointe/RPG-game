"""Tool: store_asset — Store company assets in R2 or local filesystem."""
from __future__ import annotations

import json
import mimetypes
import re
import uuid
from pathlib import Path

import httpx

from app.agents.tools import ToolDefinition

STORE_ASSET_SCHEMA = {
    "type": "object",
    "properties": {
        "company_id": {
            "type": "string",
            "description": "The company ID this asset belongs to.",
        },
        "filename": {
            "type": "string",
            "description": "Desired filename (e.g. 'hero-image.webp', 'logo.png').",
        },
        "content_url": {
            "type": "string",
            "description": "URL to download the asset from.",
        },
        "asset_type": {
            "type": "string",
            "enum": ["image", "document", "code"],
            "description": "Type of asset being stored.",
            "default": "image",
        },
    },
    "required": ["company_id", "filename", "content_url"],
}

ASSETS_ROOT = Path("data/assets")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _safe_filename(name: str) -> str:
    sanitized = re.sub(r"[^\w.\-]", "_", name)
    return sanitized[:100] or f"asset_{uuid.uuid4().hex[:8]}"


async def _save_asset_record(
    company_id: str,
    filename: str,
    asset_type: str,
    storage_key: str,
    public_url: str | None,
    size_bytes: int,
) -> str:
    from app.core.database import SessionLocal
    from app.models.entities import CompanyAsset

    async with SessionLocal() as db:
        asset = CompanyAsset(
            company_id=company_id,
            filename=filename,
            asset_type=asset_type,
            storage_key=storage_key,
            public_url=public_url,
            size_bytes=size_bytes,
        )
        db.add(asset)
        await db.commit()
        await db.refresh(asset)
        return asset.id


async def _execute_store_asset(
    company_id: str,
    filename: str,
    content_url: str,
    asset_type: str = "image",
) -> str:
    from app.core.config import get_settings

    settings = get_settings()
    safe_name = _safe_filename(filename)

    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(content_url)
            resp.raise_for_status()
            content = resp.content

            if len(content) > MAX_FILE_SIZE:
                return json.dumps({
                    "error": f"File too large ({len(content)} bytes, max {MAX_FILE_SIZE})",
                })

    except Exception as exc:
        return json.dumps({"error": f"Download failed: {exc}"})

    content_type = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
    storage_key = f"{company_id}/{asset_type}/{safe_name}"
    public_url: str | None = None

    if settings.r2_configured:
        try:
            from app.services.r2_storage import upload_bytes

            public_url = upload_bytes(storage_key, content, content_type)
        except Exception as exc:
            return json.dumps({"error": f"R2 upload failed: {exc}"})
    else:
        company_dir = ASSETS_ROOT / company_id / asset_type
        company_dir.mkdir(parents=True, exist_ok=True)
        dest = company_dir / safe_name
        if dest.exists():
            stem, suffix = dest.stem, dest.suffix
            safe_name = f"{stem}_{uuid.uuid4().hex[:6]}{suffix}"
            dest = company_dir / safe_name
            storage_key = f"{company_id}/{asset_type}/{safe_name}"
        dest.write_bytes(content)
        public_url = str(dest)

    asset_id = await _save_asset_record(
        company_id, safe_name, asset_type, storage_key, public_url, len(content)
    )

    return json.dumps({
        "stored": True,
        "asset_id": asset_id,
        "filename": safe_name,
        "storage": "r2" if settings.r2_configured else "local",
        "public_url": public_url,
        "size_bytes": len(content),
        "asset_type": asset_type,
        "company_id": company_id,
    })


def create_store_asset_tool() -> ToolDefinition:
    async def execute(
        company_id: str,
        filename: str,
        content_url: str,
        asset_type: str = "image",
    ) -> str:
        return await _execute_store_asset(company_id, filename, content_url, asset_type)

    return ToolDefinition(
        name="store_asset",
        description=(
            "Download and store a company asset (image, document, or code file) "
            "from a URL. Saves to Cloudflare R2 (or local fallback). "
            "Use after generating images or creating documents to persist them."
        ),
        parameters=STORE_ASSET_SCHEMA,
        execute=execute,
    )
