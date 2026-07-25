"""
Lightweight persistent memory layer for VEGAS AIOS.
Uses stdlib sqlite3 with a local database at ~/.vegas/vegas.db.
Provides task tracking, an append-only event log, key-value preferences,
conversation dialogue logs, project memory, coding preferences, tool execution history,
and long-term summaries.
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_DB_DIR = Path.home() / ".vegas"
_DB_PATH = _DB_DIR / "vegas.db"
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    """Returns the module-level connection, creating it on first access."""
    global _conn
    if _conn is None:
        _DB_DIR.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
    return _conn


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Creates all SQLite tables if they don't exist, maintaining full backward compatibility."""
    conn = _get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id          TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'pending',
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            result      TEXT
        );

        CREATE TABLE IF NOT EXISTS events (
            id        TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            kind      TEXT NOT NULL,
            summary   TEXT NOT NULL,
            detail    TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS preferences (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id         TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role       TEXT NOT NULL,
            message    TEXT NOT NULL,
            thoughts   TEXT,
            timestamp  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projects (
            project_path         TEXT PRIMARY KEY,
            name                 TEXT NOT NULL,
            tech_stack           TEXT NOT NULL DEFAULT '',
            architecture_summary TEXT NOT NULL DEFAULT '',
            updated_at           TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS coding_preferences (
            key        TEXT PRIMARY KEY,
            category   TEXT NOT NULL DEFAULT 'general',
            value      TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 1.0,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tool_history (
            id             TEXT PRIMARY KEY,
            tool_name      TEXT NOT NULL,
            agent_role     TEXT NOT NULL,
            status         TEXT NOT NULL,
            duration_ms    REAL NOT NULL DEFAULT 0.0,
            result_summary TEXT NOT NULL DEFAULT '',
            timestamp      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS long_term_summaries (
            id            TEXT PRIMARY KEY,
            scope         TEXT NOT NULL,
            summary_text  TEXT NOT NULL,
            entities_json TEXT NOT NULL DEFAULT '[]',
            created_at    TEXT NOT NULL
        );
        """
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def add_task(description: str) -> str:
    """Inserts a new task with status 'pending'. Returns the generated task id."""
    conn = _get_conn()
    task_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO tasks (id, description, status, created_at, updated_at) VALUES (?, ?, 'pending', ?, ?)",
        (task_id, description, now, now),
    )
    conn.commit()
    return task_id


def update_task_status(task_id: str, status: str, result: Optional[str] = None) -> None:
    """Updates the status (and optionally the result) of an existing task."""
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE tasks SET status = ?, result = COALESCE(?, result), updated_at = ? WHERE id = ?",
        (status, result, now, task_id),
    )
    conn.commit()


def list_tasks(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns tasks, optionally filtered by status."""
    conn = _get_conn()
    if status:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Events (append-only activity log)
# ---------------------------------------------------------------------------

def log_event(kind: str, summary: str, detail: str = "") -> None:
    """Appends an event row to the activity log."""
    conn = _get_conn()
    event_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO events (id, timestamp, kind, summary, detail) VALUES (?, ?, ?, ?, ?)",
        (event_id, now, kind, summary, detail),
    )
    conn.commit()


def get_recent_events(limit: int = 20) -> List[Dict[str, Any]]:
    """Returns the most recent events, newest first."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Preferences (key-value store)
# ---------------------------------------------------------------------------

def set_preference(key: str, value: str) -> None:
    """Upserts a key-value preference."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO preferences (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def get_preference(key: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieves a preference value by key, returning *default* if missing."""
    conn = _get_conn()
    row = conn.execute("SELECT value FROM preferences WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


# ---------------------------------------------------------------------------
# Conversation Dialogue Memory
# ---------------------------------------------------------------------------

def record_conversation_turn(session_id: str, role: str, message: str, thoughts: Optional[str] = None) -> str:
    """Stores a conversation dialogue turn in SQLite."""
    conn = _get_conn()
    turn_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO conversations (id, session_id, role, message, thoughts, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (turn_id, session_id, role, message, thoughts, now),
    )
    conn.commit()
    return turn_id


def get_session_turns(session_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieves dialogue turns for a session or recent turns across all sessions."""
    conn = _get_conn()
    if session_id:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM conversations ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


# ---------------------------------------------------------------------------
# Project Memory
# ---------------------------------------------------------------------------

def store_project_memory(project_path: str, name: str, tech_stack: str = "", architecture_summary: str = "") -> None:
    """Stores or updates repository structure and tech stack facts."""
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO projects (project_path, name, tech_stack, architecture_summary, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(project_path) DO UPDATE SET
            name = excluded.name,
            tech_stack = COALESCE(NULLIF(excluded.tech_stack, ''), projects.tech_stack),
            architecture_summary = COALESCE(NULLIF(excluded.architecture_summary, ''), projects.architecture_summary),
            updated_at = excluded.updated_at
        """,
        (project_path, name, tech_stack, architecture_summary, now),
    )
    conn.commit()


def get_project_memory(project_path: str) -> Optional[Dict[str, Any]]:
    """Retrieves project memory for a repository path."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM projects WHERE project_path = ?", (project_path,)).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Coding Preferences
# ---------------------------------------------------------------------------

def set_coding_preference(key: str, value: str, category: str = "general", confidence: float = 1.0) -> None:
    """Stores or updates user coding style, favorite tools, and formatting rules."""
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO coding_preferences (key, category, value, confidence, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            category = excluded.category,
            value = excluded.value,
            confidence = excluded.confidence,
            updated_at = excluded.updated_at
        """,
        (key, category, value, confidence, now),
    )
    conn.commit()


def get_coding_preferences(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves coding preferences, optionally filtered by category."""
    conn = _get_conn()
    if category:
        rows = conn.execute(
            "SELECT * FROM coding_preferences WHERE category = ? ORDER BY key ASC", (category,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM coding_preferences ORDER BY category, key ASC").fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Tool Execution History
# ---------------------------------------------------------------------------

def log_tool_execution(tool_name: str, agent_role: str, status: str, duration_ms: float = 0.0, result_summary: str = "") -> str:
    """Logs a tool execution to the performance tracking history."""
    conn = _get_conn()
    history_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO tool_history (id, tool_name, agent_role, status, duration_ms, result_summary, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (history_id, tool_name, agent_role, status, duration_ms, result_summary[:500], now),
    )
    conn.commit()
    return history_id


def get_tool_performance_stats(limit: int = 50) -> List[Dict[str, Any]]:
    """Returns recent tool execution history."""
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM tool_history ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Long-Term Summaries
# ---------------------------------------------------------------------------

def store_long_term_summary(scope: str, summary_text: str, entities: Optional[List[str]] = None) -> str:
    """Stores a long-term milestone summary."""
    conn = _get_conn()
    summary_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    entities_json = json.dumps(entities or [])
    conn.execute(
        "INSERT INTO long_term_summaries (id, scope, summary_text, entities_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (summary_id, scope, summary_text, entities_json, now),
    )
    conn.commit()
    return summary_id


def get_long_term_summaries(scope: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieves long-term milestone summaries."""
    conn = _get_conn()
    if scope:
        rows = conn.execute(
            "SELECT * FROM long_term_summaries WHERE scope = ? ORDER BY created_at DESC LIMIT ?",
            (scope, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM long_term_summaries ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# Auto-initialise the schema on import so callers never need to think about it.
init_db()
