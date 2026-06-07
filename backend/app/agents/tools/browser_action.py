"""Tool: browser_action — Headless browser automation via Browserbase.

Supports session pooling: reuses existing sessions for the same domain
to avoid redundant logins and Captcha re-submissions. Cookies are
persisted in DB between tasks.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy import select

from app.agents.tools import ToolDefinition

BROWSER_ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "url": {
            "type": "string",
            "description": "The URL to navigate to.",
        },
        "action": {
            "type": "string",
            "enum": ["screenshot", "extract_text", "extract_links"],
            "description": (
                "Action to perform: "
                "'screenshot' returns a description of the page visual state, "
                "'extract_text' returns visible text content, "
                "'extract_links' returns all links on the page."
            ),
            "default": "extract_text",
        },
        "wait_ms": {
            "type": "integer",
            "description": "Milliseconds to wait after page load before acting (default 2000).",
            "default": 2000,
        },
    },
    "required": ["url"],
}

BROWSERBASE_API = "https://www.browserbase.com/v1"

SESSION_TTL_HOURS = 1


def _extract_domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or parsed.path.split("/")[0]


async def _get_or_create_session(
    api_key: str, project_id: str, domain: str
) -> tuple[str, bool]:
    """Get an existing session for this domain or create a new one.

    Returns (session_id, reused) where reused indicates if an existing session
    was found and reused.
    """
    from app.core.database import SessionLocal
    from app.models.entities import BrowserSession

    async with SessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=SESSION_TTL_HOURS)
        result = await db.execute(
            select(BrowserSession)
            .where(
                BrowserSession.domain == domain,
                BrowserSession.last_used_at >= cutoff,
            )
            .order_by(BrowserSession.last_used_at.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.last_used_at = datetime.now(timezone.utc)
            await db.commit()
            return existing.session_id, True

    session_id = await _create_browserbase_session(api_key, project_id)

    async with SessionLocal() as db:
        db.add(BrowserSession(
            domain=domain,
            session_id=session_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS),
        ))
        await db.commit()

    return session_id, False


async def _create_browserbase_session(api_key: str, project_id: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BROWSERBASE_API}/sessions",
            headers={
                "x-bb-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={"projectId": project_id},
        )
        resp.raise_for_status()
        return resp.json()["id"]


async def _save_cookies(session_id: str, domain: str, cookies_json: str) -> None:
    """Persist cookies for session reuse."""
    from app.core.database import SessionLocal
    from app.models.entities import BrowserSession

    async with SessionLocal() as db:
        result = await db.execute(
            select(BrowserSession).where(BrowserSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        if session:
            session.cookies_json = cookies_json
            session.is_authenticated = True
            await db.commit()


async def _execute_browser_action(
    api_key: str,
    project_id: str,
    url: str,
    action: str = "extract_text",
    wait_ms: int = 2000,
) -> str:
    domain = _extract_domain(url)

    try:
        session_id, reused = await _get_or_create_session(api_key, project_id, domain)
    except Exception as exc:
        return json.dumps({"error": f"Failed to create browser session: {exc}"})

    connect_url = f"wss://connect.browserbase.com?apiKey={api_key}&sessionId={session_id}"

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return json.dumps({
            "error": "playwright not installed. Run: pip install playwright && playwright install chromium",
        })

    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(connect_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()

            await page.goto(url, wait_until="networkidle", timeout=30000)

            if wait_ms > 0:
                await page.wait_for_timeout(min(wait_ms, 10000))

            if action == "screenshot":
                title = await page.title()
                viewport = page.viewport_size or {}
                screenshot_bytes = await page.screenshot(type="png", full_page=False)

                import base64
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("ascii")

                screenshot_path = ""
                try:
                    from pathlib import Path
                    assets_dir = Path("data/screenshots")
                    assets_dir.mkdir(parents=True, exist_ok=True)
                    fname = domain.replace(".", "_") + ".png"
                    fpath = assets_dir / fname
                    fpath.write_bytes(screenshot_bytes)
                    screenshot_path = str(fpath)
                except Exception:
                    pass

                headings = await page.evaluate("""
                    Array.from(document.querySelectorAll('h1,h2,h3'))
                        .slice(0, 10)
                        .map(h => h.tagName + ': ' + h.textContent.trim())
                """)
                result_data = {
                    "action": "screenshot",
                    "url": url,
                    "title": title,
                    "headings": headings,
                    "viewport": viewport,
                    "screenshot_base64_preview": screenshot_b64[:200] + "...",
                    "screenshot_file": screenshot_path,
                    "session_reused": reused,
                }

            elif action == "extract_links":
                links = await page.evaluate("""
                    Array.from(document.querySelectorAll('a[href]'))
                        .slice(0, 50)
                        .map(a => ({text: a.textContent.trim().slice(0, 100), href: a.href}))
                """)
                result_data = {
                    "action": "extract_links",
                    "url": url,
                    "links": links,
                    "session_reused": reused,
                }

            else:
                text = await page.evaluate(
                    "document.body?.innerText || document.documentElement?.textContent || ''"
                )
                result_data = {
                    "action": "extract_text",
                    "url": url,
                    "content": text[:8000],
                    "session_reused": reused,
                }

            try:
                cookies = await context.cookies()
                if cookies:
                    await _save_cookies(session_id, domain, json.dumps(cookies))
            except Exception:
                pass

            return json.dumps(result_data)

    except Exception as exc:
        return json.dumps({"error": f"Browser action failed: {exc}"})


def create_browser_action_tool(api_key: str, project_id: str) -> ToolDefinition:
    async def execute(
        url: str, action: str = "extract_text", wait_ms: int = 2000
    ) -> str:
        return await _execute_browser_action(api_key, project_id, url, action, wait_ms)

    return ToolDefinition(
        name="browser_action",
        description=(
            "Open a real browser (via Browserbase) to navigate to a URL and perform actions. "
            "Sessions are pooled per domain — subsequent visits to the same site reuse the "
            "existing session (no re-login). "
            "Use 'screenshot' to inspect visual layout and headings, "
            "'extract_text' to get visible page content, "
            "or 'extract_links' to get all links."
        ),
        parameters=BROWSER_ACTION_SCHEMA,
        execute=execute,
    )
