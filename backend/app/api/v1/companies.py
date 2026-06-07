from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.deps import DbSession, verify_api_key
from app.agents.mission_catalog import MISSION_CATALOG
from app.core.config import get_settings
from app.models.entities import BetaFeedback, Mission, MissionLog, MissionStatus
from app.schemas.api import BetaFeedbackCreate, BetaFeedbackOut, CompanyCreate, CompanyOut, WalletOut
from app.services.company import CompanyService
from app.services.quest_chain import QuestChainService
from app.services.wallet import WalletService
from app.workers.runner import schedule_mission_run

router = APIRouter(dependencies=[Depends(verify_api_key)])

AUTO_MISSIONS: list[str] = []


def _company_out(company, wallet) -> CompanyOut:
    settings = get_settings()
    return CompanyOut(
        id=company.id,
        name=company.name,
        mission_statement=company.mission_statement,
        product_description=company.product_description,
        target_audience=company.target_audience,
        business_type=company.business_type,
        level=company.level,
        xp=company.xp,
        buildings=company.buildings,
        wallet=WalletOut(
            credits_balance=wallet.credits_balance,
            credits_cap=settings.credits_cap,
            daily_free_credits=settings.daily_free_credits,
        ),
    )


@router.post("/{user_id}", response_model=CompanyOut)
async def create_company(user_id: str, body: CompanyCreate, db: DbSession):
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

    await _launch_auto_missions(db, company)

    return _company_out(company, company.wallet)


async def _launch_auto_missions(db, company):
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


@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(company_id: str, db: DbSession):
    svc = CompanyService(db)
    company = await svc.get_company(company_id)
    if not company or not company.wallet:
        raise HTTPException(404, "Company not found")
    wallet_svc = WalletService(db)
    await wallet_svc.apply_daily_regen(company.wallet)
    await db.commit()
    return _company_out(company, company.wallet)


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
