"""Stripe Connect Express — Polsia-like platform payouts."""
from __future__ import annotations

import httpx
import structlog

from app.core.config import get_settings
from app.models.entities import Company

logger = structlog.get_logger()
STRIPE_API = "https://api.stripe.com/v1"


def _headers(secret_key: str) -> dict:
    return {"Authorization": f"Bearer {secret_key}"}


def get_stripe_status(company: Company) -> str:
    """Return not_started | pending | ready."""
    if not company.stripe_connect_account_id:
        return "not_started"
    return "pending"  # refreshed async via API when needed


async def fetch_connect_status(account_id: str) -> dict:
    settings = get_settings()
    if not settings.stripe_secret_key or not account_id:
        return {"status": "not_started"}

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{STRIPE_API}/accounts/{account_id}",
            headers=_headers(settings.stripe_secret_key),
        )
        resp.raise_for_status()
        data = resp.json()

    charges = data.get("charges_enabled", False)
    payouts = data.get("payouts_enabled", False)
    details = data.get("details_submitted", False)

    if charges and payouts and details:
        status = "ready"
    elif details:
        status = "pending"
    else:
        status = "not_started"

    return {
        "status": status,
        "charges_enabled": charges,
        "payouts_enabled": payouts,
        "details_submitted": details,
    }


async def ensure_connect_account(company: Company, db) -> str:
    """Create Connect Express account if missing."""
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise ValueError("stripe_not_configured")

    if company.stripe_connect_account_id:
        return company.stripe_connect_account_id

    data = {
        "type": "express",
        "metadata[company_id]": company.id,
        "metadata[company_slug]": company.slug or "",
        "business_profile[name]": company.name[:200],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{STRIPE_API}/accounts",
            headers=_headers(settings.stripe_secret_key),
            data=data,
        )
        resp.raise_for_status()
        account = resp.json()

    company.stripe_connect_account_id = account["id"]
    await db.commit()
    logger.info("stripe_connect_created", company_id=company.id, account_id=account["id"])
    return account["id"]


async def create_onboarding_link(company: Company, db) -> dict:
    settings = get_settings()
    account_id = await ensure_connect_account(company, db)

    data = {
        "account": account_id,
        "refresh_url": settings.stripe_connect_refresh_url,
        "return_url": settings.stripe_connect_return_url,
        "type": "account_onboarding",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{STRIPE_API}/account_links",
            headers=_headers(settings.stripe_secret_key),
            data=data,
        )
        resp.raise_for_status()
        link = resp.json()

    return {"url": link.get("url", ""), "expires_at": link.get("expires_at")}
