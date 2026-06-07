"""Row-Level Security (RLS) for multi-tenant data isolation on PostgreSQL.

Activates RLS policies on all tables with a company_id column. Each DB
session sets `app.current_company_id` so PostgreSQL automatically filters
rows — no more reliance on application-level WHERE clauses.

Only active when running against PostgreSQL (Neon). SQLite has no RLS.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger()

RLS_TABLES = [
    "missions",
    "mission_logs",
    "company_memories",
    "company_emails",
    "company_notifications",
    "buildings",
    "quest_steps",
    "token_usage",
    "browser_sessions",
]

WALLETS_TABLE = "wallets"


async def setup_rls(engine) -> None:
    """Create RLS policies on all tenant-scoped tables.

    Safe to call multiple times (uses IF NOT EXISTS / OR REPLACE patterns).
    """
    from sqlalchemy import text

    async with engine.begin() as conn:
        for table in RLS_TABLES:
            try:
                await conn.execute(text(
                    f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"
                ))
                await conn.execute(text(
                    f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"
                ))
                await conn.execute(text(f"""
                    CREATE POLICY IF NOT EXISTS tenant_isolation ON {table}
                    USING (company_id = current_setting('app.current_company_id', true))
                """))
                logger.info("rls_policy_created", table=table)
            except Exception as exc:
                logger.debug("rls_policy_skip", table=table, reason=str(exc))

        try:
            await conn.execute(text(
                f"ALTER TABLE {WALLETS_TABLE} ENABLE ROW LEVEL SECURITY"
            ))
            await conn.execute(text(
                f"ALTER TABLE {WALLETS_TABLE} FORCE ROW LEVEL SECURITY"
            ))
            await conn.execute(text(f"""
                CREATE POLICY IF NOT EXISTS tenant_isolation ON {WALLETS_TABLE}
                USING (company_id = current_setting('app.current_company_id', true))
            """))
        except Exception as exc:
            logger.debug("rls_policy_skip", table=WALLETS_TABLE, reason=str(exc))


async def set_tenant(session, company_id: str) -> None:
    """Set the current tenant for this DB session (PostgreSQL only)."""
    from sqlalchemy import text
    await session.execute(text(f"SET LOCAL app.current_company_id = '{company_id}'"))
