"""Tool: generate_video — AI video generation for Meta ads (9:16 vertical)."""
from __future__ import annotations

import json

import httpx
import structlog

from app.agents.tools import ToolDefinition

logger = structlog.get_logger()

GENERATE_VIDEO_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {
            "type": "string",
            "description": "Video scene description for vertical 9:16 ad, 15-30 seconds.",
        },
        "duration_seconds": {
            "type": "integer",
            "description": "Target duration 15-30s.",
            "default": 15,
        },
    },
    "required": ["prompt"],
}


async def _generate_via_replicate(prompt: str, duration: int = 15) -> str | None:
    from app.core.config import get_settings
    settings = get_settings()
    if not settings.replicate_api_token:
        return None

    # Use a text-to-video model on Replicate (fallback when Sora API unavailable)
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.replicate.com/v1/predictions",
            headers={
                "Authorization": f"Token {settings.replicate_api_token}",
                "Content-Type": "application/json",
            },
            json={
                "version": "minimax/video-01-live",
                "input": {
                    "prompt": prompt,
                    "duration": min(30, max(5, duration)),
                },
            },
        )
        if resp.status_code != 201:
            logger.warning("replicate_video_failed", status=resp.status_code)
            return None
        prediction = resp.json()
        poll_url = prediction.get("urls", {}).get("get", "")

        for _ in range(60):
            import asyncio
            await asyncio.sleep(5)
            poll = await client.get(
                poll_url,
                headers={"Authorization": f"Token {settings.replicate_api_token}"},
            )
            data = poll.json()
            if data.get("status") == "succeeded":
                output = data.get("output")
                if isinstance(output, list) and output:
                    return output[0]
                if isinstance(output, str):
                    return output
                return None
            if data.get("status") == "failed":
                return None
    return None


def create_generate_video_tool(company_id: str = "", company_slug: str = "") -> ToolDefinition:
    async def execute(prompt: str, duration_seconds: int = 15) -> str:
        video_url = await _generate_via_replicate(prompt, duration_seconds)
        if not video_url:
            return json.dumps({
                "generated": False,
                "error": "Video generation unavailable — configure REPLICATE_API_TOKEN",
            })

        from app.agents.tools.store_asset import _execute_store_asset
        if not company_id:
            return json.dumps({"generated": True, "video_url": video_url, "stored": False})
        raw = await _execute_store_asset(
            company_id,
            f"ad-video-{duration_seconds}s.mp4",
            video_url,
            "video",
        )
        stored = json.loads(raw)
        return json.dumps({
            "generated": True,
            "video_url": stored.get("public_url", video_url),
            "asset_id": stored.get("asset_id"),
        })

    return ToolDefinition(
        name="generate_video",
        description=(
            "Generate a vertical 9:16 video ad (15-30s) from a text prompt. "
            "Returns a hosted video URL for Meta Ads upload."
        ),
        parameters=GENERATE_VIDEO_SCHEMA,
        execute=execute,
    )
