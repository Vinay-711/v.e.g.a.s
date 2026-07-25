"""
Coding task dispatch tools for VEGAS AIOS.

Delegates scoped coding tasks to external AI coding agents
(Claude Code CLI or Antigravity SDK) running against a target repository.
"""

import os
import sys
import subprocess
from pathlib import Path

from vegas.memory import log_event


_DEFAULT_TIMEOUT = 1200  # 20 minutes — coding tasks can be long-running


def dispatch_coding_task(
    repo_path: str,
    task_description: str,
    cli: str = "antigravity",
) -> str:
    """
    Dispatches a coding task to an external AI coding agent and returns a
    natural-language summary of the outcome suitable for a voice agent.

    Supported CLI backends:
      - "antigravity" — runs the Google Antigravity SDK in headless mode via
        a one-shot Python invocation (google-antigravity is a Python library,
        not a standalone binary).
      - "claude_code" — runs Claude Code in non-interactive print mode
        (`claude -p "<prompt>"`).

    Every dispatch is logged to vegas.memory regardless of outcome.

    Args:
        repo_path: Absolute path to the target repository directory.
        task_description: Natural-language description of the coding task.
        cli: Which coding agent backend to use ("antigravity" or "claude_code").
    """
    # ------------------------------------------------------------------
    # 1. Validate repo_path
    # ------------------------------------------------------------------
    repo = Path(repo_path).expanduser().resolve()
    if not repo.exists():
        return f"Error: The path '{repo_path}' does not exist."
    if not repo.is_dir():
        return f"Error: '{repo_path}' is not a directory."

    cli = cli.strip().lower()

    # ------------------------------------------------------------------
    # 2. Build the command
    # ------------------------------------------------------------------
    if cli == "claude_code":
        # Confirmed via `claude --help`:
        #   -p, --print   Print response and exit (non-interactive).
        cmd = ["claude", "-p", task_description]

    elif cli == "antigravity":
        # google-antigravity is a Python SDK — no standalone CLI binary.
        # We invoke it headless via a one-shot python script that creates
        # an Agent, sends the prompt, and prints the final response.
        runner_script = (
            "import os\n"
            "import sys\n"
            "import asyncio\n"
            "from dotenv import load_dotenv\n"
            "load_dotenv()\n"
            "if 'GOOGLE_API_KEY' in os.environ and 'GEMINI_API_KEY' not in os.environ:\n"
            "    os.environ['GEMINI_API_KEY'] = os.environ['GOOGLE_API_KEY']\n"
            "from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig\n"
            "from google.antigravity.hooks import policy\n"
            "async def _run():\n"
            "    config = LocalAgentConfig(capabilities=CapabilitiesConfig(enable_subagents=True), policies=[policy.allow_all()])\n"
            "    async with Agent(config=config) as agent:\n"
            "        response = await agent.chat(sys.argv[1])\n"
            "        async for token in response:\n"
            "            print(token, end='', flush=True)\n"
            "        print()\n"
            "asyncio.run(_run())"
        )
        cmd = [sys.executable, "-c", runner_script, task_description]

    else:
        return f"Error: Unknown CLI backend '{cli}'. Supported values: 'antigravity', 'claude_code'."

    # ------------------------------------------------------------------
    # 3. Execute
    # ------------------------------------------------------------------
    try:
        result = subprocess.run(
            cmd,
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=_DEFAULT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        summary = f"Coding task timed out after {_DEFAULT_TIMEOUT}s — {task_description}"
        log_event("coding_task", summary=task_description, detail=f"TIMEOUT after {_DEFAULT_TIMEOUT}s")
        return summary
    except FileNotFoundError:
        msg = f"Error: The '{cmd[0]}' command was not found. Please install it first."
        log_event("coding_task", summary=task_description, detail=msg)
        return msg

    # ------------------------------------------------------------------
    # 4. Collect output & log
    # ------------------------------------------------------------------
    raw_output = (result.stdout or "") + (result.stderr or "")
    truncated = raw_output[-4000:] if len(raw_output) > 4000 else raw_output
    log_event("coding_task", summary=task_description, detail=truncated)

    # ------------------------------------------------------------------
    # 5. Build a concise natural-language summary
    # ------------------------------------------------------------------
    if result.returncode == 0:
        # Grab last meaningful lines for a spoken summary
        last_lines = [ln for ln in truncated.strip().splitlines() if ln.strip()][-5:]
        snippet = "\n".join(last_lines) if last_lines else "(no output)"
        return (
            f"Coding task completed successfully using {cli}.\n"
            f"Task: {task_description}\n"
            f"Key output:\n{snippet}"
        )
    else:
        err_lines = [ln for ln in truncated.strip().splitlines() if ln.strip()][-5:]
        snippet = "\n".join(err_lines) if err_lines else "(no error details)"
        return (
            f"Coding task failed (exit code {result.returncode}) using {cli}.\n"
            f"Task: {task_description}\n"
            f"Error summary:\n{snippet}"
        )


def register(mcp) -> None:
    """Registers coding tools with FastMCP."""
    mcp.tool()(dispatch_coding_task)
