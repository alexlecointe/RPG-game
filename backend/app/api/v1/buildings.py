from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import DbSession, verify_api_key
from app.schemas.api import BuildingOut
from app.services.building import BuildingService
from app.services.company import CompanyService

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("/companies/{company_id}/buildings/{building_id}/upgrade", response_model=BuildingOut)
async def upgrade_building(company_id: str, building_id: str, db: DbSession):
    company_svc = CompanyService(db)
    company = await company_svc.get_company(company_id)
    if not company or not company.wallet:
        raise HTTPException(404, "Company not found")

    building_svc = BuildingService(db)
    building = await building_svc.get_building(building_id)
    if not building or building.company_id != company_id:
        raise HTTPException(404, "Building not found")

    try:
        building = await building_svc.upgrade(building, company.wallet)
    except ValueError as e:
        code = str(e)
        status = 400
        if code == "insufficient_credits":
            status = 402
        elif code == "max_level_reached":
            status = 409
        raise HTTPException(status, detail=code) from e

    await db.commit()
    return building
