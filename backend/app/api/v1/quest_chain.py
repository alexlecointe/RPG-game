from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import DbSession, verify_api_key
from app.agents.mission_catalog import MISSION_CATALOG
from app.models.entities import BusinessType, Mission, MissionLog, MissionStatus, QuestStepStatus
from app.schemas.api import MissionOut, QuestStepOut
from app.services.company import CompanyService
from app.services.mission import MissionService
from app.services.quest_chain import BUILDING_NAMES, QuestChainService

router = APIRouter(dependencies=[Depends(verify_api_key)])


def _step_out(step) -> QuestStepOut:
    return QuestStepOut(
        id=step.id,
        step_number=step.step_number,
        mission_type=step.mission_type,
        title=step.title,
        description=step.description,
        agent_type=step.agent_type,
        status=step.status,
        mission_id=step.mission_id,
        building_name=BUILDING_NAMES.get(step.agent_type.value, ""),
        unlocked_at=step.unlocked_at,
        completed_at=step.completed_at,
    )


@router.get(
    "/companies/{company_id}/quest-chain",
    response_model=list[QuestStepOut],
)
async def get_quest_chain(company_id: str, db: DbSession):
    svc = QuestChainService(db)
    chain = await svc.get_chain(company_id)
    if not chain:
        company_svc = CompanyService(db)
        company = await company_svc.get_company(company_id)
        bt = company.business_type if company else BusinessType.ECOMMERCE
        chain = await svc.initialize_chain(company_id, bt)
    return [_step_out(s) for s in chain]


@router.post(
    "/companies/{company_id}/quest-chain/{step_number}/start",
    response_model=MissionOut,
)
async def start_quest_step(company_id: str, step_number: int, db: DbSession):
    from app.workers.runner import schedule_mission_run
    from sqlalchemy import select

    chain_svc = QuestChainService(db)
    step = await chain_svc.get_step(company_id, step_number)

    if not step:
        raise HTTPException(404, "Step not found")
    if step.status == QuestStepStatus.COMPLETED:
        raise HTTPException(400, "Step already completed")
    if step.status == QuestStepStatus.LOCKED:
        raise HTTPException(400, "Step is locked — complete prerequisites first")

    mission_svc = MissionService(db)

    # If step is already RUNNING, check if the mission runner is alive.
    # If mission is stuck in pending/running for > 3min, re-schedule the runner.
    if step.status == QuestStepStatus.RUNNING and step.mission_id:
        existing = await mission_svc.get_mission(step.mission_id)
        if existing and existing.status in (MissionStatus.PENDING, MissionStatus.RUNNING):
            from datetime import datetime, timezone, timedelta
            stuck_threshold = datetime.now(timezone.utc) - timedelta(minutes=3)
            ref_time = existing.started_at or existing.created_at
            if ref_time and ref_time.replace(tzinfo=timezone.utc) < stuck_threshold:
                # Mission is stuck — refire the runner
                schedule_mission_run(existing.id)
            return existing
        if existing and existing.status == MissionStatus.COMPLETED:
            raise HTTPException(400, "Step already completed")

    try:
        mission = await mission_svc.start_mission(
            company_id, step.mission_type, auto_schedule=False
        )
    except ValueError as e:
        code = str(e)
        status = 400
        if code in ("insufficient_credits", "no_credits"):
            status = 402
        elif code == "rate_limit_exceeded":
            status = 429
        raise HTTPException(status, detail=code) from e

    # Quest chain steps are CEO-proposed roadmap tasks
    from app.models.entities import TaskSource
    mission.source = TaskSource.CEO_PROPOSAL
    await db.commit()

    await chain_svc.mark_step_running(company_id, step_number, mission.id)

    # Fire the runner immediately — quest chain steps always execute right away
    schedule_mission_run(mission.id)

    return mission
