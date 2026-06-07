"""Tool: infra_action — Unified infrastructure operations (Render + Neon + GitHub).

Exposes the InfraService to agents, allowing them to provision full stacks,
deploy code, check status, and manage company infrastructure.
"""
from __future__ import annotations

import json

from app.agents.tools import ToolDefinition

INFRA_ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "provision_company",
                "push_code",
                "trigger_deploy",
                "get_status",
                "get_logs",
                "delete_all",
            ],
            "description": (
                "provision_company: create Neon DB + GitHub repo + Render service. "
                "push_code: push a file to the company's GitHub repo. "
                "trigger_deploy: trigger a Render deploy. "
                "get_status: check Render service status. "
                "get_logs: fetch Render deploy logs. "
                "delete_all: tear down all infra for a company."
            ),
        },
        "company_slug": {
            "type": "string",
            "description": "Company slug (required for most actions).",
        },
        "service_id": {
            "type": "string",
            "description": "Render service ID (for status/logs/deploy).",
        },
        "file_path": {
            "type": "string",
            "description": "File path in repo (for push_code action, e.g. 'public/index.html').",
        },
        "file_content": {
            "type": "string",
            "description": "File content to push (for push_code action).",
        },
    },
    "required": ["action"],
}


async def _execute_infra_action(
    action: str,
    company_slug: str = "",
    service_id: str = "",
    file_path: str = "",
    file_content: str = "",
) -> str:
    from app.services.infra import InfraService

    svc = InfraService()

    if action == "provision_company":
        if not company_slug:
            return json.dumps({"error": "company_slug required"})
        result = await svc.provision_company(company_slug)

    elif action == "push_code":
        if not company_slug or not file_path or not file_content:
            return json.dumps({"error": "company_slug, file_path, and file_content required"})
        result = await svc.push_code_to_repo(company_slug, file_path, file_content)

    elif action == "trigger_deploy":
        if not service_id:
            return json.dumps({"error": "service_id required"})
        result = await svc.trigger_deploy(service_id)

    elif action == "get_status":
        if not service_id:
            return json.dumps({"error": "service_id required"})
        result = await svc.get_status(service_id)

    elif action == "get_logs":
        if not service_id:
            return json.dumps({"error": "service_id required"})
        logs = await svc.get_logs(service_id)
        result = {"logs": logs}

    elif action == "delete_all":
        if not company_slug:
            return json.dumps({"error": "company_slug required"})
        from sqlalchemy import select

        from app.core.database import SessionLocal
        from app.models.entities import Company

        service_id = service_id or ""
        project_id = ""
        async with SessionLocal() as db:
            result = await db.execute(select(Company).where(Company.slug == company_slug))
            company = result.scalar_one_or_none()
            if company:
                service_id = service_id or (company.render_service_id or "")
                project_id = company.neon_project_id or ""
        infra_result = await svc.delete_all_infra(company_slug, service_id, project_id)
        result = infra_result

    else:
        result = {"error": f"Unknown action: {action}"}

    return json.dumps(result, default=str)


def create_infra_action_tool() -> ToolDefinition:
    async def execute(
        action: str,
        company_slug: str = "",
        service_id: str = "",
        file_path: str = "",
        file_content: str = "",
    ) -> str:
        return await _execute_infra_action(
            action, company_slug, service_id, file_path, file_content
        )

    return ToolDefinition(
        name="infra_action",
        description=(
            "Manage company infrastructure (Render + Neon + GitHub). "
            "Provision full stack, push code to repo, trigger deploys, "
            "check service status, view logs, or tear down infrastructure."
        ),
        parameters=INFRA_ACTION_SCHEMA,
        execute=execute,
    )
