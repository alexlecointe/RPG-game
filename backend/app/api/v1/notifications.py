from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.entities import Company, CompanyNotification
from app.services.orchestrator import OrchestratorService

router = APIRouter()


class NotificationOut(BaseModel):
    id: str
    type: str
    title: str
    message: str
    read: bool
    created_at: str

    class Config:
        from_attributes = True


class AutoPilotToggle(BaseModel):
    enabled: bool


class AutoPilotOut(BaseModel):
    auto_pilot: bool


class LaunchResult(BaseModel):
    launched: int
    steps: list[str]


@router.get("/companies/{company_id}/notifications", response_model=list[NotificationOut])
async def list_notifications(
    company_id: str,
    limit: int = 20,
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(CompanyNotification)
        .where(CompanyNotification.company_id == company_id)
        .order_by(CompanyNotification.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        query = query.where(CompanyNotification.read == False)  # noqa: E712

    result = await db.execute(query)
    notifs = result.scalars().all()
    return [
        NotificationOut(
            id=n.id,
            type=n.type.value,
            title=n.title,
            message=n.message,
            read=n.read,
            created_at=n.created_at.isoformat(),
        )
        for n in notifs
    ]


@router.post("/companies/{company_id}/notifications/read-all")
async def mark_all_read(
    company_id: str,
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(CompanyNotification)
        .where(
            CompanyNotification.company_id == company_id,
            CompanyNotification.read == False,  # noqa: E712
        )
        .values(read=True)
    )
    await db.commit()
    return {"status": "ok"}


@router.post("/companies/{company_id}/auto-pilot", response_model=AutoPilotOut)
async def toggle_auto_pilot(
    company_id: str,
    body: AutoPilotToggle,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="company_not_found")

    company.auto_pilot = body.enabled
    await db.commit()
    await db.refresh(company)

    if body.enabled:
        orch = OrchestratorService(db)
        await orch.auto_start_available_steps(company_id)

    return AutoPilotOut(auto_pilot=company.auto_pilot)


@router.post("/companies/{company_id}/launch-all", response_model=LaunchResult)
async def launch_all_available(
    company_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger auto-launch of all available quest steps."""
    orch = OrchestratorService(db)
    launched = await orch.auto_start_available_steps(company_id)
    return LaunchResult(
        launched=len(launched),
        steps=[s.title for s in launched],
    )
