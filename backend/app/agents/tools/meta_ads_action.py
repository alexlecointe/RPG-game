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
                "get_ad_account",
                "list_campaigns",
                "create_campaign",
                "create_ad_set",
                "upload_video",
                "get_video",
                "create_ad_creative",
                "create_ad",
                "list_ad_creatives",
                "get_insights",
                "pause_campaign",
                "resume_campaign",
                "update_campaign_budget",
                "create_custom_audience",
                "list_custom_audiences",
                "get_custom_audience",
                "create_lookalike_audience",
            ],
            "description": (
                "get_ad_account: get ad account info (id, currency, timezone). "
                "list_campaigns: list active campaigns. "
                "create_campaign: create campaign (PAUSED first, then activate). "
                "create_ad_set: create ad set with targeting, interests, custom_audience_ids. "
                "upload_video: upload video from URL to Meta. "
                "get_video: check video processing status (ready/processing). "
                "create_ad_creative: video ad creative with headline+body+CTA. "
                "create_ad: link creative to ad set. "
                "list_ad_creatives: list all ad creatives for the account. "
                "get_insights: campaign metrics (spend, CTR, ROAS). "
                "pause_campaign / resume_campaign: update status. "
                "update_campaign_budget: scale daily budget. "
                "create_custom_audience: create website/engagement custom audience (requires meta_pixel_id). "
                "list_custom_audiences: list all custom audiences for the account. "
                "get_custom_audience: get audience details + approximate_count + operation_status. "
                "create_lookalike_audience: create lookalike from a custom_audience_id source."
            ),
        },
        "campaign_name": {"type": "string"},
        "objective": {
            "type": "string",
            "enum": ["OUTCOME_SALES", "OUTCOME_APP_INSTALLS", "OUTCOME_LEADS"],
            "default": "OUTCOME_SALES",
            "description": "ecommerce=OUTCOME_SALES, app=OUTCOME_APP_INSTALLS, saas=OUTCOME_LEADS",
        },
        "campaign_id": {"type": "string"},
        "ad_set_id": {"type": "string"},
        "ad_set_name": {"type": "string"},
        "daily_budget_cents": {
            "type": "integer",
            "description": "Daily budget in cents (e.g. 1000 = 10 EUR)",
        },
        "video_url": {"type": "string"},
        "video_id": {"type": "string"},
        "creative_id": {"type": "string"},
        "headline": {"type": "string", "description": "Max 40 chars for Meta"},
        "body": {"type": "string"},
        "link_url": {"type": "string"},
        "ad_name": {"type": "string"},
        "status": {"type": "string", "enum": ["ACTIVE", "PAUSED"]},
        "call_to_action": {
            "type": "string",
            "enum": ["SHOP_NOW", "DOWNLOAD", "LEARN_MORE", "SIGN_UP", "GET_QUOTE"],
            "default": "SHOP_NOW",
            "description": "ecommerce=SHOP_NOW, app=DOWNLOAD, saas=LEARN_MORE or SIGN_UP",
        },
        "countries": {
            "type": "array",
            "items": {"type": "string"},
            "description": "ISO country codes, e.g. ['FR', 'BE', 'CH']",
        },
        "interests": {
            "type": "array",
            "items": {"type": "object"},
            "description": "Interest targeting objects e.g. [{\"id\": \"6003139266461\", \"name\": \"Sports & Fitness\"}]",
        },
        "age_min": {"type": "integer", "default": 18},
        "age_max": {"type": "integer", "default": 65},
        "date_preset": {
            "type": "string",
            "enum": ["today", "yesterday", "last_7_days", "last_30_days", "last_90_days"],
            "default": "last_7_days",
        },
        "level": {
            "type": "string",
            "enum": ["campaign", "adset", "ad"],
            "default": "campaign",
        },
        "source_campaign_id": {"type": "string"},
        "custom_audience_id": {
            "type": "string",
            "description": "Meta custom audience ID (source for lookalike or targeting exclusion).",
        },
        "custom_audience_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of custom audience IDs to include in ad set targeting.",
        },
        "audience_name": {
            "type": "string",
            "description": "Name for the custom audience to create.",
        },
        "audience_subtype": {
            "type": "string",
            "enum": ["WEBSITE", "ENGAGEMENT", "APP", "OFFLINE"],
            "default": "WEBSITE",
            "description": (
                "WEBSITE: pixel visitors (requires meta_pixel_id). "
                "ENGAGEMENT: people who engaged with your Facebook/Instagram page. "
            ),
        },
        "retention_days": {
            "type": "integer",
            "default": 30,
            "description": "How many days of activity to include. 30, 60, or 180 days.",
        },
        "ratio": {
            "type": "number",
            "default": 0.02,
            "description": "Lookalike ratio 0.01-0.10 (1%=similar, 10%=broader reach).",
        },
    },
    "required": ["action"],
}

# Maximum tool calls allowed per mission (full flow needs 10+)
META_ADS_MAX_CALLS = 14


def _act_id(ad_account_id: str) -> str:
    return ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"


async def get_ad_account(access_token: str, ad_account_id: str) -> dict:
    act = _act_id(ad_account_id)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{META_GRAPH}/{act}",
            params={
                "access_token": access_token,
                "fields": "id,currency,timezone_name,account_status,balance,spend_cap",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return {
        "ad_account_id": data.get("id"),
        "currency": data.get("currency"),
        "timezone": data.get("timezone_name"),
        "account_status": data.get("account_status"),
        "balance": data.get("balance"),
        "spend_cap": data.get("spend_cap"),
    }


async def get_video(access_token: str, video_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{META_GRAPH}/{video_id}",
            params={
                "access_token": access_token,
                "fields": "status,length,thumbnails,title",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    status_data = data.get("status", {})
    return {
        "video_id": video_id,
        "status": status_data.get("video_status", "unknown") if isinstance(status_data, dict) else status_data,
        "length": data.get("length"),
        "title": data.get("title"),
        "thumbnail_url": (data.get("thumbnails", {}).get("data", [{}])[0] or {}).get("uri"),
    }


async def list_ad_creatives(access_token: str, ad_account_id: str) -> dict:
    act = _act_id(ad_account_id)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{META_GRAPH}/{act}/adcreatives",
            params={
                "access_token": access_token,
                "fields": "id,name,status,effective_object_story_id",
                "limit": 25,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return {"creatives": data.get("data", []), "count": len(data.get("data", []))}


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
    countries: list[str] | None = None,
    age_min: int = 18,
    age_max: int = 65,
    objective: str = "OUTCOME_SALES",
    interests: list[dict] | None = None,
    custom_audience_ids: list[str] | None = None,
) -> dict:
    act = _act_id(ad_account_id)
    geo = countries or ["FR"]

    optimization_goal = {
        "OUTCOME_SALES": "LINK_CLICKS",
        "OUTCOME_APP_INSTALLS": "APP_INSTALLS",
        "OUTCOME_LEADS": "LEAD_GENERATION",
    }.get(objective, "LINK_CLICKS")

    targeting: dict = {
        "geo_locations": {"countries": geo},
        "age_min": age_min,
        "age_max": age_max,
    }
    if interests:
        targeting["interests"] = interests
    if custom_audience_ids:
        targeting["custom_audiences"] = [{"id": aid} for aid in custom_audience_ids]

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{META_GRAPH}/{act}/adsets",
            data={
                "access_token": access_token,
                "name": ad_set_name or "RPG Ad Set",
                "campaign_id": campaign_id,
                "daily_budget": str(daily_budget_cents or 1000),
                "billing_event": "IMPRESSIONS",
                "optimization_goal": optimization_goal,
                "bid_amount": "200",
                "status": status,
                "targeting": json.dumps(targeting),
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return {
        "created": True,
        "ad_set_id": data.get("id"),
        "status": status,
        "targeting": targeting,
    }


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
    call_to_action: str = "SHOP_NOW",
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
                "type": call_to_action or "SHOP_NOW",
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


async def get_insights(
    access_token: str,
    campaign_id: str,
    date_preset: str = "last_7_days",
    level: str = "campaign",
) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{META_GRAPH}/{campaign_id}/insights",
            params={
                "access_token": access_token,
                "fields": "spend,impressions,clicks,ctr,cpc,purchase_roas,actions",
                "date_preset": date_preset,
                "level": level,
            },
        )
        resp.raise_for_status()
        rows = resp.json().get("data", [])
    return {"insights": rows, "count": len(rows), "date_preset": date_preset}


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


async def update_campaign_budget(
    access_token: str,
    campaign_id: str,
    daily_budget_cents: int,
) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{META_GRAPH}/{campaign_id}",
            data={
                "access_token": access_token,
                "daily_budget": str(daily_budget_cents),
            },
        )
        resp.raise_for_status()
    return {"campaign_id": campaign_id, "daily_budget_cents": daily_budget_cents, "updated": True}


async def create_custom_audience(
    access_token: str,
    ad_account_id: str,
    name: str,
    subtype: str = "WEBSITE",
    retention_days: int = 30,
    countries: list[str] | None = None,
) -> dict:
    """Create a website or engagement custom audience.

    WEBSITE: requires meta_pixel_id to be configured.
    ENGAGEMENT: uses the Facebook page associated with the ad account.
    """
    act = _act_id(ad_account_id)

    payload: dict = {
        "access_token": access_token,
        "name": name,
        "subtype": subtype,
        "retention_days": str(min(180, max(1, retention_days))),
        "description": f"{name} — {subtype} audience ({retention_days}d)",
    }

    if subtype == "WEBSITE":
        settings = get_settings()
        pixel_id = settings.meta_pixel_id
        if not pixel_id:
            return {
                "error": "meta_pixel_id not configured — cannot create WEBSITE custom audience",
                "fix": "Set META_PIXEL_ID in environment variables",
            }
        payload["rule"] = json.dumps({
            "inclusions": {
                "operator": "or",
                "rules": [{
                    "event_sources": [{"id": pixel_id, "type": "pixel"}],
                    "retention_seconds": retention_days * 86400,
                    "filter": {
                        "operator": "and",
                        "filters": [{
                            "field": "event",
                            "operator": "eq",
                            "value": "PageView",
                        }],
                    },
                }],
            }
        })
    elif subtype == "ENGAGEMENT":
        # Engagement audience (page/Instagram profile)
        settings = get_settings()
        page_id = settings.meta_page_id
        if not page_id:
            return {
                "error": "meta_page_id not configured — cannot create ENGAGEMENT custom audience",
            }
        payload["rule"] = json.dumps({
            "inclusions": {
                "operator": "or",
                "rules": [{
                    "event_sources": [{"id": page_id, "type": "page"}],
                    "retention_seconds": retention_days * 86400,
                    "filter": {
                        "operator": "and",
                        "filters": [{
                            "field": "event",
                            "operator": "eq",
                            "value": "page_engaged",
                        }],
                    },
                }],
            }
        })

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{META_GRAPH}/{act}/customaudiences",
            data=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    return {
        "audience_id": data.get("id"),
        "name": name,
        "subtype": subtype,
        "retention_days": retention_days,
        "created": True,
        "note": "Audience will populate over the next few hours. Use get_custom_audience to check operation_status.",
    }


async def list_custom_audiences(access_token: str, ad_account_id: str) -> dict:
    """List custom audiences for the ad account with their status and size."""
    act = _act_id(ad_account_id)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{META_GRAPH}/{act}/customaudiences",
            params={
                "access_token": access_token,
                "fields": "id,name,subtype,approximate_count,operation_status,delivery_status,time_created",
                "limit": 25,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    audiences = data.get("data", [])
    return {
        "audiences": audiences,
        "count": len(audiences),
        "tip": "Use get_custom_audience with audience_id to check if ready (operation_status.code == 200).",
    }


async def get_custom_audience(access_token: str, audience_id: str) -> dict:
    """Get custom audience details: size, status, and whether it's ready for targeting."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{META_GRAPH}/{audience_id}",
            params={
                "access_token": access_token,
                "fields": "id,name,subtype,approximate_count,operation_status,delivery_status,time_created,retention_days",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    op_status = data.get("operation_status", {})
    is_ready = op_status.get("code", 0) == 200 if isinstance(op_status, dict) else False

    return {
        "audience_id": data.get("id"),
        "name": data.get("name"),
        "subtype": data.get("subtype"),
        "approximate_count": data.get("approximate_count"),
        "operation_status": op_status,
        "delivery_status": data.get("delivery_status"),
        "retention_days": data.get("retention_days"),
        "ready_for_targeting": is_ready,
        "note": (
            "Audience is ready for targeting and lookalike creation."
            if is_ready else
            "Audience is still populating. Check again in a few minutes."
        ),
    }


async def create_lookalike_audience(
    access_token: str,
    ad_account_id: str,
    custom_audience_id: str,
    ratio: float = 0.02,
    countries: list[str] | None = None,
    name: str = "",
) -> dict:
    """Create a lookalike audience from an existing custom audience.

    Requires a populated custom audience (check get_custom_audience: ready_for_targeting=true).
    Ratio: 0.01 (most similar 1%) to 0.10 (broader 10%).
    """
    act = _act_id(ad_account_id)
    geo = countries or ["FR"]
    audience_name = name or f"Lookalike {ratio*100:.0f}% {geo[0]} - {custom_audience_id[:8]}"

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{META_GRAPH}/{act}/customaudiences",
            data={
                "access_token": access_token,
                "name": audience_name,
                "subtype": "LOOKALIKE",
                "origin_audience_id": custom_audience_id,
                "lookalike_spec": json.dumps({
                    "type": "similarity",
                    "ratio": max(0.01, min(0.10, ratio)),
                    "country": geo[0],
                }),
            },
        )
        resp.raise_for_status()
        data = resp.json()

    return {
        "audience_id": data.get("id"),
        "name": audience_name,
        "source_custom_audience_id": custom_audience_id,
        "ratio": ratio,
        "country": geo[0],
        "created": True,
        "next_step": (
            f"Use create_ad_set with custom_audience_ids=[\"{data.get('id')}\"] "
            "to target this lookalike audience."
        ),
    }


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
        call_to_action: str = "SHOP_NOW",
        countries: list[str] | None = None,
        age_min: int = 18,
        age_max: int = 65,
        interests: list[dict] | None = None,
        custom_audience_ids: list[str] | None = None,
        custom_audience_id: str = "",
        audience_name: str = "",
        audience_subtype: str = "WEBSITE",
        retention_days: int = 30,
        date_preset: str = "last_7_days",
        level: str = "campaign",
        source_campaign_id: str = "",
        ratio: float = 0.02,
    ) -> str:
        if not ad_account_id:
            return json.dumps({"error": "META_AD_ACCOUNT_ID not configured"})
        try:
            if action == "get_ad_account":
                result = await get_ad_account(access_token, ad_account_id)
            elif action == "list_campaigns":
                result = await list_campaigns(access_token, ad_account_id)
            elif action == "list_ad_creatives":
                result = await list_ad_creatives(access_token, ad_account_id)
            elif action == "get_video":
                if not video_id:
                    return json.dumps({"error": "video_id required"})
                result = await get_video(access_token, video_id)
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
                    countries,
                    age_min,
                    age_max,
                    objective,
                    interests,
                    custom_audience_ids,
                )
            elif action == "upload_video":
                if not video_url:
                    return json.dumps({"error": "video_url required"})
                result = await upload_video(access_token, ad_account_id, video_url, headline)
            elif action == "create_ad_creative":
                if not video_id:
                    return json.dumps({"error": "video_id required"})
                result = await create_ad_creative(
                    access_token, ad_account_id, video_id, headline, body, link_url,
                    call_to_action=call_to_action,
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
                result = await get_insights(access_token, campaign_id, date_preset, level)
            elif action == "pause_campaign":
                if not campaign_id:
                    return json.dumps({"error": "campaign_id required"})
                result = await update_campaign_status(access_token, campaign_id, "PAUSED")
            elif action == "resume_campaign":
                if not campaign_id:
                    return json.dumps({"error": "campaign_id required"})
                result = await update_campaign_status(access_token, campaign_id, "ACTIVE")
            elif action == "update_campaign_budget":
                if not campaign_id or not daily_budget_cents:
                    return json.dumps({"error": "campaign_id and daily_budget_cents required"})
                result = await update_campaign_budget(access_token, campaign_id, daily_budget_cents)
            elif action == "create_custom_audience":
                if not audience_name:
                    return json.dumps({"error": "audience_name required"})
                result = await create_custom_audience(
                    access_token, ad_account_id, audience_name,
                    audience_subtype, retention_days, countries,
                )
            elif action == "list_custom_audiences":
                result = await list_custom_audiences(access_token, ad_account_id)
            elif action == "get_custom_audience":
                if not custom_audience_id:
                    return json.dumps({"error": "custom_audience_id required"})
                result = await get_custom_audience(access_token, custom_audience_id)
            elif action == "create_lookalike_audience":
                if not custom_audience_id:
                    # Legacy fallback: accept source_campaign_id for backward compat
                    if source_campaign_id:
                        return json.dumps({
                            "error": (
                                "source_campaign_id is not valid for lookalike creation. "
                                "You need a custom_audience_id. "
                                "First call create_custom_audience (WEBSITE or ENGAGEMENT), "
                                "then call get_custom_audience to confirm ready_for_targeting=true, "
                                "then call create_lookalike_audience with that custom_audience_id."
                            )
                        })
                    return json.dumps({"error": "custom_audience_id required"})
                result = await create_lookalike_audience(
                    access_token, ad_account_id, custom_audience_id,
                    ratio, countries, audience_name,
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
            "Manage Meta Ads via Marketing API: campaigns, ad sets (with interests + custom audiences), "
            "video upload, creatives, ads, insights, pause/resume, budget scaling. "
            "Audience workflow: create_custom_audience → get_custom_audience (wait ready_for_targeting) "
            "→ create_lookalike_audience → create_ad_set with custom_audience_ids. "
            f"Max {META_ADS_MAX_CALLS} calls per mission."
        ),
        parameters=META_ADS_ACTION_SCHEMA,
        execute=execute,
    )
