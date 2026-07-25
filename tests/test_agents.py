"""
Comprehensive unit test suite for VEGAS AIOS Multi-Agent Architecture.

Tests:
  - 8 Specialist Agents registration & tool ownership
  - Inter-agent message bus (send, receive, request_help, broadcast)
  - AgentRegistry routing & dispatching
  - DelegatingAgentExecutor integration
  - API agent REST endpoints
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from vegas.agents import (
    AgentMessage,
    AgentRegistry,
    BrowserAgent,
    CalendarAgent,
    ComputerAgent,
    DeveloperAgent,
    EmailAgent,
    GitAgent,
    MemoryAgent,
    MessageBus,
    PhoneAgent,
    registry,
)
from vegas.core.executor import DelegatingAgentExecutor
from vegas.core.planner import ExecutionPlan, TaskNode


# ---------------------------------------------------------------------------
# 1. Agent Tool Ownership & Registration Tests
# ---------------------------------------------------------------------------

def test_all_8_agents_are_registered_in_global_registry():
    roles = [agent["role"] for agent in registry.list_agents()]
    expected_roles = ["computer", "browser", "developer", "git", "memory", "calendar", "email", "phone"]
    for role in expected_roles:
        assert role in roles, f"Role '{role}' missing from global registry."


def test_computer_agent_owns_system_tools():
    agent = registry.get("computer")
    assert agent is not None
    assert "run_command" in agent.tools
    assert "get_system_info" in agent.tools
    assert "get_current_time" in agent.tools
    assert "play_music" in agent.tools
    assert "set_system_volume" in agent.tools


def test_browser_agent_owns_web_tools():
    agent = registry.get("browser")
    assert agent is not None
    assert "browse_and_extract" in agent.tools
    assert "fill_web_form" in agent.tools
    assert "search_web" in agent.tools
    assert "fetch_url" in agent.tools


def test_developer_agent_owns_coding_tools():
    agent = registry.get("developer")
    assert agent is not None
    assert "dispatch_coding_task" in agent.tools
    assert "view_file" in agent.tools
    assert "write_file" in agent.tools
    assert "edit_file" in agent.tools


def test_git_agent_owns_git_tools():
    agent = registry.get("git")
    assert agent is not None
    assert "git_status" in agent.tools
    assert "git_diff" in agent.tools
    assert "git_commit" in agent.tools


def test_memory_agent_owns_memory_tools():
    agent = registry.get("memory")
    assert agent is not None
    assert "store_fact" in agent.tools
    assert "retrieve_fact" in agent.tools
    assert "search_facts" in agent.tools


def test_calendar_agent_owns_workflow_tools():
    agent = registry.get("calendar")
    assert agent is not None
    assert "list_todays_events" in agent.tools
    assert "morning_briefing" in agent.tools


def test_email_agent_owns_gmail_tools():
    agent = registry.get("email")
    assert agent is not None
    assert "draft_email" in agent.tools


def test_phone_agent_owns_adb_tools():
    agent = registry.get("phone")
    assert agent is not None
    assert "list_connected_devices" in agent.tools
    assert "send_phone_sms" in agent.tools
    assert "make_phone_call" in agent.tools


# ---------------------------------------------------------------------------
# 2. Inter-Agent Communication & MessageBus Tests
# ---------------------------------------------------------------------------

def test_message_bus_delivers_direct_message():
    bus = MessageBus()
    received = []

    bus.subscribe("git", lambda msg: received.append(msg))
    bus.send(AgentMessage(sender="developer", recipient="git", msg_type="request_help", content="Need git diff"))

    assert len(received) == 1
    assert received[0].sender == "developer"
    assert received[0].recipient == "git"
    assert received[0].content == "Need git diff"


def test_message_bus_broadcast_delivers_to_all_subscribers():
    bus = MessageBus()
    dev_received = []
    git_received = []

    bus.subscribe("developer", lambda msg: dev_received.append(msg))
    bus.subscribe("git", lambda msg: git_received.append(msg))

    bus.send(AgentMessage(sender="planner", recipient="broadcast", msg_type="notification", content="Plan started"))

    assert len(dev_received) == 1
    assert len(git_received) == 1
    assert dev_received[0].content == "Plan started"


def test_agent_request_help_posts_to_bus():
    bus = MessageBus()
    dev = DeveloperAgent()
    dev.bus = bus
    git = GitAgent()
    git.bus = bus

    bus.subscribe("git", git.receive_message)

    dev.request_help("git", "Check branch status before editing")

    assert len(git.inbox) == 1
    assert git.inbox[0].sender == "developer"
    assert git.inbox[0].content == "Check branch status before editing"


# ---------------------------------------------------------------------------
# 3. AgentRegistry Dispatch & Executor Integration Tests
# ---------------------------------------------------------------------------

def test_registry_dispatch_routes_to_correct_agent():
    mock_computer = MagicMock()
    mock_computer.role = "computer"
    mock_computer.execute.return_value = MagicMock(status="success", result="Computer output", agent_role="computer")

    test_reg = AgentRegistry()
    test_reg.register(mock_computer)

    res = test_reg.dispatch("computer", "Check system info")

    assert res.status == "success"
    assert res.result == "Computer output"
    mock_computer.execute.assert_called_once_with("Check system info", None)


def test_delegating_agent_executor_uses_registry(monkeypatch):
    mock_agent = MagicMock()
    mock_agent.role = "git"
    mock_agent.execute.return_value = MagicMock(status="success", result="Clean working tree", agent_role="git")

    test_reg = AgentRegistry()
    test_reg.register(mock_agent)

    executor = DelegatingAgentExecutor(registry=test_reg)
    node = TaskNode(step_id=1, description="Inspect git", agent_role="git")
    plan = ExecutionPlan(plan_id="plan-1", goal="Update project", intent="project_update", steps=[node])

    result = executor.execute(node, plan)

    assert result["status"] == "success"
    assert "Clean working tree" in result["result"]
    mock_agent.execute.assert_called_once()


# ---------------------------------------------------------------------------
# 4. API Endpoint Tests
# ---------------------------------------------------------------------------

def test_api_agents_list_endpoint():
    import api
    client = TestClient(api.app)

    res = client.get("/api/agents")
    assert res.status_code == 200
    data = res.json()
    assert "agents" in data
    roles = [a["role"] for a in data["agents"]]
    assert "developer" in roles
    assert "computer" in roles


def test_api_agent_detail_endpoint():
    import api
    client = TestClient(api.app)

    res = client.get("/api/agents/developer")
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "developer"
    assert "dispatch_coding_task" in data["tools"]


def test_api_agent_detail_not_found():
    import api
    client = TestClient(api.app)

    res = client.get("/api/agents/non_existent_role")
    assert res.status_code == 404
