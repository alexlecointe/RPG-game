"""Tool: x_action — Post tweets via X/Twitter API v2 (OAuth 1.0a)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import urllib.parse

import httpx

from app.agents.tools import ToolDefinition

X_API = "https://api.twitter.com/2/tweets"

X_ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["post_tweet"],
            "description": "post_tweet: publish a tweet (max 280 chars).",
        },
        "text": {
            "type": "string",
            "description": "Tweet text content (max 280 characters).",
        },
    },
    "required": ["action", "text"],
}


def _oauth1_header(
    method: str,
    url: str,
    consumer_key: str,
    consumer_secret: str,
    token: str,
    token_secret: str,
) -> str:
    oauth_params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": token,
        "oauth_version": "1.0",
    }
    base_params = urllib.parse.urlencode(sorted(oauth_params.items()))
    base_string = "&".join([
        method.upper(),
        urllib.parse.quote(url, safe=""),
        urllib.parse.quote(base_params, safe=""),
    ])
    signing_key = f"{urllib.parse.quote(consumer_secret, safe='')}&{urllib.parse.quote(token_secret, safe='')}"
    signature = base64.b64encode(
        hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    ).decode()
    oauth_params["oauth_signature"] = signature
    header_params = ", ".join(
        f'{k}="{urllib.parse.quote(v, safe="")}"' for k, v in sorted(oauth_params.items())
    )
    return f"OAuth {header_params}"


async def _post_tweet(
    api_key: str,
    api_secret: str,
    access_token: str,
    access_token_secret: str,
    text: str,
) -> dict:
    if len(text) > 280:
        return {"error": "Tweet exceeds 280 characters"}

    auth_header = _oauth1_header(
        "POST", X_API, api_key, api_secret, access_token, access_token_secret
    )
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            X_API,
            headers={"Authorization": auth_header, "Content-Type": "application/json"},
            json={"text": text},
        )
        resp.raise_for_status()
        data = resp.json()

    tweet = data.get("data", {})
    return {
        "posted": True,
        "tweet_id": tweet.get("id"),
        "text": tweet.get("text", text),
    }


def create_x_action_tool(
    api_key: str,
    api_secret: str,
    access_token: str,
    access_token_secret: str,
) -> ToolDefinition:
    async def execute(action: str, text: str = "") -> str:
        try:
            if action == "post_tweet":
                if not text:
                    return json.dumps({"error": "text required"})
                result = await _post_tweet(
                    api_key, api_secret, access_token, access_token_secret, text
                )
            else:
                result = {"error": f"Unknown action: {action}"}
        except httpx.HTTPStatusError as exc:
            result = {
                "error": f"X API error: {exc.response.status_code} {exc.response.text[:400]}",
            }
        except Exception as exc:
            result = {"error": f"X error: {exc}"}

        return json.dumps(result, default=str)

    return ToolDefinition(
        name="x_action",
        description=(
            "Post tweets on the platform X/Twitter account. "
            "Use for organic content distribution after creating social posts."
        ),
        parameters=X_ACTION_SCHEMA,
        execute=execute,
    )
