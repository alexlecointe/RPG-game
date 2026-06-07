from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    api_key: str = "dev-local-key-change-in-production"

    # Database — supports both SQLite (dev) and PostgreSQL/Neon (prod)
    database_url: str = "sqlite+aiosqlite:///./rpg_agent.db"
    database_url_direct: str = ""  # unpooled URL for Alembic migrations (Neon)

    # Redis for Celery task queue
    redis_url: str = "redis://localhost:6379/0"

    agent_mode: str = "mock"  # mock | openai | anthropic | auto
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    daily_free_credits: int = 50
    credits_cap: int = 150
    mission_refund_on_fail_percent: int = 50

    mission_rate_limit_per_hour: int = 10

    # Tool calling
    tools_enabled: bool = True
    tavily_api_key: str = ""
    firecrawl_api_key: str = ""
    vercel_token: str = ""

    # New tool integrations
    replicate_api_token: str = ""
    resend_api_key: str = ""
    resend_from_domain: str = "resend.dev"
    browserbase_api_key: str = ""
    browserbase_project_id: str = ""
    serpapi_key: str = ""

    # Stripe — payments (Banque building)
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # Meta — Pixel + Conversions API + Ads (compte central plateforme)
    meta_pixel_id: str = ""
    meta_capi_token: str = ""
    meta_ad_account_id: str = ""

    # Backend public URL — Render services forwardent les webhooks Stripe ici
    backend_public_url: str = ""

    # Cloudflare R2 — stockage assets (fallback local si non configure)
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_public_url: str = ""

    # X/Twitter — compte central plateforme (OAuth 1.0a)
    x_api_key: str = ""
    x_api_secret: str = ""
    x_access_token: str = ""
    x_access_token_secret: str = ""

    # Infrastructure — Render + Neon + GitHub (modele Polsia: 1 service + 1 DB + 1 repo par company)
    render_api_key: str = ""
    neon_api_key: str = ""
    github_token: str = ""
    github_org: str = ""

    @property
    def r2_configured(self) -> bool:
        return bool(
            self.r2_account_id
            and self.r2_access_key_id
            and self.r2_secret_access_key
            and self.r2_bucket_name
        )

    @property
    def meta_configured(self) -> bool:
        return bool(self.meta_pixel_id and self.meta_capi_token)

    @property
    def x_configured(self) -> bool:
        return bool(
            self.x_api_key
            and self.x_api_secret
            and self.x_access_token
            and self.x_access_token_secret
        )

    @property
    def is_postgres(self) -> bool:
        return "postgresql" in self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
