# Tech Stack
Last Mapped: 2026-07-09

## Core Technologies
- **Languages:** Python >=3.11
- **Frameworks:** FastMCP (for tool server), LiveKit (real-time voice agent)
- **AI Models:** Google Gemini 2.5 Flash (LLM), Sarvam Saaras v3 (STT), OpenAI nova (TTS)

## Package & Dependency Management
- **Manager:** `uv`
- **Build Backend:** `hatchling`
- **Dependencies List:** `pyproject.toml`
- **Key Libraries:** `mcp[cli]`, `livekit-agents`, `livekit-plugins-google`, `livekit-plugins-openai`, `livekit-plugins-sarvam`

## Configuration
- **Environment:** Managed via `.env` file (template: `.env.example`).
- **Configuration loading:** Handled in `vegas/config.py`.
