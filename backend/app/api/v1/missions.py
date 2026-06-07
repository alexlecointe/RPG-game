from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import DbSession, verify_api_key
from app.agents.mission_catalog import MISSION_CATALOG, get_suggested_split
from app.models.entities import Mission, MissionLog, MissionStatus
from app.schemas.api import (
    ActivityFeedOut, MissionCreate, MissionLogOut, MissionOut,
    MissionPreviewOut, MissionSplitItem, RecurringMissionCreate, RecurringMissionOut,
)
from app.services.mission import MissionService

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/companies/{company_id}/missions", response_model=list[MissionOut])
async def list_missions(company_id: str, db: DbSession):
    svc = MissionService(db)
    return await svc.list_missions(company_id)


@router.get("/companies/{company_id}/missions/preview/{mission_type}", response_model=MissionPreviewOut)
async def preview_mission(company_id: str, mission_type: str, db: DbSession):
    """Preview a mission before launching — shows cost, complexity, and affordability."""
    catalog = MISSION_CATALOG.get(mission_type)
    if not catalog:
        raise HTTPException(400, detail="unknown_mission_type")

    from app.services.company import CompanyService
    from app.services.wallet import WalletService

    company_svc = CompanyService(db)
    company = await company_svc.get_company(company_id)
    if not company or not company.wallet:
        raise HTTPException(404, detail="company_not_found")

    wallet_svc = WalletService(db)
    wallet = await wallet_svc.apply_daily_regen(company.wallet)

    split = get_suggested_split(mission_type)

    return MissionPreviewOut(
        mission_type=catalog.mission_type,
        title=catalog.title,
        description=catalog.description,
        credits_cost=catalog.credits_cost,
        credits_remaining=wallet.credits_balance,
        can_afford=wallet.credits_balance >= catalog.credits_cost,
        estimated_minutes=catalog.estimated_minutes,
        complexity=catalog.complexity,
        max_images=catalog.max_images,
        agent_type=catalog.agent_type,
        suggested_split=[MissionSplitItem(**s) for s in split],
    )


@router.get(
    "/companies/{company_id}/missions/suggest-split/{mission_type}",
    response_model=list[MissionSplitItem],
)
async def suggest_split(company_id: str, mission_type: str):
    """Suggest sub-missions for a complex mission (Polsia cofounder-layer pattern)."""
    return [MissionSplitItem(**s) for s in get_suggested_split(mission_type)]


@router.post("/companies/{company_id}/missions", response_model=MissionOut)
async def start_mission(company_id: str, body: MissionCreate, db: DbSession):
    svc = MissionService(db)
    try:
        mission = await svc.start_mission(company_id, body.mission_type)
    except ValueError as e:
        code = str(e)
        status = 400
        if code == "insufficient_credits":
            status = 402
        elif code == "rate_limit_exceeded":
            status = 429
        raise HTTPException(status, detail=code) from e
    return mission


@router.get("/missions/{mission_id}", response_model=MissionOut)
async def get_mission(mission_id: str, db: DbSession):
    svc = MissionService(db)
    mission = await svc.get_mission(mission_id)
    if not mission:
        raise HTTPException(404, "Mission not found")
    return mission


@router.get("/missions/{mission_id}/tool-calls")
async def get_tool_calls(mission_id: str, db: DbSession):
    """Return the full audit log of tool calls for a mission."""
    from app.models.entities import ToolCallLog
    result = await db.execute(
        select(ToolCallLog)
        .where(ToolCallLog.mission_id == mission_id)
        .order_by(ToolCallLog.created_at.asc())
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "tool_name": r.tool_name,
            "arguments": r.arguments_json,
            "result_preview": r.result_preview,
            "status": r.status,
            "duration_ms": r.duration_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/missions/{mission_id}/logs", response_model=list[MissionLogOut])
async def get_mission_logs(mission_id: str, db: DbSession):
    result = await db.execute(
        select(MissionLog)
        .where(MissionLog.mission_id == mission_id)
        .order_by(MissionLog.created_at.asc())
    )
    return list(result.scalars().all())


@router.get("/companies/{company_id}/activity-feed", response_model=list[ActivityFeedOut])
async def get_activity_feed(company_id: str, db: DbSession, limit: int = 50):
    result = await db.execute(
        select(MissionLog, Mission)
        .join(Mission, MissionLog.mission_id == Mission.id)
        .where(Mission.company_id == company_id)
        .order_by(MissionLog.created_at.desc())
        .limit(limit)
    )
    rows = result.all()
    return [
        ActivityFeedOut(
            mission_id=log.mission_id,
            agent_type=mission.agent_type,
            mission_type=mission.mission_type,
            mission_status=mission.status,
            step=log.step,
            message=log.message,
            created_at=log.created_at,
        )
        for log, mission in rows
    ]


@router.get("/missions/{mission_id}/stream")
async def stream_mission_logs(mission_id: str, db: DbSession):
    svc = MissionService(db)
    mission = await svc.get_mission(mission_id)
    if not mission:
        raise HTTPException(404, "Mission not found")

    async def event_generator():
        from app.core.database import SessionLocal

        seen_ids: set[str] = set()

        for _ in range(120):
            async with SessionLocal() as poll_db:
                result = await poll_db.execute(
                    select(MissionLog)
                    .where(MissionLog.mission_id == mission_id)
                    .order_by(MissionLog.created_at.asc())
                )
                logs = list(result.scalars().all())

                for log in logs:
                    if log.id not in seen_ids:
                        seen_ids.add(log.id)
                        data = json.dumps({
                            "step": log.step,
                            "message": log.message,
                        }, ensure_ascii=False)
                        yield f"data: {data}\n\n"

                mission_result = await poll_db.execute(
                    select(Mission).where(Mission.id == mission_id)
                )
                m = mission_result.scalar_one_or_none()
                if m and m.status in (MissionStatus.COMPLETED, MissionStatus.FAILED):
                    done_data = json.dumps({
                        "step": "done",
                        "message": f"Mission {m.status.value}",
                        "status": m.status.value,
                    }, ensure_ascii=False)
                    yield f"data: {done_data}\n\n"
                    return

            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Recurring missions
# ---------------------------------------------------------------------------


@router.post(
    "/companies/{company_id}/recurring-missions",
    response_model=RecurringMissionOut,
)
async def create_recurring_mission(
    company_id: str, body: RecurringMissionCreate, db: DbSession,
):
    """Create a recurring mission schedule for a company."""
    from datetime import datetime, timedelta, timezone
    from app.models.entities import RecurringMission

    catalog = MISSION_CATALOG.get(body.mission_type)
    if not catalog:
        raise HTTPException(400, detail="unknown_mission_type")

    now = datetime.now(timezone.utc)
    next_run = now.replace(hour=body.hour_utc, minute=0, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)

    rm = RecurringMission(
        company_id=company_id,
        mission_type=body.mission_type,
        frequency=body.frequency,
        day_of_week=body.day_of_week,
        day_of_month=body.day_of_month,
        hour_utc=body.hour_utc,
        next_run_at=next_run,
    )
    db.add(rm)
    await db.commit()
    await db.refresh(rm)
    return rm


@router.get(
    "/companies/{company_id}/recurring-missions",
    response_model=list[RecurringMissionOut],
)
async def list_recurring_missions(company_id: str, db: DbSession):
    from app.models.entities import RecurringMission
    result = await db.execute(
        select(RecurringMission)
        .where(RecurringMission.company_id == company_id)
        .order_by(RecurringMission.created_at.desc())
    )
    return list(result.scalars().all())


@router.delete("/recurring-missions/{recurring_id}")
async def delete_recurring_mission(recurring_id: str, db: DbSession):
    from app.models.entities import RecurringMission
    result = await db.execute(
        select(RecurringMission).where(RecurringMission.id == recurring_id)
    )
    rm = result.scalar_one_or_none()
    if not rm:
        raise HTTPException(404, detail="recurring_mission_not_found")
    rm.is_active = False
    await db.commit()
    return {"status": "deactivated", "id": recurring_id}
