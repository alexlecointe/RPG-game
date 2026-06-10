"""Meta Ads orchestration — Polsia-like launch, wallet, monitoring (5 triggers)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools.meta_ads_action import (
    create_ad,
    create_ad_creative,
    upload_video,
)
from app.core.config import get_settings
from app.models.entities import (
    AdCampaign,
    AdCampaignStatus,
    AdCreative,
    AdSnapshot,
    Company,
    CompanyNotification,
    NotificationType,
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

logger = structlog.get_logger()
META_GRAPH = "https://graph.facebook.com/v21.0"

# ---
# Polsia trigger thresholds
# ---
TRIGGER_UNDERPERFORMING_HOURS = 48    # spend=0 after 48h → pause
TRIGGER_ROAS_SCALE_THRESHOLD = 2.0    # ROAS ≥ 2x → suggest scaling
TRIGGER_SCALE_MIN_SPEND_CENTS = 5000  # min $50 spend before scaling recommendation
TRIGGER_SCALE_NOTIFY_INTERVAL_H = 72  # re-notify max every 3 days

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
    "no_campaigns": "No ad campaigns yet. Ask the Marketer agent to launch your first Meta Ads campaign.",
    "draft": "Campaign draft created. The Marketer agent will activate it once creatives are ready.",
}

SPLIT_TEST_MIN_HOURS = 120  # 5 days before surfacing split test observation


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

    targeting_data = {
        "geo_locations": {"countries": geo},
        "age_min": age_min,
        "age_max": age_max,
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
        "OUTCOME_SALES": "LINK_CLICKS",
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
            },
        )
        resp.raise_for_status()
        meta_campaign_id = resp.json().get("id")
        campaign.meta_campaign_id = meta_campaign_id

        # Ad set PAUSED
        resp = await client.post(
            f"{META_GRAPH}/{act_id}/adsets",
            data={
                "access_token": token,
                "name": f"{campaign.name} AdSet",
                "campaign_id": meta_campaign_id,
                "daily_budget": str(budget),
                "billing_event": "IMPRESSIONS",
                "optimization_goal": optimization_goal,
                "bid_amount": "200",
                "status": "PAUSED",
                "targeting": json.dumps(targeting_data),
            },
        )
        resp.raise_for_status()
        ad_set_id = resp.json().get("id")
        campaign.meta_ad_set_id = ad_set_id

        link_url = _get_company_site_url(company)

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
                if video_id and settings.meta_page_id:
                    cr_resp = await create_ad_creative(
                        token, ad_account, video_id, title, body_text, link_url,
                        call_to_action=call_to_action,
                    )
                    creative.meta_creative_id = cr_resp.get("creative_id")
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
                        creative.status = "active"
                logger.info(
                    "ad_creative_stored",
                    creative_id=creative.id,
                    meta_ad_id=creative.meta_ad_id,
                )
            except Exception as exc:
                logger.warning("meta_video_upload_failed", error=str(exc), video_url=video_url[:80])

        # Activate campaign now that creatives are ready
        if campaign.meta_campaign_id:
            try:
                await client.post(
                    f"{META_GRAPH}/{campaign.meta_campaign_id}",
                    data={"access_token": token, "status": "ACTIVE"},
                )
            except Exception as exc:
                logger.warning("campaign_activate_failed", error=str(exc))

    campaign.status = AdCampaignStatus.ACTIVE
    company.ads_wallet_balance_cents = (company.ads_wallet_balance_cents or 0) - budget
    await db.commit()
    await db.refresh(campaign)
    return campaign


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

        company_desc = company.description or company.name or "product"
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
                body=(
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
                        "fields": "spend,impressions,clicks,ctr,cpc,purchase_roas,reach,frequency,video_30_sec_viewed,video_thruplay_watched",
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
                    note=f"Monitor {now.isoformat()}",
                )
                db.add(snap)
                snapshots.append(snap)

                # Record debit transaction when spend increased
                new_spend = camp.spend_cents or 0
                if new_spend > prev_spend and company:
                    delta = new_spend - prev_spend
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
                        notif = CompanyNotification(
                            company_id=company_id,
                            type=NotificationType.ADS,
                            title="Campagne en pause",
                            body=f"La campagne \"{camp.name}\" n'a eu aucune dépense après {int(hours_alive)}h. Vérifiez votre creative ou votre ciblage.",
                        )
                        db.add(notif)
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
                                notif = CompanyNotification(
                                    company_id=company_id,
                                    type=NotificationType.ADS,
                                    title="Creative bloquée par Meta",
                                    body=f"La campagne \"{camp.name}\" a été bloquée pour violation de politique. Une nouvelle creative est générée automatiquement.",
                                )
                                db.add(notif)
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
                        notif = CompanyNotification(
                            company_id=company_id,
                            type=NotificationType.ADS,
                            title="Scaling recommandé",
                            body=(
                                f"La campagne \"{camp.name}\" a un ROAS de {purchase_roas:.1f}x "
                                f"et ${(camp.spend_cents or 0) / 100:.0f} de dépenses. "
                                "Tu peux augmenter ton budget pour maximiser les résultats."
                            ),
                        )
                        db.add(notif)
                        camp.last_scale_notified_at = now
                        logger.info("ads_trigger_roas_scale", campaign_id=camp.id, roas=purchase_roas)

                # Split test J5 — ad-level performance analysis
                if hours_alive >= SPLIT_TEST_MIN_HOURS and camp.meta_ad_set_id:
                    await _apply_split_test(db, client, camp, company, token, company_id)

            except Exception as exc:
                logger.warning("ads_monitor_failed", campaign_id=camp.id, error=str(exc))

    if snapshots:
        await db.commit()
    return snapshots


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

    # Aggregate metrics
    total_spend_cents = sum(c.spend_cents or 0 for c in campaigns)
    total_impressions = sum(c.impressions or 0 for c in campaigns)
    total_clicks = sum(c.clicks or 0 for c in campaigns)
    ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0.0
    cpc_cents = (total_spend_cents // total_clicks) if total_clicks > 0 else 0

    # 7-day spend rollup from AdSnapshot (1 value per day)
    spend_rollup_7d = await _compute_spend_rollup_7d(db, company_id)

    # Global state determination
    active_camps = [c for c in campaigns if c.status == AdCampaignStatus.ACTIVE]
    blocked_camps = [c for c in campaigns if c.status == AdCampaignStatus.BLOCKED]
    paused_camps = [c for c in campaigns if c.status == AdCampaignStatus.PAUSED]

    wallet = company.ads_wallet_balance_cents or 0

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
    elif not campaigns:
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
        elif youngest < 48:
            state = "warming_up"
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

    state_message = STATE_MESSAGES.get(state)

    daily_budget = company.daily_ads_budget_cents or 0

    return {
        "state": state,
        "state_message": state_message,
        "wallet_balance_cents": wallet,
        "daily_budget_cents": daily_budget,
        "total_spend_cents": total_spend_cents,
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "ctr": round(ctr, 2),
        "cpc_cents": cpc_cents,
        "spend_rollup_7d": spend_rollup_7d,
        "campaigns": campaigns,
        "creatives": creatives,
        "owner_actionable": owner_actionable,
        "actionable_message": actionable_message,
    }


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
