"""Polsia-like task routing — find_best_agent() heuristic.

Maps a free-form task title/description to the most appropriate AgentType.
Priority: explicit agent_type > keyword match > ORCHESTRATOR fallback.
"""
from __future__ import annotations

from app.models.entities import AgentType

# ---------------------------------------------------------------------------
# Keyword → AgentType mapping (order matters — first match wins)
# ---------------------------------------------------------------------------

_KEYWORD_MAP: list[tuple[list[str], AgentType]] = [
    # Meta Ads / paid marketing
    (
        [
            "meta ads", "facebook ads", "instagram ads", "ad creative", "video ad",
            "campagne pub", "campagne meta", "ads manager", "daily ads",
            "budget ads", "ctr", "roas", "creative", "publicité", "meta campaign",
            "ad delivery", "ads diagnostic", "pixel events", "audit ads",
        ],
        AgentType.MARKETER,
    ),
    # Browser automation / web scraping (before BUILDER — "automate" is specific)
    (
        [
            "click", "navigate", "scrape", "automate", "fill form",
            "automation web", "browser", "test ux", "selenium", "playwright",
            "screenshot", "web automation", "clique sur", "ouvre le site",
        ],
        AgentType.BROWSER,
    ),
    # Ops / infrastructure / deployment (before BUILDER — cloudflare/vercel/docker are specific)
    (
        [
            "ops", "deployment", "server", "hosting", "cloudflare", "render.com",
            "vercel", "heroku", "kubernetes", "docker", "ssl", "nginx",
            "load balancer", "monitoring", "uptime", "configure", "infrastructure ops",
        ],
        AgentType.OPS,
    ),
    # Engineering / code / infra
    (
        [
            "code", "bug", "fix", "feature", "engineering", "landing page",
            "deploy", "dns", "infrastructure", "database", "api",
            "pixel", "stripe", "webhook", "backend", "frontend",
            "install", "setup", "integration", "développement", "refactor",
            "migration", "schema", "endpoint", "route", "build",
        ],
        AgentType.BUILDER,
    ),
    # Research / competitive intelligence
    (
        [
            "research", "competitor", "analyse concurrentielle", "market",
            "survey", "benchmark", "sourcing", "fournisseur", "idea storm",
            "tendance", "trend", "industry", "étude", "veille", "web search",
            "find information", "lookup", "investigate",
        ],
        AgentType.RESEARCHER,
    ),
    # Growth / acquisition / virality
    (
        [
            "growth", "acquisition", "go-to-market", "gtm", "audience",
            "viral", "referral", "seo", "aso", "croissance", "k-factor",
            "funnel", "onboarding", "activation", "retention", "churn",
            "product-led", "growth hack",
        ],
        AgentType.GROWTH,
    ),
    # Data / analytics / SQL
    (
        [
            "analytics", "data", "sql", "rapport", "report", "dashboard",
            "kpi", "metrics", "analyse données", "query", "cohort",
            "conversion rate", "data analysis", "statistics", "tableau",
        ],
        AgentType.DATA,
    ),
    # Outreach / cold email / prospecting
    (
        [
            "email", "cold outreach", "prospect", "lead", "outbound",
            "community", "linkedin", "contact", "relance", "séquence",
            "cold email", "drip campaign", "follow up",
        ],
        AgentType.OUTREACH,
    ),
    # Support / customer service
    (
        [
            "support", "ticket", "customer", "client", "inbox", "email support",
            "réponse client", "service client", "user complaint", "faq",
        ],
        AgentType.SUPPORT,
    ),
    # Finance / billing
    (
        [
            "revenue", "finance", "budget", "facturation", "invoice",
            "rapport financier", "p&l", "chiffre d'affaires", "billing",
            "payment", "cashflow", "expense",
        ],
        AgentType.FINANCE,
    ),
    # Content / copywriting
    (
        [
            "blog", "article", "content", "copywriting", "newsletter",
            "social media", "post", "caption", "brand", "design",
            "rédaction", "contenu", "texte", "twitter", "tiktok",
            "instagram caption", "copy", "script vidéo",
        ],
        AgentType.CONTENT,
    ),
    # CEO / strategy / planning (fallback before pure orchestrator)
    (
        [
            "plan", "stratégie", "strategy", "next step", "roadmap",
            "audit", "optimization", "morning plan", "evening summary",
            "what should i do", "prioritize", "priorité",
        ],
        AgentType.ORCHESTRATOR,
    ),
]


def find_best_agent(title: str, description: str = "") -> AgentType:
    """Return the best AgentType for the given task title + description."""
    text = (title + " " + description).lower()

    for keywords, agent_type in _KEYWORD_MAP:
        if any(kw in text for kw in keywords):
            return agent_type

    return AgentType.ORCHESTRATOR


def agent_type_from_string(value: str) -> AgentType | None:
    """Parse an agent type string to AgentType enum, return None if invalid."""
    try:
        return AgentType(value.lower())
    except ValueError:
        return None


def mission_type_for_freeform(agent_type: AgentType) -> str:
    """Return the default mission_type string for freeform tasks by agent."""
    _defaults = {
        AgentType.BUILDER: "landing_page",
        AgentType.MARKETER: "ads_launch_plan",
        AgentType.RESEARCHER: "market_scan",
        AgentType.ORCHESTRATOR: "ceo_next_move",
        AgentType.OUTREACH: "cold_email_sequence",
        AgentType.SUPPORT: "inbox_review",
        AgentType.FINANCE: "revenue_report",
        AgentType.CONTENT: "blog_article",
        AgentType.BROWSER: "ceo_next_move",
        AgentType.DATA: "market_scan",
        AgentType.OPS: "landing_page",
        AgentType.GROWTH: "ads_launch_plan",
    }
    return _defaults.get(agent_type, "ceo_next_move")
