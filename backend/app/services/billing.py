"""Polsia-like billing service — subscription plans, credit packs, monthly reset."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import (
    Company,
    CompanyNotification,
    GodModeSession,
    NotificationType,
    Subscription,
    SubscriptionStatus,
    WalletTransaction,
)
# NOTE: stripe imported locally within functions to avoid import at module load

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Plan & pack definitions (Polsia exact pricing)
# ---------------------------------------------------------------------------

SUBSCRIPTION_PLANS: dict[str, dict[str, Any]] = {
    "starter": {"cents": 1900, "credits": 15, "label": "Starter"},
    "growth":  {"cents": 2900, "credits": 25, "label": "Growth"},
    "pro":     {"cents": 4900, "credits": 50, "label": "Pro"},
    "scale":   {"cents": 9900, "credits": 100, "label": "Scale"},
    "power":   {"cents": 19900, "credits": 200, "label": "Power"},
    "ultra":   {"cents": 49900, "credits": 500, "label": "Ultra"},
    "max":     {"cents": 99900, "credits": 1000, "label": "Max"},
}

CREDIT_PACKS: dict[str, dict[str, Any]] = {
    "pack_3":   {"cents": 900,  "credits": 3,   "label": "3 crédits"},
    "pack_10":  {"cents": 2500, "credits": 10,  "label": "10 crédits"},
    "pack_25":  {"cents": 4900, "credits": 25,  "label": "25 crédits"},
    "pack_60":  {"cents": 9900, "credits": 60,  "label": "60 crédits"},
    "pack_150": {"cents": 19900,"credits": 150, "label": "150 crédits"},
}

TRIAL_DAYS = 3
WELCOME_CREDITS = 10  # one-shot bonus at first subscription

# ---------------------------------------------------------------------------
# God Mode — autonomous agent session (Polsia exact pricing, separate billing)
# ---------------------------------------------------------------------------

GOD_MODE_PLANS: dict[str, dict[str, Any]] = {
    "god_1h":   {"cents": 1900,  "hours": 1,   "label": "1 heure"},
    "god_2h":   {"cents": 3500,  "hours": 2,   "label": "2 heures"},
    "god_3h":   {"cents": 4900,  "hours": 3,   "label": "3 heures"},
    "god_6h":   {"cents": 7900,  "hours": 6,   "label": "6 heures"},
    "god_12h":  {"cents": 14900, "hours": 12,  "label": "12 heures"},
    "god_24h":  {"cents": 24900, "hours": 24,  "label": "24 heures"},
    "god_48h":  {"cents": 37900, "hours": 48,  "label": "48 heures"},
    "god_72h":  {"cents": 49900, "hours": 72,  "label": "72 heures"},
    "god_7d":   {"cents": 99900, "hours": 168, "label": "7 jours"},
}


def _stripe_price_id(plan_id: str) -> str:
    settings = get_settings()
    mapping = {
        "starter": settings.stripe_price_starter,
        "growth":  settings.stripe_price_growth,
        "pro":     settings.stripe_price_pro,
        "scale":   settings.stripe_price_scale,
        "power":   settings.stripe_price_power,
        "ultra":   settings.stripe_price_ultra,
        "max":     settings.stripe_price_max,
    }
    return mapping.get(plan_id, "")


# ---------------------------------------------------------------------------
# Subscription helpers
# ---------------------------------------------------------------------------

async def get_or_create_subscription(db: AsyncSession, company: Company) -> Subscription:
    """Return existing subscription or create a trial one."""
    result = await db.execute(
        select(Subscription).where(Subscription.company_id == company.id)
    )
    sub = result.scalar_one_or_none()
    if sub:
        return sub

    now = datetime.now(timezone.utc)
    sub = Subscription(
        company_id=company.id,
        status=SubscriptionStatus.TRIAL,
        credits_monthly=0,
        credits_remaining=0,
        credits_used_period=0,
        pack_credits=0,
        trial_end=now + timedelta(days=TRIAL_DAYS),
    )
    db.add(sub)
    await db.flush()
    logger.info("subscription_created_trial", company_id=company.id)
    return sub


async def debit_credit(db: AsyncSession, subscription: Subscription) -> None:
    """Debit 1 credit. Pack credits consumed first, then plan credits. Raises if 0."""
    total = (subscription.credits_remaining or 0) + (subscription.pack_credits or 0)
    if total <= 0:
        raise ValueError("no_credits")

    if (subscription.pack_credits or 0) > 0:
        subscription.pack_credits -= 1
    else:
        subscription.credits_remaining -= 1

    subscription.credits_used_period = (subscription.credits_used_period or 0) + 1
    await db.flush()


async def reset_monthly_credits(
    db: AsyncSession,
    subscription: Subscription,
    plan_id: str,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> None:
    """Monthly renewal: reset plan credits, preserve pack credits."""
    plan = SUBSCRIPTION_PLANS.get(plan_id, {})
    monthly = plan.get("credits", 0)

    subscription.credits_remaining = monthly
    subscription.credits_monthly = monthly
    subscription.credits_used_period = 0
    subscription.plan_id = plan_id
    subscription.status = SubscriptionStatus.ACTIVE
    if period_start:
        subscription.current_period_start = period_start
    if period_end:
        subscription.current_period_end = period_end

    await db.flush()
    logger.info(
        "monthly_credits_reset",
        company_id=subscription.company_id,
        plan_id=plan_id,
        credits=monthly,
    )


async def add_pack_credits(db: AsyncSession, subscription: Subscription, amount: int) -> None:
    """Add one-shot pack credits (do not rollover from plan)."""
    subscription.pack_credits = (subscription.pack_credits or 0) + amount
    await db.flush()
    logger.info("pack_credits_added", company_id=subscription.company_id, amount=amount)


async def get_subscription_status(db: AsyncSession, company_id: str) -> dict:
    """Return serializable subscription status for API response."""
    result = await db.execute(
        select(Subscription).where(Subscription.company_id == company_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        now = datetime.now(timezone.utc)
        return {
            "status": "no_subscription",
            "plan_id": None,
            "credits_remaining": 0,
            "pack_credits": 0,
            "credits_used_period": 0,
            "credits_monthly": 0,
            "trial_end": None,
            "current_period_end": None,
            "owner_actionable": True,
            "actionable_message": "Abonnez-vous pour exécuter des missions.",
        }

    now = datetime.now(timezone.utc)
    total_credits = (sub.credits_remaining or 0) + (sub.pack_credits or 0)
    owner_actionable = False
    actionable_message = None

    if sub.status == SubscriptionStatus.TRIAL:
        trial_end = sub.trial_end
        if trial_end:
            trial_end_aware = trial_end.replace(tzinfo=timezone.utc) if trial_end.tzinfo is None else trial_end
            if now > trial_end_aware:
                owner_actionable = True
                actionable_message = "Votre essai gratuit est terminé. Abonnez-vous pour continuer."
    elif sub.status == SubscriptionStatus.PAST_DUE:
        owner_actionable = True
        actionable_message = "Paiement en échec. Mettez à jour votre carte."
    elif sub.status in (SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED):
        owner_actionable = True
        actionable_message = "Abonnement annulé. Réabonnez-vous pour continuer."
    elif total_credits == 0:
        owner_actionable = True
        actionable_message = "Plus de crédits. Achetez un pack ou attendez le renouvellement mensuel."
    elif total_credits < 3:
        owner_actionable = True
        actionable_message = f"Seulement {total_credits} crédit(s) restant(s). Pensez à recharger."

    plan_info = SUBSCRIPTION_PLANS.get(sub.plan_id or "", {})

    return {
        "status": sub.status.value if sub.status else "no_subscription",
        "plan_id": sub.plan_id,
        "plan_label": plan_info.get("label"),
        "credits_remaining": sub.credits_remaining or 0,
        "pack_credits": sub.pack_credits or 0,
        "total_credits": total_credits,
        "credits_used_period": sub.credits_used_period or 0,
        "credits_monthly": sub.credits_monthly or 0,
        "trial_end": sub.trial_end.isoformat() if sub.trial_end else None,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "owner_actionable": owner_actionable,
        "actionable_message": actionable_message,
    }


async def create_checkout_session(
    company: Company,
    checkout_type: str,
    plan_or_pack_id: str,
    success_url: str,
    cancel_url: str,
    stripe_customer_id: str | None = None,
) -> str:
    """Create Stripe Checkout session and return URL. Returns mock URL if not configured."""
    settings = get_settings()
    if not settings.stripe_secret_key:
        logger.warning("stripe_not_configured_checkout", company_id=company.id)
        return f"https://checkout.stripe.com/mock?company={company.id}&type={checkout_type}&plan={plan_or_pack_id}"

    import stripe
    stripe.api_key = settings.stripe_secret_key

    metadata = {
        "company_id": company.id,
        "company_slug": company.slug or "",
        "checkout_type": checkout_type,
        "plan_or_pack_id": plan_or_pack_id,
    }

    if checkout_type == "subscription":
        price_id = _stripe_price_id(plan_or_pack_id)
        if not price_id:
            raise ValueError(f"stripe_price_not_configured for plan {plan_or_pack_id}")

        params: dict[str, Any] = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": metadata,
            "subscription_data": {
                "trial_period_days": TRIAL_DAYS,
                "metadata": metadata,
            },
            "allow_promotion_codes": True,
        }
        if stripe_customer_id:
            params["customer"] = stripe_customer_id

        session = stripe.checkout.Session.create(**params)

    elif checkout_type == "pack":
        pack = CREDIT_PACKS.get(plan_or_pack_id)
        if not pack:
            raise ValueError(f"unknown_pack {plan_or_pack_id}")

        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "unit_amount": pack["cents"],
                    "product_data": {
                        "name": f"RPG Agent — {pack['label']}",
                        "description": f"{pack['credits']} task credits (one-shot)",
                    },
                },
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
        )
    else:
        raise ValueError(f"unknown checkout_type: {checkout_type}")

    return session.url or ""


async def create_god_mode_checkout(
    company: Company,
    god_plan_id: str,
    success_url: str,
    cancel_url: str,
    stripe_customer_id: str | None = None,
) -> str:
    """Create a one-shot Stripe Checkout for a God Mode session.
    Does NOT touch task credits — billed separately.
    """
    plan = GOD_MODE_PLANS.get(god_plan_id)
    if not plan:
        raise ValueError(f"unknown_god_plan {god_plan_id}")

    settings = get_settings()
    if not settings.stripe_secret_key:
        return f"https://checkout.stripe.com/mock?company={company.id}&type=god_mode&plan={god_plan_id}"

    import stripe
    stripe.api_key = settings.stripe_secret_key

    metadata = {
        "company_id": company.id,
        "company_slug": company.slug or "",
        "checkout_type": "god_mode",
        "god_plan_id": god_plan_id,
        "hours": str(plan["hours"]),
    }

    params: dict[str, Any] = {
        "mode": "payment",
        "line_items": [{
            "price_data": {
                "currency": "eur",
                "unit_amount": plan["cents"],
                "product_data": {
                    "name": f"RPG Agent — God Mode {plan['label']}",
                    "description": f"Session autonome {plan['label']} · N'utilise pas vos task credits",
                },
            },
            "quantity": 1,
        }],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": metadata,
    }
    if stripe_customer_id:
        params["customer"] = stripe_customer_id

    session = stripe.checkout.Session.create(**params)
    return session.url or ""


async def get_active_god_mode_session(
    db: AsyncSession, company_id: str
) -> GodModeSession | None:
    """Return the currently active God Mode session for a company, or None."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(GodModeSession)
        .where(
            GodModeSession.company_id == company_id,
            GodModeSession.status == "active",
            GodModeSession.expires_at > now,
        )
        .order_by(GodModeSession.expires_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def expire_god_mode_sessions(db: AsyncSession) -> int:
    """Mark expired active sessions as 'expired'. Called by the daily cron or inline."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(GodModeSession).where(
            GodModeSession.status == "active",
            GodModeSession.expires_at <= now,
        )
    )
    sessions = result.scalars().all()
    for s in sessions:
        s.status = "expired"
    if sessions:
        await db.commit()
        logger.info("god_mode_expired", count=len(sessions))
    return len(sessions)


async def charge_ads_wallet_stripe(
    db: AsyncSession,
    company: Company,
) -> dict:
    """Charge the daily ads budget via Stripe and credit the ads wallet.

    Requires the company's Subscription to have a stripe_customer_id with a
    default payment method. Returns a result dict with amount_charged_cents.
    """
    settings = get_settings()
    if not company.daily_ads_budget_cents or company.daily_ads_budget_cents <= 0:
        return {"skipped": True, "reason": "no_daily_budget"}

    result = await db.execute(
        select(Subscription).where(Subscription.company_id == company.id)
    )
    sub = result.scalar_one_or_none()
    stripe_customer_id = sub.stripe_customer_id if sub else None

    if not settings.stripe_secret_key or not stripe_customer_id:
        # Fallback: credit wallet without Stripe (manual top-up)
        logger.warning(
            "ads_stripe_charge_skipped",
            company_id=company.id,
            reason="no_stripe_customer" if not stripe_customer_id else "no_stripe_key",
        )
        return {"skipped": True, "reason": "no_stripe_configured"}

    import stripe
    stripe.api_key = settings.stripe_secret_key

    budget = company.daily_ads_budget_cents
    fee_pct = settings.ads_platform_fee_percent
    spendable = int(budget * (100 - fee_pct) / 100)
    fee = budget - spendable

    try:
        # Create PaymentIntent using the customer's default payment method
        intent = stripe.PaymentIntent.create(
            amount=budget,
            currency="usd",
            customer=stripe_customer_id,
            payment_method_types=["card"],
            confirm=True,
            off_session=True,
            metadata={
                "company_id": company.id,
                "type": "ads_daily_charge",
                "spendable_cents": str(spendable),
                "fee_cents": str(fee),
            },
        )

        if intent.status in ("succeeded", "processing"):
            company.ads_wallet_balance_cents = (company.ads_wallet_balance_cents or 0) + spendable
            company.ads_payment_state = None  # clear any previous payment error
            db.add(WalletTransaction(
                company_id=company.id,
                amount_cents=spendable,
                type="credit",
                note=f"Daily top-up — ${budget / 100:.2f} charged, ${spendable / 100:.2f} to ads",
            ))
            db.add(WalletTransaction(
                company_id=company.id,
                amount_cents=-fee,
                type="fee",
                note=f"Polsia platform fee ({fee_pct}%)",
            ))
            await db.commit()
            logger.info(
                "ads_daily_charge_success",
                company_id=company.id,
                budget=budget,
                spendable=spendable,
                intent_id=intent.id,
            )
            return {"charged_cents": budget, "spendable_cents": spendable, "intent_id": intent.id}

        return {"skipped": True, "reason": f"stripe_status_{intent.status}"}

    except stripe.error.CardError as exc:
        err = exc.error if hasattr(exc, "error") else {}
        decline_code = (err.get("decline_code") or "") if isinstance(err, dict) else ""
        stripe_code = (err.get("code") or "") if isinstance(err, dict) else ""

        if decline_code == "expired_card" or stripe_code == "expired_card":
            payment_state = "card_expired"
        else:
            payment_state = "payment_method_missing"

        company.ads_payment_state = payment_state
        db.add(CompanyNotification(
            company_id=company.id,
            type=NotificationType.ADS,
            title="Problème de paiement",
            message=(
                "Votre carte a expiré. Mettez-la à jour pour continuer à diffuser vos publicités."
                if payment_state == "card_expired"
                else "Le paiement de votre budget pub a échoué. Vérifiez votre moyen de paiement."
            ),
        ))
        await db.commit()
        logger.warning("ads_daily_charge_card_error", company_id=company.id, payment_state=payment_state, error=str(exc))
        return {"skipped": True, "reason": payment_state, "message": str(exc)}

    except Exception as exc:
        logger.warning("ads_daily_charge_failed", company_id=company.id, error=str(exc))
        return {"skipped": True, "reason": "stripe_error", "message": str(exc)}
