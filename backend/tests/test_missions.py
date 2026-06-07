import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import init_db
from app.main import app


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_full_mission_flow(client: AsyncClient):
    headers = {"X-API-Key": "dev-local-key-change-in-production"}

    user = await client.post("/api/v1/users", json={"device_id": "test-device-1"}, headers=headers)
    assert user.status_code == 200
    user_id = user.json()["id"]

    company = await client.post(
        f"/api/v1/companies/{user_id}",
        json={"name": "Test Co", "mission_statement": "Ship fast"},
        headers=headers,
    )
    assert company.status_code == 200
    company_id = company.json()["id"]
    assert company.json()["wallet"]["credits_balance"] >= 30

    catalog = await client.get("/api/v1/catalog/missions", headers=headers)
    assert catalog.status_code == 200
    assert len(catalog.json()) >= 6

    mission = await client.post(
        f"/api/v1/companies/{company_id}/missions",
        json={"mission_type": "idea_storm"},
        headers=headers,
    )
    assert mission.status_code == 200
    mission_id = mission.json()["id"]

    import asyncio

    for _ in range(30):
        await asyncio.sleep(0.5)
        detail = await client.get(f"/api/v1/missions/{mission_id}", headers=headers)
        status = detail.json()["status"]
        if status in ("completed", "failed"):
            break

    detail = await client.get(f"/api/v1/missions/{mission_id}", headers=headers)
    assert detail.json()["status"] == "completed"
    assert detail.json()["deliverable"] is not None
