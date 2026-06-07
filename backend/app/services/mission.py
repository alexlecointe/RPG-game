from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.mission_catalog import MISSION_CATALOG
from app.models.entities import Mission, MissionLog, MissionStatus
from app.services.company import CompanyService
from app.services.wallet import WalletService
from app.workers.runner import schedule_mission_run


class MissionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.wallet_svc = WalletService(db)
        self.company_svc = CompanyService(db)

    async def list_missions(self, company_id: str, limit: int = 20) -> list[Mission]:
        result = await self.db.execute(
            select(Mission)
            .where(Mission.company_id == company_id)
            .order_by(Mission.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_mission(self, mission_id: str) -> Mission | None:
        result = await self.db.execute(
            select(Mission).where(Mission.id == mission_id).options(selectinload(Mission.logs))
        )
        return result.scalar_one_or_none()

    async def count_recent_missions(self, company_id: str, hours: int = 1) -> int:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = await self.db.execute(
            select(func.count())
            .select_from(Mission)
            .where(Mission.company_id == company_id, Mission.created_at >= since)
        )
        return result.scalar_one() or 0

    async def start_mission(self, company_id: str, mission_type: str) -> Mission:
        from app.core.config import get_settings

        settings = get_settings()
        catalog = MISSION_CATALOG.get(mission_type)
        if not catalog:
            raise ValueError("unknown_mission_type")

        company = await self.company_svc.get_company(company_id)
        if not company or not company.wallet:
            raise ValueError("company_not_found")

        wallet = await self.wallet_svc.apply_daily_regen(company.wallet)

        recent = await self.count_recent_missions(company_id)
        if recent >= settings.mission_rate_limit_per_hour:
            raise ValueError("rate_limit_exceeded")

        building_level = 1
        for b in company.buildings:
            if b.agent_type == catalog.agent_type:
                building_level = b.level
                break

        from app.services.building import BuildingService

        effective_cost = BuildingService.effective_mission_cost(
            catalog.credits_cost, building_level
        )

        await self.wallet_svc.debit(wallet, effective_cost)

        xp_reward = int(effective_cost * 1.5)
        if building_level >= 3:
            xp_reward += building_level * 2

        mission = Mission(
            company_id=company_id,
            agent_type=catalog.agent_type,
            mission_type=mission_type,
            status=MissionStatus.PENDING,
            credits_cost=effective_cost,
            xp_reward=xp_reward,
        )
        self.db.add(mission)
        await self.db.flush()
        self.db.add(
            MissionLog(
                mission_id=mission.id,
                step="debited",
                message=f"Débit de {effective_cost} crédits"
                + (f" (niv.{building_level}, -{BuildingService.credit_discount_percent(building_level)}%)" if building_level > 1 else ""),
            )
        )
        self.db.add(
            MissionLog(mission_id=mission.id, step="created", message=f"Mission {mission_type} créée")
        )
        await self.db.commit()

        schedule_mission_run(mission.id)
        await self.db.refresh(mission)
        return mission

    async def _log(self, mission_id: str | None, step: str, message: str) -> None:
        if mission_id is None:
            return
        self.db.add(MissionLog(mission_id=mission_id, step=step, message=message))
        await self.db.flush()

    async def complete_mission(
        self,
        mission: Mission,
        deliverable_format: str,
        deliverable: str,
    ) -> Mission:
        mission.status = MissionStatus.COMPLETED
        mission.deliverable_format = deliverable_format
        mission.deliverable = deliverable
        mission.completed_at = datetime.now(timezone.utc)
        await self._log(mission.id, "completed", "Livrable prêt")

        company = await self.company_svc.get_company(mission.company_id)
        if company:
            xp = mission.xp_reward
            if mission.quality_score is not None:
                if mission.quality_score >= 9:
                    xp = int(xp * 1.10)
                elif mission.quality_score >= 7:
                    xp = int(xp * 1.05)
                mission.xp_reward = xp
            await self.company_svc.add_xp(company, mission.xp_reward)

        await self.db.commit()

        from app.services.quest_chain import QuestChainService

        chain_svc = QuestChainService(self.db)
        quest_step = await chain_svc.find_step_for_mission(
            mission.company_id, mission.mission_type
        )
        if quest_step:
            bt = company.business_type if company else None
            from app.models.entities import BusinessType
            await chain_svc.complete_step(
                mission.company_id, quest_step.step_number,
                business_type=bt or BusinessType.ECOMMERCE,
            )

        return mission

    async def fail_mission(self, mission: Mission, error: str) -> Mission:
        mission.status = MissionStatus.FAILED
        mission.error_message = error
        mission.completed_at = datetime.now(timezone.utc)
        await self._log(mission.id, "failed", error)

        company = await self.company_svc.get_company(mission.company_id)
        if company and company.wallet:
            refund = self.wallet_svc.refund_amount(mission.credits_cost)
            await self.wallet_svc.credit(company.wallet, refund)
            await self._log(mission.id, "refunded", f"Remboursement {refund} crédits")

        await self.db.commit()
        return mission
