"""Agent executors used by the VEGAS planner.

The planner owns intent, sequencing, and recovery. Executors delegate execution
to specialized agents via the AgentRegistry without exposing raw tools directly to the Planner.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from vegas.core.planner import ExecutionPlan, StepStatus, TaskNode
from vegas.memory import log_event


class DelegatingAgentExecutor:
    """Dispatch planner steps to specialized agents via AgentRegistry."""

    def __init__(self, repo_path: str | None = None, coding_backend: str | None = None, registry: Optional[Any] = None):
        self.repo_path = str(Path(repo_path or os.getcwd()).expanduser().resolve())
        self.coding_backend = (coding_backend or os.getenv("VEGAS_CODING_AGENT", "antigravity")).strip()
        if registry is None:
            from vegas.agents import registry as default_registry
            self.registry = default_registry
        else:
            self.registry = registry

    def execute(self, step: TaskNode, plan: ExecutionPlan) -> Dict[str, Any]:
        role = step.agent_role
        log_event(
            "planner",
            f"Dispatching step {step.step_id} to {role}",
            f"Plan {plan.plan_id}: {step.description}",
        )

        context = {
            "repo_path": self.repo_path,
            "coding_backend": self.coding_backend,
            "plan_id": plan.plan_id,
            "goal": plan.goal,
            "intent": plan.intent,
            "step": step,
            "plan": plan,
        }

        # Dispatch step through the multi-agent registry
        agent_result = self.registry.dispatch(role, step.description, context)

        # Convert AgentResult to expected Executor return schema
        status_val = (
            StepStatus.SUCCESS.value if agent_result.status == "success"
            else StepStatus.BLOCKED.value if agent_result.status == "blocked"
            else StepStatus.FAILED.value
        )

        return {
            "status": status_val,
            "result": agent_result.result,
            "agent_role": agent_result.agent_role,
        }
