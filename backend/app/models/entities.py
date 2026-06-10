from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class MissionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class TaskSource(str, enum.Enum):
    USER = "user"
    CEO_PROPOSAL = "ceo_proposal"
    AGENT_GENERATED = "agent_generated"
    RECURRING_TASK = "recurring_task"


class BusinessType(str, enum.Enum):
    ECOMMERCE = "ecommerce"
    APP = "app"
    SAAS = "saas"


class AgentType(str, enum.Enum):
    BUILDER = "builder"
    MARKETER = "marketer"
    RESEARCHER = "researcher"
    ORCHESTRATOR = "orchestrator"
    OUTREACH = "outreach"
    SUPPORT = "support"
    FINANCE = "finance"
    CONTENT = "content"
    # Polsia extended agent types
    BROWSER = "browser"
    DATA = "data"
    OPS = "ops"
    GROWTH = "growth"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    device_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    companies: Mapped[list["Company"]] = relationship(back_populates="user")


def _slugify(name: str) -> str:
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().strip()).strip("-")
    return slug[:100] or "company"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    mission_statement: Mapped[str] = mapped_column(Text, default="")
    product_description: Mapped[str] = mapped_column(Text, default="")
    target_audience: Mapped[str] = mapped_column(Text, default="")
    competitor_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    business_type: Mapped[BusinessType] = mapped_column(
        Enum(BusinessType, native_enum=False), default=BusinessType.ECOMMERCE
    )
    auto_pilot: Mapped[bool] = mapped_column(Boolean, default=False)
    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    render_service_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    render_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    neon_project_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    github_repo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    infra_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="pending")
    product_image_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    stripe_connect_account_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    daily_ads_budget_cents: Mapped[int] = mapped_column(Integer, default=0)
    ads_wallet_balance_cents: Mapped[int] = mapped_column(Integer, default=0)
    ads_payment_state: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    ads_winding_down: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="companies")
    wallet: Mapped["Wallet"] = relationship(back_populates="company", uselist=False)
    buildings: Mapped[list["Building"]] = relationship(back_populates="company")
    missions: Mapped[list["Mission"]] = relationship(back_populates="company")
    quest_steps: Mapped[list["QuestStep"]] = relationship(
        back_populates="company", order_by="QuestStep.step_number"
    )


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), unique=True)
    credits_balance: Mapped[int] = mapped_column(Integer, default=50)
    last_daily_regen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_daily_reward_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    daily_streak: Mapped[int] = mapped_column(Integer, default=0)

    company: Mapped["Company"] = relationship(back_populates="wallet")


class SubscriptionStatus(str, enum.Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"
    EXPIRED = "expired"


class Subscription(Base):
    """Polsia-like subscription — task credits per month, separate from Stripe Connect."""
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), unique=True, index=True)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    plan_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # "starter" | "growth" | etc.
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, native_enum=False), default=SubscriptionStatus.TRIAL
    )
    credits_monthly: Mapped[int] = mapped_column(Integer, default=0)    # allocation plan
    credits_remaining: Mapped[int] = mapped_column(Integer, default=0)  # current balance (plan credits)
    credits_used_period: Mapped[int] = mapped_column(Integer, default=0)
    pack_credits: Mapped[int] = mapped_column(Integer, default=0)       # one-shot pack credits
    welcome_bonus_given: Mapped[bool] = mapped_column(Boolean, default=False)
    trial_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped["Company"] = relationship()


class Building(Base):
    __tablename__ = "buildings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    agent_type: Mapped[AgentType] = mapped_column(Enum(AgentType, native_enum=False))
    level: Mapped[int] = mapped_column(Integer, default=1)

    company: Mapped["Company"] = relationship(back_populates="buildings")


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    agent_type: Mapped[AgentType] = mapped_column(Enum(AgentType, native_enum=False, values_callable=lambda x: [e.value for e in x]))
    mission_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[MissionStatus] = mapped_column(Enum(MissionStatus, native_enum=False, values_callable=lambda x: [e.value for e in x]), default=MissionStatus.PENDING)
    source: Mapped[TaskSource] = mapped_column(
        Enum(TaskSource, native_enum=False, values_callable=lambda x: [e.value for e in x]), default=TaskSource.USER
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    queue_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    rejected_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    credits_cost: Mapped[int] = mapped_column(Integer)
    xp_reward: Mapped[int] = mapped_column(Integer, default=0)
    is_auto_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    deliverable_format: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    deliverable: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped["Company"] = relationship(back_populates="missions")
    logs: Mapped[list["MissionLog"]] = relationship(back_populates="mission")


class MissionLog(Base):
    __tablename__ = "mission_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"), index=True)
    step: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text, default="")
    level: Mapped[str] = mapped_column(String(10), default="info")
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    mission: Mapped["Mission"] = relationship(back_populates="logs")


class MemoryCategory(str, enum.Enum):
    PROFILE = "profile"
    MARKET = "market"
    BRAND = "brand"
    COMPETITORS = "competitors"
    PRODUCT = "product"
    STRATEGY = "strategy"
    ANALYTICS = "analytics"


class CompanyMemory(Base):
    __tablename__ = "company_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    category: Mapped[MemoryCategory] = mapped_column(Enum(MemoryCategory, native_enum=False))
    key: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    source_mission_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("missions.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    company: Mapped["Company"] = relationship()
    source_mission: Mapped[Optional["Mission"]] = relationship()


class NotificationType(str, enum.Enum):
    STEP_COMPLETED = "step_completed"
    STEP_UNLOCKED = "step_unlocked"
    STEP_FAILED = "step_failed"
    STEP_AUTO_LAUNCHED = "step_auto_launched"
    CHAIN_COMPLETED = "chain_completed"
    PAYMENT_RECEIVED = "payment_received"
    CEO_NEXT_MOVE = "ceo_next_move"
    SYSTEM = "system"
    ADS = "ads"


class CompanyNotification(Base):
    __tablename__ = "company_notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType, native_enum=False))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text, default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    company: Mapped["Company"] = relationship()


class QuestStepStatus(str, enum.Enum):
    LOCKED = "locked"
    AVAILABLE = "available"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class QuestStep(Base):
    __tablename__ = "quest_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    step_number: Mapped[int] = mapped_column(Integer)
    mission_type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    agent_type: Mapped[AgentType] = mapped_column(Enum(AgentType, native_enum=False))
    status: Mapped[QuestStepStatus] = mapped_column(
        Enum(QuestStepStatus, native_enum=False), default=QuestStepStatus.LOCKED
    )
    mission_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("missions.id"), nullable=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    unlocked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    company: Mapped["Company"] = relationship(back_populates="quest_steps")
    mission: Mapped[Optional["Mission"]] = relationship()


# ---------------------------------------------------------------------------
# Email mutualisé
# ---------------------------------------------------------------------------

class EmailDirection(str, enum.Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class CompanyEmail(Base):
    __tablename__ = "company_emails"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    direction: Mapped[EmailDirection] = mapped_column(
        Enum(EmailDirection, native_enum=False)
    )
    from_address: Mapped[str] = mapped_column(String(320))
    to_address: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(500), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    message_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    company: Mapped["Company"] = relationship()


# ---------------------------------------------------------------------------
# Site artifacts — shared gateway hosting (scalable, 1 gateway for all sites)
# ---------------------------------------------------------------------------

class SiteArtifact(Base):
    """Published website version for a company.

    Replaces per-company Render services. The shared gateway reads this table
    by slug and serves the HTML directly.
    """
    __tablename__ = "site_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    slug: Mapped[str] = mapped_column(String(100), index=True)
    html_content: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_live: Mapped[bool] = mapped_column(Boolean, default=True)
    mission_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("missions.id"), nullable=True, index=True
    )
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    company: Mapped["Company"] = relationship()


# ---------------------------------------------------------------------------
# Company assets (R2 or local)
# ---------------------------------------------------------------------------

class CompanyAsset(Base):
    __tablename__ = "company_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    asset_type: Mapped[str] = mapped_column(String(32), default="image")
    storage_key: Mapped[str] = mapped_column(String(500))
    public_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    company: Mapped["Company"] = relationship()


# ---------------------------------------------------------------------------
# Learnings cross-company
# ---------------------------------------------------------------------------

class Learning(Base):
    __tablename__ = "learnings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    content: Mapped[str] = mapped_column(Text)
    source_company_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("companies.id"), nullable=True, index=True
    )
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    source_company: Mapped[Optional["Company"]] = relationship()


# ---------------------------------------------------------------------------
# Token usage tracking
# ---------------------------------------------------------------------------

class TokenUsage(Base):
    __tablename__ = "token_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"), index=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    provider: Mapped[str] = mapped_column(String(20))  # anthropic | openai
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    mission: Mapped["Mission"] = relationship()
    company: Mapped["Company"] = relationship()


# ---------------------------------------------------------------------------
# Browser session pooling
# ---------------------------------------------------------------------------

class BrowserSession(Base):
    __tablename__ = "browser_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    domain: Mapped[str] = mapped_column(String(255), index=True)
    session_id: Mapped[str] = mapped_column(String(100))
    cookies_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_authenticated: Mapped[bool] = mapped_column(Boolean, default=False)
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ---------------------------------------------------------------------------
# LLM call logging (observability)
# ---------------------------------------------------------------------------

class LLMCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    mission_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("missions.id"), index=True, nullable=True
    )
    company_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("companies.id"), index=True, nullable=True
    )
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(64))
    call_type: Mapped[str] = mapped_column(String(20), default="agent")  # agent | scorer
    system_prompt_hash: Mapped[str] = mapped_column(String(16), default="")
    user_prompt_preview: Mapped[str] = mapped_column(Text, default="")
    response_preview: Mapped[str] = mapped_column(Text, default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(10), default="success")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    skill_version: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ---------------------------------------------------------------------------
# Tool call audit log
# ---------------------------------------------------------------------------

class ToolCallLog(Base):
    __tablename__ = "tool_call_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    mission_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("missions.id"), index=True, nullable=True
    )
    company_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("companies.id"), index=True, nullable=True
    )
    tool_name: Mapped[str] = mapped_column(String(64))
    arguments_json: Mapped[str] = mapped_column(Text, default="{}")
    result_preview: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(10), default="success")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ---------------------------------------------------------------------------
# Recurring missions (scheduling)
# ---------------------------------------------------------------------------

class SkillTier(str, enum.Enum):
    BASIC = "basic"
    EXPERT = "expert"


class SkillShopItem(Base):
    __tablename__ = "skill_shop_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    mission_type: Mapped[str] = mapped_column(String(64), index=True)
    tier: Mapped[SkillTier] = mapped_column(
        Enum(SkillTier, native_enum=False), default=SkillTier.EXPERT
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    credits_cost: Mapped[int] = mapped_column(Integer, default=50)
    icon: Mapped[str] = mapped_column(String(10), default="📖")
    preview_benefits: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CompanySkill(Base):
    __tablename__ = "company_skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    skill_item_id: Mapped[str] = mapped_column(
        ForeignKey("skill_shop_items.id"), index=True
    )
    purchased_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    times_used: Mapped[int] = mapped_column(Integer, default=0)

    company: Mapped["Company"] = relationship()
    skill_item: Mapped["SkillShopItem"] = relationship()


class BetaFeedback(Base):
    __tablename__ = "beta_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    mission_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("missions.id"), nullable=True, index=True
    )
    mission_type: Mapped[str] = mapped_column(String(64), default="")
    used_deliverable: Mapped[bool] = mapped_column(Boolean, default=False)
    rating: Mapped[int] = mapped_column(Integer, default=3)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    company: Mapped["Company"] = relationship()


class RecurringMission(Base):
    __tablename__ = "recurring_missions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    mission_type: Mapped[str] = mapped_column(String(64))
    frequency: Mapped[str] = mapped_column(String(10))  # daily | weekly | monthly
    day_of_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0-6
    day_of_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-28
    hour_utc: Mapped[int] = mapped_column(Integer, default=9)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    company: Mapped["Company"] = relationship()


class AdCampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    BLOCKED = "blocked"


class AdCampaign(Base):
    __tablename__ = "ad_campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    meta_campaign_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    meta_ad_set_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[AdCampaignStatus] = mapped_column(
        Enum(AdCampaignStatus, native_enum=False), default=AdCampaignStatus.DRAFT
    )
    daily_budget_cents: Mapped[int] = mapped_column(Integer, default=0)
    spend_cents: Mapped[int] = mapped_column(Integer, default=0)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    ctr: Mapped[float] = mapped_column(Float, default=0.0)
    cpc_cents: Mapped[int] = mapped_column(Integer, default=0)
    # Polsia-like fields
    targeting_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    objective: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    call_to_action: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    purchase_roas: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hours_since_activation: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reach: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    frequency: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    video_views: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    video_thruplay_watched: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_scale_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_split_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    company: Mapped["Company"] = relationship()
    creatives: Mapped[list["AdCreative"]] = relationship(back_populates="campaign")


class AdCreative(Base):
    __tablename__ = "ad_creatives"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("ad_campaigns.id"), index=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    meta_ad_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    meta_creative_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    video_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    spend_cents: Mapped[int] = mapped_column(Integer, default=0)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    ctr: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    campaign: Mapped["AdCampaign"] = relationship(back_populates="creatives")
    company: Mapped["Company"] = relationship()


class AdSnapshot(Base):
    __tablename__ = "ad_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    campaign_id: Mapped[Optional[str]] = mapped_column(ForeignKey("ad_campaigns.id"), nullable=True)
    spend_cents: Mapped[int] = mapped_column(Integer, default=0)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    ctr: Mapped[float] = mapped_column(Float, default=0.0)
    cpc_cents: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped["Company"] = relationship()


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    type: Mapped[str] = mapped_column(String(20), default="credit")  # "credit" | "debit" | "fee"
    note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped["Company"] = relationship()


# ---------------------------------------------------------------------------
# PaymentLink — liens Stripe créés par l'agent ou le founder (Système B)
# ---------------------------------------------------------------------------

class PaymentLink(Base):
    """Permanent Stripe Payment Link created for a founder's product."""
    __tablename__ = "payment_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    stripe_payment_link_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    url: Mapped[str] = mapped_column(String(500))
    product_name: Mapped[str] = mapped_column(String(255))
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="eur")
    stripe_product_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    stripe_price_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped["Company"] = relationship()


# ---------------------------------------------------------------------------
# God Mode sessions — session autonome achetée séparément (Polsia exact)
# ---------------------------------------------------------------------------

class GodModeSession(Base):
    """One-shot autonomous agent session — does NOT consume task credits."""
    __tablename__ = "god_mode_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    stripe_session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    god_plan_id: Mapped[str] = mapped_column(String(20))  # "god_1h" | "god_24h" ...
    hours: Mapped[int] = mapped_column(Integer, default=1)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | active | expired
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped["Company"] = relationship()


# ---------------------------------------------------------------------------
# Orders — ventes des founders à leurs clients (Système B / Polsia Stripe)
# ---------------------------------------------------------------------------

class Order(Base):
    """Customer purchase on a founder's product via Stripe Checkout / Payment Link."""
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    stripe_payment_intent_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    stripe_session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    customer_email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="eur")
    product_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    meta_event_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped["Company"] = relationship()
