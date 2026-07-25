"""
Calendar Agent for VEGAS AIOS.

Owns Google Calendar integration, event listing, schedule checks, and morning briefings.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from vegas.agents.base import AgentResult, BaseAgent
from vegas.tools.workflow import list_todays_events, morning_briefing


class CalendarAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Calendar Agent",
            role="calendar",
            description="Inspects Google Calendar events, checks user schedule, and composes daily morning briefings.",
        )
        self.register_tool("list_todays_events", list_todays_events)
        self.register_tool("morning_briefing", morning_briefing)

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        start_time = time.time()
        lowered = task.lower()

        try:
            if "briefing" in lowered or "digest" in lowered:
                output = self.tools["morning_briefing"]()
            else:
                output = self.tools["list_todays_events"]()

            duration = (time.time() - start_time) * 1000
            status = "failed" if "error" in output.lower() else "success"
            return AgentResult(
                agent_role=self.role,
                status=status,
                result=output,
                duration_ms=duration,
            )
        except Exception as e:
            return AgentResult(
                agent_role=self.role,
                status="failed",
                result=f"CalendarAgent execution error: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
            )
