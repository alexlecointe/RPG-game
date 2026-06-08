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

# Polsia-like simplified chain — HQ → Website → Payments → Ads
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
        "mission_type": "competitor_ads_analysis",
        "title": "Analyse concurrentielle",
        "description": "Analyse les top pubs et strategies de tes concurrents.",
        "agent_type": AgentType.RESEARCHER,
        "requires": [1],
        "building": "hq",
    },
    {
        "step": 3,
        "mission_type": "product_brief",
        "title": "Brief produit",
        "description": "Definis ton produit : nom, USP, prix et angle marketing.",
        "agent_type": AgentType.BUILDER,
        "requires": [1],
        "building": "website",
    },
    {
        "step": 4,
        "mission_type": "brand_design",
        "title": "Design de marque",
        "description": "Charte graphique : palette, typo, ton et mood board.",
        "agent_type": AgentType.CONTENT,
        "requires": [3],
        "building": "website",
    },
    {
        "step": 5,
        "mission_type": "landing_page",
        "title": "Site web live",
        "description": "Genere et heberge ta landing page sur ton sous-domaine.",
        "agent_type": AgentType.BUILDER,
        "requires": [3, 4],
        "building": "website",
    },
    {
        "step": 6,
        "mission_type": "payment_setup",
        "title": "Setup paiements",
        "description": "Configure Stripe Connect pour recevoir tes paiements.",
        "agent_type": AgentType.FINANCE,
        "requires": [5],
        "building": "payments",
    },
    {
        "step": 7,
        "mission_type": "ad_creation",
        "title": "Creation pubs video",
        "description": "Genere 3 videos ads verticales 9:16 pour Meta.",
        "agent_type": AgentType.MARKETER,
        "requires": [5],
        "building": "ads",
    },
    {
        "step": 8,
        "mission_type": "ads_launch_plan",
        "title": "Lancement Meta Ads",
        "description": "Lance les campagnes Meta avec ton budget quotidien.",
        "agent_type": AgentType.MARKETER,
        "requires": [6, 7],
        "building": "ads",
    },
]

APP_CHAIN: list[dict] = [
    {"step": 1, "mission_type": "market_scan", "title": "Etude de marche", "description": "Analyse le marche des apps.", "agent_type": AgentType.RESEARCHER, "requires": [], "building": "hq"},
    {"step": 2, "mission_type": "product_brief", "title": "Brief produit", "description": "Features MVP et specs.", "agent_type": AgentType.BUILDER, "requires": [1], "building": "website"},
    {"step": 3, "mission_type": "brand_design", "title": "Design de marque", "description": "Charte graphique et icone app.", "agent_type": AgentType.CONTENT, "requires": [2], "building": "website"},
    {"step": 4, "mission_type": "landing_page", "title": "Site web live", "description": "Landing page hebergee.", "agent_type": AgentType.BUILDER, "requires": [2, 3], "building": "website"},
    {"step": 5, "mission_type": "payment_setup", "title": "Setup paiements", "description": "Stripe Connect.", "agent_type": AgentType.FINANCE, "requires": [4], "building": "payments"},
    {"step": 6, "mission_type": "ad_creation", "title": "Creation pubs video", "description": "Videos ads Meta.", "agent_type": AgentType.MARKETER, "requires": [4], "building": "ads"},
    {"step": 7, "mission_type": "ads_launch_plan", "title": "Lancement Meta Ads", "description": "Campagnes Meta live.", "agent_type": AgentType.MARKETER, "requires": [5, 6], "building": "ads"},
]

SAAS_CHAIN: list[dict] = [
    {"step": 1, "mission_type": "market_scan", "title": "Etude de marche", "description": "Analyse marche SaaS.", "agent_type": AgentType.RESEARCHER, "requires": [], "building": "hq"},
    {"step": 2, "mission_type": "competitor_ads_analysis", "title": "Analyse concurrentielle", "description": "Concurrents SaaS.", "agent_type": AgentType.RESEARCHER, "requires": [1], "building": "hq"},
    {"step": 3, "mission_type": "product_brief", "title": "Brief produit / pricing", "description": "Produit et tiers pricing.", "agent_type": AgentType.BUILDER, "requires": [1], "building": "website"},
    {"step": 4, "mission_type": "brand_design", "title": "Design de marque", "description": "Charte graphique.", "agent_type": AgentType.CONTENT, "requires": [3], "building": "website"},
    {"step": 5, "mission_type": "landing_page", "title": "Site web live", "description": "Landing hebergee.", "agent_type": AgentType.BUILDER, "requires": [3, 4], "building": "website"},
    {"step": 6, "mission_type": "payment_setup", "title": "Setup paiements", "description": "Stripe Connect + abonnements.", "agent_type": AgentType.FINANCE, "requires": [5], "building": "payments"},
    {"step": 7, "mission_type": "ad_creation", "title": "Creation pubs video", "description": "Videos ads Meta.", "agent_type": AgentType.MARKETER, "requires": [5], "building": "ads"},
    {"step": 8, "mission_type": "ads_launch_plan", "title": "Lancement Meta Ads", "description": "Campagnes Meta live.", "agent_type": AgentType.MARKETER, "requires": [6, 7], "building": "ads"},
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
                    "deliverable": mission.deliverable,
                })

        return sorted(deliverables, key=lambda d: d["step_number"])
