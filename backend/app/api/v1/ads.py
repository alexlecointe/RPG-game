from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DbSession, verify_api_key
from app.models.entities import AdCampaign, AdCreative
from app.schemas.api import AdCampaignOut, AdCreativeOut
from app.services.ads import charge_ads_wallet, launch_meta_campaign, monitor_campaigns, set_daily_budget
from app.services.company import CompanyService

router = APIRouter(dependencies=[Depends(verify_api_key)])


class AdsBudgetBody(BaseModel):
    daily_budget_cents: int = Field(..., ge=100, description="Daily budget in cents, e.g. 1000 = 10 EUR")


class AdsLaunchBody(BaseModel):
    campaign_name: str = ""
    video_urls: list[str] = []
    headlines: list[str] = []
    bodies: list[str] = []


@router.post("/companies/{company_id}/ads/budget")
async def set_ads_budget(company_id: str, body: AdsBudgetBody, db: DbSession):
    company = await set_daily_budget(db, company_id, body.daily_budget_cents)
    return {"daily_budget_cents": company.daily_ads_budget_cents}


@router.post("/companies/{company_id}/ads/wallet/charge")
async def charge_wallet(company_id: str, db: DbSession):
    svc = CompanyService(db)
    company = await svc.get_company(company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    added = await charge_ads_wallet(db, company)
    return {"added_cents": added, "balance_cents": company.ads_wallet_balance_cents}


@router.post("/companies/{company_id}/ads/launch", response_model=AdCampaignOut)
async def launch_ads(company_id: str, body: AdsLaunchBody, db: DbSession):
    svc = CompanyService(db)
    company = await svc.get_company(company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    if company.daily_ads_budget_cents <= 0:
        raise HTTPException(400, "Set daily budget first")

    try:
        campaign = await launch_meta_campaign(
            db, company, body.campaign_name,
            company.daily_ads_budget_cents,
            body.video_urls, body.headlines, body.bodies,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    return campaign


@router.get("/companies/{company_id}/ads/campaigns", response_model=list[AdCampaignOut])
async def list_campaigns(company_id: str, db: DbSession):
    result = await db.execute(
        select(AdCampaign).where(AdCampaign.company_id == company_id)
    )
    return list(result.scalars().all())


@router.get("/companies/{company_id}/ads/creatives", response_model=list[AdCreativeOut])
async def list_creatives(company_id: str, db: DbSession):
    result = await db.execute(
        select(AdCreative).where(AdCreative.company_id == company_id)
    )
    return list(result.scalars().all())


@router.post("/companies/{company_id}/ads/monitor")
async def monitor_ads(company_id: str, db: DbSession):
    snapshots = await monitor_campaigns(db, company_id)
    return {"snapshots": len(snapshots)}
