from __future__ import annotations

from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import CompanyMemory, MemoryCategory

logger = structlog.get_logger()

MAX_MEMORY_CONTENT_SIZE = 1500
DEFAULT_CONTEXT_TOKEN_BUDGET = 4000


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def _truncate_content(content: str, max_chars: int = MAX_MEMORY_CONTENT_SIZE) -> str:
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "\n[... tronque ...]"

MEMORY_RELEVANCE: dict[str, list[str]] = {
    "market_scan": ["profile"],
    "product_brief": ["profile", "market"],
    "brand_design": ["profile", "market", "product"],
    "landing_page": ["profile", "market", "product", "brand"],
    "ad_copy_pack": ["profile", "market", "brand", "product"],
    "supplier_sourcing": ["profile", "market", "product"],
    "competitor_ads_analysis": ["profile", "market", "competitors"],
    "ad_creation": ["profile", "brand", "product", "market"],
    "ads_launch_plan": ["profile", "brand", "product", "market", "competitors"],
    "analytics_tracking": ["profile", "product", "strategy"],
    "support_setup": ["profile", "product"],
    "optimization_audit": ["profile", "market", "product", "analytics", "strategy"],
    "aso_optimization": ["profile", "product", "market", "competitors"],
    "organic_content_strategy": ["profile", "brand", "product", "market"],
    "community_building": ["profile", "brand", "product"],
    "growth_loop": ["profile", "product", "market", "analytics"],
    "content_seo": ["profile", "product", "market", "brand"],
    "cold_outbound": ["profile", "product", "market", "competitors"],
    "payment_setup": ["profile", "product", "strategy"],
    "cold_email_sequence": ["profile", "product", "market"],
    "blog_article": ["profile", "product", "brand", "market"],
    "social_batch": ["profile", "brand", "product"],
    "prospect_report": ["profile", "product", "market"],
    "image_brief": ["profile", "brand", "product"],
}

MISSION_TO_MEMORY: dict[str, tuple[str, str]] = {
    "market_scan": ("market", "market_research"),
    "product_brief": ("product", "product_brief"),
    "brand_design": ("brand", "brand_guidelines"),
    "landing_page": ("product", "landing_page"),
    "ad_copy_pack": ("strategy", "ad_copies"),
    "supplier_sourcing": ("product", "supplier_research"),
    "competitor_ads_analysis": ("competitors", "ads_analysis"),
    "aso_optimization": ("strategy", "aso_strategy"),
    "organic_content_strategy": ("strategy", "content_strategy"),
    "community_building": ("strategy", "community_plan"),
    "growth_loop": ("strategy", "growth_loops"),
    "content_seo": ("strategy", "seo_content"),
    "cold_outbound": ("strategy", "outbound_sequences"),
    "payment_setup": ("product", "payment_config"),
    "analytics_tracking": ("analytics", "tracking_plan"),
    "optimization_audit": ("analytics", "optimization_report"),
    "cold_email_sequence": ("strategy", "email_sequences"),
    "prospect_report": ("market", "prospect_report"),
    "blog_article": ("strategy", "blog_content"),
    "support_setup": ("product", "support_config"),
}


class MemoryService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def store(
        self,
        company_id: str,
        category: str,
        key: str,
        content: str,
        source_mission_id: Optional[str] = None,
        max_chars: int = MAX_MEMORY_CONTENT_SIZE,
    ) -> CompanyMemory:
        """Upsert a memory entry by (company_id, category, key).

        Content is automatically truncated to MAX_MEMORY_CONTENT_SIZE to
        prevent context window bloat on re-injection.
        """
        compacted = _truncate_content(content, max_chars=max_chars)
        cat = MemoryCategory(category)
        result = await self._db.execute(
            select(CompanyMemory).where(
                CompanyMemory.company_id == company_id,
                CompanyMemory.category == cat,
                CompanyMemory.key == key,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.content = compacted
            existing.source_mission_id = source_mission_id
            await self._db.commit()
            await self._db.refresh(existing)
            logger.info("memory_updated", company_id=company_id, category=category, key=key)
            return existing

        mem = CompanyMemory(
            company_id=company_id,
            category=cat,
            key=key,
            content=compacted,
            source_mission_id=source_mission_id,
        )
        self._db.add(mem)
        await self._db.commit()
        await self._db.refresh(mem)
        logger.info("memory_stored", company_id=company_id, category=category, key=key)
        return mem

    async def get(
        self, company_id: str, category: str, key: str
    ) -> Optional[CompanyMemory]:
        cat = MemoryCategory(category)
        result = await self._db.execute(
            select(CompanyMemory).where(
                CompanyMemory.company_id == company_id,
                CompanyMemory.category == cat,
                CompanyMemory.key == key,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_categories(
        self, company_id: str, categories: list[str]
    ) -> list[CompanyMemory]:
        cats = [MemoryCategory(c) for c in categories]
        result = await self._db.execute(
            select(CompanyMemory)
            .where(
                CompanyMemory.company_id == company_id,
                CompanyMemory.category.in_(cats),
            )
            .order_by(CompanyMemory.category, CompanyMemory.updated_at.desc())
        )
        return list(result.scalars().all())

    async def build_agent_context(
        self,
        company_id: str,
        mission_type: str,
        industry: str | None = None,
        max_tokens: int = DEFAULT_CONTEXT_TOKEN_BUDGET,
    ) -> list[dict]:
        """Build structured memory context bounded by a token budget.

        Nodes are sorted by relevance (category priority in MEMORY_RELEVANCE)
        and truncated to MAX_MEMORY_CONTENT_SIZE each. Injection stops when
        the token budget is reached — Polsia pattern: bounded nodes, not
        raw text truncation.
        """
        relevant_cats = MEMORY_RELEVANCE.get(mission_type, [])
        context: list[dict] = []
        tokens_used = 0

        if relevant_cats:
            memories = await self.get_by_categories(company_id, relevant_cats)
            for mem in memories:
                truncated = _truncate_content(mem.content)
                node_tokens = _estimate_tokens(truncated)
                if tokens_used + node_tokens > max_tokens:
                    break
                context.append({
                    "category": mem.category.value,
                    "key": mem.key,
                    "content": truncated,
                })
                tokens_used += node_tokens

        if industry and tokens_used < max_tokens:
            from app.services.learnings import LearningsService
            learnings_svc = LearningsService(self._db)
            learnings = await learnings_svc.get_for_industry(industry, limit=5)
            for learning in learnings:
                truncated = _truncate_content(learning.content, 1000)
                node_tokens = _estimate_tokens(truncated)
                if tokens_used + node_tokens > max_tokens:
                    break
                context.append({
                    "category": "learning",
                    "key": f"industry_insight_{learning.id[:8]}",
                    "content": truncated,
                })
                tokens_used += node_tokens

        logger.debug(
            "context_built",
            mission_type=mission_type,
            nodes=len(context),
            tokens_estimated=tokens_used,
            budget=max_tokens,
        )
        return context

    async def extract_and_store_memory(
        self,
        company_id: str,
        mission_type: str,
        deliverable: str,
        source_mission_id: Optional[str] = None,
        industry: str | None = None,
    ) -> None:
        """Extract and store memory from a completed mission's deliverable.

        Also extracts generic insights into the global Learnings table
        for cross-company knowledge sharing.
        """
        mapping = MISSION_TO_MEMORY.get(mission_type)
        if not mapping:
            logger.debug("no_memory_mapping", mission_type=mission_type)
            return

        category, key = mapping
        await self.store(company_id, category, key, deliverable, source_mission_id)
        logger.info(
            "memory_extracted",
            company_id=company_id,
            mission_type=mission_type,
            category=category,
            key=key,
        )

        LEARNING_MISSIONS = {
            "market_scan", "competitor_ads_analysis", "aso_optimization",
            "organic_content_strategy", "growth_loop", "content_seo",
            "prospect_report", "supplier_sourcing",
        }
        if mission_type in LEARNING_MISSIONS and len(deliverable) > 200:
            from app.services.learnings import LearningsService
            learnings_svc = LearningsService(self._db)
            summary = _truncate_content(deliverable)
            await learnings_svc.create(
                content=summary,
                source_company_id=company_id,
                industry=industry,
                tags=[mission_type, category],
            )
            logger.info(
                "learning_extracted",
                company_id=company_id,
                mission_type=mission_type,
                industry=industry,
            )
