"""
VegasBrain — The Gemini-powered AI reasoning engine for V.E.G.A.S.

The Brain is the intelligence layer that sits between user goals and the
rule-based Planner.  It never executes tools directly.  Instead it:

  1. Understands intent  — classifies what the user wants with confidence.
  2. Decomposes goals    — breaks complex requests into ordered subtasks.
  3. Selects agents      — maps each subtask to the best specialist agent.
  4. Recovers from fails — analyzes errors and proposes retry strategies.
  5. Summarizes results  — produces rich natural-language execution reports.
  6. Reflects & learns   — extracts lessons and persists them in memory.

All Gemini interactions use structured JSON output for reliable parsing.
When the API is unavailable the Brain falls back gracefully and returns
``None`` so the caller can use rule-based defaults.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types


# ---------------------------------------------------------------------------
# Structured output schemas
# ---------------------------------------------------------------------------

@dataclass
class IntentAnalysis:
    """Result of AI intent classification."""
    intent: str
    confidence: float
    reasoning: str
    entities: List[str] = field(default_factory=list)
    is_multi_intent: bool = False
    secondary_intents: List[str] = field(default_factory=list)


@dataclass
class SubtaskSpec:
    """A single decomposed subtask produced by the Brain."""
    description: str
    agent_role: str
    intent: str = ""
    dependencies: List[int] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    max_attempts: int = 3
    recovery_hint: str = ""


@dataclass
class DecompositionResult:
    """Full output of goal decomposition."""
    goal: str
    summary: str
    assumptions: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    subtasks: List[SubtaskSpec] = field(default_factory=list)


@dataclass
class RecoveryStrategy:
    """AI-generated recovery plan for a failed step."""
    action: str          # "retry" | "skip" | "abort" | "escalate"
    strategy: str        # human-readable description
    modified_description: str = ""   # optional rewritten task for retry
    requires_user: bool = False


@dataclass
class ExecutionReflection:
    """Post-execution lessons extracted by the Brain."""
    lessons_learned: List[str] = field(default_factory=list)
    patterns_detected: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Cache entry
# ---------------------------------------------------------------------------

@dataclass
class _CacheEntry:
    result: Any
    created_at: float
    ttl: float = 300.0  # 5 minutes default

    @property
    def expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl


# ---------------------------------------------------------------------------
# The Brain
# ---------------------------------------------------------------------------

# Known agent roles the Brain can route to.
KNOWN_AGENT_ROLES = (
    "git", "developer", "testing", "research", "browser",
    "device", "workflow", "memory", "safety", "reporting",
)

# Known intent types the Brain can classify.
KNOWN_INTENTS = (
    "chat", "project_update", "coding", "testing", "git",
    "research", "browser", "device", "workflow", "memory", "system", "unknown",
)


class VegasBrain:
    """Gemini-powered reasoning engine for the V.E.G.A.S. Planner."""

    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model
        self._client: Optional[genai.Client] = None
        self._cache: Dict[str, _CacheEntry] = {}
        self._last_reasoning_trace: str = ""
        self._call_count: int = 0
        self._init_client()

    def _init_client(self) -> None:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if api_key:
            try:
                self._client = genai.Client(api_key=api_key)
            except Exception:
                self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def status(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "model": self.model,
            "cached_plans": len(self._cache),
            "total_calls": self._call_count,
            "last_reasoning_trace": self._last_reasoning_trace[:500],
        }

    # ------------------------------------------------------------------
    # 1. Intent Understanding
    # ------------------------------------------------------------------

    def understand_intent(self, goal: str) -> Optional[IntentAnalysis]:
        """Classify user intent using Gemini structured output.

        Returns ``None`` when the API is unavailable so the caller can
        fall back to keyword-based classification.
        """
        if not self.available:
            return None

        cache_key = self._cache_key("intent", goal)
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        prompt = (
            "You are the intent-classification module of an AI operating system called V.E.G.A.S.\n"
            "Analyze the following user goal and return a JSON object with these exact keys:\n"
            "- intent: one of " + str(KNOWN_INTENTS) + "\n"
            "- confidence: float 0.0-1.0\n"
            "- reasoning: one sentence explaining your classification\n"
            "- entities: list of key entities/nouns extracted from the goal\n"
            "- is_multi_intent: boolean, true if the goal spans multiple intent categories\n"
            "- secondary_intents: list of secondary intent strings if multi-intent\n\n"
            f'User goal: "{goal}"\n\n'
            "Return ONLY valid JSON, no markdown fences."
        )

        raw = self._call_gemini(prompt)
        if raw is None:
            return None

        try:
            data = json.loads(raw)
            # Clamp intent to known values
            intent_val = data.get("intent", "unknown")
            if intent_val not in KNOWN_INTENTS:
                intent_val = "unknown"
            result = IntentAnalysis(
                intent=intent_val,
                confidence=max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
                reasoning=str(data.get("reasoning", "")),
                entities=list(data.get("entities", [])),
                is_multi_intent=bool(data.get("is_multi_intent", False)),
                secondary_intents=list(data.get("secondary_intents", [])),
            )
            self._set_cache(cache_key, result)
            return result
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # 2. Goal Decomposition
    # ------------------------------------------------------------------

    def decompose_goal(
        self, goal: str, intent: str, confidence: float = 0.7
    ) -> Optional[DecompositionResult]:
        """Break a user goal into ordered subtasks with agent assignments.

        Returns ``None`` when unavailable so the caller uses rule-based templates.
        """
        if not self.available:
            return None

        cache_key = self._cache_key("decompose", goal)
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        prompt = (
            "You are the task-decomposition engine of an AI operating system called V.E.G.A.S.\n"
            "Break the following user goal into an ordered list of subtasks.\n\n"
            "Available specialist agents and their capabilities:\n"
            "- git: repository inspection, status, diff, branch operations\n"
            "- developer: code implementation, file editing, debugging, refactoring\n"
            "- testing: running tests, builds, linting, verification\n"
            "- research: web search, document lookup, summarization\n"
            "- browser: web page automation, scraping, form filling\n"
            "- device: phone/tablet control, SMS, calls, Bluetooth\n"
            "- workflow: Google Calendar, Gmail drafts, morning briefings\n"
            "- memory: storing facts, recalling context, persisting decisions\n"
            "- safety: risk review, confirmation gates, permission checks\n"
            "- reporting: final summaries, next-step recommendations\n\n"
            "Rules:\n"
            "1. Each subtask must be assigned to exactly one agent_role from the list above.\n"
            "2. Include dependencies as step indices (1-based). Step 1 has no dependencies.\n"
            "3. Each subtask needs at least one acceptance_criteria string.\n"
            "4. Provide recovery_hint for steps likely to fail.\n"
            "5. Always end with a 'memory' step to persist context and a 'reporting' step for the final summary.\n"
            "6. Use the minimum number of steps needed — avoid redundancy.\n\n"
            f'User goal: "{goal}"\n'
            f"Classified intent: {intent} (confidence: {confidence:.2f})\n\n"
            "Return a JSON object with keys:\n"
            "- summary: one-line plan summary\n"
            "- assumptions: list of assumptions made\n"
            "- risks: list of identified risks\n"
            "- subtasks: list of objects with keys: description, agent_role, intent, "
            "dependencies (list of int step indices), acceptance_criteria (list of str), "
            "max_attempts (int), recovery_hint (str)\n\n"
            "Return ONLY valid JSON, no markdown fences."
        )

        raw = self._call_gemini(prompt)
        if raw is None:
            return None

        try:
            data = json.loads(raw)
            subtasks = []
            for spec in data.get("subtasks", []):
                role = spec.get("agent_role", "developer")
                if role not in KNOWN_AGENT_ROLES:
                    role = "developer"
                subtasks.append(SubtaskSpec(
                    description=str(spec.get("description", "")),
                    agent_role=role,
                    intent=str(spec.get("intent", intent)),
                    dependencies=[int(d) for d in spec.get("dependencies", [])],
                    acceptance_criteria=list(spec.get("acceptance_criteria", [])),
                    max_attempts=max(1, int(spec.get("max_attempts", 3))),
                    recovery_hint=str(spec.get("recovery_hint", "")),
                ))
            if not subtasks:
                return None
            result = DecompositionResult(
                goal=goal,
                summary=str(data.get("summary", "")),
                assumptions=list(data.get("assumptions", [])),
                risks=list(data.get("risks", [])),
                subtasks=subtasks,
            )
            self._set_cache(cache_key, result)
            return result
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # 3. Agent Selection
    # ------------------------------------------------------------------

    def select_agent(self, task_description: str, context: str = "") -> Optional[str]:
        """AI-powered agent selection for a specific subtask.

        Returns ``None`` when unavailable so the caller uses keyword matching.
        """
        if not self.available:
            return None

        prompt = (
            "You are the agent-routing module of V.E.G.A.S.\n"
            "Given a task description, select the single best specialist agent.\n\n"
            "Available agents: " + ", ".join(KNOWN_AGENT_ROLES) + "\n\n"
            f'Task: "{task_description}"\n'
            f'Context: "{context}"\n\n'
            "Return ONLY the agent role name as a single word, nothing else."
        )

        raw = self._call_gemini(prompt)
        if raw is None:
            return None

        role = raw.strip().lower().split()[0] if raw.strip() else None
        if role and role in KNOWN_AGENT_ROLES:
            return role
        return None

    # ------------------------------------------------------------------
    # 4. Failure Recovery
    # ------------------------------------------------------------------

    def generate_recovery_strategy(
        self,
        step_description: str,
        agent_role: str,
        error_output: str,
        attempt_number: int,
        max_attempts: int,
        plan_context: str = "",
    ) -> Optional[RecoveryStrategy]:
        """Analyze a failed step and produce an intelligent retry strategy."""
        if not self.available:
            return None

        prompt = (
            "You are the failure-recovery module of V.E.G.A.S.\n"
            "A specialist agent step has failed. Analyze the error and recommend a strategy.\n\n"
            f"Failed step: {step_description}\n"
            f"Agent: {agent_role}\n"
            f"Attempt: {attempt_number}/{max_attempts}\n"
            f"Error output (last 1500 chars): {error_output[-1500:]}\n"
            f"Plan context: {plan_context}\n\n"
            "Return a JSON object with keys:\n"
            '- action: one of "retry", "skip", "abort", "escalate"\n'
            "- strategy: human-readable recovery description\n"
            "- modified_description: if retrying, an improved task description (empty string if not retrying)\n"
            "- requires_user: boolean, true if user intervention is needed\n\n"
            "Return ONLY valid JSON, no markdown fences."
        )

        raw = self._call_gemini(prompt)
        if raw is None:
            return None

        try:
            data = json.loads(raw)
            action = data.get("action", "retry")
            if action not in ("retry", "skip", "abort", "escalate"):
                action = "retry"
            return RecoveryStrategy(
                action=action,
                strategy=str(data.get("strategy", "")),
                modified_description=str(data.get("modified_description", "")),
                requires_user=bool(data.get("requires_user", False)),
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # 5. Execution Summary
    # ------------------------------------------------------------------

    def generate_execution_summary(self, plan_data: Dict[str, Any]) -> Optional[str]:
        """Produce a rich natural-language execution summary."""
        if not self.available:
            return None

        # Build a compact representation of the plan for the prompt
        steps_summary = []
        for step in plan_data.get("steps", []):
            steps_summary.append({
                "id": step.get("step_id"),
                "desc": step.get("description", "")[:120],
                "agent": step.get("agent_role"),
                "status": step.get("status"),
                "result": (step.get("result") or "")[:200],
            })

        prompt = (
            "You are the reporting module of V.E.G.A.S.\n"
            "Generate a concise but comprehensive execution summary for the user.\n\n"
            f"Goal: {plan_data.get('goal', 'Unknown')}\n"
            f"Intent: {plan_data.get('intent', 'unknown')}\n"
            f"Status: {plan_data.get('status', 'unknown')}\n"
            f"Steps: {json.dumps(steps_summary, indent=2)}\n\n"
            "Format the summary in markdown with sections:\n"
            "1. **Goal** — what was requested\n"
            "2. **Execution Flow** — what each agent did (use bullet points)\n"
            "3. **Result** — overall outcome\n"
            "4. **Next Steps** — recommendations if applicable\n\n"
            "Be concise and direct. Use ✅ for success, ❌ for failure, ⏸️ for blocked."
        )

        return self._call_gemini(prompt)

    # ------------------------------------------------------------------
    # 6. Post-Execution Reflection
    # ------------------------------------------------------------------

    def reflect_on_plan(self, plan_data: Dict[str, Any]) -> Optional[ExecutionReflection]:
        """Extract lessons learned from a completed or failed execution plan."""
        if not self.available:
            return None

        history = plan_data.get("history", [])[-10:]
        prompt = (
            "You are the learning module of V.E.G.A.S.\n"
            "Analyze this completed execution plan and extract actionable lessons.\n\n"
            f"Goal: {plan_data.get('goal', '')}\n"
            f"Final status: {plan_data.get('status', '')}\n"
            f"Execution history: {json.dumps(history, indent=2)}\n\n"
            "Return a JSON object with keys:\n"
            "- lessons_learned: list of brief lesson strings\n"
            "- patterns_detected: list of patterns observed (e.g. 'testing always succeeds after developer')\n"
            "- recommendations: list of actionable improvements for future similar goals\n\n"
            "Return ONLY valid JSON, no markdown fences."
        )

        raw = self._call_gemini(prompt)
        if raw is None:
            return None

        try:
            data = json.loads(raw)
            return ExecutionReflection(
                lessons_learned=list(data.get("lessons_learned", [])),
                patterns_detected=list(data.get("patterns_detected", [])),
                recommendations=list(data.get("recommendations", [])),
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_gemini(self, prompt: str) -> Optional[str]:
        """Make a single Gemini API call.  Returns raw text or ``None``."""
        if not self._client:
            return None
        self._call_count += 1
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.2),
            )
            text = response.text or ""
            # Strip markdown fences if the model wraps them anyway
            text = text.strip()
            if text.startswith("```"):
                lines = text.splitlines()
                # Remove first and last fence lines
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines).strip()
            self._last_reasoning_trace = text[:1000]
            return text
        except Exception as exc:
            self._last_reasoning_trace = f"API Error: {exc}"
            return None

    def _cache_key(self, namespace: str, value: str) -> str:
        h = hashlib.sha256(value.strip().lower().encode()).hexdigest()[:16]
        return f"{namespace}:{h}"

    def _get_cache(self, key: str) -> Any:
        entry = self._cache.get(key)
        if entry is None or entry.expired:
            self._cache.pop(key, None)
            return None
        return entry.result

    def _set_cache(self, key: str, result: Any, ttl: float = 300.0) -> None:
        self._cache[key] = _CacheEntry(result=result, created_at=time.time(), ttl=ttl)
        # Evict old entries if cache grows too large
        if len(self._cache) > 100:
            oldest_key = min(self._cache, key=lambda k: self._cache[k].created_at)
            self._cache.pop(oldest_key, None)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
brain = VegasBrain()
