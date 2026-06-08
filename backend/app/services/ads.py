"""Meta Ads orchestration — Polsia-like launch, wallet, monitoring."""
from __future__ import annotations

import json
from datetime import datetime, timezone

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
from app.models.entities import AdCampaign, AdCampaignStatus, AdCreative, AdSnapshot, Company
from app.services.site_deploy import build_site_url

logger = structlog.get_logger()
META_GRAPH = "https://graph.facebook.com/v21.0"


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
) -> AdCampaign:
    """Create ACTIVE Meta campaign + ad set + ads with video creatives."""
    settings = get_settings()
    token = settings.meta_capi_token
    ad_account = settings.meta_ad_account_id
    if not token or not ad_account:
        raise ValueError("meta_not_configured")

    act_id = ad_account if ad_account.startswith("act_") else f"act_{ad_account}"
    budget = daily_budget_cents or company.daily_ads_budget_cents or 1000

    campaign = AdCampaign(
        company_id=company.id,
        name=campaign_name or f"{company.name} Ads",
        daily_budget_cents=budget,
        status=AdCampaignStatus.DRAFT,
    )
    db.add(campaign)
    await db.flush()

    async with httpx.AsyncClient(timeout=60) as client:
        # Campaign ACTIVE
        resp = await client.post(
            f"{META_GRAPH}/{act_id}/campaigns",
            data={
                "access_token": token,
                "name": campaign.name,
                "objective": "OUTCOME_SALES",
                "status": "ACTIVE",
                "special_ad_categories": "[]",
            },
        )
        resp.raise_for_status()
        meta_campaign_id = resp.json().get("id")
        campaign.meta_campaign_id = meta_campaign_id

        # Ad set ACTIVE
        resp = await client.post(
            f"{META_GRAPH}/{act_id}/adsets",
            data={
                "access_token": token,
                "name": f"{campaign.name} AdSet",
                "campaign_id": meta_campaign_id,
                "daily_budget": str(budget),
                "billing_event": "IMPRESSIONS",
                "optimization_goal": "LINK_CLICKS",
                "bid_amount": "200",
                "status": "ACTIVE",
                "targeting": json.dumps({"geo_locations": {"countries": ["FR"]}}),
            },
        )
        resp.raise_for_status()
        ad_set_id = resp.json().get("id")
        campaign.meta_ad_set_id = ad_set_id

        link_url = build_site_url(company.slug or "", company.render_url) or ""

        for i, video_url in enumerate(video_urls[:3]):
            title = headlines[i] if i < len(headlines) else campaign.name
            body_text = bodies[i] if i < len(bodies) else ""

            creative = AdCreative(
                campaign_id=campaign.id,
                company_id=company.id,
                title=title,
                body=body_text,
                video_url=video_url,
                status="active",
            )
            db.add(creative)
            await db.flush()

            try:
                video_resp = await upload_video(token, ad_account, video_url, title)
                video_id = video_resp.get("video_id", "")
                if video_id and settings.meta_page_id:
                    cr_resp = await create_ad_creative(
                        token, ad_account, video_id, title, body_text, link_url
                    )
                    creative.meta_creative_id = cr_resp.get("creative_id")
                    if creative.meta_creative_id and ad_set_id:
                        ad_resp = await create_ad(
                            token,
                            ad_account,
                            ad_set_id,
                            creative.meta_creative_id,
                            title,
                            "ACTIVE",
                        )
                        creative.meta_ad_id = ad_resp.get("ad_id")
                logger.info(
                    "ad_creative_stored",
                    creative_id=creative.id,
                    meta_ad_id=creative.meta_ad_id,
                )
            except Exception as exc:
                logger.warning("meta_video_upload_failed", error=str(exc), video_url=video_url[:80])

    campaign.status = AdCampaignStatus.ACTIVE
    company.ads_wallet_balance_cents = max(
        0, (company.ads_wallet_balance_cents or 0) - budget
    )
    await db.commit()
    await db.refresh(campaign)
    return campaign


async def monitor_campaigns(db: AsyncSession, company_id: str) -> list[AdSnapshot]:
    """Pull insights and snapshot performance."""
    settings = get_settings()
    token = settings.meta_capi_token
    ad_account = settings.meta_ad_account_id
    if not token or not ad_account:
        return []

    result = await db.execute(
        select(AdCampaign).where(AdCampaign.company_id == company_id)
    )
    campaigns = list(result.scalars().all())
    snapshots: list[AdSnapshot] = []

    act_id = ad_account if ad_account.startswith("act_") else f"act_{ad_account}"

    async with httpx.AsyncClient(timeout=30) as client:
        for camp in campaigns:
            if not camp.meta_campaign_id:
                continue
            try:
                resp = await client.get(
                    f"{META_GRAPH}/{camp.meta_campaign_id}/insights",
                    params={
                        "access_token": token,
                        "fields": "spend,impressions,clicks,ctr,cpc",
                        "date_preset": "today",
                    },
                )
                if resp.status_code != 200:
                    continue
                data = resp.json().get("data", [{}])[0]
                spend = float(data.get("spend", 0) or 0)
                impressions = int(data.get("impressions", 0) or 0)
                clicks = int(data.get("clicks", 0) or 0)
                ctr = float(data.get("ctr", 0) or 0)
                cpc = float(data.get("cpc", 0) or 0)

                camp.spend_cents = int(spend * 100)
                camp.impressions = impressions
                camp.clicks = clicks
                camp.ctr = ctr
                camp.cpc_cents = int(cpc * 100)

                snap = AdSnapshot(
                    company_id=company_id,
                    campaign_id=camp.id,
                    spend_cents=camp.spend_cents,
                    impressions=impressions,
                    clicks=clicks,
                    ctr=ctr,
                    cpc_cents=camp.cpc_cents,
                    note=f"Monitor {datetime.now(timezone.utc).isoformat()}",
                )
                db.add(snap)
                snapshots.append(snap)

                if ctr < 0.5 and impressions > 500:
                    camp.status = AdCampaignStatus.PAUSED
            except Exception as exc:
                logger.warning("ads_monitor_failed", campaign_id=camp.id, error=str(exc))

    if snapshots:
        await db.commit()
    return snapshots
