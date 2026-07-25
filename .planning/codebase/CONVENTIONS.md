# Coding Conventions
Last Mapped: 2026-07-09

## Code Style & Patterns
- **Tool Registration:** MCP tools are defined in modular files within `vegas/tools/` and use the `@mcp.tool()` decorator. They must be explicitly registered via an initialization function (e.g., `register_all_tools(mcp)`).
- **Configuration:** Environment variables are strictly preferred for credentials. Runtime swaps for AI providers (STT, LLM, TTS) are managed via constants defined at the top of `agent_vegas.py`.

## Error Handling
- The architecture handles failures resiliently by relying on LiveKit's agent abstractions and FastMCP's robust SSE protocol.
