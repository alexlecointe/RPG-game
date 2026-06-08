from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

import structlog

logger = structlog.get_logger()

TOOL_CALL_LIMITS: dict[str, int] = {
    "send_email": 2,
    "deploy_site": 1,
    "infra_action": 2,
    "stripe_action": 3,
    "meta_ads_action": 3,
    "x_action": 2,
    "generate_image": 3,
    "generate_video": 3,
    "store_asset": 3,
    "company_assets": 5,
    "web_search": 5,
    "web_scrape": 5,
    "google_trends": 5,
    "query_learnings": 5,
    "browser_action": 5,
    "create_task": 3,
}

READONLY_TOOLS = frozenset({
    "web_search", "web_scrape", "google_trends",
    "query_learnings", "browser_action", "company_assets",
})

# Tools available to all agent types (injected per-mission with company context)
UNIVERSAL_TOOLS = frozenset({"create_task"})


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    execute: Callable[..., Awaitable[str]]
    is_readonly: bool = True
    max_calls_per_mission: int = 5

    def to_anthropic_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolCallRecord:
    tool_name: str
    arguments: dict
    result: str


def _with_create_task(tools: list[str]) -> list[str]:
    """Append create_task to a tool list if not already present."""
    return tools + ["create_task"] if "create_task" not in tools else tools


MISSION_TOOLS: dict[str, list[str]] = {
    "market_scan": _with_create_task(["web_search", "web_scrape", "google_trends", "query_learnings", "store_asset", "company_assets"]),
    "product_brief": _with_create_task(["web_search", "query_learnings", "store_asset", "company_assets"]),
    "supplier_sourcing": _with_create_task(["web_search", "web_scrape", "query_learnings", "store_asset", "company_assets"]),
    "brand_design": _with_create_task(["web_search", "generate_image", "store_asset", "company_assets"]),
    "landing_page": _with_create_task(["web_search", "web_scrape", "deploy_site", "generate_image", "browser_action", "send_email", "infra_action", "store_asset", "company_assets"]),
    "payment_setup": _with_create_task(["web_search", "stripe_action", "store_asset", "company_assets"]),
    "competitor_ads_analysis": _with_create_task(["web_search", "web_scrape", "browser_action", "google_trends", "query_learnings", "store_asset", "company_assets"]),
    "ad_copy_pack": _with_create_task(["web_search", "generate_image", "store_asset", "company_assets"]),
    "ad_creation": _with_create_task(["web_search", "generate_image", "generate_video", "store_asset", "company_assets", "meta_ads_action"]),
    "analytics_tracking": _with_create_task(["web_search", "store_asset", "company_assets"]),
    "optimization_audit": _with_create_task(["web_search", "web_scrape", "browser_action", "query_learnings", "store_asset", "company_assets"]),
    "aso_optimization": _with_create_task(["web_search", "google_trends", "query_learnings", "store_asset", "company_assets"]),
    "organic_content_strategy": _with_create_task(["web_search", "google_trends", "query_learnings", "store_asset", "company_assets", "x_action"]),
    "community_building": _with_create_task(["web_search", "store_asset", "company_assets"]),
    "growth_loop": _with_create_task(["web_search", "google_trends", "query_learnings", "store_asset", "company_assets"]),
    "content_seo": _with_create_task(["web_search", "google_trends", "query_learnings", "store_asset", "company_assets"]),
    "cold_outbound": _with_create_task(["web_search", "send_email", "store_asset", "company_assets"]),
    "prospect_report": _with_create_task(["web_search", "web_scrape", "query_learnings", "store_asset", "company_assets"]),
    "ads_launch_plan": _with_create_task(["web_search", "web_scrape", "google_trends", "store_asset", "company_assets", "meta_ads_action"]),
    "support_setup": _with_create_task(["web_search", "store_asset", "company_assets"]),
    # Freeform tasks have all base tools + create_task
    "ceo_next_move": _with_create_task(["web_search", "query_learnings", "company_assets"]),
    "cold_email_sequence": _with_create_task(["web_search", "query_learnings", "store_asset", "company_assets"]),
    "inbox_review": _with_create_task(["query_learnings", "store_asset", "company_assets"]),
    "revenue_report": _with_create_task(["query_learnings", "store_asset", "company_assets"]),
    "blog_article": _with_create_task(["web_search", "query_learnings", "store_asset", "company_assets"]),
}


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._call_counts: dict[str, int] = {}
        self._mission_id: str = ""
        self._company_id: str = ""

    def set_mission_context(self, mission_id: str = "", company_id: str = "") -> None:
        """Set context for audit logging and reset per-mission call counters."""
        self._mission_id = mission_id
        self._company_id = company_id
        self._call_counts = {}

    def register(self, tool: ToolDefinition) -> None:
        tool.is_readonly = tool.name in READONLY_TOOLS
        tool.max_calls_per_mission = TOOL_CALL_LIMITS.get(tool.name, 5)
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def get_tools_for_mission(self, mission_type: str) -> list[ToolDefinition]:
        tool_names = MISSION_TOOLS.get(mission_type, [])
        return [self._tools[n] for n in tool_names if n in self._tools]

    async def execute_tool(self, name: str, arguments: dict) -> str:
        tool = self._tools.get(name)
        if not tool:
            return json.dumps({"error": f"Tool '{name}' not found"})

        current_count = self._call_counts.get(name, 0)
        if current_count >= tool.max_calls_per_mission:
            logger.warning(
                "tool_rate_limited",
                tool=name,
                limit=tool.max_calls_per_mission,
                mission_id=self._mission_id,
            )
            return json.dumps({
                "error": f"Tool '{name}' rate limit reached ({tool.max_calls_per_mission} calls/mission)."
            })

        t0 = time.monotonic()
        status = "success"
        result = ""
        try:
            result = await tool.execute(**arguments)
            self._call_counts[name] = current_count + 1
            logger.info(
                "tool_executed",
                tool=name,
                args_keys=list(arguments.keys()),
                readonly=tool.is_readonly,
                call_number=current_count + 1,
            )
            return result
        except Exception as exc:
            status = "error"
            result = json.dumps({"error": str(exc)})
            logger.warning("tool_execution_failed", tool=name, error=str(exc))
            return result
        finally:
            duration_ms = int((time.monotonic() - t0) * 1000)
            self._persist_tool_call(name, arguments, result, status, duration_ms)

    def _persist_tool_call(
        self, name: str, arguments: dict, result: str, status: str, duration_ms: int
    ) -> None:
        """Fire-and-forget audit log persistence."""
        if not self._mission_id:
            return
        try:
            import asyncio
            asyncio.get_running_loop().create_task(
                self._save_tool_call(name, arguments, result, status, duration_ms)
            )
        except RuntimeError:
            pass

    async def _save_tool_call(
        self, name: str, arguments: dict, result: str, status: str, duration_ms: int
    ) -> None:
        try:
            from app.core.database import SessionLocal
            from app.models.entities import ToolCallLog
            async with SessionLocal() as db:
                db.add(ToolCallLog(
                    mission_id=self._mission_id,
                    company_id=self._company_id or None,
                    tool_name=name,
                    arguments_json=json.dumps(arguments, ensure_ascii=False)[:2000],
                    result_preview=result[:500],
                    status=status,
                    duration_ms=duration_ms,
                ))
                await db.commit()
        except Exception as exc:
            logger.debug("tool_call_log_failed", error=str(exc))


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _register_all_tools(_registry)
    return _registry


def get_company_tool_registry(
    company_id: str,
    company_slug: str = "default",
) -> ToolRegistry:
    """Create a tool registry with company-specific tools (e.g. send_email with slug)."""
    base = get_tool_registry()
    registry = ToolRegistry()
    registry._tools = dict(base._tools)

    from app.core.config import get_settings
    settings = get_settings()

    if settings.resend_api_key:
        from app.agents.tools.send_email import create_send_email_tool
        registry.register(create_send_email_tool(
            settings.resend_api_key,
            from_domain=settings.resend_from_domain,
            company_slug=company_slug,
            company_id=company_id,
        ))

    from app.agents.tools.deploy_site import create_deploy_site_tool
    registry.register(create_deploy_site_tool(company_slug=company_slug))

    # create_task: allows agents to generate sub-tasks (source=agent_generated)
    from app.agents.tools.create_task import create_create_task_tool
    registry.register(create_create_task_tool(company_id=company_id))

    if settings.replicate_api_token:
        from app.agents.tools.generate_image import create_generate_image_tool
        registry.register(create_generate_image_tool(settings.replicate_api_token, company_id=company_id))
        from app.agents.tools.generate_video import create_generate_video_tool
        registry.register(create_generate_video_tool(company_id=company_id, company_slug=company_slug))

    if settings.stripe_secret_key:
        from app.agents.tools.stripe_action import create_stripe_action_tool
        registry.register(create_stripe_action_tool(
            settings.stripe_secret_key,
            company_slug=company_slug,
        ))

    return registry


def _register_all_tools(registry: ToolRegistry) -> None:
    from app.core.config import get_settings

    settings = get_settings()

    if settings.tavily_api_key:
        from app.agents.tools.web_search import create_web_search_tool
        registry.register(create_web_search_tool(settings.tavily_api_key))

    from app.agents.tools.web_scrape import create_web_scrape_tool
    registry.register(create_web_scrape_tool(settings.firecrawl_api_key))

    from app.agents.tools.deploy_site import create_deploy_site_tool
    registry.register(create_deploy_site_tool())

    if settings.replicate_api_token:
        from app.agents.tools.generate_image import create_generate_image_tool
        registry.register(create_generate_image_tool(settings.replicate_api_token))
        from app.agents.tools.generate_video import create_generate_video_tool
        registry.register(create_generate_video_tool())

    # send_email is registered per-mission with company context via get_company_tools()
    # A default global registration is kept for backwards compatibility
    if settings.resend_api_key:
        from app.agents.tools.send_email import create_send_email_tool
        registry.register(create_send_email_tool(
            settings.resend_api_key,
            from_domain=settings.resend_from_domain,
        ))

    if settings.browserbase_api_key and settings.browserbase_project_id:
        from app.agents.tools.browser_action import create_browser_action_tool
        registry.register(create_browser_action_tool(
            settings.browserbase_api_key, settings.browserbase_project_id,
        ))

    if settings.serpapi_key:
        from app.agents.tools.google_trends import create_google_trends_tool
        registry.register(create_google_trends_tool(settings.serpapi_key))

    from app.agents.tools.store_asset import create_store_asset_tool
    registry.register(create_store_asset_tool())

    from app.agents.tools.company_assets import create_company_assets_tool
    registry.register(create_company_assets_tool())

    from app.agents.tools.query_learnings import create_query_learnings_tool
    registry.register(create_query_learnings_tool())

    if settings.stripe_secret_key:
        from app.agents.tools.stripe_action import create_stripe_action_tool
        registry.register(create_stripe_action_tool(settings.stripe_secret_key))

    if settings.meta_capi_token and settings.meta_ad_account_id:
        from app.agents.tools.meta_ads_action import create_meta_ads_action_tool
        registry.register(create_meta_ads_action_tool(
            settings.meta_capi_token, settings.meta_ad_account_id
        ))

    if settings.x_configured:
        from app.agents.tools.x_action import create_x_action_tool
        registry.register(create_x_action_tool(
            settings.x_api_key,
            settings.x_api_secret,
            settings.x_access_token,
            settings.x_access_token_secret,
        ))

    if settings.render_api_key or settings.github_token or settings.neon_api_key:
        from app.agents.tools.infra_action import create_infra_action_tool
        registry.register(create_infra_action_tool())
