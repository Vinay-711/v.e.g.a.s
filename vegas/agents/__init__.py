"""
VEGAS AIOS Specialist Agents Package.

Exports:
  - BaseAgent, AgentMessage, MessageBus, AgentResult, message_bus
  - AgentRegistry, registry
  - ComputerAgent, BrowserAgent, DeveloperAgent, GitAgent
  - MemoryAgent, CalendarAgent, EmailAgent, PhoneAgent
"""

from vegas.agents.base import AgentMessage, AgentResult, BaseAgent, MessageBus, message_bus
from vegas.agents.browser_agent import BrowserAgent
from vegas.agents.calendar_agent import CalendarAgent
from vegas.agents.computer import ComputerAgent
from vegas.agents.developer_agent import DeveloperAgent
from vegas.agents.email_agent import EmailAgent
from vegas.agents.git_agent import GitAgent
from vegas.agents.memory_agent import MemoryAgent
from vegas.agents.phone_agent import PhoneAgent
from vegas.agents.registry import AgentRegistry, agent_registry, registry


def _init_default_registry() -> AgentRegistry:
    """Instantiate and register all default specialist agents."""
    computer = ComputerAgent()
    browser = BrowserAgent()
    developer = DeveloperAgent()
    git = GitAgent()
    memory = MemoryAgent()
    calendar = CalendarAgent()
    email = EmailAgent()
    phone = PhoneAgent()

    agent_registry.register(computer)
    agent_registry.register(browser)
    agent_registry.register(developer)
    agent_registry.register(git)
    agent_registry.register(memory)
    agent_registry.register(calendar)
    agent_registry.register(email)
    agent_registry.register(phone)

    # Register role aliases for planner compatibility
    agent_registry.register(ComputerAgent())  # role='computer'
    # Alias 'device' -> phone agent
    phone_alias = PhoneAgent()
    phone_alias.role = "device"
    agent_registry.register(phone_alias)

    # Alias 'workflow' -> calendar agent
    calendar_alias = CalendarAgent()
    calendar_alias.role = "workflow"
    agent_registry.register(calendar_alias)

    # Alias 'testing' -> developer agent
    testing_alias = DeveloperAgent()
    testing_alias.role = "testing"
    agent_registry.register(testing_alias)

    # Alias 'research' -> browser agent
    research_alias = BrowserAgent()
    research_alias.role = "research"
    agent_registry.register(research_alias)

    # Alias 'reporting' -> computer agent
    reporting_alias = ComputerAgent()
    reporting_alias.role = "reporting"
    agent_registry.register(reporting_alias)

    # Alias 'safety' -> computer agent
    safety_alias = ComputerAgent()
    safety_alias.role = "safety"
    agent_registry.register(safety_alias)

    return agent_registry


# Initialize registry upon package import
_init_default_registry()

__all__ = [
    "AgentMessage",
    "MessageBus",
    "message_bus",
    "AgentResult",
    "BaseAgent",
    "AgentRegistry",
    "agent_registry",
    "registry",
    "ComputerAgent",
    "BrowserAgent",
    "DeveloperAgent",
    "GitAgent",
    "MemoryAgent",
    "CalendarAgent",
    "EmailAgent",
    "PhoneAgent",
]
