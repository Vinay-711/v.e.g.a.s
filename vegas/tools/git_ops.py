"""
Git integration tools for VEGAS AIOS.

Allows status checking, diffs, and confirmation-gated commits and branch creation.
All actions log their calls to the VEGAS memory log.
"""

import subprocess
from pathlib import Path
from vegas.safety import requires_confirmation
from vegas.memory import log_event

def _run_git(cmd: list[str], repo_path: str) -> tuple[int, str]:
    """Helper to execute a git command in the target repository directory."""
    path = Path(repo_path).expanduser().resolve()
    if not path.exists():
        return 1, f"Error: Path '{repo_path}' does not exist."
    if not path.is_dir():
        return 1, f"Error: Path '{repo_path}' is not a directory."
        
    try:
        res = subprocess.run(
            ["git"] + cmd,
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=30
        )
        output = (res.stdout or "") + (res.stderr or "")
        return res.returncode, output
    except Exception as e:
        return 1, f"Git error: {str(e)}"

def git_status(repo_path: str = ".") -> str:
    """
    Checks the current git status of a repository (unstaged, staged, untracked files).

    Args:
        repo_path: Path to the target git repository (defaults to current directory).
    """
    log_event("git_ops", f"git status in {repo_path}")
    code, output = _run_git(["status"], repo_path)
    return output

def git_diff(repo_path: str = ".") -> str:
    """
    Retrieves unstaged diff changes in the repository.

    Args:
        repo_path: Path to the target git repository.
    """
    log_event("git_ops", f"git diff in {repo_path}")
    code, output = _run_git(["diff"], repo_path)
    if not output.strip():
        return "No unstaged changes."
    return output[:4000]

@requires_confirmation
def git_commit(repo_path: str, message: str, stage_all: bool = True) -> str:
    """
    Stages files and commits changes to the repository. Gated by @requires_confirmation.

    Args:
        repo_path: Path to the target git repository.
        message: Commit message.
        stage_all: If True, stages all changes (git add -A) before committing.
    """
    log_event("git_ops", f"git commit in {repo_path}", f"Message: {message}, Stage all: {stage_all}")
    if stage_all:
        code, add_out = _run_git(["add", "-A"], repo_path)
        if code != 0:
            return f"Failed to stage changes:\n{add_out}"
            
    code, commit_out = _run_git(["commit", "-m", message], repo_path)
    if code != 0:
        return f"Failed to commit changes:\n{commit_out}"
    return f"Successfully committed changes:\n{commit_out}"

@requires_confirmation
def git_create_branch(repo_path: str, branch_name: str) -> str:
    """
    Creates and switches to a new git branch. Gated by @requires_confirmation.

    Args:
        repo_path: Path to the target git repository.
        branch_name: Name of the new branch to create.
    """
    log_event("git_ops", f"git checkout -b {branch_name} in {repo_path}")
    code, output = _run_git(["checkout", "-b", branch_name], repo_path)
    if code != 0:
        return f"Failed to create branch '{branch_name}':\n{output}"
    return f"Successfully created and checked out branch '{branch_name}'.\n{output}"

def register(mcp) -> None:
    """Registers git tools with FastMCP."""
    mcp.tool()(git_status)
    mcp.tool()(git_diff)
    mcp.tool()(git_commit)
    mcp.tool()(git_create_branch)
