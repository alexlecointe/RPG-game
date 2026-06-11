from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.models.entities import AgentType, BusinessType, MissionStatus, QuestStepStatus


class UserCreate(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=255)


class UserOut(BaseModel):
    id: str
    device_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    mission_statement: str = ""
    product_description: str = ""
    target_audience: str = ""
    competitor_url: Optional[str] = None
    business_type: BusinessType = BusinessType.ECOMMERCE


class BuildingOut(BaseModel):
    id: str
    agent_type: AgentType
    level: int

    model_config = {"from_attributes": True}


class WalletOut(BaseModel):
    credits_balance: int
    credits_cap: int
    daily_free_credits: int

    model_config = {"from_attributes": True}


class CompanyOut(BaseModel):
    id: str
    name: str
    slug: Optional[str] = None
    mission_statement: str
    product_description: str
    target_audience: str
    business_type: BusinessType
    level: int
    xp: int
    buildings: list[BuildingOut]
    render_url: Optional[str] = None
    site_url: Optional[str] = None
    site_version: Optional[int] = None  # version number of the live site artifact
    site_status: str = "not_created"  # not_created | publishing | live | failed
    stripe_connect_status: str = "not_started"  # not_started | pending | ready
    daily_ads_budget_cents: int = 0
    ads_wallet_balance_cents: int = 0
    auto_pilot: bool = False
    wallet: WalletOut
    product_image_url: Optional[str] = None

    model_config = {"from_attributes": True}


class MissionCatalogItem(BaseModel):
    mission_type: str
    agent_type: AgentType
    title: str
    description: str
    credits_cost: int
    estimated_minutes: int
    output_format: Literal["html", "markdown", "json"]
    complexity: int = 3  # 1-5, tasks above 5 are rejected (Polsia pattern)
    max_images: int = 20
    max_tool_iterations: int = 5
    max_context_tokens: int = 4000
    preferred_provider: str = ""
    preferred_model: str = ""


class MissionCreate(BaseModel):
    mission_type: str = Field(..., min_length=1, max_length=64)


class MissionOut(BaseModel):
    id: str
    company_id: str
    agent_type: AgentType
    mission_type: str
    status: MissionStatus
    source: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    queue_order: Optional[int] = None
    rejected_reason: Optional[str] = None
    credits_cost: int
    xp_reward: int
    deliverable_format: Optional[str]
    deliverable: Optional[str]
    quality_score: Optional[float] = None
    quality_feedback: Optional[str] = None
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class MissionLogOut(BaseModel):
    step: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DailyRewardOut(BaseModel):
    credits_awarded: int
    streak: int
    bonus_active: bool


class ActivityFeedOut(BaseModel):
    mission_id: str
    agent_type: AgentType
    mission_type: str
    mission_status: MissionStatus
    step: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MissionSplitItem(BaseModel):
    mission_type: str
    title: str
    credits_cost: int
    complexity: int


class MissionPreviewOut(BaseModel):
    mission_type: str
    title: str
    description: str
    credits_cost: int
    credits_remaining: int
    can_afford: bool
    estimated_minutes: int
    complexity: int
    max_images: int
    agent_type: AgentType
    suggested_split: list[MissionSplitItem] = []


class RecurringMissionCreate(BaseModel):
    mission_type: str = Field(..., min_length=1, max_length=64)
    frequency: Literal["daily", "weekly", "monthly"]
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    day_of_month: Optional[int] = Field(None, ge=1, le=28)
    hour_utc: int = Field(9, ge=0, le=23)


class RecurringMissionOut(BaseModel):
    id: str
    company_id: str
    mission_type: str
    frequency: str
    day_of_week: Optional[int]
    day_of_month: Optional[int]
    hour_utc: int
    is_active: bool
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Admin Dashboard
# ---------------------------------------------------------------------------


class AdminOverview(BaseModel):
    total_companies: int
    total_missions: int
    missions_by_status: dict[str, int]
    total_tokens: int
    total_cost_usd: float
    error_rate: float
    period_days: int


class AdminCompanyRow(BaseModel):
    id: str
    name: str
    slug: Optional[str] = None
    business_type: str
    level: int
    mission_count: int
    total_tokens: int
    total_cost_usd: float
    avg_quality_score: Optional[float]
    last_mission_at: Optional[datetime]
    created_at: datetime


class AdminMissionRow(BaseModel):
    id: str
    company_id: str
    company_name: str
    mission_type: str
    agent_type: AgentType
    status: MissionStatus
    quality_score: Optional[float]
    token_cost_usd: float
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]


class AdminTokenSpendRow(BaseModel):
    date: str
    provider: str
    model: str
    total_tokens: int
    total_cost_usd: float
    call_count: int


class AdminErrorRow(BaseModel):
    id: str
    company_id: str
    company_name: str
    mission_type: str
    error_message: Optional[str]
    created_at: datetime


class AdminToolUsageRow(BaseModel):
    tool_name: str
    total_calls: int
    error_count: int
    error_rate: float
    avg_duration_ms: float


# ---------------------------------------------------------------------------
# Skill Shop
# ---------------------------------------------------------------------------


class SkillShopItemOut(BaseModel):
    id: str
    mission_type: str
    tier: str
    title: str
    description: str
    credits_cost: int
    icon: str
    preview_benefits: Optional[str]
    owned: bool = False

    model_config = {"from_attributes": True}


class CompanySkillOut(BaseModel):
    id: str
    mission_type: str
    tier: str
    title: str
    icon: str
    purchased_at: datetime
    times_used: int

    model_config = {"from_attributes": True}


class SkillPurchaseOut(BaseModel):
    success: bool
    skill: CompanySkillOut
    credits_remaining: int


class BetaFeedbackCreate(BaseModel):
    mission_id: Optional[str] = None
    mission_type: str = Field("", max_length=64)
    used_deliverable: bool = False
    rating: int = Field(3, ge=1, le=5)
    comment: str = Field("", max_length=500)


class BetaFeedbackOut(BaseModel):
    id: str
    mission_type: str
    used_deliverable: bool
    rating: int
    created_at: datetime

    model_config = {"from_attributes": True}


class QuestStepOut(BaseModel):
    id: str
    step_number: int
    mission_type: str
    title: str
    description: str
    agent_type: AgentType
    status: QuestStepStatus
    mission_id: Optional[str]
    building_name: str = ""
    unlocked_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class StripeStatusOut(BaseModel):
    status: str
    charges_enabled: bool = False
    payouts_enabled: bool = False


class StripeOnboardingCreate(BaseModel):
    country: Optional[str] = Field(
        None,
        min_length=2,
        max_length=2,
        description="ISO 3166-1 alpha-2 country code for the Connect account.",
    )


class StripeOnboardingOut(BaseModel):
    url: str


class AdCampaignOut(BaseModel):
    id: str
    company_id: str
    name: str
    status: str
    daily_budget_cents: int
    spend_cents: int
    impressions: int
    clicks: int
    ctr: float
    cpc_cents: int
    meta_campaign_id: Optional[str] = None
    targeting_json: Optional[str] = None
    objective: Optional[str] = None
    call_to_action: Optional[str] = None
    purchase_roas: Optional[float] = None
    hours_since_activation: Optional[int] = None
    reach: Optional[int] = None
    frequency: Optional[float] = None
    video_views: Optional[int] = None
    video_thruplay_watched: Optional[int] = None

    model_config = {"from_attributes": True}


class AdCreativeOut(BaseModel):
    id: str
    campaign_id: str
    title: str
    body: str
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    status: str
    spend_cents: int
    impressions: int
    clicks: int
    ctr: float

    model_config = {"from_attributes": True}


class AdsSummaryOut(BaseModel):
    state: str
    state_message: Optional[str] = None
    wallet_balance_cents: int
    daily_budget_cents: int
    total_spend_cents: int
    total_impressions: int
    total_clicks: int
    total_reach: int = 0
    avg_frequency: float = 0.0
    total_video_views: int = 0
    total_video_thruplays: int = 0
    total_purchases: int = 0
    total_revenue_cents: int = 0
    purchase_roas: float = 0.0
    ctr: float
    cpc_cents: int
    spend_rollup_7d: list[int] = Field(default_factory=list)
    campaigns: list[AdCampaignOut]
    creatives: list[AdCreativeOut]
    owner_actionable: bool
    actionable_message: Optional[str] = None
    agent_view: dict = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class WalletTransactionOut(BaseModel):
    id: str
    company_id: str
    amount_cents: int
    type: str
    note: str
    created_at: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Billing — Polsia-like subscription + credit packs
# ---------------------------------------------------------------------------

class SubscriptionOut(BaseModel):
    status: str
    plan_id: Optional[str] = None
    plan_label: Optional[str] = None
    credits_remaining: int = 0
    pack_credits: int = 0
    total_credits: int = 0
    credits_used_period: int = 0
    credits_monthly: int = 0
    trial_end: Optional[str] = None
    current_period_end: Optional[str] = None
    owner_actionable: bool = False
    actionable_message: Optional[str] = None

    model_config = {"from_attributes": True}


class BillingPlanOut(BaseModel):
    id: str
    label: str
    cents: int
    credits: int
    price_display: str
    is_current: bool = False


class CreditPackOut(BaseModel):
    id: str
    label: str
    cents: int
    credits: int
    price_display: str


class BillingPlansResponse(BaseModel):
    plans: list[BillingPlanOut]
    packs: list[CreditPackOut]
    current_subscription: Optional[SubscriptionOut] = None


class CheckoutSessionOut(BaseModel):
    checkout_url: str
