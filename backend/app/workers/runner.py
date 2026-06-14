from __future__ import annotations

import asyncio

import structlog

from app.agents.scorer import QUALITY_THRESHOLD, MAX_QUALITY_RETRIES, score_deliverable
from app.agents.base import AgentResult
from app.core.database import SessionLocal
from app.models.entities import Mission, MissionLog, MissionStatus, NotificationType, TokenUsage

logger = structlog.get_logger()

WEBSITE_MISSION_TYPES = {"landing_page", "landing_page_revision"}


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
            logger.error("mission_not_found_for_worker", mission_id=mission_id)
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

            # For website missions: infra check, strategy, product image, revision context.
            website_profile = ""
            website_brief = ""
            website_strategy = ""
            product_image_url = ""
            existing_site_html = ""
            revision_request = ""
            if mission.mission_type in WEBSITE_MISSION_TYPES:
                # --- 1. Vérifier que l'infra est prête (uniquement si provisioning dédié) ---
                if company.infra_status not in ("gateway", "provisioned"):
                    if log_step:
                        await log_step("infra_check", "Vérification infra (GitHub + Render)...")
                    infra_ready = await _wait_for_infra(company, log_step)
                    if not infra_ready and log_step:
                        await log_step(
                            "infra_warning",
                            "Infra non prête — déploiement via gateway partagé",
                        )

                previous_site_spec = ""
                previous_company_profile = ""
                if mission.mission_type == "landing_page_revision":
                    from app.models.entities import SiteArtifact as _SiteArtifact

                    latest_site_result = await db.execute(
                        select(_SiteArtifact)
                        .where(_SiteArtifact.company_id == company.id)
                        .order_by(_SiteArtifact.version.desc())
                        .limit(1)
                    )
                    latest_site = latest_site_result.scalar_one_or_none()
                    if latest_site:
                        existing_site_html = latest_site.html_content or ""
                        previous_site_spec = latest_site.site_spec_json or ""
                        try:
                            import json as _json
                            _prev_spec = _json.loads(previous_site_spec) if previous_site_spec else {}
                            previous_company_profile = _json.dumps(
                                _prev_spec.get("company_profile", {}),
                                ensure_ascii=False,
                            )
                        except Exception:
                            previous_company_profile = ""
                    revision_request = (
                        (mission.description or "").strip()
                        or (mission.title or "").strip()
                        or "Améliore le site en gardant le produit et l'offre."
                    )
                    if log_step:
                        await log_step("revision_context", "Site existant chargé pour révision")

                # --- 2. Company profile + creative brief + site spec ---
                if log_step:
                    await log_step(
                        "website_strategy",
                        "Analyse du business, profil de marque et choix du playbook website...",
                    )
                market_scan_deliverable = ""
                stripe_checkout_url = ""
                if chain_context:
                    import re as _re
                    for ctx in chain_context:
                        if ctx.get("mission_type") == "market_scan":
                            market_scan_deliverable = ctx.get("deliverable", "")[:5000]
                        if ctx.get("mission_type") == "payment_setup":
                            _ps = ctx.get("deliverable", "")
                            _m = _re.search(r"https://buy\.stripe\.com/[^\s\"'>\)]+", _ps)
                            if _m:
                                stripe_checkout_url = _m.group(0)
                from app.services.website_strategy import generate_company_profile, generate_site_spec

                website_profile = await generate_company_profile(
                    company_name=company.name,
                    mission_statement=company.mission_statement,
                    product_description=company.product_description or "",
                    target_audience=company.target_audience or "",
                    business_type=company.business_type.value,
                    market_scan=market_scan_deliverable,
                    revision_request=revision_request,
                    previous_profile_json=previous_company_profile,
                )

                website_strategy = await generate_site_spec(
                    company_name=company.name,
                    mission_statement=company.mission_statement,
                    product_description=company.product_description or "",
                    target_audience=company.target_audience or "",
                    business_type=company.business_type.value,
                    market_scan=market_scan_deliverable,
                    stripe_checkout_url=stripe_checkout_url,
                    revision_request=revision_request,
                    previous_spec_json=previous_site_spec,
                    company_profile_json=website_profile,
                )
                website_brief = await _generate_website_brief(
                    company_name=company.name,
                    mission_statement=company.mission_statement,
                    product_description=company.product_description or "",
                    target_audience=company.target_audience or "",
                    business_type=company.business_type.value,
                    market_scan=market_scan_deliverable,
                    stripe_checkout_url=stripe_checkout_url,
                )

                # --- 6. Stocker le profil et le brief comme memory ---
                if website_profile:
                    from app.services.memory import MemoryService as _MS
                    _mem = _MS(db)
                    await _mem.store(
                        company.id, "brand", "company_profile", website_profile, mission.id
                    )
                    if log_step:
                        await log_step(
                            "website_profile_ready",
                            "Company profile prêt — positionnement, cible, USP et objections",
                        )
                if website_brief:
                    from app.services.memory import MemoryService as _MS
                    _mem = _MS(db)
                    await _mem.store(
                        company.id, "brand", "website_brief", website_brief, mission.id
                    )
                    if log_step:
                        await log_step("website_brief_ready", "Brief créatif prêt — palette, vibe, image produit")
                if website_strategy:
                    from app.services.memory import MemoryService as _MS
                    _mem = _MS(db)
                    await _mem.store(
                        company.id, "brand", "website_strategy", website_strategy, mission.id
                    )
                    if log_step:
                        await log_step(
                            "website_strategy_ready",
                            "Website playbook prêt — structure et direction visuelle",
                        )

                # --- 3. Pré-générer l'image produit ---
                from app.core.config import get_settings as _get_settings
                _settings = _get_settings()
                if mission.mission_type == "landing_page_revision" and company.product_image_url:
                    product_image_url = company.product_image_url
                elif not _settings.replicate_api_token:
                    if log_step:
                        await log_step(
                            "product_image_missing",
                            "⚠️ Image produit non générée — REPLICATE_API_TOKEN absent. "
                            "Le site sera créé sans image produit. Tu pourras en générer une plus tard.",
                        )
                else:
                    if log_step:
                        await log_step("product_image", "Génération de l'image produit...")
                    product_image_url = await _pregenerate_product_image(
                        company.id,
                        website_brief,
                        company.name,
                        log_step,
                        website_strategy,
                        product_description=company.product_description or company.mission_statement,
                        target_audience=company.target_audience or "",
                        business_type=company.business_type.value,
                    )
                    if not product_image_url and log_step:
                        await log_step(
                            "product_image_failed",
                            "⚠️ Génération image produit échouée — site créé sans image. "
                            "Tu pourras en générer une plus tard depuis la fiche Website.",
                        )
                    elif product_image_url:
                        # Persist as CompanyAsset so it appears in Documents
                        await _store_product_image_asset(db, company.id, product_image_url, mission.id)
                        # Save on company for API exposure
                        async with SessionLocal() as _upd:
                            from app.models.entities import Company as _Co
                            _c = await _upd.get(_Co, company.id)
                            if _c:
                                _c.product_image_url = product_image_url
                                await _upd.commit()

            while quality_retry <= MAX_QUALITY_RETRIES:
                try:
                    if mission.mission_type in WEBSITE_MISSION_TYPES:
                        from app.core.config import get_settings as _settings_for_render
                        from app.services.website_project_generator import generate_website_project

                        if log_step:
                            await log_step(
                                "website_engineering",
                                "Agent engineering — génération d'un mini-projet website structuré",
                            )
                        website_project = await generate_website_project(
                            company_name=company.name,
                            mission_statement=company.mission_statement,
                            product_description=company.product_description or "",
                            target_audience=company.target_audience or "",
                            business_type=company.business_type.value,
                            company_profile_json=website_profile,
                            site_spec_json=website_strategy,
                            product_image_url=product_image_url,
                            checkout_url=stripe_checkout_url,
                            meta_pixel_id=_settings_for_render().meta_pixel_id,
                            revision_request=revision_request,
                            existing_site_html=existing_site_html,
                            quality_feedback=feedback_addendum or "",
                        )
                        if log_step:
                            await log_step(
                                "website_project_ready",
                                f"Projet website prêt — {len(website_project.files)} fichiers, moteur {website_project.engine}",
                            )
                        agent_result = AgentResult(
                            format="html",
                            content=website_project.html,
                            metadata=website_project.metadata
                            | {"uses_company_profile": bool(website_profile)},
                            token_stats=website_project.token_stats,
                        )
                    else:
                        agent_result = await asyncio.wait_for(
                            execute_agent(
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
                                website_profile=website_profile,
                                website_brief=website_brief,
                                website_strategy=website_strategy,
                                product_image_url=product_image_url,
                                existing_site_html=existing_site_html,
                                revision_request=revision_request,
                            ),
                            timeout=120 if mission.mission_type == "market_scan" else 900,
                        )
                except asyncio.TimeoutError as exc:
                    if log_step:
                        await log_step(
                            "timeout",
                            "Mission trop longue — arrêt sans livrable template.",
                        )
                    raise RuntimeError("mission_timeout") from exc
                if agent_result.tool_calls and log_step:
                    for tc in agent_result.tool_calls:
                        await log_step(
                            "tool_used",
                            f"Outil {tc['tool']} utilise — {tc.get('result', '')[:100]}",
                        )

                # Landing page vide = l'agent n'a pas généré de HTML → forcer le retry
                if mission.mission_type in WEBSITE_MISSION_TYPES and not (agent_result.content or "").strip():
                    if log_step:
                        await log_step(
                            "html_empty",
                            "⚠️ HTML vide — l'agent n'a pas généré de contenu. Relance forcée.",
                        )
                    feedback_addendum = (
                        "ERREUR CRITIQUE : Tu n'as PAS généré de HTML. "
                        "Tu DOIS générer le HTML complet (<!DOCTYPE html>...jusqu'à</html>) "
                        "dans ta réponse finale. "
                        "Si generate_image échoue, utilise un placeholder CSS — ne t'arrête JAMAIS sans HTML."
                    )
                    quality_retry += 1
                    if quality_retry <= MAX_QUALITY_RETRIES:
                        if log_step:
                            await log_step(
                                "quality_retry",
                                f"HTML vide — relance forcée {quality_retry}/{MAX_QUALITY_RETRIES}",
                            )
                        continue
                    else:
                        break

                # Pre-validation HTML structurelle — alimente le feedback mais ne bypass pas le scorer
                if mission.mission_type in WEBSITE_MISSION_TYPES:
                    html_issues = _validate_landing_html(
                        agent_result.content,
                        product_image_url=product_image_url,
                        business_type=company.business_type.value,
                    )
                    visual_issues = _validate_visual_quality(
                        agent_result.content,
                        website_profile=website_profile,
                        website_strategy=website_strategy,
                        product_image_url=product_image_url,
                        business_type=company.business_type.value,
                    )
                    html_issues.extend(visual_issues)
                    if html_issues:
                        if log_step:
                            await log_step(
                                "html_validation",
                                f"{len(html_issues)} problème(s) structurel(s) détecté(s) dans le HTML",
                            )
                        # Injecter dans le feedback_addendum pour le prochain retry
                        html_feedback = (
                            "PROBLÈMES STRUCTURELS DANS LE HTML (OBLIGATOIRES À CORRIGER):\n"
                            + "\n".join(f"- {issue}" for issue in html_issues)
                        )
                        feedback_addendum = (
                            (feedback_addendum + "\n\n" if feedback_addendum else "")
                            + html_feedback
                        )
                        quality_retry += 1
                        if quality_retry <= MAX_QUALITY_RETRIES:
                            if log_step:
                                await log_step(
                                    "quality_retry",
                                    f"Validation website insuffisante — relance "
                                    f"{quality_retry}/{MAX_QUALITY_RETRIES}",
                                )
                            continue
                        best_result = best_result or agent_result
                        best_score = max(best_score, 1)
                    elif log_step:
                        await log_step("html_validation", "HTML structurel validé")

                score_mission_type = (
                    "landing_page"
                    if mission.mission_type in WEBSITE_MISSION_TYPES
                    else mission.mission_type
                )
                score, feedback = await score_deliverable(
                    score_mission_type,
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

            if not (agent_result.content or "").strip():
                if log_step:
                    await log_step(
                        "empty_deliverable_failed",
                        "Livrable vide après retries — mission arrêtée.",
                    )
                raise RuntimeError("empty_deliverable_after_retries")

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

            if mission.mission_type in WEBSITE_MISSION_TYPES and agent_result.content:
                from sqlalchemy import select as _sa_sel
                from app.models.entities import SiteArtifact as _SA
                from app.services.site_hosting import build_gateway_url, get_live_artifact, publish_site

                slug = company.slug or ""
                if not slug:
                    raise RuntimeError("website_publish_missing_company_slug")

                # If the agent already called deploy_site for this mission, skip republication
                _existing = await db.execute(
                    _sa_sel(_SA)
                    .where(_SA.mission_id == mission.id, _SA.is_live == True)
                    .limit(1)
                )
                _already_published = _existing.scalar_one_or_none()

                if _already_published:
                    artifact = _already_published
                    if log_step:
                        await log_step("site_deployed", f"Site déjà publié par l'agent (v{artifact.version})")
                else:
                    site_spec_to_store = website_strategy or None
                    if site_spec_to_store and agent_result.metadata.get("renderer"):
                        try:
                            import json as _json
                            _spec_payload = _json.loads(site_spec_to_store)
                            if isinstance(_spec_payload, dict):
                                _spec_payload["_website_engineering"] = {
                                    "engine": agent_result.metadata.get("renderer"),
                                    "provider": agent_result.metadata.get("provider"),
                                    "model": agent_result.metadata.get("model"),
                                    "project_files": agent_result.metadata.get("project_files", []),
                                    "warnings": agent_result.metadata.get("warnings", []),
                                }
                                site_spec_to_store = _json.dumps(_spec_payload, ensure_ascii=False, indent=2)
                        except Exception:
                            site_spec_to_store = website_strategy or None
                    artifact = await publish_site(
                        db,
                        company_id=company.id,
                        slug=slug,
                        html_content=agent_result.content,
                        mission_id=mission.id,
                        quality_score=float(best_score) if best_score else None,
                        site_spec_json=site_spec_to_store,
                    )
                    live_artifact = await get_live_artifact(db, slug)
                    if not live_artifact:
                        if log_step:
                            await log_step(
                                "site_deploy_failed",
                                f"Site publié mais introuvable via le slug public : {slug}",
                            )
                        raise RuntimeError(f"site_artifact_not_found_after_publish:{slug}")
                    if log_step:
                        site_url_log = build_gateway_url(slug)
                        await log_step(
                            "site_deployed",
                            f"Site publié (v{artifact.version}) : {site_url_log or slug}",
                        )

                site_url = build_gateway_url(slug)
                if site_url:
                    deliverable_content = (
                        f"{agent_result.content}\n\n---\n\n"
                        f"**Site live :** {site_url}\n"
                    )

            if mission.mission_type == "ads_launch_plan":
                # Prefer the deterministic backend launcher, then keep the
                # deliverable parser as a compatibility fallback for tool-call runs.
                try:
                    from app.services.ads import launch_ads_v1

                    if company.daily_ads_budget_cents and company.daily_ads_budget_cents > 0:
                        launched = await launch_ads_v1(db, company)
                        if log_step:
                            await log_step(
                                "ads_launch_v1",
                                f"Campagne Meta Ads lancee : {launched.name}",
                            )
                        deliverable_content = (
                            f"{deliverable_content}\n\n---\n\n"
                            f"**Campagne Meta Ads lancee :** {launched.name}\n"
                            f"**Budget quotidien :** ${(launched.daily_budget_cents or 0) / 100:.2f}\n"
                        )
                    elif log_step:
                        await log_step(
                            "ads_launch_blocked",
                            "Budget ads quotidien requis avant le lancement Meta Ads.",
                        )
                except Exception as exc:
                    if log_step:
                        await log_step("ads_launch_blocked", f"Lancement Meta Ads bloque : {str(exc)[:180]}")
                    logger.warning("ads_launch_v1_failed", mission_id=mission.id, error=str(exc))
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


async def _store_product_image_asset(db, company_id: str, image_url: str, mission_id: str) -> None:
    """Persist product image as a CompanyAsset so it appears in Documents/gallery."""
    try:
        from app.models.entities import CompanyAsset
        filename = _product_image_filename(image_url)
        storage_key = f"{company_id}/product_image/{filename}"
        existing = await db.execute(
            __import__("sqlalchemy", fromlist=["select"]).select(CompanyAsset).where(
                CompanyAsset.company_id == company_id,
                CompanyAsset.asset_type == "product_image",
            )
        )
        current = existing.scalars().first()
        if current:
            current.public_url = image_url
            current.storage_key = storage_key
            current.filename = filename
            await db.commit()
            logger.info("product_image_asset_updated", company_id=company_id, url=image_url[:60])
            return
        asset = CompanyAsset(
            company_id=company_id,
            filename=filename,
            asset_type="product_image",
            storage_key=storage_key,
            public_url=image_url,
            size_bytes=0,
        )
        db.add(asset)
        await db.commit()
        logger.info("product_image_asset_stored", company_id=company_id, url=image_url[:60])
    except Exception as exc:
        logger.warning("product_image_asset_store_failed", company_id=company_id, error=str(exc))


def _product_image_filename(image_url: str) -> str:
    lower = (image_url or "").lower().split("?", 1)[0]
    if lower.endswith(".png"):
        return "product_image.png"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "product_image.jpg"
    return "product_image.webp"


async def _mirror_product_image_to_r2(company_id: str, image_url: str, log_step=None) -> str:
    """Copy a generated product image to our R2 public bucket when configured.

    Replicate URLs are useful immediately but not ideal as long-lived product
    assets. R2 gives us a stable URL for the site, ads, and document gallery.
    """
    if not image_url:
        return ""

    from app.core.config import get_settings

    settings = get_settings()
    if not settings.r2_configured:
        return image_url

    try:
        import httpx
        from app.services.r2_storage import upload_bytes

        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(image_url)
            resp.raise_for_status()
            content = resp.content

        if not content:
            return image_url

        content_type = resp.headers.get("content-type", "image/webp").split(";")[0].strip()
        extension = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/webp": "webp",
        }.get(content_type, "webp")
        storage_key = f"{company_id}/product_image/product_image.{extension}"
        public_url = upload_bytes(storage_key, content, content_type or "image/webp")
        if log_step:
            await log_step("product_image_stored", f"Image produit stockée R2 : {public_url[:60]}...")
        return public_url
    except Exception as exc:
        logger.warning("product_image_r2_mirror_failed", company_id=company_id, error=str(exc))
        if log_step:
            await log_step(
                "product_image_storage_fallback",
                "Image produit générée, stockage R2 indisponible — URL provider conservée.",
            )
        return image_url


async def _wait_for_infra(company, log_step, max_wait: int = 90) -> bool:
    """Poll company.infra_status until provisioned or timeout.

    Returns True if infra is ready, False if timeout or failed.
    Attempts re-provisioning if status is 'failed'.
    """
    from app.core.database import SessionLocal
    from app.models.entities import Company as _Company

    if company.infra_status == "provisioned":
        return True

    if company.infra_status == "failed":
        # Attempt re-provisioning
        if log_step:
            await log_step("infra_reprovision", "Infra en échec — nouvelle tentative de provisioning...")
        try:
            from app.services.infra import InfraService
            infra = InfraService()
            result = await infra.provision_company(company.slug or company.name)
            async with SessionLocal() as db:
                _c = await db.get(_Company, company.id)
                if _c:
                    if result.get("neon", {}).get("project_id"):
                        _c.neon_project_id = result["neon"]["project_id"]
                    if result.get("github", {}).get("repo_url"):
                        _c.github_repo_url = result["github"]["repo_url"]
                    if result.get("render", {}).get("service_id"):
                        _c.render_service_id = result["render"]["service_id"]
                    if result.get("url"):
                        _c.render_url = result["url"]
                    _c.infra_status = "provisioned" if result.get("provisioned") else "failed"
                    await db.commit()
            return result.get("provisioned", False)
        except Exception as exc:
            logger.warning("infra_reprovision_failed", company_id=company.id, error=str(exc))
            return False

    # Status is 'pending' — wait for background provisioning to complete
    elapsed = 0
    poll_interval = 5
    while elapsed < max_wait:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        async with SessionLocal() as db:
            _c = await db.get(_Company, company.id)
            if _c and _c.infra_status == "provisioned":
                # Refresh caller's company object
                company.render_service_id = _c.render_service_id
                company.render_url = _c.render_url
                company.github_repo_url = _c.github_repo_url
                return True
            if _c and _c.infra_status == "failed":
                return False
        if log_step:
            await log_step("infra_waiting", f"Attente infra... ({elapsed}s/{max_wait}s)")

    return False


async def _pregenerate_product_image(
    company_id: str,
    website_brief: str,
    company_name: str,
    log_step,
    website_strategy: str = "",
    product_description: str = "",
    target_audience: str = "",
    business_type: str = "ecommerce",
) -> str:
    """Pre-generate the product image from the brief's image section before the Builder runs.

    Extracts the image brief from section 3 of the website_brief and calls Replicate directly.
    Returns the image URL or empty string on failure.
    """
    import re as _re
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.replicate_api_token:
        return ""

    # Product imagery must stay anchored to the actual product. Do not trust
    # generic site_spec prompts such as "before/after athletes" for ecommerce.
    image_prompt = ""
    visual_style = ""
    if website_strategy:
        try:
            import json as _json
            spec = _json.loads(website_strategy)
            visual_style = str(
                spec.get("asset_direction")
                or spec.get("visual_system", {}).get("photo_style", "")
                or ""
            ).strip()
        except Exception:
            visual_style = ""

    try:
        from app.services.website_strategy import build_product_image_prompt

        image_prompt = build_product_image_prompt(
            company_name=company_name,
            product_description=product_description or company_name,
            target_audience=target_audience,
            business_type=business_type,
            visual_style=visual_style,
        )
    except Exception:
        image_prompt = ""

    section_match = _re.search(
        r"(?:3\.|##\s*3|BRIEF IMAGE PRODUIT|IMAGE PRODUIT)[^\n]*\n([\s\S]{30,400}?)(?=\n(?:4\.|##\s*4|STRUCTURE|CTA)|$)",
        website_brief,
        _re.IGNORECASE,
    )
    if not image_prompt and section_match:
        image_prompt = section_match.group(1).strip()
        # Remove markdown bullet points and clean up
        image_prompt = _re.sub(r"^[-*•]\s*", "", image_prompt, flags=_re.MULTILINE)
        image_prompt = " ".join(image_prompt.split())[:400]

    if not image_prompt:
        image_prompt = (
            f"Professional product photo for {company_name}. "
            "Studio lighting, white background, premium brand aesthetic, "
            "high-end commercial photography style."
        )
    image_prompt = " ".join(image_prompt.split())[:500]

    try:
        if log_step:
            await log_step("product_image_generating", f"Génération image produit : {image_prompt[:80]}...")
        quality = (settings.website_image_quality or "premium").lower().strip()
        preferred_model = (
            settings.replicate_image_model_premium
            if quality == "premium" and business_type == "ecommerce"
            else settings.replicate_image_model_standard
        )
        fallback_model = settings.replicate_image_model_standard
        if log_step:
            await log_step(
                "product_image_model",
                f"Mode image {quality} — modèle {preferred_model}",
            )
        result_json = await _generate_product_image_with_fallback(
            settings.replicate_api_token,
            image_prompt,
            preferred_model=preferred_model,
            fallback_model=fallback_model,
            log_step=log_step,
        )
        import json as _json
        result = _json.loads(result_json)
        url = result.get("image_url", "")
        if url:
            url = await _mirror_product_image_to_r2(company_id, url, log_step)
        if url and log_step:
            await log_step("product_image_ready", f"Image produit prête : {url[:60]}...")
        return url
    except Exception as exc:
        logger.warning("product_image_pregeneration_failed", company_id=company_id, error=str(exc))
        return ""


async def _generate_product_image_with_fallback(
    api_token: str,
    image_prompt: str,
    *,
    preferred_model: str,
    fallback_model: str,
    log_step=None,
) -> str:
    from app.agents.tools.generate_image import _execute_generate_image

    try:
        return await _execute_generate_image(
            api_token,
            image_prompt,
            width=1024,
            height=1024,
            model_slug=preferred_model,
        )
    except Exception as exc:
        if preferred_model == fallback_model:
            raise
        logger.warning(
            "premium_product_image_failed_falling_back",
            preferred_model=preferred_model,
            fallback_model=fallback_model,
            error=str(exc),
        )
        if log_step:
            await log_step(
                "product_image_model_fallback",
                f"Modèle premium indisponible — fallback {fallback_model}",
            )
        return await _execute_generate_image(
            api_token,
            image_prompt,
            width=1024,
            height=1024,
            model_slug=fallback_model,
        )


def _validate_landing_html(html: str, product_image_url: str = "", business_type: str = "ecommerce") -> list[str]:
    """Structural pre-validation of landing page HTML before LLM scoring.

    Returns a list of issues to fix. Empty list = HTML passes validation.
    """
    issues: list[str] = []
    if not html:
        return ["HTML vide ou manquant"]

    h = html.lower()

    # Structure de base
    if "<!doctype" not in h and "<html" not in h:
        issues.append("DOCTYPE ou balise <html> manquante")
    if "</html>" not in h:
        issues.append("Balise </html> fermante manquante")
    if "<head" not in h or "<body" not in h:
        issues.append("Structure <head>/<body> incomplète")

    # Responsive
    if "viewport" not in h:
        issues.append("Meta viewport manquante (site non responsive)")

    # Image produit
    if product_image_url and product_image_url not in html:
        issues.append(f"Image produit pré-générée non intégrée ({product_image_url[:50]}...)")
    elif "<img" not in h and not any(
        visual in h for visual in ["product-render", "dashboard", "phone-screen", "visual-wrap"]
    ):
        issues.append("Aucun visuel produit/UI dans le HTML — section visuelle manquante")

    # Sections obligatoires
    import re as _re
    section_count = len(_re.findall(r"<(section|div)[^>]*(?:class|id)[^>]*>", html, _re.IGNORECASE))
    if section_count < 3:
        issues.append(f"Trop peu de sections ({section_count}) — minimum 3 attendues")

    # CTA / bouton d'achat
    has_cta = any(kw in h for kw in ["<button", "<a ", "href=", "cta", "acheter", "buy", "order", "commander"])
    if not has_cta:
        issues.append("Aucun CTA/bouton d'achat détecté")

    # Pas de waitlist pour ecommerce
    if business_type == "ecommerce":
        if any(kw in h for kw in ["waitlist", "liste d'attente", "join the waitlist", "coming soon"]):
            issues.append("Formulaire waitlist détecté pour e-commerce — remplacer par un bouton d'achat Stripe")
        if "stripe" not in h and "buy.stripe.com" not in h:
            issues.append("Aucun lien Stripe détecté — le CTA doit pointer vers un Stripe Payment Link")

    # Analytics Meta Pixel
    if "fbq(" not in html and "facebook.net" not in html:
        issues.append("Meta Pixel / fbq() manquant dans le HTML")

    return issues


def _validate_visual_quality(
    html: str,
    *,
    website_profile: str = "",
    website_strategy: str = "",
    product_image_url: str = "",
    business_type: str = "ecommerce",
) -> list[str]:
    """Opinionated visual/CRO checks before accepting a generated website."""
    issues: list[str] = []
    if not html:
        return ["HTML vide — impossible de valider le rendu visuel"]

    import json as _json
    import re as _re

    h = html.lower()
    spec: dict = {}
    if website_strategy:
        try:
            spec = _json.loads(website_strategy)
        except Exception:
            spec = {}
    profile: dict = {}
    if website_profile:
        try:
            profile = _json.loads(website_profile)
        except Exception:
            profile = {}

    playbook_key = str(spec.get("playbook_key", ""))
    required_visuals = [str(v).lower() for v in spec.get("mandatory_visuals", [])]
    anti_patterns = [str(v).lower() for v in spec.get("anti_patterns", [])]
    product_words = _important_profile_words(str(profile.get("product", "")))
    customer_words = _important_profile_words(str(profile.get("core_customer", "")))
    hero_words = _important_profile_words(str(profile.get("hero_claim", "")))

    if product_words and not any(word in h for word in product_words[:4]):
        issues.append("Company profile ignoré — le produit concret n'est pas assez visible dans le copy")
    if customer_words and not any(word in h for word in customer_words[:4]):
        issues.append("Company profile ignoré — la cible spécifique n'est pas assez visible")
    if hero_words and not any(word in h[:2500] for word in hero_words[:5]):
        issues.append("Hero trop détaché du company profile — reformuler depuis le hero_claim")

    first_screen = h[:3500]
    if not any(tag in first_screen for tag in ["<img", "mockup", "iphone", "dashboard", "product"]):
        issues.append("Hero trop abstrait — aucun visuel produit/UI fort détecté au-dessus du fold")

    generic_phrases = [
        "votre solution", "solution innovante", "transformez votre business",
        "boostez votre croissance", "l'avenir de", "révolutionnez votre",
        "revolutionnez votre", "simple et efficace",
    ]
    if any(phrase in h for phrase in generic_phrases):
        issues.append("Copy trop générique — remplacer par des bénéfices spécifiques au produit")

    css_signals = [
        "display:grid", "display: grid", "display:flex", "display: flex",
        "border-radius", "box-shadow", "linear-gradient", "@media", "position: sticky",
        "max-width", "gap:", "letter-spacing",
    ]
    css_score = sum(1 for signal in css_signals if signal in h)
    if css_score < 6:
        issues.append("Design system trop pauvre — enrichir layout, espacements, cartes et responsive CSS")

    section_titles = len(_re.findall(r"<h[123][^>]*>", html, flags=_re.IGNORECASE))
    if section_titles < 4:
        issues.append("Hiérarchie éditoriale trop faible — ajouter des titres de sections clairs")

    if product_image_url and product_image_url not in html:
        issues.append("Image produit générée absente du rendu final")

    if "saas" in playbook_key or business_type == "saas":
        if not any(word in h for word in ["dashboard", "mockup", "interface", "workflow", "demo"]):
            issues.append("SaaS sans mockup/UI produit — ajouter une interface visible")
        if not any(word in h for word in ["pricing", "tarif", "demo", "trial", "essai"]):
            issues.append("SaaS sans pricing/demo/trial clair")

    if playbook_key == "mobile_app" or business_type == "app":
        if not any(word in h for word in ["iphone", "phone", "mockup", "screen", "écran", "ecran"]):
            issues.append("App mobile sans mockup téléphone ou écrans simulés")

    if business_type == "ecommerce":
        if not any(word in h for word in ["€", "eur", "prix", "offre", "commander", "acheter"]):
            issues.append("E-commerce sans offre/prix/achat suffisamment visible")
        if not any(word in h for word in ["garantie", "livraison", "retour", "sécurisé", "securise"]):
            issues.append("E-commerce sans réduction de risque visible (garantie, livraison, retours)")

    for anti_pattern in anti_patterns:
        normalized = anti_pattern.replace("é", "e")
        if normalized in h or anti_pattern in h:
            issues.append(f"Anti-pattern du playbook détecté : {anti_pattern}")
            break

    for required in required_visuals[:3]:
        words = [w for w in _re.split(r"[^a-z0-9à-ÿ]+", required) if len(w) > 3]
        if words and not any(word in h for word in words):
            issues.append(f"Visuel obligatoire peu visible : {required}")
            break

    return issues


def _important_profile_words(text: str) -> list[str]:
    import re as _re

    stopwords = {
        "avec", "pour", "dans", "from", "that", "this", "your", "vous", "nous",
        "leur", "leurs", "the", "and", "une", "des", "les", "aux", "sur",
        "qui", "que", "plus", "sans", "etre", "être", "get", "better",
    }
    words = [
        w.lower()
        for w in _re.split(r"[^a-zA-Z0-9à-ÿ]+", text)
        if len(w) >= 4
    ]
    return [w for w in words if w not in stopwords][:8]


async def _generate_website_brief(
    company_name: str,
    mission_statement: str,
    product_description: str,
    target_audience: str,
    business_type: str,
    market_scan: str = "",
    stripe_checkout_url: str = "",
) -> str:
    """Generate a creative website brief (brand direction, palette, image brief, structure)
    before the Builder agent runs. Uses a cheap/fast model (gpt-4o-mini).
    Returns a markdown brief to inject into the landing_page user prompt.
    """
    from app.agents.llm_client import call_simple
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.openai_api_key and not settings.anthropic_api_key:
        return ""

    provider = "openai" if settings.openai_api_key else "anthropic"

    system_prompt = (
        "Tu es un directeur artistique et growth marketer spécialisé en création de marques digitales.\n"
        "À partir d'une description de business, tu génères un brief créatif complet pour guider "
        "la génération d'une landing page professionnelle.\n"
        "Sois spécifique, actionnable et cohérent. Pas de généricités. "
        "Adapte tout au vrai produit et à la vraie cible."
    )

    market_excerpt = market_scan[:1000] if market_scan else ""
    cta_instruction = (
        f"\nSTRIPE CHECKOUT URL disponible: {stripe_checkout_url}\n"
        "Le CTA principal DOIT pointer vers cette URL Stripe. JAMAIS de formulaire waitlist.\n"
        if stripe_checkout_url
        else (
            "\nPour e-commerce: CTA = bouton d'achat vers Stripe Payment Link (placeholder: "
            "https://buy.stripe.com/PLACEHOLDER). JAMAIS de formulaire waitlist.\n"
            if business_type == "ecommerce"
            else ""
        )
    )
    user_msg = (
        f"Business: {company_name}\n"
        f"Type: {business_type}\n"
        f"Mission: {mission_statement}\n"
        f"Produit: {product_description or '(non précisé)'}\n"
        f"Audience: {target_audience or '(non précisée)'}\n"
        + (f"\nExtrait étude de marché:\n{market_excerpt}\n" if market_excerpt else "")
        + cta_instruction
        + "\n\nGénère un brief créatif structuré en 6 sections :\n"
        "1. VIBE DE MARQUE (1 phrase : ambiance, univers, ton — ex: 'premium wellness, naturel, chaleureux')\n"
        "2. SYSTÈME VISUEL (palette 3 couleurs hex + nom, typographie headline + body, style photo)\n"
        "3. BRIEF IMAGE PRODUIT (prompt détaillé pour générer une photo produit IA, 2-3 phrases, style "
        "photo de marque premium — nomme 2 marques de référence esthétique)\n"
        "4. STRUCTURE DE PAGE (sections ordonnées, spécifiques au type de business et au produit)\n"
        "5. CTA & TRUST SIGNALS (type de CTA principal, 3-4 trust signals spécifiques au produit)\n"
        "6. ANALYTICS EVENTS (liste les 3-4 events JS à tracker : ViewContent au load, "
        "Lead sur email submit, InitiateCheckout sur CTA click, Purchase confirmation)\n\n"
        "Format: markdown concis, chaque section titrée. Max 450 mots."
    )

    try:
        resp = await call_simple(system_prompt, user_msg, provider=provider, max_tokens=700)
        return resp.content.strip()
    except Exception as exc:
        logger.warning("website_brief_generation_failed", error=str(exc))
        return ""


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
