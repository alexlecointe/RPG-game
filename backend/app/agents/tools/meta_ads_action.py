"""Tool: meta_ads_action — Meta Marketing API (campaigns en mode PAUSED)."""
from __future__ import annotations

import json

import httpx

from app.agents.tools import ToolDefinition

META_GRAPH = "https://graph.facebook.com/v21.0"

META_ADS_ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["list_campaigns", "create_campaign", "create_ad_set"],
            "description": (
                "list_campaigns: list existing campaigns. "
                "create_campaign: create a PAUSED campaign. "
                "create_ad_set: create a PAUSED ad set in a campaign."
            ),
        },
        "campaign_name": {
            "type": "string",
            "description": "Campaign name (for create_campaign).",
        },
        "objective": {
            "type": "string",
            "description": "Campaign objective, e.g. OUTCOME_SALES, OUTCOME_TRAFFIC.",
            "default": "OUTCOME_SALES",
        },
        "campaign_id": {
            "type": "string",
            "description": "Parent campaign ID (for create_ad_set).",
        },
        "ad_set_name": {
            "type": "string",
            "description": "Ad set name (for create_ad_set).",
        },
        "daily_budget_cents": {
            "type": "integer",
            "description": "Daily budget in cents (for create_ad_set).",
        },
    },
    "required": ["action"],
}


async def _list_campaigns(access_token: str, ad_account_id: str) -> dict:
    act_id = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{META_GRAPH}/{act_id}/campaigns",
            params={
                "access_token": access_token,
                "fields": "id,name,status,objective,daily_budget",
                "limit": 25,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return {"campaigns": data.get("data", []), "count": len(data.get("data", []))}


async def _create_campaign(
    access_token: str,
    ad_account_id: str,
    campaign_name: str,
    objective: str = "OUTCOME_SALES",
) -> dict:
    act_id = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{META_GRAPH}/{act_id}/campaigns",
            data={
                "access_token": access_token,
                "name": campaign_name or "RPG Campaign",
                "objective": objective or "OUTCOME_SALES",
                "status": "PAUSED",
                "special_ad_categories": "[]",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return {"created": True, "campaign_id": data.get("id"), "status": "PAUSED"}


async def _create_ad_set(
    access_token: str,
    ad_account_id: str,
    campaign_id: str,
    ad_set_name: str,
    daily_budget_cents: int = 1000,
) -> dict:
    act_id = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{META_GRAPH}/{act_id}/adsets",
            data={
                "access_token": access_token,
                "name": ad_set_name or "RPG Ad Set",
                "campaign_id": campaign_id,
                "daily_budget": str(daily_budget_cents or 1000),
                "billing_event": "IMPRESSIONS",
                "optimization_goal": "LINK_CLICKS",
                "bid_amount": "200",
                "status": "PAUSED",
                "targeting": json.dumps({"geo_locations": {"countries": ["FR"]}}),
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return {"created": True, "ad_set_id": data.get("id"), "status": "PAUSED"}


def create_meta_ads_action_tool(access_token: str, ad_account_id: str) -> ToolDefinition:
    async def execute(
        action: str,
        campaign_name: str = "",
        objective: str = "OUTCOME_SALES",
        campaign_id: str = "",
        ad_set_name: str = "",
        daily_budget_cents: int = 1000,
    ) -> str:
        if not ad_account_id:
            return json.dumps({"error": "META_AD_ACCOUNT_ID not configured"})
        try:
            if action == "list_campaigns":
                result = await _list_campaigns(access_token, ad_account_id)
            elif action == "create_campaign":
                if not campaign_name:
                    return json.dumps({"error": "campaign_name required"})
                result = await _create_campaign(
                    access_token, ad_account_id, campaign_name, objective
                )
            elif action == "create_ad_set":
                if not campaign_id:
                    return json.dumps({"error": "campaign_id required"})
                result = await _create_ad_set(
                    access_token, ad_account_id, campaign_id, ad_set_name, daily_budget_cents
                )
            else:
                result = {"error": f"Unknown action: {action}"}
        except httpx.HTTPStatusError as exc:
            result = {
                "error": f"Meta API error: {exc.response.status_code} {exc.response.text[:400]}",
            }
        except Exception as exc:
            result = {"error": f"Meta Ads error: {exc}"}

        return json.dumps(result, default=str)

    return ToolDefinition(
        name="meta_ads_action",
        description=(
            "Manage Meta Ads campaigns via Marketing API. "
            "List campaigns, create PAUSED campaigns and ad sets for review before launch. "
            "Requires META_AD_ACCOUNT_ID configured."
        ),
        parameters=META_ADS_ACTION_SCHEMA,
        execute=execute,
    )
