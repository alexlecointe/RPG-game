from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, verify_api_key
from app.core.config import get_settings
from app.models.entities import Company, Mission, MissionStatus, QuestStep, QuestStepStatus
from app.services.quest_chain import BUILDING_NAMES

router = APIRouter(dependencies=[Depends(verify_api_key)])


class SageMessageIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list)


class SageMessageOut(BaseModel):
    reply: str


def _build_sage_system_prompt(company: Company, quest_steps: list[QuestStep], missions: list[Mission]) -> str:
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

    return f"""Tu es Le Sage, le mentor du village dans RPG Agent Company.
Tu guides le fondateur dans le lancement de son business.

CONTEXTE DE LA COMPANY:
- Nom: {company.name}
- Type de business: {bt}
- Mission: {company.mission_statement or 'Non definie'}
- Produit: {company.product_description or 'Non decrit'}
- Audience cible: {company.target_audience or 'Non definie'}
- Niveau: {company.level} | XP: {company.xp}
- Batiments: {buildings_list}

PROGRESSION QUEST CHAIN ({len(completed_steps)}/{len(quest_steps)} etapes):
{chr(10).join(quest_status)}

MISSIONS EN COURS ({len(running_missions)}):
{chr(10).join(f'- {m.mission_type} ({m.agent_type.value})' for m in running_missions) or 'Aucune'}

LIVRABLES PRODUITS ({len(deliverables)}):
{chr(10).join(deliverables[:5]) if deliverables else 'Aucun livrable pour le moment'}

REGLES:
- Reponds en francais, de maniere concise et utile (2-4 phrases max sauf si l'utilisateur demande plus de details)
- Reste dans ton role de Sage/mentor bienveillant du village RPG
- Si l'utilisateur demande de l'aide sur une etape, guide-le vers le bon batiment/agent
- Si l'utilisateur demande des conseils business, donne des conseils adaptes a son type de business ({bt})
- Tu peux suggerer de lancer des quetes disponibles
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

    system_prompt = _build_sage_system_prompt(company, quest_steps, missions)

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
        reply = await _call_llm(messages, settings)
        return SageMessageOut(reply=reply)
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
