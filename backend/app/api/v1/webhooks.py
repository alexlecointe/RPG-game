"""Webhook endpoints for inbound services (email, payments, etc.)."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.entities import (
    Company, CompanyEmail, CompanyNotification,
    EmailDirection, GodModeSession, NotificationType, Order, Subscription, SubscriptionStatus,
)

router = APIRouter()
logger = structlog.get_logger()


def _verify_stripe_signature(payload: bytes, sig_header: str, secret: str) -> bool:
    """Verify Stripe webhook signature (HMAC-SHA256). Returns True if valid."""
    try:
        parts: dict[str, str] = {}
        for item in sig_header.split(","):
            k, _, v = item.partition("=")
            parts[k.strip()] = v.strip()

        timestamp = parts.get("t", "")
        v1_sig = parts.get("v1", "")
        if not timestamp or not v1_sig:
            return False

        if abs(time.time() - int(timestamp)) > 300:
            logger.warning("stripe_webhook_timestamp_too_old", timestamp=timestamp)
            return False

        signed = f"{timestamp}.{payload.decode('utf-8')}"
        expected = hmac.new(
            secret.encode("utf-8"),
            signed.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, v1_sig)
    except Exception:
        return False


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


async def _process_stripe_event_bg(payload: bytes, event_type: str, data_obj: dict, body: dict) -> None:
    """Heavy Stripe event processing run in background to avoid webhook timeout."""
    from app.core.database import SessionLocal
    async with SessionLocal() as db:
        await _handle_stripe_event(db, event_type, data_obj, body)


async def _handle_stripe_event(db: AsyncSession, event_type: str, data_obj: dict, body: dict) -> None:
    """Core Stripe event handler (shared between sync and background paths)."""
    metadata = data_obj.get("metadata", {}) or {}
    checkout_type = metadata.get("checkout_type", "")

    if checkout_type in ("pack", "subscription"):
        return

    company_slug = metadata.get("company_slug", "")

    if not company_slug and event_type == "checkout.session.completed":
        pi = data_obj.get("payment_intent", "")
        if isinstance(pi, dict):
            company_slug = (pi.get("metadata") or {}).get("company_slug", "")

    if not company_slug and event_type == "payment_intent.succeeded":
        company_slug = (data_obj.get("metadata") or {}).get("company_slug", "")

    if not company_slug:
        logger.warning("stripe_event_no_slug", event_type=event_type)
        return

    result = await db.execute(select(Company).where(Company.slug == company_slug))
    company = result.scalar_one_or_none()
    if not company:
        logger.warning("stripe_event_company_not_found", slug=company_slug, event_type=event_type)
        return

    if event_type == "payment_intent.succeeded":
        pi_id = data_obj.get("id", "")
        existing = await db.execute(
            select(Order).where(Order.stripe_payment_intent_id == pi_id)
        )
        if existing.scalar_one_or_none():
            return

        amount = data_obj.get("amount", 0)
        currency = data_obj.get("currency", "eur")
        customer_email = (data_obj.get("charges", {}).get("data", [{}]) or [{}])[0].get(
            "billing_details", {}
        ).get("email")
        product_name = (data_obj.get("metadata") or {}).get("product_name", "")

        order = Order(
            company_id=company.id,
            stripe_payment_intent_id=pi_id,
            customer_email=customer_email,
            amount_cents=amount,
            currency=currency,
            product_name=product_name,
        )
        db.add(order)

        notif = CompanyNotification(
            company_id=company.id,
            type=NotificationType.PAYMENT_RECEIVED,
            title="Paiement reçu !",
            message=f"{amount / 100:.2f} {currency.upper()} via Stripe",
        )
        db.add(notif)
        await db.commit()

        from app.services.meta_capi import send_purchase_event
        from app.services.site_hosting import build_gateway_url
        try:
            capi_result = await send_purchase_event(
                payment_intent_id=pi_id,
                value_cents=amount,
                currency=currency.upper(),
                customer_email=customer_email,
                event_source_url=build_gateway_url(company.slug or ""),
            )
            order.meta_event_sent = bool(capi_result.get("sent"))
            await db.commit()
        except Exception as exc:
            logger.warning("meta_capi_failed", error=str(exc))

    elif event_type == "checkout.session.completed":
        if checkout_type == "god_mode":
            god_plan_id = metadata.get("god_plan_id", "")
            from app.services.billing import GOD_MODE_PLANS
            plan = GOD_MODE_PLANS.get(god_plan_id, {})
            hours = plan.get("hours", int(metadata.get("hours", 1)))
            amount = data_obj.get("amount_total", 0) or 0
            stripe_session_id = data_obj.get("id", "")
            payment_intent = data_obj.get("payment_intent") or ""
            if isinstance(payment_intent, dict):
                payment_intent = payment_intent.get("id", "")

            if stripe_session_id:
                from sqlalchemy import select as sa_select
                dup = await db.execute(
                    sa_select(GodModeSession).where(
                        GodModeSession.stripe_session_id == stripe_session_id
                    )
                )
                if dup.scalar_one_or_none():
                    return

            from datetime import timedelta
            now = datetime.now(timezone.utc)
            gm_session = GodModeSession(
                company_id=company.id,
                stripe_payment_intent_id=str(payment_intent) or None,
                stripe_session_id=stripe_session_id or None,
                god_plan_id=god_plan_id,
                hours=hours,
                amount_cents=int(amount),
                status="active",
                started_at=now,
                expires_at=now + timedelta(hours=hours),
            )
            db.add(gm_session)
            db.add(CompanyNotification(
                company_id=company.id,
                type=NotificationType.SYSTEM,
                title=f"God Mode activé — {plan.get('label', str(hours) + 'h')}",
                message="Session autonome démarrée. Vos agents travaillent sans interruption.",
            ))
            await db.commit()
            logger.info("god_mode_activated_bg", company_id=company.id, plan=god_plan_id)

            from app.workers.runner import schedule_god_mode_loop
            schedule_god_mode_loop(company.id, gm_session.id)
            return

        # Regular product sale
        pi_id = data_obj.get("payment_intent", "")
        if isinstance(pi_id, dict):
            pi_id = pi_id.get("id", "")
        if pi_id:
            existing = await db.execute(select(Order).where(Order.stripe_payment_intent_id == pi_id))
            if existing.scalar_one_or_none():
                return

        amount = data_obj.get("amount_total", 0)
        currency = data_obj.get("currency", "eur")
        customer_email = data_obj.get("customer_email") or data_obj.get("customer_details", {}).get("email")
        product_name = metadata.get("product_name", "")

        order = Order(
            company_id=company.id,
            stripe_payment_intent_id=pi_id or f"cs_{data_obj.get('id', '')}",
            stripe_session_id=data_obj.get("id"),
            customer_email=customer_email,
            amount_cents=amount,
            currency=currency,
            product_name=product_name,
        )
        db.add(order)
        db.add(CompanyNotification(
            company_id=company.id,
            type=NotificationType.PAYMENT_RECEIVED,
            title="Vente reçue !",
            message=f"{amount / 100:.2f} {currency.upper()} — {customer_email or 'client'}",
        ))
        await db.commit()

        from app.services.meta_capi import send_purchase_event
        from app.services.site_hosting import build_gateway_url
        try:
            event_id = pi_id or data_obj.get("id", "")
            capi_result = await send_purchase_event(
                payment_intent_id=event_id,
                value_cents=amount,
                currency=currency.upper(),
                customer_email=customer_email,
                event_source_url=build_gateway_url(company.slug or ""),
            )
            order.meta_event_sent = bool(capi_result.get("sent"))
            await db.commit()
        except Exception as exc:
            logger.warning("meta_capi_checkout_failed", error=str(exc))


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Receive Stripe webhook events. Validates signature, then processes in background."""
    payload = await request.body()
    settings = get_settings()

    if settings.stripe_webhook_secret:
        sig_header = request.headers.get("stripe-signature", "")
        if not _verify_stripe_signature(payload, sig_header, settings.stripe_webhook_secret):
            logger.warning("stripe_webhook_invalid_signature")
            return JSONResponse(status_code=400, content={"error": "Invalid signature"})

    body = json.loads(payload)
    event_type = body.get("type", "")
    data_obj = body.get("data", {}).get("object", {})

    # Handle account.updated inline (fast, no external calls)
    if event_type == "account.updated":
        from app.core.database import SessionLocal
        account_id = data_obj.get("id", "")
        if account_id:
            async with SessionLocal() as db:
                result = await db.execute(
                    select(Company).where(Company.stripe_connect_account_id == account_id)
                )
                company = result.scalar_one_or_none()
                if company:
                    charges = data_obj.get("charges_enabled", False)
                    payouts = data_obj.get("payouts_enabled", False)
                    status_label = "ready" if charges and payouts else "pending"
                    db.add(CompanyNotification(
                        company_id=company.id,
                        type=NotificationType.SYSTEM,
                        title="Stripe Connect mis à jour",
                        message=f"Statut paiements : {status_label}",
                    ))
                    await db.commit()
        return {"received": True, "processed": True}

    if event_type in ("payment_intent.succeeded", "checkout.session.completed"):
        # Dispatch heavy processing to background — respond immediately to Stripe
        background_tasks.add_task(_process_stripe_event_bg, payload, event_type, data_obj, body)
        return {"received": True, "queued": True}

    return {"received": True, "processed": False}


@router.post("/webhooks/stripe/billing")
async def stripe_billing_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Handle Stripe billing events: subscription lifecycle + credit pack purchases."""
    payload = await request.body()
    settings = get_settings()

    if settings.stripe_billing_webhook_secret:
        sig_header = request.headers.get("stripe-signature", "")
        if not _verify_stripe_signature(payload, sig_header, settings.stripe_billing_webhook_secret):
            logger.warning("stripe_billing_webhook_invalid_signature")
            return JSONResponse(status_code=400, content={"error": "Invalid signature"})

    body = json.loads(payload)
    event_type = body.get("type", "")
    data_obj = body.get("data", {}).get("object", {})

    logger.info("stripe_billing_event", event_type=event_type)

    # -------------------------------------------------------------------
    # customer.subscription.created / customer.subscription.updated
    # -------------------------------------------------------------------
    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        stripe_subscription_id = data_obj.get("id", "")
        stripe_customer_id = data_obj.get("customer", "")
        stripe_status = data_obj.get("status", "")
        metadata = data_obj.get("metadata", {}) or {}
        company_id = metadata.get("company_id", "")
        plan_id = metadata.get("plan_or_pack_id", "")

        # Determine plan from line items if not in metadata
        if not plan_id:
            items = (data_obj.get("items", {}) or {}).get("data", [])
            if items:
                price_id = (items[0].get("price", {}) or {}).get("id", "")
                from app.core.config import get_settings
                settings = get_settings()
                price_plan_map = {
                    settings.stripe_price_starter: "starter",
                    settings.stripe_price_growth: "growth",
                    settings.stripe_price_pro: "pro",
                    settings.stripe_price_scale: "scale",
                    settings.stripe_price_power: "power",
                    settings.stripe_price_ultra: "ultra",
                    settings.stripe_price_max: "max",
                }
                plan_id = price_plan_map.get(price_id, "")

        if not company_id:
            result = await db.execute(
                select(Subscription).where(Subscription.stripe_subscription_id == stripe_subscription_id)
            )
            sub = result.scalar_one_or_none()
            if sub:
                company_id = sub.company_id
        else:
            result = await db.execute(
                select(Subscription).where(Subscription.company_id == company_id)
            )
            sub = result.scalar_one_or_none()

        if not sub and company_id:
            sub = Subscription(company_id=company_id, status=SubscriptionStatus.TRIAL)
            db.add(sub)
            await db.flush()

        if sub:
            sub.stripe_subscription_id = stripe_subscription_id
            sub.stripe_customer_id = stripe_customer_id

            from app.services.billing import SUBSCRIPTION_PLANS, WELCOME_CREDITS
            plan_info = SUBSCRIPTION_PLANS.get(plan_id, {})
            monthly = plan_info.get("credits", 0)

            if stripe_status == "trialing":
                sub.status = SubscriptionStatus.TRIAL
                trial_end_ts = data_obj.get("trial_end")
                if trial_end_ts:
                    sub.trial_end = datetime.fromtimestamp(trial_end_ts, tz=timezone.utc)
            elif stripe_status == "active":
                sub.status = SubscriptionStatus.ACTIVE
                # Add welcome bonus on first activation
                if not sub.welcome_bonus_given and monthly > 0:
                    sub.credits_remaining = monthly + WELCOME_CREDITS
                    sub.welcome_bonus_given = True
                    logger.info("welcome_bonus_given", company_id=company_id, bonus=WELCOME_CREDITS)
                elif monthly > 0:
                    sub.credits_remaining = max(sub.credits_remaining or 0, monthly)
            elif stripe_status == "past_due":
                sub.status = SubscriptionStatus.PAST_DUE
            elif stripe_status in ("canceled", "cancelled", "unpaid", "incomplete_expired"):
                sub.status = SubscriptionStatus.CANCELLED

            if plan_id:
                sub.plan_id = plan_id
                sub.credits_monthly = monthly

            period_start = data_obj.get("current_period_start")
            period_end = data_obj.get("current_period_end")
            if period_start:
                sub.current_period_start = datetime.fromtimestamp(period_start, tz=timezone.utc)
            if period_end:
                sub.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)

            await db.commit()
            logger.info("subscription_updated", company_id=company_id, plan=plan_id, status=stripe_status)

        return {"received": True, "event": event_type}

    # -------------------------------------------------------------------
    # invoice.paid — monthly renewal → reset credits
    # -------------------------------------------------------------------
    if event_type == "invoice.paid":
        stripe_subscription_id = data_obj.get("subscription", "")
        stripe_customer_id = data_obj.get("customer", "")
        billing_reason = data_obj.get("billing_reason", "")

        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == stripe_subscription_id)
        )
        sub = result.scalar_one_or_none()

        if sub and billing_reason in ("subscription_cycle", "subscription_update"):
            from app.services.billing import reset_monthly_credits
            await reset_monthly_credits(db, sub, sub.plan_id or "")

            company = await db.get(Company, sub.company_id)
            if company:
                plan_info = {}
                if sub.plan_id:
                    from app.services.billing import SUBSCRIPTION_PLANS
                    plan_info = SUBSCRIPTION_PLANS.get(sub.plan_id, {})
                notif = CompanyNotification(
                    company_id=sub.company_id,
                    type=NotificationType.SYSTEM,
                    title="Crédits renouvelés",
                    message=f"{plan_info.get('credits', 0)} task credits ajoutés — plan {sub.plan_id or '?'}.",
                )
                db.add(notif)

            await db.commit()
            logger.info("monthly_credits_reset_via_invoice", company_id=sub.company_id)

        return {"received": True, "event": event_type}

    # -------------------------------------------------------------------
    # customer.subscription.deleted — cancellation
    # -------------------------------------------------------------------
    if event_type == "customer.subscription.deleted":
        stripe_subscription_id = data_obj.get("id", "")
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == stripe_subscription_id)
        )
        sub = result.scalar_one_or_none()
        if sub:
            sub.status = SubscriptionStatus.CANCELLED
            company = await db.get(Company, sub.company_id)
            if company:
                notif = CompanyNotification(
                    company_id=sub.company_id,
                    type=NotificationType.SYSTEM,
                    title="Abonnement annulé",
                    message="Votre abonnement a été annulé. Réabonnez-vous pour continuer.",
                )
                db.add(notif)
            await db.commit()
            logger.info("subscription_cancelled", company_id=sub.company_id)

        return {"received": True, "event": event_type}

    # -------------------------------------------------------------------
    # checkout.session.completed — credit pack purchase
    # -------------------------------------------------------------------
    if event_type == "checkout.session.completed":
        metadata = data_obj.get("metadata", {}) or {}
        checkout_type = metadata.get("checkout_type", "")
        company_id = metadata.get("company_id", "")
        plan_or_pack_id = metadata.get("plan_or_pack_id", "")

        if checkout_type == "pack" and company_id and plan_or_pack_id:
            from app.services.billing import CREDIT_PACKS, add_pack_credits, get_or_create_subscription
            pack = CREDIT_PACKS.get(plan_or_pack_id)
            if pack:
                company = await db.get(Company, company_id)
                if company:
                    sub = await get_or_create_subscription(db, company)
                    await add_pack_credits(db, sub, pack["credits"])
                    notif = CompanyNotification(
                        company_id=company_id,
                        type=NotificationType.SYSTEM,
                        title=f"+{pack['credits']} crédits ajoutés",
                        message=f"Pack {pack['label']} crédité sur votre compte.",
                    )
                    db.add(notif)
                    await db.commit()
                    logger.info("pack_credited", company_id=company_id, pack=plan_or_pack_id, credits=pack["credits"])

        elif checkout_type == "god_mode" and company_id:
            from app.services.billing import GOD_MODE_PLANS
            god_plan_id = metadata.get("god_plan_id", "")
            plan = GOD_MODE_PLANS.get(god_plan_id, {})
            hours = plan.get("hours", int(metadata.get("hours", 1)))
            amount = data_obj.get("amount_total", 0) or 0
            stripe_session_id = data_obj.get("id", "")

            payment_intent = data_obj.get("payment_intent") or ""
            if isinstance(payment_intent, dict):
                payment_intent = payment_intent.get("id", "")

            # Idempotency — skip if this session was already processed
            if stripe_session_id:
                from sqlalchemy import select as sa_select
                dup = await db.execute(
                    sa_select(GodModeSession).where(
                        GodModeSession.stripe_session_id == stripe_session_id
                    )
                )
                if dup.scalar_one_or_none():
                    logger.info("god_mode_duplicate_skipped", session_id=stripe_session_id)
                    return {"received": True, "event": event_type, "duplicate": True}

            from datetime import timedelta
            now = datetime.now(timezone.utc)
            session = GodModeSession(
                company_id=company_id,
                stripe_payment_intent_id=str(payment_intent) or None,
                stripe_session_id=stripe_session_id or None,
                god_plan_id=god_plan_id,
                hours=hours,
                amount_cents=int(amount),
                status="active",
                started_at=now,
                expires_at=now + timedelta(hours=hours),
            )
            db.add(session)

            notif = CompanyNotification(
                company_id=company_id,
                type=NotificationType.SYSTEM,
                title=f"God Mode activé — {plan.get('label', str(hours) + 'h')}",
                message="Session autonome démarrée. Vos agents travaillent sans interruption.",
            )
            db.add(notif)
            await db.commit()
            logger.info("god_mode_activated", company_id=company_id, god_plan=god_plan_id, hours=hours)

            # Start autonomous mission loop in background
            from app.workers.runner import schedule_god_mode_loop
            schedule_god_mode_loop(company_id, session.id)

        return {"received": True, "event": event_type}

    return {"received": True, "event": event_type, "processed": False}
