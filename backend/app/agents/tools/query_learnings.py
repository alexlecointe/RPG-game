"""Tool: query_learnings — Search cross-company insights before re-researching.

Agents can check if a topic has already been researched by another company,
avoiding redundant scraping and LLM calls.
"""
from __future__ import annotations

import json

from app.agents.tools import ToolDefinition

QUERY_LEARNINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Keyword or topic to search in existing learnings.",
        },
        "industry": {
            "type": "string",
            "description": "Optional industry filter (e.g. 'ecommerce', 'saas', 'app').",
        },
    },
    "required": ["query"],
}


async def _execute_query_learnings(query: str, industry: str = "") -> str:
    from app.core.database import SessionLocal
    from app.services.learnings import LearningsService

    async with SessionLocal() as db:
        svc = LearningsService(db)
        learnings = await svc.query(query, industry=industry or None, limit=5)

    if not learnings:
        return json.dumps({
            "found": False,
            "message": "No existing learnings found for this query. You should research this topic.",
        })

    return json.dumps({
        "found": True,
        "count": len(learnings),
        "learnings": [
            {
                "content": l.content[:500],
                "industry": l.industry,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in learnings
        ],
    })


def create_query_learnings_tool() -> ToolDefinition:
    async def execute(query: str, industry: str = "") -> str:
        return await _execute_query_learnings(query, industry)

    return ToolDefinition(
        name="query_learnings",
        description=(
            "Search existing cross-company learnings/insights before re-researching a topic. "
            "If relevant learnings exist, use them instead of scraping again. "
            "Provide a keyword or topic to search."
        ),
        parameters=QUERY_LEARNINGS_SCHEMA,
        execute=execute,
    )
