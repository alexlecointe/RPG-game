from __future__ import annotations

import json
import re

import httpx

from app.agents.tools import ToolDefinition

WEB_SCRAPE_SCHEMA = {
    "type": "object",
    "properties": {
        "url": {
            "type": "string",
            "description": "The URL of the page to scrape.",
        },
    },
    "required": ["url"],
}

MAX_CONTENT_LENGTH = 5000


def _strip_html(html: str) -> str:
    """Naive HTML to text — strip tags, collapse whitespace."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def _scrape_with_httpx(url: str) -> str:
    async with httpx.AsyncClient(
        timeout=20,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; RPGAgent/1.0)"},
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        text = _strip_html(resp.text)
        return text[:MAX_CONTENT_LENGTH]


async def _scrape_with_firecrawl(api_key: str, url: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"url": url, "formats": ["markdown"]},
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("data", {}).get("markdown", "")
        return content[:MAX_CONTENT_LENGTH] if content else "Aucun contenu extrait."


async def _execute_web_scrape(firecrawl_key: str, url: str) -> str:
    if firecrawl_key:
        return await _scrape_with_firecrawl(firecrawl_key, url)
    return await _scrape_with_httpx(url)


def create_web_scrape_tool(firecrawl_api_key: str = "") -> ToolDefinition:
    async def execute(url: str) -> str:
        return await _execute_web_scrape(firecrawl_api_key, url)

    return ToolDefinition(
        name="web_scrape",
        description=(
            "Scrape a specific web page and extract its text content. "
            "Use this to read detailed information from a specific URL "
            "(product pages, competitor sites, app store listings, articles). "
            "Returns plain text content (max 5000 chars)."
        ),
        parameters=WEB_SCRAPE_SCHEMA,
        execute=execute,
    )
