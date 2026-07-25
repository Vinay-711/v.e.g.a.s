"""
Developer Agent for VEGAS AIOS.

Owns code implementation, debugging, file system operations, and external coding CLI dispatches.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from vegas.agents.base import AgentResult, BaseAgent
from vegas.tools.coding import dispatch_coding_task
from vegas.tools.developer import edit_file, list_directory, search_directory, view_file, write_file


class DeveloperAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Developer Agent",
            role="developer",
            description="Writes, edits, reads, and debugs code across repository files and dispatches external coding agents.",
        )
        self.register_tool("dispatch_coding_task", dispatch_coding_task)
        self.register_tool("view_file", view_file)
        self.register_tool("write_file", write_file)
        self.register_tool("edit_file", edit_file)
        self.register_tool("search_directory", search_directory)
        self.register_tool("list_directory", list_directory)

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        start_time = time.time()
        ctx = context or {}
        repo_path = ctx.get("repo_path", ".")
        cli = ctx.get("coding_backend", "antigravity")

        try:
            # Delegate task via coding dispatch by default for complex implementation
            output = self.tools["dispatch_coding_task"](
                repo_path=repo_path,
                task_description=task,
                cli=cli,
            )

            duration = (time.time() - start_time) * 1000
            status = "failed" if self._looks_failed(output) else "success"
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
                result=f"DeveloperAgent execution error: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
            )

    def _looks_failed(self, text: str) -> bool:
        lowered = text.lower()
        return any(
            marker in lowered
            for marker in ("failed", "error:", "traceback", "timed out", "not configured", "lacks api key")
        )
