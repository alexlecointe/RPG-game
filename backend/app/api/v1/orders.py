"""Orders API — ventes des founders à leurs clients (Système B)."""
from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.entities import Company, Order

router = APIRouter()
logger = structlog.get_logger()

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/companies/{company_id}/orders")
async def list_orders(company_id: str, db: DbSession, limit: int = 50, offset: int = 0):
    """List customer orders for a company (founder's product sales)."""
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    result = await db.execute(
        select(Order)
        .where(Order.company_id == company_id)
        .order_by(Order.created_at.desc())
        .limit(min(limit, 200))
        .offset(offset)
    )
    orders = result.scalars().all()

    total_result = await db.execute(
        select(func.count(Order.id)).where(Order.company_id == company_id)
    )
    total = total_result.scalar_one()

    revenue_result = await db.execute(
        select(func.sum(Order.amount_cents)).where(Order.company_id == company_id)
    )
    total_revenue_cents = revenue_result.scalar_one() or 0

    return {
        "orders": [
            {
                "id": o.id,
                "stripe_payment_intent_id": o.stripe_payment_intent_id,
                "stripe_session_id": o.stripe_session_id,
                "customer_email": o.customer_email,
                "amount_cents": o.amount_cents,
                "currency": o.currency,
                "product_name": o.product_name,
                "meta_event_sent": o.meta_event_sent,
                "created_at": o.created_at.isoformat(),
            }
            for o in orders
        ],
        "total": total,
        "total_revenue_cents": total_revenue_cents,
    }


@router.get("/companies/{company_id}/orders/{order_id}")
async def get_order(company_id: str, order_id: str, db: DbSession):
    """Get a single order."""
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.company_id == company_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return {
        "id": order.id,
        "stripe_payment_intent_id": order.stripe_payment_intent_id,
        "stripe_session_id": order.stripe_session_id,
        "customer_email": order.customer_email,
        "amount_cents": order.amount_cents,
        "currency": order.currency,
        "product_name": order.product_name,
        "meta_event_sent": order.meta_event_sent,
        "created_at": order.created_at.isoformat(),
    }
