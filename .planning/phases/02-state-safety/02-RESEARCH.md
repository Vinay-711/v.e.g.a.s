# Phase 2: State & Safety - Research

## Context and Findings

The requirements for Phase 2 are:
- SAFE-01: Agent persists context and state across sessions via SQLite memory
- SAFE-02: Implement `requires_confirmation` decorator for tools
- SAFE-03: Agent halts execution and waits for explicit user confirmation on gated tools

### Existing Implementations
Upon scouting the codebase, I discovered that these components have **already been implemented**:
1. **`vegas/memory.py`**: Contains a fully functional SQLite-backed persistent memory layer (tasks, events, preferences).
2. **`vegas/safety.py`**: Contains the `@requires_confirmation` decorator which parks tasks in the database and waits for confirmation.
3. **`vegas/tools/memory.py`**: Exposes the MCP tools `remember`, `recall`, `whats_pending`, `confirm_task`, `cancel_task`, and `send_email_stub` (decorated with `@requires_confirmation`).
4. **`vegas/tools/__init__.py`**: Successfully registers the memory tools.

### Gaps to Close
Since the foundation exists, Phase 2 planning should focus on:
1. **Validation & Testing**: Ensuring the existing SQLite memory and `requires_confirmation` decorator work end-to-end.
2. **Application**: Applying the `@requires_confirmation` decorator to other destructive tools like file deletion in `vegas/tools/files.py`.
3. **LLM Instructions Update**: Verifying that `server.py` and `agent_vegas.py` properly instruct the LLM to use the confirmation loop (this appears mostly done in `server.py`'s instructions, but we should verify).

## Validation Architecture
- We can write a unit/integration test to verify that calling a decorated function parks the task, and `confirm_task` executes it.
- We can also test the SQLite `memory.py` functions to ensure data persists.
