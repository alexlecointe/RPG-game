"""Skill Shop catalog — defines available expert skills for purchase.

On app startup, these items are synced to the skill_shop_items table.
"""
from __future__ import annotations

EXPERT_SKILLS: list[dict] = [
    {
        "mission_type": "landing_page",
        "title": "Landing Page Expert — AIDA Framework",
        "description": (
            "Transforme ton agent Builder en expert copywriting. "
            "Utilise le framework AIDA pour structurer la page, "
            "avec des exemples de headlines, des regles de responsive design, "
            "et les erreurs classiques a eviter."
        ),
        "credits_cost": 60,
        "icon": "🏗️",
        "preview_benefits": (
            "Framework AIDA integre|"
            "Copywriting formulas (headline, CTA)|"
            "Regles responsive mobile-first|"
            "Anti-patterns a eviter|"
            "Exemple de sortie HTML"
        ),
    },
    {
        "mission_type": "market_scan",
        "title": "Etude de Marche Expert — Porter + JTBD",
        "description": (
            "Analyse de marche de niveau consultant. "
            "5 Forces de Porter, methodologie TAM/SAM/SOM, "
            "Jobs to Be Done, et recommandation strategique actionnable."
        ),
        "credits_cost": 50,
        "icon": "🔬",
        "preview_benefits": (
            "Porter's 5 Forces|"
            "TAM/SAM/SOM avec methode|"
            "Jobs to Be Done (3 jobs)|"
            "5+ concurrents analyses en profondeur|"
            "Recommandation strategique"
        ),
    },
    {
        "mission_type": "ad_creation",
        "title": "Creation Pub Expert — AIDA + PAS",
        "description": (
            "Creatives publicitaires multi-plateforme de qualite agence. "
            "3 angles obligatoires (douleur, benefice, preuve sociale), "
            "specs exactes Meta/TikTok/Google, plan de test A/B."
        ),
        "credits_cost": 55,
        "icon": "🎯",
        "preview_benefits": (
            "Frameworks AIDA + PAS|"
            "3 angles creatifs par campagne|"
            "Specs Meta + TikTok + Google|"
            "Plan de test A/B|"
            "Visual direction par creative"
        ),
    },
    {
        "mission_type": "aso_optimization",
        "title": "ASO Expert — Scoring 6 dimensions",
        "description": (
            "Optimisation App Store de niveau professionnel. "
            "Scoring ASO sur 100 (6 dimensions ponderees), "
            "formule de priorite keywords, strategie screenshots, "
            "et checklist pre-soumission complete."
        ),
        "credits_cost": 55,
        "icon": "📱",
        "preview_benefits": (
            "Scoring ASO sur 100 (6 dimensions)|"
            "Formule priorite keywords|"
            "Strategie screenshots et video|"
            "Optimisation ratings et reviews|"
            "Checklist pre-soumission 15 points"
        ),
    },
    {
        "mission_type": "growth_loop",
        "title": "Growth Expert — AARRR + Hook + STEPPS",
        "description": (
            "Strategie de croissance inspiree des meilleures startups. "
            "Diagnostic de stade, framework AARRR complet, "
            "Hook Model pour la retention, K-factor et programme de referral."
        ),
        "credits_cost": 65,
        "icon": "🚀",
        "preview_benefits": (
            "Diagnostic stade produit|"
            "AARRR Pirate Metrics|"
            "Hook Model (retention)|"
            "K-factor + STEPPS (viralite)|"
            "Programme referral avec benchmarks"
        ),
    },
]


async def sync_shop_catalog() -> None:
    """Upsert shop catalog items into the database.

    Called during app startup. Matches on mission_type to avoid duplicates.
    """
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.entities import SkillShopItem, SkillTier

    async with SessionLocal() as session:
        for item_data in EXPERT_SKILLS:
            result = await session.execute(
                select(SkillShopItem).where(
                    SkillShopItem.mission_type == item_data["mission_type"],
                    SkillShopItem.tier == SkillTier.EXPERT,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.title = item_data["title"]
                existing.description = item_data["description"]
                existing.credits_cost = item_data["credits_cost"]
                existing.icon = item_data["icon"]
                existing.preview_benefits = item_data.get("preview_benefits")
            else:
                session.add(SkillShopItem(
                    mission_type=item_data["mission_type"],
                    tier=SkillTier.EXPERT,
                    title=item_data["title"],
                    description=item_data["description"],
                    credits_cost=item_data["credits_cost"],
                    icon=item_data["icon"],
                    preview_benefits=item_data.get("preview_benefits"),
                ))

        await session.commit()
