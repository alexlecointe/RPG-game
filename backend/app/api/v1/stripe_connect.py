from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import DbSession, verify_api_key
from app.schemas.api import StripeOnboardingOut, StripeStatusOut
from app.services.company import CompanyService
from app.services.stripe_connect import create_onboarding_link, fetch_connect_status

router = APIRouter(dependencies=[Depends(verify_api_key)])


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
async def stripe_onboarding(company_id: str, db: DbSession):
    svc = CompanyService(db)
    company = await svc.get_company(company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    try:
        link = await create_onboarding_link(company, db)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    return StripeOnboardingOut(url=link.get("url", ""))
