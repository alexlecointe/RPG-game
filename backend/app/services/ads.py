"""Meta Ads orchestration — Polsia-like launch, wallet, monitoring (5 triggers)."""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools.meta_ads_action import (
    create_ad,
    create_ad_set,
    create_ad_creative,
    create_custom_audience,
    create_lookalike_audience,
    get_video,
    list_custom_audiences,
    upload_video,
)
from app.core.config import get_settings
from app.models.entities import (
    AdCampaign,
    AdCampaignStatus,
    AdCreative,
    AdSnapshot,
    Company,
    CompanyAsset,
    CompanyNotification,
    NotificationType,
    Order,
    WalletTransaction,
)
from app.services.site_hosting import build_gateway_url as _build_site_url_gateway
from app.services.site_deploy import build_site_url as _build_site_url_legacy


def _get_company_site_url(company) -> str:
    """Resolve the live site URL: gateway first, legacy Render as fallback."""
    slug = company.slug or ""
    url = _build_site_url_gateway(slug)
    if url:
        return url
    return _build_site_url_legacy(slug, company.render_url) or ""


def _business_objective(company: Company) -> tuple[str, str, int, int]:
    """Return Meta objective defaults by business type."""
    business_type = getattr(getattr(company, "business_type", None), "value", str(getattr(company, "business_type", "")))
    if business_type == "app":
        return "OUTCOME_APP_INSTALLS", "DOWNLOAD", 18, 35
    if business_type == "saas":
        return "OUTCOME_LEADS", "LEARN_MORE", 25, 55
    return "OUTCOME_SALES", "SHOP_NOW", 18, 45


def _default_ad_variants(company: Company) -> list[dict[str, str]]:
    product = (company.product_description or company.mission_statement or company.name).strip()
    product_short = product.split(".")[0].strip()[:90] or company.name
    return [
        {
            "headline": f"{company.name[:26]} est live"[:40],
            "body": f"Decouvre {product_short}. Commande en quelques secondes.",
            "angle": "direct-benefit",
        },
        {
            "headline": "Le produit a tester"[:40],
            "body": f"Une nouvelle offre pensee pour {company.target_audience or 'les premiers clients'}.",
            "angle": "curiosity",
        },
        {
            "headline": "Disponible maintenant"[:40],
            "body": f"Passe a l'action aujourd'hui avec {company.name}.",
            "angle": "urgency",
        },
    ]


def _video_prompt(company: Company, variant: dict[str, str]) -> str:
    product = company.product_description or company.mission_statement or company.name
    audience = company.target_audience or "early adopters"
    return (
        "Vertical 9:16 Meta video ad, 15 seconds. "
        f"Brand: {company.name}. Product: {product}. Audience: {audience}. "
        f"Angle: {variant['angle']}. "
        "Show the product or service in use, fast opening hook, clean premium visuals, "
        "no voiceover, minimal text overlays, clear final CTA."
    )


async def _resolve_meta_video_thumbnail(
    access_token: str,
    video_id: str,
    fallback_url: str = "",
    attempts: int = 12,
    delay_seconds: int = 5,
) -> str:
    """Wait for Meta to finish processing a video and expose a usable thumbnail."""
    resolved = fallback_url or ""
    for idx in range(attempts):
        try:
            meta_video = await get_video(access_token, video_id)
            thumb = meta_video.get("thumbnail_url") or ""
            if thumb:
                return thumb
        except Exception as exc:
            logger.warning("meta_video_thumbnail_fetch_failed", error=str(exc), video_id=video_id, attempt=idx + 1)
        if idx < attempts - 1:
            await asyncio.sleep(delay_seconds)
    return resolved


async def _latest_company_video_urls(db: AsyncSession, company_id: str, limit: int = 3) -> list[str]:
    result = await db.execute(
        select(CompanyAsset)
        .where(CompanyAsset.company_id == company_id, CompanyAsset.asset_type == "video")
        .order_by(CompanyAsset.created_at.desc())
        .limit(limit)
    )
    return [
        asset.public_url
        for asset in result.scalars().all()
        if asset.public_url and asset.public_url.startswith(("http://", "https://"))
    ]


async def _store_ad_video_asset(company: Company, video_url: str, idx: int) -> str:
    """Persist ad videos to R2 when configured, and enforce R2 in prod if requested."""
    settings = get_settings()
    if not video_url:
        return ""

    r2_base = settings.r2_public_url.rstrip("/")
    if r2_base and video_url.startswith(r2_base):
        return video_url

    if settings.ads_video_r2_required and not settings.r2_configured:
        raise ValueError("r2_required_for_ads_video: configure Cloudflare R2 or disable ADS_VIDEO_R2_REQUIRED")

    if not settings.r2_configured:
        return video_url

    if "api.openai.com/v1/videos/" in video_url and "/content" in video_url:
        if not settings.openai_api_key:
            raise ValueError("openai_api_key_required_for_video_download")

        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                resp = await client.get(
                    video_url,
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                )
                resp.raise_for_status()
                content = resp.content
        except Exception as exc:
            raise ValueError(f"openai_video_download_failed: {exc}") from exc

        try:
            from app.services.r2_storage import upload_bytes

            storage_key = f"{company.id}/video/meta-ad-{idx + 1}-{uuid.uuid4().hex[:8]}.mp4"
            return upload_bytes(storage_key, content, "video/mp4")
        except Exception as exc:
            raise ValueError(f"video_store_failed: {exc}") from exc

    from app.agents.tools.store_asset import _execute_store_asset

    raw = await _execute_store_asset(
        company.id,
        f"meta-ad-{idx + 1}.mp4",
        video_url,
        "video",
    )
    try:
        stored = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"video_store_failed: {raw[:200]}") from exc

    if stored.get("error"):
        raise ValueError(f"video_store_failed: {stored['error']}")

    public_url = stored.get("public_url") or video_url
    if settings.ads_video_r2_required and r2_base and not public_url.startswith(r2_base):
        raise ValueError("r2_required_for_ads_video: stored video is not using R2 public URL")
    return public_url

logger = structlog.get_logger()
META_GRAPH = "https://graph.facebook.com/v21.0"

# ---
# Polsia trigger thresholds
# ---
TRIGGER_UNDERPERFORMING_HOURS = 48    # spend=0 after 48h → pause
TRIGGER_ROAS_SCALE_THRESHOLD = 2.0    # ROAS ≥ 2x → suggest scaling
TRIGGER_SCALE_MIN_SPEND_CENTS = 5000  # min $50 spend before scaling recommendation
TRIGGER_SCALE_NOTIFY_INTERVAL_H = 72  # re-notify max every 3 days
TRIGGER_LOOKALIKE_MIN_HOURS = 168     # min 7 days before automatic lookalike creation

# ---
# State contextual messages (Polsia-like copy)
# ---
STATE_MESSAGES: dict[str, str] = {
    "running": "Your ads are running and Meta is using your daily budget across the day.",
    "warming_up": "Meta is in its learning phase — performance data may be volatile for the first 48–72h. No action needed.",
    "paused": "Ads are paused — Meta's learning phase resets after extended pauses, which may reduce early performance when you restart.",
    "winding_down": "Your campaigns are winding down — all active ads have been paused. Results from the last cycle are preserved.",
    "delivery_blocked": "One or more ads were flagged for policy violation. A new creative is being generated automatically.",
    "stale_no_delivery": "Campaign has been live for 48h+ with zero spend. Check your targeting, creative, or billing setup.",
    "card_expired": "Your payment method has expired. Update your card to resume daily top-ups.",
    "payment_method_missing": "No payment method on file. Add a card to enable daily ad spend.",
    "budget_exhausted": "Your ads wallet is exhausted. The next daily top-up must succeed to keep delivery healthy.",
    "no_campaigns": "No ad campaigns yet. Ask the Marketer agent to launch your first Meta Ads campaign.",
    "draft": "Campaign draft created. The Marketer agent will activate it once creatives are ready.",
    "scale_suggested": "A campaign is performing well. Review the suggested budget increase before scaling.",
}

SPLIT_TEST_MIN_HOURS = 120  # 5 days before surfacing split test observation


def _action_type_value(action: dict, action_type: str) -> int:
    if not isinstance(action, dict):
        return 0
    if action.get("action_type") != action_type:
        return 0
    try:
        return int(float(action.get("value", 0) or 0))
    except (TypeError, ValueError):
        return 0


def _parse_actions(actions: list[dict] | None) -> tuple[int, int]:
    """Return (purchases, add_to_cart) from Meta action rows."""
    purchases = 0
    add_to_cart = 0
    for action in actions or []:
        purchases += _action_type_value(action, "purchase")
        purchases += _action_type_value(action, "offsite_conversion.fb_pixel_purchase")
        add_to_cart += _action_type_value(action, "add_to_cart")
        add_to_cart += _action_type_value(action, "offsite_conversion.fb_pixel_add_to_cart")
    return purchases, add_to_cart


async def _notify_ads(
    db: AsyncSession,
    company_id: str,
    title: str,
    message: str,
) -> None:
    db.add(CompanyNotification(
        company_id=company_id,
        type=NotificationType.ADS,
        title=title,
        message=message,
    ))


async def set_daily_budget(db: AsyncSession, company_id: str, budget_cents: int) -> Company:
    company = await db.get(Company, company_id)
    if not company:
        raise ValueError("company_not_found")
    company.daily_ads_budget_cents = max(100, budget_cents)
    await db.commit()
    return company


async def charge_ads_wallet(db: AsyncSession, company: Company) -> int:
    """Credit ads wallet from daily budget (80% to spend after platform fee)."""
    settings = get_settings()
    if company.daily_ads_budget_cents <= 0:
        return 0
    fee_pct = settings.ads_platform_fee_percent
    spendable = int(company.daily_ads_budget_cents * (100 - fee_pct) / 100)
    company.ads_wallet_balance_cents = (company.ads_wallet_balance_cents or 0) + spendable

    # Record wallet credit transaction
    txn = WalletTransaction(
        company_id=company.id,
        amount_cents=spendable,
        type="credit",
        note=f"Daily top-up ({100 - fee_pct}% of ${company.daily_ads_budget_cents / 100:.2f} budget)",
    )
    db.add(txn)
    await db.commit()
    return spendable


async def ensure_ads_wallet_funded(
    db: AsyncSession,
    company: Company,
    *,
    allow_manual_fallback: bool = True,
) -> dict:
    """Top up the ads wallet before launch/cycle if the spendable balance is empty."""
    if not company.daily_ads_budget_cents or company.daily_ads_budget_cents <= 0:
        return {"skipped": True, "reason": "no_daily_budget"}

    if (company.ads_wallet_balance_cents or 0) > 0:
        return {
            "skipped": True,
            "reason": "wallet_already_funded",
            "balance_cents": company.ads_wallet_balance_cents or 0,
        }

    try:
        from app.services.billing import charge_ads_wallet_stripe

        result = await charge_ads_wallet_stripe(db, company)
    except Exception as exc:
        logger.warning("ads_wallet_stripe_topup_failed", company_id=company.id, error=str(exc))
        result = {"skipped": True, "reason": "stripe_error", "message": str(exc)}

    if not result.get("skipped"):
        await db.refresh(company)
        result["balance_cents"] = company.ads_wallet_balance_cents or 0
        return result

    reason = result.get("reason")
    if allow_manual_fallback and reason == "no_stripe_configured":
        added = await charge_ads_wallet(db, company)
        await db.refresh(company)
        return {
            "charged_cents": 0,
            "spendable_cents": added,
            "balance_cents": company.ads_wallet_balance_cents or 0,
            "manual_fallback": True,
            "reason": "no_stripe_configured",
        }

    return result


async def launch_meta_campaign(
    db: AsyncSession,
    company: Company,
    campaign_name: str,
    daily_budget_cents: int,
    video_urls: list[str],
    headlines: list[str],
    bodies: list[str],
    countries: list[str] | None = None,
    age_min: int = 18,
    age_max: int = 65,
    call_to_action: str = "SHOP_NOW",
    objective: str = "OUTCOME_SALES",
) -> AdCampaign:
    """Create Meta campaign + ad set + ads with video creatives (PAUSED first, then ACTIVE)."""
    if not video_urls:
        raise ValueError("video_urls_required: provide at least 1 video URL")

    settings = get_settings()
    token = settings.meta_capi_token
    ad_account = settings.meta_ad_account_id
    if not token or not ad_account:
        raise ValueError("meta_not_configured")

    act_id = ad_account if ad_account.startswith("act_") else f"act_{ad_account}"
    budget = daily_budget_cents or company.daily_ads_budget_cents or 1000
    geo = countries or ["FR"]
    dsa_beneficiary = (settings.meta_dsa_beneficiary or company.name or "").strip()
    dsa_payor = (settings.meta_dsa_payor or dsa_beneficiary).strip()

    targeting_data = {
        "geo_locations": {"countries": geo},
        "age_min": age_min,
        "age_max": age_max,
        "targeting_automation": {"advantage_audience": 0},
    }

    campaign = AdCampaign(
        company_id=company.id,
        name=campaign_name or f"{company.name} Ads",
        daily_budget_cents=budget,
        status=AdCampaignStatus.DRAFT,
        objective=objective,
        call_to_action=call_to_action,
        targeting_json=json.dumps(targeting_data),
    )
    db.add(campaign)
    await db.flush()

    optimization_goal = {
        "OUTCOME_SALES": "OFFSITE_CONVERSIONS" if settings.meta_pixel_id else "LINK_CLICKS",
        "OUTCOME_APP_INSTALLS": "APP_INSTALLS",
        "OUTCOME_LEADS": "LEAD_GENERATION",
    }.get(objective, "LINK_CLICKS")

    async with httpx.AsyncClient(timeout=60) as client:
        # Create campaign in PAUSED state first (Meta review)
        resp = await client.post(
            f"{META_GRAPH}/{act_id}/campaigns",
            data={
                "access_token": token,
                "name": campaign.name,
                "objective": objective,
                "status": "PAUSED",
                "special_ad_categories": "[]",
                "is_adset_budget_sharing_enabled": "false",
            },
        )
        if resp.status_code >= 400:
            raise ValueError(f"meta_campaign_create_failed: {resp.text[:500]}")
        meta_campaign_id = resp.json().get("id")
        campaign.meta_campaign_id = meta_campaign_id

        # Ad set PAUSED
        adset_payload = {
            "access_token": token,
            "name": f"{campaign.name} AdSet",
            "campaign_id": meta_campaign_id,
            "daily_budget": str(budget),
            "billing_event": "IMPRESSIONS",
            "optimization_goal": optimization_goal,
            "bid_amount": "200",
            "status": "PAUSED",
            "targeting": json.dumps(targeting_data),
            "dsa_beneficiary": dsa_beneficiary,
            "dsa_payor": dsa_payor,
        }
        if settings.meta_pixel_id and objective == "OUTCOME_SALES":
            adset_payload["promoted_object"] = json.dumps({
                "pixel_id": settings.meta_pixel_id,
                "custom_event_type": "PURCHASE",
            })

        resp = await client.post(
            f"{META_GRAPH}/{act_id}/adsets",
            data=adset_payload,
        )
        if resp.status_code >= 400:
            raise ValueError(f"meta_adset_create_failed: {resp.text[:500]}")
        ad_set_id = resp.json().get("id")
        campaign.meta_ad_set_id = ad_set_id

        link_url = _get_company_site_url(company)
        created_ad_ids: list[str] = []

        for i, video_url in enumerate(video_urls[:3]):
            title = headlines[i] if i < len(headlines) and headlines[i] else campaign.name
            body_text = bodies[i] if i < len(bodies) and bodies[i] else ""

            creative = AdCreative(
                campaign_id=campaign.id,
                company_id=company.id,
                title=title,
                body=body_text,
                video_url=video_url,
                status="draft",
            )
            db.add(creative)
            await db.flush()

            try:
                video_resp = await upload_video(token, ad_account, video_url, title)
                video_id = video_resp.get("video_id", "")
                thumbnail_url = company.product_image_url or ""
                if video_id:
                    thumbnail_url = await _resolve_meta_video_thumbnail(
                        token,
                        video_id,
                        fallback_url=thumbnail_url,
                    )
                if video_id and settings.meta_page_id:
                    cr_resp = await create_ad_creative(
                        token, ad_account, video_id, title, body_text, link_url,
                        call_to_action=call_to_action,
                        thumbnail_url=thumbnail_url,
                    )
                    creative.meta_creative_id = cr_resp.get("creative_id")
                    creative.thumbnail_url = thumbnail_url or None
                    if creative.meta_creative_id and ad_set_id:
                        ad_resp = await create_ad(
                            token,
                            ad_account,
                            ad_set_id,
                            creative.meta_creative_id,
                            title,
                            "PAUSED",
                        )
                        creative.meta_ad_id = ad_resp.get("ad_id")
                        if creative.meta_ad_id:
                            created_ad_ids.append(creative.meta_ad_id)
                        creative.status = "active"
                logger.info(
                    "ad_creative_stored",
                    creative_id=creative.id,
                    meta_ad_id=creative.meta_ad_id,
                )
            except Exception as exc:
                logger.warning("meta_creative_pipeline_failed", error=str(exc), video_url=video_url[:80])

        # Activate delivery objects now that creatives are ready
        if campaign.meta_ad_set_id:
            try:
                await client.post(
                    f"{META_GRAPH}/{campaign.meta_ad_set_id}",
                    data={"access_token": token, "status": "ACTIVE"},
                )
            except Exception as exc:
                logger.warning("adset_activate_failed", error=str(exc), ad_set_id=campaign.meta_ad_set_id)

        for ad_id in created_ad_ids:
            try:
                await client.post(
                    f"{META_GRAPH}/{ad_id}",
                    data={"access_token": token, "status": "ACTIVE"},
                )
            except Exception as exc:
                logger.warning("ad_activate_failed", error=str(exc), ad_id=ad_id)

        if campaign.meta_campaign_id:
            try:
                await client.post(
                    f"{META_GRAPH}/{campaign.meta_campaign_id}",
                    data={"access_token": token, "status": "ACTIVE"},
                )
            except Exception as exc:
                logger.warning("campaign_activate_failed", error=str(exc))

    campaign.status = AdCampaignStatus.ACTIVE
    await db.commit()
    await db.refresh(campaign)
    return campaign


async def launch_ads_v1(
    db: AsyncSession,
    company: Company,
    campaign_name: str = "",
    daily_budget_cents: int | None = None,
    video_urls: list[str] | None = None,
    headlines: list[str] | None = None,
    bodies: list[str] | None = None,
    countries: list[str] | None = None,
    age_min: int | None = None,
    age_max: int | None = None,
    call_to_action: str | None = None,
    objective: str | None = None,
    auto_generate_videos: bool = True,
) -> AdCampaign:
    """Deterministic Polsia-style launch path for the Ads mission.

    The agent can still provide videos/copy, but this path makes the launch
    robust when it only has company context and a budget.
    """
    default_objective, default_cta, default_age_min, default_age_max = _business_objective(company)
    objective = objective or default_objective
    call_to_action = call_to_action or default_cta
    age_min = age_min or default_age_min
    age_max = age_max or default_age_max
    budget = daily_budget_cents or company.daily_ads_budget_cents or 0
    if budget <= 0:
        raise ValueError("ads_budget_required")

    funding = await ensure_ads_wallet_funded(db, company)
    if funding.get("skipped") and funding.get("reason") in {
        "card_expired",
        "payment_method_missing",
        "stripe_error",
    }:
        raise ValueError(f"ads_wallet_topup_failed: {funding.get('reason')}")

    variants = _default_ad_variants(company)
    resolved_headlines = [
        (headlines[i] if headlines and i < len(headlines) and headlines[i] else variants[i]["headline"])[:40]
        for i in range(3)
    ]
    resolved_bodies = [
        (bodies[i] if bodies and i < len(bodies) and bodies[i] else variants[i]["body"])
        for i in range(3)
    ]

    resolved_videos = list(video_urls or [])[:3]
    if len(resolved_videos) < 3:
        for url in await _latest_company_video_urls(db, company.id, limit=3 - len(resolved_videos)):
            if url not in resolved_videos:
                resolved_videos.append(url)

    if len(resolved_videos) < 3 and auto_generate_videos and not resolved_videos:
        from app.agents.tools.generate_video import generate_video

        # For a cold start with no uploaded videos, generate one hero video first
        # so the launch can proceed quickly, then reuse it across the first ad set.
        generated = await generate_video(
            _video_prompt(company, variants[0]),
            duration_seconds=15,
            aspect_ratio="9:16",
        )
        if generated:
            resolved_videos.append(generated)

    if not resolved_videos:
        raise ValueError(
            "video_urls_required: provide video URLs or configure OPENAI_VIDEO_MODEL/REPLICATE_API_TOKEN for auto-generation"
        )

    while len(resolved_videos) < 3:
        resolved_videos.append(resolved_videos[-1])

    stored_videos: list[str] = []
    for idx, url in enumerate(resolved_videos[:3]):
        stored_url = await _store_ad_video_asset(company, url, idx)
        if stored_url:
            stored_videos.append(stored_url)

    if not stored_videos:
        raise ValueError("video_urls_required: no public/stored video URL available for Meta upload")

    return await launch_meta_campaign(
        db=db,
        company=company,
        campaign_name=campaign_name or f"{company.name} Meta Ads V1",
        daily_budget_cents=budget,
        video_urls=stored_videos[:3],
        headlines=resolved_headlines,
        bodies=resolved_bodies,
        countries=countries or ["FR", "BE", "CH"],
        age_min=age_min,
        age_max=age_max,
        call_to_action=call_to_action,
        objective=objective,
    )


async def _auto_refresh_creative(
    db: AsyncSession,
    camp: AdCampaign,
    company: Company,
    token: str,
    ad_account: str,
) -> None:
    """Trigger 2: generate new video (Sora → Replicate) → upload → swap creative (best-effort)."""
    settings = get_settings()
    video_gen_available = bool(
        (settings.openai_api_key and settings.openai_video_model)
        or settings.replicate_api_token
    )
    if not video_gen_available:
        logger.warning("trigger2_no_video_provider", campaign_id=camp.id)
        return

    # Find the most recent creative to get headline/body copy
    result = await db.execute(
        select(AdCreative)
        .where(AdCreative.campaign_id == camp.id)
        .order_by(AdCreative.created_at.desc())
        .limit(1)
    )
    old_creative = result.scalar_one_or_none()
    if not old_creative:
        return

    try:
        from app.agents.tools.generate_video import generate_video as gen_video

        company_desc = company.product_description or company.mission_statement or company.name or "product"
        prompt = (
            f"Professional vertical video ad (9:16) for: {old_creative.title}. "
            f"Brand: {company_desc}. "
            "Style: clean, modern, high energy. Show the product in action. "
            "No voiceover needed. 15 seconds. No text overlays."
        )
        new_video_url = await gen_video(prompt, duration_seconds=15, aspect_ratio="9:16")
        if not new_video_url:
            logger.warning("trigger2_video_generation_failed", campaign_id=camp.id)
            return
        new_video_url = await _store_ad_video_asset(company, new_video_url, 0)

        link_url = _get_company_site_url(company)

        # Upload to Meta
        video_resp = await upload_video(token, ad_account, new_video_url, old_creative.title)
        video_id = video_resp.get("video_id", "")
        if not video_id or not settings.meta_page_id:
            return

        cr_resp = await create_ad_creative(
            token, ad_account, video_id,
            old_creative.title, old_creative.body, link_url,
            call_to_action=camp.call_to_action or "SHOP_NOW",
        )
        new_meta_creative_id = cr_resp.get("creative_id")
        if not new_meta_creative_id or not camp.meta_ad_set_id:
            return

        ad_resp = await create_ad(
            token, ad_account, camp.meta_ad_set_id,
            new_meta_creative_id, f"{old_creative.title} (refreshed)", "ACTIVE",
        )
        new_meta_ad_id = ad_resp.get("ad_id")

        # Pause the blocked ad
        if old_creative.meta_ad_id:
            async with httpx.AsyncClient(timeout=30) as c:
                try:
                    await c.post(
                        f"{META_GRAPH}/{old_creative.meta_ad_id}",
                        data={"access_token": token, "status": "PAUSED"},
                    )
                except Exception:
                    pass

        # Persist new creative
        new_creative = AdCreative(
            campaign_id=camp.id,
            company_id=camp.company_id,
            title=f"{old_creative.title} (refreshed)",
            body=old_creative.body,
            video_url=new_video_url,
            meta_creative_id=new_meta_creative_id,
            meta_ad_id=new_meta_ad_id,
            status="active",
        )
        db.add(new_creative)

        # Unblock the campaign
        camp.status = AdCampaignStatus.ACTIVE
        async with httpx.AsyncClient(timeout=30) as c:
            try:
                await c.post(
                    f"{META_GRAPH}/{camp.meta_campaign_id}",
                    data={"access_token": token, "status": "ACTIVE"},
                )
            except Exception:
                pass

        logger.info("trigger2_creative_refreshed", campaign_id=camp.id, new_ad_id=new_meta_ad_id)

    except Exception as exc:
        logger.warning("trigger2_refresh_failed", campaign_id=camp.id, error=str(exc))


async def apply_scale_campaign(
    db: AsyncSession,
    company_id: str,
    campaign_id: str,
    scale_pct: int = 20,
) -> dict:
    """User-triggered: increase campaign daily budget by scale_pct (default +20%)."""
    camp = await db.get(AdCampaign, campaign_id)
    if not camp or camp.company_id != company_id:
        raise ValueError("campaign_not_found")

    settings = get_settings()
    token = settings.meta_capi_token
    old_budget = camp.daily_budget_cents or 0
    new_budget = int(old_budget * (1 + scale_pct / 100))

    if token and camp.meta_ad_set_id:
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                await client.post(
                    f"{META_GRAPH}/{camp.meta_ad_set_id}",
                    data={"access_token": token, "daily_budget": str(new_budget)},
                )
            except Exception as exc:
                logger.warning("apply_scale_meta_failed", campaign_id=camp.id, error=str(exc))

    camp.daily_budget_cents = new_budget
    camp.last_scale_notified_at = None  # reset so future recommendations can fire
    await db.commit()
    logger.info("apply_scale_done", campaign_id=camp.id, old=old_budget, new=new_budget)
    return {"campaign_id": campaign_id, "old_budget_cents": old_budget, "new_budget_cents": new_budget}


async def apply_split_winner(
    db: AsyncSession,
    company_id: str,
    campaign_id: str,
) -> dict:
    """User-triggered: pull ad-level insights, pause losers, scale winner adset budget."""
    camp = await db.get(AdCampaign, campaign_id)
    if not camp or camp.company_id != company_id:
        raise ValueError("campaign_not_found")
    if not camp.meta_ad_set_id:
        raise ValueError("no_adset")

    settings = get_settings()
    token = settings.meta_capi_token
    if not token:
        raise ValueError("meta_not_configured")

    paused_count = 0
    winner_ad_id = None

    async with httpx.AsyncClient(timeout=30) as client:
        # Pull ads in adset
        resp = await client.get(
            f"{META_GRAPH}/{camp.meta_ad_set_id}/ads",
            params={"access_token": token, "fields": "id,name,status,effective_status"},
        )
        if resp.status_code != 200:
            raise ValueError("meta_ads_fetch_failed")
        ads = [a for a in resp.json().get("data", []) if a.get("effective_status") not in ("DELETED", "ARCHIVED")]
        if len(ads) < 2:
            raise ValueError("not_enough_ads")

        # Score each ad
        ad_scores: list[tuple[str, float]] = []
        for ad in ads:
            ins = await client.get(
                f"{META_GRAPH}/{ad['id']}/insights",
                params={"access_token": token, "fields": "spend,purchase_roas,clicks", "date_preset": "last_7_days"},
            )
            if ins.status_code != 200:
                continue
            row = (ins.json().get("data") or [{}])[0]
            ad_spend = float(row.get("spend", 0) or 0)
            roas_list = row.get("purchase_roas", []) or []
            ad_roas = sum(float(r.get("value", 0)) for r in roas_list) if roas_list else 0.0
            score = ad_roas if ad_roas > 0 else (float(row.get("clicks", 0) or 0) / max(ad_spend, 0.01))
            ad_scores.append((ad["id"], score))

        if not ad_scores:
            raise ValueError("no_insights")

        ad_scores.sort(key=lambda x: x[1], reverse=True)
        winner_ad_id, winner_score = ad_scores[0]

        if winner_score == 0:
            raise ValueError("no_winner_data")

        # Pause losers (score < 50% of winner)
        for ad_id, score in ad_scores[1:]:
            if score < winner_score * 0.5:
                try:
                    await client.post(
                        f"{META_GRAPH}/{ad_id}",
                        data={"access_token": token, "status": "PAUSED"},
                    )
                    paused_count += 1
                except Exception:
                    pass

        # Scale winner adset budget +20%
        new_budget = int(camp.daily_budget_cents * 1.2)
        try:
            await client.post(
                f"{META_GRAPH}/{camp.meta_ad_set_id}",
                data={"access_token": token, "daily_budget": str(new_budget)},
            )
            camp.daily_budget_cents = new_budget
        except Exception as exc:
            logger.warning("apply_split_scale_failed", error=str(exc))

    camp.last_split_notified_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("apply_split_winner_done", campaign_id=camp.id, winner=winner_ad_id, paused=paused_count)
    return {
        "campaign_id": campaign_id,
        "winner_ad_id": winner_ad_id,
        "paused_losers": paused_count,
        "new_budget_cents": camp.daily_budget_cents,
    }


async def _apply_split_test(
    db: AsyncSession,
    client: httpx.AsyncClient,
    camp: AdCampaign,
    company: Company | None,
    token: str,
    company_id: str,
) -> None:
    """Split test observation: pull ad-level insights and notify owner of potential winner.

    No automatic Meta actions (pause/scale) until Polsia confirms the exact
    winner metric, loser threshold, and auto vs recommendation behavior.
    """
    try:
        resp = await client.get(
            f"{META_GRAPH}/{camp.meta_ad_set_id}/ads",
            params={
                "access_token": token,
                "fields": "id,name,status,effective_status",
            },
        )
        if resp.status_code != 200:
            return
        ads = resp.json().get("data", [])
        if len(ads) < 2:
            return

        ad_scores: list[tuple[str, str, float]] = []
        for ad in ads:
            if ad.get("effective_status") in ("DELETED", "ARCHIVED"):
                continue
            ins_resp = await client.get(
                f"{META_GRAPH}/{ad['id']}/insights",
                params={
                    "access_token": token,
                    "fields": "spend,purchase_roas,clicks",
                    "date_preset": "last_7_days",
                },
            )
            if ins_resp.status_code != 200:
                continue
            ins_data = ins_resp.json().get("data", [{}])
            ins_row = ins_data[0] if ins_data else {}
            ad_spend = float(ins_row.get("spend", 0) or 0)
            roas_list = ins_row.get("purchase_roas", []) or []
            ad_roas = sum(float(r.get("value", 0)) for r in roas_list) if roas_list else 0.0
            score = ad_roas if ad_roas > 0 else (float(ins_row.get("clicks", 0) or 0) / max(ad_spend, 0.01))
            ad_scores.append((ad["id"], ad.get("name", ad["id"]), score))

        if not ad_scores:
            return

        ad_scores.sort(key=lambda x: x[2], reverse=True)
        winner_id, winner_name, winner_score = ad_scores[0]

        if winner_score == 0:
            return

        # Notification only — no automatic Meta action
        # Notify at most once per campaign (last_split_notified_at)
        if company and not camp.last_split_notified_at:
            loser_count = sum(1 for _, _, s in ad_scores[1:] if s < winner_score * 0.5)
            notif = CompanyNotification(
                company_id=company_id,
                type=NotificationType.ADS,
                title="Split test — résultat disponible",
                message=(
                    f"Campagne \"{camp.name}\" : après {int(SPLIT_TEST_MIN_HOURS / 24)} jours, "
                    f"la pub \"{winner_name}\" semble la plus performante"
                    + (f" ({loser_count} autre(s) sous-performante(s))" if loser_count else "")
                    + ". Consulte tes stats Meta pour décider de la suite."
                ),
            )
            db.add(notif)
            camp.last_split_notified_at = datetime.now(timezone.utc)
            logger.info(
                "split_test_observation",
                campaign_id=camp.id,
                winner_ad=winner_id,
                winner_score=winner_score,
                total_ads=len(ad_scores),
            )

    except Exception as exc:
        logger.warning("split_test_error", campaign_id=camp.id, error=str(exc))


async def _auto_create_lookalike(
    db: AsyncSession,
    company: Company,
    camp: AdCampaign,
    token: str,
    ad_account: str,
) -> None:
    """Best-effort ROAS trigger: create website source audience + 1% lookalike."""
    settings = get_settings()
    if not settings.meta_pixel_id or not token or not ad_account:
        return

    try:
        source_name = f"RPG {company.slug or company.id} website visitors/source"
        lookalike_name = f"RPG {company.slug or company.id} lookalike 1pct"

        audiences = await list_custom_audiences(token, ad_account)
        existing = audiences.get("audiences", [])
        existing_lookalike = next((a for a in existing if a.get("name") == lookalike_name), None)
        if existing_lookalike:
            logger.info("lookalike_already_exists", campaign_id=camp.id, audience_id=existing_lookalike.get("id"))
            return

        source = next((a for a in existing if a.get("name") == source_name), None)
        if not source:
            source = await create_custom_audience(
                token,
                ad_account,
                name=source_name,
                subtype="WEBSITE",
                retention_days=30,
            )
            if source.get("error"):
                logger.warning("lookalike_source_create_failed", campaign_id=camp.id, error=source.get("error"))
                return

        source_id = source.get("id") or source.get("audience_id")
        if not source_id:
            return

        result = await create_lookalike_audience(
            token,
            ad_account,
            source_id,
            ratio=0.01,
            countries=["FR"],
            name=lookalike_name,
        )
        if result.get("created"):
            lookalike_adset_id = None
            lookalike_id = result.get("audience_id")
            if camp.meta_campaign_id and lookalike_id:
                adset = await create_ad_set(
                    token,
                    ad_account,
                    camp.meta_campaign_id,
                    f"{camp.name} Lookalike 1%",
                    daily_budget_cents=max(camp.daily_budget_cents or 1000, 1000),
                    status="PAUSED",
                    countries=["FR"],
                    age_min=18,
                    age_max=45,
                    objective=camp.objective or "OUTCOME_SALES",
                    custom_audience_ids=[lookalike_id],
                )
                lookalike_adset_id = adset.get("ad_set_id")

                creative_result = await db.execute(
                    select(AdCreative)
                    .where(
                        AdCreative.campaign_id == camp.id,
                        AdCreative.meta_creative_id.is_not(None),
                    )
                    .order_by(AdCreative.ctr.desc(), AdCreative.created_at.desc())
                    .limit(1)
                )
                creative = creative_result.scalar_one_or_none()
                if creative and creative.meta_creative_id and lookalike_adset_id:
                    await create_ad(
                        token,
                        ad_account,
                        lookalike_adset_id,
                        creative.meta_creative_id,
                        f"{creative.title} Lookalike",
                        "PAUSED",
                    )

            await _notify_ads(
                db,
                company.id,
                "Lookalike audience créée",
                (
                    f"La campagne \"{camp.name}\" dépasse le seuil ROAS. "
                    "Une audience lookalike 1% a été créée"
                    + (f" avec un adset prêt ({lookalike_adset_id})." if lookalike_adset_id else ".")
                ),
            )
            logger.info(
                "lookalike_created",
                campaign_id=camp.id,
                audience_id=result.get("audience_id"),
                adset_id=lookalike_adset_id,
            )

    except Exception as exc:
        logger.warning("lookalike_auto_failed", campaign_id=camp.id, error=str(exc))


async def monitor_campaigns(db: AsyncSession, company_id: str) -> list[AdSnapshot]:
    """Pull insights and apply 5 Polsia triggers."""
    settings = get_settings()
    token = settings.meta_capi_token
    if not token:
        return []

    result = await db.execute(
        select(AdCampaign).where(AdCampaign.company_id == company_id)
    )
    campaigns = list(result.scalars().all())
    snapshots: list[AdSnapshot] = []
    now = datetime.now(timezone.utc)

    # Reload company for wallet balance
    company = await db.get(Company, company_id)

    async with httpx.AsyncClient(timeout=30) as client:
        for camp in campaigns:
            if not camp.meta_campaign_id:
                continue
            if camp.status == AdCampaignStatus.BLOCKED:
                # Still attempt Trigger 2 auto-refresh for blocked campaigns
                ad_account = settings.meta_ad_account_id or ""
                await _auto_refresh_creative(db, camp, company, token, ad_account)
                continue

            try:
                resp = await client.get(
                    f"{META_GRAPH}/{camp.meta_campaign_id}/insights",
                    params={
                        "access_token": token,
                        "fields": "spend,impressions,clicks,ctr,cpc,purchase_roas,actions,reach,frequency,video_30_sec_viewed,video_thruplay_watched",
                        "date_preset": "last_7_days",
                    },
                )
                if resp.status_code != 200:
                    continue

                data = resp.json().get("data", [{}])
                row = data[0] if data else {}
                spend = float(row.get("spend", 0) or 0)
                impressions = int(row.get("impressions", 0) or 0)
                clicks = int(row.get("clicks", 0) or 0)
                ctr = float(row.get("ctr", 0) or 0)
                cpc = float(row.get("cpc", 0) or 0)
                reach = int(row.get("reach", 0) or 0)
                frequency = float(row.get("frequency", 0) or 0)
                video_views = int(row.get("video_30_sec_viewed", 0) or 0)
                thruplay = int(row.get("video_thruplay_watched", 0) or 0)
                purchases, add_to_cart = _parse_actions(row.get("actions", []) or [])

                # ROAS: sum of purchase_roas values
                roas_list = row.get("purchase_roas", []) or []
                purchase_roas = sum(float(r.get("value", 0)) for r in roas_list) if roas_list else 0.0

                prev_spend = camp.spend_cents or 0

                camp.spend_cents = int(spend * 100)
                camp.impressions = impressions
                camp.clicks = clicks
                camp.ctr = ctr
                camp.cpc_cents = int(cpc * 100)
                camp.purchase_roas = purchase_roas
                camp.reach = reach
                camp.frequency = frequency
                camp.video_views = video_views
                camp.video_thruplay_watched = thruplay

                # Calculate hours since activation
                hours_alive = 0.0
                if camp.created_at:
                    created_aware = camp.created_at.replace(tzinfo=timezone.utc) if camp.created_at.tzinfo is None else camp.created_at
                    hours_alive = (now - created_aware).total_seconds() / 3600
                camp.hours_since_activation = int(hours_alive)

                snap = AdSnapshot(
                    company_id=company_id,
                    campaign_id=camp.id,
                    spend_cents=camp.spend_cents,
                    impressions=impressions,
                    clicks=clicks,
                    ctr=ctr,
                    cpc_cents=camp.cpc_cents,
                    note=f"Monitor {now.isoformat()} purchases={purchases} add_to_cart={add_to_cart}",
                )
                db.add(snap)
                snapshots.append(snap)

                # Record debit transaction when spend increased
                new_spend = camp.spend_cents or 0
                if new_spend > prev_spend and company:
                    delta = new_spend - prev_spend
                    company.ads_wallet_balance_cents = (company.ads_wallet_balance_cents or 0) - delta
                    txn = WalletTransaction(
                        company_id=company_id,
                        amount_cents=-delta,
                        type="debit",
                        note=f"Meta spend on \"{camp.name}\"",
                    )
                    db.add(txn)

                # --- 5 Polsia triggers ---

                # Trigger 3 — LEARNING_PHASE: campaign < 48h, do nothing
                if hours_alive < TRIGGER_UNDERPERFORMING_HOURS:
                    logger.info("ads_trigger_learning_phase", campaign_id=camp.id, hours=hours_alive)
                    continue

                # Trigger 1 — UNDERPERFORMING: spend=0 after 48h
                if spend == 0 and hours_alive >= TRIGGER_UNDERPERFORMING_HOURS:
                    camp.status = AdCampaignStatus.PAUSED
                    if token and camp.meta_campaign_id:
                        try:
                            await client.post(
                                f"{META_GRAPH}/{camp.meta_campaign_id}",
                                data={"access_token": token, "status": "PAUSED"},
                            )
                        except Exception:
                            pass
                    if company:
                        await _notify_ads(
                            db,
                            company_id,
                            "Campagne en pause",
                            f"La campagne \"{camp.name}\" n'a eu aucune dépense après {int(hours_alive)}h. Vérifiez votre creative ou votre ciblage.",
                        )
                    logger.warning("ads_trigger_underperforming", campaign_id=camp.id)
                    continue

                # Trigger 2 — DELIVERY_BLOCKED: check Meta effective_status
                try:
                    status_resp = await client.get(
                        f"{META_GRAPH}/{camp.meta_campaign_id}",
                        params={
                            "access_token": token,
                            "fields": "effective_status",
                        },
                    )
                    if status_resp.status_code == 200:
                        eff_status = status_resp.json().get("effective_status", "")
                        if "DISAPPROVED" in eff_status or "POLICY" in eff_status:
                            camp.status = AdCampaignStatus.BLOCKED
                            if company:
                                await _notify_ads(
                                    db,
                                    company_id,
                                    "Creative bloquée par Meta",
                                    f"La campagne \"{camp.name}\" a été bloquée pour violation de politique. Une nouvelle creative est générée automatiquement.",
                                )
                            logger.warning("ads_trigger_delivery_blocked", campaign_id=camp.id)
                            # Auto-refresh creative immediately
                            ad_account = settings.meta_ad_account_id or ""
                            await _auto_refresh_creative(db, camp, company, token, ad_account)
                            continue
                except Exception:
                    pass

                # Trigger 5 — ROAS ≥ 2x + min spend → suggest scaling (max once per 72h)
                if (
                    purchase_roas >= TRIGGER_ROAS_SCALE_THRESHOLD
                    and (camp.spend_cents or 0) >= TRIGGER_SCALE_MIN_SPEND_CENTS
                    and hours_alive >= TRIGGER_UNDERPERFORMING_HOURS
                    and company
                ):
                    last_notified = camp.last_scale_notified_at
                    already_notified_recently = (
                        last_notified is not None
                        and (now - (last_notified if last_notified.tzinfo else last_notified.replace(tzinfo=timezone.utc))).total_seconds()
                        < TRIGGER_SCALE_NOTIFY_INTERVAL_H * 3600
                    )
                    if not already_notified_recently:
                        await _notify_ads(
                            db,
                            company_id,
                            "Scaling recommandé",
                            (
                                f"La campagne \"{camp.name}\" a un ROAS de {purchase_roas:.1f}x "
                                f"et ${(camp.spend_cents or 0) / 100:.0f} de dépenses. "
                                "Tu peux augmenter ton budget pour maximiser les résultats."
                            ),
                        )
                        camp.last_scale_notified_at = now
                        logger.info("ads_trigger_roas_scale", campaign_id=camp.id, roas=purchase_roas)

                    if hours_alive >= TRIGGER_LOOKALIKE_MIN_HOURS:
                        await _auto_create_lookalike(
                            db,
                            company,
                            camp,
                            token,
                            settings.meta_ad_account_id or "",
                        )

                # Trigger 4 — BUDGET_EXHAUSTED: owner must fix billing/top-up.
                if company and (company.ads_wallet_balance_cents or 0) <= 0 and company.daily_ads_budget_cents > 0:
                    logger.warning(
                        "ads_trigger_budget_exhausted",
                        campaign_id=camp.id,
                        wallet=company.ads_wallet_balance_cents,
                    )

                # Split test J5 — ad-level performance analysis
                if hours_alive >= SPLIT_TEST_MIN_HOURS and camp.meta_ad_set_id:
                    await _apply_split_test(db, client, camp, company, token, company_id)

            except Exception as exc:
                logger.warning("ads_monitor_failed", campaign_id=camp.id, error=str(exc))

    await db.commit()
    return snapshots


async def run_ads_daily_cycle(
    db: AsyncSession,
    company_id: str,
    charge_wallet: bool = True,
) -> dict:
    """Polsia-like daily ads loop: top up, monitor, summarize, and notify."""
    company = await db.get(Company, company_id)
    if not company:
        return {"skipped": True, "reason": "company_not_found"}

    charge_result: dict | None = None
    active_result = await db.execute(
        select(AdCampaign).where(
            AdCampaign.company_id == company_id,
            AdCampaign.status == AdCampaignStatus.ACTIVE,
        )
    )
    active_campaigns = list(active_result.scalars().all())

    if charge_wallet and active_campaigns and not company.ads_winding_down:
        try:
            charge_result = await ensure_ads_wallet_funded(db, company)
        except Exception as exc:
            charge_result = {"skipped": True, "reason": "charge_error", "message": str(exc)}
            logger.warning("ads_daily_cycle_charge_failed", company_id=company_id, error=str(exc))

    snapshots = await monitor_campaigns(db, company_id)
    summary = await get_ads_summary(db, company_id)

    if active_campaigns or summary["owner_actionable"]:
        title = "Rapport Ads quotidien"
        if summary["owner_actionable"]:
            title = "Action requise sur les Ads"
        message = (
            f"Etat: {summary['state']}. "
            f"Spend 7j: ${summary['total_spend_cents'] / 100:.2f}. "
            f"CTR: {summary['ctr']:.1f}%. "
            f"ROAS: {summary.get('purchase_roas', 0):.1f}x."
        )
        if summary.get("actionable_message"):
            message = f"{message} {summary['actionable_message']}"
        await _notify_ads(db, company_id, title, message)
        await db.commit()

    return {
        "company_id": company_id,
        "charged": charge_result,
        "snapshots": len(snapshots),
        "state": summary["state"],
        "owner_actionable": summary["owner_actionable"],
    }


async def _reconcile_meta_campaign_objects(
    db: AsyncSession,
    campaign: AdCampaign,
    creatives: list[AdCreative],
) -> dict:
    """Fill local Meta ids when a launch created objects but did not persist every id."""
    if not campaign.meta_campaign_id:
        return {"changed": False, "reason": "no_meta_campaign_id"}

    needs_adset = not campaign.meta_ad_set_id
    should_fetch_ads = bool(creatives)
    if not needs_adset and not should_fetch_ads:
        return {"changed": False, "reason": "already_synced"}

    settings = get_settings()
    token = settings.meta_capi_token
    if not token:
        return {"changed": False, "reason": "meta_token_missing"}

    changed = False
    synced_ads = 0
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if needs_adset:
                resp = await client.get(
                    f"{META_GRAPH}/{campaign.meta_campaign_id}/adsets",
                    params={
                        "access_token": token,
                        "fields": "id,name,status,effective_status",
                        "limit": "10",
                    },
                )
                resp.raise_for_status()
                adsets = resp.json().get("data") or []
                if adsets:
                    campaign.meta_ad_set_id = adsets[0].get("id")
                    changed = True

            if campaign.meta_ad_set_id and should_fetch_ads:
                if settings.meta_pixel_id and campaign.objective == "OUTCOME_SALES":
                    fix_resp = await client.post(
                        f"{META_GRAPH}/{campaign.meta_ad_set_id}",
                        data={
                            "access_token": token,
                            "promoted_object": json.dumps({
                                "pixel_id": settings.meta_pixel_id,
                                "custom_event_type": "PURCHASE",
                            }),
                        },
                    )
                    fix_resp.raise_for_status()

                resp = await client.get(
                    f"{META_GRAPH}/{campaign.meta_ad_set_id}/ads",
                    params={
                        "access_token": token,
                        "fields": "id,name,status,effective_status,creative{id,name}",
                        "limit": "50",
                    },
                )
                resp.raise_for_status()
                ads = resp.json().get("data") or []
                ads_by_name = {str(ad.get("name") or ""): ad for ad in ads}
                for creative in creatives:
                    ad = ads_by_name.get(creative.title)
                    if not ad:
                        continue
                    meta_ad_id = ad.get("id")
                    meta_creative = ad.get("creative") or {}
                    meta_creative_id = meta_creative.get("id")
                    meta_status = str(ad.get("effective_status") or ad.get("status") or "").lower()

                    if meta_ad_id and creative.meta_ad_id != meta_ad_id:
                        creative.meta_ad_id = meta_ad_id
                        changed = True
                    if meta_creative_id and creative.meta_creative_id != meta_creative_id:
                        creative.meta_creative_id = meta_creative_id
                        changed = True
                    if meta_status and creative.status != meta_status:
                        creative.status = meta_status
                        changed = True
                    synced_ads += 1

        if changed:
            await db.commit()
            await db.refresh(campaign)
            for creative in creatives:
                await db.refresh(creative)
        return {
            "changed": changed,
            "meta_campaign_id": campaign.meta_campaign_id,
            "meta_ad_set_id": campaign.meta_ad_set_id,
            "synced_ads": synced_ads,
        }
    except Exception as exc:
        logger.warning(
            "meta_campaign_reconcile_failed",
            campaign_id=campaign.id,
            meta_campaign_id=campaign.meta_campaign_id,
            error=str(exc),
        )
        return {"changed": False, "reason": "meta_error", "error": str(exc)}


async def get_ads_summary(db: AsyncSession, company_id: str) -> dict:
    """Return Polsia-like ads summary: global state + aggregated metrics + wallet."""
    company = await db.get(Company, company_id)
    if not company:
        raise ValueError("company_not_found")

    camp_result = await db.execute(
        select(AdCampaign).where(AdCampaign.company_id == company_id)
    )
    campaigns = list(camp_result.scalars().all())

    creative_result = await db.execute(
        select(AdCreative).where(AdCreative.company_id == company_id)
    )
    creatives = list(creative_result.scalars().all())

    visible_campaigns = _visible_ads_campaigns(campaigns)
    visible_campaign_ids = {c.id for c in visible_campaigns}
    visible_creatives = [
        creative for creative in creatives
        if creative.campaign_id in visible_campaign_ids
    ]
    for campaign in visible_campaigns:
        await _reconcile_meta_campaign_objects(
            db,
            campaign,
            [creative for creative in visible_creatives if creative.campaign_id == campaign.id],
        )

    order_result = await db.execute(
        select(Order).where(Order.company_id == company_id)
    )
    orders = list(order_result.scalars().all())

    # Aggregate metrics
    metric_campaigns = visible_campaigns
    total_spend_cents = sum(c.spend_cents or 0 for c in metric_campaigns)
    total_impressions = sum(c.impressions or 0 for c in metric_campaigns)
    total_clicks = sum(c.clicks or 0 for c in metric_campaigns)
    total_reach = sum(c.reach or 0 for c in metric_campaigns)
    total_video_views = sum(c.video_views or 0 for c in metric_campaigns)
    total_video_thruplays = sum(c.video_thruplay_watched or 0 for c in metric_campaigns)
    active_frequency_values = [c.frequency or 0 for c in metric_campaigns if c.frequency]
    avg_frequency = (
        sum(active_frequency_values) / len(active_frequency_values)
        if active_frequency_values else 0.0
    )
    total_revenue_cents = sum(o.amount_cents or 0 for o in orders)
    total_purchases = len(orders)
    ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0.0
    cpc_cents = (total_spend_cents // total_clicks) if total_clicks > 0 else 0
    campaign_roas_values = [c.purchase_roas or 0 for c in metric_campaigns if c.purchase_roas]
    meta_purchase_roas = (
        sum(campaign_roas_values) / len(campaign_roas_values)
        if campaign_roas_values else 0.0
    )
    order_roas = (total_revenue_cents / total_spend_cents) if total_spend_cents > 0 else 0.0
    purchase_roas = round(meta_purchase_roas or order_roas, 2)

    # 7-day spend rollup from AdSnapshot (1 value per day)
    spend_rollup_7d = await _compute_spend_rollup_7d(db, company_id)

    # Global state determination
    state_campaigns = visible_campaigns
    active_camps = [c for c in state_campaigns if c.status == AdCampaignStatus.ACTIVE]
    blocked_camps = [c for c in state_campaigns if c.status == AdCampaignStatus.BLOCKED]
    paused_camps = [c for c in state_campaigns if c.status == AdCampaignStatus.PAUSED]

    wallet = company.ads_wallet_balance_cents or 0
    daily_budget = company.daily_ads_budget_cents or 0

    owner_actionable = False
    actionable_message = None

    # Payment state overrides everything — user must fix payment first
    payment_state = company.ads_payment_state or None

    if payment_state in ("card_expired", "payment_method_missing"):
        state = payment_state
        owner_actionable = True
        actionable_message = (
            "Votre carte a expiré. Mettez-la à jour pour que vos pubs continuent."
            if payment_state == "card_expired"
            else "Aucun moyen de paiement valide. Ajoutez une carte pour activer les recharges automatiques."
        )
    elif not state_campaigns:
        state = "no_campaigns"
    elif blocked_camps:
        state = "delivery_blocked"
        owner_actionable = True
        actionable_message = "Une ou plusieurs campagnes sont bloquées par Meta. Une nouvelle creative est générée automatiquement."
    elif active_camps:
        youngest = min((c.hours_since_activation or 0) for c in active_camps)
        stale = any(
            (c.hours_since_activation or 0) >= TRIGGER_UNDERPERFORMING_HOURS
            and (c.spend_cents or 0) == 0
            for c in active_camps
        )
        if stale:
            state = "stale_no_delivery"
            owner_actionable = True
            actionable_message = "Campagne active depuis 48h+ sans dépense. Vérifiez le ciblage ou les créatifs."
        elif wallet <= 0 and daily_budget > 0:
            state = "budget_exhausted"
            owner_actionable = True
            actionable_message = "Le wallet ads est épuisé. Vérifiez que la recharge quotidienne Stripe passe bien."
        elif youngest < 48:
            state = "warming_up"
        elif any((c.purchase_roas or 0) >= TRIGGER_ROAS_SCALE_THRESHOLD for c in active_camps):
            state = "scale_suggested"
            owner_actionable = True
            actionable_message = "Une campagne dépasse le seuil ROAS. Validez une hausse de budget ou un lookalike."
        else:
            state = "running"
    elif paused_camps:
        if getattr(company, "ads_winding_down", False):
            state = "winding_down"
            owner_actionable = True
            actionable_message = "Vos campagnes s'arrêtent progressivement. Les résultats de ce cycle sont conservés."
        else:
            state = "paused"
            owner_actionable = True
            actionable_message = "Vos campagnes sont en pause. Rechargez le wallet ou relancez manuellement."
    else:
        state = "draft"
        if any(c.name == "Preparing Meta Ads" and not c.meta_campaign_id for c in state_campaigns):
            actionable_message = "Préparation des vidéos et des créas en cours. Le premier lancement peut prendre quelques minutes."

    state_message = STATE_MESSAGES.get(state)

    agent_view = {
        "customer_framing": state_message,
        "owner_actionable": owner_actionable,
        "balance_usd_to_show": round(wallet / 100, 2),
        "next_best_action": actionable_message or (
            "Laissez Meta apprendre pendant 48-72h."
            if state == "warming_up" else "Surveillez les performances."
        ),
    }

    return {
        "state": state,
        "state_message": state_message,
        "wallet_balance_cents": wallet,
        "daily_budget_cents": daily_budget,
        "total_spend_cents": total_spend_cents,
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "total_reach": total_reach,
        "avg_frequency": round(avg_frequency, 2),
        "total_video_views": total_video_views,
        "total_video_thruplays": total_video_thruplays,
        "total_purchases": total_purchases,
        "total_revenue_cents": total_revenue_cents,
        "purchase_roas": purchase_roas,
        "ctr": round(ctr, 2),
        "cpc_cents": cpc_cents,
        "spend_rollup_7d": spend_rollup_7d,
        "campaigns": visible_campaigns,
        "creatives": visible_creatives,
        "owner_actionable": owner_actionable,
        "actionable_message": actionable_message,
        "agent_view": agent_view,
    }


async def reconcile_company_ads_with_meta(db: AsyncSession, company_id: str) -> dict:
    """Explicitly reconcile the current visible local campaign with Meta objects."""
    result = await db.execute(
        select(AdCampaign).where(AdCampaign.company_id == company_id)
    )
    campaigns = list(result.scalars().all())
    visible_campaigns = _visible_ads_campaigns(campaigns)
    if not visible_campaigns:
        return {"reconciled": False, "reason": "no_visible_campaign"}

    campaign = visible_campaigns[0]
    creative_result = await db.execute(
        select(AdCreative).where(AdCreative.campaign_id == campaign.id)
    )
    creatives = list(creative_result.scalars().all())
    reconcile_result = await _reconcile_meta_campaign_objects(db, campaign, creatives)
    return {
        "reconciled": bool(reconcile_result.get("changed")),
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "meta_campaign_id": campaign.meta_campaign_id,
        "meta_ad_set_id": campaign.meta_ad_set_id,
        "creative_count": len(creatives),
        "creatives": [
            {
                "id": creative.id,
                "title": creative.title,
                "status": creative.status,
                "meta_ad_id": creative.meta_ad_id,
                "meta_creative_id": creative.meta_creative_id,
            }
            for creative in creatives
        ],
        "meta": reconcile_result,
    }


async def cleanup_ads_test_rows(db: AsyncSession, company_id: str) -> dict:
    """Remove old local ads launch attempts and keep the current visible campaign."""
    result = await db.execute(
        select(AdCampaign).where(AdCampaign.company_id == company_id)
    )
    campaigns = list(result.scalars().all())
    keep_campaigns = _visible_ads_campaigns(campaigns)
    keep_ids = {campaign.id for campaign in keep_campaigns}
    remove_ids = [campaign.id for campaign in campaigns if campaign.id not in keep_ids]

    if not remove_ids:
        return {
            "kept_campaign_ids": list(keep_ids),
            "removed_campaigns": 0,
            "removed_creatives": 0,
            "removed_snapshots": 0,
        }

    creatives_result = await db.execute(
        select(AdCreative.id).where(AdCreative.campaign_id.in_(remove_ids))
    )
    creative_ids = list(creatives_result.scalars().all())

    snapshots_result = await db.execute(
        select(AdSnapshot.id).where(AdSnapshot.campaign_id.in_(remove_ids))
    )
    snapshot_ids = list(snapshots_result.scalars().all())

    await db.execute(delete(AdCreative).where(AdCreative.campaign_id.in_(remove_ids)))
    await db.execute(delete(AdSnapshot).where(AdSnapshot.campaign_id.in_(remove_ids)))
    await db.execute(delete(AdCampaign).where(AdCampaign.id.in_(remove_ids)))
    await db.commit()

    return {
        "kept_campaign_ids": list(keep_ids),
        "removed_campaigns": len(remove_ids),
        "removed_creatives": len(creative_ids),
        "removed_snapshots": len(snapshot_ids),
    }


def _visible_ads_campaigns(campaigns: list[AdCampaign]) -> list[AdCampaign]:
    """Keep the dashboard focused on the current delivery attempt."""
    delivery_statuses = {
        AdCampaignStatus.ACTIVE,
        AdCampaignStatus.PAUSED,
        AdCampaignStatus.BLOCKED,
    }
    delivery_campaigns = [
        campaign for campaign in campaigns
        if campaign.status in delivery_statuses and campaign.meta_campaign_id
    ]
    if delivery_campaigns:
        return [max(
            delivery_campaigns,
            key=lambda campaign: campaign.created_at or datetime.min.replace(tzinfo=timezone.utc),
        )]

    pending = [
        campaign for campaign in campaigns
        if campaign.name == "Preparing Meta Ads" and campaign.status == AdCampaignStatus.DRAFT
    ]
    if pending:
        return [max(
            pending,
            key=lambda campaign: campaign.created_at or datetime.min.replace(tzinfo=timezone.utc),
        )]

    return []


async def _compute_spend_rollup_7d(db: AsyncSession, company_id: str) -> list[int]:
    """Compute daily spend totals for the last 7 days from AdSnapshot records."""
    now = datetime.now(timezone.utc)
    rollup = []
    for days_ago in range(6, -1, -1):
        day_start = (now - timedelta(days=days_ago)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        result = await db.execute(
            select(AdSnapshot).where(
                AdSnapshot.company_id == company_id,
                AdSnapshot.created_at >= day_start,
                AdSnapshot.created_at < day_end,
            )
        )
        snaps = list(result.scalars().all())
        day_spend = max((s.spend_cents for s in snaps), default=0) if snaps else 0
        rollup.append(day_spend)
    return rollup


async def get_wallet_transactions(
    db: AsyncSession, company_id: str, limit: int = 20
) -> list[WalletTransaction]:
    """Return recent wallet transactions for the company."""
    result = await db.execute(
        select(WalletTransaction)
        .where(WalletTransaction.company_id == company_id)
        .order_by(WalletTransaction.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
