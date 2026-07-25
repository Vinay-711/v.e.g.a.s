# Technical Concerns
Last Mapped: 2026-07-09

## Technical Debt & Fragility
- **Hardcoded Toggles:** Provider selection (e.g., `STT_PROVIDER = "sarvam"`) is hardcoded in `agent_vegas.py` rather than being completely extracted to configuration files or environment variables.
- **Dual Process Requirement:** Operating the system requires running two separate processes (MCP Server and Voice Agent). Process orchestration could be improved via a runner script or containerization (Docker).

## Security
- **Credential Proliferation:** Requires a substantial number of high-privileged API keys (LiveKit, Google, OpenAI, Sarvam). Leaks could be costly.
- **Missing automated testing:** Lack of automated tests introduces fragility when modifying the voice pipeline or tool schemas.
