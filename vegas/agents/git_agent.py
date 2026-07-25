"""
Git Agent for VEGAS AIOS.

Owns repository status checking, diff inspection, branching, and commits.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from vegas.agents.base import AgentResult, BaseAgent
from vegas.tools.git_ops import git_commit, git_create_branch, git_diff, git_status


class GitAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Git Agent",
            role="git",
            description="Inspects git status, diffs, commits changes, and manages repository branches.",
        )
        self.register_tool("git_status", git_status)
        self.register_tool("git_diff", git_diff)
        self.register_tool("git_commit", git_commit)
        self.register_tool("git_create_branch", git_create_branch)

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        start_time = time.time()
        ctx = context or {}
        repo_path = ctx.get("repo_path", ".")
        lowered = task.lower()

        try:
            if "commit" in lowered:
                msg = ctx.get("commit_message", task)
                output = self.tools["git_commit"](repo_path=repo_path, message=msg)
            elif "branch" in lowered:
                branch = ctx.get("branch_name", "feature/update")
                output = self.tools["git_create_branch"](repo_path=repo_path, branch_name=branch)
            elif "diff" in lowered:
                output = self.tools["git_diff"](repo_path=repo_path)
            else:
                status_out = self.tools["git_status"](repo_path=repo_path)
                diff_out = self.tools["git_diff"](repo_path=repo_path)
                output = f"[git status]\n{status_out}\n\n[git diff]\n{diff_out[:3000]}"

            duration = (time.time() - start_time) * 1000
            status = "failed" if "error" in output.lower() or "fatal" in output.lower() else "success"
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
                result=f"GitAgent execution error: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
            )
