"""Admin dashboard API — aggregated KPIs across all companies."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import case, cast, Date, func, select

from app.api.deps import DbSession, verify_api_key
from app.models.entities import BetaFeedback, Company, Mission, MissionStatus, TokenUsage, ToolCallLog
from app.schemas.api import (
    AdminCompanyRow,
    AdminErrorRow,
    AdminMissionRow,
    AdminOverview,
    AdminTokenSpendRow,
    AdminToolUsageRow,
    BetaFeedbackOut,
)

router = APIRouter(prefix="/admin", dependencies=[Depends(verify_api_key)])


@router.get("/overview", response_model=AdminOverview)
async def admin_overview(days: int = 30, db: DbSession = None):
    since = datetime.now(timezone.utc) - timedelta(days=days)

    company_count = (await db.execute(select(func.count(Company.id)))).scalar() or 0

    mission_result = await db.execute(
        select(Mission.status, func.count(Mission.id))
        .where(Mission.created_at >= since)
        .group_by(Mission.status)
    )
    status_map: dict[str, int] = {}
    total_missions = 0
    failed_count = 0
    for status, count in mission_result.all():
        status_map[status.value] = count
        total_missions += count
        if status == MissionStatus.FAILED:
            failed_count = count

    token_result = await db.execute(
        select(
            func.coalesce(func.sum(TokenUsage.total_tokens), 0),
            func.coalesce(func.sum(TokenUsage.estimated_cost_usd), 0.0),
        ).where(TokenUsage.created_at >= since)
    )
    token_row = token_result.one()

    return AdminOverview(
        total_companies=company_count,
        total_missions=total_missions,
        missions_by_status=status_map,
        total_tokens=token_row[0],
        total_cost_usd=round(token_row[1], 4),
        error_rate=round(failed_count / total_missions, 4) if total_missions else 0.0,
        period_days=days,
    )


@router.get("/companies", response_model=list[AdminCompanyRow])
async def admin_companies(
    limit: int = 50, offset: int = 0, db: DbSession = None,
):
    mission_sub = (
        select(
            Mission.company_id,
            func.count(Mission.id).label("mission_count"),
            func.avg(Mission.quality_score).label("avg_quality"),
            func.max(Mission.created_at).label("last_mission_at"),
        )
        .group_by(Mission.company_id)
        .subquery()
    )

    token_sub = (
        select(
            TokenUsage.company_id,
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(TokenUsage.estimated_cost_usd), 0.0).label("total_cost"),
        )
        .group_by(TokenUsage.company_id)
        .subquery()
    )

    result = await db.execute(
        select(
            Company,
            func.coalesce(mission_sub.c.mission_count, 0),
            func.coalesce(token_sub.c.total_tokens, 0),
            func.coalesce(token_sub.c.total_cost, 0.0),
            mission_sub.c.avg_quality,
            mission_sub.c.last_mission_at,
        )
        .outerjoin(mission_sub, Company.id == mission_sub.c.company_id)
        .outerjoin(token_sub, Company.id == token_sub.c.company_id)
        .order_by(Company.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    return [
        AdminCompanyRow(
            id=c.id,
            name=c.name,
            business_type=c.business_type.value,
            level=c.level,
            mission_count=mc,
            total_tokens=tt,
            total_cost_usd=round(tc, 4),
            avg_quality_score=round(aq, 2) if aq else None,
            last_mission_at=lm,
            created_at=c.created_at,
        )
        for c, mc, tt, tc, aq, lm in result.all()
    ]


@router.get("/missions", response_model=list[AdminMissionRow])
async def admin_missions(
    status: Optional[str] = None,
    company_id: Optional[str] = None,
    mission_type: Optional[str] = None,
    days: int = 30,
    limit: int = 50,
    offset: int = 0,
    db: DbSession = None,
):
    since = datetime.now(timezone.utc) - timedelta(days=days)

    token_sub = (
        select(
            TokenUsage.mission_id,
            func.coalesce(func.sum(TokenUsage.estimated_cost_usd), 0.0).label("cost"),
        )
        .group_by(TokenUsage.mission_id)
        .subquery()
    )

    q = (
        select(Mission, Company.name, func.coalesce(token_sub.c.cost, 0.0))
        .join(Company, Mission.company_id == Company.id)
        .outerjoin(token_sub, Mission.id == token_sub.c.mission_id)
        .where(Mission.created_at >= since)
    )

    if status:
        q = q.where(Mission.status == MissionStatus(status))
    if company_id:
        q = q.where(Mission.company_id == company_id)
    if mission_type:
        q = q.where(Mission.mission_type == mission_type)

    q = q.order_by(Mission.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)

    return [
        AdminMissionRow(
            id=m.id,
            company_id=m.company_id,
            company_name=cname,
            mission_type=m.mission_type,
            agent_type=m.agent_type,
            status=m.status,
            quality_score=m.quality_score,
            token_cost_usd=round(cost, 4),
            error_message=m.error_message,
            created_at=m.created_at,
            completed_at=m.completed_at,
        )
        for m, cname, cost in result.all()
    ]


@router.get("/token-spend", response_model=list[AdminTokenSpendRow])
async def admin_token_spend(days: int = 30, db: DbSession = None):
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            cast(TokenUsage.created_at, Date).label("day"),
            TokenUsage.provider,
            TokenUsage.model,
            func.sum(TokenUsage.total_tokens),
            func.sum(TokenUsage.estimated_cost_usd),
            func.count(TokenUsage.id),
        )
        .where(TokenUsage.created_at >= since)
        .group_by("day", TokenUsage.provider, TokenUsage.model)
        .order_by("day")
    )

    return [
        AdminTokenSpendRow(
            date=str(day),
            provider=prov,
            model=model,
            total_tokens=tokens,
            total_cost_usd=round(cost, 4),
            call_count=count,
        )
        for day, prov, model, tokens, cost, count in result.all()
    ]


@router.get("/errors", response_model=list[AdminErrorRow])
async def admin_errors(days: int = 7, limit: int = 50, db: DbSession = None):
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(Mission, Company.name)
        .join(Company, Mission.company_id == Company.id)
        .where(
            Mission.status == MissionStatus.FAILED,
            Mission.created_at >= since,
        )
        .order_by(Mission.created_at.desc())
        .limit(limit)
    )

    return [
        AdminErrorRow(
            id=m.id,
            company_id=m.company_id,
            company_name=cname,
            mission_type=m.mission_type,
            error_message=m.error_message,
            created_at=m.created_at,
        )
        for m, cname in result.all()
    ]


@router.get("/tool-usage", response_model=list[AdminToolUsageRow])
async def admin_tool_usage(days: int = 30, db: DbSession = None):
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            ToolCallLog.tool_name,
            func.count(ToolCallLog.id),
            func.sum(case((ToolCallLog.status == "error", 1), else_=0)),
            func.avg(ToolCallLog.duration_ms),
        )
        .where(ToolCallLog.created_at >= since)
        .group_by(ToolCallLog.tool_name)
        .order_by(func.count(ToolCallLog.id).desc())
    )

    return [
        AdminToolUsageRow(
            tool_name=name,
            total_calls=total,
            error_count=errors,
            error_rate=round(errors / total, 4) if total else 0.0,
            avg_duration_ms=round(avg_ms, 1) if avg_ms else 0.0,
        )
        for name, total, errors, avg_ms in result.all()
    ]


@router.get("/beta-feedback", response_model=list[BetaFeedbackOut])
async def admin_beta_feedback(limit: int = 100, db: DbSession = None):
    result = await db.execute(
        select(BetaFeedback)
        .order_by(BetaFeedback.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get("/beta-feedback/summary")
async def admin_beta_feedback_summary(db: DbSession = None):
    total = (await db.execute(select(func.count(BetaFeedback.id)))).scalar() or 0
    used = (
        await db.execute(
            select(func.count(BetaFeedback.id)).where(BetaFeedback.used_deliverable == True)
        )
    ).scalar() or 0
    avg_rating = (
        await db.execute(select(func.avg(BetaFeedback.rating)))
    ).scalar()
    return {
        "total_responses": total,
        "used_deliverable_count": used,
        "used_deliverable_rate": round(used / total, 2) if total else 0.0,
        "avg_rating": round(float(avg_rating), 2) if avg_rating else None,
    }
