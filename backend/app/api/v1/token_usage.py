"""API endpoints for token usage tracking and cost monitoring."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import DbSession, verify_api_key
from app.models.entities import TokenUsage

router = APIRouter(dependencies=[Depends(verify_api_key)])


class TokenUsageSummary(BaseModel):
    company_id: str
    total_tokens: int
    total_input_tokens: int
    total_output_tokens: int
    estimated_cost_usd: float
    mission_count: int
    period_days: int


class TokenUsageByProvider(BaseModel):
    provider: str
    model: str
    total_tokens: int
    estimated_cost_usd: float
    call_count: int


@router.get(
    "/companies/{company_id}/token-usage",
    response_model=TokenUsageSummary,
)
async def get_token_usage(
    company_id: str,
    days: int = 30,
    db: DbSession = None,
):
    """Get token usage summary for a company over a period."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            func.coalesce(func.sum(TokenUsage.total_tokens), 0),
            func.coalesce(func.sum(TokenUsage.input_tokens), 0),
            func.coalesce(func.sum(TokenUsage.output_tokens), 0),
            func.coalesce(func.sum(TokenUsage.estimated_cost_usd), 0.0),
            func.count(func.distinct(TokenUsage.mission_id)),
        )
        .where(
            TokenUsage.company_id == company_id,
            TokenUsage.created_at >= since,
        )
    )
    row = result.one()

    return TokenUsageSummary(
        company_id=company_id,
        total_tokens=row[0],
        total_input_tokens=row[1],
        total_output_tokens=row[2],
        estimated_cost_usd=round(row[3], 4),
        mission_count=row[4],
        period_days=days,
    )


@router.get(
    "/companies/{company_id}/token-usage/by-provider",
    response_model=list[TokenUsageByProvider],
)
async def get_token_usage_by_provider(
    company_id: str,
    days: int = 30,
    db: DbSession = None,
):
    """Get token usage breakdown by provider/model."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            TokenUsage.provider,
            TokenUsage.model,
            func.sum(TokenUsage.total_tokens),
            func.sum(TokenUsage.estimated_cost_usd),
            func.count(TokenUsage.id),
        )
        .where(
            TokenUsage.company_id == company_id,
            TokenUsage.created_at >= since,
        )
        .group_by(TokenUsage.provider, TokenUsage.model)
    )

    return [
        TokenUsageByProvider(
            provider=row[0],
            model=row[1],
            total_tokens=row[2],
            estimated_cost_usd=round(row[3], 4),
            call_count=row[4],
        )
        for row in result.all()
    ]
