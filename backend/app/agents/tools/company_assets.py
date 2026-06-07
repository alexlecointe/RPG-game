"""Tool: company_assets — List stored assets for a company."""
from __future__ import annotations

import json

from sqlalchemy import select

from app.agents.tools import ToolDefinition

COMPANY_ASSETS_SCHEMA = {
    "type": "object",
    "properties": {
        "company_id": {
            "type": "string",
            "description": "The company ID to list assets for.",
        },
        "asset_type": {
            "type": "string",
            "enum": ["image", "document", "code", "all"],
            "description": "Filter by asset type (default: all).",
            "default": "all",
        },
    },
    "required": ["company_id"],
}


async def _execute_company_assets(company_id: str, asset_type: str = "all") -> str:
    from app.core.database import SessionLocal
    from app.models.entities import CompanyAsset

    async with SessionLocal() as db:
        stmt = select(CompanyAsset).where(CompanyAsset.company_id == company_id)
        if asset_type and asset_type != "all":
            stmt = stmt.where(CompanyAsset.asset_type == asset_type)
        stmt = stmt.order_by(CompanyAsset.created_at.desc()).limit(50)
        result = await db.execute(stmt)
        assets = result.scalars().all()

    if not assets:
        return json.dumps({
            "found": False,
            "count": 0,
            "assets": [],
            "message": "No assets stored yet for this company.",
        })

    return json.dumps({
        "found": True,
        "count": len(assets),
        "assets": [
            {
                "id": a.id,
                "filename": a.filename,
                "asset_type": a.asset_type,
                "public_url": a.public_url,
                "size_bytes": a.size_bytes,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in assets
        ],
    })


def create_company_assets_tool() -> ToolDefinition:
    async def execute(company_id: str, asset_type: str = "all") -> str:
        return await _execute_company_assets(company_id, asset_type)

    return ToolDefinition(
        name="company_assets",
        description=(
            "List all stored assets (images, documents, code) for a company. "
            "Use before creating new assets to avoid duplicates, or to reuse "
            "existing brand images and documents in new missions."
        ),
        parameters=COMPANY_ASSETS_SCHEMA,
        execute=execute,
    )
