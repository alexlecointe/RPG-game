from fastapi import APIRouter, Depends

from app.api.deps import DbSession, verify_api_key
from app.schemas.api import UserCreate, UserOut
from app.services.company import CompanyService

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("", response_model=UserOut)
async def register_user(body: UserCreate, db: DbSession):
    svc = CompanyService(db)
    user = await svc.get_or_create_user(body.device_id)
    await db.commit()
    return user
