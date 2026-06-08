"""Tool: generate_video — AI video generation for Meta ads (9:16 vertical).

Provider chain (in order of preference):
  1. OpenAI Sora — if OPENAI_API_KEY + OPENAI_VIDEO_MODEL are set
  2. Replicate minimax/video-01-live — if REPLICATE_API_TOKEN is set
  3. Error — with clear message for the agent

Videos are stored as company assets when company_id is provided.
"""
from __future__ import annotations

import asyncio
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
            "description": (
                "Video scene description for vertical 9:16 ad, 15-30 seconds. "
                "Be specific: product shown, action, mood, text overlays if any."
            ),
        },
        "duration_seconds": {
            "type": "integer",
            "description": "Target duration 5-30s. Default 15.",
            "default": 15,
        },
        "aspect_ratio": {
            "type": "string",
            "enum": ["9:16", "16:9", "1:1"],
            "default": "9:16",
            "description": "9:16 vertical for Meta Reels/Stories (recommended for ads).",
        },
    },
    "required": ["prompt"],
}

OPENAI_VIDEO_API = "https://api.openai.com/v1/videos/generations"
REPLICATE_API = "https://api.replicate.com/v1/predictions"


async def _generate_via_openai(
    prompt: str,
    duration: int = 15,
    aspect_ratio: str = "9:16",
) -> str | None:
    """Generate video via OpenAI Sora API (polling until completed)."""
    from app.core.config import get_settings
    settings = get_settings()
    if not settings.openai_api_key or not settings.openai_video_model:
        return None

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            OPENAI_VIDEO_API,
            headers=headers,
            json={
                "model": settings.openai_video_model,
                "prompt": prompt,
                "duration": min(30, max(5, duration)),
                "size": "1080x1920" if aspect_ratio == "9:16" else (
                    "1920x1080" if aspect_ratio == "16:9" else "1080x1080"
                ),
                "n": 1,
            },
        )
        if resp.status_code not in (200, 202):
            logger.warning(
                "openai_video_create_failed",
                status=resp.status_code,
                body=resp.text[:300],
            )
            return None

        data = resp.json()

    # Immediate result (synchronous model response)
    if data.get("status") == "completed" and data.get("data"):
        video_data = data["data"][0]
        return video_data.get("url") or video_data.get("b64_json")

    # Async job — poll by job id
    job_id = data.get("id")
    if not job_id:
        logger.warning("openai_video_no_job_id", response_keys=list(data.keys()))
        return None

    logger.info("openai_video_polling", job_id=job_id, model=settings.openai_video_model)

    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(120):  # max 10 min (5s intervals)
            await asyncio.sleep(5)
            poll = await client.get(
                f"{OPENAI_VIDEO_API}/{job_id}",
                headers=headers,
            )
            if poll.status_code != 200:
                continue
            result = poll.json()
            status = result.get("status", "")
            if status == "completed":
                video_list = result.get("data", [])
                if video_list:
                    url = video_list[0].get("url") or video_list[0].get("b64_json")
                    logger.info("openai_video_completed", job_id=job_id, attempt=attempt)
                    return url
                return None
            if status in ("failed", "cancelled"):
                logger.warning(
                    "openai_video_failed",
                    job_id=job_id,
                    status=status,
                    error=result.get("error"),
                )
                return None

    logger.warning("openai_video_timeout", job_id=job_id)
    return None


async def _generate_via_replicate(
    prompt: str,
    duration: int = 15,
    aspect_ratio: str = "9:16",
) -> str | None:
    """Generate video via Replicate minimax/video-01-live model (polling)."""
    from app.core.config import get_settings
    settings = get_settings()
    if not settings.replicate_api_token:
        return None

    headers = {
        "Authorization": f"Token {settings.replicate_api_token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            REPLICATE_API,
            headers=headers,
            json={
                "version": "minimax/video-01-live",
                "input": {
                    "prompt": prompt,
                    "duration": min(30, max(5, duration)),
                    "aspect_ratio": aspect_ratio,
                },
            },
        )
        if resp.status_code != 201:
            logger.warning("replicate_video_create_failed", status=resp.status_code)
            return None
        prediction = resp.json()

    poll_url = prediction.get("urls", {}).get("get", "")
    if not poll_url:
        return None

    logger.info("replicate_video_polling", prediction_id=prediction.get("id"))

    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(60):  # max 5 min
            await asyncio.sleep(5)
            poll = await client.get(
                poll_url,
                headers={"Authorization": f"Token {settings.replicate_api_token}"},
            )
            data = poll.json()
            status = data.get("status", "")
            if status == "succeeded":
                output = data.get("output")
                if isinstance(output, list) and output:
                    logger.info("replicate_video_completed", attempt=attempt)
                    return output[0]
                if isinstance(output, str):
                    return output
                return None
            if status == "failed":
                logger.warning("replicate_video_failed", error=data.get("error"))
                return None

    logger.warning("replicate_video_timeout")
    return None


async def generate_video(
    prompt: str,
    duration_seconds: int = 15,
    aspect_ratio: str = "9:16",
) -> str | None:
    """Try OpenAI Sora first, fall back to Replicate, return URL or None."""
    # Provider 1: OpenAI Sora
    from app.core.config import get_settings
    settings = get_settings()
    if settings.openai_api_key and settings.openai_video_model:
        url = await _generate_via_openai(prompt, duration_seconds, aspect_ratio)
        if url:
            logger.info("video_generated_via_openai", duration=duration_seconds)
            return url
        logger.warning("openai_video_unavailable_falling_back_to_replicate")

    # Provider 2: Replicate
    url = await _generate_via_replicate(prompt, duration_seconds, aspect_ratio)
    if url:
        logger.info("video_generated_via_replicate", duration=duration_seconds)
        return url

    return None


def create_generate_video_tool(company_id: str = "", company_slug: str = "") -> ToolDefinition:
    async def execute(
        prompt: str,
        duration_seconds: int = 15,
        aspect_ratio: str = "9:16",
    ) -> str:
        video_url = await generate_video(prompt, duration_seconds, aspect_ratio)
        if not video_url:
            return json.dumps({
                "generated": False,
                "error": (
                    "Video generation unavailable. "
                    "Configure OPENAI_VIDEO_MODEL + OPENAI_API_KEY (Sora) "
                    "or REPLICATE_API_TOKEN (Replicate minimax) to enable."
                ),
            })

        if not company_id:
            return json.dumps({"generated": True, "video_url": video_url, "stored": False})

        from app.agents.tools.store_asset import _execute_store_asset
        try:
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
                "stored": True,
            })
        except Exception as exc:
            logger.warning("video_store_failed", error=str(exc))
            return json.dumps({"generated": True, "video_url": video_url, "stored": False})

    return ToolDefinition(
        name="generate_video",
        description=(
            "Generate a vertical 9:16 video ad (5–30s) from a text prompt. "
            "Uses OpenAI Sora if configured, falls back to Replicate minimax. "
            "Returns a hosted video URL ready for Meta Ads upload."
        ),
        parameters=GENERATE_VIDEO_SCHEMA,
        execute=execute,
    )
