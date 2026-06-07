from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.agents.mission_catalog import MISSION_CATALOG, get_catalog_for_agent
from app.api.deps import verify_api_key
from app.models.entities import AgentType
from app.schemas.api import MissionCatalogItem

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/missions", response_model=list[MissionCatalogItem])
async def list_catalog(agent_type: Optional[AgentType] = Query(None)):
    if agent_type:
        return get_catalog_for_agent(agent_type)
    return list(MISSION_CATALOG.values())
