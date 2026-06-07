from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Building
from app.services.wallet import WalletService


class BuildingService:
    MAX_LEVEL = 5

    def __init__(self, db: AsyncSession):
        self.db = db
        self.wallet_svc = WalletService(db)

    @staticmethod
    def upgrade_cost(current_level: int) -> int:
        return current_level * 30

    @staticmethod
    def credit_discount_percent(building_level: int) -> int:
        """Level 1 = 0%, level 2 = 5%, ... level 5 = 20%."""
        if building_level <= 1:
            return 0
        return min(20, (building_level - 1) * 5)

    @staticmethod
    def effective_mission_cost(base_cost: int, building_level: int) -> int:
        discount = BuildingService.credit_discount_percent(building_level) / 100
        return max(1, int(base_cost * (1 - discount)))

    async def get_building(self, building_id: str) -> Building | None:
        result = await self.db.execute(select(Building).where(Building.id == building_id))
        return result.scalar_one_or_none()

    async def upgrade(self, building: Building, wallet) -> Building:
        if building.level >= self.MAX_LEVEL:
            raise ValueError("max_level_reached")

        cost = self.upgrade_cost(building.level)
        await self.wallet_svc.debit(wallet, cost)

        building.level += 1
        await self.db.flush()
        return building
