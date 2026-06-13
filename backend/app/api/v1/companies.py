from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select

from app.api.deps import DbSession, verify_api_key
from app.agents.mission_catalog import MISSION_CATALOG
from app.core.config import get_settings
from app.models.entities import BetaFeedback, Mission, MissionLog, MissionStatus, QuestStepStatus
from app.schemas.api import BetaFeedbackCreate, BetaFeedbackOut, CompanyCreate, CompanyOut, WalletOut
from app.services.company import CompanyService
from app.services.quest_chain import QuestChainService
from app.services.wallet import WalletService
from app.workers.runner import schedule_mission_run

router = APIRouter(dependencies=[Depends(verify_api_key)])

AUTO_MISSIONS: list[str] = ["market_scan"]
WEBSITE_MISSION_TYPES = ("landing_page", "landing_page_revision")


async def _company_out(company, wallet) -> CompanyOut:
    from app.services.site_hosting import build_gateway_url, get_live_artifact
    from app.services.stripe_connect import fetch_connect_status, get_stripe_status
    from app.core.database import SessionLocal
    settings = get_settings()

    # Check if a live site artifact exists for this company. Website status is
    # mission-aware: active generation beats an older live/completed quest state.
    site_url: str | None = None
    site_version: int | None = None
    site_status = "not_created"
    if company.slug:
        async with SessionLocal() as _db:
            from sqlalchemy import select as _sel
            from app.models.entities import Mission, MissionStatus as _MS, TaskSource as _TS

            publishing = await _db.execute(
                _sel(Mission)
                .where(
                    Mission.company_id == company.id,
                    Mission.mission_type.in_(WEBSITE_MISSION_TYPES),
                    (
                        (Mission.status == _MS.RUNNING)
                        | (
                            (Mission.status == _MS.PENDING)
                            & (
                                Mission.source.is_(None)
                                | (Mission.source != _TS.CEO_PROPOSAL)
                            )
                        )
                    ),
                )
                .order_by(Mission.created_at.desc())
                .limit(1)
            )
            is_publishing = publishing.scalar_one_or_none() is not None

            artifact = await get_live_artifact(_db, company.slug)
            if artifact:
                site_url = build_gateway_url(company.slug)
                site_version = artifact.version
                site_status = "publishing" if is_publishing else "live"
            elif is_publishing:
                site_status = "publishing"
            else:
                # Check if last website mission failed
                failed = await _db.execute(
                    _sel(Mission)
                    .where(
                        Mission.company_id == company.id,
                        Mission.mission_type.in_(WEBSITE_MISSION_TYPES),
                        Mission.status == _MS.FAILED,
                    )
                    .order_by(Mission.created_at.desc())
                    .limit(1)
                )
                if failed.scalar_one_or_none():
                    site_status = "failed"
    stripe_status = get_stripe_status(company)
    if company.stripe_connect_account_id:
        try:
            data = await fetch_connect_status(company.stripe_connect_account_id)
            stripe_status = data.get("status", stripe_status)
        except Exception:
            pass

    return CompanyOut(
        id=company.id,
        name=company.name,
        slug=company.slug,
        mission_statement=company.mission_statement,
        product_description=company.product_description,
        target_audience=company.target_audience,
        business_type=company.business_type,
        level=company.level,
        xp=company.xp,
        buildings=company.buildings,
        render_url=company.render_url,
        site_url=site_url,
        site_version=site_version,
        site_status=site_status,
        stripe_connect_status=stripe_status,
        daily_ads_budget_cents=company.daily_ads_budget_cents or 0,
        ads_wallet_balance_cents=company.ads_wallet_balance_cents or 0,
        auto_pilot=company.auto_pilot or False,
        product_image_url=company.product_image_url,
        wallet=WalletOut(
            credits_balance=wallet.credits_balance,
            credits_cap=settings.credits_cap,
            daily_free_credits=settings.daily_free_credits,
        ),
    )


@router.post("/{user_id}", response_model=CompanyOut)
async def create_company(user_id: str, body: CompanyCreate, background_tasks: BackgroundTasks, db: DbSession):
    svc = CompanyService(db)
    company = await svc.create_company(user_id, body)
    await db.commit()
    company = await svc.get_company(company.id)
    if not company or not company.wallet:
        raise HTTPException(500, "Failed to create company")
    wallet_svc = WalletService(db)
    await wallet_svc.apply_daily_regen(company.wallet)
    await db.commit()

    chain_svc = QuestChainService(db)
    await chain_svc.initialize_chain(company.id, company.business_type)

    await _launch_auto_missions(db, company, background_tasks)

    return await _company_out(company, company.wallet)


async def _launch_auto_missions(db, company, background_tasks: BackgroundTasks):
    from app.services.quest_chain import QuestChainService
    from app.workers.runner import _run_mission

    chain_svc = QuestChainService(db)
    step1 = await chain_svc.get_step(company.id, 1)

    for mission_type in AUTO_MISSIONS:
        catalog = MISSION_CATALOG.get(mission_type)
        if not catalog:
            continue
        mission = Mission(
            company_id=company.id,
            agent_type=catalog.agent_type,
            mission_type=mission_type,
            status=MissionStatus.PENDING,
            credits_cost=0,
            xp_reward=int(catalog.credits_cost * 1.0),
            is_auto_generated=True,
        )
        db.add(mission)
        await db.flush()
        db.add(MissionLog(
            mission_id=mission.id,
            step="auto_created",
            message=f"Mission {mission_type} lancee automatiquement",
        ))
        if step1 and step1.mission_type == mission_type and step1.status == QuestStepStatus.AVAILABLE:
            await chain_svc.mark_step_running(company.id, 1, mission.id)
    await db.commit()

    result = await db.execute(
        select(Mission).where(
            Mission.company_id == company.id,
            Mission.is_auto_generated == True,
            Mission.status == MissionStatus.PENDING,
        )
    )
    for mission in result.scalars().all():
        schedule_mission_run(mission.id)
        background_tasks.add_task(_run_mission, mission.id)


@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(company_id: str, db: DbSession):
    svc = CompanyService(db)
    company = await svc.get_company(company_id)
    if not company or not company.wallet:
        raise HTTPException(404, "Company not found")
    wallet_svc = WalletService(db)
    await wallet_svc.apply_daily_regen(company.wallet)
    await db.commit()
    return await _company_out(company, company.wallet)


@router.delete("/{company_id}", status_code=204)
async def delete_company(company_id: str, db: DbSession):
    """Delete a company and all its data + infra (debug / reset flow)."""
    from sqlalchemy import delete as _del
    from app.models.entities import (
        AdCampaign, AdCreative, AdSnapshot, BetaFeedback, Building,
        BrowserSession, CompanyAsset, CompanyEmail, CompanyMemory,
        CompanyNotification, CompanySkill, GodModeSession, Learning,
        LLMCall, Mission, MissionLog, Order, PaymentLink, QuestStep,
        RecurringMission, Subscription, TokenUsage, ToolCallLog,
        WalletTransaction, Wallet,
    )

    company_result = await db.execute(
        select(Company).where(Company.id == company_id)
    )
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")

    # Tear down infra best-effort (non-blocking)
    if company.render_service_id or company.github_repo_url or company.neon_project_id:
        try:
            from app.services.infra import InfraService
            infra = InfraService()
            await infra.delete_all_infra(
                company.slug or company.name,
                service_id=company.render_service_id or "",
                neon_project_id=company.neon_project_id or "",
            )
        except Exception:
            pass

    mission_ids_subq = select(Mission.id).where(Mission.company_id == company_id)

    for stmt in [
        # Mission logs first (FK to missions)
        _del(MissionLog).where(MissionLog.mission_id.in_(mission_ids_subq)),
        _del(TokenUsage).where(TokenUsage.company_id == company_id),
        _del(LLMCall).where(LLMCall.company_id == company_id),
        _del(ToolCallLog).where(ToolCallLog.company_id == company_id),
        _del(BrowserSession).where(BrowserSession.company_id == company_id),
        # Ads
        _del(AdCreative).where(AdCreative.company_id == company_id),
        _del(AdSnapshot).where(AdSnapshot.company_id == company_id),
        _del(AdCampaign).where(AdCampaign.company_id == company_id),
        # Missions
        _del(Mission).where(Mission.company_id == company_id),
        _del(QuestStep).where(QuestStep.company_id == company_id),
        # Company data
        _del(Building).where(Building.company_id == company_id),
        _del(CompanyMemory).where(CompanyMemory.company_id == company_id),
        _del(CompanyAsset).where(CompanyAsset.company_id == company_id),
        _del(CompanyEmail).where(CompanyEmail.company_id == company_id),
        _del(CompanyNotification).where(CompanyNotification.company_id == company_id),
        _del(CompanySkill).where(CompanySkill.company_id == company_id),
        _del(BetaFeedback).where(BetaFeedback.company_id == company_id),
        _del(RecurringMission).where(RecurringMission.company_id == company_id),
        _del(Learning).where(Learning.source_company_id == company_id),
        # Billing
        _del(WalletTransaction).where(WalletTransaction.company_id == company_id),
        _del(PaymentLink).where(PaymentLink.company_id == company_id),
        _del(GodModeSession).where(GodModeSession.company_id == company_id),
        _del(Order).where(Order.company_id == company_id),
        _del(Subscription).where(Subscription.company_id == company_id),
        _del(Wallet).where(Wallet.company_id == company_id),
        # Company itself
        _del(Company).where(Company.id == company_id),
    ]:
        await db.execute(stmt)

    await db.commit()


@router.post(
    "/{company_id}/feedback",
    response_model=BetaFeedbackOut,
)
async def submit_beta_feedback(
    company_id: str, body: BetaFeedbackCreate, db: DbSession
):
    svc = CompanyService(db)
    company = await svc.get_company(company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    feedback = BetaFeedback(
        company_id=company_id,
        mission_id=body.mission_id,
        mission_type=body.mission_type,
        used_deliverable=body.used_deliverable,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return feedback


@router.get(
    "/{company_id}/feedback",
    response_model=list[BetaFeedbackOut],
)
async def list_beta_feedback(company_id: str, db: DbSession):
    result = await db.execute(
        select(BetaFeedback)
        .where(BetaFeedback.company_id == company_id)
        .order_by(BetaFeedback.created_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())
