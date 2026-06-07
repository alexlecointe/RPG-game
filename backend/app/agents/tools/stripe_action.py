"""Tool: stripe_action — Stripe payment operations for the Banque building.

Allows agents to create checkout links, list products/prices, check balance,
and manage Stripe Connect Express accounts for merchant payouts.
"""
from __future__ import annotations

import json

import httpx

from app.agents.tools import ToolDefinition

STRIPE_API = "https://api.stripe.com/v1"

STRIPE_ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "create_checkout_link",
                "list_products",
                "get_balance",
                "create_connect_account",
                "create_account_link",
                "get_connect_status",
            ],
            "description": (
                "create_checkout_link: create a Stripe Checkout Session URL. "
                "list_products: list existing products and prices. "
                "get_balance: get current account balance. "
                "create_connect_account: create Stripe Connect Express account. "
                "create_account_link: generate onboarding link for Connect account. "
                "get_connect_status: check Connect account onboarding status."
            ),
        },
        "product_name": {
            "type": "string",
            "description": "Product name (for create_checkout_link).",
        },
        "amount_cents": {
            "type": "integer",
            "description": "Price in cents, e.g. 2900 for 29.00 EUR (for create_checkout_link).",
        },
        "currency": {
            "type": "string",
            "description": "ISO currency code (default: eur).",
            "default": "eur",
        },
        "success_url": {
            "type": "string",
            "description": "URL to redirect after successful payment.",
        },
        "cancel_url": {
            "type": "string",
            "description": "URL to redirect if customer cancels.",
        },
        "connect_account_id": {
            "type": "string",
            "description": "Stripe Connect account ID for destination charges.",
        },
        "refresh_url": {
            "type": "string",
            "description": "URL if onboarding link expires (create_account_link).",
        },
        "return_url": {
            "type": "string",
            "description": "URL after onboarding completes (create_account_link).",
        },
        "email": {
            "type": "string",
            "description": "Merchant email (create_connect_account).",
        },
    },
    "required": ["action"],
}


def _headers(secret_key: str) -> dict:
    return {"Authorization": f"Bearer {secret_key}"}


async def _create_checkout_link(
    secret_key: str,
    product_name: str,
    amount_cents: int,
    currency: str = "eur",
    success_url: str = "https://example.com/success",
    cancel_url: str = "https://example.com/cancel",
    company_slug: str = "",
    connect_account_id: str = "",
) -> dict:
    data: dict[str, str] = {
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "line_items[0][price_data][currency]": currency,
        "line_items[0][price_data][product_data][name]": product_name or "Product",
        "line_items[0][price_data][unit_amount]": str(amount_cents or 1000),
        "line_items[0][quantity]": "1",
    }
    if company_slug:
        data["metadata[company_slug]"] = company_slug
        data["payment_intent_data[metadata][company_slug]"] = company_slug
    if connect_account_id:
        data["payment_intent_data[transfer_data][destination]"] = connect_account_id

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{STRIPE_API}/checkout/sessions",
            headers=_headers(secret_key),
            data=data,
        )
        resp.raise_for_status()
        session_data = resp.json()

    return {
        "created": True,
        "checkout_url": session_data.get("url", ""),
        "session_id": session_data.get("id", ""),
        "amount": f"{(amount_cents or 1000) / 100:.2f} {currency.upper()}",
    }


async def _list_products(secret_key: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{STRIPE_API}/products",
            headers=_headers(secret_key),
            params={"limit": 20, "active": "true"},
        )
        resp.raise_for_status()
        products = resp.json().get("data", [])

        resp_prices = await client.get(
            f"{STRIPE_API}/prices",
            headers=_headers(secret_key),
            params={"limit": 50, "active": "true"},
        )
        resp_prices.raise_for_status()
        prices = resp_prices.json().get("data", [])

    price_map: dict[str, list] = {}
    for p in prices:
        pid = p.get("product", "")
        price_map.setdefault(pid, []).append({
            "price_id": p.get("id"),
            "amount": p.get("unit_amount", 0),
            "currency": p.get("currency", ""),
            "recurring": p.get("recurring"),
        })

    return {
        "products": [
            {
                "id": prod.get("id"),
                "name": prod.get("name"),
                "description": prod.get("description", ""),
                "prices": price_map.get(prod.get("id"), []),
            }
            for prod in products
        ],
        "count": len(products),
    }


async def _get_balance(secret_key: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{STRIPE_API}/balance",
            headers=_headers(secret_key),
        )
        resp.raise_for_status()
        data = resp.json()

    available = data.get("available", [])
    pending = data.get("pending", [])
    return {
        "available": [
            {"amount": b.get("amount", 0) / 100, "currency": b.get("currency")}
            for b in available
        ],
        "pending": [
            {"amount": b.get("amount", 0) / 100, "currency": b.get("currency")}
            for b in pending
        ],
    }


async def _create_connect_account(secret_key: str, email: str = "") -> dict:
    data: dict[str, str] = {
        "type": "express",
        "capabilities[card_payments][requested]": "true",
        "capabilities[transfers][requested]": "true",
    }
    if email:
        data["email"] = email

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{STRIPE_API}/accounts",
            headers=_headers(secret_key),
            data=data,
        )
        resp.raise_for_status()
        account = resp.json()

    return {
        "created": True,
        "account_id": account.get("id"),
        "type": account.get("type"),
    }


async def _create_account_link(
    secret_key: str,
    connect_account_id: str,
    refresh_url: str,
    return_url: str,
) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{STRIPE_API}/account_links",
            headers=_headers(secret_key),
            data={
                "account": connect_account_id,
                "refresh_url": refresh_url or "https://example.com/reauth",
                "return_url": return_url or "https://example.com/return",
                "type": "account_onboarding",
            },
        )
        resp.raise_for_status()
        link = resp.json()

    return {
        "created": True,
        "url": link.get("url"),
        "expires_at": link.get("expires_at"),
    }


async def _get_connect_status(secret_key: str, connect_account_id: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{STRIPE_API}/accounts/{connect_account_id}",
            headers=_headers(secret_key),
        )
        resp.raise_for_status()
        account = resp.json()

    return {
        "account_id": account.get("id"),
        "charges_enabled": account.get("charges_enabled"),
        "payouts_enabled": account.get("payouts_enabled"),
        "details_submitted": account.get("details_submitted"),
        "email": account.get("email"),
    }


async def _get_connect_account_for_slug(company_slug: str) -> str:
    if not company_slug:
        return ""
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.entities import Company

    async with SessionLocal() as db:
        result = await db.execute(select(Company).where(Company.slug == company_slug))
        company = result.scalar_one_or_none()
        return company.stripe_connect_account_id or "" if company else ""


def create_stripe_action_tool(
    secret_key: str,
    company_slug: str = "",
    default_connect_account_id: str = "",
) -> ToolDefinition:
    async def execute(
        action: str,
        product_name: str = "",
        amount_cents: int = 0,
        currency: str = "eur",
        success_url: str = "https://example.com/success",
        cancel_url: str = "https://example.com/cancel",
        connect_account_id: str = "",
        refresh_url: str = "https://example.com/reauth",
        return_url: str = "https://example.com/return",
        email: str = "",
        **_: object,
    ) -> str:
        acct_id = connect_account_id or default_connect_account_id
        if not acct_id and company_slug:
            acct_id = await _get_connect_account_for_slug(company_slug)
        try:
            if action == "create_checkout_link":
                if not product_name or not amount_cents:
                    return json.dumps({"error": "product_name and amount_cents required"})
                result = await _create_checkout_link(
                    secret_key, product_name, amount_cents, currency,
                    success_url, cancel_url, company_slug, acct_id,
                )
            elif action == "list_products":
                result = await _list_products(secret_key)
            elif action == "get_balance":
                result = await _get_balance(secret_key)
            elif action == "create_connect_account":
                result = await _create_connect_account(secret_key, email)
                if result.get("account_id") and company_slug:
                    await _persist_connect_account(company_slug, result["account_id"])
            elif action == "create_account_link":
                if not acct_id:
                    return json.dumps({"error": "connect_account_id required"})
                result = await _create_account_link(
                    secret_key, acct_id, refresh_url, return_url
                )
            elif action == "get_connect_status":
                if not acct_id:
                    return json.dumps({"error": "connect_account_id required"})
                result = await _get_connect_status(secret_key, acct_id)
            else:
                result = {"error": f"Unknown action: {action}"}
        except httpx.HTTPStatusError as exc:
            result = {"error": f"Stripe API error: {exc.response.status_code} {exc.response.text[:300]}"}
        except Exception as exc:
            result = {"error": f"Stripe error: {exc}"}

        return json.dumps(result, default=str)

    return ToolDefinition(
        name="stripe_action",
        description=(
            "Interact with Stripe for payment operations. "
            "Create checkout links, list products, check balance, "
            "and manage Stripe Connect Express accounts for merchant payouts."
        ),
        parameters=STRIPE_ACTION_SCHEMA,
        execute=execute,
    )


async def _persist_connect_account(company_slug: str, account_id: str) -> None:
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.entities import Company

    async with SessionLocal() as db:
        result = await db.execute(select(Company).where(Company.slug == company_slug))
        company = result.scalar_one_or_none()
        if company:
            company.stripe_connect_account_id = account_id
            await db.commit()
