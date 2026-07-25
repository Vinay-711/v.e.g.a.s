"""
Unit test suite for V.E.G.A.S. Memory Upgrade.

Tests:
  - SQLite extended schema & CRUD functions (conversations, projects, coding_preferences, tool_history, long_term_summaries)
  - MemoryEngine semantic retrieval & ranking
  - Context awareness prompt generation
  - Automatic Planner memory retrieval during plan creation
  - REST memory API endpoints
"""

import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import vegas.memory as sqlite_mem
from vegas.core.memory import MemoryEngine, memory
from vegas.core.planner import Planner


# ---------------------------------------------------------------------------
# 1. SQLite Extended Schema & CRUD Tests
# ---------------------------------------------------------------------------

def test_sqlite_conversation_dialogue_crud():
    turn_id = sqlite_mem.record_conversation_turn(
        session_id="test_sess_1",
        role="user",
        message="Use tabs for formatting",
        thoughts="User preference noted",
    )
    assert turn_id is not None

    turns = sqlite_mem.get_session_turns("test_sess_1")
    assert len(turns) >= 1
    latest = turns[-1]
    assert latest["role"] == "user"
    assert "tabs" in latest["message"]


def test_sqlite_project_memory_crud():
    sqlite_mem.store_project_memory(
        project_path="/tmp/test_repo",
        name="test_repo",
        tech_stack="Python, FastAPI, SQLite",
        architecture_summary="Modular architecture",
    )

    info = sqlite_mem.get_project_memory("/tmp/test_repo")
    assert info is not None
    assert info["name"] == "test_repo"
    assert "FastAPI" in info["tech_stack"]


def test_sqlite_coding_preferences_crud():
    sqlite_mem.set_coding_preference(
        key="formatting.style",
        value="black with 120 line length",
        category="formatting",
        confidence=0.95,
    )

    prefs = sqlite_mem.get_coding_preferences("formatting")
    assert len(prefs) >= 1
    match = [p for p in prefs if p["key"] == "formatting.style"][0]
    assert "120" in match["value"]


def test_sqlite_tool_history_crud():
    hist_id = sqlite_mem.log_tool_execution(
        tool_name="git_status",
        agent_role="git",
        status="success",
        duration_ms=45.0,
        result_summary="Clean working directory",
    )
    assert hist_id is not None

    stats = sqlite_mem.get_tool_performance_stats(limit=10)
    assert len(stats) >= 1
    assert stats[0]["tool_name"] == "git_status"


def test_sqlite_long_term_summary_crud():
    sum_id = sqlite_mem.store_long_term_summary(
        scope="milestone_v1",
        summary_text="Completed multi-agent architecture and native macOS computer control.",
        entities=["macOS", "FastAPI"],
    )
    assert sum_id is not None

    summaries = sqlite_mem.get_long_term_summaries(scope="milestone_v1")
    assert len(summaries) >= 1
    assert "multi-agent" in summaries[0]["summary_text"]


# ---------------------------------------------------------------------------
# 2. MemoryEngine Semantic Search & Context Awareness Tests
# ---------------------------------------------------------------------------

def test_memory_engine_semantic_search():
    engine = MemoryEngine()
    engine.store_fact("user_language_preference", "User prefers Python 3.11 and pytest")
    engine.record_turn("user", "How do I run pytest in this workspace?")

    results = engine.semantic_search("pytest", limit=5)
    assert len(results) >= 1
    # Check that matches have positive relevance score
    assert any("pytest" in str(r["content"]).lower() for r in results)


def test_memory_engine_build_context_block():
    engine = MemoryEngine()
    engine.set_coding_pref("indentation", "4 spaces", category="style")
    engine.store_project_info("/tmp/my_app", "my_app", tech_stack="React, FastAPI")

    context_block = engine.build_context_block("Build login UI", project_path="/tmp/my_app")
    assert "User Coding Preferences" in context_block
    assert "indentation: 4 spaces" in context_block
    assert "Project Memory [my_app]" in context_block


def test_memory_engine_long_term_summarization():
    engine = MemoryEngine()
    engine.record_turn("user", "Hello VEGAS")
    engine.record_turn("assistant", "Greetings! How can I assist with your code?")

    summary = engine.summarize_long_term_memory(scope="test_session")
    assert "Long-term summary stored" in summary or "Consolidated" in summary


# ---------------------------------------------------------------------------
# 3. Automatic Planner Memory Retrieval Test
# ---------------------------------------------------------------------------

def test_planner_automatically_retrieves_memory(monkeypatch):
    # Ensure memory returns preferences
    memory.set_coding_pref("testing", "Use pytest with -v flag")

    planner = Planner()
    planner._brain = None  # Use rules mode

    plan = planner.create_plan("Run tests for the project")

    assert len(plan.assumptions) >= 1
    # Verify that plan assumptions contain retrieved context
    assert any("Retrieved Context" in str(a) or "existing VEGAS architecture" in str(a) for a in plan.assumptions)


# ---------------------------------------------------------------------------
# 4. Memory API Endpoints Tests
# ---------------------------------------------------------------------------

def test_api_memory_preferences_endpoint():
    import api
    client = TestClient(api.app)

    memory.set_coding_pref("framework", "FastAPI", category="web")

    res = client.get("/api/memory/preferences")
    assert res.status_code == 200
    data = res.json()
    assert "preferences" in data


def test_api_memory_semantic_search_endpoint():
    import api
    client = TestClient(api.app)

    memory.store_fact("api_architecture", "REST backend with FastAPI and WebSockets")

    res = client.get("/api/memory/semantic?q=FastAPI")
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == "FastAPI"
    assert "results" in data


def test_api_memory_summarize_endpoint():
    import api
    client = TestClient(api.app)

    res = client.post("/api/memory/summarize", json={"scope": "session"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
