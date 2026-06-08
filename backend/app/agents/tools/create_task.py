"""Tool: create_task

Allows a running agent to create a sub-task for itself or another agent.
Created tasks have source=AGENT_GENERATED, are queued without auto-schedule,
and cost 1 credit when executed (not at creation).
"""
from __future__ import annotations

from app.agents.tools import ToolDefinition


def create_create_task_tool(company_id: str) -> ToolDefinition:
    """Build a create_task tool bound to a specific company."""

    async def _execute(
        title: str,
        description: str = "",
        agent_type: str | None = None,
        tag: str | None = None,
    ) -> str:
        import json
        from app.core.database import SessionLocal
        from app.models.entities import TaskSource
        from app.services.mission import MissionService
        from app.services.company import CompanyService

        async with SessionLocal() as db:
            try:
                svc = MissionService(db)
                full_description = description
                if tag:
                    full_description = f"[tag:{tag}] {description}".strip()
                mission = await svc.create_freeform_task(
                    company_id=company_id,
                    title=title,
                    description=full_description,
                    agent_type_str=agent_type,
                    source=TaskSource.AGENT_GENERATED,
                    auto_schedule=False,
                )
                return json.dumps({
                    "status": "created",
                    "task_id": mission.id,
                    "title": mission.title,
                    "agent": mission.agent_type.value,
                    "queue_order": mission.queue_order,
                    "message": f"Tâche '{title}' créée et mise en queue (source: agent_generated). 1 crédit sera débité à l'exécution.",
                })
            except ValueError as e:
                return json.dumps({"status": "error", "error": str(e)})

    return ToolDefinition(
        name="create_task",
        description=(
            "Create a new task in the company's queue. Use this when you identify "
            "work that should be done by another agent or as a follow-up to your current task. "
            "The task will wait in queue until manually triggered. "
            "Cost: 0 credits to create, 1 credit when executed. "
            "Examples: create a 'Fix login bug' task for the builder agent after identifying an issue, "
            "or create 'Analyze competitor ads' for the researcher agent."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short task title (max 60 chars). Be specific: 'Fix checkout redirect bug' not 'Fix bug'.",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of what the agent should do. Include context, expected output, and any constraints.",
                },
                "agent_type": {
                    "type": "string",
                    "enum": [
                        "builder", "marketer", "researcher", "orchestrator",
                        "outreach", "support", "finance", "content",
                        "browser", "data", "ops", "growth",
                    ],
                    "description": "Agent to assign. If omitted, auto-routing is used based on the title/description.",
                },
                "tag": {
                    "type": "string",
                    "description": "Optional tag for task categorization, e.g. 'meta_ads', 'billing', 'content'. Prepended to the description as [tag:value].",
                },
            },
            "required": ["title"],
        },
        execute=_execute,
        is_readonly=False,
        max_calls_per_mission=3,
    )
