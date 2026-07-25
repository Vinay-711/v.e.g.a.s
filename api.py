"""
VEGAS Backend API — The bridge between the premium Web UI and the VEGAS tool engine.

Exposes:
  /api/chat          — Main Gemini-powered conversation with full tool access
  /api/system-status — Live system stats for the HUD sidebar
  /api/tools         — List of all available tools for the UI to render
  /api/memory        — Memory read/write endpoints
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
import os
import platform
import sys
import hmac
import json
import asyncio
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("vegas.api")

from vegas.daemon.status import DashboardStatusHub
from vegas.core.kernel import kernel

# --------------------------------------------------------------------------
# Import ALL tool modules
# --------------------------------------------------------------------------
from vegas.tools.web import search_web, fetch_url, get_world_news, open_world_monitor, open_map_location, open_in_browser
from vegas.tools.system import get_current_time, get_system_info
from vegas.tools.utils import format_json, word_count
from vegas.tools.developer import run_command, edit_file, search_directory
from vegas.tools.memory import remember, recall, whats_pending, confirm_task, cancel_task
from vegas.tools.coding import dispatch_coding_task
from vegas.tools.git_ops import git_status, git_diff, git_commit, git_create_branch
from vegas.tools.workflow import list_todays_events, draft_email, morning_briefing
from vegas.tools.autonomous import delegate_autonomous_task
from vegas.tools.aios import (
    execute_active_plan,
    execute_next_planner_step,
    get_execution_summary,
    get_planner_status,
    plan_goal,
    reflect_on_execution,
)
from vegas.tools.browser import browse_and_extract, fill_web_form
from vegas.tools.files import read_file as sandboxed_read, write_file as sandboxed_write, delete_file as sandboxed_delete, list_directory as sandboxed_list, _verify_sandbox_path
from vegas.tools.media import play_music, open_youtube_video, set_system_volume, play_pause_media, speak_text
from vegas.tools.device import list_connected_devices, execute_phone_command, send_phone_sms, make_phone_call, pair_wireless_device
from vegas.tools.macos import (
    focus_window,
    get_battery_status,
    get_bluetooth_status,
    get_wifi_status,
    launch_application,
    manage_clipboard,
    open_in_finder,
    open_system_settings,
    quit_application,
    send_system_notification,
    set_display_brightness,
    take_screenshot,
)
from vegas.mobile.companion import companion_hub
from vegas.tools.companion import (
    capture_companion_camera_frame,
    forward_phone_voice,
    get_companion_telemetry,
    make_companion_call,
    send_companion_sms,
    sync_phone_clipboard,
    sync_phone_shared_memory,
    transfer_phone_file,
)


app = FastAPI(title="VEGAS Backend API")

# The daemon runs in a separate, supervised process.  This in-process hub
# receives its reconnecting websocket heartbeat and exposes it to both the
# existing polling dashboard and new live dashboard clients.
daemon_status_hub = DashboardStatusHub()

allowed_origins = os.getenv(
    "VEGAS_CORS_ORIGINS",
    "http://127.0.0.1:8001,http://localhost:8001,http://127.0.0.1:5173,http://localhost:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Enforce desktop security headers and prevent stale JS caching."""
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Mount web UI static files
web_dir = Path(__file__).parent / "web"
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")


@app.get("/")
async def serve_index():
    """Serves the V.E.G.A.S. Mission Control Web Interface."""
    index_file = web_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return {"message": "VEGAS AIOS Mission Control API Running"}

# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str

class MemoryRequest(BaseModel):
    fact: str

class RecallRequest(BaseModel):
    query: str


class VoiceCommandRequest(BaseModel):
    """A final local STT transcript submitted by the VEGAS daemon."""

    message: str
    conversation_id: str


class PlannerGoalRequest(BaseModel):
    goal: str


class PlannerExecuteRequest(BaseModel):
    max_steps: int = 20

class ChatResponse(BaseModel):
    response: Optional[str] = None
    error: Optional[str] = None

class GenericResultResponse(BaseModel):
    result: str

class FileViewResponse(BaseModel):
    content: str

class ResetResponse(BaseModel):
    result: str


def _is_loopback_websocket(websocket: WebSocket) -> bool:
    """Daemon status is intentionally a local-only control-plane channel."""
    client = websocket.client
    return client is not None and client.host in {"127.0.0.1", "::1", "localhost"}


def _valid_daemon_token(websocket: WebSocket) -> bool:
    """Require a token when one is configured, without breaking local setups."""
    expected = os.environ.get("VEGAS_DAEMON_TOKEN")
    if not expected:
        return True
    supplied = websocket.headers.get("X-VEGAS-Daemon-Token", "")
    return hmac.compare_digest(supplied, expected)

# --------------------------------------------------------------------------
# Gemini Client Setup
# --------------------------------------------------------------------------
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().with_name(".env"))

api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("WARNING: GEMINI_API_KEY / GOOGLE_API_KEY not found in environment!")
else:
    print(f"INFO: Loaded API Key successfully (length: {len(api_key)})")

# System status, daemon health, and the dashboard remain available even when a
# model key is not configured yet. Chat reports a precise configuration error
# instead of preventing the background daemon from starting.
client = genai.Client(api_key=api_key) if api_key else None

# --------------------------------------------------------------------------
# Files Endpoints
# --------------------------------------------------------------------------
@app.get("/api/files/list")
async def list_files_endpoint(path: str = "."):
    try:
        resolved = _verify_sandbox_path(path)
        if not resolved.exists():
            raise HTTPException(status_code=404, detail=f"Directory '{path}' does not exist.")
        if not resolved.is_dir():
            raise HTTPException(status_code=400, detail=f"'{path}' is not a directory.")

        items = []
        for name in os.listdir(resolved):
            if name.startswith('.'):
                continue
            full_path = resolved / name
            items.append({
                "name": name,
                "path": str(full_path),
                "is_dir": full_path.is_dir()
            })
        items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        return {"files": items}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list directory: {e}")

@app.get("/api/files/view", response_model=FileViewResponse)
async def view_file_endpoint(path: str):
    try:
        resolved = _verify_sandbox_path(path)
        if not resolved.exists():
            raise HTTPException(status_code=404, detail=f"File '{path}' does not exist.")
        if not resolved.is_file():
            raise HTTPException(status_code=400, detail=f"'{path}' is not a file.")

        with open(resolved, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return FileViewResponse(content=content)
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")

SYSTEM_PROMPT = """
You are VEGAS, the Versatile Executive Guardian & Assistant System — the world's
most advanced Autonomous AI Operating System. You run locally on the user's host
machine. You are witty, concise, extremely competent, and stylistically inspired
by JARVIS from Iron Man.

Your capabilities:
- Web Research: search the web, fetch URLs, get world news, world monitor HUD, open map location, open in browser
- System Control: check time, get system info, run shell commands
- File Operations: list/view/write/edit/search files and directories
- Memory: persistently remember facts, recall stored information
- Code Delegation: dispatch coding tasks to Antigravity CLI or Claude Code
- Planner Brain: understand goals, decompose subtasks, route to specialist agents, coordinate delegated execution, recover from failures, and summarize outcomes
- Git Operations: check status, view diffs, commit changes, create branches
- Task Management: track pending tasks, confirm or cancel gated actions
- Mobile Ecosystem Control: control phone apps, open URLs/maps on phone, check phone battery, take phone screenshots, send SMS/calls, pair wireless devices

Cross-Device Ecosystem & Mobile Phone Control Rules:
1. You are connected to a Cross-Device Ecosystem bridge via ADB (USB & Wireless ADB).
2. When the user asks you to perform an action on their phone or mobile device (e.g. "do X on my phone", "open YouTube on my phone", "search location on phone maps", "check phone battery", "take phone screenshot", "send SMS", "call number"):
   - Use `execute_phone_command` with the appropriate action (e.g. action="open_app", target="youtube", action="open_map", target="ramanagara", action="battery_status", action="take_screenshot", action="open_url").
   - Use `list_connected_devices` to discover connected phones/tablets.
   - Use `pair_wireless_device` to connect wirelessly to a phone IP address over local Wi-Fi.
   - Use `send_phone_sms` / `make_phone_call` for SMS/calling.

Direct Navigation & Media Rules:
1. When the user asks to search a place on maps, show/open a location on maps, navigate somewhere, or locate a place on laptop (e.g. "search ramanagara on maps", "show me Eiffel Tower on maps"), ALWAYS call `open_map_location` immediately. Do NOT ask follow-up clarifying questions or give text-only answers.
2. When the user asks to play music, a song, or a video (e.g. "play khairiyat song"), ALWAYS call `play_music` or `open_youtube_video` immediately.
3. When the user asks to open a website or URL in their browser, call `open_in_browser`.

Planner Rules:
1. For complex goals, first call `plan_goal` so the Planner can classify intent, assign specialist agents, and produce a step graph.
2. The Planner never executes low-level tools directly. Use `execute_next_planner_step` or `execute_active_plan` only when the user asks V.E.G.A.S. to proceed with execution.
3. Use `get_execution_summary` after delegated execution or failure recovery.

Safety & Gating Rules:
1. File operations (reading, writing, deleting, listing) are restricted to the sandboxed workspace root (the repository folder). Any attempt to access paths outside this root will return a PermissionError.
2. State-changing operations are safety-gated and require explicit user confirmation. These include:
   - Creating/writing a file (write_file)
   - Deleting a file (delete_file)
   - Editing a file (edit_file)
   - Running terminal commands (run_command)
   - Git commits and branch creation (git_commit, git_create_branch)
   - Creating draft emails (draft_email)
   - Submitting web forms (fill_web_form with submit=True)
   - Drafting/sending SMS on phone (send_phone_sms) or calling (make_phone_call)
3. When you call a gated tool, the tool returns a confirmation warning containing a task_id (e.g. '⚠️  VEGAS: This action requires your confirmation...').
4. When this happens:
   - Explain the action clearly to the user.
   - Present the returned task_id.
   - Explicitly ask the user to confirm or cancel the task (e.g., "Confirm task <id>?").
   - Do NOT attempt to run the tool again. Wait for the user to say "confirm" or "cancel".

When you use a tool, report the results clearly and concisely.
Never refuse a reasonable request. Be proactive and helpful.
If a tool execution fails, explain the error and suggest alternatives.
Format responses with markdown for readability.
"""

AVAILABLE_TOOLS = [
    # Web & Research
    search_web, fetch_url, get_world_news, open_world_monitor, open_map_location, open_in_browser,
    # System
    get_current_time, get_system_info,
    # Developer & Files
    run_command, edit_file, search_directory,
    sandboxed_list, sandboxed_read, sandboxed_write, sandboxed_delete,
    # Browser Automation
    browse_and_extract, fill_web_form,
    # Memory
    remember, recall, whats_pending,
    # Coding
    dispatch_coding_task,
    # Planner Brain
    plan_goal, get_planner_status, execute_next_planner_step, execute_active_plan, get_execution_summary, reflect_on_execution,
    # Git
    git_status, git_diff,
    # Utils
    format_json, word_count,
    # Daily Workflows
    list_todays_events, draft_email, morning_briefing,
    # Autonomous
    delegate_autonomous_task,
    # Media
    play_music, open_youtube_video, set_system_volume, play_pause_media, speak_text,
    # Cross-Device Ecosystem
    list_connected_devices, execute_phone_command, send_phone_sms, make_phone_call, pair_wireless_device,
    # Native macOS Control
    launch_application, quit_application, focus_window, take_screenshot, manage_clipboard,
    send_system_notification, open_in_finder, open_system_settings, get_battery_status,
    get_wifi_status, get_bluetooth_status, set_display_brightness,
    # Android Companion (Encrypted Wi-Fi)
    get_companion_telemetry, sync_phone_clipboard, transfer_phone_file,
    capture_companion_camera_frame, forward_phone_voice, sync_phone_shared_memory,
    send_companion_sms, make_companion_call,
]

chat_sessions = {}
chat_sessions_lock = threading.RLock()


def _create_chat_session():
    assert client is not None
    return client.chats.create(
        model="gemini-2.5-flash",
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=AVAILABLE_TOOLS,
        ),
    )


def _get_chat_session(session_id: str):
    with chat_sessions_lock:
        if session_id not in chat_sessions:
            chat_sessions[session_id] = _create_chat_session()
        return chat_sessions[session_id]


def _response_text(response) -> str:  # type: ignore[no-untyped-def]
    """Extract text from both one-shot and streamed Google GenAI responses."""
    if not response:
        return ""
    if hasattr(response, "text") and response.text:
        return str(response.text)
    candidates = getattr(response, "candidates", None) or []
    parts_text: list[str] = []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            if getattr(part, "text", None):
                parts_text.append(str(part.text))
            elif getattr(part, "function_response", None):
                response_object = part.function_response.response
                if isinstance(response_object, dict) and "result" in response_object:
                    parts_text.append(str(response_object["result"]))
                else:
                    parts_text.append(str(response_object))
    return "\n".join(parts_text)


def _ndjson(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"


def _stream_voice_command(request: VoiceCommandRequest):
    """Plan then stream tool-enabled conversation output for local TTS.

    This is deliberately additive: browser text chat continues to use its
    existing one-shot endpoint and default session, while every voice session
    receives a separate persistent conversation identifier.
    """
    message = request.message.strip()
    if not message:
        yield _ndjson({"type": "error", "detail": "No speech was transcribed."})
        return

    try:
        plan = kernel.process_system_command(message)
        yield _ndjson({"type": "plan", "payload": plan})
    except Exception as exc:
        yield _ndjson({"type": "error", "detail": f"Planner rejected the request: {exc}"})
        return

    if client is None:
        yield _ndjson({"type": "error", "detail": "GEMINI_API_KEY or GOOGLE_API_KEY is not configured."})
        return

    conversation_id = request.conversation_id.strip()[:128] or "default"
    chat = _get_chat_session(f"voice:{conversation_id}")
    spoken_prompt = (
        "This request came through VEGAS voice. Execute it using the existing tools when appropriate. "
        "Respond naturally in concise, easy-to-speak sentences.\n\n"
        f"User request: {message}"
    )
    response_parts: list[str] = []
    try:
        for response in chat.send_message_stream(spoken_prompt):
            text = _response_text(response)
            if not text:
                continue
            response_parts.append(text)
            yield _ndjson({"type": "delta", "text": text})
    except Exception as exc:
        yield _ndjson({"type": "error", "detail": str(exc)})
        return

    final_text = "".join(response_parts).strip() or "Command processed successfully."
    yield _ndjson({"type": "final", "text": final_text})

# --------------------------------------------------------------------------
# Chat Endpoint
# --------------------------------------------------------------------------
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    session_id = "default"

    if client is None:
        return {"error": "GEMINI_API_KEY or GOOGLE_API_KEY must be configured before chat is available."}

    chat = _get_chat_session(session_id)

    try:
        response = await asyncio.to_thread(chat.send_message, req.message)
        ans = _response_text(response)

        if not ans or ans.strip() == "None":
            ans = "Command processed successfully."

        return {"response": ans}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/voice/stream")
def voice_stream_endpoint(request: VoiceCommandRequest):
    """Stream planner and response events to the local daemon as NDJSON."""
    return StreamingResponse(
        _stream_voice_command(request),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

# --------------------------------------------------------------------------
# System Status — feeds the HUD
# --------------------------------------------------------------------------
@app.get("/api/system-status")
async def system_status():
    try:
        import psutil
        vm = psutil.virtual_memory()
        cpu_pct = psutil.cpu_percent(interval=None)
        mem_used = round(vm.used / (1024**3), 1)
        mem_total = round(vm.total / (1024**3), 1)
        mem_pct = vm.percent
    except ImportError:
        cpu_pct = -1
        mem_used = -1
        mem_total = -1
        mem_pct = -1

    return {
        "status": "ONLINE",
        "model": "Gemini 2.5 Flash",
        "os": f"{platform.system()} {platform.release()}",
        "python": sys.version.split()[0],
        "cpu_cores": os.cpu_count(),
        "cpu_percent": cpu_pct,
        "mem_used_gb": mem_used,
        "mem_total_gb": mem_total,
        "mem_percent": mem_pct,
        "uptime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tool_count": len(AVAILABLE_TOOLS),
        "daemon": daemon_status_hub.snapshot(),
        "planner": kernel.planner.status(),
        "brain": kernel.brain.status(),
        "agents": kernel.registry.list_agents(),
        "companion": companion_hub.get_status(),
    }


# --------------------------------------------------------------------------
# Daemon status transport — additive to the existing REST dashboard surface
# --------------------------------------------------------------------------
@app.get("/api/daemon/status")
async def daemon_status():
    """Return the most recent daemon heartbeat for polling clients."""
    return daemon_status_hub.snapshot()


@app.get("/api/voice/status")
async def voice_status():
    """Return the additive local voice-interface state for dashboard clients."""
    return daemon_status_hub.snapshot().get("voice", {"state": "unknown"})


@app.post("/api/planner/plan")
async def planner_plan(req: PlannerGoalRequest):
    """Create a structured execution plan without running delegated work."""
    try:
        res_str = await asyncio.to_thread(plan_goal, req.goal)
        return json.loads(res_str)
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/api/planner/status")
async def planner_status():
    """Return active planner state and registered specialist agents."""
    try:
        res_str = await asyncio.to_thread(get_planner_status)
        return json.loads(res_str)
    except Exception as exc:
        return {"error": str(exc)}


@app.post("/api/planner/execute-next")
async def planner_execute_next():
    """Delegate the next active planner step to its selected specialist agent."""
    try:
        res_str = await asyncio.to_thread(execute_next_planner_step)
        return json.loads(res_str)
    except Exception as exc:
        return {"error": str(exc)}


@app.post("/api/planner/execute")
async def planner_execute(req: PlannerExecuteRequest):
    """Execute active planner steps until completion, failure, or confirmation."""
    try:
        res_str = await asyncio.to_thread(execute_active_plan, req.max_steps)
        return json.loads(res_str)
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/api/planner/summary")
async def planner_summary():
    """Return a concise human-readable execution summary."""
    return {"summary": get_execution_summary()}


@app.get("/api/planner/brain")
async def planner_brain_status():
    """Return AI Brain status: model availability, cache size, reasoning trace."""
    return kernel.brain.status()


@app.post("/api/planner/reflect")
async def planner_reflect():
    """Trigger post-execution reflection and return extracted lessons."""
    try:
        return json.loads(reflect_on_execution())
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/api/agents")
async def list_agents():
    """Return status and owned tools for all registered specialist agents."""
    return {"agents": kernel.registry.list_agents()}


@app.get("/api/agents/{role}")
async def get_agent_detail(role: str):
    """Return detailed status and tool manifest for a specific agent role."""
    agent = kernel.registry.get(role)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent role '{role}' not found.")
    return agent.status()


@app.get("/api/memory/preferences")
async def get_memory_preferences():
    """Return stored user coding preferences and style rules."""
    return {"preferences": kernel.memory.get_coding_prefs()}


@app.get("/api/memory/projects")
async def get_memory_projects(path: str = "."):
    """Return stored project memory facts for a repository."""
    info = kernel.memory.get_project_info(path)
    return {"project": info or {}}


@app.get("/api/memory/semantic")
async def search_memory_semantic(q: str, limit: int = 5, category: Optional[str] = None):
    """Perform semantic retrieval across conversations, project facts, preferences, and summaries."""
    results = await asyncio.to_thread(kernel.memory.semantic_search, q, limit=limit, category=category)
    return {"query": q, "results": results}


@app.post("/api/memory/summarize")
async def summarize_memory_long_term(scope: str = "session"):
    """Consolidate dialogue history into a long-term milestone summary."""
    summary_text = await asyncio.to_thread(kernel.memory.summarize_long_term_memory, scope=scope)
    return {"status": "success", "summary": summary_text}


@app.get("/api/companion/status")
async def companion_status():
    """Return live Android Companion Wi-Fi telemetry and connection status."""
    return companion_hub.get_status()


@app.post("/api/companion/sync")
async def companion_sync_data(payload: dict):
    """REST fallback sync for Android Companion telemetry or frames."""
    return companion_hub.process_incoming_frame(json.dumps(payload))


@app.websocket("/api/companion/ws")
async def companion_websocket_endpoint(websocket: WebSocket):
    """
    Encrypted Wi-Fi WebSocket endpoint for Android Companion phone connection.
    Exchanges authenticated JSON frames for telemetry, clipboard, notifications,
    camera streaming, voice forwarding, and shared memory.
    """
    await websocket.accept()
    dev_id = "android_wifi_device"
    companion_hub.register_connection(dev_id, "Android Phone (Wi-Fi)", websocket)
    try:
        while True:
            raw_text = await websocket.receive_text()
            response = companion_hub.process_incoming_frame(raw_text)
            await websocket.send_json(response)
    except WebSocketDisconnect:
        companion_hub.unregister_connection(dev_id)
    except Exception:
        companion_hub.unregister_connection(dev_id)


@app.websocket("/api/daemon/ws")
async def daemon_status_ingest(websocket: WebSocket):
    """Receive daemon heartbeats with an optional local shared-secret check."""
    if not _is_loopback_websocket(websocket) or not _valid_daemon_token(websocket):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    try:
        await websocket.send_json({"type": "connected"})
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                await websocket.send_json({"type": "error", "detail": "Expected a JSON object."})
                continue

            message_type = message.get("type")
            if message_type == "status" and isinstance(message.get("payload"), dict):
                await daemon_status_hub.update(message["payload"])
                await websocket.send_json({"type": "ack"})
            elif message_type == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                await websocket.send_json({"type": "error", "detail": "Unsupported daemon message."})
    except WebSocketDisconnect:
        return


@app.websocket("/api/daemon/status/ws")
async def daemon_status_dashboard(websocket: WebSocket):
    """Stream daemon status to local dashboard clients."""
    if not _is_loopback_websocket(websocket):
        await websocket.close(code=1008)
        return

    await daemon_status_hub.add_dashboard(websocket)
    try:
        while True:
            # The dashboard does not need to send messages, but receiving keeps
            # disconnect detection and browser-close cleanup reliable.
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    finally:
        daemon_status_hub.remove_dashboard(websocket)

# --------------------------------------------------------------------------
# Tools Registry — UI can render tool cards from this
# --------------------------------------------------------------------------
@app.get("/api/tools")
async def list_tools():
    tools = [
        {"name": "search_web",       "category": "Web Research",   "icon": "🔍", "description": "Search the web with DuckDuckGo"},
        {"name": "fetch_url",        "category": "Web Research",   "icon": "🌐", "description": "Fetch and extract text from any URL"},
        {"name": "get_world_news",   "category": "Web Research",   "icon": "📰", "description": "Get latest news headlines by topic"},
        {"name": "open_world_monitor","category": "Web Research",  "icon": "🌍", "description": "Full situation report: world, tech & business"},
        {"name": "get_current_time", "category": "System",         "icon": "⏱️", "description": "Get current date/time in any timezone"},
        {"name": "get_system_info",  "category": "System",         "icon": "💻", "description": "OS, CPU, memory, Python version"},
        {"name": "run_command",      "category": "Developer",      "icon": "⚡", "description": "Execute shell commands on the host"},
        {"name": "list_directory",   "category": "Developer & Files", "icon": "📁", "description": "List files and folders in sandboxed directory"},
        {"name": "read_file",        "category": "Developer & Files", "icon": "📄", "description": "Read the contents of a sandboxed file"},
        {"name": "write_file",       "category": "Developer & Files", "icon": "✏️", "description": "Write or create sandboxed files (gated)"},
        {"name": "delete_file",      "category": "Developer & Files", "icon": "🗑️", "description": "Delete sandboxed files (gated)"},
        {"name": "edit_file",        "category": "Developer",      "icon": "🔧", "description": "Edit existing files with find/replace"},
        {"name": "search_directory", "category": "Developer",      "icon": "🔎", "description": "Grep/search within a directory"},
        {"name": "browse_and_extract","category": "Browser Automation", "icon": "🌐", "description": "Extract text from any URL using Playwright"},
        {"name": "fill_web_form",    "category": "Browser Automation", "icon": "📋", "description": "Fill and submit web forms with Playwright (gated)"},
        {"name": "remember",         "category": "Memory",         "icon": "🧠", "description": "Store a fact in persistent memory"},
        {"name": "recall",           "category": "Memory",         "icon": "💭", "description": "Search stored memories and events"},
        {"name": "whats_pending",    "category": "Memory",         "icon": "📋", "description": "List all pending tasks & actions"},
        {"name": "plan_goal",         "category": "Planner Brain",  "icon": "🧭", "description": "Understand a goal, break it into subtasks, and route work to agents"},
        {"name": "get_planner_status","category": "Planner Brain",  "icon": "🧠", "description": "Inspect active plan, known plans, and specialist agent profiles"},
        {"name": "execute_next_planner_step", "category": "Planner Brain", "icon": "▶️", "description": "Delegate the next planned step to its chosen agent"},
        {"name": "execute_active_plan", "category": "Planner Brain", "icon": "⚙️", "description": "Coordinate active plan execution until completion, failure, or confirmation"},
        {"name": "get_execution_summary", "category": "Planner Brain", "icon": "📄", "description": "Produce the current execution summary"},
        {"name": "reflect_on_execution", "category": "Planner Brain", "icon": "🔮", "description": "Extract lessons learned and patterns from completed execution"},
        {"name": "dispatch_coding_task","category": "Coding",      "icon": "🤖", "description": "Delegate coding to Antigravity CLI"},
        {"name": "git_status",       "category": "Git",            "icon": "📊", "description": "Check git status of a repository"},
        {"name": "git_diff",         "category": "Git",            "icon": "📝", "description": "View uncommitted changes"},
        {"name": "format_json",      "category": "Utilities",      "icon": "📐", "description": "Pretty-format JSON strings"},
        {"name": "word_count",       "category": "Utilities",      "icon": "🔢", "description": "Count words in text"},
        {"name": "list_todays_events", "category": "Daily Workflows", "icon": "📅", "description": "List remaining Google Calendar events for today"},
        {"name": "draft_email",       "category": "Daily Workflows", "icon": "✉️", "description": "Create a draft email in Gmail (gated)"},
        {"name": "morning_briefing",  "category": "Daily Workflows", "icon": "☕", "description": "Generate daily morning briefing digest"},
        {"name": "delegate_autonomous_task", "category": "Autonomous", "icon": "🧠", "description": "Delegate a complex task to background agent"},
    ]
    return {"tools": tools, "total": len(tools)}

# --------------------------------------------------------------------------
# Memory Endpoints
# --------------------------------------------------------------------------
@app.post("/api/memory/remember", response_model=GenericResultResponse)
async def memory_remember(req: MemoryRequest):
    result = remember(req.fact)
    return GenericResultResponse(result=result)

@app.post("/api/memory/recall", response_model=GenericResultResponse)
async def memory_recall(req: RecallRequest):
    result = recall(req.query)
    return GenericResultResponse(result=result)

@app.get("/api/memory/pending", response_model=GenericResultResponse)
async def memory_pending():
    result = whats_pending()
    return GenericResultResponse(result=result)

# --------------------------------------------------------------------------
# Reset Chat Session
# --------------------------------------------------------------------------
@app.post("/api/reset", response_model=ResetResponse)
async def reset_chat():
    with chat_sessions_lock:
        chat_sessions.clear()
    return ResetResponse(result="Session cleared. VEGAS memory persists, but conversation context has been reset.")

def main() -> None:
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8001, reload=True)

if __name__ == "__main__":
    main()
