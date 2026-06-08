from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    AgentType,
    BusinessType,
    Company,
    Mission,
    MissionStatus,
    QuestStep,
    QuestStepStatus,
)
from sqlalchemy.orm import selectinload

# ---------------------------------------------------------------------------
# Quest chain definitions per business type
# ---------------------------------------------------------------------------

# Polsia model — 4 buildings, 5 steps : QG → Site Web → Paiements → Ads (x2)
# Step 1 : QG (researcher)   — valider le marche
# Step 2 : Site Web (builder) — lancer le site
# Step 3 : Paiements (finance) — encaisser
# Step 4 : Ads (marketer)    — preparer les pubs / acquisition
# Step 5 : Ads (marketer)    — lancer Meta Ads
ECOMMERCE_CHAIN: list[dict] = [
    {
        "step": 1,
        "mission_type": "market_scan",
        "title": "Etude de marche",
        "description": "Analyse le marche, les concurrents et les opportunites.",
        "agent_type": AgentType.RESEARCHER,
        "requires": [],
        "building": "hq",
    },
    {
        "step": 2,
        "mission_type": "landing_page",
        "title": "Site web live",
        "description": "Genere et heberge ta landing page avec hero, produit et CTA.",
        "agent_type": AgentType.BUILDER,
        "requires": [1],
        "building": "website",
    },
    {
        "step": 3,
        "mission_type": "payment_setup",
        "title": "Setup paiements",
        "description": "Configure Stripe Connect pour encaisser tes premiers clients.",
        "agent_type": AgentType.FINANCE,
        "requires": [2],
        "building": "payments",
    },
    {
        "step": 4,
        "mission_type": "ad_creation",
        "title": "Creation des pubs",
        "description": "3 variantes d'ads Meta : headlines, visuels et CTAs.",
        "agent_type": AgentType.MARKETER,
        "requires": [2],
        "building": "ads",
    },
    {
        "step": 5,
        "mission_type": "ads_launch_plan",
        "title": "Lancement Meta Ads",
        "description": "Lance les campagnes Meta avec budget, audiences et KPIs.",
        "agent_type": AgentType.MARKETER,
        "requires": [3, 4],
        "building": "ads",
    },
]

APP_CHAIN: list[dict] = [
    {
        "step": 1,
        "mission_type": "market_scan",
        "title": "Etude de marche",
        "description": "Analyse le marche des apps et valide le besoin.",
        "agent_type": AgentType.RESEARCHER,
        "requires": [],
        "building": "hq",
    },
    {
        "step": 2,
        "mission_type": "landing_page",
        "title": "Site web live",
        "description": "Landing page app avec features, screenshots et CTA telechargement.",
        "agent_type": AgentType.BUILDER,
        "requires": [1],
        "building": "website",
    },
    {
        "step": 3,
        "mission_type": "payment_setup",
        "title": "Setup paiements",
        "description": "Integre Stripe pour les in-app purchases et abonnements.",
        "agent_type": AgentType.FINANCE,
        "requires": [2],
        "building": "payments",
    },
    {
        "step": 4,
        "mission_type": "aso_optimization",
        "title": "ASO & fiche store",
        "description": "Optimise ta fiche App Store : titre, keywords et screenshots.",
        "agent_type": AgentType.MARKETER,
        "requires": [2],
        "building": "ads",
    },
    {
        "step": 5,
        "mission_type": "ads_launch_plan",
        "title": "Lancement Meta Ads",
        "description": "Campagnes Meta ciblant les installers de ton app.",
        "agent_type": AgentType.MARKETER,
        "requires": [3, 4],
        "building": "ads",
    },
]

SAAS_CHAIN: list[dict] = [
    {
        "step": 1,
        "mission_type": "market_scan",
        "title": "Etude de marche",
        "description": "Analyse marche SaaS, concurrents et pricing.",
        "agent_type": AgentType.RESEARCHER,
        "requires": [],
        "building": "hq",
    },
    {
        "step": 2,
        "mission_type": "landing_page",
        "title": "Site web live",
        "description": "Landing SaaS avec pricing, features et CTA demo/trial.",
        "agent_type": AgentType.BUILDER,
        "requires": [1],
        "building": "website",
    },
    {
        "step": 3,
        "mission_type": "payment_setup",
        "title": "Setup paiements",
        "description": "Stripe avec abonnements, essai gratuit et webhooks.",
        "agent_type": AgentType.FINANCE,
        "requires": [2],
        "building": "payments",
    },
    {
        "step": 4,
        "mission_type": "competitor_ads_analysis",
        "title": "Analyse pubs concurrents",
        "description": "Top 5 pubs SaaS concurrentes, angles et budgets estimes.",
        "agent_type": AgentType.MARKETER,
        "requires": [2],
        "building": "ads",
    },
    {
        "step": 5,
        "mission_type": "ads_launch_plan",
        "title": "Lancement Meta Ads",
        "description": "Campagnes Meta ciblant les leads SaaS B2B.",
        "agent_type": AgentType.MARKETER,
        "requires": [3, 4],
        "building": "ads",
    },
]

QUEST_CHAINS: dict[BusinessType, list[dict]] = {
    BusinessType.ECOMMERCE: ECOMMERCE_CHAIN,
    BusinessType.APP: APP_CHAIN,
    BusinessType.SAAS: SAAS_CHAIN,
}

# Keep backward-compatible alias
QUEST_CHAIN_DEFINITION = ECOMMERCE_CHAIN


def get_chain_definition(business_type: BusinessType) -> list[dict]:
    return QUEST_CHAINS.get(business_type, ECOMMERCE_CHAIN)


def get_dependency_graph(business_type: BusinessType) -> dict[int, list[int]]:
    chain = get_chain_definition(business_type)
    return {d["step"]: d["requires"] for d in chain}


# Keep backward-compatible alias
DEPENDENCY_GRAPH: dict[int, list[int]] = get_dependency_graph(BusinessType.ECOMMERCE)

BUILDING_NAMES: dict[str, str] = {
    "orchestrator": "QG",
    "builder": "Site Web",
    "marketer": "Ads",
    "finance": "Paiements",
    "researcher": "QG",
    "content": "QG",
    "support": "QG",
    "outreach": "QG",
}

POLSIA_BUILDING_FOR_AGENT: dict[str, str] = {
    "orchestrator": "orchestrator",
    "researcher": "orchestrator",
    "content": "orchestrator",
    "support": "orchestrator",
    "outreach": "orchestrator",
    "builder": "builder",
    "marketer": "marketer",
    "finance": "finance",
}


class QuestChainService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def initialize_chain(
        self, company_id: str, business_type: BusinessType = BusinessType.ECOMMERCE
    ) -> list[QuestStep]:
        chain_def = get_chain_definition(business_type)
        steps: list[QuestStep] = []
        now = datetime.now(timezone.utc)

        for defn in chain_def:
            status = QuestStepStatus.AVAILABLE if defn["step"] == 1 else QuestStepStatus.LOCKED
            step = QuestStep(
                company_id=company_id,
                step_number=defn["step"],
                mission_type=defn["mission_type"],
                title=defn["title"],
                description=defn["description"],
                agent_type=defn["agent_type"],
                status=status,
                unlocked_at=now if status == QuestStepStatus.AVAILABLE else None,
            )
            self.db.add(step)
            steps.append(step)

        await self.db.commit()
        for s in steps:
            await self.db.refresh(s)
        return steps

    async def get_chain(self, company_id: str) -> list[QuestStep]:
        result = await self.db.execute(
            select(QuestStep)
            .where(QuestStep.company_id == company_id)
            .order_by(QuestStep.step_number)
        )
        return list(result.scalars().all())

    async def get_step(self, company_id: str, step_number: int) -> Optional[QuestStep]:
        result = await self.db.execute(
            select(QuestStep).where(
                QuestStep.company_id == company_id,
                QuestStep.step_number == step_number,
            )
        )
        return result.scalar_one_or_none()

    async def mark_step_running(
        self, company_id: str, step_number: int, mission_id: str
    ) -> Optional[QuestStep]:
        step = await self.get_step(company_id, step_number)
        if not step or step.status != QuestStepStatus.AVAILABLE:
            return None
        step.status = QuestStepStatus.RUNNING
        step.mission_id = mission_id
        await self.db.commit()
        await self.db.refresh(step)
        return step

    async def complete_step(
        self, company_id: str, step_number: int,
        business_type: BusinessType = BusinessType.ECOMMERCE,
    ) -> list[QuestStep]:
        """Mark a step completed and unlock any dependents whose prereqs are now all met."""
        step = await self.get_step(company_id, step_number)
        if not step:
            return []
        step.status = QuestStepStatus.COMPLETED
        step.completed_at = datetime.now(timezone.utc)
        await self.db.commit()

        dep_graph = get_dependency_graph(business_type)
        chain = await self.get_chain(company_id)
        completed_numbers = {s.step_number for s in chain if s.status == QuestStepStatus.COMPLETED}
        now = datetime.now(timezone.utc)
        newly_unlocked: list[QuestStep] = []

        for s in chain:
            if s.status != QuestStepStatus.LOCKED:
                continue
            prereqs = dep_graph.get(s.step_number, [])
            if prereqs and all(p in completed_numbers for p in prereqs):
                s.status = QuestStepStatus.AVAILABLE
                s.unlocked_at = now
                newly_unlocked.append(s)

        if newly_unlocked:
            await self.db.commit()

        return newly_unlocked

    async def find_step_for_mission(
        self, company_id: str, mission_type: str
    ) -> Optional[QuestStep]:
        result = await self.db.execute(
            select(QuestStep).where(
                QuestStep.company_id == company_id,
                QuestStep.mission_type == mission_type,
                QuestStep.status.in_([
                    QuestStepStatus.AVAILABLE,
                    QuestStepStatus.RUNNING,
                ]),
            )
        )
        return result.scalar_one_or_none()

    async def get_prerequisite_deliverables(
        self, company_id: str, step_number: int,
        business_type: BusinessType = BusinessType.ECOMMERCE,
    ) -> list[dict]:
        """Return deliverables from completed prerequisite steps."""
        dep_graph = get_dependency_graph(business_type)
        prereq_numbers = dep_graph.get(step_number, [])
        if not prereq_numbers:
            return []

        result = await self.db.execute(
            select(QuestStep)
            .where(
                QuestStep.company_id == company_id,
                QuestStep.step_number.in_(prereq_numbers),
                QuestStep.status == QuestStepStatus.COMPLETED,
                QuestStep.mission_id.isnot(None),
            )
        )
        steps = list(result.scalars().all())

        deliverables = []
        for step in steps:
            mission_result = await self.db.execute(
                select(Mission).where(
                    Mission.id == step.mission_id,
                    Mission.status == MissionStatus.COMPLETED,
                )
            )
            mission = mission_result.scalar_one_or_none()
            if mission and mission.deliverable:
                deliverables.append({
                    "step_number": step.step_number,
                    "title": step.title,
                    "mission_type": step.mission_type,
                    "deliverable": _summarize_deliverable(step.mission_type, mission.deliverable),
                })

        return sorted(deliverables, key=lambda d: d["step_number"])


def _summarize_deliverable(mission_type: str, deliverable: str) -> str:
    """For HTML deliverables (landing_page), extract site URL and strip the raw HTML
    to avoid flooding downstream agents with thousands of tokens of markup.
    For all other formats, truncate to 2000 chars.
    """
    if mission_type != "landing_page":
        return deliverable[:2000]

    import re

    # Extract the deployed URL appended by the runner
    site_url = ""
    url_match = re.search(r"\*\*Site live\s*:\*\*\s*(https?://\S+)", deliverable)
    if url_match:
        site_url = url_match.group(1).strip()

    # Extract meaningful text nodes from HTML (title, meta description, h1-h3, p, li)
    text_chunks: list[str] = []
    for tag in ("title", "h1", "h2", "h3", "p", "li"):
        for match in re.finditer(rf"<{tag}[^>]*>(.*?)</{tag}>", deliverable, re.DOTALL | re.IGNORECASE):
            text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
            if text and len(text) > 10:
                text_chunks.append(text)

    summary_parts = []
    if site_url:
        summary_parts.append(f"Site live : {site_url}")
    if text_chunks:
        combined = " | ".join(text_chunks[:30])
        summary_parts.append(f"Contenu de la landing page : {combined[:1500]}")
    else:
        # Fallback: strip all tags and return plain text
        plain = re.sub(r"<[^>]+>", " ", deliverable)
        plain = re.sub(r"\s+", " ", plain).strip()
        summary_parts.append(plain[:1500])

    return "\n".join(summary_parts)
