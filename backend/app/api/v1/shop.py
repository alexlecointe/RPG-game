from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, verify_api_key
from app.models.entities import Company, CompanySkill, SkillShopItem, Wallet
from app.schemas.api import CompanySkillOut, SkillPurchaseOut, SkillShopItemOut

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get(
    "/companies/{company_id}/shop/skills",
    response_model=list[SkillShopItemOut],
)
async def browse_skill_shop(
    company_id: str = Path(...),
    db: DbSession = None,  # type: ignore[assignment]
):
    """List all available skills in the shop, marking owned ones."""
    owned_q = await db.execute(
        select(CompanySkill.skill_item_id).where(
            CompanySkill.company_id == company_id
        )
    )
    owned_ids = {row[0] for row in owned_q.all()}

    result = await db.execute(
        select(SkillShopItem).where(SkillShopItem.is_active.is_(True))
    )
    items = result.scalars().all()

    return [
        SkillShopItemOut(
            id=item.id,
            mission_type=item.mission_type,
            tier=item.tier.value,
            title=item.title,
            description=item.description,
            credits_cost=item.credits_cost,
            icon=item.icon,
            preview_benefits=item.preview_benefits,
            owned=item.id in owned_ids,
        )
        for item in items
    ]


@router.post(
    "/companies/{company_id}/shop/skills/{item_id}/buy",
    response_model=SkillPurchaseOut,
)
async def buy_skill(
    company_id: str = Path(...),
    item_id: str = Path(...),
    db: DbSession = None,  # type: ignore[assignment]
):
    """Purchase an expert skill for a company."""
    item = await db.get(SkillShopItem, item_id)
    if not item or not item.is_active:
        raise HTTPException(404, "Skill not found")

    existing = await db.execute(
        select(CompanySkill).where(
            CompanySkill.company_id == company_id,
            CompanySkill.skill_item_id == item_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Skill already owned")

    wallet = await db.execute(
        select(Wallet).where(Wallet.company_id == company_id)
    )
    wallet_obj = wallet.scalar_one_or_none()
    if not wallet_obj:
        raise HTTPException(404, "Wallet not found")

    if wallet_obj.credits_balance < item.credits_cost:
        raise HTTPException(
            402,
            f"Not enough credits ({wallet_obj.credits_balance} < {item.credits_cost})",
        )

    wallet_obj.credits_balance -= item.credits_cost

    company_skill = CompanySkill(
        company_id=company_id,
        skill_item_id=item_id,
    )
    db.add(company_skill)
    await db.commit()
    await db.refresh(company_skill)

    return SkillPurchaseOut(
        success=True,
        skill=CompanySkillOut(
            id=company_skill.id,
            mission_type=item.mission_type,
            tier=item.tier.value,
            title=item.title,
            icon=item.icon,
            purchased_at=company_skill.purchased_at,
            times_used=0,
        ),
        credits_remaining=wallet_obj.credits_balance,
    )


@router.get(
    "/companies/{company_id}/skills",
    response_model=list[CompanySkillOut],
)
async def list_owned_skills(
    company_id: str = Path(...),
    db: DbSession = None,  # type: ignore[assignment]
):
    """List all skills owned by a company."""
    result = await db.execute(
        select(CompanySkill)
        .where(CompanySkill.company_id == company_id)
        .options(selectinload(CompanySkill.skill_item))
    )
    skills = result.scalars().all()

    return [
        CompanySkillOut(
            id=cs.id,
            mission_type=cs.skill_item.mission_type,
            tier=cs.skill_item.tier.value,
            title=cs.skill_item.title,
            icon=cs.skill_item.icon,
            purchased_at=cs.purchased_at,
            times_used=cs.times_used,
        )
        for cs in skills
    ]
