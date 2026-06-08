"""Celery application for background mission execution.

Replaces the fire-and-forget asyncio.create_task() pattern with a proper
task queue backed by Redis.  Each mission runs in a Celery worker process,
isolated from the FastAPI server.
"""
from __future__ import annotations

import asyncio

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "rpg_agent",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,  # 30 min hard limit (Polsia complexity=5 cap)
    task_soft_time_limit=1500,  # 25 min soft limit for graceful shutdown
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_concurrency=2,
    beat_schedule={
        "check-recurring-missions": {
            "task": "app.workers.celery_app.check_recurring_missions",
            "schedule": 3600.0,  # every hour
        },
        "monitor-ads-campaigns": {
            "task": "app.workers.celery_app.monitor_ads_campaigns",
            "schedule": 14400.0,  # every 4 hours
        },
    },
)

celery_app.conf.task_routes = {
    "app.workers.celery_app.run_mission_task": {"queue": "missions"},
    "app.workers.celery_app.check_recurring_missions": {"queue": "missions"},
}


def _run_async(coro):
    """Run an async coroutine in a new event loop (Celery workers are sync)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    name="app.workers.celery_app.run_mission_task",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
)
def run_mission_task(self, mission_id: str) -> dict:
    """Execute a mission in a Celery worker."""
    from app.workers.runner import _run_mission

    _run_async(_run_mission(mission_id))

    return {"mission_id": mission_id, "status": "completed"}


@celery_app.task(name="app.workers.celery_app.check_recurring_missions")
def check_recurring_missions() -> dict:
    """Check for recurring missions due to run and dispatch them."""
    return _run_async(_check_recurring_missions_async())


async def _check_recurring_missions_async() -> dict:
    """Query RecurringMission entries that are due and launch missions."""
    import structlog
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.entities import RecurringMission
    from app.services.mission import MissionService

    logger = structlog.get_logger()
    now = datetime.now(timezone.utc)
    launched = 0

    async with SessionLocal() as db:
        result = await db.execute(
            select(RecurringMission).where(
                RecurringMission.is_active == True,  # noqa: E712
                RecurringMission.next_run_at <= now,
            )
        )
        due_missions = list(result.scalars().all())

        for rm in due_missions:
            try:
                svc = MissionService(db)
                mission = await svc.start_mission(rm.company_id, rm.mission_type)

                rm.last_run_at = now
                rm.next_run_at = _compute_next_run(rm, now)
                await db.commit()

                from app.workers.runner import schedule_mission_run
                schedule_mission_run(mission.id)
                launched += 1

                logger.info(
                    "recurring_mission_launched",
                    company_id=rm.company_id,
                    mission_type=rm.mission_type,
                    next_run_at=rm.next_run_at.isoformat() if rm.next_run_at else None,
                )
            except Exception as exc:
                logger.warning(
                    "recurring_mission_failed",
                    company_id=rm.company_id,
                    mission_type=rm.mission_type,
                    error=str(exc),
                )
                continue

    return {"checked": len(due_missions), "launched": launched}


def _compute_next_run(rm, now) -> "datetime":
    """Compute the next run time based on frequency."""
    from datetime import timedelta

    if rm.frequency == "daily":
        return now + timedelta(days=1)
    elif rm.frequency == "weekly":
        return now + timedelta(weeks=1)
    elif rm.frequency == "monthly":
        return now + timedelta(days=28)
    return now + timedelta(days=1)


@celery_app.task(name="app.workers.celery_app.monitor_ads_campaigns")
def monitor_ads_campaigns() -> dict:
    """Monitor Meta Ads performance for all companies with active campaigns."""
    return _run_async(_monitor_ads_async())


async def _monitor_ads_async() -> dict:
    import structlog
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.entities import AdCampaign, Company
    from app.services.ads import monitor_campaigns

    logger = structlog.get_logger()
    monitored = 0

    async with SessionLocal() as db:
        result = await db.execute(
            select(Company.id).join(AdCampaign).distinct()
        )
        company_ids = [row[0] for row in result.all()]

        for cid in company_ids:
            try:
                await monitor_campaigns(db, cid)
                monitored += 1
            except Exception as exc:
                logger.warning("ads_monitor_company_failed", company_id=cid, error=str(exc))

    return {"monitored": monitored}
