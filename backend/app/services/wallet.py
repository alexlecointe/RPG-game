from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import Wallet


class WalletService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def get_wallet(self, company_id: str) -> Wallet | None:
        result = await self.db.execute(select(Wallet).where(Wallet.company_id == company_id))
        return result.scalar_one_or_none()

    async def apply_daily_regen(self, wallet: Wallet) -> Wallet:
        now = datetime.now(timezone.utc)
        today = now.date()
        last = wallet.last_daily_regen_at
        if last is not None and last.date() >= today:
            return wallet
        wallet.credits_balance = min(
            wallet.credits_balance + self.settings.daily_free_credits,
            self.settings.credits_cap,
        )
        wallet.last_daily_regen_at = now
        await self.db.flush()
        return wallet

    async def debit(self, wallet: Wallet, amount: int) -> None:
        if wallet.credits_balance < amount:
            raise ValueError("insufficient_credits")
        wallet.credits_balance -= amount
        await self.db.flush()

    async def credit(self, wallet: Wallet, amount: int) -> None:
        wallet.credits_balance = min(wallet.credits_balance + amount, self.settings.credits_cap)
        await self.db.flush()

    def refund_amount(self, credits_cost: int) -> int:
        pct = self.settings.mission_refund_on_fail_percent
        return max(1, (credits_cost * pct) // 100)

    async def claim_daily_reward(self, wallet: Wallet) -> dict:
        now = datetime.now(timezone.utc)
        today = now.date()
        last = wallet.last_daily_reward_at

        if last is not None and last.date() >= today:
            raise ValueError("daily_reward_already_claimed")

        if last is not None and (today - last.date()).days == 1:
            wallet.daily_streak += 1
        else:
            wallet.daily_streak = 1

        base_reward = 15
        streak_bonus = min(wallet.daily_streak - 1, 6) * 3
        total = base_reward + streak_bonus
        bonus_active = wallet.daily_streak >= 3

        wallet.credits_balance = min(wallet.credits_balance + total, self.settings.credits_cap)
        wallet.last_daily_reward_at = now
        await self.db.flush()

        return {
            "credits_awarded": total,
            "streak": wallet.daily_streak,
            "bonus_active": bonus_active,
        }
