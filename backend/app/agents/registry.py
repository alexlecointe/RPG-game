from app.agents.base import BaseAgent
from app.agents.builder import BuilderAgent
from app.agents.content import ContentAgent
from app.agents.finance import FinanceAgent
from app.agents.marketer import MarketerAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.outreach import OutreachAgent
from app.agents.researcher import ResearcherAgent
from app.agents.support import SupportAgent
from app.models.entities import AgentType

AGENT_MAP: dict[AgentType, BaseAgent] = {
    AgentType.BUILDER: BuilderAgent(),
    AgentType.MARKETER: MarketerAgent(),
    AgentType.RESEARCHER: ResearcherAgent(),
    AgentType.ORCHESTRATOR: OrchestratorAgent(),
    AgentType.OUTREACH: OutreachAgent(),
    AgentType.SUPPORT: SupportAgent(),
    AgentType.FINANCE: FinanceAgent(),
    AgentType.CONTENT: ContentAgent(),
}


def get_agent(agent_type: AgentType) -> BaseAgent:
    return AGENT_MAP[agent_type]
