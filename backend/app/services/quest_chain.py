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

ECOMMERCE_CHAIN: list[dict] = [
    {
        "step": 1,
        "mission_type": "market_scan",
        "title": "Etude de marche",
        "description": "Analyse tes concurrents, le marche cible et les gaps a exploiter.",
        "agent_type": AgentType.RESEARCHER,
        "requires": [],
    },
    {
        "step": 2,
        "mission_type": "product_brief",
        "title": "Brief produit",
        "description": "Definis ton produit : nom, USP, prix, specs et angle marketing.",
        "agent_type": AgentType.BUILDER,
        "requires": [1],
    },
    {
        "step": 3,
        "mission_type": "supplier_sourcing",
        "title": "Recherche fournisseur",
        "description": "Trouve 3-5 fournisseurs (AliExpress/Alibaba) avec prix et delais.",
        "agent_type": AgentType.RESEARCHER,
        "requires": [2],
    },
    {
        "step": 4,
        "mission_type": "brand_design",
        "title": "Design de marque",
        "description": "Cree ta charte graphique : palette, typo, ton et mood board.",
        "agent_type": AgentType.CONTENT,
        "requires": [2],
    },
    {
        "step": 5,
        "mission_type": "landing_page",
        "title": "Page produit",
        "description": "Construis ta landing page avec sections, CTA et copy de vente.",
        "agent_type": AgentType.BUILDER,
        "requires": [3, 4],
    },
    {
        "step": 6,
        "mission_type": "payment_setup",
        "title": "Setup paiements",
        "description": "Prepare l'integration Stripe : checklist, config et webhooks.",
        "agent_type": AgentType.FINANCE,
        "requires": [5],
    },
    {
        "step": 7,
        "mission_type": "competitor_ads_analysis",
        "title": "Analyse pubs concurrents",
        "description": "Analyse les top pubs de tes concurrents : budgets, angles et visuels.",
        "agent_type": AgentType.MARKETER,
        "requires": [5],
    },
    {
        "step": 8,
        "mission_type": "ad_creation",
        "title": "Creation des pubs",
        "description": "Cree 3-5 variantes de pubs avec headlines, body et descriptions visuelles.",
        "agent_type": AgentType.CONTENT,
        "requires": [7],
    },
    {
        "step": 9,
        "mission_type": "ads_launch_plan",
        "title": "Plan lancement ads",
        "description": "Planifie le lancement Meta Ads : budget, audiences, calendar et KPIs.",
        "agent_type": AgentType.MARKETER,
        "requires": [6, 8],
    },
    {
        "step": 10,
        "mission_type": "analytics_tracking",
        "title": "Analytics et tracking",
        "description": "Definis les events, KPIs et specs du dashboard de suivi.",
        "agent_type": AgentType.ORCHESTRATOR,
        "requires": [9],
    },
    {
        "step": 11,
        "mission_type": "support_setup",
        "title": "Support client",
        "description": "Prepare la FAQ, 10 templates de reponses et un workflow d'escalade.",
        "agent_type": AgentType.SUPPORT,
        "requires": [5],
    },
    {
        "step": 12,
        "mission_type": "optimization_audit",
        "title": "Optimisation continue",
        "description": "Audit et recommandations pour ameliorer site, ads et conversion.",
        "agent_type": AgentType.ORCHESTRATOR,
        "requires": [10],
    },
]

APP_CHAIN: list[dict] = [
    {
        "step": 1,
        "mission_type": "market_scan",
        "title": "Etude de marche",
        "description": "Analyse le marche des apps, les concurrents et les opportunites.",
        "agent_type": AgentType.RESEARCHER,
        "requires": [],
    },
    {
        "step": 2,
        "mission_type": "product_brief",
        "title": "Brief produit / specs",
        "description": "Definis les features cles, le MVP, les specs et l'experience utilisateur.",
        "agent_type": AgentType.BUILDER,
        "requires": [1],
    },
    {
        "step": 3,
        "mission_type": "brand_design",
        "title": "Design de marque",
        "description": "Cree ta charte graphique : palette, typo, icone app et mood board.",
        "agent_type": AgentType.CONTENT,
        "requires": [2],
    },
    {
        "step": 4,
        "mission_type": "landing_page",
        "title": "Landing / page store",
        "description": "Construis ta landing page et prepare les assets pour l'App Store.",
        "agent_type": AgentType.BUILDER,
        "requires": [2, 3],
    },
    {
        "step": 5,
        "mission_type": "aso_optimization",
        "title": "ASO / fiche store",
        "description": "Optimise ta fiche App Store : titre, sous-titre, keywords et screenshots.",
        "agent_type": AgentType.MARKETER,
        "requires": [4],
    },
    {
        "step": 6,
        "mission_type": "organic_content_strategy",
        "title": "Strategie contenu organique",
        "description": "Planifie ta strategie de contenu : TikTok, Instagram, blog et SEO.",
        "agent_type": AgentType.CONTENT,
        "requires": [4],
    },
    {
        "step": 7,
        "mission_type": "community_building",
        "title": "Community building",
        "description": "Cree et anime ta communaute : Discord, newsletter et ambassadeurs.",
        "agent_type": AgentType.OUTREACH,
        "requires": [5],
    },
    {
        "step": 8,
        "mission_type": "analytics_tracking",
        "title": "Analytics et tracking",
        "description": "Definis les events, funnels et KPIs pour mesurer la retention.",
        "agent_type": AgentType.ORCHESTRATOR,
        "requires": [6, 7],
    },
    {
        "step": 9,
        "mission_type": "support_setup",
        "title": "Support utilisateurs",
        "description": "Prepare le support : FAQ in-app, templates et workflow d'escalade.",
        "agent_type": AgentType.SUPPORT,
        "requires": [4],
    },
    {
        "step": 10,
        "mission_type": "growth_loop",
        "title": "Growth loop / optimisation",
        "description": "Cree des boucles de croissance : referral, viralite et retention.",
        "agent_type": AgentType.ORCHESTRATOR,
        "requires": [8],
    },
]

SAAS_CHAIN: list[dict] = [
    {
        "step": 1,
        "mission_type": "market_scan",
        "title": "Etude de marche",
        "description": "Analyse le marche SaaS, les concurrents et le positionnement.",
        "agent_type": AgentType.RESEARCHER,
        "requires": [],
    },
    {
        "step": 2,
        "mission_type": "product_brief",
        "title": "Brief produit / pricing",
        "description": "Definis le produit, les tiers de pricing et la proposition de valeur.",
        "agent_type": AgentType.BUILDER,
        "requires": [1],
    },
    {
        "step": 3,
        "mission_type": "brand_design",
        "title": "Design de marque",
        "description": "Cree ta charte graphique : palette, typo, logo et guidelines.",
        "agent_type": AgentType.CONTENT,
        "requires": [2],
    },
    {
        "step": 4,
        "mission_type": "landing_page",
        "title": "Landing page",
        "description": "Construis ta landing page avec pricing, features et social proof.",
        "agent_type": AgentType.BUILDER,
        "requires": [2, 3],
    },
    {
        "step": 5,
        "mission_type": "payment_setup",
        "title": "Paiements / pricing tiers",
        "description": "Configure Stripe avec les plans d'abonnement et la facturation.",
        "agent_type": AgentType.FINANCE,
        "requires": [4],
    },
    {
        "step": 6,
        "mission_type": "content_seo",
        "title": "Content marketing / SEO",
        "description": "Planifie ta strategie SEO : articles, pages piliers et mots-cles.",
        "agent_type": AgentType.CONTENT,
        "requires": [4],
    },
    {
        "step": 7,
        "mission_type": "cold_outbound",
        "title": "Outbound / cold email",
        "description": "Cree des sequences d'emails de prospection et identifie tes leads.",
        "agent_type": AgentType.OUTREACH,
        "requires": [4],
    },
    {
        "step": 8,
        "mission_type": "competitor_ads_analysis",
        "title": "Analyse concurrence ads",
        "description": "Analyse les pubs de tes concurrents SaaS : angles, canaux et budgets.",
        "agent_type": AgentType.MARKETER,
        "requires": [4],
    },
    {
        "step": 9,
        "mission_type": "ad_creation",
        "title": "Creation des pubs",
        "description": "Cree des variantes de pubs pour Google Ads et LinkedIn.",
        "agent_type": AgentType.CONTENT,
        "requires": [8],
    },
    {
        "step": 10,
        "mission_type": "analytics_tracking",
        "title": "Analytics et tracking",
        "description": "Definis les events, funnels de conversion et KPIs SaaS (MRR, churn).",
        "agent_type": AgentType.ORCHESTRATOR,
        "requires": [5, 6, 7],
    },
    {
        "step": 11,
        "mission_type": "optimization_audit",
        "title": "Optimisation continue",
        "description": "Audit complet : onboarding, conversion, retention et upsell.",
        "agent_type": AgentType.ORCHESTRATOR,
        "requires": [10],
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
    "builder": "Forge",
    "marketer": "Agence",
    "researcher": "Observatoire",
    "orchestrator": "QG",
    "outreach": "Poste",
    "support": "Auberge",
    "finance": "Banque",
    "content": "Atelier",
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
