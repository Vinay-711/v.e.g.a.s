# Architecture
Last Mapped: 2026-07-09

## System Design
The system uses a decoupled architecture with two primary components running concurrently:
1. **MCP Server (FastMCP):** Provides external tools (web search, news, system telemetry) to the LLM via standard MCP protocol over SSE.
2. **Voice Agent (LiveKit):** Manages the real-time WebRTC audio pipeline.

## Data Flow
- **Microphone -> STT (Sarvam):** Captures user voice and converts to text.
- **STT -> LLM (Gemini):** Processes text. If tools are needed, makes JSON-RPC calls over SSE to the local MCP Server.
- **LLM -> TTS (OpenAI):** Generates conversational text responses which are synthesized to audio.
- **TTS -> Speaker (LiveKit Room):** Plays audio back to the user.

## Entry Points
- `uv run vegas`: Starts the MCP server via `server:main`.
- `uv run vegas_voice`: Starts the voice agent via `agent_vegas:dev`.
