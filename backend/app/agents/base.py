from dataclasses import dataclass, field
from typing import Literal


@dataclass
class TokenStats:
    provider: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    @property
    def estimated_cost_usd(self) -> float:
        """Rough cost estimate based on current pricing."""
        costs = {
            "claude-sonnet-4-20250514": (3.0, 15.0),   # per 1M tokens
            "claude-3-5-sonnet": (3.0, 15.0),
            "gpt-4o-mini": (0.15, 0.6),
            "gpt-4o": (2.5, 10.0),
        }
        input_rate, output_rate = costs.get(self.model, (3.0, 15.0))
        return (self.input_tokens * input_rate + self.output_tokens * output_rate) / 1_000_000


@dataclass
class AgentResult:
    format: Literal["html", "markdown", "json"]
    content: str
    metadata: dict
    tool_calls: list[dict] = field(default_factory=list)
    token_stats: list[TokenStats] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return sum(t.total_tokens for t in self.token_stats)

    @property
    def total_cost_usd(self) -> float:
        return sum(t.estimated_cost_usd for t in self.token_stats)


class BaseAgent:
    agent_id: str = "base"

    async def run(self, mission_type: str, company_name: str, mission_statement: str) -> AgentResult:
        raise NotImplementedError
