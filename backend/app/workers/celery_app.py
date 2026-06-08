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
        "charge-ads-wallets-daily": {
            "task": "app.workers.celery_app.charge_ads_wallets_daily",
            "schedule": 86400.0,  # once per day (~06:00 UTC on first beat tick)
        },
        "expire-god-mode-sessions": {
            "task": "app.workers.celery_app.expire_god_mode_sessions_task",
            "schedule": 300.0,  # every 5 minutes — keeps sessions fresh
        },
        "resume-god-mode-loops": {
            "task": "app.workers.celery_app.resume_god_mode_loops_task",
            "schedule": 600.0,  # every 10 minutes — restart loops if worker restarted
        },
    },
)

celery_app.conf.task_routes = {
    "app.workers.celery_app.run_mission_task": {"queue": "missions"},
    "app.workers.celery_app.check_recurring_missions": {"queue": "missions"},
    "app.workers.celery_app.run_god_mode_step": {"queue": "missions"},
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
                # start_mission already calls schedule_mission_run internally — no double dispatch
                mission = await svc.start_mission(rm.company_id, rm.mission_type)

                # Tag as recurring_task source
                from app.models.entities import TaskSource
                mission.source = TaskSource.RECURRING_TASK

                rm.last_run_at = now
                rm.next_run_at = _compute_next_run(rm, now)
                await db.commit()

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
    """Compute the next run time based on frequency, honoring hour_utc / day_of_week / day_of_month."""
    from datetime import timedelta

    hour = rm.hour_utc if rm.hour_utc is not None else 9

    if rm.frequency == "daily":
        candidate = now + timedelta(days=1)
        return candidate.replace(hour=hour, minute=0, second=0, microsecond=0)

    elif rm.frequency == "weekly":
        target_weekday = rm.day_of_week if rm.day_of_week is not None else now.weekday()
        # Advance at least 1 day, then land on the right weekday
        candidate = now + timedelta(days=1)
        while candidate.weekday() != target_weekday:
            candidate += timedelta(days=1)
        return candidate.replace(hour=hour, minute=0, second=0, microsecond=0)

    elif rm.frequency == "monthly":
        target_day = rm.day_of_month if rm.day_of_month is not None else now.day
        # Move to next month, snap to target day (capped at 28 for safety)
        if now.month == 12:
            next_month, next_year = 1, now.year + 1
        else:
            next_month, next_year = now.month + 1, now.year
        import calendar
        max_day = calendar.monthrange(next_year, next_month)[1]
        day = min(target_day, max_day)
        return now.replace(year=next_year, month=next_month, day=day, hour=hour, minute=0, second=0, microsecond=0)

    # Fallback: daily
    candidate = now + timedelta(days=1)
    return candidate.replace(hour=hour, minute=0, second=0, microsecond=0)


@celery_app.task(name="app.workers.celery_app.monitor_ads_campaigns")
def monitor_ads_campaigns() -> dict:
    """Monitor Meta Ads performance for all companies with active campaigns."""
    return _run_async(_monitor_ads_async())


@celery_app.task(name="app.workers.celery_app.charge_ads_wallets_daily")
def charge_ads_wallets_daily() -> dict:
    """Charge daily ads budgets via Stripe for all companies with active campaigns."""
    return _run_async(_charge_ads_wallets_async())


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


@celery_app.task(name="app.workers.celery_app.expire_god_mode_sessions_task")
def expire_god_mode_sessions_task() -> dict:
    """Mark expired God Mode sessions (status=active but expires_at past)."""
    return _run_async(_expire_god_mode_async())


@celery_app.task(
    name="app.workers.celery_app.run_god_mode_step",
    bind=True,
    max_retries=0,
)
def run_god_mode_step(self, company_id: str, god_session_id: str, step_index: int) -> dict:
    """Run one God Mode step (1 mission) then re-enqueue next step if session still active."""
    return _run_async(_god_mode_step_async(company_id, god_session_id, step_index))


@celery_app.task(name="app.workers.celery_app.resume_god_mode_loops_task")
def resume_god_mode_loops_task() -> dict:
    """On worker restart, re-enqueue God Mode steps for all active sessions without a running loop."""
    return _run_async(_resume_god_mode_loops_async())


async def _expire_god_mode_async() -> dict:
    from app.core.database import SessionLocal
    from app.services.billing import expire_god_mode_sessions
    async with SessionLocal() as db:
        expired = await expire_god_mode_sessions(db)
    return {"expired": expired}


_GOD_MODE_SEQUENCE = [
    "landing_page",
    "ad_copy_pack",
    "payment_setup",
    "market_research",
    "ad_creation",
]
_GOD_MODE_STEP_DELAY_SECONDS = 720  # 12 min between steps


async def _god_mode_step_async(company_id: str, god_session_id: str, step_index: int) -> dict:
    """Execute one autonomous mission step, then schedule the next if still active."""
    import structlog as _sl
    from datetime import datetime, timezone
    from app.core.database import SessionLocal
    from app.models.entities import GodModeSession
    from app.services.mission import MissionService

    logger = _sl.get_logger()

    async with SessionLocal() as db:
        session = await db.get(GodModeSession, god_session_id)
        if not session:
            return {"skipped": True, "reason": "session_missing"}

        now = datetime.now(timezone.utc)
        if session.status != "active" or (session.expires_at and session.expires_at <= now):
            if session.status == "active":
                session.status = "expired"
                await db.commit()
            return {"skipped": True, "reason": "session_expired"}

        mission_type = _GOD_MODE_SEQUENCE[step_index % len(_GOD_MODE_SEQUENCE)]
        try:
            svc = MissionService(db)
            mission = await svc.start_mission(company_id, mission_type)
            await db.commit()
            logger.info(
                "god_mode_celery_step",
                company_id=company_id,
                mission_id=mission.id,
                step=step_index,
                mission_type=mission_type,
            )
        except Exception as exc:
            logger.warning("god_mode_step_failed", error=str(exc), step=step_index)

        # Schedule next step (Celery countdown)
        remaining = (session.expires_at - now).total_seconds() if session.expires_at else 0
        if remaining > _GOD_MODE_STEP_DELAY_SECONDS + 60:
            run_god_mode_step.apply_async(
                args=[company_id, god_session_id, step_index + 1],
                countdown=_GOD_MODE_STEP_DELAY_SECONDS,
            )

    return {"step": step_index, "mission_type": mission_type}


async def _resume_god_mode_loops_async() -> dict:
    """Find active God Mode sessions with no recent Celery task and re-enqueue them."""
    import structlog as _sl
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.core.database import SessionLocal
    from app.models.entities import GodModeSession

    logger = _sl.get_logger()
    resumed = 0

    async with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(GodModeSession).where(
                GodModeSession.status == "active",
                GodModeSession.expires_at > now,
            )
        )
        sessions = result.scalars().all()

        for s in sessions:
            # Use Redis to check if a loop is already running for this session
            try:
                import redis.asyncio as aioredis
                from app.core.config import get_settings
                settings = get_settings()
                r = aioredis.from_url(settings.redis_url)
                key = f"god_mode:loop:{s.id}"
                already = await r.get(key)
                if already:
                    await r.aclose()
                    continue
                # Mark as running for 15 min (one step duration + buffer)
                await r.set(key, "1", ex=900)
                await r.aclose()
            except Exception:
                pass  # No Redis → always try to resume

            run_god_mode_step.apply_async(args=[s.company_id, s.id, 0], countdown=5)
            resumed += 1
            logger.info("god_mode_loop_resumed", company_id=s.company_id, session_id=s.id)

    return {"resumed": resumed}


async def _charge_ads_wallets_async() -> dict:
    import structlog
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.entities import AdCampaign, AdCampaignStatus, Company
    from app.services.billing import charge_ads_wallet_stripe

    logger = structlog.get_logger()
    charged = 0
    skipped = 0

    async with SessionLocal() as db:
        # Find companies with active ad campaigns and a daily budget set
        result = await db.execute(
            select(Company)
            .join(AdCampaign, AdCampaign.company_id == Company.id)
            .where(
                AdCampaign.status == AdCampaignStatus.ACTIVE,
                Company.daily_ads_budget_cents > 0,
            )
            .distinct()
        )
        companies = list(result.scalars().all())

        for company in companies:
            try:
                res = await charge_ads_wallet_stripe(db, company)
                if res.get("skipped"):
                    skipped += 1
                else:
                    charged += 1
                    logger.info(
                        "ads_daily_charge_done",
                        company_id=company.id,
                        charged_cents=res.get("charged_cents"),
                    )
            except Exception as exc:
                logger.warning("ads_daily_charge_error", company_id=company.id, error=str(exc))
                skipped += 1

    return {"charged": charged, "skipped": skipped}
