from __future__ import annotations

import json as _json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, verify_api_key
from app.core.config import get_settings
from app.models.entities import (
    Company,
    Mission,
    MissionStatus,
    QuestStep,
    QuestStepStatus,
    SiteArtifact,
    TaskSource,
)
from app.services.quest_chain import BUILDING_NAMES

router = APIRouter(dependencies=[Depends(verify_api_key)])


WEBSITE_WORDS = ("site", "website", "landing", "page", "hero", "homepage")
WEBSITE_CHANGE_WORDS = (
    "modifie", "modifier", "change", "changer", "ameliore", "améliore",
    "ameliorer", "améliorer", "refais", "refaire", "rends", "mettre",
    "mets", "ajoute", "ajouter", "retire", "supprime", "corrige",
    "premium", "luxe", "stylé", "style", "vibe",
)


class SageMessageIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list)


class SageMessageOut(BaseModel):
    reply: str
    created_task_id: Optional[str] = None
    created_task_title: Optional[str] = None


def _is_website_revision_request(message: str) -> bool:
    msg = message.lower()
    return any(w in msg for w in WEBSITE_WORDS) and any(w in msg for w in WEBSITE_CHANGE_WORDS)


# ---------------------------------------------------------------------------
# Sage tool definitions (Polsia CEO agent tools)
# ---------------------------------------------------------------------------

SAGE_TOOLS = [
    {
        "name": "create_task",
        "description": (
            "Crée une nouvelle tâche dans la file d'attente du joueur. "
            "Utilise cet outil quand le joueur demande de lancer une action, "
            "ou quand tu identifies le prochain move prioritaire. "
            "La tâche sera exécutée par l'agent le plus adapté. 1 crédit sera débité."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Titre court de la tâche (ex: 'Diagnostiquer les Meta Ads')"},
                "description": {"type": "string", "description": "Description détaillée de ce que l'agent doit faire"},
                "agent_type": {
                    "type": "string",
                    "enum": ["builder", "marketer", "researcher", "orchestrator", "outreach", "support", "finance", "content", "browser", "data", "ops", "growth"],
                    "description": "Type d'agent à assigner (optionnel — auto-routing si absent)",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "reject_task",
        "description": "Rejette (annule) une tâche en attente dans la file. Rembourse 1 crédit.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "L'ID de la tâche à rejeter"},
                "reason": {"type": "string", "description": "Raison du rejet (ex: 'duplicate', 'no_longer_needed')"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "get_task_queue",
        "description": "Lit la file d'attente actuelle des tâches en attente. Aucun crédit consommé.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

# OpenAI format (slightly different schema key)
SAGE_TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        },
    }
    for t in SAGE_TOOLS
]


def _build_sage_system_prompt(
    company: Company,
    quest_steps: list[QuestStep],
    missions: list[Mission],
    pending_tasks: list[Mission] | None = None,
    subscription_info: dict | None = None,
) -> str:
    bt = company.business_type.value if company.business_type else "ecommerce"

    completed_steps = [s for s in quest_steps if s.status == QuestStepStatus.COMPLETED]
    available_steps = [s for s in quest_steps if s.status == QuestStepStatus.AVAILABLE]
    running_steps = [s for s in quest_steps if s.status == QuestStepStatus.RUNNING]
    locked_steps = [s for s in quest_steps if s.status == QuestStepStatus.LOCKED]

    running_missions = [m for m in missions if m.status in (MissionStatus.RUNNING, MissionStatus.PENDING)]
    completed_missions = [m for m in missions if m.status == MissionStatus.COMPLETED]

    buildings_list = ", ".join(
        f"{BUILDING_NAMES.get(b.agent_type.value, b.agent_type.value)} (niv.{b.level})"
        for b in company.buildings
    )

    quest_status = []
    for s in quest_steps:
        status_icon = {"completed": "done", "available": "DISPONIBLE", "running": "en cours", "locked": "verrouillee"}
        quest_status.append(f"  {s.step_number}. {s.title} [{status_icon.get(s.status.value, s.status.value)}]")

    deliverables = []
    for m in completed_missions:
        if m.deliverable:
            deliverables.append(f"- {m.mission_type}: {m.deliverable[:500]}")

    # Task queue context
    pending_list = pending_tasks or []
    queue_lines = []
    for t in pending_list[:8]:
        display = t.title or t.mission_type
        queue_lines.append(f"  [{t.id[:8]}] #{t.queue_order or '?'} — {display} ({t.agent_type.value}, source={t.source.value if t.source else 'user'})")

    # Credits context
    credits_info = ""
    if subscription_info:
        total = subscription_info.get("total_credits", 0)
        status = subscription_info.get("status", "")
        credits_info = f"- Crédits disponibles: {total} (statut: {status})"
        if total < 3:
            credits_info += " ⚠️ CRÉDITS FAIBLES"

    return f"""Tu es Le Sage, le CEO agent et mentor du village dans RPG Agent Company.
Tu guides le fondateur dans le lancement de son business ET tu peux créer des tâches pour les agents.

CONTEXTE DE LA COMPANY:
- Nom: {company.name}
- Type de business: {bt}
- Mission: {company.mission_statement or 'Non definie'}
- Produit: {company.product_description or 'Non decrit'}
- Audience cible: {company.target_audience or 'Non definie'}
- Niveau: {company.level} | XP: {company.xp}
- Batiments: {buildings_list}
{credits_info}

PROGRESSION QUEST CHAIN ({len(completed_steps)}/{len(quest_steps)} etapes):
{chr(10).join(quest_status)}

TÂCHES EN ATTENTE ({len(pending_list)}):
{chr(10).join(queue_lines) if queue_lines else 'Aucune tâche en attente'}

MISSIONS EN COURS ({len(running_missions)}):
{chr(10).join(f'- {m.mission_type} ({m.agent_type.value})' for m in running_missions) or 'Aucune'}

LIVRABLES PRODUITS ({len(deliverables)}):
{chr(10).join(deliverables[:5]) if deliverables else 'Aucun livrable pour le moment'}

REGLES:
- Reponds en francais, de maniere concise et utile (2-4 phrases max sauf si l'utilisateur demande plus de details)
- Reste dans ton role de Sage/mentor bienveillant du village RPG
- Si l'utilisateur demande de lancer une action ou une tâche → utilise l'outil create_task
- Avant de créer une tâche similaire à une existante en queue, vérifie si ce n'est pas un doublon
- Si credits < 3, avertis l'utilisateur avant de créer une tâche
- Si credits = 0, ne crée PAS de tâche — dis à l'utilisateur d'acheter des crédits
- Tu peux utiliser reject_task pour nettoyer les doublons si l'utilisateur le demande
- Ne genere pas de livrables complets, oriente vers les agents specialises
- Si l'utilisateur pose une question hors sujet, ramene la conversation sur son business
"""


@router.post("/companies/{company_id}/sage", response_model=SageMessageOut)
async def sage_chat(company_id: str, body: SageMessageIn, db: DbSession):
    result = await db.execute(
        select(Company)
        .where(Company.id == company_id)
        .options(selectinload(Company.buildings))
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")

    quest_result = await db.execute(
        select(QuestStep)
        .where(QuestStep.company_id == company_id)
        .order_by(QuestStep.step_number)
    )
    quest_steps = list(quest_result.scalars().all())

    mission_result = await db.execute(
        select(Mission)
        .where(Mission.company_id == company_id)
        .order_by(Mission.created_at.desc())
        .limit(20)
    )
    missions = list(mission_result.scalars().all())

    # Fetch pending task queue + subscription for context
    from app.models.entities import MissionStatus as MS
    pending_result = await db.execute(
        select(Mission)
        .where(Mission.company_id == company_id, Mission.status == MS.PENDING)
        .order_by(Mission.queue_order.asc().nulls_last())
        .limit(10)
    )
    pending_tasks = list(pending_result.scalars().all())

    from app.services.billing import get_subscription_status
    sub_info = await get_subscription_status(db, company_id)

    if _is_website_revision_request(body.message):
        from app.services.mission import MissionService

        latest_site_result = await db.execute(
            select(SiteArtifact)
            .where(SiteArtifact.company_id == company_id)
            .order_by(SiteArtifact.version.desc())
            .limit(1)
        )
        latest_site = latest_site_result.scalar_one_or_none()
        mission_type = "landing_page_revision" if latest_site else "landing_page"
        title = "Réviser le site" if latest_site else "Créer le site"
        svc = MissionService(db)
        try:
            mission = await svc.create_catalog_task(
                company_id=company_id,
                mission_type=mission_type,
                title=title,
                description=body.message,
                source=TaskSource.CEO_PROPOSAL,
                auto_schedule=False,
            )
            reply = (
                "Parfait, j'ai ajouté une révision du site à la file. "
                "Le Builder gardera la version actuelle comme base et republiera une nouvelle version."
                if latest_site
                else (
                    "Je n'ai pas trouvé de site existant, donc j'ai ajouté la création "
                    "du site à la file."
                )
            )
            return SageMessageOut(
                reply=reply,
                created_task_id=mission.id,
                created_task_title=mission.title or mission.mission_type,
            )
        except ValueError as exc:
            if str(exc) == "no_credits":
                return SageMessageOut(
                    reply="Tu n'as plus de crédits pour lancer cette modification du site."
                )
            return SageMessageOut(reply=f"Je n'ai pas pu créer la tâche Website : {exc}")

    system_prompt = _build_sage_system_prompt(company, quest_steps, missions, pending_tasks, sub_info)

    messages = [{"role": "system", "content": system_prompt}]
    for h in body.history[-10:]:
        role = h.get("role", "user")
        content = h.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": body.message})

    settings = get_settings()

    if settings.agent_mode == "mock":
        return SageMessageOut(reply=_mock_reply(body.message, quest_steps))

    try:
        reply, tool_results = await _call_llm_with_tools(messages, settings, company_id, db)
        created = tool_results.get("created_task")
        return SageMessageOut(
            reply=reply,
            created_task_id=created.id if created else None,
            created_task_title=created.title or created.mission_type if created else None,
        )
    except Exception:
        return SageMessageOut(reply=_mock_reply(body.message, quest_steps))


class SageDailyBrief(BaseModel):
    brief: str
    recommended_action: str
    progress_pct: float


@router.get("/companies/{company_id}/sage/daily-brief", response_model=SageDailyBrief)
async def sage_daily_brief(company_id: str, db: DbSession):
    """P2 — Proactive Sage: generates a daily brief without user input.

    Call this on app open or via background refresh to give the user
    a Polsia-style 'CEO daily cycle' insight.
    """
    result = await db.execute(
        select(Company)
        .where(Company.id == company_id)
        .options(selectinload(Company.buildings))
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")

    quest_result = await db.execute(
        select(QuestStep)
        .where(QuestStep.company_id == company_id)
        .order_by(QuestStep.step_number)
    )
    quest_steps = list(quest_result.scalars().all())

    mission_result = await db.execute(
        select(Mission)
        .where(Mission.company_id == company_id)
        .order_by(Mission.created_at.desc())
        .limit(10)
    )
    missions = list(mission_result.scalars().all())

    completed = [s for s in quest_steps if s.status == QuestStepStatus.COMPLETED]
    available = [s for s in quest_steps if s.status == QuestStepStatus.AVAILABLE]
    running = [s for s in quest_steps if s.status == QuestStepStatus.RUNNING]

    progress_pct = round(len(completed) / len(quest_steps) * 100, 1) if quest_steps else 0.0

    settings = get_settings()
    if settings.agent_mode == "mock" or (not settings.anthropic_api_key and not settings.openai_api_key):
        recommended = available[0].title if available else (running[0].title if running else "Continuer la progression")
        return SageDailyBrief(
            brief=f"Progression : {len(completed)}/{len(quest_steps)} étapes. {'Mission en cours : ' + running[0].title if running else 'Prêt pour la prochaine étape.'}",
            recommended_action=recommended,
            progress_pct=progress_pct,
        )

    # Build proactive prompt
    last_deliverable = ""
    for m in missions:
        if m.status == MissionStatus.COMPLETED and m.deliverable:
            last_deliverable = f"\nDernier livrable ({m.mission_type}) : {m.deliverable[:600]}"
            break

    proactive_prompt = f"""Tu es Le Sage de {company.name}. Génère un daily brief proactif en 3 parties COURTES :

**État du business :**
- Business : {company.business_type.value} | {company.name}
- Mission : {company.mission_statement or 'Non définie'}
- Progression : {len(completed)}/{len(quest_steps)} étapes ({progress_pct}%)
- En cours : {', '.join(s.title for s in running) if running else 'rien'}
- Disponibles : {', '.join(s.title for s in available) if available else 'rien'}
{last_deliverable}

Réponds en JSON avec ces 3 clés exactes :
{{"brief": "2-3 phrases sur l'état actuel et un insight stratégique", "recommended_action": "1 action concrète à faire maintenant (max 15 mots)"}}

Sois direct, concis, actionnable. En français."""

    try:
        messages = [{"role": "user", "content": proactive_prompt}]
        raw = await _call_llm(messages, settings)

        import json as _json
        # Try to parse JSON from LLM response
        cleaned = raw.strip()
        if "```" in cleaned:
            cleaned = cleaned.split("```")[1].replace("json", "").strip()
        parsed = _json.loads(cleaned)
        return SageDailyBrief(
            brief=parsed.get("brief", ""),
            recommended_action=parsed.get("recommended_action", ""),
            progress_pct=progress_pct,
        )
    except Exception:
        # Fallback if LLM doesn't return valid JSON
        recommended = available[0].title if available else (running[0].title if running else "Continuer")
        return SageDailyBrief(
            brief=f"{len(completed)}/{len(quest_steps)} étapes complétées. {('En cours : ' + running[0].title) if running else 'Des étapes sont disponibles.'}",
            recommended_action=recommended,
            progress_pct=progress_pct,
        )


def _mock_reply(message: str, quest_steps: list[QuestStep]) -> str:
    available = [s for s in quest_steps if s.status == QuestStepStatus.AVAILABLE]
    running = [s for s in quest_steps if s.status == QuestStepStatus.RUNNING]
    completed = [s for s in quest_steps if s.status == QuestStepStatus.COMPLETED]

    msg_lower = message.lower()

    if any(w in msg_lower for w in ["quete", "quest", "etape", "mission", "lancer"]):
        if available:
            step = available[0]
            building = BUILDING_NAMES.get(step.agent_type.value, "un batiment")
            return (
                f"Tu as une etape disponible : \"{step.title}\". "
                f"Va voir l'agent a {building} pour la lancer !"
            )
        if running:
            return f"Patience, {len(running)} mission(s) en cours. Reviens quand c'est termine !"
        return f"Tu as complete {len(completed)}/{len(quest_steps)} etapes. Continue comme ca !"

    if any(w in msg_lower for w in ["aide", "help", "bloque", "quoi faire", "conseil"]):
        if available:
            step = available[0]
            return (
                f"Je te conseille de lancer l'etape \"{step.title}\". "
                f"C'est la prochaine dans ta quest chain !"
            )
        if running:
            return "Des agents travaillent en ce moment. Patiente un peu, les resultats arrivent !"
        return "Explore le village et parle aux habitants pour decouvrir de nouvelles opportunites."

    if any(w in msg_lower for w in ["progres", "avancement", "status", "ou j'en suis"]):
        return (
            f"Tu as complete {len(completed)}/{len(quest_steps)} etapes. "
            f"{len(running)} en cours, {len(available)} disponible(s). "
            f"{'Tout avance bien !' if completed else 'Il est temps de commencer !'}"
        )

    return (
        "Bonne question ! En tant que Sage, je te conseille de consulter "
        "tes quetes et de parler aux agents dans le village. "
        "Chaque batiment a un specialiste qui peut t'aider."
    )


async def _execute_sage_tool(
    tool_name: str,
    tool_input: dict,
    company_id: str,
    db: AsyncSession,
) -> tuple[str, dict]:
    """Execute a Sage tool call and return (text_result, side_effects)."""
    from app.models.entities import MissionStatus, TaskSource
    from app.services.mission import MissionService
    from sqlalchemy import select

    svc = MissionService(db)
    side_effects: dict = {}

    if tool_name == "get_task_queue":
        tasks = await svc.get_task_queue(company_id)
        if not tasks:
            return "File d'attente vide.", side_effects
        lines = [f"#{t.queue_order or '?'} [{t.id[:8]}] {t.title or t.mission_type} ({t.agent_type.value})" for t in tasks]
        return "Tâches en attente :\n" + "\n".join(lines), side_effects

    if tool_name == "create_task":
        title = tool_input.get("title", "Nouvelle tâche")
        description = tool_input.get("description", "")
        agent_type_str = tool_input.get("agent_type")
        try:
            mission = await svc.create_freeform_task(
                company_id=company_id,
                title=title,
                description=description,
                agent_type_str=agent_type_str,
                source=TaskSource.CEO_PROPOSAL,
            )
            side_effects["created_task"] = mission
            return f"Tâche créée : [{mission.id[:8]}] {title} (agent: {mission.agent_type.value})", side_effects
        except ValueError as e:
            return f"Impossible de créer la tâche : {e}", side_effects

    if tool_name == "reject_task":
        task_id = tool_input.get("task_id", "")
        reason = tool_input.get("reason", "rejected_by_sage")
        # Try full ID first, then partial
        result = await db.execute(select(Mission).where(Mission.id == task_id))
        mission = result.scalar_one_or_none()
        if not mission:
            # Try prefix match
            result2 = await db.execute(
                select(Mission)
                .where(Mission.company_id == company_id, Mission.id.startswith(task_id))
                .limit(1)
            )
            mission = result2.scalar_one_or_none()
        if not mission:
            return f"Tâche {task_id} introuvable.", side_effects
        if mission.status != MissionStatus.PENDING:
            return f"Tâche {task_id} n'est pas en attente (status: {mission.status.value}).", side_effects
        try:
            await svc.reject_task(mission.id, company_id, reason)
            return f"Tâche [{task_id[:8]}] rejetée ({reason}).", side_effects
        except ValueError as e:
            return f"Erreur rejet : {e}", side_effects

    return f"Outil inconnu: {tool_name}", side_effects


async def _call_llm_with_tools(
    messages: list[dict],
    settings,
    company_id: str,
    db: AsyncSession,
) -> tuple[str, dict]:
    """Call LLM with tool support. Returns (final_text, side_effects_dict)."""
    all_side_effects: dict = {}

    if settings.anthropic_api_key:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        system_msg = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
        chat_messages = [m for m in messages if m["role"] != "system"]

        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            system=system_msg,
            messages=chat_messages,
            tools=SAGE_TOOLS,
        )

        # Process tool use blocks
        tool_results_content = []
        for block in response.content:
            if block.type == "tool_use":
                tool_result, side = await _execute_sage_tool(block.name, block.input, company_id, db)
                all_side_effects.update(side)
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": tool_result,
                })

        if tool_results_content:
            # Continue conversation with tool results
            chat_messages.append({"role": "assistant", "content": response.content})
            chat_messages.append({"role": "user", "content": tool_results_content})
            final_response = await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=1024,
                system=system_msg,
                messages=chat_messages,
            )
            text = "".join(b.text for b in final_response.content if hasattr(b, "text"))
        else:
            text = "".join(b.text for b in response.content if hasattr(b, "text"))

        return text, all_side_effects

    if settings.openai_api_key:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            max_tokens=1024,
            tools=SAGE_TOOLS_OPENAI,
            tool_choice="auto",
        )
        msg = response.choices[0].message

        # Handle tool calls
        if msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]})
            for tc in msg.tool_calls:
                args = _json.loads(tc.function.arguments)
                tool_result, side = await _execute_sage_tool(tc.function.name, args, company_id, db)
                all_side_effects.update(side)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_result})

            final = await client.chat.completions.create(
                model=settings.openai_model, messages=messages, max_tokens=1024
            )
            return final.choices[0].message.content or "", all_side_effects

        return msg.content or "", all_side_effects

    raise RuntimeError("No LLM provider configured")


async def _call_llm(messages: list[dict], settings) -> str:
    if settings.anthropic_api_key:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        system_msg = messages[0]["content"] if messages[0]["role"] == "system" else ""
        chat_messages = [m for m in messages if m["role"] != "system"]
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            system=system_msg,
            messages=chat_messages,
        )
        return response.content[0].text if response.content else ""

    if settings.openai_api_key:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            max_tokens=1024,
        )
        return response.choices[0].message.content or ""

    raise RuntimeError("No LLM provider configured")
