"""
SQLite database client tools for VEGAS AIOS.

Allows executing SQL queries against SQLite databases located in the sandbox root.
Gated by @requires_confirmation for statements modifying the database (INSERT, UPDATE, DELETE, CREATE, DROP, ALTER).
"""

import sqlite3
from vegas.tools.files import _verify_sandbox_path
from vegas.safety import requires_confirmation
from vegas.memory import log_event

def _is_mutation_query(sql: str) -> bool:
    """Returns True if the SQL query contains write/mutation statements."""
    s = sql.strip().upper()
    mutations = ["INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "REPLACE"]
    return any(s.startswith(m) for m in mutations)

@requires_confirmation
def _confirmed_execute_sql(db_path: str, sql: str) -> str:
    """Confirmation-gated SQL execution for mutations."""
    return _execute_sqlite(db_path, sql)

def _execute_sqlite(db_path: str, sql: str) -> str:
    """Internal query executor."""
    try:
        resolved_db = _verify_sandbox_path(db_path)
    except PermissionError as pe:
        return str(pe)
        
    conn = None
    try:
        conn = sqlite3.connect(str(resolved_db), timeout=10.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.execute(sql)
        
        if _is_mutation_query(sql):
            conn.commit()
            rows_affected = cursor.rowcount
            return f"Query executed successfully. Rows affected: {rows_affected}."
        else:
            rows = cursor.fetchall()
            if not rows:
                return "Query returned no rows."
            # Format rows nicely
            headers = rows[0].keys()
            header_str = " | ".join(headers)
            separator = "-" * len(header_str)
            row_lines = []
            for row in rows:
                row_lines.append(" | ".join(str(row[h]) for h in headers))
            return f"{header_str}\n{separator}\n" + "\n".join(row_lines)
    except sqlite3.OperationalError as oe:
        return f"Database query operational error (locked or busy): {oe}"
    except Exception as e:
        return f"Database query failed: {e}"
    finally:
        if conn:
            conn.close()

def query_sqlite(db_path: str, sql: str) -> str:
    """
    Executes a SQL query against a SQLite database in the sandbox.
    Automatically intercepts and requires confirmation if executing mutating statements
    like INSERT, UPDATE, DELETE, CREATE, DROP, or ALTER.

    Args:
        db_path: Path to the SQLite .db file relative to the sandbox root.
        sql: The SQL statement to run.
    """
    log_event("db_client", f"Query sqlite db '{db_path}'", sql)
    if _is_mutation_query(sql):
        # Route through the confirmation-gated wrapper
        return _confirmed_execute_sql(db_path, sql)
        
    # Standard read-only path (no confirmation)
    return _execute_sqlite(db_path, sql)

def register(mcp) -> None:
    """Registers database tools with FastMCP."""
    mcp.tool()(query_sqlite)
