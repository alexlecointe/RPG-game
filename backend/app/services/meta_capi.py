"""Meta Conversions API (CAPI) — send Purchase events from Stripe payments."""
from __future__ import annotations

import hashlib
import time
from typing import Optional

import httpx
import structlog

from app.core.config import get_settings

logger = structlog.get_logger()
META_GRAPH = "https://graph.facebook.com/v21.0"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


async def send_purchase_event(
    payment_intent_id: str,
    value_cents: int,
    currency: str = "usd",
    customer_email: Optional[str] = None,
    customer_ip: Optional[str] = None,
    event_source_url: Optional[str] = None,
) -> dict:
    """Send a Purchase event to Meta CAPI.

    - event_id = payment_intent_id for deduplication with browser Pixel
    - value = amount in major currency unit (cents → dollars)
    - email hashed with SHA-256 if provided
    """
    settings = get_settings()
    if not settings.meta_pixel_id or not settings.meta_capi_token:
        logger.info("meta_capi_skipped", reason="not_configured")
        return {"skipped": True, "reason": "not_configured"}

    value = round(value_cents / 100, 2)
    event_time = int(time.time())

    user_data: dict = {}
    if customer_email:
        user_data["em"] = [_sha256(customer_email)]
    if customer_ip:
        user_data["client_ip_address"] = customer_ip

    event = {
        "event_name": "Purchase",
        "event_time": event_time,
        "event_id": payment_intent_id,
        "action_source": "website",
        "user_data": user_data,
        "custom_data": {
            "currency": currency.lower(),
            "value": value,
        },
    }
    if event_source_url:
        event["event_source_url"] = event_source_url

    payload = {
        "data": [event],
        "access_token": settings.meta_capi_token,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{META_GRAPH}/{settings.meta_pixel_id}/events",
                json=payload,
            )
            result = resp.json()
            if resp.status_code == 200:
                logger.info(
                    "meta_capi_purchase_sent",
                    payment_intent_id=payment_intent_id,
                    value=value,
                    currency=currency,
                    events_received=result.get("events_received"),
                )
                return {"sent": True, "events_received": result.get("events_received")}
            else:
                logger.warning(
                    "meta_capi_purchase_failed",
                    status=resp.status_code,
                    error=result,
                )
                return {"skipped": True, "reason": "api_error", "detail": result}
    except Exception as exc:
        logger.warning("meta_capi_purchase_error", error=str(exc))
        return {"skipped": True, "reason": "exception", "detail": str(exc)}
