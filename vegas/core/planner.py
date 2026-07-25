"""
Planner brain for VEGAS AIOS.

The planner understands a user goal, decomposes it into ordered subtasks,
assigns each subtask to a specialized agent role, tracks execution, applies
bounded recovery, and produces a final report. It does not call low-level tools
directly; execution is performed through an injected agent executor.

When a VegasBrain instance is attached, the planner delegates intent
classification, decomposition, agent selection, recovery, and summarization
to the Gemini-powered AI engine.  When the Brain is unavailable or returns
None, all methods fall back to the original rule-based logic transparently.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Optional, Protocol

from vegas.core.memory import memory

if TYPE_CHECKING:
    from vegas.core.brain import VegasBrain


class PlannerError(Exception):
    """Raised when a plan cannot be created or coordinated safely."""


class Intent(str, Enum):
    CHAT = "chat"
    PROJECT_UPDATE = "project_update"
    CODING = "coding"
    TESTING = "testing"
    GIT = "git"
    RESEARCH = "research"
    BROWSER = "browser"
    DEVICE = "device"
    WORKFLOW = "workflow"
    MEMORY = "memory"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class PlanStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    NEEDS_CONFIRMATION = "needs_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class AgentProfile:
    """Planner-visible capability profile for a specialized executor."""

    role: str
    display_name: str
    purpose: str
    capabilities: tuple[str, ...]
    safe_for_background: bool = True


AGENT_PROFILES: Dict[str, AgentProfile] = {
    "git": AgentProfile(
        "git",
        "Git Agent",
        "Inspects repository state and prepares commit/branch operations.",
        ("git_status", "git_diff", "change_summary"),
    ),
    "developer": AgentProfile(
        "developer",
        "Developer Agent",
        "Implements scoped code, file, and integration changes through coding delegation.",
        ("code_editing", "debugging", "implementation"),
        safe_for_background=False,
    ),
    "testing": AgentProfile(
        "testing",
        "Testing Agent",
        "Runs or delegates verification and reports failures with enough detail to recover.",
        ("tests", "builds", "lint", "verification"),
        safe_for_background=False,
    ),
    "research": AgentProfile(
        "research",
        "Research Agent",
        "Finds and summarizes external or local reference material.",
        ("web_research", "document_research", "summaries"),
    ),
    "browser": AgentProfile(
        "browser",
        "Browser Agent",
        "Performs browser observation and browser automation tasks.",
        ("browse", "extract", "form_fill"),
        safe_for_background=False,
    ),
    "device": AgentProfile(
        "device",
        "Device Agent",
        "Coordinates connected phones, tablets, and paired devices.",
        ("device_discovery", "phone_control", "sms", "calls"),
        safe_for_background=False,
    ),
    "workflow": AgentProfile(
        "workflow",
        "Workflow Agent",
        "Handles calendar, email drafting, briefings, and recurring work.",
        ("calendar", "email_drafts", "briefings"),
        safe_for_background=False,
    ),
    "memory": AgentProfile(
        "memory",
        "Memory Agent",
        "Records durable context, decisions, task state, and execution history.",
        ("working_memory", "semantic_memory", "task_history"),
    ),
    "safety": AgentProfile(
        "safety",
        "Safety Agent",
        "Identifies confirmation gates, risky operations, and required user approvals.",
        ("confirmation", "risk_review", "policy_check"),
    ),
    "reporting": AgentProfile(
        "reporting",
        "Reporting Agent",
        "Synthesizes plan results into a clear final execution summary.",
        ("summaries", "next_steps", "failure_reports"),
    ),
}


@dataclass
class TaskNode:
    description: str
    step_id: int
    agent_role: str = "developer"
    intent: str = Intent.UNKNOWN.value
    dependencies: list[int] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    status: str = StepStatus.PENDING.value
    result: str = ""
    attempts: int = 0
    max_attempts: int = 3
    recovery_hint: str = ""
    started_at: Optional[float] = None
    finished_at: Optional[float] = None

    def serialize(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "description": self.description,
            "agent_role": self.agent_role,
            "agent": AGENT_PROFILES.get(self.agent_role, AGENT_PROFILES["developer"]).display_name,
            "intent": self.intent,
            "dependencies": self.dependencies,
            "acceptance_criteria": self.acceptance_criteria,
            "status": self.status,
            "result": self.result,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "recovery_hint": self.recovery_hint,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass
class ExecutionPlan:
    goal: str
    plan_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    intent: str = Intent.UNKNOWN.value
    status: str = PlanStatus.PLANNED.value
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    current_step_idx: int = 0
    confidence: float = 0.5
    summary: str = ""
    steps: List[TaskNode] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)

    def add_step(
        self,
        description: str,
        agent_role: str = "developer",
        *,
        intent: str | Intent | None = None,
        dependencies: Optional[Iterable[int]] = None,
        acceptance_criteria: Optional[Iterable[str]] = None,
        max_attempts: int = 3,
    ) -> TaskNode:
        role = agent_role if agent_role in AGENT_PROFILES else "developer"
        step_id = len(self.steps) + 1
        node = TaskNode(
            description=description,
            step_id=step_id,
            agent_role=role,
            intent=(intent.value if isinstance(intent, Intent) else intent) or self.intent,
            dependencies=list(dependencies or ([] if step_id == 1 else [step_id - 1])),
            acceptance_criteria=list(acceptance_criteria or []),
            max_attempts=max(1, max_attempts),
        )
        self.steps.append(node)
        self.touch()
        return node

    def touch(self) -> None:
        self.updated_at = time.time()

    def get_active_step(self) -> Optional[TaskNode]:
        while self.current_step_idx < len(self.steps):
            step = self.steps[self.current_step_idx]
            if step.status in {StepStatus.SUCCESS.value, StepStatus.SKIPPED.value}:
                self.current_step_idx += 1
                continue
            return step
        return None

    def completed(self) -> bool:
        return bool(self.steps) and all(step.status == StepStatus.SUCCESS.value for step in self.steps)

    def serialize(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "intent": self.intent,
            "status": self.status,
            "confidence": self.confidence,
            "summary": self.summary,
            "current_step_idx": self.current_step_idx,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "assumptions": self.assumptions,
            "risks": self.risks,
            "steps": [step.serialize() for step in self.steps],
            "history": self.history,
        }


class AgentExecutor(Protocol):
    """Interface used by the planner to delegate work without calling tools."""

    def execute(self, step: TaskNode, plan: ExecutionPlan) -> Dict[str, Any]:
        ...


class Planner:
    """Intent-aware coordinator for VEGAS task execution."""

    def __init__(self):
        self.active_plan: Optional[ExecutionPlan] = None
        self.plans: Dict[str, ExecutionPlan] = {}
        self._brain: Optional[VegasBrain] = None

    def set_brain(self, brain: VegasBrain) -> None:
        """Attach the AI Brain to enable Gemini-powered reasoning."""
        self._brain = brain

    def initialize_plan(self, goal: str, steps_list: List[str]) -> ExecutionPlan:
        """Backward-compatible entry point for callers that already provide steps."""
        plan = ExecutionPlan(goal=goal, intent=self.classify_intent(goal).value)
        for step in steps_list:
            role = self.choose_agent(step, plan.intent)
            plan.add_step(step, role, acceptance_criteria=["Step result is recorded."])
        return self._activate(plan)

    def create_plan(self, goal: str) -> ExecutionPlan:
        """Create and activate a detailed plan for a user goal."""
        clean_goal = " ".join(goal.strip().split())
        if not clean_goal:
            raise PlannerError("Cannot plan an empty goal.")

        # Automatic Memory Retrieval
        memory_context = memory.build_context_block(clean_goal)

        intent = self.classify_intent(clean_goal)
        plan = ExecutionPlan(
            goal=clean_goal,
            intent=intent.value,
            confidence=self._intent_confidence(clean_goal, intent),
        )
        plan.assumptions = self._assumptions_for(clean_goal, intent)
        if memory_context and memory_context != "No prior context stored.":
            plan.assumptions.append(f"Retrieved Context: {memory_context[:250]}...")

        plan.risks = self._risks_for(clean_goal, intent)
        plan.summary = self._goal_summary(clean_goal, intent)

        for spec in self._decompose(clean_goal, intent):
            plan.add_step(
                spec["description"],
                spec["agent_role"],
                intent=spec.get("intent", intent.value),
                dependencies=spec.get("dependencies"),
                acceptance_criteria=spec.get("acceptance_criteria", []),
                max_attempts=spec.get("max_attempts", 3),
            )

        return self._activate(plan)

    def _activate(self, plan: ExecutionPlan) -> ExecutionPlan:
        self.active_plan = plan
        self.plans[plan.plan_id] = plan
        memory.set_objective(plan.goal)
        memory.update_task_list(
            [f"{step.step_id}. {step.agent_role}: {step.description}" for step in plan.steps]
        )
        memory.store_fact("active_execution_plan", plan.serialize())
        return plan

    def classify_intent(self, goal: str) -> Intent:
        # --- AI Brain delegation ---
        if self._brain and self._brain.available:
            analysis = self._brain.understand_intent(goal)
            if analysis is not None:
                try:
                    return Intent(analysis.intent)
                except ValueError:
                    pass  # Fall through to rule-based

        # --- Rule-based fallback ---
        text = goal.lower()
        keyword_map: tuple[tuple[Intent, tuple[str, ...]], ...] = (
            (Intent.PROJECT_UPDATE, ("update my project", "update the project", "upgrade project", "ship project")),
            (Intent.CODING, ("implement", "build", "fix", "refactor", "write code", "feature", "bug")),
            (Intent.TESTING, ("test", "verify", "lint", "build check", "failing test")),
            (Intent.GIT, ("git", "commit", "branch", "status", "diff", "push", "pull")),
            (Intent.RESEARCH, ("research", "search", "find out", "look up", "latest")),
            (Intent.BROWSER, ("browser", "website", "web page", "form", "click", "open site")),
            (Intent.DEVICE, ("phone", "device", "sms", "call", "bluetooth", "pair")),
            (Intent.WORKFLOW, ("calendar", "email", "briefing", "schedule", "meeting")),
            (Intent.MEMORY, ("remember", "recall", "what do you know", "forget")),
            (Intent.SYSTEM, ("system", "cpu", "memory", "volume", "play music", "open app")),
        )
        for intent, keywords in keyword_map:
            if any(keyword in text for keyword in keywords):
                return intent
        if len(text.split()) <= 8:
            return Intent.CHAT
        return Intent.UNKNOWN

    def choose_agent(self, task_description: str, intent: str | Intent) -> str:
        """Choose the best specialized agent role for a task description."""
        # --- AI Brain delegation ---
        if self._brain and self._brain.available:
            ai_choice = self._brain.select_agent(task_description, str(intent))
            if ai_choice is not None:
                return ai_choice

        # --- Rule-based fallback ---
        text = task_description.lower()
        try:
            normalized_intent = intent if isinstance(intent, Intent) else Intent(str(intent))
        except ValueError:
            normalized_intent = Intent.UNKNOWN
        if any(word in text for word in ("git", "commit", "branch", "diff", "status")):
            return "git"
        if any(word in text for word in ("test", "verify", "lint", "build", "pytest", "npm")):
            return "testing"
        if any(word in text for word in ("remember", "memory", "record", "learn", "persist")):
            return "memory"
        if any(word in text for word in ("report", "summary", "summarize", "final")):
            return "reporting"
        if any(word in text for word in ("risk", "permission", "confirm", "approval", "safety")):
            return "safety"
        if any(word in text for word in ("research", "search", "source", "docs")):
            return "research"
        if any(word in text for word in ("browser", "click", "form", "website")):
            return "browser"
        if any(word in text for word in ("phone", "device", "sms", "call")):
            return "device"
        if any(word in text for word in ("calendar", "email", "meeting", "briefing")):
            return "workflow"
        if normalized_intent == Intent.GIT:
            return "git"
        if normalized_intent == Intent.RESEARCH:
            return "research"
        if normalized_intent == Intent.DEVICE:
            return "device"
        if normalized_intent == Intent.WORKFLOW:
            return "workflow"
        if normalized_intent == Intent.MEMORY:
            return "memory"
        return "developer"

    def record_step_result(self, step_id: int, status: str, result: str) -> None:
        """Records the outcome of a plan step execution."""
        if not self.active_plan:
            return

        normalized = status if status in StepStatus._value2member_map_ else StepStatus.FAILED.value
        for step in self.active_plan.steps:
            if step.step_id != step_id:
                continue
            step.status = normalized
            step.result = result
            step.finished_at = time.time()
            self.active_plan.history.append(
                {
                    "step_id": step_id,
                    "agent_role": step.agent_role,
                    "action": step.description,
                    "status": normalized,
                    "result": result,
                    "timestamp": step.finished_at,
                }
            )
            break

        if normalized == StepStatus.SUCCESS.value:
            while (
                self.active_plan.current_step_idx < len(self.active_plan.steps)
                and self.active_plan.steps[self.active_plan.current_step_idx].status
                == StepStatus.SUCCESS.value
            ):
                self.active_plan.current_step_idx += 1

        if self.active_plan.completed():
            self.active_plan.status = PlanStatus.COMPLETED.value
            self.active_plan.summary = self.execution_summary()
        elif any(step.status == StepStatus.FAILED.value for step in self.active_plan.steps):
            self.active_plan.status = PlanStatus.FAILED.value
        elif any(step.status == StepStatus.BLOCKED.value for step in self.active_plan.steps):
            self.active_plan.status = PlanStatus.NEEDS_CONFIRMATION.value
        else:
            self.active_plan.status = PlanStatus.RUNNING.value

        self.active_plan.touch()
        memory.store_fact("active_execution_plan", self.active_plan.serialize())

    def execute_next(self, executor: AgentExecutor) -> Dict[str, Any]:
        """Coordinate execution of the next step through an injected agent executor."""
        if not self.active_plan:
            return {"status": "idle", "message": "No active plan to execute."}

        step = self.active_plan.get_active_step()
        if not step:
            self.active_plan.status = PlanStatus.COMPLETED.value
            self.active_plan.summary = self.execution_summary()
            memory.store_fact("active_execution_plan", self.active_plan.serialize())
            return {
                "status": "completed",
                "message": f"Execution finished. Goal achieved: {self.active_plan.goal}",
                "summary": self.active_plan.summary,
                "plan": self.active_plan.serialize(),
            }

        blocked_by = [
            dep_id
            for dep_id in step.dependencies
            if self.active_plan.steps[dep_id - 1].status != StepStatus.SUCCESS.value
        ]
        if blocked_by:
            step.status = StepStatus.BLOCKED.value
            self.active_plan.status = PlanStatus.RUNNING.value
            return {
                "status": "blocked",
                "message": f"Step {step.step_id} is waiting on dependencies: {blocked_by}",
                "plan": self.active_plan.serialize(),
            }

        step.status = StepStatus.RUNNING.value
        step.started_at = time.time()
        step.attempts += 1
        self.active_plan.status = PlanStatus.RUNNING.value
        self.active_plan.touch()

        try:
            result = executor.execute(step, self.active_plan)
        except Exception as exc:
            result = {"status": "failed", "result": str(exc)}

        status = str(result.get("status", StepStatus.FAILED.value))
        output = str(result.get("result") or result.get("message") or "")
        if "requires your confirmation" in output.lower():
            status = StepStatus.BLOCKED.value
            self.active_plan.status = PlanStatus.NEEDS_CONFIRMATION.value
            output = self._confirmation_message(step, output)
        elif status not in StepStatus._value2member_map_:
            status = StepStatus.SUCCESS.value if result.get("success") else StepStatus.FAILED.value

        if status == StepStatus.FAILED.value and step.attempts < step.max_attempts:
            correction = self.reflect_and_correct(step, output, lambda _cmd: None)
            step.status = StepStatus.PENDING.value
            step.recovery_hint = correction.get("strategy", "")
            self.active_plan.history.append(
                {
                    "step_id": step.step_id,
                    "agent_role": step.agent_role,
                    "action": step.description,
                    "status": "retry_planned",
                    "result": output,
                    "recovery": step.recovery_hint,
                    "timestamp": time.time(),
                }
            )
            memory.store_fact("active_execution_plan", self.active_plan.serialize())
            return {
                "status": "retry_pending",
                "step": step.serialize(),
                "strategy": step.recovery_hint,
                "plan": self.active_plan.serialize(),
            }

        self.record_step_result(step.step_id, status, output)
        return {
            "status": status,
            "completed_step": step.description if status == StepStatus.SUCCESS.value else None,
            "step": step.serialize(),
            "plan": self.active_plan.serialize(),
        }

    def execute_all(self, executor: AgentExecutor, *, max_steps: int = 20) -> Dict[str, Any]:
        """Execute steps until completion, failure, confirmation, or max step count."""
        iterations = 0
        last: Dict[str, Any] = {"status": "idle"}
        while iterations < max_steps:
            iterations += 1
            last = self.execute_next(executor)
            if last["status"] in {
                "completed",
                StepStatus.FAILED.value,
                StepStatus.BLOCKED.value,
                PlanStatus.NEEDS_CONFIRMATION.value,
                "retry_pending",
            }:
                break
            if self.active_plan and self.active_plan.status == PlanStatus.COMPLETED.value:
                break
        return {
            "status": self.active_plan.status if self.active_plan else last["status"],
            "last_result": last,
            "summary": self.execution_summary(),
            "plan": self.active_plan.serialize() if self.active_plan else None,
        }

    def reflect_and_correct(
        self,
        step: TaskNode,
        error_output: str,
        tool_caller: Callable[[str], Any],
    ) -> Dict[str, Any]:
        """
        Analyze a failed delegated step and prepare a retry strategy.

        The ``tool_caller`` parameter remains for backward compatibility but is
        intentionally unused: the planner coordinates, it does not execute tools.
        """
        del tool_caller
        if step.attempts >= step.max_attempts:
            step.status = StepStatus.FAILED.value
            return {
                "action": "abort",
                "message": f"Step '{step.description}' failed after {step.attempts} attempts: {error_output}",
            }

        # --- AI Brain delegation ---
        if self._brain and self._brain.available:
            plan_context = self.active_plan.goal if self.active_plan else ""
            recovery = self._brain.generate_recovery_strategy(
                step_description=step.description,
                agent_role=step.agent_role,
                error_output=error_output,
                attempt_number=step.attempts,
                max_attempts=step.max_attempts,
                plan_context=plan_context,
            )
            if recovery is not None:
                return {
                    "action": recovery.action,
                    "strategy": recovery.strategy,
                    "attempt": step.attempts + 1,
                    "modified_description": recovery.modified_description,
                    "requires_user": recovery.requires_user,
                }

        # --- Rule-based fallback ---
        lowered = error_output.lower()
        if "syntaxerror" in lowered or "indentationerror" in lowered:
            strategy = "Return the failing file and exact parser error to the Developer Agent for a minimal syntax fix."
        elif "modulenotfounderror" in lowered or "no module named" in lowered:
            strategy = "Ask the Developer Agent to inspect dependencies and add or document the missing package."
        elif "permission" in lowered or "denied" in lowered or "requires your confirmation" in lowered:
            strategy = "Pause execution and request explicit user confirmation or an alternate safe route."
        elif "timeout" in lowered:
            strategy = "Retry with a narrower command, smaller scope, or longer-running delegated agent."
        elif "high demand" in lowered or "rate limit" in lowered:
            strategy = "Retry later or switch to another configured coding agent backend."
        else:
            strategy = "Ask the assigned agent to summarize the failure, adjust the approach, and retry once."

        return {"action": "retry", "strategy": strategy, "attempt": step.attempts + 1}

    def execution_summary(self) -> str:
        if not self.active_plan:
            return "No active execution plan."

        # --- AI Brain delegation ---
        if self._brain and self._brain.available:
            ai_summary = self._brain.generate_execution_summary(self.active_plan.serialize())
            if ai_summary:
                return ai_summary

        # --- Rule-based fallback ---
        plan = self.active_plan
        completed = [step for step in plan.steps if step.status == StepStatus.SUCCESS.value]
        failed = [step for step in plan.steps if step.status == StepStatus.FAILED.value]
        blocked = [step for step in plan.steps if step.status == StepStatus.BLOCKED.value]
        lines = [
            f"Goal: {plan.goal}",
            f"Status: {plan.status}",
            f"Completed: {len(completed)}/{len(plan.steps)}",
        ]
        if failed:
            lines.append("Failed: " + "; ".join(f"{step.step_id}. {step.description}" for step in failed))
        if blocked:
            lines.append("Blocked: " + "; ".join(f"{step.step_id}. {step.description}" for step in blocked))
        if plan.history:
            last = plan.history[-1]
            lines.append(f"Last result: Step {last['step_id']} via {last['agent_role']} -> {last['status']}")
        return "\n".join(lines)

    def post_execution_reflect(self) -> Optional[Dict[str, Any]]:
        """Run post-execution reflection to extract lessons and persist them."""
        if not self.active_plan or not self._brain:
            return None
        reflection = self._brain.reflect_on_plan(self.active_plan.serialize())
        if reflection is None:
            return None
        result = asdict(reflection)
        # Persist lessons in memory
        memory.store_fact(
            f"lessons:{self.active_plan.plan_id}",
            {
                "goal": self.active_plan.goal,
                "intent": self.active_plan.intent,
                "status": self.active_plan.status,
                **result,
            },
        )
        return result

    def status(self) -> Dict[str, Any]:
        return {
            "active": self.active_plan.serialize() if self.active_plan else None,
            "known_plans": len(self.plans),
            "agents": [profile.__dict__ for profile in AGENT_PROFILES.values()],
            "brain": self._brain.status() if self._brain else {"available": False},
        }

    def _decompose(self, goal: str, intent: Intent) -> List[Dict[str, Any]]:
        # --- AI Brain delegation ---
        if self._brain and self._brain.available:
            result = self._brain.decompose_goal(goal, intent.value)
            if result is not None and result.subtasks:
                return [
                    {
                        "description": s.description,
                        "agent_role": s.agent_role,
                        "intent": s.intent or intent.value,
                        "dependencies": s.dependencies if s.dependencies else None,
                        "acceptance_criteria": s.acceptance_criteria,
                        "max_attempts": s.max_attempts,
                    }
                    for s in result.subtasks
                ]

        # --- Rule-based fallback ---
        return self._decompose_rules(goal, intent)

    def _decompose_rules(self, goal: str, intent: Intent) -> List[Dict[str, Any]]:
        """Original rule-based decomposition templates."""
        if intent == Intent.PROJECT_UPDATE:
            return [
                {
                    "description": f"Inspect repository state for project update request: {goal}",
                    "agent_role": "git",
                    "acceptance_criteria": ["Current branch, dirty files, and recent changes are known."],
                },
                {
                    "description": f"Implement the requested project update: {goal}",
                    "agent_role": "developer",
                    "acceptance_criteria": ["Existing architecture is extended without unrelated rewrites."],
                },
                {
                    "description": "Run focused verification for the changed project areas.",
                    "agent_role": "testing",
                    "acceptance_criteria": ["Relevant tests or build checks have been executed or a blocker is recorded."],
                },
                {
                    "description": "Record important decisions, changed behavior, and residual risks in memory.",
                    "agent_role": "memory",
                    "acceptance_criteria": ["Execution context is persisted for future sessions."],
                },
                {
                    "description": "Produce a final project update report for the user.",
                    "agent_role": "reporting",
                    "acceptance_criteria": ["Summary includes changes, verification, failures, and next steps."],
                },
            ]
        if intent == Intent.CODING:
            return [
                {
                    "description": f"Analyze implementation scope and impacted files for: {goal}",
                    "agent_role": "developer",
                    "acceptance_criteria": ["Target modules and constraints are identified."],
                },
                {
                    "description": f"Delegate implementation work for: {goal}",
                    "agent_role": "developer",
                    "acceptance_criteria": ["Code changes are scoped and compatible with existing architecture."],
                },
                {
                    "description": "Verify the implementation with focused tests or builds.",
                    "agent_role": "testing",
                    "acceptance_criteria": ["Verification output is captured."],
                },
                {
                    "description": "Store implementation summary and final report.",
                    "agent_role": "memory",
                    "acceptance_criteria": ["What changed and what remains are persisted."],
                },
                {
                    "description": "Summarize the implementation outcome.",
                    "agent_role": "reporting",
                    "acceptance_criteria": ["User receives a concise execution summary."],
                },
            ]
        if intent == Intent.TESTING:
            return [
                {
                    "description": f"Determine the smallest meaningful verification command for: {goal}",
                    "agent_role": "testing",
                    "acceptance_criteria": ["Verification target is explicit."],
                },
                {
                    "description": "Run or delegate the verification task.",
                    "agent_role": "testing",
                    "acceptance_criteria": ["Results include pass/fail and useful failure details."],
                },
                {
                    "description": "Report verification status and recommended fixes.",
                    "agent_role": "reporting",
                    "acceptance_criteria": ["Failures have actionable next steps."],
                },
            ]
        if intent == Intent.GIT:
            return [
                {
                    "description": f"Inspect git repository state for: {goal}",
                    "agent_role": "git",
                    "acceptance_criteria": ["Git status and diff context are captured."],
                },
                {
                    "description": "Apply safety review before any state-changing git operation.",
                    "agent_role": "safety",
                    "acceptance_criteria": ["Confirmation needs are clearly identified."],
                },
                {
                    "description": "Summarize repository state and next git action.",
                    "agent_role": "reporting",
                    "acceptance_criteria": ["Report names files and required approval, if any."],
                },
            ]
        if intent == Intent.RESEARCH:
            return [
                {
                    "description": f"Research and collect relevant context for: {goal}",
                    "agent_role": "research",
                    "acceptance_criteria": ["Sources or local references are identified."],
                },
                {
                    "description": "Synthesize findings into decision-ready notes.",
                    "agent_role": "reporting",
                    "acceptance_criteria": ["Summary separates facts, uncertainty, and recommendations."],
                },
                {
                    "description": "Store durable research notes in memory.",
                    "agent_role": "memory",
                    "acceptance_criteria": ["Reusable context is saved."],
                },
            ]
        if intent == Intent.BROWSER:
            return [
                {
                    "description": f"Open or inspect the requested browser target: {goal}",
                    "agent_role": "browser",
                    "acceptance_criteria": ["Browser state or extracted page data is captured."],
                },
                {
                    "description": "Apply safety review before submitting forms or changing remote state.",
                    "agent_role": "safety",
                    "acceptance_criteria": ["Any confirmation-gated action is paused for approval."],
                },
                {
                    "description": "Report browser task outcome.",
                    "agent_role": "reporting",
                    "acceptance_criteria": ["User receives the visible result or blocker."],
                },
            ]
        if intent == Intent.DEVICE:
            return [
                {
                    "description": "Discover available connected devices.",
                    "agent_role": "device",
                    "acceptance_criteria": ["Target device availability is known."],
                },
                {
                    "description": f"Coordinate the requested device action: {goal}",
                    "agent_role": "device",
                    "acceptance_criteria": ["Device command result or approval requirement is captured."],
                },
                {
                    "description": "Report device task outcome.",
                    "agent_role": "reporting",
                    "acceptance_criteria": ["User receives final device status."],
                },
            ]
        if intent == Intent.WORKFLOW:
            return [
                {
                    "description": f"Prepare workflow context for: {goal}",
                    "agent_role": "workflow",
                    "acceptance_criteria": ["Relevant calendar, email, or briefing context is gathered."],
                },
                {
                    "description": "Apply safety review before sending, drafting, or scheduling.",
                    "agent_role": "safety",
                    "acceptance_criteria": ["Confirmation-gated operations are parked."],
                },
                {
                    "description": "Report workflow result and pending confirmations.",
                    "agent_role": "reporting",
                    "acceptance_criteria": ["User sees the result and any task IDs."],
                },
            ]
        if intent == Intent.MEMORY:
            return [
                {
                    "description": f"Resolve the memory request: {goal}",
                    "agent_role": "memory",
                    "acceptance_criteria": ["Memory is searched or updated as requested."],
                },
                {
                    "description": "Report memory result.",
                    "agent_role": "reporting",
                    "acceptance_criteria": ["User receives a concise memory response."],
                },
            ]
        if intent == Intent.CHAT:
            return [
                {
                    "description": f"Answer directly while preserving relevant context: {goal}",
                    "agent_role": "reporting",
                    "acceptance_criteria": ["Response is concise and useful."],
                }
            ]
        return [
            {
                "description": f"Clarify objective and identify execution path for: {goal}",
                "agent_role": "safety",
                "acceptance_criteria": ["Ambiguities and safe assumptions are explicit."],
            },
            {
                "description": "Route the clarified objective to the correct specialist agent.",
                "agent_role": "reporting",
                "acceptance_criteria": ["User receives a proposed path or clarification request."],
            },
        ]

    def _intent_confidence(self, goal: str, intent: Intent) -> float:
        if intent in {Intent.CHAT, Intent.UNKNOWN}:
            return 0.55
        words = set(goal.lower().split())
        signal = len(words.intersection({"build", "implement", "update", "test", "git", "phone", "email"}))
        return min(0.95, 0.72 + signal * 0.04)

    def _assumptions_for(self, goal: str, intent: Intent) -> List[str]:
        assumptions = ["Use existing VEGAS architecture and safety gates."]
        if intent in {Intent.CODING, Intent.PROJECT_UPDATE, Intent.TESTING, Intent.GIT}:
            assumptions.append("The current workspace is the target repository unless the user says otherwise.")
        if "update my project" in goal.lower():
            assumptions.append("Project update means inspect, implement, verify, remember, then report.")
        return assumptions

    def _risks_for(self, goal: str, intent: Intent) -> List[str]:
        risks: list[str] = []
        if intent in {Intent.CODING, Intent.PROJECT_UPDATE, Intent.TESTING}:
            risks.append("Coding and test agents may need external model or CLI availability.")
        if intent in {Intent.GIT, Intent.DEVICE, Intent.WORKFLOW, Intent.BROWSER}:
            risks.append("State-changing operations may require explicit confirmation.")
        if intent == Intent.UNKNOWN:
            risks.append("Intent is ambiguous; planner should ask for clarification before mutation.")
        return risks

    def _goal_summary(self, goal: str, intent: Intent) -> str:
        return f"Intent '{intent.value}' routed into {len(self._decompose(goal, intent))} coordinated step(s)."

    def _confirmation_message(self, step: TaskNode, output: str) -> str:
        return (
            f"{AGENT_PROFILES[step.agent_role].display_name} needs user confirmation before continuing.\n"
            f"{output}"
        )


class ThoughtNode:
    def __init__(self, node_id: str, parent_id: Optional[str], content: str):
        self.node_id = node_id
        self.parent_id = parent_id
        self.content = content
        self.score = 0.5
        self.feedback = ""
        self.children: List[str] = []


class TreeOfThoughtsPlanner:
    def __init__(self):
        self.nodes: Dict[str, ThoughtNode] = {}
        self.root_id: Optional[str] = None

    def initialize_tree(self, root_content: str) -> str:
        root_id = "root"
        self.nodes[root_id] = ThoughtNode(root_id, None, root_content)
        self.root_id = root_id
        return root_id

    def propose_thoughts(self, parent_id: str, thoughts: List[str]) -> List[str]:
        if parent_id not in self.nodes:
            raise KeyError(f"Parent node '{parent_id}' not found in tree.")

        generated_ids = []
        for idx, content in enumerate(thoughts, 1):
            node_id = f"{parent_id}_t{idx}"
            node = ThoughtNode(node_id, parent_id, content)
            self.nodes[node_id] = node
            self.nodes[parent_id].children.append(node_id)
            generated_ids.append(node_id)

        return generated_ids

    def evaluate_thought(self, node_id: str, score: float, feedback: str = "") -> None:
        if node_id not in self.nodes:
            raise KeyError(f"Node '{node_id}' not found in tree.")
        self.nodes[node_id].score = max(0.0, min(1.0, score))
        self.nodes[node_id].feedback = feedback

    def get_best_thought_path(self) -> List[str]:
        if not self.root_id:
            return []

        path = []
        curr_id = self.root_id

        while curr_id:
            path.append(self.nodes[curr_id].content)
            children_ids = self.nodes[curr_id].children
            if not children_ids:
                break

            best_child = max(children_ids, key=lambda node_id: self.nodes[node_id].score)
            curr_id = best_child

        return path


planner = Planner()
tree_planner = TreeOfThoughtsPlanner()
