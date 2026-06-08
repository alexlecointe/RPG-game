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

        # Debit 1 credit at execution start (Polsia model — never at creation)
        # Skip debit entirely if company has an active God Mode session
        if mission.credits_cost > 0:
            from app.services.billing import (
                debit_credit,
                get_active_god_mode_session,
                get_or_create_subscription,
            )
            from app.services.company import CompanyService
            company_svc = CompanyService(db)
            company_for_billing = await company_svc.get_company(mission.company_id)
            if company_for_billing:
                god_session = await get_active_god_mode_session(db, mission.company_id)
                if god_session:
                    db.add(MissionLog(
                        mission_id=mission_id,
                        step="god_mode_bypass",
                        message=f"God Mode actif — crédit non débité (expire {god_session.expires_at.strftime('%d/%m %Hh')})",
                    ))
                else:
                    sub = await get_or_create_subscription(db, company_for_billing)
                    try:
                        await debit_credit(db, sub)
                        db.add(MissionLog(
                            mission_id=mission_id,
                            step="credit_debited",
                            message="1 crédit débité au démarrage (Polsia)",
                        ))
                    except ValueError:
                        db.add(MissionLog(
                            mission_id=mission_id,
                            step="no_credits",
                            message="Exécution annulée : plus de crédits",
                        ))
                        mission.status = MissionStatus.FAILED
                        mission.error_message = "no_credits"
                        mission.completed_at = datetime.now(timezone.utc)
                        await db.commit()
                        logger.warning("mission_no_credits", mission_id=mission_id)
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
                    competitor_url=company.competitor_url or "",
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

            deliverable_content = agent_result.content
            deliverable_format = agent_result.format

            if mission.mission_type == "landing_page" and agent_result.content:
                from app.services.site_deploy import build_site_url, deploy_landing_html
                import json as _json

                # Skip runner-side deploy if the agent already called deploy_site successfully
                agent_already_deployed = any(
                    tc.get("tool") == "deploy_site"
                    and _json.loads(tc.get("result", "{}") or "{}").get("deployed")
                    for tc in (agent_result.tool_calls or [])
                )

                if agent_already_deployed:
                    site_url = build_site_url(company.slug or "", company.render_url)
                    if log_step:
                        await log_step("site_deployed", f"Site deploye par l'agent : {site_url or 'en cours'}")
                else:
                    deploy_result = await deploy_landing_html(
                        company.slug or company.name,
                        agent_result.content,
                        company.slug or "site",
                        company.render_service_id,
                    )
                    site_url = deploy_result.get("site_url") or build_site_url(
                        company.slug or "", company.render_url
                    )
                    if log_step:
                        await log_step("site_deployed", f"Site deploye : {site_url or 'en cours'}")

                if site_url:
                    deliverable_content = (
                        f"{agent_result.content}\n\n---\n\n"
                        f"**Site live :** {site_url}\n"
                    )

            if mission.mission_type == "ads_launch_plan":
                # The LLM calls meta_ads_action directly to create campaigns.
                # We parse the deliverable to extract Meta campaign IDs and persist them in DB.
                await _persist_ads_from_deliverable(db, company, deliverable_content, log_step)

            svc = MissionService(db)
            await db.refresh(mission)
            mission = await svc.get_mission(mission_id) or mission
            mission.quality_score = best_score
            mission.quality_feedback = feedback
            await svc.complete_mission(mission, deliverable_format, deliverable_content)

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

            # Polsia retry loop: CEO proposes a new retry task after failure
            await _propose_retry_task(db, mission, company, str(exc))


async def _propose_retry_task(db, mission, company, error: str) -> None:
    """Polsia retry loop: after task failure, CEO auto-creates a new ceo_proposal retry task.

    The retry task sits in queue (no auto-execute) — user must manually trigger it.
    Only creates a retry if: not already a retry (avoid infinite loops) and not no_credits.
    """
    if error == "no_credits":
        return  # No point retrying without credits

    # Avoid cascading retries: don't retry a retry more than twice
    from sqlalchemy import select as _select
    from app.models.entities import Mission as _Mission, MissionStatus as _MS, TaskSource as _TS

    # Dedup: if a retry for this agent_type is already pending in queue, skip
    pending_result = await db.execute(
        _select(_Mission).where(
            _Mission.company_id == mission.company_id,
            _Mission.agent_type == mission.agent_type,
            _Mission.source == _TS.CEO_PROPOSAL,
            _Mission.status == _MS.PENDING,
        )
    )
    if list(pending_result.scalars().all()):
        logger.info(
            "retry_already_pending_skipping",
            mission_id=mission.id,
            mission_type=mission.mission_type,
        )
        return

    retry_count_result = await db.execute(
        _select(_Mission).where(
            _Mission.company_id == mission.company_id,
            _Mission.agent_type == mission.agent_type,
            _Mission.source == _TS.CEO_PROPOSAL,
            _Mission.status == _MS.FAILED,
        )
    )
    previous_retries = list(retry_count_result.scalars().all())
    if len(previous_retries) >= 2:
        # Too many retries for same agent type — don't add more
        logger.info(
            "retry_limit_reached",
            mission_id=mission.id,
            mission_type=mission.mission_type,
            retries=len(previous_retries),
        )
        return

    try:
        from app.services.mission import MissionService
        from app.services.task_router import find_best_agent

        svc = MissionService(db)

        display_title = mission.title or mission.mission_type.replace("_", " ").title()
        retry_number = len(previous_retries) + 1
        retry_title = f"Retry #{retry_number} — {display_title}"
        retry_description = (
            f"Relance de la tâche '{display_title}' après échec.\n"
            f"Erreur précédente : {error[:200]}\n"
            f"Approche différente recommandée."
        )

        await svc.create_freeform_task(
            company_id=mission.company_id,
            title=retry_title,
            description=retry_description,
            agent_type_str=mission.agent_type.value,
            source=_TS.CEO_PROPOSAL,
            auto_schedule=False,
        )

        logger.info(
            "retry_task_created",
            original_mission_id=mission.id,
            mission_type=mission.mission_type,
            retry_number=retry_number,
        )
    except ValueError:
        # no_credits during retry creation — skip silently
        pass
    except Exception as exc:
        logger.warning("retry_task_creation_failed", error=str(exc))


async def _persist_ads_from_deliverable(db, company, deliverable_content: str, log_step) -> None:
    """Parse deliverable for Meta campaign IDs created by LLM and persist to DB."""
    import re

    from app.models.entities import AdCampaign, AdCampaignStatus

    # Look for campaign_id patterns in the deliverable JSON
    campaign_ids = re.findall(r'"campaign_id"\s*:\s*"(\d+)"', deliverable_content or "")
    if not campaign_ids:
        # Try alternate formats: "id": "12345..."
        campaign_ids = re.findall(r'(?:meta_campaign_id|campaign_id)["\s:]+(\d{10,})', deliverable_content or "")

    if campaign_ids:
        for meta_cid in campaign_ids[:3]:
            existing = await db.execute(
                __import__("sqlalchemy", fromlist=["select"]).select(AdCampaign).where(
                    AdCampaign.company_id == company.id,
                    AdCampaign.meta_campaign_id == meta_cid,
                )
            )
            if not existing.scalars().first():
                camp = AdCampaign(
                    company_id=company.id,
                    name=f"{company.name} Ads",
                    meta_campaign_id=meta_cid,
                    daily_budget_cents=company.daily_ads_budget_cents or 1000,
                    status=AdCampaignStatus.ACTIVE,
                )
                db.add(camp)
        await db.commit()
        if log_step:
            await log_step("ads_persisted", f"{len(campaign_ids)} campagne(s) Meta enregistree(s)")


# ---------------------------------------------------------------------------
# God Mode autonomous loop — runs while GodModeSession is active
# ---------------------------------------------------------------------------

# Sequence of missions the God Mode loop chains automatically (Builder → Marketer → Finance)
_GOD_MODE_SEQUENCE = [
    "landing_page",
    "ad_copy_pack",
    "payment_setup",
    "market_research",
    "ad_creation",
]

# Interval between automatic mission launches (minutes)
_GOD_MODE_INTERVAL_MINUTES = 12


def schedule_god_mode_loop(company_id: str, god_session_id: str) -> None:
    """Start the God Mode autonomous loop. Uses Celery if available, asyncio otherwise."""
    from app.core.config import get_settings
    settings = get_settings()

    if settings.redis_url and settings.app_env != "development":
        try:
            from app.workers.celery_app import run_god_mode_step
            run_god_mode_step.apply_async(args=[company_id, god_session_id, 0], countdown=30)
            logger.info("god_mode_loop_queued_celery", company_id=company_id, session_id=god_session_id)
            return
        except Exception as exc:
            logger.warning("god_mode_celery_dispatch_failed", error=str(exc))

    # Dev fallback: asyncio task
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_god_mode_loop(company_id, god_session_id))
        logger.info("god_mode_loop_started_asyncio", company_id=company_id, session_id=god_session_id)
    except RuntimeError:
        asyncio.run(_god_mode_loop(company_id, god_session_id))


async def _god_mode_loop(company_id: str, god_session_id: str) -> None:
    """Continuously launch missions until the God Mode session expires."""
    from datetime import datetime, timezone

    from sqlalchemy import select as _select

    from app.models.entities import Company, GodModeSession
    from app.services.mission import MissionService

    logger.info("god_mode_loop_begin", company_id=company_id)
    step_index = 0

    while True:
        # Check session still active
        async with SessionLocal() as db:
            result = await db.execute(
                _select(GodModeSession).where(GodModeSession.id == god_session_id)
            )
            session = result.scalar_one_or_none()

        if not session:
            logger.warning("god_mode_session_missing", session_id=god_session_id)
            return

        now = datetime.now(timezone.utc)
        if session.status != "active" or (session.expires_at and session.expires_at <= now):
            async with SessionLocal() as db:
                s2 = await db.get(GodModeSession, god_session_id)
                if s2 and s2.status == "active":
                    s2.status = "expired"
                    await db.commit()
            logger.info("god_mode_loop_ended", company_id=company_id, reason="expired")
            return

        # Pick next mission in sequence (cycles through)
        mission_type = _GOD_MODE_SEQUENCE[step_index % len(_GOD_MODE_SEQUENCE)]
        step_index += 1

        try:
            async with SessionLocal() as db:
                svc = MissionService(db)
                mission = await svc.start_mission(
                    company_id=company_id,
                    mission_type=mission_type,
                )
                await db.commit()
                logger.info(
                    "god_mode_mission_launched",
                    company_id=company_id,
                    mission_id=mission.id,
                    mission_type=mission_type,
                )
        except Exception as exc:
            logger.warning(
                "god_mode_mission_failed",
                company_id=company_id,
                mission_type=mission_type,
                error=str(exc),
            )

        # Wait before next mission
        await asyncio.sleep(_GOD_MODE_INTERVAL_MINUTES * 60)
