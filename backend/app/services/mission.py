from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.mission_catalog import MISSION_CATALOG
from app.models.entities import AgentType, Mission, MissionLog, MissionStatus, TaskSource
from app.services.company import CompanyService
from app.services.wallet import WalletService
from app.workers.runner import schedule_mission_run


class MissionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.wallet_svc = WalletService(db)
        self.company_svc = CompanyService(db)

    async def _check_and_debit_subscription(self, company_id: str, credits_cost: int) -> bool:
        """Debit from subscription (1 credit) if available. Falls back to wallet for free missions."""
        if credits_cost == 0:
            return True
        from app.services.billing import debit_credit, get_or_create_subscription
        company = await self.company_svc.get_company(company_id)
        if not company:
            return False
        sub = await get_or_create_subscription(self.db, company)
        try:
            await debit_credit(self.db, sub)
            return True
        except ValueError:
            raise ValueError("no_credits")

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

    async def _next_queue_order(self, company_id: str) -> int:
        """Return the next available queue_order for a new PENDING mission."""
        result = await self.db.execute(
            select(func.max(Mission.queue_order))
            .where(Mission.company_id == company_id, Mission.status == MissionStatus.PENDING)
        )
        max_order = result.scalar_one_or_none()
        return (max_order or 0) + 1

    async def get_task_queue(self, company_id: str) -> list[Mission]:
        """Return all PENDING missions ordered by queue_order."""
        result = await self.db.execute(
            select(Mission)
            .where(Mission.company_id == company_id, Mission.status == MissionStatus.PENDING)
            .order_by(Mission.queue_order.asc().nulls_last(), Mission.created_at.asc())
        )
        return list(result.scalars().all())

    async def reject_task(self, mission_id: str, company_id: str, reason: str = "") -> Mission:
        """Reject a PENDING mission. No credit is charged (it was debited at creation)."""
        result = await self.db.execute(
            select(Mission).where(Mission.id == mission_id, Mission.company_id == company_id)
        )
        mission = result.scalar_one_or_none()
        if not mission:
            raise ValueError("mission_not_found")
        if mission.status != MissionStatus.PENDING:
            raise ValueError("mission_not_pending")

        # No credit refund needed — credits are only debited at execution (Polsia model)
        mission.status = MissionStatus.REJECTED
        mission.rejected_reason = reason or "user_cancelled"
        await self._log(mission.id, "rejected", f"Tâche rejetée : {reason or 'user_cancelled'} (0 crédit)")
        await self.db.commit()
        return mission

    async def move_to_top(self, mission_id: str, company_id: str) -> Mission:
        """Move a PENDING mission to position 1 in the queue."""
        result = await self.db.execute(
            select(Mission).where(Mission.id == mission_id, Mission.company_id == company_id)
        )
        mission = result.scalar_one_or_none()
        if not mission:
            raise ValueError("mission_not_found")
        if mission.status != MissionStatus.PENDING:
            raise ValueError("mission_not_pending")

        # Shift all others by +1
        await self.db.execute(
            update(Mission)
            .where(
                Mission.company_id == company_id,
                Mission.status == MissionStatus.PENDING,
                Mission.id != mission_id,
            )
            .values(queue_order=Mission.queue_order + 1)
        )
        mission.queue_order = 1
        await self.db.commit()
        await self.db.refresh(mission)
        return mission

    async def reorder_task(self, mission_id: str, company_id: str, position: int) -> Mission:
        """Move a PENDING mission to a specific position in the queue."""
        result = await self.db.execute(
            select(Mission).where(Mission.id == mission_id, Mission.company_id == company_id)
        )
        mission = result.scalar_one_or_none()
        if not mission:
            raise ValueError("mission_not_found")
        if mission.status != MissionStatus.PENDING:
            raise ValueError("mission_not_pending")

        old_order = mission.queue_order or 999
        new_order = max(1, position)

        if new_order < old_order:
            # Moving up — shift tasks between [new, old-1] down by 1
            await self.db.execute(
                update(Mission)
                .where(
                    Mission.company_id == company_id,
                    Mission.status == MissionStatus.PENDING,
                    Mission.id != mission_id,
                    Mission.queue_order >= new_order,
                    Mission.queue_order < old_order,
                )
                .values(queue_order=Mission.queue_order + 1)
            )
        else:
            # Moving down — shift tasks between [old+1, new] up by 1
            await self.db.execute(
                update(Mission)
                .where(
                    Mission.company_id == company_id,
                    Mission.status == MissionStatus.PENDING,
                    Mission.id != mission_id,
                    Mission.queue_order > old_order,
                    Mission.queue_order <= new_order,
                )
                .values(queue_order=Mission.queue_order - 1)
            )

        mission.queue_order = new_order
        await self.db.commit()
        await self.db.refresh(mission)
        return mission

    async def edit_task(self, mission_id: str, company_id: str, title: str | None, description: str | None) -> Mission:
        """Edit title/description of a PENDING mission."""
        result = await self.db.execute(
            select(Mission).where(Mission.id == mission_id, Mission.company_id == company_id)
        )
        mission = result.scalar_one_or_none()
        if not mission:
            raise ValueError("mission_not_found")
        if mission.status != MissionStatus.PENDING:
            raise ValueError("mission_not_pending")

        if title is not None:
            mission.title = title
        if description is not None:
            mission.description = description

        await self.db.commit()
        await self.db.refresh(mission)
        return mission

    async def create_freeform_task(
        self,
        company_id: str,
        title: str,
        description: str = "",
        agent_type_str: str | None = None,
        source: TaskSource = TaskSource.USER,
        auto_schedule: bool = False,
    ) -> Mission:
        """Create a freeform task with auto-routing.

        Credit is NOT debited at creation (Polsia model):
        it is debited when the agent starts execution in runner.py.
        auto_schedule=False by default so task waits in queue for manual trigger.
        """
        from app.services.task_router import agent_type_from_string, find_best_agent, mission_type_for_freeform

        agent_type = agent_type_from_string(agent_type_str or "") or find_best_agent(title, description)
        mission_type = mission_type_for_freeform(agent_type)

        company = await self.company_svc.get_company(company_id)
        if not company:
            raise ValueError("company_not_found")

        # Check credits are available before queuing (but don't debit yet)
        from app.services.billing import get_or_create_subscription
        sub = await get_or_create_subscription(self.db, company)
        total_credits = (sub.credits_remaining or 0) + (sub.pack_credits or 0)
        if total_credits <= 0:
            raise ValueError("no_credits")

        queue_order = await self._next_queue_order(company_id)

        mission = Mission(
            company_id=company_id,
            agent_type=agent_type,
            mission_type=mission_type,
            title=title,
            description=description or None,
            source=source,
            status=MissionStatus.PENDING,
            queue_order=queue_order,
            credits_cost=1,
            xp_reward=5,
        )
        self.db.add(mission)
        await self.db.flush()
        self.db.add(
            MissionLog(
                mission_id=mission.id,
                step="created",
                message=f"Tâche créée : {title}",
            )
        )
        await self.db.commit()

        if auto_schedule:
            schedule_mission_run(mission.id)

        await self.db.refresh(mission)
        return mission

    async def create_catalog_task(
        self,
        company_id: str,
        mission_type: str,
        title: str,
        description: str = "",
        source: TaskSource = TaskSource.USER,
        auto_schedule: bool = False,
    ) -> Mission:
        """Create a queued task for an explicit catalog mission type."""
        catalog = MISSION_CATALOG.get(mission_type)
        if not catalog:
            raise ValueError("unknown_mission_type")

        company = await self.company_svc.get_company(company_id)
        if not company:
            raise ValueError("company_not_found")

        if catalog.credits_cost > 0:
            from app.services.billing import get_or_create_subscription
            sub = await get_or_create_subscription(self.db, company)
            total_credits = (sub.credits_remaining or 0) + (sub.pack_credits or 0)
            if total_credits <= 0:
                raise ValueError("no_credits")

        queue_order = await self._next_queue_order(company_id)
        mission = Mission(
            company_id=company_id,
            agent_type=catalog.agent_type,
            mission_type=mission_type,
            title=title,
            description=description or None,
            source=source,
            status=MissionStatus.PENDING,
            queue_order=queue_order,
            credits_cost=1 if catalog.credits_cost > 0 else 0,
            xp_reward=int(catalog.credits_cost * 1.5) or 5,
        )
        self.db.add(mission)
        await self.db.flush()
        self.db.add(MissionLog(mission_id=mission.id, step="created", message=f"Tâche créée : {title}"))
        await self.db.commit()

        if auto_schedule:
            schedule_mission_run(mission.id)

        await self.db.refresh(mission)
        return mission

    async def start_mission(
        self,
        company_id: str,
        mission_type: str,
        *,
        auto_schedule: bool = True,
    ) -> Mission:
        from app.core.config import get_settings

        settings = get_settings()
        catalog = MISSION_CATALOG.get(mission_type)
        if not catalog:
            raise ValueError("unknown_mission_type")

        company = await self.company_svc.get_company(company_id)
        if not company or not company.wallet:
            raise ValueError("company_not_found")

        recent = await self.count_recent_missions(company_id)
        if recent >= settings.mission_rate_limit_per_hour:
            raise ValueError("rate_limit_exceeded")

        building_level = 1
        for b in company.buildings:
            if b.agent_type == catalog.agent_type:
                building_level = b.level
                break

        from app.services.building import BuildingService

        # Credit is NOT debited here — it is debited in runner.py at execution start.
        # Free missions (ceo_next_move) still cost 0 at execution.
        effective_cost = 1 if catalog.credits_cost > 0 else 0

        # Check credits are available before queuing (but don't debit yet)
        if effective_cost > 0:
            from app.services.billing import get_or_create_subscription
            sub = await get_or_create_subscription(self.db, company)
            total_credits = (sub.credits_remaining or 0) + (sub.pack_credits or 0)
            if total_credits <= 0:
                raise ValueError("no_credits")

        xp_reward = int(catalog.credits_cost * 1.5) or 5
        if building_level >= 3:
            xp_reward += building_level * 2

        queue_order = await self._next_queue_order(company_id)

        mission = Mission(
            company_id=company_id,
            agent_type=catalog.agent_type,
            mission_type=mission_type,
            source=TaskSource.USER,
            queue_order=queue_order,
            status=MissionStatus.PENDING,
            credits_cost=effective_cost,
            xp_reward=xp_reward,
        )
        self.db.add(mission)
        await self.db.flush()
        self.db.add(
            MissionLog(
                mission_id=mission.id,
                step="created",
                message=f"Mission {mission_type} créée — en attente d'exécution",
            )
        )
        if auto_schedule:
            self.db.add(
                MissionLog(
                    mission_id=mission.id,
                    step="queued",
                    message="Mission envoyée au worker",
                )
            )
        await self.db.commit()

        if auto_schedule:
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
        import structlog as _slog
        _slog.get_logger().info("debug_complete_mission", mission_id=mission.id, deliverable_len=len(deliverable) if deliverable else -1, deliverable_preview=(deliverable or "")[:120], deliverable_format=deliverable_format)
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

        # Polsia model: credits are NOT refunded on failure
        # (the agent tried — 1 credit was consumed at execution start)

        await self.db.commit()
        return mission
