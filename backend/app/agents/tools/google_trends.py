"""Tool: google_trends — Fetch Google Trends data via SerpAPI.

Returns interest-over-time data and related queries for given keywords.
Useful for market research, content strategy, and competitor analysis.
"""
from __future__ import annotations

import json

import httpx

from app.agents.tools import ToolDefinition

GOOGLE_TRENDS_SCHEMA = {
    "type": "object",
    "properties": {
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of keywords to compare (max 5).",
        },
        "geo": {
            "type": "string",
            "description": "Country code for geographic filter (e.g. 'US', 'FR'). Empty for worldwide.",
            "default": "",
        },
        "timeframe": {
            "type": "string",
            "description": (
                "Time range: 'today 1-m' (last month), 'today 3-m', 'today 12-m' (last year), "
                "'today 5-y' (5 years). Default: last 12 months."
            ),
            "default": "today 12-m",
        },
    },
    "required": ["keywords"],
}

SERPAPI_URL = "https://serpapi.com/search.json"


async def _execute_google_trends(
    api_key: str,
    keywords: list[str],
    geo: str = "",
    timeframe: str = "today 12-m",
) -> str:
    keywords = keywords[:5]
    query = ",".join(keywords)

    params = {
        "engine": "google_trends",
        "q": query,
        "data_type": "TIMESERIES",
        "api_key": api_key,
    }
    if geo:
        params["geo"] = geo.upper()
    if timeframe:
        params["date"] = timeframe

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(SERPAPI_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    interest_over_time = data.get("interest_over_time", {})
    timeline_data = interest_over_time.get("timeline_data", [])

    trends_summary = []
    for kw in keywords:
        values = []
        for point in timeline_data:
            for v in point.get("values", []):
                if v.get("query", "").lower() == kw.lower():
                    values.append(int(v.get("extracted_value", 0)))
        if values:
            trends_summary.append({
                "keyword": kw,
                "avg_interest": round(sum(values) / len(values), 1),
                "peak_interest": max(values),
                "current_interest": values[-1] if values else 0,
                "trend": "rising" if len(values) > 1 and values[-1] > values[0] else "declining",
                "data_points": len(values),
            })
        else:
            trends_summary.append({
                "keyword": kw,
                "avg_interest": 0,
                "note": "No data found",
            })

    related_params = {
        "engine": "google_trends",
        "q": query,
        "data_type": "RELATED_QUERIES",
        "api_key": api_key,
    }
    if geo:
        related_params["geo"] = geo.upper()

    related_queries = []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(SERPAPI_URL, params=related_params)
            if resp.status_code == 200:
                rdata = resp.json()
                for block in rdata.get("related_queries", {}).values():
                    if isinstance(block, dict):
                        for q in block.get("rising", [])[:5]:
                            related_queries.append(q.get("query", ""))
                        for q in block.get("top", [])[:5]:
                            related_queries.append(q.get("query", ""))
    except Exception:
        pass

    return json.dumps({
        "keywords": keywords,
        "geo": geo or "worldwide",
        "timeframe": timeframe,
        "trends": trends_summary,
        "related_queries": list(set(related_queries))[:15],
    })


def create_google_trends_tool(api_key: str) -> ToolDefinition:
    async def execute(
        keywords: list[str], geo: str = "", timeframe: str = "today 12-m"
    ) -> str:
        return await _execute_google_trends(api_key, keywords, geo, timeframe)

    return ToolDefinition(
        name="google_trends",
        description=(
            "Fetch Google Trends data for keywords. Returns interest over time, "
            "peak/current interest, trend direction (rising/declining), and related queries. "
            "Use for market research, content strategy, and identifying trending topics. "
            "Compare up to 5 keywords at once."
        ),
        parameters=GOOGLE_TRENDS_SCHEMA,
        execute=execute,
    )
