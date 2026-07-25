"""
MCP tool wrappers for the VEGAS persistent memory layer.
Exposes remember / recall / whats_pending / confirm_task / cancel_task / search_semantic_memory
and the demo send_email_stub as LLM-callable tools.
"""

import json
from typing import Optional

from vegas.core.memory import memory
from vegas.memory import (
    get_coding_preferences,
    get_preference,
    get_project_memory,
    get_recent_events,
    list_tasks,
    set_preference,
    update_task_status,
)
from vegas.safety import pop_pending_action, requires_confirmation


def remember(fact: str) -> str:
    """
    Stores a fact or preference for later recall.
    The fact is persisted as a key-value pair in the VEGAS memory database.

    Args:
        fact: A short statement to remember (e.g. "User prefers dark mode").
    """
    key = fact.strip()[:120]
    set_preference(key, fact)
    memory.store_fact(key, fact)
    return f"Remembered: {fact}"


def recall(query: str) -> str:
    """
    Searches stored preferences, conversations, and recent events for matches to the query.

    Args:
        query: A search string (case-insensitive substring match).
    """
    # Use upgraded semantic retrieval
    matches = memory.semantic_search(query, limit=5)
    if matches:
        lines = [f"[{m['store']}] {m['content']}" for m in matches]
        return "\n".join(lines)

    q = query.lower()
    hits: list[str] = []

    from vegas.memory import _get_conn

    conn = _get_conn()
    rows = conn.execute("SELECT key, value FROM preferences").fetchall()
    for row in rows:
        if q in row["key"].lower() or q in row["value"].lower():
            hits.append(f"[pref] {row['value']}")

    events = get_recent_events(limit=50)
    for ev in events:
        if q in ev["summary"].lower() or q in ev.get("detail", "").lower():
            hits.append(f"[event {ev['kind']}] {ev['summary']}")

    if not hits:
        return f"No matches found for '{query}'."
    return "\n".join(hits)


def search_semantic_memory(query: str, category: Optional[str] = None) -> str:
    """
    Performs semantic retrieval across conversations, project facts, coding preferences,
    tool execution logs, and long-term milestone summaries.

    Args:
        query: Search prompt or question.
        category: Optional filter ('conversations', 'semantic_facts', 'coding_preferences', 'long_term_summaries').
    """
    results = memory.semantic_search(query, limit=5, category=category)
    if not results:
        return f"No semantic memory matches found for '{query}'."
    return json.dumps(results, indent=2)


def get_coding_preferences_tool() -> str:
    """
    Retrieves stored user coding preferences, style guidelines, and framework defaults.
    """
    prefs = memory.get_coding_prefs()
    if not prefs:
        return "No specific coding preferences recorded yet."
    return json.dumps(prefs, indent=2)


def get_project_memory_tool(project_path: str = ".") -> str:
    """
    Retrieves stored project memory (tech stack, architecture summary, rules) for a repository.

    Args:
        project_path: Path to the target project directory.
    """
    info = memory.get_project_info(project_path)
    if not info:
        return f"No stored project memory found for path '{project_path}'."
    return json.dumps(info, indent=2)


def whats_pending() -> str:
    """
    Returns all tasks that are currently in 'pending' status,
    formatted as a human-readable numbered list.
    """
    tasks = list_tasks(status="pending")
    if not tasks:
        return "No pending tasks."
    lines = [f"{i}. {t['description']}  (id: {t['id']})" for i, t in enumerate(tasks, 1)]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Confirmation / cancellation tools
# ---------------------------------------------------------------------------

def confirm_task(task_id: str) -> str:
    """
    Confirms and executes a previously parked action that was awaiting approval.

    Args:
        task_id: The id returned by the confirmation prompt.
    """
    entry = pop_pending_action(task_id)
    if entry is None:
        return f"No pending action found for task '{task_id}'. It may have already been confirmed or cancelled."

    fn, args, kwargs = entry
    try:
        result = fn(*args, **kwargs)
    except Exception as exc:
        update_task_status(task_id, "failed", result=str(exc))
        return f"Task {task_id} failed during execution: {exc}"

    result_str = str(result)
    update_task_status(task_id, "completed", result=result_str)
    return f"✅ Task {task_id} confirmed and executed.\nResult: {result_str}"


def cancel_task(task_id: str) -> str:
    """
    Cancels a previously parked action, discarding it without execution.

    Args:
        task_id: The id returned by the confirmation prompt.
    """
    pop_pending_action(task_id)
    update_task_status(task_id, "cancelled")
    return f"🚫 Task {task_id} has been cancelled."


@requires_confirmation
def send_email_stub(to: str, subject: str, body: str) -> str:
    """
    Placeholder email tool. Decorated with @requires_confirmation.
    """
    return f"Would have sent email → to={to}, subject='{subject}', body='{body}'"


def register(mcp) -> None:
    """Registers memory and safety MCP tools."""
    mcp.tool()(remember)
    mcp.tool()(recall)
    mcp.tool()(search_semantic_memory)
    mcp.tool()(get_coding_preferences_tool)
    mcp.tool()(get_project_memory_tool)
    mcp.tool()(whats_pending)
    mcp.tool()(confirm_task)
    mcp.tool()(cancel_task)
    mcp.tool()(send_email_stub)
