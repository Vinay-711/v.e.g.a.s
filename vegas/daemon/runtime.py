"""VEGAS daemon lifecycle, service supervision, and status transport."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import websockets
from dotenv import load_dotenv

from .services import ServiceSpec, ServiceSupervisor
from .status import DaemonStatus
from .wakeword import PorcupineWakeWordMonitor, WakeWordConfig
from vegas.voice import VoiceConfig, VoiceSessionManager


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if 1 <= parsed <= 65535 else default


def _env_float(name: str, default: float, *, minimum: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed if parsed >= minimum else default


@dataclass(frozen=True)
class VegasDaemonConfig:
    """Runtime configuration, intentionally independent of legacy config.py."""

    project_root: Path
    python_executable: Path
    api_host: str
    api_port: int
    mcp_port: int
    status_ws_url: str
    status_token: str | None
    monitor_interval_seconds: float
    heartbeat_interval_seconds: float
    log_dir: Path
    start_api: bool
    start_mcp: bool

    @classmethod
    def from_environment(cls, project_root: Path | None = None) -> "VegasDaemonConfig":
        root = (project_root or Path(os.getenv("VEGAS_PROJECT_ROOT", Path.cwd()))).expanduser().resolve()
        # LaunchAgents do not inherit an interactive shell's environment.
        # Load the project-local configuration here so the daemon itself (not
        # only its FastAPI child) receives the wake-word and service settings.
        # Explicit environment variables still take precedence.
        load_dotenv(root / ".env", override=False)
        api_host = os.getenv("VEGAS_API_HOST", "127.0.0.1")
        api_port = _env_int("VEGAS_API_PORT", 8001)
        status_ws_url = os.getenv(
            "VEGAS_DAEMON_STATUS_WS_URL",
            f"ws://{api_host}:{api_port}/api/daemon/ws",
        )
        return cls(
            project_root=root,
            # Do not resolve this path: a virtualenv's python is commonly a
            # symlink to the system interpreter, and resolving it drops the
            # virtualenv site-packages used by uvicorn and VEGAS.
            python_executable=Path(sys.executable).absolute(),
            api_host=api_host,
            api_port=api_port,
            mcp_port=_env_int("VEGAS_MCP_PORT", 8000),
            status_ws_url=status_ws_url,
            status_token=os.getenv("VEGAS_DAEMON_TOKEN") or None,
            monitor_interval_seconds=_env_float(
                "VEGAS_DAEMON_MONITOR_INTERVAL_SECONDS", 2.0, minimum=0.25
            ),
            heartbeat_interval_seconds=_env_float(
                "VEGAS_DAEMON_HEARTBEAT_SECONDS", 5.0, minimum=1.0
            ),
            log_dir=Path(os.getenv("VEGAS_DAEMON_LOG_DIR", "~/.vegas/logs")).expanduser(),
            start_api=_env_flag("VEGAS_DAEMON_START_API", True),
            start_mcp=_env_flag("VEGAS_DAEMON_START_MCP", True),
        )

    def service_specs(self) -> list[ServiceSpec]:
        """Return existing FastAPI/FastMCP services without changing their entry points."""
        return [
            ServiceSpec(
                name="fastapi",
                command=(
                    str(self.python_executable),
                    "-m",
                    "uvicorn",
                    "api:app",
                    "--host",
                    self.api_host,
                    "--port",
                    str(self.api_port),
                    "--no-access-log",
                ),
                port=self.api_port,
                health_url=f"http://{self.api_host}:{self.api_port}/api/system-status",
                enabled=self.start_api,
            ),
            ServiceSpec(
                name="fastmcp",
                command=(str(self.python_executable), str(self.project_root / "server.py")),
                port=self.mcp_port,
                enabled=self.start_mcp,
                # server.py reads this to configure FastMCP explicitly.
                environment={"VEGAS_MCP_PORT": str(self.mcp_port)},
            ),
        ]


class StatusWebSocketClient:
    """Reconnect a daemon to FastAPI with heartbeat and websocket keepalives."""

    def __init__(
        self,
        *,
        url: str,
        token: str | None,
        heartbeat_interval_seconds: float,
        status_provider: Callable[[], dict[str, Any]],
        connection_callback: Callable[..., None],
    ) -> None:
        self._url = url
        self._token = token
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._status_provider = status_provider
        self._connection_callback = connection_callback
        self._connection: Any | None = None
        self._send_lock: asyncio.Lock | None = None

    async def run(self, stop_event: asyncio.Event) -> None:
        reconnect_attempts = 0
        while not stop_event.is_set():
            self._connection_callback("connecting", reconnect_attempts=reconnect_attempts)
            try:
                async with websockets.connect(
                    self._url,
                    additional_headers=self._headers(),
                    open_timeout=5,
                    close_timeout=2,
                    ping_interval=20,
                    ping_timeout=10,
                    proxy=None,
                ) as websocket:
                    self._connection = websocket
                    reconnect_attempts = 0
                    self._connection_callback("connected", reconnect_attempts=0)
                    await self.publish_current()
                    await self._heartbeat_loop(websocket, stop_event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                reconnect_attempts += 1
                self._connection_callback(
                    "reconnecting",
                    reconnect_attempts=reconnect_attempts,
                    error=str(exc),
                )
                await self._wait_or_stop(stop_event, self._backoff_seconds(reconnect_attempts))
            finally:
                self._connection = None

        self._connection_callback("disconnected", reconnect_attempts=reconnect_attempts)

    async def publish_current(self) -> bool:
        """Push the latest status immediately when a connection is available."""
        if self._connection is None:
            return False
        payload = {"type": "status", "payload": self._status_provider()}
        try:
            lock = self._send_lock
            if lock is None:
                lock = asyncio.Lock()
                self._send_lock = lock
            async with lock:
                await self._connection.send(json.dumps(payload, ensure_ascii=False))
            return True
        except Exception as exc:
            self._connection_callback("reconnecting", error=str(exc))
            return False

    async def _heartbeat_loop(self, websocket: Any, stop_event: asyncio.Event) -> None:
        next_heartbeat = time.monotonic() + self._heartbeat_interval_seconds
        while not stop_event.is_set():
            timeout = max(0.1, next_heartbeat - time.monotonic())
            try:
                # FastAPI emits acknowledgement messages.  They are deliberately
                # ignored here; receiving them proves the channel remains usable.
                await asyncio.wait_for(websocket.recv(), timeout=timeout)
            except TimeoutError:
                if not await self.publish_current():
                    raise ConnectionError("Unable to publish daemon heartbeat.")
                next_heartbeat = time.monotonic() + self._heartbeat_interval_seconds
            except Exception:
                raise

    def _headers(self) -> dict[str, str] | None:
        if not self._token:
            return None
        return {"X-VEGAS-Daemon-Token": self._token}

    @staticmethod
    async def _wait_or_stop(stop_event: asyncio.Event, delay: float) -> None:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
        except TimeoutError:
            return

    @staticmethod
    def _backoff_seconds(reconnect_attempts: int) -> float:
        return min(30.0, 1.0 * (2 ** min(reconnect_attempts - 1, 5)))


class VegasDaemon:
    """Always-on local supervisor for VEGAS.

    The main loop wakes every two seconds by default.  It does no active audio
    polling: wake-word capture is handled by the audio backend's blocking
    callback.  This keeps idle CPU usage low while retaining process recovery
    and dashboard heartbeats.
    """

    def __init__(
        self,
        config: VegasDaemonConfig,
        *,
        status: DaemonStatus | None = None,
        supervisor: ServiceSupervisor | None = None,
        wake_word_monitor: PorcupineWakeWordMonitor | None = None,
        status_client: StatusWebSocketClient | None = None,
        voice_session: VoiceSessionManager | None = None,
    ) -> None:
        self.config = config
        self.status = status or DaemonStatus()
        self._supervisor = supervisor or ServiceSupervisor(
            config.service_specs(),
            project_root=config.project_root,
            log_dir=config.log_dir,
            status_callback=self._on_service_update,
        )
        self._wake_word_monitor = wake_word_monitor or PorcupineWakeWordMonitor(
            WakeWordConfig.from_environment(),
            status_callback=self._on_wake_word_status,
        )
        self._voice_session = voice_session or VoiceSessionManager(
            VoiceConfig.from_environment(api_host=config.api_host, api_port=config.api_port),
            status_callback=self._on_voice_status,
            pause_wake_word=getattr(self._wake_word_monitor, "pause", self._wake_word_monitor.stop),
            resume_wake_word=getattr(self._wake_word_monitor, "resume", self._wake_word_monitor.start),
        )
        self._status_client = status_client or StatusWebSocketClient(
            url=config.status_ws_url,
            token=config.status_token,
            heartbeat_interval_seconds=config.heartbeat_interval_seconds,
            status_provider=self.status.snapshot,
            connection_callback=self._on_websocket_status,
        )
        self._stop_requested: asyncio.Event | None = None
        self._status_transport_stop: asyncio.Event | None = None
        self._status_task: asyncio.Task[None] | None = None
        self._shutdown_requested = False
        self._started = False

    async def run_forever(self) -> None:
        """Start services and remain active until SIGINT or SIGTERM."""
        if self._started:
            raise RuntimeError("VegasDaemon is already running.")
        if not self.config.project_root.is_dir():
            raise RuntimeError(f"VEGAS project root does not exist: {self.config.project_root}")

        self._started = True
        self._stop_requested = asyncio.Event()
        self._status_transport_stop = asyncio.Event()
        if self._shutdown_requested:
            self._stop_requested.set()
        self._install_signal_handlers()

        self.status.set_state("starting")
        self.status.add_event("daemon_started", "VEGAS daemon started")
        self._supervisor.start_all()
        self._wake_word_monitor.start()
        self._status_task = asyncio.create_task(
            self._status_client.run(self._status_transport_stop),
            name="vegas-daemon-status-websocket",
        )
        # Start publishing before loading a local Whisper model, which can
        # take seconds on first boot. The dashboard then sees initializing
        # rather than mistaking model warm-up for a dead daemon.
        await self._voice_session.start()

        try:
            while not self._stop_requested.is_set():
                self._supervisor.tick()
                await self._drain_wake_word_events()
                self._refresh_overall_state()
                await self._wait_for_shutdown(self.config.monitor_interval_seconds)
        finally:
            await self._shutdown()

    def request_shutdown(self) -> None:
        """Request a graceful shutdown from a signal handler or controlling CLI."""
        self._shutdown_requested = True
        self.status.set_state("stopping")
        self.status.add_event("shutdown_requested", "Graceful shutdown requested")
        if self._stop_requested is not None:
            self._stop_requested.set()

    def _on_service_update(self, name: str, payload: dict[str, Any]) -> None:
        self.status.update_service(name, **payload)

    def _on_wake_word_status(self, state: str, backend: str | None, detail: str | None) -> None:
        self.status.update_wake_word(state, backend=backend, detail=detail)

    def _on_websocket_status(self, state: str, **values: Any) -> None:
        self.status.set_websocket(state, **values)

    def _on_voice_status(self, state: str, values: dict[str, Any]) -> None:
        self.status.update_voice(state, **values)

    async def _drain_wake_word_events(self) -> None:
        detections = self._wake_word_monitor.drain_detections()
        if detections:
            for _ in range(detections):
                self.status.note_wake_word()
            self.status.update_wake_word(
                "listening",
                backend=self._wake_word_monitor.backend_name,
                detail="Hey Vegas detected; opening the voice interaction pipeline.",
            )
            # Coalesce multiple callback hits from one phrase into one command;
            # a later phrase during speech still arrives as a separate tick and
            # is handled as an interruption.
            await self._voice_session.handle_wake_word()

    def _refresh_overall_state(self) -> None:
        if self._shutdown_requested:
            return
        services = self._supervisor.snapshot()
        service_states = {service["state"] for service in services.values()}
        status_snapshot = self.status.snapshot()
        wake_state = status_snapshot["wake_word"]["state"]
        voice_state = status_snapshot["voice"]["state"]
        if "failed" in service_states or "degraded" in service_states:
            self.status.set_state("degraded")
        elif wake_state in {"unavailable", "disabled"}:
            self.status.set_state("degraded", detail="Wake-word monitoring is not active.")
        elif voice_state in {"unavailable", "disabled", "error"}:
            self.status.set_state("degraded", detail="Voice interaction is not active.")
        elif service_states and service_states <= {"running", "external", "disabled"}:
            self.status.set_state("running")
        else:
            self.status.set_state("starting")

    def _install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.request_shutdown)
            except (NotImplementedError, RuntimeError):
                # Tests and non-POSIX hosts can still use request_shutdown().
                signal.signal(sig, lambda _signum, _frame: self.request_shutdown())

    async def _wait_for_shutdown(self, timeout_seconds: float) -> None:
        assert self._stop_requested is not None
        try:
            await asyncio.wait_for(self._stop_requested.wait(), timeout=timeout_seconds)
        except TimeoutError:
            return

    async def _shutdown(self) -> None:
        self.status.set_state("stopping")
        await self._status_client.publish_current()
        await self._voice_session.stop()
        self._wake_word_monitor.stop()
        self._supervisor.stop_all()
        self.status.set_state("stopped")
        self.status.add_event("daemon_stopped", "VEGAS daemon stopped")
        # Give the dashboard a final terminal state before the status transport
        # closes. This is best effort: a stopped FastAPI service may already
        # have closed the local WebSocket.
        await self._status_client.publish_current()

        if self._status_transport_stop is not None:
            self._status_transport_stop.set()
        if self._status_task is not None:
            self._status_task.cancel()
            try:
                await self._status_task
            except asyncio.CancelledError:
                pass


def configure_logging() -> None:
    """Configure concise logs for foreground runs and LaunchAgent capture."""
    level_name = os.getenv("VEGAS_DAEMON_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
