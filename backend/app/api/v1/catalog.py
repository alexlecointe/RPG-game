from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.agents.mission_catalog import MISSION_CATALOG, find_agent_for_task, get_catalog_for_agent
from app.api.deps import verify_api_key
from app.models.entities import AgentType
from app.schemas.api import MissionCatalogItem

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/missions", response_model=list[MissionCatalogItem])
async def list_catalog(agent_type: Optional[AgentType] = Query(None)):
    if agent_type:
        return get_catalog_for_agent(agent_type)
    return list(MISSION_CATALOG.values())


@router.get("/find-agent")
async def route_task(
    task_tag: str = Query("", description="Tag de la tâche (ex: meta_ads, research, engineering)"),
    mission_type: str = Query("", description="Type de mission exact (ex: landing_page)"),
):
    """Polsia-style routing: given a task tag or mission_type, returns the best agent."""
    agent = find_agent_for_task(task_tag=task_tag, mission_type=mission_type)
    catalog_item = MISSION_CATALOG.get(mission_type)
    return {
        "agent_type": agent.value,
        "confidence": "high" if mission_type in MISSION_CATALOG else "medium",
        "mission_type": mission_type or None,
        "credits_cost": catalog_item.credits_cost if catalog_item else None,
        "mcp_servers": _agent_mcp_map().get(agent, []),
    }


def _agent_mcp_map() -> dict[AgentType, list[str]]:
    return {
        AgentType.BUILDER: ["polsia_infra", "deploy_site", "infra_action"],
        AgentType.RESEARCHER: ["web_search", "web_scrape", "google_trends", "browser_action"],
        AgentType.MARKETER: ["web_search", "google_trends", "meta_ads_action"],
        AgentType.CONTENT: ["web_search", "generate_image", "store_asset", "x_action"],
        AgentType.OUTREACH: ["web_search", "send_email"],
        AgentType.SUPPORT: ["web_search", "send_email"],
        AgentType.FINANCE: ["stripe_action"],
        AgentType.ORCHESTRATOR: ["web_search", "query_learnings", "company_assets"],
    }
