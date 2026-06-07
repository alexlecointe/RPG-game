from __future__ import annotations

import asyncio

import structlog

from app.agents.scorer import QUALITY_THRESHOLD, MAX_QUALITY_RETRIES, score_deliverable
from app.core.database import SessionLocal
from app.models.entities import Mission, MissionLog, MissionStatus, NotificationType, TokenUsage

logger = structlog.get_logger()


def schedule_mission_run(mission_id: str) -> None:
    """Dispatch mission to Celery queue, with asyncio fallback for dev."""
    from app.core.config import get_settings

    settings = get_settings()

    if settings.redis_url and settings.app_env != "development":
        try:
            from app.workers.celery_app import run_mission_task
            run_mission_task.delay(mission_id)
            logger.info("mission_queued_celery", mission_id=mission_id)
            return
        except Exception as exc:
            logger.warning("celery_dispatch_failed", error=str(exc))

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run_mission(mission_id))
        logger.info("mission_queued_asyncio", mission_id=mission_id)
    except RuntimeError:
        asyncio.run(_run_mission(mission_id))


async def _acquire_mission_lock(mission_id: str) -> bool:
    """Try to acquire a distributed lock for this mission via Redis.

    Returns True if lock acquired, False if mission is already running.
    Falls back to True (proceed) if Redis is unavailable.
    """
    from app.core.config import get_settings
    settings = get_settings()

    if not settings.redis_url or settings.app_env == "development":
        return True

    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        lock_key = f"mission:{mission_id}:lock"
        acquired = await r.set(lock_key, "1", nx=True, ex=1800)  # TTL 30 min
        await r.aclose()
        return bool(acquired)
    except Exception as exc:
        logger.warning("mission_lock_failed", mission_id=mission_id, error=str(exc))
        return True


async def _release_mission_lock(mission_id: str) -> None:
    """Release the distributed lock for this mission."""
    from app.core.config import get_settings
    settings = get_settings()

    if not settings.redis_url or settings.app_env == "development":
        return

    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        await r.delete(f"mission:{mission_id}:lock")
        await r.aclose()
    except Exception:
        pass


async def _run_mission(mission_id: str) -> None:
    from datetime import datetime, timezone

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.agents.executor import execute_agent
    from app.models.entities import Company
    from app.services.mission import MissionService

    if not await _acquire_mission_lock(mission_id):
        logger.info("mission_already_locked", mission_id=mission_id)
        return

    logger.info("mission_run_started", mission_id=mission_id)
    await asyncio.sleep(2)

    try:
        await _run_mission_inner(mission_id)
    finally:
        await _release_mission_lock(mission_id)


async def _run_mission_inner(mission_id: str) -> None:
    from datetime import datetime, timezone

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.agents.executor import execute_agent
    from app.models.entities import Company
    from app.services.mission import MissionService

    async with SessionLocal() as db:
        result = await db.execute(
            select(Mission).where(Mission.id == mission_id).options(selectinload(Mission.logs))
        )
        mission = result.scalar_one_or_none()
        if not mission:
            return

        mission.status = MissionStatus.RUNNING
        mission.started_at = datetime.now(timezone.utc)
        db.add(MissionLog(mission_id=mission_id, step="agent_started", message="Agent en route..."))
        await db.commit()

        company_result = await db.execute(select(Company).where(Company.id == mission.company_id))
        company = company_result.scalar_one_or_none()
        if not company:
            svc = MissionService(db)
            await svc.fail_mission(mission, "company_not_found")
            return

        async def log_step(step: str, message: str):
            async with SessionLocal() as log_db:
                log_db.add(MissionLog(mission_id=mission_id, step=step, message=message))
                await log_db.commit()

        from app.services.quest_chain import QuestChainService

        chain_context = None
        chain_svc = QuestChainService(db)
        quest_step = await chain_svc.find_step_for_mission(
            mission.company_id, mission.mission_type
        )
        if quest_step:
            chain_context = await chain_svc.get_prerequisite_deliverables(
                mission.company_id, quest_step.step_number,
                business_type=company.business_type,
            )
            if chain_context and log_step:
                await log_step(
                    "context_loaded",
                    f"Contexte charge : {len(chain_context)} etape(s) precedente(s)",
                )

        from app.agents.mission_catalog import MISSION_CATALOG
        from app.services.memory import MemoryService

        memory_svc = MemoryService(db)
        _catalog = MISSION_CATALOG.get(mission.mission_type)
        _context_budget = _catalog.max_context_tokens if _catalog else 4000
        memory_context = await memory_svc.build_agent_context(
            company.id, mission.mission_type,
            industry=company.business_type.value,
            max_tokens=_context_budget,
        )
        if memory_context and log_step:
            await log_step(
                "memory_loaded",
                f"Memoire chargee : {len(memory_context)} entree(s)",
            )

        try:
            quality_retry = 0
            feedback_addendum = ""
            best_result = None
            best_score = 0

            while quality_retry <= MAX_QUALITY_RETRIES:
                agent_result = await execute_agent(
                    mission.agent_type,
                    mission.mission_type,
                    company.name,
                    company.mission_statement,
                    product_description=company.product_description,
                    target_audience=company.target_audience,
                    log_callback=log_step,
                    chain_context=chain_context,
                    business_type=company.business_type.value,
                    memory_context=memory_context,
                    quality_feedback=feedback_addendum or None,
                    company_id=company.id,
                    company_slug=company.slug or "default",
                )
                if agent_result.tool_calls and log_step:
                    for tc in agent_result.tool_calls:
                        await log_step(
                            "tool_used",
                            f"Outil {tc['tool']} utilise — {tc.get('result', '')[:100]}",
                        )

                score, feedback = await score_deliverable(
                    mission.mission_type,
                    company.mission_statement,
                    agent_result.content,
                    company.business_type.value,
                )

                if log_step:
                    await log_step(
                        "quality_check",
                        f"Score qualite : {score}/10"
                        + (f" (tentative {quality_retry + 1})" if quality_retry else ""),
                    )

                if score > best_score:
                    best_score = score
                    best_result = agent_result

                if score >= QUALITY_THRESHOLD:
                    break

                quality_retry += 1
                if quality_retry <= MAX_QUALITY_RETRIES:
                    feedback_addendum = (
                        f"FEEDBACK PRECEDENT (score {score}/10):\n{feedback}\n"
                        "Ameliore le livrable en tenant compte de ce feedback."
                    )
                    if log_step:
                        await log_step(
                            "quality_retry",
                            f"Score {score}/10 insuffisant — relance {quality_retry}/{MAX_QUALITY_RETRIES}",
                        )

            agent_result = best_result or agent_result

            for i, ts in enumerate(agent_result.token_stats):
                db.add(TokenUsage(
                    mission_id=mission_id,
                    company_id=company.id,
                    provider=ts.provider,
                    model=ts.model,
                    input_tokens=ts.input_tokens,
                    output_tokens=ts.output_tokens,
                    total_tokens=ts.total_tokens,
                    estimated_cost_usd=ts.estimated_cost_usd,
                    iteration=i,
                ))
            if agent_result.token_stats:
                await db.flush()
                if log_step:
                    total = agent_result.total_tokens
                    cost = agent_result.total_cost_usd
                    await log_step(
                        "token_usage",
                        f"Tokens: {total:,} (${cost:.4f})",
                    )

            svc = MissionService(db)
            await db.refresh(mission)
            mission = await svc.get_mission(mission_id) or mission
            mission.quality_score = best_score
            mission.quality_feedback = feedback
            await svc.complete_mission(mission, agent_result.format, agent_result.content)

            if best_score < QUALITY_THRESHOLD:
                from app.services.orchestrator import OrchestratorService as _Orch

                _orch = _Orch(db)
                await _orch._notify(
                    company.id,
                    NotificationType.STEP_COMPLETED,
                    f"Qualite moyenne ({best_score}/10)",
                    f'Mission "{mission.mission_type}" acceptee avec un score de {best_score}/10 apres {quality_retry} tentatives.',
                )

            await memory_svc.extract_and_store_memory(
                company.id, mission.mission_type, agent_result.content, mission.id,
                industry=company.business_type.value,
            )

            logger.info(
                "mission_run_completed",
                mission_id=mission_id,
                tool_calls=len(agent_result.tool_calls),
                quality_score=best_score,
            )

            from app.services.orchestrator import OrchestratorService

            orch = OrchestratorService(db)
            step_title = quest_step.title if quest_step else ""
            await orch.after_mission_completed(company.id, step_title)

        except Exception as exc:
            logger.exception("mission_run_failed", mission_id=mission_id)
            svc = MissionService(db)
            await db.refresh(mission)
            mission = await svc.get_mission(mission_id) or mission
            await svc.fail_mission(mission, str(exc))

            from app.services.orchestrator import OrchestratorService

            orch = OrchestratorService(db)
            await orch.handle_step_failure(company.id, mission.mission_type)
