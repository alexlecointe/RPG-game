from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import DbSession, verify_api_key
from app.schemas.api import DailyRewardOut
from app.services.company import CompanyService
from app.services.wallet import WalletService

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("/companies/{company_id}/daily-reward", response_model=DailyRewardOut)
async def claim_daily_reward(company_id: str, db: DbSession):
    company_svc = CompanyService(db)
    company = await company_svc.get_company(company_id)
    if not company or not company.wallet:
        raise HTTPException(404, "Company not found")

    wallet_svc = WalletService(db)
    try:
        result = await wallet_svc.claim_daily_reward(company.wallet)
    except ValueError as e:
        code = str(e)
        if code == "daily_reward_already_claimed":
            raise HTTPException(409, detail=code) from e
        raise HTTPException(400, detail=code) from e

    await company_svc.add_xp(company, 5)
    await db.commit()

    return DailyRewardOut(**result)
