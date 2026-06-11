from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from app.api.deps import DbSession, verify_api_key
from app.schemas.api import StripeOnboardingCreate, StripeOnboardingOut, StripeStatusOut
from app.services.company import CompanyService
from app.services.stripe_connect import create_onboarding_link, fetch_connect_status

router = APIRouter(dependencies=[Depends(verify_api_key)])

# These are public (no API key) — Stripe redirects here after onboarding
_public_router = APIRouter()


@_public_router.get("/stripe/connect/return", response_class=HTMLResponse)
async def stripe_connect_return():
    """Stripe redirects here after Connect onboarding completion."""
    return HTMLResponse("""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{background:#000;color:#fff;font-family:monospace;display:flex;align-items:center;
justify-content:center;height:100vh;margin:0;text-align:center}
h2{font-size:1.2rem;letter-spacing:.1em}p{opacity:.5;font-size:.8rem}</style>
</head><body>
<div><h2>✓ STRIPE CONNECTÉ</h2><p>Vous pouvez retourner dans l'application.</p>
<script>setTimeout(()=>{ try{window.location='rpgagent://stripe/return';}catch(e){} },500);</script>
</div></body></html>""")


@_public_router.get("/stripe/connect/refresh", response_class=HTMLResponse)
async def stripe_connect_refresh():
    """Stripe redirects here when the link expired and needs refreshing."""
    return HTMLResponse("""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{background:#000;color:#fff;font-family:monospace;display:flex;align-items:center;
justify-content:center;height:100vh;margin:0;text-align:center}
h2{font-size:1.2rem;letter-spacing:.1em}p{opacity:.5;font-size:.8rem}</style>
</head><body>
<div><h2>⟳ LIEN EXPIRÉ</h2><p>Retournez dans l'application pour relancer la configuration.</p>
<script>setTimeout(()=>{ try{window.location='rpgagent://stripe/refresh';}catch(e){} },500);</script>
</div></body></html>""")


@router.get("/companies/{company_id}/stripe/status", response_model=StripeStatusOut)
async def stripe_status(company_id: str, db: DbSession):
    svc = CompanyService(db)
    company = await svc.get_company(company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    if not company.stripe_connect_account_id:
        return StripeStatusOut(status="not_started")

    data = await fetch_connect_status(company.stripe_connect_account_id)
    return StripeStatusOut(
        status=data.get("status", "pending"),
        charges_enabled=data.get("charges_enabled", False),
        payouts_enabled=data.get("payouts_enabled", False),
    )


@router.post("/companies/{company_id}/stripe/onboarding", response_model=StripeOnboardingOut)
async def stripe_onboarding(
    company_id: str,
    db: DbSession,
    body: StripeOnboardingCreate | None = None,
):
    svc = CompanyService(db)
    company = await svc.get_company(company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    try:
        link = await create_onboarding_link(company, db, country=body.country if body else None)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    return StripeOnboardingOut(url=link.get("url", ""))
