from app.models.entities import AgentType
from app.schemas.api import MissionCatalogItem

MISSION_CATALOG: dict[str, MissionCatalogItem] = {
    # --- Forge (Builder) ---
    "landing_page": MissionCatalogItem(
        mission_type="landing_page",
        agent_type=AgentType.BUILDER,
        title="Forger la landing",
        description="Page HTML + copy hero pour ta company.",
        credits_cost=15,
        estimated_minutes=8,
        output_format="html",
        complexity=5,
        max_images=5,
        max_context_tokens=6000,
    ),
    "product_brief": MissionCatalogItem(
        mission_type="product_brief",
        agent_type=AgentType.BUILDER,
        title="Brief produit",
        description="PRD leger en 5 sections.",
        credits_cost=12,
        estimated_minutes=5,
        output_format="markdown",
        complexity=3,
        max_context_tokens=4000,
    ),
    # --- Marche (Marketer) ---
    "ad_copy_pack": MissionCatalogItem(
        mission_type="ad_copy_pack",
        agent_type=AgentType.MARKETER,
        title="Pack Meta Ads",
        description="3 headlines x 3 descriptions pour Meta.",
        credits_cost=20,
        estimated_minutes=7,
        output_format="json",
        complexity=3,
        max_images=3,
    ),
    "social_batch": MissionCatalogItem(
        mission_type="social_batch",
        agent_type=AgentType.MARKETER,
        title="Batch social",
        description="5 posts prets a publier.",
        credits_cost=15,
        estimated_minutes=4,
        output_format="markdown",
        complexity=2,
    ),
    # --- Labo (Researcher) ---
    "market_scan": MissionCatalogItem(
        mission_type="market_scan",
        agent_type=AgentType.RESEARCHER,
        title="Scan marche",
        description="Concurrents, gaps, signaux TAM.",
        credits_cost=10,
        estimated_minutes=6,
        output_format="markdown",
        complexity=4,
        max_context_tokens=6000,
    ),
    "idea_storm": MissionCatalogItem(
        mission_type="idea_storm",
        agent_type=AgentType.RESEARCHER,
        title="Tempete d'idees",
        description="10 hooks produit + cible.",
        credits_cost=8,
        estimated_minutes=3,
        output_format="markdown",
        complexity=2,
        max_context_tokens=2000,
    ),
    # --- QG (Orchestrator) ---
    "ceo_next_move": MissionCatalogItem(
        mission_type="ceo_next_move",
        agent_type=AgentType.ORCHESTRATOR,
        title="Next Move CEO",
        description="Analyse le livrable et decide la prochaine action strategique.",
        credits_cost=0,
        estimated_minutes=1,
        output_format="markdown",
        complexity=1,
        max_tool_iterations=0,
        max_context_tokens=3000,
    ),
    "morning_plan": MissionCatalogItem(
        mission_type="morning_plan",
        agent_type=AgentType.ORCHESTRATOR,
        title="Plan du matin",
        description="Priorites, KPIs et recommandations pour la journee.",
        credits_cost=5,
        estimated_minutes=3,
        output_format="markdown",
        complexity=1,
        max_context_tokens=2000,
    ),
    "evening_summary": MissionCatalogItem(
        mission_type="evening_summary",
        agent_type=AgentType.ORCHESTRATOR,
        title="Resume du soir",
        description="Bilan de la journee et plan pour demain.",
        credits_cost=5,
        estimated_minutes=3,
        output_format="markdown",
        complexity=1,
        max_context_tokens=2000,
    ),
    # --- Bureau de Poste (Outreach) ---
    "cold_email_sequence": MissionCatalogItem(
        mission_type="cold_email_sequence",
        agent_type=AgentType.OUTREACH,
        title="Sequence cold email",
        description="3 emails de prospection personnalises.",
        credits_cost=12,
        estimated_minutes=5,
        output_format="markdown",
        complexity=3,
    ),
    "prospect_report": MissionCatalogItem(
        mission_type="prospect_report",
        agent_type=AgentType.OUTREACH,
        title="Rapport prospection",
        description="25 prospects qualifies avec scoring.",
        credits_cost=15,
        estimated_minutes=7,
        output_format="markdown",
        complexity=4,
    ),
    # --- Auberge (Support) ---
    "inbox_review": MissionCatalogItem(
        mission_type="inbox_review",
        agent_type=AgentType.SUPPORT,
        title="Revue inbox",
        description="Trier et repondre aux messages clients.",
        credits_cost=8,
        estimated_minutes=4,
        output_format="markdown",
        complexity=2,
    ),
    "support_templates": MissionCatalogItem(
        mission_type="support_templates",
        agent_type=AgentType.SUPPORT,
        title="Templates support",
        description="Reponses types par categorie de demande.",
        credits_cost=10,
        estimated_minutes=5,
        output_format="markdown",
        complexity=3,
    ),
    # --- Banque (Finance) ---
    "revenue_report": MissionCatalogItem(
        mission_type="revenue_report",
        agent_type=AgentType.FINANCE,
        title="Rapport revenus",
        description="MRR, churn, LTV et analyse mensuelle.",
        credits_cost=10,
        estimated_minutes=5,
        output_format="markdown",
        complexity=3,
    ),
    "budget_tracking": MissionCatalogItem(
        mission_type="budget_tracking",
        agent_type=AgentType.FINANCE,
        title="Suivi budget",
        description="Depenses, alertes et projections.",
        credits_cost=8,
        estimated_minutes=4,
        output_format="markdown",
        complexity=2,
    ),
    # --- Atelier (Content) ---
    "blog_article": MissionCatalogItem(
        mission_type="blog_article",
        agent_type=AgentType.CONTENT,
        title="Article de blog",
        description="Article SEO-friendly de 500-1000 mots.",
        credits_cost=15,
        estimated_minutes=8,
        output_format="markdown",
        complexity=4,
    ),
    "image_brief": MissionCatalogItem(
        mission_type="image_brief",
        agent_type=AgentType.CONTENT,
        title="Brief visuel",
        description="Brief pour hero image, icones et bannieres.",
        credits_cost=10,
        estimated_minutes=4,
        output_format="markdown",
        complexity=2,
        max_images=10,
    ),
    # --- Quest Chain ---
    "supplier_sourcing": MissionCatalogItem(
        mission_type="supplier_sourcing",
        agent_type=AgentType.RESEARCHER,
        title="Recherche fournisseur",
        description="Trouve 3-5 fournisseurs (AliExpress/Alibaba) avec prix, MOQ et delais.",
        credits_cost=12,
        estimated_minutes=6,
        output_format="markdown",
        complexity=4,
    ),
    "brand_design": MissionCatalogItem(
        mission_type="brand_design",
        agent_type=AgentType.CONTENT,
        title="Design de marque",
        description="Charte graphique : palette, typo, ton et mood board.",
        credits_cost=15,
        estimated_minutes=7,
        output_format="markdown",
        complexity=4,
        max_images=5,
    ),
    "payment_setup": MissionCatalogItem(
        mission_type="payment_setup",
        agent_type=AgentType.FINANCE,
        title="Setup paiements",
        description="Guide integration Stripe : checklist, config et webhooks.",
        credits_cost=10,
        estimated_minutes=5,
        output_format="markdown",
        complexity=3,
    ),
    "competitor_ads_analysis": MissionCatalogItem(
        mission_type="competitor_ads_analysis",
        agent_type=AgentType.MARKETER,
        title="Analyse pubs concurrents",
        description="Top 5 pubs concurrentes, budgets estimes, angles et visuels.",
        credits_cost=15,
        estimated_minutes=7,
        output_format="markdown",
        complexity=4,
    ),
    "ad_creation": MissionCatalogItem(
        mission_type="ad_creation",
        agent_type=AgentType.CONTENT,
        title="Creation des pubs",
        description="3-5 variantes de pubs avec headline, body, CTA et description image.",
        credits_cost=18,
        estimated_minutes=8,
        output_format="markdown",
        complexity=4,
        max_images=10,
    ),
    "ads_launch_plan": MissionCatalogItem(
        mission_type="ads_launch_plan",
        agent_type=AgentType.MARKETER,
        title="Plan lancement ads",
        description="Plan media : budget quotidien, audiences cibles, calendar et KPIs.",
        credits_cost=15,
        estimated_minutes=6,
        output_format="markdown",
        complexity=4,
    ),
    "analytics_tracking": MissionCatalogItem(
        mission_type="analytics_tracking",
        agent_type=AgentType.ORCHESTRATOR,
        title="Analytics et tracking",
        description="Plan de tracking : events, KPIs et specs du dashboard.",
        credits_cost=10,
        estimated_minutes=5,
        output_format="markdown",
        complexity=3,
    ),
    "support_setup": MissionCatalogItem(
        mission_type="support_setup",
        agent_type=AgentType.SUPPORT,
        title="Support client",
        description="FAQ + 10 templates de reponses + workflow escalade.",
        credits_cost=12,
        estimated_minutes=6,
        output_format="markdown",
        complexity=3,
    ),
    "optimization_audit": MissionCatalogItem(
        mission_type="optimization_audit",
        agent_type=AgentType.ORCHESTRATOR,
        title="Optimisation continue",
        description="Audit complet : recommandations site, ads et conversion.",
        credits_cost=15,
        estimated_minutes=7,
        output_format="markdown",
        complexity=5,
        max_context_tokens=6000,
    ),
    # --- App-specific ---
    "aso_optimization": MissionCatalogItem(
        mission_type="aso_optimization",
        agent_type=AgentType.MARKETER,
        title="ASO / fiche store",
        description="Optimise ta fiche App Store : titre, sous-titre, keywords et screenshots.",
        credits_cost=12,
        estimated_minutes=6,
        output_format="markdown",
        complexity=4,
    ),
    "organic_content_strategy": MissionCatalogItem(
        mission_type="organic_content_strategy",
        agent_type=AgentType.CONTENT,
        title="Strategie contenu organique",
        description="Plan de contenu organique : TikTok, Instagram, blog et calendrier editorial.",
        credits_cost=15,
        estimated_minutes=7,
        output_format="markdown",
        complexity=4,
    ),
    "community_building": MissionCatalogItem(
        mission_type="community_building",
        agent_type=AgentType.OUTREACH,
        title="Community building",
        description="Plan communaute : Discord, newsletter, ambassadeurs et engagement.",
        credits_cost=12,
        estimated_minutes=6,
        output_format="markdown",
        complexity=3,
    ),
    "growth_loop": MissionCatalogItem(
        mission_type="growth_loop",
        agent_type=AgentType.ORCHESTRATOR,
        title="Growth loop",
        description="Boucles de croissance : referral, viralite, retention et metriques.",
        credits_cost=15,
        estimated_minutes=7,
        output_format="markdown",
        complexity=5,
        max_context_tokens=6000,
    ),
    # --- SaaS-specific ---
    "content_seo": MissionCatalogItem(
        mission_type="content_seo",
        agent_type=AgentType.CONTENT,
        title="Content marketing / SEO",
        description="Strategie SEO : articles piliers, mots-cles cibles et calendrier.",
        credits_cost=15,
        estimated_minutes=7,
        output_format="markdown",
        complexity=4,
    ),
    "cold_outbound": MissionCatalogItem(
        mission_type="cold_outbound",
        agent_type=AgentType.OUTREACH,
        title="Outbound / cold email",
        description="Sequences de prospection, identification de leads et scoring.",
        credits_cost=12,
        estimated_minutes=6,
        output_format="markdown",
        complexity=3,
    ),
}


MISSION_DECOMPOSITION: dict[str, list[str]] = {
    "optimization_audit": ["market_scan", "competitor_ads_analysis", "analytics_tracking"],
    "growth_loop": ["market_scan", "organic_content_strategy", "community_building"],
    "landing_page": ["product_brief", "brand_design"],
    "ads_launch_plan": ["competitor_ads_analysis", "ad_copy_pack", "ad_creation"],
    "content_seo": ["market_scan", "blog_article"],
    "cold_outbound": ["prospect_report", "cold_email_sequence"],
}


def get_catalog_for_agent(agent_type: AgentType) -> list[MissionCatalogItem]:
    return [item for item in MISSION_CATALOG.values() if item.agent_type == agent_type]


def get_suggested_split(mission_type: str) -> list[dict]:
    """Return recommended sub-missions for a complex mission."""
    sub_types = MISSION_DECOMPOSITION.get(mission_type, [])
    return [
        {
            "mission_type": mt,
            "title": MISSION_CATALOG[mt].title,
            "credits_cost": MISSION_CATALOG[mt].credits_cost,
            "complexity": MISSION_CATALOG[mt].complexity,
        }
        for mt in sub_types
        if mt in MISSION_CATALOG
    ]


# ---------------------------------------------------------------------------
# P1 — Dynamic routing: find_agent_for_task()
# Polsia-style: given a task description/tag, return the best AgentType.
# Phase 1: static keyword routing (fast, no LLM cost).
# Phase 2 (future): LLM routing for ambiguous tasks.
# ---------------------------------------------------------------------------

_TAG_TO_AGENT: dict[str, AgentType] = {
    # Engineering / infra / code
    "engineering": AgentType.BUILDER,
    "code": AgentType.BUILDER,
    "deploy": AgentType.BUILDER,
    "infra": AgentType.BUILDER,
    "landing": AgentType.BUILDER,
    "page": AgentType.BUILDER,
    "build": AgentType.BUILDER,
    # Research / intel
    "research": AgentType.RESEARCHER,
    "market": AgentType.RESEARCHER,
    "competitor": AgentType.RESEARCHER,
    "sourcing": AgentType.RESEARCHER,
    "supplier": AgentType.RESEARCHER,
    "data": AgentType.RESEARCHER,
    # Marketing / ads
    "ads": AgentType.MARKETER,
    "meta_ads": AgentType.MARKETER,
    "advertising": AgentType.MARKETER,
    "paid": AgentType.MARKETER,
    "launch": AgentType.MARKETER,
    "aso": AgentType.MARKETER,
    # Content / creation
    "content": AgentType.CONTENT,
    "brand": AgentType.CONTENT,
    "design": AgentType.CONTENT,
    "social": AgentType.CONTENT,
    "image": AgentType.CONTENT,
    "organic": AgentType.CONTENT,
    # Outreach / community
    "outreach": AgentType.OUTREACH,
    "community": AgentType.OUTREACH,
    "email": AgentType.OUTREACH,
    "cold": AgentType.OUTREACH,
    # Support
    "support": AgentType.SUPPORT,
    "inbox": AgentType.SUPPORT,
    "ticket": AgentType.SUPPORT,
    # Finance
    "finance": AgentType.FINANCE,
    "payment": AgentType.FINANCE,
    "stripe": AgentType.FINANCE,
    "revenue": AgentType.FINANCE,
    # Orchestration / strategy
    "orchestrator": AgentType.ORCHESTRATOR,
    "strategy": AgentType.ORCHESTRATOR,
    "analytics": AgentType.ORCHESTRATOR,
    "audit": AgentType.ORCHESTRATOR,
    "growth": AgentType.ORCHESTRATOR,
    "ceo": AgentType.ORCHESTRATOR,
}


def find_agent_for_task(
    task_tag: str = "",
    mission_type: str = "",
) -> AgentType:
    """Return the best AgentType for a given task.

    Priority:
    1. Exact match in MISSION_CATALOG (mission_type → agent_type)
    2. Keyword match in _TAG_TO_AGENT (task_tag → agent_type)
    3. Fallback: ORCHESTRATOR

    Usage:
        agent = find_agent_for_task(task_tag="meta_ads")      # → MARKETER
        agent = find_agent_for_task(mission_type="landing_page")  # → BUILDER
    """
    # 1. Catalog exact match
    if mission_type and mission_type in MISSION_CATALOG:
        return MISSION_CATALOG[mission_type].agent_type

    # 2. Keyword match (longest match wins)
    tag = (task_tag or mission_type or "").lower().replace("-", "_").replace(" ", "_")
    best: AgentType | None = None
    best_len = 0
    for keyword, agent_type in _TAG_TO_AGENT.items():
        if keyword in tag and len(keyword) > best_len:
            best = agent_type
            best_len = len(keyword)
    if best:
        return best

    # 3. Fallback
    return AgentType.ORCHESTRATOR
