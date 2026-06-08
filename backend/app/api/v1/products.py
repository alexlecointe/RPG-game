"""Products API — Payment Links + Stripe products for founder sales (Système B)."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DbSession, verify_api_key
from app.core.config import get_settings
from app.models.entities import PaymentLink
from app.services.company import CompanyService

router = APIRouter(dependencies=[Depends(verify_api_key)])
logger = structlog.get_logger()


class CreatePaymentLinkBody(BaseModel):
    product_name: str
    amount_cents: int
    currency: str = "eur"
    success_url: str = ""


@router.get("/companies/{company_id}/products")
async def list_products(company_id: str, db: DbSession):
    """List all Payment Links persisted for a company (from DB, not live Stripe call)."""
    svc = CompanyService(db)
    company = await svc.get_company(company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    result = await db.execute(
        select(PaymentLink)
        .where(PaymentLink.company_id == company_id, PaymentLink.active == True)  # noqa: E712
        .order_by(PaymentLink.created_at.desc())
        .limit(50)
    )
    links = result.scalars().all()

    return {
        "products": [
            {
                "id": lnk.stripe_product_id or lnk.id,
                "name": lnk.product_name,
                "description": "",
                "payment_link_id": lnk.stripe_payment_link_id,
                "payment_link_url": lnk.url,
                "active": lnk.active,
                "prices": [
                    {
                        "price_id": lnk.stripe_price_id,
                        "amount": lnk.amount_cents,
                        "currency": lnk.currency,
                        "recurring": None,
                    }
                ],
                "created_at": lnk.created_at.isoformat(),
            }
            for lnk in links
        ],
        "count": len(links),
    }


@router.post("/companies/{company_id}/products/payment-link")
async def create_payment_link(company_id: str, body: CreatePaymentLinkBody, db: DbSession):
    """Create a permanent Stripe Payment Link and persist it to DB."""
    if not body.product_name or body.amount_cents <= 0:
        raise HTTPException(400, "product_name and amount_cents > 0 required")

    svc = CompanyService(db)
    company = await svc.get_company(company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    settings = get_settings()

    if not settings.stripe_secret_key:
        mock_link_id = f"plink_mock_{body.product_name[:8].replace(' ', '_').lower()}"
        mock_url = f"https://buy.stripe.com/mock/{company.slug or company_id}/{body.product_name.lower().replace(' ', '-')}"
        db.add(PaymentLink(
            company_id=company_id,
            stripe_payment_link_id=mock_link_id,
            url=mock_url,
            product_name=body.product_name,
            amount_cents=body.amount_cents,
            currency=body.currency.lower(),
        ))
        await db.commit()
        return {"url": mock_url, "payment_link_id": mock_link_id, "product_id": None, "price_id": None}

    from app.agents.tools.stripe_action import _create_payment_link
    connect_account_id = getattr(company, "stripe_connect_account_id", None) or ""
    result = await _create_payment_link(
        secret_key=settings.stripe_secret_key,
        product_name=body.product_name,
        amount_cents=body.amount_cents,
        currency=body.currency.lower(),
        success_url=body.success_url or settings.backend_public_url or "https://example.com/merci",
        company_slug=company.slug or "",
        connect_account_id=connect_account_id,
    )

    db.add(PaymentLink(
        company_id=company_id,
        stripe_payment_link_id=result["payment_link_id"],
        url=result["payment_link_url"],
        product_name=body.product_name,
        amount_cents=body.amount_cents,
        currency=body.currency.lower(),
        stripe_product_id=result.get("product_id"),
        stripe_price_id=result.get("price_id"),
    ))
    await db.commit()

    logger.info("payment_link_created_via_api", company_id=company_id, url=result.get("payment_link_url"))
    return result


@router.delete("/companies/{company_id}/products/payment-link/{link_id}")
async def deactivate_payment_link(company_id: str, link_id: str, db: DbSession):
    """Soft-delete a Payment Link (marks active=False)."""
    result = await db.execute(
        select(PaymentLink).where(
            PaymentLink.company_id == company_id,
            PaymentLink.stripe_payment_link_id == link_id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(404, "Payment link not found")
    link.active = False
    await db.commit()
    return {"deactivated": True}
