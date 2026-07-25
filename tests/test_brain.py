"""Tests for the VegasBrain — the Gemini-powered AI reasoning engine.

All tests mock the Gemini API so they run offline without credentials.
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from vegas.core.brain import (
    DecompositionResult,
    ExecutionReflection,
    IntentAnalysis,
    RecoveryStrategy,
    SubtaskSpec,
    VegasBrain,
    _CacheEntry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_brain(available: bool = True) -> VegasBrain:
    """Create a VegasBrain with a mock Gemini client."""
    brain = VegasBrain.__new__(VegasBrain)
    brain.model = "gemini-2.5-flash"
    brain._cache = {}
    brain._last_reasoning_trace = ""
    brain._call_count = 0
    if available:
        brain._client = MagicMock()
    else:
        brain._client = None
    return brain


def _mock_gemini_response(text: str):
    """Create a mock Gemini response object."""
    response = MagicMock()
    response.text = text
    return response


# ---------------------------------------------------------------------------
# 1. Intent Understanding
# ---------------------------------------------------------------------------

class TestBrainUnderstandsIntent:
    def test_understands_project_update_intent(self):
        brain = _make_brain()
        brain._client.models.generate_content.return_value = _mock_gemini_response(
            json.dumps({
                "intent": "project_update",
                "confidence": 0.92,
                "reasoning": "User wants to update their project codebase.",
                "entities": ["project"],
                "is_multi_intent": False,
                "secondary_intents": [],
            })
        )

        result = brain.understand_intent("Update my project")

        assert result is not None
        assert result.intent == "project_update"
        assert result.confidence >= 0.9
        assert "project" in result.entities

    def test_understands_coding_intent(self):
        brain = _make_brain()
        brain._client.models.generate_content.return_value = _mock_gemini_response(
            json.dumps({
                "intent": "coding",
                "confidence": 0.88,
                "reasoning": "User wants to implement a new feature.",
                "entities": ["authentication", "API"],
                "is_multi_intent": False,
                "secondary_intents": [],
            })
        )

        result = brain.understand_intent("Build an authentication API")

        assert result is not None
        assert result.intent == "coding"
        assert result.confidence > 0.8

    def test_clamps_unknown_intent_to_unknown(self):
        brain = _make_brain()
        brain._client.models.generate_content.return_value = _mock_gemini_response(
            json.dumps({
                "intent": "invalid_intent_xyz",
                "confidence": 0.5,
                "reasoning": "Unclear.",
                "entities": [],
                "is_multi_intent": False,
                "secondary_intents": [],
            })
        )

        result = brain.understand_intent("Something weird")

        assert result is not None
        assert result.intent == "unknown"

    def test_returns_none_when_api_unavailable(self):
        brain = _make_brain(available=False)

        result = brain.understand_intent("Update my project")

        assert result is None

    def test_returns_none_on_malformed_json(self):
        brain = _make_brain()
        brain._client.models.generate_content.return_value = _mock_gemini_response(
            "This is not valid JSON at all"
        )

        result = brain.understand_intent("Do something")

        assert result is None

    def test_detects_multi_intent(self):
        brain = _make_brain()
        brain._client.models.generate_content.return_value = _mock_gemini_response(
            json.dumps({
                "intent": "coding",
                "confidence": 0.85,
                "reasoning": "Primary is coding, secondary is git.",
                "entities": ["feature", "branch"],
                "is_multi_intent": True,
                "secondary_intents": ["git"],
            })
        )

        result = brain.understand_intent("Build the feature and push to a new branch")

        assert result is not None
        assert result.is_multi_intent is True
        assert "git" in result.secondary_intents


# ---------------------------------------------------------------------------
# 2. Goal Decomposition
# ---------------------------------------------------------------------------

class TestBrainDecomposesGoals:
    def test_decomposes_complex_goal_into_agent_steps(self):
        brain = _make_brain()
        brain._client.models.generate_content.return_value = _mock_gemini_response(
            json.dumps({
                "summary": "Update project via git, developer, testing, memory, reporting.",
                "assumptions": ["Current workspace is target."],
                "risks": ["Tests may fail."],
                "subtasks": [
                    {
                        "description": "Check git status",
                        "agent_role": "git",
                        "intent": "git",
                        "dependencies": [],
                        "acceptance_criteria": ["Status is known."],
                        "max_attempts": 2,
                        "recovery_hint": "Re-run status.",
                    },
                    {
                        "description": "Implement changes",
                        "agent_role": "developer",
                        "intent": "coding",
                        "dependencies": [1],
                        "acceptance_criteria": ["Code is written."],
                        "max_attempts": 3,
                        "recovery_hint": "",
                    },
                    {
                        "description": "Run tests",
                        "agent_role": "testing",
                        "intent": "testing",
                        "dependencies": [2],
                        "acceptance_criteria": ["Tests pass."],
                        "max_attempts": 3,
                        "recovery_hint": "Fix failing tests.",
                    },
                    {
                        "description": "Persist decisions",
                        "agent_role": "memory",
                        "intent": "memory",
                        "dependencies": [3],
                        "acceptance_criteria": ["Context saved."],
                        "max_attempts": 1,
                        "recovery_hint": "",
                    },
                    {
                        "description": "Final report",
                        "agent_role": "reporting",
                        "intent": "project_update",
                        "dependencies": [4],
                        "acceptance_criteria": ["Summary generated."],
                        "max_attempts": 1,
                        "recovery_hint": "",
                    },
                ],
            })
        )

        result = brain.decompose_goal("Update my project", "project_update")

        assert result is not None
        assert len(result.subtasks) == 5
        assert result.subtasks[0].agent_role == "git"
        assert result.subtasks[1].agent_role == "developer"
        assert result.subtasks[2].agent_role == "testing"
        assert result.subtasks[3].agent_role == "memory"
        assert result.subtasks[4].agent_role == "reporting"
        assert result.subtasks[2].dependencies == [2]
        assert len(result.assumptions) >= 1

    def test_returns_none_when_api_unavailable(self):
        brain = _make_brain(available=False)

        result = brain.decompose_goal("Update my project", "project_update")

        assert result is None

    def test_returns_none_on_empty_subtasks(self):
        brain = _make_brain()
        brain._client.models.generate_content.return_value = _mock_gemini_response(
            json.dumps({"summary": "Empty.", "assumptions": [], "risks": [], "subtasks": []})
        )

        result = brain.decompose_goal("Do nothing", "unknown")

        assert result is None

    def test_clamps_invalid_agent_role_to_developer(self):
        brain = _make_brain()
        brain._client.models.generate_content.return_value = _mock_gemini_response(
            json.dumps({
                "summary": "Single step.",
                "assumptions": [],
                "risks": [],
                "subtasks": [
                    {
                        "description": "Do something",
                        "agent_role": "alien_agent",
                        "dependencies": [],
                        "acceptance_criteria": ["Done."],
                        "max_attempts": 1,
                        "recovery_hint": "",
                    }
                ],
            })
        )

        result = brain.decompose_goal("Weird task", "unknown")

        assert result is not None
        assert result.subtasks[0].agent_role == "developer"


# ---------------------------------------------------------------------------
# 3. Agent Selection
# ---------------------------------------------------------------------------

class TestBrainSelectsAgents:
    def test_selects_correct_agent(self):
        brain = _make_brain()
        brain._client.models.generate_content.return_value = _mock_gemini_response("git")

        result = brain.select_agent("Check repository status and recent commits")

        assert result == "git"

    def test_returns_none_for_invalid_agent(self):
        brain = _make_brain()
        brain._client.models.generate_content.return_value = _mock_gemini_response(
            "super_agent_9000"
        )

        result = brain.select_agent("Something unknown")

        assert result is None

    def test_returns_none_when_unavailable(self):
        brain = _make_brain(available=False)

        result = brain.select_agent("Any task")

        assert result is None


# ---------------------------------------------------------------------------
# 4. Failure Recovery
# ---------------------------------------------------------------------------

class TestBrainRecovery:
    def test_recovery_strategy_includes_actionable_fix(self):
        brain = _make_brain()
        brain._client.models.generate_content.return_value = _mock_gemini_response(
            json.dumps({
                "action": "retry",
                "strategy": "Fix the SyntaxError on line 42 of utils.py by adding the missing colon.",
                "modified_description": "Fix SyntaxError in utils.py at line 42",
                "requires_user": False,
            })
        )

        result = brain.generate_recovery_strategy(
            step_description="Run tests",
            agent_role="testing",
            error_output="SyntaxError: invalid syntax (utils.py, line 42)",
            attempt_number=1,
            max_attempts=3,
        )

        assert result is not None
        assert result.action == "retry"
        assert "SyntaxError" in result.strategy
        assert result.requires_user is False

    def test_escalation_when_user_needed(self):
        brain = _make_brain()
        brain._client.models.generate_content.return_value = _mock_gemini_response(
            json.dumps({
                "action": "escalate",
                "strategy": "Database credentials are needed. User must provide them.",
                "modified_description": "",
                "requires_user": True,
            })
        )

        result = brain.generate_recovery_strategy(
            step_description="Connect to database",
            agent_role="developer",
            error_output="PermissionError: missing credentials",
            attempt_number=2,
            max_attempts=3,
        )

        assert result is not None
        assert result.action == "escalate"
        assert result.requires_user is True


# ---------------------------------------------------------------------------
# 5. Execution Summary
# ---------------------------------------------------------------------------

class TestBrainSummary:
    def test_summary_includes_all_plan_phases(self):
        brain = _make_brain()
        brain._client.models.generate_content.return_value = _mock_gemini_response(
            "## Goal\nUpdate project\n## Execution Flow\n- ✅ Git Agent inspected repo\n"
            "- ✅ Developer Agent made changes\n- ✅ Testing Agent verified\n"
            "## Result\nAll steps completed successfully.\n## Next Steps\nCommit and push."
        )

        plan_data = {
            "goal": "Update my project",
            "intent": "project_update",
            "status": "completed",
            "steps": [
                {"step_id": 1, "description": "Check git", "agent_role": "git", "status": "success", "result": "clean"},
                {"step_id": 2, "description": "Implement", "agent_role": "developer", "status": "success", "result": "done"},
                {"step_id": 3, "description": "Test", "agent_role": "testing", "status": "success", "result": "passed"},
            ],
        }

        result = brain.generate_execution_summary(plan_data)

        assert result is not None
        assert "Git Agent" in result
        assert "Developer Agent" in result
        assert "✅" in result


# ---------------------------------------------------------------------------
# 6. Caching
# ---------------------------------------------------------------------------

class TestBrainCaching:
    def test_caches_identical_goals(self):
        brain = _make_brain()
        brain._client.models.generate_content.return_value = _mock_gemini_response(
            json.dumps({
                "intent": "coding",
                "confidence": 0.9,
                "reasoning": "Coding task.",
                "entities": [],
                "is_multi_intent": False,
                "secondary_intents": [],
            })
        )

        first = brain.understand_intent("Build a feature")
        second = brain.understand_intent("Build a feature")

        assert first is not None
        assert second is not None
        assert first.intent == second.intent
        # Gemini should only be called once due to caching
        assert brain._client.models.generate_content.call_count == 1

    def test_cache_expires(self):
        entry = _CacheEntry(result="test", created_at=time.time() - 400, ttl=300)
        assert entry.expired is True

        fresh = _CacheEntry(result="test", created_at=time.time(), ttl=300)
        assert fresh.expired is False


# ---------------------------------------------------------------------------
# 7. Fallback Behavior
# ---------------------------------------------------------------------------

class TestBrainFallback:
    def test_falls_back_to_rules_without_api_key(self):
        brain = _make_brain(available=False)

        assert brain.understand_intent("anything") is None
        assert brain.decompose_goal("anything", "unknown") is None
        assert brain.select_agent("anything") is None
        assert brain.generate_recovery_strategy("step", "dev", "err", 1, 3) is None
        assert brain.generate_execution_summary({}) is None
        assert brain.reflect_on_plan({}) is None

    def test_api_error_returns_none(self):
        brain = _make_brain()
        brain._client.models.generate_content.side_effect = Exception("API down")

        assert brain.understand_intent("anything") is None
        assert brain._last_reasoning_trace.startswith("API Error")


# ---------------------------------------------------------------------------
# 8. Status
# ---------------------------------------------------------------------------

class TestBrainStatus:
    def test_status_returns_dict(self):
        brain = _make_brain()
        status = brain.status()

        assert status["available"] is True
        assert status["model"] == "gemini-2.5-flash"
        assert "cached_plans" in status
        assert "total_calls" in status

    def test_status_unavailable(self):
        brain = _make_brain(available=False)
        status = brain.status()

        assert status["available"] is False


# ---------------------------------------------------------------------------
# 9. Reflection
# ---------------------------------------------------------------------------

class TestBrainReflection:
    def test_reflect_extracts_lessons(self):
        brain = _make_brain()
        brain._client.models.generate_content.return_value = _mock_gemini_response(
            json.dumps({
                "lessons_learned": ["Always run tests after code changes."],
                "patterns_detected": ["Testing always follows developer steps."],
                "recommendations": ["Add pre-commit hooks."],
            })
        )

        result = brain.reflect_on_plan({
            "goal": "Build feature",
            "status": "completed",
            "history": [{"step_id": 1, "agent_role": "developer", "status": "success"}],
        })

        assert result is not None
        assert len(result.lessons_learned) >= 1
        assert "tests" in result.lessons_learned[0].lower()

    def test_reflect_returns_none_when_unavailable(self):
        brain = _make_brain(available=False)
        assert brain.reflect_on_plan({}) is None
