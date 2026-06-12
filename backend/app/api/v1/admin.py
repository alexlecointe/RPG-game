"""Admin dashboard API — aggregated KPIs across all companies."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import case, cast, Date, func, or_, select

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


def _business_type_value(value: object) -> str:
    if value is None:
        return "unknown"
    return getattr(value, "value", str(value))


@router.post("/infra/provision/{slug}")
async def admin_provision_company(slug: str):
    """Test + run infra provisioning for a company slug. Returns full result."""
    from app.services.infra import InfraService
    infra = InfraService()
    result = await infra.provision_company(slug)
    return result


@router.post("/infra/deploy-landing/{company_id}")
async def admin_deploy_landing(company_id: str, db: DbSession):
    """Re-publish the latest landing_page deliverable via the shared gateway."""
    from sqlalchemy import select as sa_select, text as sa_text
    from app.models.entities import Mission, MissionStatus
    from app.services.company import CompanyService
    from app.services.site_hosting import build_gateway_url, publish_site

    # Bypass RLS for admin queries by setting the tenant context
    await db.execute(sa_text(f"SET LOCAL app.current_company_id = '{company_id}'"))

    result = await db.execute(
        sa_select(Mission)
        .where(
            Mission.company_id == company_id,
            Mission.mission_type == "landing_page",
            Mission.status == MissionStatus.COMPLETED,
        )
        .order_by(Mission.completed_at.desc())
        .limit(1)
    )
    mission = result.scalar_one_or_none()
    if not mission or not mission.deliverable:
        return {"error": "No completed landing_page mission found"}

    svc = CompanyService(db)
    company = await svc.get_company(company_id)
    if not company:
        return {"error": "Company not found"}

    slug = company.slug or ""
    if not slug:
        return {"error": "Company has no slug"}

    artifact = await publish_site(
        db,
        company_id=company_id,
        slug=slug,
        html_content=mission.deliverable,
        mission_id=mission.id,
    )
    await db.commit()

    site_url = build_gateway_url(slug)
    return {"deployed": True, "platform": "gateway", "slug": slug, "site_url": site_url, "version": artifact.version}


@router.post("/sites/repair/{company_id}")
async def admin_repair_site(
    company_id: str,
    clear_product_image: bool = True,
    db: DbSession = None,
):
    """Repair a published site from the latest completed landing_page deliverable."""
    from sqlalchemy import select as sa_select, text as sa_text
    from app.models.entities import Mission, MissionStatus
    from app.services.company import CompanyService
    from app.services.site_hosting import (
        build_gateway_url,
        publish_site,
        replace_image_url_with_product_placeholder,
        sanitize_site_html,
    )

    await db.execute(sa_text(f"SET LOCAL app.current_company_id = '{company_id}'"))

    svc = CompanyService(db)
    company = await svc.get_company(company_id)
    if not company:
        return {"error": "Company not found"}
    slug = company.slug or ""
    if not slug:
        return {"error": "Company has no slug"}

    result = await db.execute(
        sa_select(Mission)
        .where(
            Mission.company_id == company_id,
            Mission.mission_type == "landing_page",
            Mission.status == MissionStatus.COMPLETED,
        )
        .order_by(Mission.completed_at.desc())
        .limit(1)
    )
    mission = result.scalar_one_or_none()
    if not mission or not mission.deliverable:
        return {"error": "No completed landing_page mission found"}

    old_image_url = company.product_image_url or ""
    html = sanitize_site_html(mission.deliverable)
    image_removed = False
    if clear_product_image and old_image_url:
        repaired = replace_image_url_with_product_placeholder(
            html,
            old_image_url,
            company_name=company.name,
            product_description=company.product_description or company.mission_statement or "",
        )
        image_removed = repaired != html
        html = repaired
        company.product_image_url = None

    artifact = await publish_site(
        db,
        company_id=company_id,
        slug=slug,
        html_content=html,
        mission_id=mission.id,
    )
    await db.commit()

    site_url = build_gateway_url(slug)
    return {
        "repaired": True,
        "slug": slug,
        "site_url": site_url,
        "version": artifact.version,
        "image_removed": image_removed,
    }


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
            slug=c.slug,
            business_type=_business_type_value(c.business_type),
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


@router.get("/companies/search")
async def admin_companies_search(query: str, limit: int = 20, db: DbSession = None):
    term = query.strip()
    if not term:
        return {"companies": [], "count": 0}

    result = await db.execute(
        select(Company)
        .where(
            or_(
                Company.name.ilike(f"%{term}%"),
                Company.slug.ilike(f"%{term}%"),
            )
        )
        .order_by(Company.created_at.desc())
        .limit(limit)
    )
    companies = result.scalars().all()
    return {
        "companies": [
            {
                "id": c.id,
                "name": c.name,
                "slug": c.slug,
                "business_type": _business_type_value(c.business_type),
                "created_at": c.created_at.isoformat(),
            }
            for c in companies
        ],
        "count": len(companies),
    }


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
