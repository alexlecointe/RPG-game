"""Tool: send_email — Send emails via Resend with mutualized company identity.

Each company gets a dynamic from-address: {slug}@{domain}.
Outbound cold emails are rate-limited to protect sender reputation.
All sent emails are stored in company_emails for tracking.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools import ToolDefinition
from app.models.entities import CompanyEmail, EmailDirection

SEND_EMAIL_SCHEMA = {
    "type": "object",
    "properties": {
        "to": {
            "type": "string",
            "description": "Recipient email address.",
        },
        "subject": {
            "type": "string",
            "description": "Email subject line.",
        },
        "html_body": {
            "type": "string",
            "description": "Email body in HTML format.",
        },
        "from_name": {
            "type": "string",
            "description": "Sender display name (default: company name).",
            "default": "RPG Agent",
        },
    },
    "required": ["to", "subject", "html_body"],
}

RESEND_API = "https://api.resend.com/emails"
DAILY_COLD_EMAIL_LIMIT = 2


async def _check_rate_limit(db: AsyncSession, company_id: str) -> bool:
    """Return True if company is within the daily cold email limit."""
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    result = await db.execute(
        select(func.count(CompanyEmail.id))
        .where(
            CompanyEmail.company_id == company_id,
            CompanyEmail.direction == EmailDirection.OUTBOUND,
            CompanyEmail.created_at >= since,
        )
    )
    count = result.scalar() or 0
    return count < DAILY_COLD_EMAIL_LIMIT


async def _store_email(
    db: AsyncSession,
    company_id: str,
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
    message_id: str,
    direction: EmailDirection = EmailDirection.OUTBOUND,
) -> None:
    email = CompanyEmail(
        company_id=company_id,
        direction=direction,
        from_address=from_addr,
        to_address=to_addr,
        subject=subject,
        body=body,
        message_id=message_id,
    )
    db.add(email)
    await db.commit()


async def _execute_send_email(
    api_key: str,
    from_domain: str,
    company_slug: str,
    company_id: str,
    to: str,
    subject: str,
    html_body: str,
    from_name: str = "RPG Agent",
) -> str:
    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        if not await _check_rate_limit(db, company_id):
            return json.dumps({
                "sent": False,
                "error": f"Daily cold email limit reached ({DAILY_COLD_EMAIL_LIMIT}/day). Try again tomorrow.",
            })

        since = datetime.now(timezone.utc) - timedelta(hours=24)
        dup_result = await db.execute(
            select(CompanyEmail).where(
                CompanyEmail.company_id == company_id,
                CompanyEmail.to_address == to,
                CompanyEmail.subject == subject,
                CompanyEmail.direction == EmailDirection.OUTBOUND,
                CompanyEmail.created_at >= since,
            ).limit(1)
        )
        existing = dup_result.scalar_one_or_none()
        if existing:
            return json.dumps({
                "sent": True,
                "message_id": existing.message_id or "",
                "to": to,
                "subject": subject,
                "deduplicated": True,
            })

        from_email = f"{from_name} <noreply@{company_slug}.{from_domain}>"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                RESEND_API,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": from_email,
                    "to": [to],
                    "subject": subject,
                    "html": html_body,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        msg_id = data.get("id", "")

        await _store_email(
            db, company_id, from_email, to, subject, html_body, msg_id,
        )

    return json.dumps({
        "sent": True,
        "message_id": msg_id,
        "to": to,
        "subject": subject,
        "from": from_email,
    })


def create_send_email_tool(
    api_key: str,
    from_domain: str = "resend.dev",
    company_slug: str = "default",
    company_id: str = "",
) -> ToolDefinition:
    async def execute(
        to: str, subject: str, html_body: str, from_name: str = "RPG Agent"
    ) -> str:
        return await _execute_send_email(
            api_key, from_domain, company_slug, company_id,
            to, subject, html_body, from_name,
        )

    return ToolDefinition(
        name="send_email",
        description=(
            "Send an email via Resend. Use this for cold outreach emails, "
            "customer notifications, or transactional messages. "
            "Provide recipient, subject, and HTML body. "
            f"Rate limited to {DAILY_COLD_EMAIL_LIMIT} cold emails/day/company."
        ),
        parameters=SEND_EMAIL_SCHEMA,
        execute=execute,
    )
