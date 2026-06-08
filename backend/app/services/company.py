from __future__ import annotations

import asyncio
import math
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entities import AgentType, Building, BusinessType, Company, User, Wallet, _slugify
from app.schemas.api import CompanyCreate

logger = structlog.get_logger()

# Polsia-like: 4 functional buildings — HQ, Website, Ads, Payments
POLSIA_BUILDINGS: list[AgentType] = [
    AgentType.ORCHESTRATOR,  # HQ — research, docs, strategy
    AgentType.BUILDER,       # Website — landing, product
    AgentType.MARKETER,      # Ads — Meta campaigns
    AgentType.FINANCE,       # Payments — Stripe Connect
]

BUILDINGS_BY_BUSINESS_TYPE: dict[BusinessType, list[AgentType]] = {
    BusinessType.ECOMMERCE: POLSIA_BUILDINGS,
    BusinessType.APP: POLSIA_BUILDINGS,
    BusinessType.SAAS: POLSIA_BUILDINGS,
}

# Map legacy agent types to Polsia building for UI/NPC routing
AGENT_TO_POLSIA_BUILDING: dict[AgentType, AgentType] = {
    AgentType.RESEARCHER: AgentType.ORCHESTRATOR,
    AgentType.CONTENT: AgentType.ORCHESTRATOR,
    AgentType.SUPPORT: AgentType.ORCHESTRATOR,
    AgentType.OUTREACH: AgentType.ORCHESTRATOR,
    AgentType.BUILDER: AgentType.BUILDER,
    AgentType.MARKETER: AgentType.MARKETER,
    AgentType.FINANCE: AgentType.FINANCE,
    AgentType.ORCHESTRATOR: AgentType.ORCHESTRATOR,
}


class CompanyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _slug_exists(self, slug: str) -> bool:
        result = await self.db.execute(
            select(Company.id).where(Company.slug == slug).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _ensure_unique_slug(self, name: str) -> str:
        base = _slugify(name)
        if not await self._slug_exists(base):
            return base
        for i in range(2, 100):
            candidate = f"{base[:90]}-{i}"
            if not await self._slug_exists(candidate):
                return candidate
        return f"{base[:80]}-{uuid.uuid4().hex[:8]}"

    async def create_company(self, user_id: str, data: CompanyCreate) -> Company:
        slug = await self._ensure_unique_slug(data.name)
        company = Company(
            user_id=user_id,
            name=data.name,
            slug=slug,
            mission_statement=data.mission_statement,
            product_description=data.product_description,
            target_audience=data.target_audience,
            competitor_url=data.competitor_url,
            business_type=data.business_type,
        )
        self.db.add(company)
        await self.db.flush()

        wallet = Wallet(company_id=company.id, credits_balance=80)
        self.db.add(wallet)

        agent_types = BUILDINGS_BY_BUSINESS_TYPE.get(data.business_type, list(AgentType))
        for agent_type in agent_types:
            self.db.add(Building(company_id=company.id, agent_type=agent_type, level=1))

        await self.db.flush()
        await self.db.refresh(company)

        self._fire_and_forget_provision(company.slug or data.name, company.id)

        return company

    @staticmethod
    def _fire_and_forget_provision(slug: str, company_id: str) -> None:
        """Provision infra (Neon + GitHub + Render) in background, like Polsia HEURE 0."""
        from app.core.config import get_settings
        settings = get_settings()
        if not (settings.render_api_key and settings.github_token and settings.github_org):
            return

        async def _run():
            try:
                from app.core.database import SessionLocal
                from app.models.entities import Company
                from app.services.infra import InfraService

                infra = InfraService()
                result = await infra.provision_company(slug)
                logger.info("infra_provisioned", company_id=company_id, slug=slug, result=result)

                async with SessionLocal() as db:
                    company = await db.get(Company, company_id)
                    if company:
                        if result.get("neon", {}).get("project_id"):
                            company.neon_project_id = result["neon"]["project_id"]
                        if result.get("github", {}).get("repo_url"):
                            company.github_repo_url = result["github"]["repo_url"]
                        if result.get("render", {}).get("service_id"):
                            company.render_service_id = result["render"]["service_id"]
                        if result.get("url"):
                            company.render_url = result["url"]
                        await db.commit()
            except Exception as exc:
                logger.warning("infra_provision_failed", company_id=company_id, error=str(exc))

        try:
            asyncio.get_running_loop().create_task(_run())
        except RuntimeError:
            pass

    async def get_company(self, company_id: str) -> Company | None:
        result = await self.db.execute(
            select(Company)
            .where(Company.id == company_id)
            .options(selectinload(Company.buildings), selectinload(Company.wallet))
        )
        return result.scalar_one_or_none()

    async def add_xp(self, company: Company, xp: int) -> Company:
        company.xp += xp
        company.level = self._level_from_xp(company.xp)
        await self.db.flush()
        return company

    @staticmethod
    def _level_from_xp(xp: int) -> int:
        return max(1, int(math.sqrt(xp / 100)) + 1)

    async def get_or_create_user(self, device_id: str) -> User:
        result = await self.db.execute(select(User).where(User.device_id == device_id))
        user = result.scalar_one_or_none()
        if user:
            return user
        user = User(device_id=device_id)
        self.db.add(user)
        await self.db.flush()
        return user
