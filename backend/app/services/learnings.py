"""Service for cross-company learnings — avoids redundant re-research.

When an agent discovers a useful insight (e.g. a competitor's pricing), it
is stored as a Learning.  Future agents in the same industry can query
existing learnings before scraping again, saving tokens + compute.
"""
from __future__ import annotations

import json
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Learning

logger = structlog.get_logger()


class LearningsService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(
        self,
        content: str,
        source_company_id: str | None = None,
        industry: str | None = None,
        tags: list[str] | None = None,
    ) -> Learning:
        learning = Learning(
            content=content,
            source_company_id=source_company_id,
            industry=industry,
            tags=json.dumps(tags) if tags else None,
        )
        self._db.add(learning)
        await self._db.commit()
        await self._db.refresh(learning)
        logger.info("learning_created", id=learning.id, industry=industry, tags=tags)
        return learning

    async def query(
        self,
        query: str,
        industry: str | None = None,
        limit: int = 10,
    ) -> list[Learning]:
        """Search learnings by keyword match and optional industry filter."""
        stmt = select(Learning)
        if industry:
            stmt = stmt.where(Learning.industry == industry)

        stmt = stmt.where(Learning.content.ilike(f"%{query}%"))
        stmt = stmt.order_by(Learning.created_at.desc()).limit(limit)

        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def search_by_tags(
        self,
        tags: list[str],
        limit: int = 10,
    ) -> list[Learning]:
        """Search learnings by tag match (stored as JSON array in text)."""
        stmt = select(Learning).order_by(Learning.created_at.desc())
        results = []
        result = await self._db.execute(stmt.limit(100))
        for learning in result.scalars().all():
            if learning.tags:
                try:
                    stored_tags = json.loads(learning.tags)
                    if any(t in stored_tags for t in tags):
                        results.append(learning)
                        if len(results) >= limit:
                            break
                except json.JSONDecodeError:
                    continue
        return results

    async def get_for_industry(
        self, industry: str, limit: int = 20
    ) -> list[Learning]:
        stmt = (
            select(Learning)
            .where(Learning.industry == industry)
            .order_by(Learning.created_at.desc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
