import json

from fastapi.testclient import TestClient

from vegas.core.planner import Planner, StepStatus


def _mute_core_memory(monkeypatch):
    import vegas.core.planner as planner_module

    monkeypatch.setattr(planner_module.memory, "set_objective", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(planner_module.memory, "update_task_list", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(planner_module.memory, "store_fact", lambda *_args, **_kwargs: None)


def _detach_brain(planner_instance):
    """Ensure the planner uses rule-based logic, not the AI Brain."""
    planner_instance._brain = None


def test_planner_routes_update_my_project_to_specialist_agents(monkeypatch):
    _mute_core_memory(monkeypatch)
    planner = Planner()
    _detach_brain(planner)

    plan = planner.create_plan("Update my project")

    assert plan.intent == "project_update"
    assert [step.agent_role for step in plan.steps] == [
        "git",
        "developer",
        "testing",
        "memory",
        "reporting",
    ]
    assert "existing VEGAS architecture" in plan.assumptions[0]
    assert plan.serialize()["steps"][0]["agent"] == "Git Agent"


def test_planner_coordinates_execution_through_executor_only(monkeypatch):
    _mute_core_memory(monkeypatch)
    planner = Planner()
    _detach_brain(planner)
    planner.initialize_plan("Verify project", ["Run focused tests"])
    planner.active_plan.steps[0].agent_role = "testing"

    class FakeExecutor:
        def __init__(self):
            self.calls = []

        def execute(self, step, plan):
            self.calls.append((step.description, plan.goal))
            return {"status": StepStatus.SUCCESS.value, "result": "tests passed"}

    executor = FakeExecutor()
    result = planner.execute_next(executor)

    assert executor.calls == [("Run focused tests", "Verify project")]
    assert result["status"] == "success"
    assert planner.active_plan.status == "completed"
    assert "Completed: 1/1" in planner.execution_summary()


def test_planner_failure_creates_recovery_hint_before_final_failure(monkeypatch):
    _mute_core_memory(monkeypatch)
    planner = Planner()
    _detach_brain(planner)
    plan = planner.initialize_plan("Fix syntax", ["Repair SyntaxError in module"])
    plan.steps[0].max_attempts = 2

    class FailingExecutor:
        def execute(self, step, plan):
            return {"status": StepStatus.FAILED.value, "result": "SyntaxError: invalid syntax"}

    first = planner.execute_next(FailingExecutor())
    second = planner.execute_next(FailingExecutor())

    assert first["status"] == "retry_pending"
    assert "syntax fix" in first["strategy"].lower()
    assert second["status"] == "failed"
    assert planner.active_plan.status == "failed"


def test_confirmation_gate_sets_plan_to_needs_confirmation(monkeypatch):
    _mute_core_memory(monkeypatch)
    planner = Planner()
    _detach_brain(planner)
    planner.initialize_plan("Commit changes", ["Create git commit"])
    planner.active_plan.steps[0].agent_role = "git"

    class ConfirmationExecutor:
        def execute(self, step, plan):
            return {
                "status": StepStatus.SUCCESS.value,
                "result": "VEGAS: This action requires your confirmation - confirm task abc123",
            }

    result = planner.execute_next(ConfirmationExecutor())

    assert result["status"] == "blocked"
    assert planner.active_plan.status == "needs_confirmation"
    assert "needs user confirmation" in result["step"]["result"]


def test_aios_planner_tools_return_json(monkeypatch):
    _mute_core_memory(monkeypatch)
    from vegas.tools.aios import get_planner_status, plan_goal

    planned = json.loads(plan_goal("Update my project"))
    status = json.loads(get_planner_status())

    assert planned["action"] == "planning_active"
    assert planned["plan"]["intent"] == "project_update"
    assert status["active"]["plan_id"] == planned["plan"]["plan_id"]
    assert any(agent["role"] == "developer" for agent in status["agents"])


def test_api_planner_status_endpoint_exposes_active_plan(monkeypatch):
    _mute_core_memory(monkeypatch)
    import api

    # Ensure the kernel planner uses rules, not AI
    api.kernel.planner._brain = None

    client = TestClient(api.app)
    plan_response = client.post("/api/planner/plan", json={"goal": "Update my project"})
    status_response = client.get("/api/planner/status")

    assert plan_response.status_code == 200
    assert status_response.status_code == 200
    assert plan_response.json()["plan"]["intent"] == "project_update"
    assert status_response.json()["active"]["goal"] == "Update my project"


def test_post_execution_reflect_persists_lessons(monkeypatch):
    from unittest.mock import MagicMock
    from vegas.core.brain import ExecutionReflection

    _mute_core_memory(monkeypatch)
    planner = Planner()

    # Create and complete a simple plan
    planner.initialize_plan("Test goal", ["Step 1"])
    planner.record_step_result(1, "success", "done")

    # Attach a mock brain that returns a reflection
    mock_brain = MagicMock()
    mock_brain.reflect_on_plan.return_value = ExecutionReflection(
        lessons_learned=["Always verify outputs."],
        patterns_detected=["Testing follows coding."],
        recommendations=["Add linting."],
    )
    planner._brain = mock_brain

    result = planner.post_execution_reflect()

    assert result is not None
    assert "Always verify outputs." in result["lessons_learned"]
    assert "Testing follows coding." in result["patterns_detected"]
    mock_brain.reflect_on_plan.assert_called_once()
