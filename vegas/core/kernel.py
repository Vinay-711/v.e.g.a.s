"""
Core Kernel Coordinator for VEGAS AIOS.
Acts as the central CPU, linking Planning, Runtimes, Memory, and Security Guardrails.
The Kernel instantiates the AI Brain and injects it into the Planner.
"""

from typing import Any, Dict

from vegas.core.brain import brain
from vegas.core.executor import DelegatingAgentExecutor
from vegas.core.memory import memory
from vegas.core.planner import PlanStatus, planner
from vegas.runtime.sandbox import sandbox
from vegas.security.guardrails import guardrails
from vegas.skills.manager import skill_manager


class VegasKernel:
    def __init__(self):
        self.memory = memory
        self.planner = planner
        self.brain = brain
        self.sandbox = sandbox
        self.skill_manager = skill_manager
        self.guardrails = guardrails
        self._executor = None

        # Inject the AI Brain into the Planner
        self.planner.set_brain(self.brain)

    @property
    def registry(self):
        """Lazy-loaded AgentRegistry to prevent circular import during tool initialization."""
        from vegas.agents import agent_registry
        return agent_registry

    @property
    def executor(self) -> DelegatingAgentExecutor:
        """Lazy-loaded DelegatingAgentExecutor."""
        if self._executor is None:
            self._executor = DelegatingAgentExecutor(registry=self.registry)
        return self._executor

    def process_system_command(self, query: str) -> Dict[str, Any]:
        """
        Main entry point for incoming user goals or text inputs.
        If it requires complex multi-step execution, generates a plan.
        """
        # Record user query in episodic memory
        self.memory.record_turn("user", query)

        plan = self.planner.create_plan(query)
        if len(plan.steps) > 1 or plan.intent not in {"chat", "unknown"}:
            return {
                "response": f"Affirmative. Planned {len(plan.steps)} coordinated step(s) for: {query}",
                "action": "planning_active",
                "plan": plan.serialize(),
            }

        return {
            "response": f"Vegas Core Kernel: Processing query '{query}' in single-turn response mode.",
            "action": "complete",
            "plan": plan.serialize(),
        }

    def execute_next_plan_step(self) -> Dict[str, Any]:
        """
        Retrieves the next pending step from the planner and runs it.
        """
        if not self.planner.active_plan:
            return {"status": "idle", "message": "No active plan to execute."}

        result = self.planner.execute_next(self.executor)
        if self.planner.active_plan and self.planner.active_plan.status == PlanStatus.COMPLETED.value:
            result["summary"] = self.planner.execution_summary()
            # Trigger post-execution reflection to persist lessons learned
            reflection = self.planner.post_execution_reflect()
            if reflection:
                result["reflection"] = reflection
        return result


# Global Kernel instance
kernel = VegasKernel()
