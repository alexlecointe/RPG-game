"""Billing API — Polsia-like subscription + credit packs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import DbSession, verify_api_key
from app.schemas.api import (
    BillingPlanOut,
    BillingPlansResponse,
    CheckoutSessionOut,
    CreditPackOut,
    SubscriptionOut,
)
from app.services.billing import (
    CREDIT_PACKS,
    GOD_MODE_PLANS,
    SUBSCRIPTION_PLANS,
    create_checkout_session,
    create_god_mode_checkout,
    expire_god_mode_sessions,
    get_active_god_mode_session,
    get_or_create_subscription,
    get_subscription_status,
)
from app.services.company import CompanyService

router = APIRouter(dependencies=[Depends(verify_api_key)])


class CheckoutBody(BaseModel):
    type: str                # "subscription" | "pack"
    plan_or_pack_id: str     # "pro" | "pack_10"
    success_url: str = "rpgagent://billing/success"
    cancel_url: str = "rpgagent://billing/cancel"


@router.get("/companies/{company_id}/billing/subscription", response_model=SubscriptionOut)
async def get_subscription(company_id: str, db: DbSession):
    """Return current subscription status and credits."""
    status = await get_subscription_status(db, company_id)
    return status


@router.get("/companies/{company_id}/billing/plans", response_model=BillingPlansResponse)
async def list_billing_plans(company_id: str, db: DbSession):
    """Return all subscription plans and credit packs with pricing."""
    sub_status = await get_subscription_status(db, company_id)
    current_plan = sub_status.get("plan_id")

    plans = [
        BillingPlanOut(
            id=plan_id,
            label=plan["label"],
            cents=plan["cents"],
            credits=plan["credits"],
            price_display=f"${plan['cents'] // 100}/mois",
            is_current=(plan_id == current_plan),
        )
        for plan_id, plan in SUBSCRIPTION_PLANS.items()
    ]

    packs = [
        CreditPackOut(
            id=pack_id,
            label=pack["label"],
            cents=pack["cents"],
            credits=pack["credits"],
            price_display=f"${pack['cents'] // 100}",
        )
        for pack_id, pack in CREDIT_PACKS.items()
    ]

    return BillingPlansResponse(
        plans=plans,
        packs=packs,
        current_subscription=SubscriptionOut(**sub_status),
    )


@router.post("/companies/{company_id}/billing/checkout", response_model=CheckoutSessionOut)
async def create_checkout(company_id: str, body: CheckoutBody, db: DbSession):
    """Create a Stripe Checkout session. Returns the checkout URL to open in Safari."""
    svc = CompanyService(db)
    company = await svc.get_company(company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    if body.type not in ("subscription", "pack"):
        raise HTTPException(400, "type must be 'subscription' or 'pack'")

    if body.type == "subscription" and body.plan_or_pack_id not in SUBSCRIPTION_PLANS:
        raise HTTPException(400, f"Unknown plan: {body.plan_or_pack_id}")

    if body.type == "pack" and body.plan_or_pack_id not in CREDIT_PACKS:
        raise HTTPException(400, f"Unknown pack: {body.plan_or_pack_id}")

    # Get stripe_customer_id if already subscribed
    sub = await get_or_create_subscription(db, company)
    await db.commit()

    try:
        url = await create_checkout_session(
            company=company,
            checkout_type=body.type,
            plan_or_pack_id=body.plan_or_pack_id,
            success_url=body.success_url,
            cancel_url=body.cancel_url,
            stripe_customer_id=sub.stripe_customer_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    return CheckoutSessionOut(checkout_url=url)


@router.get("/companies/{company_id}/billing/god-mode/plans")
async def list_god_mode_plans(company_id: str):
    """Return available God Mode session plans."""
    return {
        "plans": [
            {
                "id": plan_id,
                "label": plan["label"],
                "cents": plan["cents"],
                "hours": plan["hours"],
                "price_display": f"${plan['cents'] // 100}",
            }
            for plan_id, plan in GOD_MODE_PLANS.items()
        ]
    }


class GodModeCheckoutBody(BaseModel):
    god_plan_id: str
    success_url: str = "rpgagent://billing/god-mode/success"
    cancel_url: str = "rpgagent://billing/god-mode/cancel"


@router.post("/companies/{company_id}/billing/god-mode/checkout", response_model=CheckoutSessionOut)
async def create_god_mode_checkout_session(
    company_id: str, body: GodModeCheckoutBody, db: DbSession
):
    """Create a one-shot Stripe Checkout for a God Mode session."""
    svc = CompanyService(db)
    company = await svc.get_company(company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    sub = await get_or_create_subscription(db, company)
    await db.commit()

    try:
        url = await create_god_mode_checkout(
            company=company,
            god_plan_id=body.god_plan_id,
            success_url=body.success_url,
            cancel_url=body.cancel_url,
            stripe_customer_id=sub.stripe_customer_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    return CheckoutSessionOut(checkout_url=url)


@router.get("/companies/{company_id}/billing/god-mode/active")
async def get_active_god_mode(company_id: str, db: DbSession):
    """Return the active God Mode session for a company, or null."""
    await expire_god_mode_sessions(db)
    session = await get_active_god_mode_session(db, company_id)
    if not session:
        return {"active": False, "session": None}
    return {
        "active": True,
        "session": {
            "id": session.id,
            "god_plan_id": session.god_plan_id,
            "hours": session.hours,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "expires_at": session.expires_at.isoformat() if session.expires_at else None,
        },
    }


@router.post("/companies/{company_id}/billing/god-mode/expire")
async def expire_god_mode(company_id: str, db: DbSession):
    """Manually expire all active God Mode sessions for a company (e.g. on cancel)."""
    from sqlalchemy import update as sa_update
    from app.models.entities import GodModeSession
    from datetime import datetime, timezone
    await db.execute(
        sa_update(GodModeSession)
        .where(GodModeSession.company_id == company_id, GodModeSession.status == "active")
        .values(status="expired")
    )
    await db.commit()
    return {"expired": True}


@router.get("/companies/{company_id}/billing/portal")
async def create_billing_portal(company_id: str, db: DbSession):
    """Create a Stripe Customer Portal session so founder can manage subscription."""
    svc = CompanyService(db)
    company = await svc.get_company(company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    from app.core.config import get_settings
    settings = get_settings()
    if not settings.stripe_secret_key:
        return {"portal_url": f"https://billing.stripe.com/mock?company={company_id}"}

    sub = await get_or_create_subscription(db, company)
    if not sub.stripe_customer_id:
        raise HTTPException(400, "No Stripe customer associated. Subscribe first.")

    import stripe
    stripe.api_key = settings.stripe_secret_key
    portal = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url="rpgagent://billing/portal/return",
    )
    return {"portal_url": portal.url}


@router.get("/companies/{company_id}/billing/invoices")
async def list_invoices(company_id: str, db: DbSession):
    """List Stripe invoices for the company's billing subscription."""
    svc = CompanyService(db)
    company = await svc.get_company(company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    from app.core.config import get_settings
    settings = get_settings()
    if not settings.stripe_secret_key:
        return {"invoices": []}

    sub = await get_or_create_subscription(db, company)
    if not sub.stripe_customer_id:
        return {"invoices": []}

    import stripe
    stripe.api_key = settings.stripe_secret_key
    invoices = stripe.Invoice.list(customer=sub.stripe_customer_id, limit=20)
    return {
        "invoices": [
            {
                "id": inv.id,
                "number": inv.number,
                "amount_paid": inv.amount_paid,
                "currency": inv.currency,
                "status": inv.status,
                "created": inv.created,
                "hosted_invoice_url": inv.hosted_invoice_url,
                "invoice_pdf": inv.invoice_pdf,
            }
            for inv in invoices.data
        ]
    }


@router.get("/companies/{company_id}/billing/init")
async def init_subscription(company_id: str, db: DbSession):
    """Ensure a trial subscription exists for the company."""
    svc = CompanyService(db)
    company = await svc.get_company(company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    sub = await get_or_create_subscription(db, company)
    await db.commit()
    status = await get_subscription_status(db, company_id)
    return status
