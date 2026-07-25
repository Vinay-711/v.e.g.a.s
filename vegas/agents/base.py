"""
Base Agent and Message Bus abstractions for VEGAS AIOS.

Defines:
  - AgentMessage: Payload for inter-agent communication.
  - MessageBus: Internal pub/sub message broker enabling agents to communicate.
  - AgentResult: Standardized execution output structure.
  - BaseAgent: Base class for all specialist agents.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class AgentMessage:
    """Inter-agent message payload."""

    sender: str
    recipient: str  # Agent role or 'broadcast'
    msg_type: str  # 'request_help', 'data_share', 'status_update', 'notification'
    content: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class MessageBus:
    """Internal message bus for agent-to-agent communication."""

    def __init__(self):
        self._handlers: Dict[str, List[Callable[[AgentMessage], None]]] = {}
        self._queues: Dict[str, List[AgentMessage]] = {}
        self._history: List[AgentMessage] = []

    def subscribe(self, agent_role: str, handler: Callable[[AgentMessage], None]) -> None:
        """Register a handler for a specific agent role."""
        role = agent_role.lower()
        if role not in self._handlers:
            self._handlers[role] = []
        self._handlers[role].append(handler)

    def send(self, message: AgentMessage) -> None:
        """Send a message to a recipient agent or queue if not active."""
        self._history.append(message)
        recipient = message.recipient.lower()

        if recipient == "broadcast":
            for role, handlers in self._handlers.items():
                if role != message.sender.lower():
                    for handler in handlers:
                        try:
                            handler(message)
                        except Exception as e:
                            print(f"[MessageBus] Error delivering to {role}: {e}")
            return

        if recipient in self._handlers and self._handlers[recipient]:
            for handler in self._handlers[recipient]:
                try:
                    handler(message)
                except Exception as e:
                    print(f"[MessageBus] Error delivering to {recipient}: {e}")
        else:
            # Queue for offline recipient
            if recipient not in self._queues:
                self._queues[recipient] = []
            self._queues[recipient].append(message)

    def get_pending(self, agent_role: str) -> List[AgentMessage]:
        """Retrieve and clear queued messages for an agent."""
        role = agent_role.lower()
        messages = self._queues.pop(role, [])
        return messages

    @property
    def history(self) -> List[AgentMessage]:
        """Return global message history."""
        return list(self._history)


# Global MessageBus instance
message_bus = MessageBus()


@dataclass
class AgentResult:
    """Standard output object returned by any agent execution."""

    agent_role: str
    status: str  # 'success' | 'failed' | 'blocked'
    result: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


class BaseAgent(ABC):
    """Abstract Base Class for all VEGAS Specialist Agents."""

    def __init__(self, name: str, role: str, description: str, bus: Optional[MessageBus] = None):
        self.name = name
        self.role = role.lower().strip()
        self.description = description
        self.bus = bus or message_bus
        self.tools: Dict[str, Callable[..., Any]] = {}
        self.inbox: List[AgentMessage] = []

        # Subscribe to bus
        self.bus.subscribe(self.role, self.receive_message)

    def register_tool(self, name: str, tool_func: Callable[..., Any]) -> None:
        """Assign an existing tool function to this agent."""
        self.tools[name] = tool_func

    def receive_message(self, message: AgentMessage) -> None:
        """Handle incoming inter-agent message."""
        self.inbox.append(message)
        self.on_message(message)

    def on_message(self, message: AgentMessage) -> None:
        """Custom hook for subclasses to handle messages reactively."""
        pass

    def send_message(self, recipient: str, msg_type: str, content: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Send a message to another agent via the shared message bus."""
        msg = AgentMessage(
            sender=self.role,
            recipient=recipient,
            msg_type=msg_type,
            content=content,
            metadata=metadata or {},
        )
        self.bus.send(msg)

    def request_help(self, agent_role: str, task: str) -> None:
        """Inter-agent delegation: request assistance from another specialist."""
        self.send_message(
            recipient=agent_role,
            msg_type="request_help",
            content=task,
            metadata={"originator": self.role},
        )

    def process_pending_inbox(self) -> List[AgentMessage]:
        """Fetch and clear offline messages from bus queue."""
        pending = self.bus.get_pending(self.role)
        self.inbox.extend(pending)
        return list(self.inbox)

    @abstractmethod
    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """Execute a task assigned by the Planner using owned tools."""
        pass

    def status(self) -> Dict[str, Any]:
        """Return status and tool manifest for this agent."""
        return {
            "name": self.name,
            "role": self.role,
            "description": self.description,
            "tools": list(self.tools.keys()),
            "inbox_size": len(self.inbox),
        }
