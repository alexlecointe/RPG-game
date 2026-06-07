from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import init_db

_settings = get_settings()

_shared_processors = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]

if _settings.app_env == "development":
    structlog.configure(
        processors=[*_shared_processors, structlog.dev.ConsoleRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(0),
    )
else:
    structlog.configure(
        processors=[*_shared_processors, structlog.processors.JSONRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(20),
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    import structlog as _sl
    _log = _sl.get_logger()
    try:
        await init_db()
    except Exception as _exc:
        _log.warning("startup_db_failed", error=str(_exc))
    try:
        from app.agents.skill_shop_catalog import sync_shop_catalog
        await sync_shop_catalog()
    except Exception as _exc:
        _log.warning("startup_catalog_failed", error=str(_exc))
    yield


app = FastAPI(
    title="RPG Agent Company API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Basic health check: DB + Redis connectivity."""
    status: dict = {"status": "ok"}
    from app.core.database import SessionLocal
    try:
        async with SessionLocal() as db:
            from sqlalchemy import text
            await db.execute(text("SELECT 1"))
        status["db"] = "ok"
    except Exception as exc:
        status["db"] = f"error: {exc}"
        status["status"] = "degraded"

    if _settings.redis_url:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(_settings.redis_url)
            await r.ping()
            await r.aclose()
            status["redis"] = "ok"
        except Exception as exc:
            status["redis"] = f"error: {exc}"
            status["status"] = "degraded"

    return status


app.include_router(api_router, prefix="/api/v1")
