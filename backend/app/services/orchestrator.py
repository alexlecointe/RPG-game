from __future__ import annotations

from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.mission_catalog import MISSION_CATALOG
from app.models.entities import (
    BusinessType,
    Company,
    CompanyNotification,
    NotificationType,
    QuestStep,
    QuestStepStatus,
)
from app.services.quest_chain import get_dependency_graph

logger = structlog.get_logger()

MAX_STEP_RETRIES = 2


class OrchestratorService:
    def __init__(self, db: AsyncSession):
        self._db = db

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    async def _notify(
        self,
        company_id: str,
        ntype: NotificationType,
        title: str,
        message: str,
    ) -> None:
        self._db.add(CompanyNotification(
            company_id=company_id,
            type=ntype,
            title=title,
            message=message,
        ))
        await self._db.flush()

    # ------------------------------------------------------------------
    # Core: after a mission completes successfully
    # ------------------------------------------------------------------

    async def after_mission_completed(
        self, company_id: str, completed_step_title: str = "",
    ) -> list[QuestStep]:
        """Called by the runner after a quest-chain mission completes.

        1. Emit a step_completed notification
        2. Check for newly available steps
        3. If auto_pilot is on, auto-launch them
        4. Emit appropriate notifications
        """
        company = await self._get_company(company_id)
        if not company:
            return []

        if completed_step_title:
            await self._notify(
                company_id,
                NotificationType.STEP_COMPLETED,
                "Etape terminee",
                f'"{completed_step_title}" est terminee. Le livrable est pret.',
            )

        chain = await self._get_chain(company_id)
        available = [s for s in chain if s.status == QuestStepStatus.AVAILABLE]

        if not available:
            all_done = all(s.status == QuestStepStatus.COMPLETED for s in chain)
            if all_done and chain:
                await self._notify(
                    company_id,
                    NotificationType.CHAIN_COMPLETED,
                    "Quest chain terminee !",
                    "Toutes les etapes sont completees. Ton business est lance !",
                )
            await self._db.commit()
            return []

        newly_names = [s.title for s in available if s.unlocked_at and not s.mission_id]
        if newly_names:
            await self._notify(
                company_id,
                NotificationType.STEP_UNLOCKED,
                f"{len(newly_names)} nouvelle(s) etape(s) disponible(s)",
                f"Etapes debloquees : {', '.join(newly_names)}",
            )

        if not company.auto_pilot:
            await self._db.commit()
            return available

        launched = await self._auto_launch(company, available)
        await self._db.commit()
        return launched

    # ------------------------------------------------------------------
    # Auto-launch available steps (callable from API too)
    # ------------------------------------------------------------------

    async def auto_start_available_steps(self, company_id: str) -> list[QuestStep]:
        """Manually trigger auto-launch of all available steps."""
        company = await self._get_company(company_id)
        if not company:
            return []

        chain = await self._get_chain(company_id)
        available = [
            s for s in chain
            if s.status == QuestStepStatus.AVAILABLE and not s.mission_id
        ]
        if not available:
            return []

        launched = await self._auto_launch(company, available)
        await self._db.commit()
        return launched

    # ------------------------------------------------------------------
    # Retry a failed step
    # ------------------------------------------------------------------

    async def handle_step_failure(
        self, company_id: str, mission_type: str,
    ) -> Optional[QuestStep]:
        """Called when a quest-chain mission fails.

        If retry_count < MAX_STEP_RETRIES -> set step back to AVAILABLE.
        Else -> mark step FAILED and notify.
        """
        step = await self._find_step(company_id, mission_type)
        if not step:
            return None

        step.retry_count += 1

        if step.retry_count <= MAX_STEP_RETRIES:
            step.status = QuestStepStatus.AVAILABLE
            step.mission_id = None
            logger.info(
                "step_retry",
                company_id=company_id,
                step=step.step_number,
                retry=step.retry_count,
            )
            await self._db.commit()
            return step

        step.status = QuestStepStatus.FAILED
        await self._notify(
            company_id,
            NotificationType.STEP_FAILED,
            f'Etape "{step.title}" echouee',
            f"L'etape {step.step_number} a echoue apres {step.retry_count} tentatives.",
        )
        logger.warning(
            "step_failed_permanently",
            company_id=company_id,
            step=step.step_number,
        )
        await self._db.commit()
        return step

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _auto_launch(
        self, company: Company, available: list[QuestStep],
    ) -> list[QuestStep]:
        """Launch available steps in priority order, respecting credits and rate limit."""
        from app.services.mission import MissionService
        from app.services.quest_chain import QuestChainService

        mission_svc = MissionService(self._db)
        chain_svc = QuestChainService(self._db)

        prioritized = self._prioritize_steps(available, company.business_type)
        launched: list[QuestStep] = []

        for step in prioritized:
            if step.mission_id:
                continue

            catalog = MISSION_CATALOG.get(step.mission_type)
            if not catalog:
                continue

            try:
                mission = await mission_svc.start_mission(
                    company.id, step.mission_type
                )
                await chain_svc.mark_step_running(
                    company.id, step.step_number, mission.id
                )
                launched.append(step)
                logger.info(
                    "step_auto_launched",
                    company_id=company.id,
                    step=step.step_number,
                    mission_type=step.mission_type,
                )
            except ValueError as exc:
                logger.warning(
                    "auto_launch_skipped",
                    step=step.step_number,
                    reason=str(exc),
                )
                if str(exc) in ("rate_limit_exceeded", "insufficient_credits"):
                    break

        if launched:
            names = [s.title for s in launched]
            await self._notify(
                company.id,
                NotificationType.STEP_AUTO_LAUNCHED,
                f"{len(launched)} etape(s) lancee(s) automatiquement",
                f"L'orchestrateur a lance : {', '.join(names)}",
            )

        return launched

    def _prioritize_steps(
        self, steps: list[QuestStep], business_type: BusinessType,
    ) -> list[QuestStep]:
        """Sort steps by critical path: steps that unblock the most dependants first."""
        dep_graph = get_dependency_graph(business_type)
        reverse_graph: dict[int, int] = {}

        for step_num, prereqs in dep_graph.items():
            for prereq in prereqs:
                reverse_graph[prereq] = reverse_graph.get(prereq, 0) + 1

        def _downstream_count(step_num: int) -> int:
            """Count how many steps are (transitively) blocked by this one."""
            count = 0
            queue = [step_num]
            visited = set()
            while queue:
                current = queue.pop(0)
                for sn, prereqs in dep_graph.items():
                    if current in prereqs and sn not in visited:
                        visited.add(sn)
                        count += 1
                        queue.append(sn)
            return count

        return sorted(steps, key=lambda s: _downstream_count(s.step_number), reverse=True)

    async def _get_company(self, company_id: str) -> Optional[Company]:
        from sqlalchemy.orm import selectinload
        result = await self._db.execute(
            select(Company)
            .where(Company.id == company_id)
            .options(selectinload(Company.wallet))
        )
        return result.scalar_one_or_none()

    async def _get_chain(self, company_id: str) -> list[QuestStep]:
        result = await self._db.execute(
            select(QuestStep)
            .where(QuestStep.company_id == company_id)
            .order_by(QuestStep.step_number)
        )
        return list(result.scalars().all())

    async def _find_step(
        self, company_id: str, mission_type: str,
    ) -> Optional[QuestStep]:
        result = await self._db.execute(
            select(QuestStep).where(
                QuestStep.company_id == company_id,
                QuestStep.mission_type == mission_type,
                QuestStep.status == QuestStepStatus.RUNNING,
            )
        )
        return result.scalar_one_or_none()
