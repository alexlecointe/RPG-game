from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DbSession, verify_api_key
from app.models.entities import AdCampaign, AdCampaignStatus, AdCreative
from app.schemas.api import AdCampaignOut, AdCreativeOut, AdsSummaryOut, WalletTransactionOut
from app.services.ads import (
    apply_scale_campaign,
    apply_split_winner,
    charge_ads_wallet,
    get_ads_summary,
    get_wallet_transactions,
    launch_ads_v1,
    monitor_campaigns,
    run_ads_daily_cycle,
    set_daily_budget,
)
from app.services.company import CompanyService

router = APIRouter(dependencies=[Depends(verify_api_key)])
logger = structlog.get_logger()


class AdsBudgetBody(BaseModel):
    daily_budget_cents: int = Field(..., ge=100, description="Daily budget in cents, e.g. 1000 = 10 EUR")


class AdsLaunchBody(BaseModel):
    campaign_name: str = ""
    video_urls: list[str] = Field(default_factory=list)
    headlines: list[str] = Field(default_factory=list)
    bodies: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=lambda: ["FR"], description="ISO country codes")
    age_min: int | None = Field(default=None, ge=13, le=65)
    age_max: int | None = Field(default=None, ge=18, le=65)
    call_to_action: str | None = Field(default=None, description="SHOP_NOW | DOWNLOAD | LEARN_MORE | SIGN_UP")
    objective: str | None = Field(default=None, description="OUTCOME_SALES | OUTCOME_APP_INSTALLS | OUTCOME_LEADS")
    auto_generate_videos: bool = Field(default=True, description="Generate/reuse videos if video_urls are missing")


class AdsLaunchQueuedOut(BaseModel):
    queued: bool
    task_id: str


class AdsLaunchTaskStatusOut(BaseModel):
    task_id: str
    state: str
    result: dict | None = None
    error: str | None = None


async def _launch_ads_background(company_id: str, payload: dict, placeholder_id: str) -> None:
    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        try:
            company = await CompanyService(db).get_company(company_id)
            if not company:
                raise ValueError("company_not_found")
            if company.daily_ads_budget_cents <= 0:
                raise ValueError("ads_budget_required")

            campaign = await launch_ads_v1(
                db,
                company,
                payload.get("campaign_name", ""),
                company.daily_ads_budget_cents,
                payload.get("video_urls") or [],
                payload.get("headlines") or [],
                payload.get("bodies") or [],
                countries=payload.get("countries") or ["FR"],
                age_min=payload.get("age_min"),
                age_max=payload.get("age_max"),
                call_to_action=payload.get("call_to_action"),
                objective=payload.get("objective"),
                auto_generate_videos=payload.get("auto_generate_videos", True),
            )

            placeholder = await db.get(AdCampaign, placeholder_id)
            if placeholder and placeholder.meta_campaign_id is None:
                await db.delete(placeholder)
                await db.commit()

            logger.info(
                "ads_launch_background_done",
                company_id=company_id,
                campaign_id=campaign.id,
                meta_campaign_id=campaign.meta_campaign_id,
            )
        except Exception as exc:
            placeholder = await db.get(AdCampaign, placeholder_id)
            if placeholder:
                placeholder.status = AdCampaignStatus.BLOCKED
                placeholder.targeting_json = json.dumps({
                    "launch_error": str(exc),
                    "phase": "background_launch",
                })
                await db.commit()
            logger.warning("ads_launch_background_failed", company_id=company_id, error=str(exc))


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


@router.post("/companies/{company_id}/ads/daily-cycle")
async def ads_daily_cycle(company_id: str, db: DbSession):
    """Manually run the Polsia-like ads daily cycle for QA/testing."""
    try:
        return await run_ads_daily_cycle(db, company_id, charge_wallet=True)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/companies/{company_id}/ads/launch", response_model=AdCampaignOut)
async def launch_ads(
    company_id: str,
    body: AdsLaunchBody,
    db: DbSession,
    background_tasks: BackgroundTasks,
):
    svc = CompanyService(db)
    company = await svc.get_company(company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    if company.daily_ads_budget_cents <= 0:
        raise HTTPException(400, "Set daily budget first")

    existing = await db.execute(
        select(AdCampaign)
        .where(
            AdCampaign.company_id == company_id,
            AdCampaign.meta_campaign_id.is_(None),
            AdCampaign.name == "Preparing Meta Ads",
        )
    )
    placeholders = list(existing.scalars().all())

    pending = next((campaign for campaign in placeholders if campaign.status == AdCampaignStatus.DRAFT), None)
    if pending:
        created_at = getattr(pending, "created_at", None)
        is_stale = bool(
            created_at
            and (datetime.now(timezone.utc) - created_at) > timedelta(minutes=15)
        )
        if not is_stale:
            return pending
        await db.delete(pending)
        placeholders = [campaign for campaign in placeholders if campaign.id != pending.id]
        await db.commit()
        logger.info("ads_launch_stale_pending_cleanup", company_id=company_id, campaign_id=pending.id)

    # Clean up stale local placeholders from previous failed attempts. If there is
    # no Meta campaign id attached, these rows are only local "preparing" shells.
    for placeholder in placeholders:
        await db.delete(placeholder)
    if placeholders:
        await db.commit()
        logger.info("ads_launch_placeholder_cleanup", company_id=company_id, removed=len(placeholders))

    campaign = AdCampaign(
        company_id=company.id,
        name="Preparing Meta Ads",
        status=AdCampaignStatus.DRAFT,
        daily_budget_cents=company.daily_ads_budget_cents,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    background_tasks.add_task(_launch_ads_background, company_id, body.model_dump(), campaign.id)

    return campaign


@router.post("/companies/{company_id}/ads/launch-async", response_model=AdsLaunchQueuedOut)
async def launch_ads_async(company_id: str, body: AdsLaunchBody, db: DbSession):
    svc = CompanyService(db)
    company = await svc.get_company(company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    if company.daily_ads_budget_cents <= 0:
        raise HTTPException(400, "Set daily budget first")

    from app.workers.celery_app import launch_ads_task

    task = launch_ads_task.apply_async(args=[company_id, body.model_dump()], queue="ads")
    return {"queued": True, "task_id": task.id}


@router.get("/companies/{company_id}/ads/launch-status/{task_id}", response_model=AdsLaunchTaskStatusOut)
async def ads_launch_status(company_id: str, task_id: str):
    from app.workers.celery_app import celery_app

    result = celery_app.AsyncResult(task_id)
    payload = result.result if isinstance(result.result, dict) else None
    error = None
    if result.failed():
        error = str(result.result)
    return {
        "task_id": task_id,
        "state": result.state,
        "result": payload,
        "error": error,
    }


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


@router.get("/companies/{company_id}/ads/summary", response_model=AdsSummaryOut)
async def ads_summary(company_id: str, db: DbSession):
    """Polsia-like dashboard: global state + contextual message + metrics + wallet + campaigns."""
    try:
        summary = await get_ads_summary(db, company_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return summary


@router.get("/companies/{company_id}/ads/transactions", response_model=list[WalletTransactionOut])
async def ads_transactions(company_id: str, db: DbSession, limit: int = 20):
    """Return recent wallet transaction history for the ads wallet."""
    transactions = await get_wallet_transactions(db, company_id, limit=min(limit, 100))
    return [
        {
            "id": t.id,
            "company_id": t.company_id,
            "amount_cents": t.amount_cents,
            "type": t.type,
            "note": t.note,
            "created_at": t.created_at.isoformat(),
        }
        for t in transactions
    ]


@router.post("/companies/{company_id}/ads/campaigns/{campaign_id}/pause")
async def pause_campaign(company_id: str, campaign_id: str, db: DbSession):
    campaign = await db.get(AdCampaign, campaign_id)
    if not campaign or campaign.company_id != company_id:
        raise HTTPException(404, "Campaign not found")

    from app.core.config import get_settings
    from app.agents.tools.meta_ads_action import update_campaign_status
    from app.models.entities import Company as CompanyModel, AdCampaignStatus as ACS

    settings = get_settings()
    campaign.status = AdCampaignStatus.PAUSED
    if campaign.meta_campaign_id and settings.meta_capi_token:
        try:
            await update_campaign_status(settings.meta_capi_token, campaign.meta_campaign_id, "PAUSED")
        except Exception:
            pass

    # Mark winding_down if all remaining campaigns are now paused
    from sqlalchemy import select as sa_select
    company = await db.get(CompanyModel, company_id)
    if company:
        result = await db.execute(sa_select(AdCampaign).where(AdCampaign.company_id == company_id))
        all_camps = list(result.scalars().all())
        if all_camps and all(c.status == ACS.PAUSED for c in all_camps):
            company.ads_winding_down = True

    await db.commit()
    return {"campaign_id": campaign_id, "status": "paused"}


@router.post("/companies/{company_id}/ads/campaigns/{campaign_id}/resume")
async def resume_campaign(company_id: str, campaign_id: str, db: DbSession):
    campaign = await db.get(AdCampaign, campaign_id)
    if not campaign or campaign.company_id != company_id:
        raise HTTPException(404, "Campaign not found")

    from app.core.config import get_settings
    from app.agents.tools.meta_ads_action import update_campaign_status
    from app.models.entities import Company as CompanyModel

    settings = get_settings()
    campaign.status = AdCampaignStatus.ACTIVE
    if campaign.meta_campaign_id and settings.meta_capi_token:
        try:
            await update_campaign_status(settings.meta_capi_token, campaign.meta_campaign_id, "ACTIVE")
        except Exception:
            pass

    # Resuming clears winding_down flag
    company = await db.get(CompanyModel, company_id)
    if company:
        company.ads_winding_down = False

    await db.commit()
    return {"campaign_id": campaign_id, "status": "active"}


@router.post("/companies/{company_id}/ads/campaigns/{campaign_id}/apply-scale")
async def apply_scale(company_id: str, campaign_id: str, db: DbSession):
    """User applies scaling recommendation: increase campaign budget +20%."""
    try:
        result = await apply_scale_campaign(db, company_id, campaign_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return result


@router.post("/companies/{company_id}/ads/campaigns/{campaign_id}/apply-split-winner")
async def apply_split(company_id: str, campaign_id: str, db: DbSession):
    """User applies split test result: pause losers, scale winner budget."""
    try:
        result = await apply_split_winner(db, company_id, campaign_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return result


@router.post("/companies/{company_id}/ads/monitor")
async def monitor_ads(company_id: str, db: DbSession):
    snapshots = await monitor_campaigns(db, company_id)
    return {"snapshots": len(snapshots)}
