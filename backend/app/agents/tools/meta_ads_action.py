"""Tool: meta_ads_action — Meta Marketing API (campaigns, creatives, insights)."""
from __future__ import annotations

import json

import httpx

from app.agents.tools import ToolDefinition
from app.core.config import get_settings

META_GRAPH = "https://graph.facebook.com/v21.0"

META_ADS_ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "list_campaigns",
                "create_campaign",
                "create_ad_set",
                "upload_video",
                "create_ad_creative",
                "create_ad",
                "get_insights",
                "pause_campaign",
                "resume_campaign",
            ],
            "description": (
                "list_campaigns: list campaigns. "
                "create_campaign: create campaign (PAUSED by default). "
                "create_ad_set: create ad set. "
                "upload_video: upload video from URL. "
                "create_ad_creative: video ad creative. "
                "create_ad: link creative to ad set. "
                "get_insights: campaign metrics. "
                "pause_campaign / resume_campaign: update status."
            ),
        },
        "campaign_name": {"type": "string"},
        "objective": {"type": "string", "default": "OUTCOME_SALES"},
        "campaign_id": {"type": "string"},
        "ad_set_id": {"type": "string"},
        "ad_set_name": {"type": "string"},
        "daily_budget_cents": {"type": "integer"},
        "video_url": {"type": "string"},
        "video_id": {"type": "string"},
        "creative_id": {"type": "string"},
        "headline": {"type": "string"},
        "body": {"type": "string"},
        "link_url": {"type": "string"},
        "ad_name": {"type": "string"},
        "status": {"type": "string", "enum": ["ACTIVE", "PAUSED"]},
    },
    "required": ["action"],
}


def _act_id(ad_account_id: str) -> str:
    return ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"


async def list_campaigns(access_token: str, ad_account_id: str) -> dict:
    act = _act_id(ad_account_id)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{META_GRAPH}/{act}/campaigns",
            params={
                "access_token": access_token,
                "fields": "id,name,status,objective,daily_budget",
                "limit": 25,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return {"campaigns": data.get("data", []), "count": len(data.get("data", []))}


async def create_campaign(
    access_token: str,
    ad_account_id: str,
    campaign_name: str,
    objective: str = "OUTCOME_SALES",
    status: str = "PAUSED",
) -> dict:
    act = _act_id(ad_account_id)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{META_GRAPH}/{act}/campaigns",
            data={
                "access_token": access_token,
                "name": campaign_name or "RPG Campaign",
                "objective": objective or "OUTCOME_SALES",
                "status": status,
                "special_ad_categories": "[]",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return {"created": True, "campaign_id": data.get("id"), "status": status}


async def create_ad_set(
    access_token: str,
    ad_account_id: str,
    campaign_id: str,
    ad_set_name: str,
    daily_budget_cents: int = 1000,
    status: str = "PAUSED",
) -> dict:
    act = _act_id(ad_account_id)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{META_GRAPH}/{act}/adsets",
            data={
                "access_token": access_token,
                "name": ad_set_name or "RPG Ad Set",
                "campaign_id": campaign_id,
                "daily_budget": str(daily_budget_cents or 1000),
                "billing_event": "IMPRESSIONS",
                "optimization_goal": "LINK_CLICKS",
                "bid_amount": "200",
                "status": status,
                "targeting": json.dumps({"geo_locations": {"countries": ["FR"]}}),
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return {"created": True, "ad_set_id": data.get("id"), "status": status}


async def upload_video(
    access_token: str,
    ad_account_id: str,
    video_url: str,
    title: str = "",
) -> dict:
    act = _act_id(ad_account_id)
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{META_GRAPH}/{act}/advideos",
            data={
                "access_token": access_token,
                "file_url": video_url,
                "title": title or "RPG Ad Video",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return {"video_id": data.get("id"), "uploaded": True}


async def create_ad_creative(
    access_token: str,
    ad_account_id: str,
    video_id: str,
    headline: str,
    body: str,
    link_url: str,
    page_id: str | None = None,
) -> dict:
    settings = get_settings()
    page = page_id or getattr(settings, "meta_page_id", "") or ""
    act = _act_id(ad_account_id)

    object_story_spec = {
        "page_id": page,
        "video_data": {
            "video_id": video_id,
            "title": headline or "Ad",
            "message": body or "",
            "call_to_action": {
                "type": "SHOP_NOW",
                "value": {"link": link_url or "https://example.com"},
            },
        },
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{META_GRAPH}/{act}/adcreatives",
            data={
                "access_token": access_token,
                "name": headline or "RPG Creative",
                "object_story_spec": json.dumps(object_story_spec),
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return {"creative_id": data.get("id"), "created": True}


async def create_ad(
    access_token: str,
    ad_account_id: str,
    ad_set_id: str,
    creative_id: str,
    ad_name: str = "",
    status: str = "PAUSED",
) -> dict:
    act = _act_id(ad_account_id)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{META_GRAPH}/{act}/ads",
            data={
                "access_token": access_token,
                "name": ad_name or "RPG Ad",
                "adset_id": ad_set_id,
                "creative": json.dumps({"creative_id": creative_id}),
                "status": status,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return {"ad_id": data.get("id"), "status": status}


async def get_insights(access_token: str, campaign_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{META_GRAPH}/{campaign_id}/insights",
            params={
                "access_token": access_token,
                "fields": "spend,impressions,clicks,ctr,cpc",
                "date_preset": "today",
            },
        )
        resp.raise_for_status()
        rows = resp.json().get("data", [])
    return {"insights": rows, "count": len(rows)}


async def update_campaign_status(
    access_token: str,
    campaign_id: str,
    status: str,
) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{META_GRAPH}/{campaign_id}",
            data={"access_token": access_token, "status": status},
        )
        resp.raise_for_status()
        data = resp.json()
    return {"campaign_id": campaign_id, "status": data.get("status", status)}


def create_meta_ads_action_tool(access_token: str, ad_account_id: str) -> ToolDefinition:
    async def execute(
        action: str,
        campaign_name: str = "",
        objective: str = "OUTCOME_SALES",
        campaign_id: str = "",
        ad_set_id: str = "",
        ad_set_name: str = "",
        daily_budget_cents: int = 1000,
        video_url: str = "",
        video_id: str = "",
        creative_id: str = "",
        headline: str = "",
        body: str = "",
        link_url: str = "",
        ad_name: str = "",
        status: str = "PAUSED",
    ) -> str:
        if not ad_account_id:
            return json.dumps({"error": "META_AD_ACCOUNT_ID not configured"})
        try:
            if action == "list_campaigns":
                result = await list_campaigns(access_token, ad_account_id)
            elif action == "create_campaign":
                if not campaign_name:
                    return json.dumps({"error": "campaign_name required"})
                result = await create_campaign(
                    access_token, ad_account_id, campaign_name, objective, status
                )
            elif action == "create_ad_set":
                if not campaign_id:
                    return json.dumps({"error": "campaign_id required"})
                result = await create_ad_set(
                    access_token,
                    ad_account_id,
                    campaign_id,
                    ad_set_name,
                    daily_budget_cents,
                    status,
                )
            elif action == "upload_video":
                if not video_url:
                    return json.dumps({"error": "video_url required"})
                result = await upload_video(access_token, ad_account_id, video_url, headline)
            elif action == "create_ad_creative":
                if not video_id:
                    return json.dumps({"error": "video_id required"})
                result = await create_ad_creative(
                    access_token, ad_account_id, video_id, headline, body, link_url
                )
            elif action == "create_ad":
                if not ad_set_id or not creative_id:
                    return json.dumps({"error": "ad_set_id and creative_id required"})
                result = await create_ad(
                    access_token, ad_account_id, ad_set_id, creative_id, ad_name, status
                )
            elif action == "get_insights":
                if not campaign_id:
                    return json.dumps({"error": "campaign_id required"})
                result = await get_insights(access_token, campaign_id)
            elif action == "pause_campaign":
                if not campaign_id:
                    return json.dumps({"error": "campaign_id required"})
                result = await update_campaign_status(access_token, campaign_id, "PAUSED")
            elif action == "resume_campaign":
                if not campaign_id:
                    return json.dumps({"error": "campaign_id required"})
                result = await update_campaign_status(access_token, campaign_id, "ACTIVE")
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
            "Manage Meta Ads via Marketing API: campaigns, ad sets, video upload, "
            "creatives, ads, insights, pause/resume."
        ),
        parameters=META_ADS_ACTION_SCHEMA,
        execute=execute,
    )
