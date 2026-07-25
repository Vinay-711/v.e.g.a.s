"""
Email Agent for VEGAS AIOS.

Owns Gmail integration, email drafting, composition, and message handling.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from vegas.agents.base import AgentResult, BaseAgent
from vegas.tools.workflow import draft_email


class EmailAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Email Agent",
            role="email",
            description="Drafts, composes, and prepares emails via Gmail integration.",
        )
        self.register_tool("draft_email", draft_email)

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        start_time = time.time()
        ctx = context or {}

        to_addr = ctx.get("to", "recipient@example.com")
        subject = ctx.get("subject", "Update from V.E.G.A.S.")
        body = ctx.get("body", task)

        try:
            output = self.tools["draft_email"](to=to_addr, subject=subject, body=body)

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
                result=f"EmailAgent execution error: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
            )
