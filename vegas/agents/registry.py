"""
Agent Registry for VEGAS AIOS.

Manages all registered specialist agents, handles routing and dispatch,
and facilitates inter-agent coordination.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from vegas.agents.base import AgentResult, BaseAgent, message_bus


class AgentRegistry:
    """Central registry and coordinator for all VEGAS specialist agents."""

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self.bus = message_bus

    def register(self, agent: BaseAgent) -> None:
        """Register a specialist agent."""
        role = agent.role.lower().strip()
        self._agents[role] = agent

    def get(self, role: str) -> Optional[BaseAgent]:
        """Retrieve an agent instance by role name."""
        return self._agents.get(role.lower().strip())

    def dispatch(self, role: str, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """
        Dispatch a task to a specialist agent by role.
        Falls back gracefully if role is unmapped.
        """
        target_role = role.lower().strip()
        agent = self.get(target_role)

        if not agent:
            # Fallback to developer agent or return failure
            developer = self.get("developer")
            if developer:
                return developer.execute(f"[{role.upper()} FALLBACK] {task}", context)
            return AgentResult(
                agent_role=role,
                status="failed",
                result=f"AgentRegistry Error: No agent registered for role '{role}'. Available: {list(self._agents.keys())}",
            )

        return agent.execute(task, context)

    def list_agents(self) -> List[Dict[str, Any]]:
        """Return status and tool manifest for all registered agents."""
        return [agent.status() for agent in self._agents.values()]

    def broadcast(self, sender: str, msg_type: str, content: Any) -> None:
        """Send a broadcast message from one agent to all others."""
        self.bus.send(
            AgentMessage(
                sender=sender,
                recipient="broadcast",
                msg_type=msg_type,
                content=content,
            )
        )


# Global registry singleton
agent_registry = AgentRegistry()
registry = agent_registry
