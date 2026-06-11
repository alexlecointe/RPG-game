from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

_engine_kwargs: dict = {"echo": settings.app_env == "development"}

if settings.is_postgres:
    _engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 10,
        # asyncpg needs ssl passed as connect_arg, not as URL ?sslmode=
        "connect_args": {"ssl": "require", "statement_cache_size": 0},
    })

engine = create_async_engine(settings.database_url, **_engine_kwargs)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def get_tenant_db(company_id: str) -> AsyncGenerator[AsyncSession, None]:
    """Yield a DB session scoped to a specific company (RLS-enforced on Postgres)."""
    async with SessionLocal() as session:
        if settings.is_postgres:
            from app.core.rls import set_tenant
            await set_tenant(session, company_id)
        yield session


async def init_db() -> None:
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if settings.is_postgres:
        await _migrate_postgres(engine)
        from app.core.rls import setup_rls
        await setup_rls(engine)
    else:
        await _migrate_sqlite(engine)


_COLUMN_MIGRATIONS: list[tuple[str, str, str, str]] = [
    # (table, column, sqlite_type, postgres_type)
    ("missions", "quality_score", "REAL", "DOUBLE PRECISION"),
    ("missions", "quality_feedback", "TEXT", "TEXT"),
    ("missions", "source", "VARCHAR(32) DEFAULT 'user'", "VARCHAR(32) DEFAULT 'user'"),
    ("missions", "title", "VARCHAR(255)", "VARCHAR(255)"),
    ("missions", "description", "TEXT", "TEXT"),
    ("missions", "queue_order", "INTEGER", "INTEGER"),
    ("missions", "rejected_reason", "VARCHAR(255)", "VARCHAR(255)"),
    ("companies", "slug", "VARCHAR(100)", "VARCHAR(100)"),
    ("companies", "auto_pilot", "BOOLEAN DEFAULT 0", "BOOLEAN DEFAULT FALSE"),
    ("companies", "render_service_id", "VARCHAR(64)", "VARCHAR(64)"),
    ("companies", "render_url", "VARCHAR(500)", "VARCHAR(500)"),
    ("companies", "neon_project_id", "VARCHAR(64)", "VARCHAR(64)"),
    ("companies", "github_repo_url", "VARCHAR(500)", "VARCHAR(500)"),
    ("companies", "stripe_connect_account_id", "VARCHAR(64)", "VARCHAR(64)"),
    ("companies", "daily_ads_budget_cents", "INTEGER DEFAULT 0", "INTEGER DEFAULT 0"),
    ("companies", "ads_wallet_balance_cents", "INTEGER DEFAULT 0", "INTEGER DEFAULT 0"),
    ("companies", "ads_payment_state", "VARCHAR(40)", "VARCHAR(40)"),
    ("companies", "ads_winding_down", "BOOLEAN DEFAULT 0", "BOOLEAN DEFAULT FALSE"),
    ("companies", "infra_status", "VARCHAR(20) DEFAULT 'pending'", "VARCHAR(20) DEFAULT 'pending'"),
    ("companies", "product_image_url", "VARCHAR(500)", "VARCHAR(500)"),
    ("payment_links", "payout_status", "VARCHAR(32) DEFAULT 'connected'", "VARCHAR(32) DEFAULT 'connected'"),
    ("payment_links", "requires_connect", "BOOLEAN DEFAULT 0", "BOOLEAN DEFAULT FALSE"),
    ("quest_steps", "retry_count", "INTEGER DEFAULT 0", "INTEGER DEFAULT 0"),
    ("mission_logs", "level", "VARCHAR(10) DEFAULT 'info'", "VARCHAR(10) DEFAULT 'info'"),
    ("mission_logs", "metadata_json", "TEXT", "TEXT"),
]


async def _migrate_sqlite(eng) -> None:
    """Lightweight ALTER TABLE for SQLite only (no Alembic)."""
    from sqlalchemy import text

    async with eng.begin() as conn:
        for table, column, sqlite_type, _ in _COLUMN_MIGRATIONS:
            try:
                await conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {column} {sqlite_type}")
                )
            except Exception:
                pass


async def _migrate_postgres(eng) -> None:
    """Lightweight ALTER TABLE for Postgres (no Alembic)."""
    from sqlalchemy import text

    async with eng.begin() as conn:
        for table, column, _, pg_type in _COLUMN_MIGRATIONS:
            await conn.execute(
                text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {pg_type}")
            )
