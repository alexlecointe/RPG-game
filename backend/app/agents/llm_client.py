"""Centralized LLM client with retry, timeout, and circuit breaker.

Replaces the duplicated _call_anthropic / _call_openai / _score_anthropic /
_score_openai functions with a single resilient client.
"""
from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field

import structlog

from app.agents.base import TokenStats
from app.core.config import get_settings

logger = structlog.get_logger()

MAX_RETRIES = 3
BASE_BACKOFF_S = 1.0
DEFAULT_TIMEOUT_S = 60
COMPLEX_TIMEOUT_S = 120

CIRCUIT_ERROR_THRESHOLD = 3
CIRCUIT_RESET_S = 300

_anthropic_client = None
_openai_client = None


@dataclass
class _CircuitState:
    error_count: int = 0
    last_error_at: float = 0.0

    def record_error(self) -> None:
        self.error_count += 1
        self.last_error_at = time.monotonic()

    def record_success(self) -> None:
        self.error_count = 0

    @property
    def is_open(self) -> bool:
        if self.error_count < CIRCUIT_ERROR_THRESHOLD:
            return False
        if time.monotonic() - self.last_error_at > CIRCUIT_RESET_S:
            self.error_count = 0
            return False
        return True


_circuits: dict[str, _CircuitState] = {
    "anthropic": _CircuitState(),
    "openai": _CircuitState(),
}


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import AsyncAnthropic
        settings = get_settings()
        _anthropic_client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=COMPLEX_TIMEOUT_S,
        )
    return _anthropic_client


def _get_openai():
    global _openai_client
    if _openai_client is None:
        from openai import AsyncOpenAI
        settings = get_settings()
        _openai_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=COMPLEX_TIMEOUT_S,
        )
    return _openai_client


def _is_retryable(exc: Exception) -> bool:
    """Check if the error is transient and worth retrying."""
    exc_str = str(type(exc).__name__).lower()
    msg = str(exc).lower()
    retryable_patterns = [
        "rate_limit", "ratelimit", "429",
        "overloaded", "503", "500",
        "timeout", "timed out",
        "server_error", "service_unavailable",
    ]
    return any(p in exc_str or p in msg for p in retryable_patterns)


def _prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


@dataclass
class LLMResponse:
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    provider: str = ""
    model: str = ""
    latency_ms: int = 0


async def call_anthropic_raw(
    system_prompt: str,
    messages: list[dict],
    max_tokens: int = 4096,
    tools: list[dict] | None = None,
    tool_choice: dict | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    max_retries: int = MAX_RETRIES,
):
    """Low-level Anthropic call with retry + timeout. Returns the raw response."""
    settings = get_settings()
    client = _get_anthropic()
    circuit = _circuits["anthropic"]

    if circuit.is_open:
        raise ConnectionError("Anthropic circuit breaker open")

    kwargs = {
        "model": settings.anthropic_model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": messages,
        "timeout": timeout_s,
    }
    if tools:
        kwargs["tools"] = tools
    if tool_choice:
        kwargs["tool_choice"] = tool_choice

    last_exc = None
    for attempt in range(max_retries):
        t0 = time.monotonic()
        try:
            response = await asyncio.wait_for(
                client.messages.create(**kwargs),
                timeout=timeout_s,
            )
            circuit.record_success()
            latency = int((time.monotonic() - t0) * 1000)
            logger.debug(
                "llm_call_ok",
                provider="anthropic",
                model=settings.anthropic_model,
                latency_ms=latency,
                attempt=attempt + 1,
            )
            return response, latency
        except Exception as exc:
            last_exc = exc
            latency = int((time.monotonic() - t0) * 1000)
            if _is_retryable(exc) and attempt < max_retries - 1:
                wait = BASE_BACKOFF_S * (2 ** attempt)
                logger.warning(
                    "llm_call_retry",
                    provider="anthropic",
                    attempt=attempt + 1,
                    wait_s=wait,
                    error=str(exc)[:200],
                    latency_ms=latency,
                )
                await asyncio.sleep(wait)
                continue
            circuit.record_error()
            raise

    raise last_exc  # type: ignore[misc]


async def call_openai_raw(
    system_prompt: str,
    user_content: str,
    messages: list[dict] | None = None,
    max_tokens: int = 4096,
    tools: list[dict] | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
):
    """Low-level OpenAI call with retry + timeout. Returns the raw response."""
    settings = get_settings()
    client = _get_openai()
    circuit = _circuits["openai"]

    if circuit.is_open:
        raise ConnectionError("OpenAI circuit breaker open")

    if messages is None:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

    kwargs = {
        "model": settings.openai_model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = tools

    last_exc = None
    for attempt in range(MAX_RETRIES):
        t0 = time.monotonic()
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(**kwargs),
                timeout=timeout_s,
            )
            circuit.record_success()
            latency = int((time.monotonic() - t0) * 1000)
            logger.debug(
                "llm_call_ok",
                provider="openai",
                model=settings.openai_model,
                latency_ms=latency,
                attempt=attempt + 1,
            )
            return response, latency
        except Exception as exc:
            last_exc = exc
            latency = int((time.monotonic() - t0) * 1000)
            if _is_retryable(exc) and attempt < MAX_RETRIES - 1:
                wait = BASE_BACKOFF_S * (2 ** attempt)
                logger.warning(
                    "llm_call_retry",
                    provider="openai",
                    attempt=attempt + 1,
                    wait_s=wait,
                    error=str(exc)[:200],
                    latency_ms=latency,
                )
                await asyncio.sleep(wait)
                continue
            circuit.record_error()
            raise

    raise last_exc  # type: ignore[misc]


async def call_simple(
    system_prompt: str,
    user_prompt: str,
    provider: str = "anthropic",
    max_tokens: int = 512,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    max_retries: int = MAX_RETRIES,
) -> LLMResponse:
    """Simple one-shot call (used by the scorer). Returns content string."""
    settings = get_settings()
    t0 = time.monotonic()

    if provider == "anthropic":
        resp, latency = await call_anthropic_raw(
            system_prompt,
            [{"role": "user", "content": user_prompt}],
            max_tokens=max_tokens,
            timeout_s=timeout_s,
            max_retries=max_retries,
        )
        text = resp.content[0].text
        usage = resp.usage
        return LLMResponse(
            content=text,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            provider="anthropic",
            model=settings.anthropic_model,
            latency_ms=latency,
        )
    else:
        resp, latency = await call_openai_raw(
            system_prompt,
            user_prompt,
            max_tokens=max_tokens,
        )
        choice = resp.choices[0]
        usage = resp.usage
        return LLMResponse(
            content=choice.message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            provider="openai",
            model=settings.openai_model,
            latency_ms=latency,
        )


def get_circuit_status() -> dict[str, dict]:
    """Return circuit breaker status (useful for health check)."""
    return {
        name: {
            "is_open": state.is_open,
            "error_count": state.error_count,
        }
        for name, state in _circuits.items()
    }
