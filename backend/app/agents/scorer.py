"""Quality gate — LLM-based scoring of mission deliverables.

Calls a lightweight LLM to rate each deliverable 1-10 against mission-specific
criteria.  Returns (score, feedback) so the runner can decide whether to retry.
"""
from __future__ import annotations

import json

import structlog

from app.core.config import get_settings

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Per-mission scoring rubrics injected into the scorer prompt
# ---------------------------------------------------------------------------

SCORING_RUBRICS: dict[str, str] = {
    "market_scan": (
        "- Factual data with cited sources (URLs, numbers)\n"
        "- TAM/SAM/SOM estimates with methodology\n"
        "- At least 3 named competitors with real details\n"
        "- Actionable insights (not generic advice)\n"
        "- Target customer profile backed by data"
    ),
    "product_brief": (
        "- Clear one-sentence pitch\n"
        "- Problem/solution well articulated\n"
        "- MVP scope with 5-8 specific features\n"
        "- Pricing strategy with justification\n"
        "- North Star metric and 3+ KPIs defined"
    ),
    "landing_page": (
        "- Complete, valid HTML (DOCTYPE to closing </html>)\n"
        "- Clear hero section with compelling headline + CTA\n"
        "- Responsive / mobile-friendly CSS\n"
        "- Multiple sections (hero, benefits, how-it-works, social proof, pricing/offer, FAQ)\n"
        "- No placeholder text — all content is specific to the company\n"
        "- Coherent visual system: consistent palette, typography and spacing (not default grey/blue)\n"
        "- Product image embedded (real URL or well-crafted CSS mockup) — not a generic placeholder\n"
        "- Brand vibe matches the product category (wellness=natural, sport=energetic, tech=clean)\n"
        "- CTA is specific to the product (not generic 'Click here')\n"
        "- Trust signals are product-specific (ingredients, guarantee, proof, etc.)"
    ),
    "ad_copy_pack": (
        "- At least 5 distinct ad copy variations\n"
        "- Strong hooks (pattern interrupt, curiosity, pain point)\n"
        "- Platform-appropriate formats (Meta, TikTok, Google)\n"
        "- Clear CTA in each ad\n"
        "- Variety in angles (problem, social proof, urgency, benefit, story)"
    ),
    "brand_design": (
        "- Color palette with hex codes (primary, secondary, accent)\n"
        "- Typography choices with Google Fonts names\n"
        "- Brand voice and tone guidelines\n"
        "- Logo concept brief\n"
        "- WCAG AA contrast compliance noted"
    ),
    "supplier_sourcing": (
        "- At least 5 named suppliers with contact/URL\n"
        "- Comparison table (price, MOQ, shipping, quality)\n"
        "- Supply chain risk analysis\n"
        "- Margin calculations per supplier\n"
        "- Recommended supplier with justification"
    ),
    "payment_setup": (
        "- Monetization model clearly defined\n"
        "- Stripe product/price structure specified\n"
        "- Checkout flow described step by step\n"
        "- Tax and compliance considerations\n"
        "- MRR/ARPU projections"
    ),
    "competitor_ads_analysis": (
        "- At least 3 competitors with real ad examples\n"
        "- Creative analysis (visuals, copy, CTA)\n"
        "- Channel breakdown (Meta, Google, TikTok)\n"
        "- Spend estimates where possible\n"
        "- 3 actionable angles to differentiate"
    ),
    "analytics_tracking": (
        "- Event taxonomy with naming conventions\n"
        "- Tool recommendations (Amplitude, GA4, etc.)\n"
        "- Dashboard KPI layout\n"
        "- Implementation code snippets\n"
        "- GDPR/privacy compliance plan"
    ),
    "optimization_audit": (
        "- Data-backed current state assessment\n"
        "- Acquisition/CAC analysis\n"
        "- Conversion funnel with drop-off points\n"
        "- Retention cohort analysis\n"
        "- Prioritized action plan (effort vs impact)"
    ),
    "aso_optimization": (
        "- 30+ keywords with search volume estimates\n"
        "- Optimized title and subtitle\n"
        "- Full long description\n"
        "- iOS keyword field strategy\n"
        "- Screenshot strategy with descriptions"
    ),
    "organic_content_strategy": (
        "- Content pillars clearly defined\n"
        "- 30-day content calendar\n"
        "- Platform-specific hooks and formats\n"
        "- Hashtag strategy\n"
        "- Engagement and growth KPIs"
    ),
    "community_building": (
        "- Platform choice with justification\n"
        "- Channel architecture\n"
        "- Launch plan (first 50 members)\n"
        "- Engagement and gamification mechanics\n"
        "- Moderation guidelines"
    ),
    "growth_loop": (
        "- Growth loop diagram/description\n"
        "- K-factor calculation\n"
        "- Referral program design\n"
        "- Share triggers identified\n"
        "- Viral metrics and targets"
    ),
    "content_seo": (
        "- Target keywords with search volume\n"
        "- H1-H3 article structure\n"
        "- Article length 1500-3000 words\n"
        "- On-page SEO optimizations listed\n"
        "- Promotion brief included"
    ),
    "cold_outbound": (
        "- 5-email sequence with timing (Day 0 to Day 21)\n"
        "- Each email under 150 words\n"
        "- 3 LinkedIn message templates\n"
        "- Personalization tokens\n"
        "- GDPR compliance noted"
    ),
    "blog_article": (
        "- SEO keyword research (primary + 3-5 secondary keywords)\n"
        "- H1-H3 structure with logical hierarchy\n"
        "- Article length 1500-3000 words, no filler\n"
        "- On-page SEO complete (meta title, meta description, slug)\n"
        "- Promotion brief with 3+ distribution channels"
    ),
    "prospect_report": (
        "- 10+ named prospects with real company details\n"
        "- Scoring matrix (fit x urgency) with justification\n"
        "- Contact channels identified per prospect\n"
        "- ICP profile backed by firmographic data\n"
        "- Prioritized action plan (week 1-4)"
    ),
    "ad_creation": (
        "- 3+ ad creatives with full specs per platform\n"
        "- Distinct angles per variant (pain, benefit, proof)\n"
        "- Copy respects platform char limits\n"
        "- Visual direction/image brief for each creative\n"
        "- CTA explicit and varied across variants"
    ),
    "ads_launch_plan": (
        "- Budget allocation by platform with CPA/ROAS targets\n"
        "- Audience targeting specs (interests, lookalikes, exclusions)\n"
        "- Test calendar with phases (test, optimize, scale)\n"
        "- A/B test plan with variables and success criteria\n"
        "- KPI thresholds for go/no-go decisions"
    ),
    "cold_email_sequence": (
        "- 5-email sequence with clear timing (Day 0 to Day 21)\n"
        "- Each email under 150 words with 1 CTA\n"
        "- Personalization tokens defined and realistic\n"
        "- Subject lines under 50 chars, no spam triggers\n"
        "- GDPR compliance (opt-out, legal basis)"
    ),
    "support_setup": (
        "- Channel recommendations justified by business type\n"
        "- 20+ FAQ entries organized by category\n"
        "- 10 response templates covering key scenarios\n"
        "- SLA tiers (P1/P2/P3) with response time targets\n"
        "- Escalation matrix with clear decision criteria"
    ),
    "support_templates": (
        "- 10+ templates covering full support lifecycle\n"
        "- Personalization tokens clearly marked [brackets]\n"
        "- Each template under 200 words with next step\n"
        "- Tone empathetic and human (not robotic)\n"
        "- Guidelines for when to personalize vs use standard"
    ),
    "revenue_report": (
        "- Executive summary with 3 key metrics and trend\n"
        "- Revenue breakdown (MRR/ARR or monthly, growth %)\n"
        "- Unit economics (LTV, CAC, LTV/CAC, payback)\n"
        "- Cost analysis with burn rate\n"
        "- 3 scenarios (base, optimistic, pessimistic) projections"
    ),
    "social_batch": (
        "- 5+ posts with varied content types\n"
        "- Hook in first line of every post\n"
        "- Platform-specific adaptations (LinkedIn vs IG vs X)\n"
        "- Content mix (education, proof, engagement, promo)\n"
        "- Publishing calendar with optimal timing"
    ),
    "morning_plan": (
        "- 3 prioritized tasks ranked by impact\n"
        "- KPIs to monitor with alert thresholds\n"
        "- Proactive recommendations based on context\n"
        "- Quick wins identified (< 15min, high value)\n"
        "- Fits on one page, immediately actionable"
    ),
    "evening_summary": (
        "- Mission completion status with quality scores\n"
        "- KPI evolution vs previous day\n"
        "- Notable insights or anomalies flagged\n"
        "- Tomorrow's top 3 priorities with rationale\n"
        "- Factual and concise (no fluff)"
    ),
    "idea_storm": (
        "- 10+ distinct ideas (no generic 'todo app' types)\n"
        "- Each idea: title, description, target, hook, feasibility\n"
        "- Scoring (originality 1-5, feasibility 1-5) justified\n"
        "- Top 3 recommended with clear rationale\n"
        "- Ideas are realizable in under 3 months"
    ),
    "inbox_review": (
        "- Triage categories (urgent, important, delegable, archive)\n"
        "- Draft responses for top 5 emails\n"
        "- Follow-up list for emails awaiting reply > 48h\n"
        "- Action items extracted with priorities\n"
        "- Each suggested response under 100 words"
    ),
    "budget_tracking": (
        "- Month snapshot: spent vs budget with % consumed\n"
        "- Category breakdown (marketing, tools, salaries, infra)\n"
        "- Alerts for categories > 10% over/under budget\n"
        "- 2-3 reallocation recommendations\n"
        "- Cash runway calculated at current burn"
    ),
    "image_brief": (
        "- Art direction with concrete references (not vague)\n"
        "- Technical specs per platform (dimensions, format, DPI)\n"
        "- Visual content description (subject, composition, text)\n"
        "- 3+ variants with different angles/contexts\n"
        "- Brand consistency with existing visual identity"
    ),
}

DEFAULT_RUBRIC = (
    "- Content is specific to the company (no generic filler)\n"
    "- Actionable and complete deliverable\n"
    "- Well-structured and professional\n"
    "- Coherent with provided context\n"
    "- Ready to use without major edits"
)

QUALITY_THRESHOLD = 7
MAX_QUALITY_RETRIES = 2


async def score_deliverable(
    mission_type: str,
    original_prompt: str,
    deliverable: str,
    business_type: str,
) -> tuple[int, str]:
    """Score a deliverable 1-10 using a lightweight LLM call.

    Returns (score, feedback_text).  Feedback explains strengths/weaknesses
    so the agent can improve on retry.
    """
    settings = get_settings()

    # Empty deliverable is always a hard failure — no LLM call needed
    if not (deliverable or "").strip():
        return 0, "Deliverable is empty. The agent produced no content."

    rubric = SCORING_RUBRICS.get(mission_type, DEFAULT_RUBRIC)

    # For landing pages, add structural HTML checks to the scoring context
    html_context = ""
    if mission_type == "landing_page" and deliverable:
        h = deliverable.lower()
        checks = {
            "has_doctype": "<!doctype" in h or "<html" in h,
            "has_viewport": "viewport" in h,
            "has_img": "<img" in h,
            "has_cta_button": "<button" in h or ("href=" in h and ("buy" in h or "acheter" in h or "commander" in h or "stripe" in h)),
            "has_stripe": "stripe" in h or "buy.stripe.com" in h,
            "has_analytics": "fbq(" in deliverable or "data-analytics" in h,
            "no_waitlist": not any(w in h for w in ["waitlist", "coming soon", "liste d'attente"]),
            "has_multiple_sections": h.count("<section") + h.count("class=\"section") >= 3,
        }
        failed = [k for k, v in checks.items() if not v]
        if failed:
            html_context = f"\nSTRUCTURAL CHECKS FAILED: {', '.join(failed)}\n"
        else:
            html_context = "\nAll structural checks passed.\n"

    scorer_prompt = (
        "You are a quality-assurance reviewer for AI-generated business deliverables.\n"
        "Score the following deliverable from 1 to 10 based on the rubric.\n\n"
        f"MISSION TYPE: {mission_type}\n"
        f"BUSINESS TYPE: {business_type}\n"
        + (html_context if html_context else "")
        + f"\nRUBRIC:\n{rubric}\n\n"
        "Respond ONLY with valid JSON:\n"
        '{"score": <int 1-10>, "feedback": "<2-3 sentences explaining score>", '
        '"strengths": ["..."], "weaknesses": ["..."]}\n\n'
        "Be strict: a score of 7+ means the deliverable is ready to use as-is.\n"
        "A score below 7 means it needs significant improvements.\n"
        "For landing pages: auto-penalize 2 points for each structural check that failed."
    )

    user_msg = (
        f"ORIGINAL BRIEF:\n{original_prompt[:1000]}\n\n"
        f"DELIVERABLE:\n{deliverable[:6000]}"
    )

    try:
        if not settings.anthropic_api_key and not settings.openai_api_key:
            logger.info("scorer_no_api_key_skipping")
            return 10, "No API key configured — quality gate skipped."

        from app.agents.llm_client import call_simple

        providers = ["openai"] if settings.openai_api_key else []
        if settings.anthropic_api_key:
            providers.append("anthropic")

        result_text = ""
        for provider in providers:
            try:
                llm_resp = await call_simple(scorer_prompt, user_msg, provider=provider, max_tokens=512)
                result_text = llm_resp.content
                logger.debug(
                    "scorer_llm_call",
                    provider=provider,
                    latency_ms=llm_resp.latency_ms,
                    tokens=llm_resp.input_tokens + llm_resp.output_tokens,
                )
                break
            except Exception as prov_exc:
                logger.warning("scorer_provider_failed", provider=provider, error=str(prov_exc))
                continue

        if not result_text:
            return 10, "All scorer providers failed — deliverable accepted by default."

        parsed = json.loads(result_text)
        score = max(1, min(10, int(parsed["score"])))
        feedback = parsed.get("feedback", "")
        strengths = parsed.get("strengths", [])
        weaknesses = parsed.get("weaknesses", [])

        full_feedback = feedback
        if strengths:
            full_feedback += f"\nPoints forts: {', '.join(strengths)}"
        if weaknesses:
            full_feedback += f"\nPoints faibles: {', '.join(weaknesses)}"

        logger.info(
            "deliverable_scored",
            mission_type=mission_type,
            score=score,
            feedback=feedback[:200],
        )
        return score, full_feedback

    except Exception as exc:
        logger.warning("scorer_failed", error=str(exc))
        return 10, f"Scoring failed ({exc}) — deliverable accepted by default."
