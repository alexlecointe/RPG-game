"""Webhook endpoints for inbound services (email, payments, etc.)."""
from __future__ import annotations

import json
import re

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.entities import (
    Company, CompanyEmail, CompanyNotification,
    EmailDirection, NotificationType,
)

router = APIRouter()
logger = structlog.get_logger()


def _extract_slug_from_email(email: str) -> str | None:
    """Extract company slug from noreply@{slug}.domain.app address."""
    match = re.match(r".*@([^.]+)\.", email)
    return match.group(1) if match else None


@router.post("/webhooks/email/inbound")
async def inbound_email(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive inbound email from Resend webhook.

    Parses the recipient address to identify the company, then stores
    the message in company_emails for agent context.
    """
    body = await request.json()

    to_address = body.get("to", "")
    from_address = body.get("from", "")
    subject = body.get("subject", "")
    text_body = body.get("text", body.get("html", ""))

    slug = _extract_slug_from_email(to_address)
    if not slug:
        logger.warning("inbound_email_no_slug", to=to_address)
        return {"status": "ignored", "reason": "no_slug_match"}

    result = await db.execute(select(Company).where(Company.slug == slug))
    company = result.scalar_one_or_none()
    if not company:
        logger.warning("inbound_email_no_company", slug=slug)
        return {"status": "ignored", "reason": "company_not_found"}

    email = CompanyEmail(
        company_id=company.id,
        direction=EmailDirection.INBOUND,
        from_address=from_address,
        to_address=to_address,
        subject=subject,
        body=text_body[:10000],
        message_id=body.get("message_id", ""),
    )
    db.add(email)
    await db.commit()

    logger.info(
        "inbound_email_stored",
        company_id=company.id,
        from_address=from_address,
        subject=subject,
    )

    return {"status": "stored", "company_id": company.id}


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive Stripe webhook events (forwarded from company Render services).

    Logs the payment event against the company for agent visibility
    in the activity feed. The actual order storage happens on the
    company's own Render service (Neon DB).
    """
    body = await request.json()

    event_type = body.get("type", "")
    data_obj = body.get("data", {}).get("object", {})
    metadata = data_obj.get("metadata", {}) or {}
    company_slug = metadata.get("company_slug", "")

    if not company_slug and event_type == "checkout.session.completed":
        payment_intent = data_obj.get("payment_intent", "")
        if isinstance(payment_intent, dict):
            company_slug = (payment_intent.get("metadata") or {}).get("company_slug", "")

    if not company_slug:
        logger.info("stripe_webhook_no_slug", event_type=event_type)
        return {"received": True, "processed": False}

    result = await db.execute(select(Company).where(Company.slug == company_slug))
    company = result.scalar_one_or_none()
    if not company:
        logger.warning("stripe_webhook_unknown_company", slug=company_slug)
        return {"received": True, "processed": False}

    customer_email = data_obj.get("customer_details", {}).get("email", "")
    amount = data_obj.get("amount_total", data_obj.get("amount", 0))
    currency = data_obj.get("currency", "eur")
    payment_id = data_obj.get("payment_intent", data_obj.get("id", ""))

    notif = CompanyNotification(
        company_id=company.id,
        type=NotificationType.PAYMENT_RECEIVED,
        title=f"Paiement de {amount / 100:.2f} {currency.upper()}",
        message=f"Client: {customer_email or 'inconnu'} — {event_type} ({payment_id[:20]}...)",
    )
    db.add(notif)
    await db.commit()

    logger.info(
        "stripe_payment_logged",
        company_id=company.id,
        amount=amount,
        event_type=event_type,
    )

    return {"received": True, "processed": True, "company_id": company.id}
