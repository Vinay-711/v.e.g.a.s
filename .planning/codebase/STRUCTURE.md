# Codebase Structure
Last Mapped: 2026-07-09

## Root Directory
- `pyproject.toml`, `uv.lock`: Dependency definitions.
- `server.py`: FastMCP entrypoint script.
- `agent_vegas.py`: LiveKit Voice Agent entrypoint script.
- `README.md`: System documentation and architecture diagrams.

## Key Directories
- `vegas/`: Core application package.
  - `config.py`: Environment configuration loading and validation.
  - `tools/`: MCP tools registry (e.g., `web.py`, `system.py`, `utils.py`).
  - `prompts/`: MCP prompt templates.
  - `resources/`: MCP resource endpoints.
  - `core/`, `memory.py`, `safety.py`: Internal business logic and state.
- `scripts/`: Standalone utilities (e.g., `daily_briefing_cron.py`).
