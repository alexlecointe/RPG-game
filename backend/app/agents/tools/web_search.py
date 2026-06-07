from __future__ import annotations

import json

import httpx

from app.agents.tools import ToolDefinition

WEB_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "The search query to look up on the web.",
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of results to return (1-10).",
            "default": 5,
        },
    },
    "required": ["query"],
}


async def _execute_web_search(
    api_key: str, query: str, max_results: int = 5
) -> str:
    max_results = min(max(max_results, 1), 10)

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": max_results,
                "include_answer": True,
                "include_raw_content": False,
            },
        )
        response.raise_for_status()
        data = response.json()

    results = []
    if data.get("answer"):
        results.append(f"Reponse synthetique: {data['answer']}\n")

    for item in data.get("results", []):
        results.append(
            f"- **{item.get('title', '')}**\n"
            f"  URL: {item.get('url', '')}\n"
            f"  {item.get('content', '')[:500]}"
        )

    return "\n\n".join(results) if results else "Aucun resultat trouve."


def create_web_search_tool(api_key: str) -> ToolDefinition:
    async def execute(query: str, max_results: int = 5) -> str:
        return await _execute_web_search(api_key, query, max_results)

    return ToolDefinition(
        name="web_search",
        description=(
            "Search the web for current information. Use this to find real data "
            "about markets, competitors, prices, trends, and any factual information. "
            "Returns titles, URLs, and content snippets."
        ),
        parameters=WEB_SEARCH_SCHEMA,
        execute=execute,
    )
