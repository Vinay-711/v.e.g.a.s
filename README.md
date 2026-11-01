# V.E.G.A.S. — Tony Stark Demo
### *Versatile Executive Guardian & Assistant System*

V.E.G.A.S. is an advanced personal AI operating system inspired by Tony Stark's J.A.R.V.I.S. and F.R.I.D.A.Y. assistant dashboards. It replaces outdated WebRTC voice pipes with a premium, highly responsive React/Vite web interface that hooks into a local FastAPI backend API, executing real-world developer commands, sandboxed file modifications, Git commits, Google Calendar events, and Playwright browser scraping.

---

## Architecture Diagram

```
+--------------------+        +--------------------+        +--------------------+
|   Vite/React UI    | <----> |  FastAPI Backend   | <----> |   Gemini Model     |
|   (Port 5173 / dev)| (CORS) |    (Port 8001)     |  (SDK) | (Gemini 2.5 Flash) |
+--------------------+        +--------------------+        +--------------------+
        ^                              |
        |                              v
+--------------------+        +--------------------+        +--------------------+
|   macOS Daemon     | -----> |   Planner Brain    | -----> | Specialist Agents  |
| Wake/Voice/Status  |        | Intent/Subtasks    |        | Git/Dev/Test/etc.  |
+--------------------+        +--------------------+        +--------------------+
                                       |
                                       v
                              +---------------------+
                              |   Tool Engine       |
                              | (Memory & Safety)   |
                              +---------------------+
                              | * Web Research      |
                              | * System Info & CMD |
                              | * Sandboxed Files   |
                              | * Git Operations    |
                              | * Code Delegation   |
                              | * Google Calendar   |
                              | * Gmail Drafts      |
                              | * Playwright Browser|
                              | * Autonomous Agents |
                              +---------------------+
```

---

## Project Components

| Component | Console Command | Description |
| :--- | :--- | :--- |
| **MCP Server** | `uv run vegas` | FastMCP server exposing core developer tools, resources, and custom modules over SSE (port `8000`). |
| **FastAPI Backend** | `uv run vegas_api` | Backend API bridging the React/Vite interface and the Gemini 2.5 Flash chat session (port `8001`). |
| **VEGAS Daemon** | `uv run vegas_daemon run` | Low-overhead local supervisor for FastAPI/FastMCP, wake-word monitoring, status WebSocket, and graceful shutdown. |
| **Vite Frontend** | `npm run dev` (in `/web`) | Premium React interface rendering live system status gauges, a sandboxed file viewer, and interactive chat console. |

---

## Project Structure

```
vegas-assistant/
├── server.py              # FastMCP Server Entry point
├── api.py                 # FastAPI Web UI Backend API entry point
├── pyproject.toml         # Dependency manager (uv)
├── .env.example           # Template for environment settings
├── .gitignore             # Standard gitignores
├── .python-version        # Target Python version (>=3.11)
├── README.md              # Documentation
├── tests/                 # Full unit test suites (memory, safety, daily workflows, browser/files)
├── vegas/
│   ├── __init__.py        # Package initialization
│   ├── config.py          # Config loader and validator
│   ├── memory.py          # SQLite persistence layer
│   ├── safety.py          # Requires confirmation decorator and queue
│   ├── autonomous.py      # Background autonomous agent CLI entrypoint
│   ├── core/
│   │   ├── planner.py     # Intent, subtask graph, agent routing, recovery, summaries
│   │   ├── executor.py    # Delegating executor that calls specialist agents
│   │   ├── kernel.py      # Shared planner/memory/security coordinator
│   │   └── collaboration.py # Specialized agent profiles
│   ├── daemon/            # Always-on supervisor, wake-word, status, LaunchAgent
│   ├── voice/             # Wake-triggered STT, planner client, TTS session manager
│   └── tools/
│       ├── __init__.py    # Registry for all tools
│       ├── web.py         # Web search and situation report tools
│       ├── system.py      # System usage and timezone tools
│       ├── utils.py       # JSON formatting and text tools
│       ├── developer.py   # Shell commands and file editing (gated)
│       ├── files.py       # Sandboxed read/write/delete (gated)
│       ├── git_ops.py     # Git status/diff/commits (gated)
│       ├── coding.py      # Subprocess external coding agent delegation
│       ├── workflow.py    # Google Calendar & Gmail integration
│       └── autonomous.py  # Background delegation tool
└── web/                   # Vite / React Web App
    ├── package.json       # React dependencies and scripts
    ├── index.html         # Application base template
    └── src/
        ├── main.tsx       # App initialization
        ├── App.tsx        # Dashboard layout, state, HUD gauges
        └── index.css      # Custom HSL design tokens, Glassmorphism, animations
```

---

## Quick Start

### Prerequisites
1.  **Python >= 3.11**
2.  **uv** package manager installed.
3.  **NodeJS >= 18** (for the frontend React dev server).

### Installation
Clone the repository and sync dependencies:
```bash
uv sync
```

Install React/Vite dev dependencies:
```bash
cd web
npm install
cd ..
```

### Configuration
1. Copy the example configuration file:
   ```bash
   cp .env.example .env
   ```
2. Populate the `.env` file with your credentials, specifically:
   *   `GOOGLE_API_KEY`: API key for Gemini (from Google AI Studio).
   *   `VEGAS_SANDBOX_ROOT`: Set this to the repository path (e.g. `/Users/.../vegas-assistant`) to allow sandboxed file operations.

### Running V.E.G.A.S.

To run the assistant, you will need three terminal windows:

1.  **Terminal 1: Start the FastMCP Server**
    ```bash
    uv run vegas
    ```
    This launches the FastMCP server on `http://127.0.0.1:8000/sse`.

2.  **Terminal 2: Start the FastAPI Backend API**
    ```bash
    uv run vegas_api
    ```
    This launches the backend API on `http://127.0.0.1:8001`.

3.  **Terminal 3: Start the Vite Dev Server**
    ```bash
    cd web
    npm run dev
    ```
    Open `http://localhost:5173` in your browser to load the V.E.G.A.S. OS dashboard!

### Always-on macOS daemon

The daemon is a user-scoped macOS LaunchAgent, rather than a root
LaunchDaemon, so it can use the signed-in user's microphone and desktop
permissions. It starts at login, restarts after crashes, and never terminates
FastAPI or FastMCP processes it did not create.

1. Configure a custom Porcupine `.ppn` wake-word model and its access key in
   `.env`. The model should represent the original VEGAS wake word.
2. Verify it in the foreground first:

   ```bash
   uv run vegas_daemon run --project-root "$(pwd)"
   ```

3. Install and start it at login:

   ```bash
   uv run vegas_daemon install --project-root "$(pwd)"
   ```

4. Inspect or control it later:

   ```bash
   uv run vegas_daemon status --project-root "$(pwd)"
   uv run vegas_daemon stop --project-root "$(pwd)"
   uv run vegas_daemon start --project-root "$(pwd)"
   uv run vegas_daemon uninstall --project-root "$(pwd)"
   ```

The daemon writes its own and child-service logs to `~/.vegas/logs/` and
`~/Library/Logs/VEGAS/`. The dashboard receives a live status stream at
`/api/daemon/status/ws`; existing `/api/system-status` polling also includes a
`daemon` object for backward compatibility.

If `VEGAS_WAKE_WORD_ENABLED=true`, the daemon uses Picovoice Porcupine plus
the system PortAudio device. Grant macOS microphone permission to the Python
environment running the LaunchAgent. If the wake-word model, access key, or
microphone is unavailable, backend services stay online and the dashboard
reports the daemon as degraded with the exact reason.

If PortAudio is not already available on the Mac, install it before the first
voice-enabled run:

```bash
brew install portaudio
```

### Voice interface

Voice is an additional interface to the existing text chat; it does not
replace the browser terminal or `/api/chat`. The local daemon listens for the
exact phrase **“Hey Vegas”** using a custom Picovoice Porcupine `.ppn` model,
captures the request, transcribes it locally with faster-whisper, sends the transcript
through the existing planner and tool-enabled FastAPI chat flow, and starts
speaking sentence-sized response chunks as they stream back.

1. Create or obtain a Porcupine custom keyword model for the exact phrase
   **Hey Vegas**, then set `VEGAS_WAKE_WORD_KEYWORD_PATH` and
   `VEGAS_PORCUPINE_ACCESS_KEY`.
2. Set `VEGAS_WHISPER_MODEL` to a local faster-whisper/CTranslate2 model
   directory. The value may also be a model name such as `base.en`; it is
   downloaded once and cached locally. The model stays on the Mac during use;
   microphone audio is not sent to a speech-to-text cloud service.
3. Grant microphone permission to the same Python/terminal application that
   runs `vegas_daemon` and use a macOS `say` voice such as `Samantha`.

After a response, VEGAS keeps the same conversation open for 12 seconds by
default (`VEGAS_VOICE_CONTINUATION_SECONDS`). Say **“Hey Vegas”** again while
it is thinking or speaking to interrupt the response immediately and begin a
new request. Voice state, partial transcript, final transcript, and response
status are included in the daemon dashboard stream and at
`GET /api/voice/status`.

### Planner brain

The Planner is the central coordination layer for V.E.G.A.S. goals. It does
not execute low-level tools directly. It classifies intent, creates a subtask
graph, assigns each subtask to a specialist agent, records execution history,
prepares recovery hints after failures, and produces a final execution
summary.

For example, `Update my project` becomes:

```text
Git Agent -> Developer Agent -> Testing Agent -> Memory Agent -> Reporting Agent
```

Planner controls are exposed through both FastAPI and FastMCP:

| Surface | Purpose |
| :--- | :--- |
| `POST /api/planner/plan` | Create a plan without executing it. |
| `GET /api/planner/status` | Inspect the active plan and registered agents. |
| `POST /api/planner/execute-next` | Delegate the next planned step to its selected specialist agent. |
| `POST /api/planner/execute` | Execute a bounded coordination pass until completion, failure, or confirmation. |
| `GET /api/planner/summary` | Return the current execution summary. |
| MCP `plan_goal` / `execute_next_planner_step` / `execute_active_plan` | Same controls for MCP clients and model-driven workflows. |

The dashboard includes Planner state in `/api/system-status`, and the shared
status badge reports daemon, wake-word, voice, and plan state.

---

## Safety Confirmation Gate

V.E.G.A.S. enforces a strict safety boundary. State-changing operations (such as running shell commands, editing files, staging Git commits, or drafting emails) are intercepted and parked.

*   When a gated tool is triggered, V.E.G.A.S. parks the task and returns:
    `⚠️ VEGAS: This action requires your confirmation — edit_file(path='...')`
*   Verify the details in the chat and click **Confirm** or enter `"confirm task <task_id>"` in the terminal console to execute, or `"cancel task <task_id>"` to discard.

---

## Environment Variables

| Variable | Required | Description |
| :--- | :--- | :--- |
| `GOOGLE_API_KEY` | **Yes** | API key for Gemini models (from Google AI Studio). |
| `VEGAS_SANDBOX_ROOT` | **Yes** | Absolute directory path where V.E.G.A.S. is allowed to perform sandboxed file operations. |
| `GOOGLE_OAUTH_CREDENTIALS_PATH` | No | Local filesystem path to your Google Client Secret JSON credentials for Calendar/Gmail. |
| `SUPABASE_URL` | No | Supabase project URL. |
| `SUPABASE_API_KEY` | No | Supabase API/Service key. |
| `VEGAS_DAEMON_TOKEN` | Recommended | Optional shared secret for the localhost daemon-status WebSocket. |
| `VEGAS_WAKE_WORD_ENABLED` | No | Enables local wake-word monitoring; defaults to `true`. |
| `VEGAS_PORCUPINE_ACCESS_KEY` | Required for voice | Picovoice access key for the wake-word engine. |
| `VEGAS_WAKE_WORD_KEYWORD_PATH` | Required for voice | Path to the custom Porcupine `.ppn` model trained for **Hey Vegas**. |
| `VEGAS_WAKE_WORD_SENSITIVITY` | No | Porcupine sensitivity from `0.0` to `1.0`; defaults to `0.55`. |
| `VEGAS_WHISPER_MODEL` | Required for voice | Local faster-whisper model directory or a model name cached after first download. |
| `VEGAS_VOICE_SPEECH_THRESHOLD` | No | PCM energy threshold for local voice activity detection; defaults to `350`. |
| `VEGAS_VOICE_CONTINUATION_SECONDS` | No | Follow-up listening window after a spoken reply; defaults to `12`. |
| `VEGAS_VOICE_TTS_VOICE` | No | macOS `say` voice used for spoken responses; defaults to `Samantha`. |

---

## Running Unit Tests
A comprehensive test suite verifies state persistence, the safety confirmation loop, sandboxed paths, calendar integrations, and Playwright form-submission gates:

```bash
PYTHONPATH=. uv run --with pytest --with pytest-asyncio pytest
```

---

## License

This project is licensed under the terms of the [MIT License](LICENSE).

## Development and permission boundaries

- [Web client guide](web/README.md): dashboard setup, scripts and API dependency.
- [pyproject.toml](pyproject.toml): Python version, dependencies and executable entry points.
- [tests](tests): planner, memory, device, workflow and voice-related test sources.
- [vegas/security/guardrails.py](vegas/security/guardrails.py): guardrail implementation to review before enabling tools.

Start in the foreground with a dedicated sandbox and synthetic data. Background daemon installation, microphone access, OAuth connections, file modifications and outbound actions are separate capabilities, not prerequisites for merely reading the source. Keep credentials and personal memory files local; test denied actions as well as successful ones before expanding access.
