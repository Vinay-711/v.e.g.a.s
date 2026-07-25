"""Focused tests for the always-on VEGAS daemon infrastructure."""

from __future__ import annotations

import asyncio
import plistlib
import sys
from pathlib import Path

from vegas.daemon.launchagent import LAUNCH_AGENT_LABEL, MacOSLaunchAgent
from vegas.daemon.runtime import VegasDaemon, VegasDaemonConfig
from vegas.daemon.services import ServiceSpec, ServiceSupervisor
from vegas.daemon.status import DaemonStatus, DashboardStatusHub
from vegas.daemon.wakeword import PorcupineWakeWordMonitor, WakeWordConfig


def test_daemon_config_preserves_the_virtualenv_interpreter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VEGAS_PROJECT_ROOT", str(tmp_path))
    config = VegasDaemonConfig.from_environment()

    assert config.python_executable == Path(sys.executable).absolute()


def test_daemon_loads_project_dotenv_without_overriding_environment(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env").write_text(
        "VEGAS_API_PORT=8123\nVEGAS_MCP_PORT=8124\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("VEGAS_API_PORT", raising=False)
    monkeypatch.delenv("VEGAS_MCP_PORT", raising=False)

    config = VegasDaemonConfig.from_environment(tmp_path)

    assert config.api_port == 8123
    assert config.mcp_port == 8124

    monkeypatch.setenv("VEGAS_API_PORT", "9123")
    overridden = VegasDaemonConfig.from_environment(tmp_path)
    assert overridden.api_port == 9123


def test_daemon_maps_its_mcp_port_to_fastmcp_settings(tmp_path: Path) -> None:
    config = VegasDaemonConfig(
        project_root=tmp_path,
        python_executable=tmp_path / "python",
        api_host="127.0.0.1",
        api_port=8001,
        mcp_port=8100,
        status_ws_url="ws://127.0.0.1:8001/api/daemon/ws",
        status_token=None,
        monitor_interval_seconds=2,
        heartbeat_interval_seconds=5,
        log_dir=tmp_path / "logs",
        start_api=True,
        start_mcp=True,
    )

    fastmcp = next(spec for spec in config.service_specs() if spec.name == "fastmcp")

    assert fastmcp.port == 8100
    assert fastmcp.environment["VEGAS_MCP_PORT"] == "8100"


def test_status_snapshot_tracks_services_wake_word_and_socket() -> None:
    status = DaemonStatus(version="test")
    status.update_service("fastapi", state="running", pid=123)
    status.update_wake_word("listening", backend="porcupine", detail="ready")
    status.set_websocket("connected", reconnect_attempts=0)
    status.note_wake_word()

    snapshot = status.snapshot()

    assert snapshot["version"] == "test"
    assert snapshot["services"]["fastapi"]["state"] == "running"
    assert snapshot["wake_word"]["detections"] == 1
    assert snapshot["websocket"]["state"] == "connected"
    assert snapshot["recent_events"][-1]["kind"] == "wake_word_detected"


def test_dashboard_hub_broadcasts_latest_snapshot() -> None:
    class FakeWebSocket:
        def __init__(self) -> None:
            self.accepted = False
            self.messages: list[dict] = []

        async def accept(self) -> None:
            self.accepted = True

        async def send_json(self, message: dict) -> None:
            self.messages.append(message)

    async def scenario() -> None:
        hub = DashboardStatusHub(stale_after_seconds=60)
        socket = FakeWebSocket()
        await hub.add_dashboard(socket)
        await hub.update({"state": "running", "wake_word": {"state": "listening"}})

        assert socket.accepted
        assert socket.messages[0]["payload"]["state"] == "offline"
        assert socket.messages[-1]["payload"]["state"] == "running"
        assert hub.snapshot()["stale"] is False

    asyncio.run(scenario())


def test_disabled_wake_word_monitor_does_not_require_audio_dependencies() -> None:
    updates: list[tuple[str, str | None, str | None]] = []
    monitor = PorcupineWakeWordMonitor(
        WakeWordConfig(enabled=False, access_key=None, keyword_path=None),
        status_callback=lambda state, backend, detail: updates.append((state, backend, detail)),
    )

    monitor.start()
    monitor.stop()

    assert updates == [("disabled", "porcupine", "Wake-word monitoring is disabled by configuration.")]
    assert monitor.drain_detections() == 0


def test_service_supervisor_adopts_an_existing_service_without_stopping_it(tmp_path: Path, monkeypatch) -> None:
    updates: list[tuple[str, dict]] = []
    spec = ServiceSpec(name="fastapi", command=("unused",), port=8123, health_url=None)
    supervisor = ServiceSupervisor(
        [spec],
        project_root=tmp_path,
        log_dir=tmp_path / "logs",
        status_callback=lambda name, payload: updates.append((name, payload)),
    )
    monkeypatch.setattr(supervisor, "_is_port_open", lambda _port: True)

    supervisor.start_all()
    supervisor.stop_all()

    snapshot = supervisor.snapshot()["fastapi"]
    assert snapshot["state"] == "external"
    assert snapshot["externally_managed"] is True
    assert snapshot["managed"] is False
    assert updates[-1][1]["state"] == "external"


def test_service_supervisor_restarts_only_after_a_child_exits(tmp_path: Path, monkeypatch) -> None:
    class FakeProcess:
        pid = 43210

        def __init__(self) -> None:
            self.exit_code: int | None = None

        def poll(self) -> int | None:
            return self.exit_code

        def wait(self, timeout: float | None = None) -> int:
            self.exit_code = self.exit_code if self.exit_code is not None else 0
            return self.exit_code

    created: list[FakeProcess] = []

    def fake_popen(*_args, **_kwargs) -> FakeProcess:
        process = FakeProcess()
        created.append(process)
        return process

    now = [0.0]
    spec = ServiceSpec(name="fastapi", command=("unused",), port=8124, health_url=None)
    supervisor = ServiceSupervisor(
        [spec],
        project_root=tmp_path,
        log_dir=tmp_path / "logs",
        popen_factory=fake_popen,
        clock=lambda: now[0],
    )
    monkeypatch.setattr(supervisor, "_is_port_open", lambda _port: False)
    monkeypatch.setattr(supervisor, "_is_ready", lambda _spec: True)
    monkeypatch.setattr(supervisor, "_terminate_process_group", lambda *_args: None)

    supervisor.start_all()
    supervisor.tick()
    assert supervisor.snapshot()["fastapi"]["state"] == "running"

    created[0].exit_code = 1
    supervisor.tick()
    failed = supervisor.snapshot()["fastapi"]
    assert failed["state"] == "failed"
    assert failed["restart_count"] == 1

    now[0] = 2.0
    supervisor.tick()
    assert len(created) == 2
    assert supervisor.snapshot()["fastapi"]["state"] == "starting"


def test_launch_agent_payload_is_valid_and_user_scoped(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    agent = MacOSLaunchAgent(tmp_path / "project")
    payload = agent.plist_payload(python_executable=tmp_path / "python")
    parsed = plistlib.loads(plistlib.dumps(payload))

    assert parsed["Label"] == LAUNCH_AGENT_LABEL
    assert parsed["RunAtLoad"] is True
    assert parsed["KeepAlive"] == {"SuccessfulExit": False}
    assert parsed["ProcessType"] == "Background"
    assert parsed["ProgramArguments"][1:3] == ["-m", "vegas.daemon"]
    assert "LaunchAgents" in str(agent.paths.plist_path)


def test_daemon_gracefully_stops_injected_components(tmp_path: Path) -> None:
    class FakeSupervisor:
        def __init__(self) -> None:
            self.started = False
            self.stopped = False

        def start_all(self) -> None:
            self.started = True

        def tick(self) -> None:
            return None

        def stop_all(self) -> None:
            self.stopped = True

        def snapshot(self) -> dict:
            return {"fastapi": {"state": "running"}, "fastmcp": {"state": "running"}}

    class FakeWakeWord:
        backend_name = "fake"

        def __init__(self) -> None:
            self.started = False
            self.stopped = False
            self._detections = 1

        def start(self) -> None:
            self.started = True

        def stop(self) -> None:
            self.stopped = True

        def drain_detections(self) -> int:
            detections, self._detections = self._detections, 0
            return detections

    class FakeStatusClient:
        def __init__(self) -> None:
            self.published = 0

        async def run(self, stop_event: asyncio.Event) -> None:
            await stop_event.wait()

        async def publish_current(self) -> bool:
            self.published += 1
            return True

    config = VegasDaemonConfig(
        project_root=tmp_path,
        python_executable=tmp_path / "python",
        api_host="127.0.0.1",
        api_port=8001,
        mcp_port=8000,
        status_ws_url="ws://127.0.0.1:8001/api/daemon/ws",
        status_token=None,
        monitor_interval_seconds=0.01,
        heartbeat_interval_seconds=1,
        log_dir=tmp_path / "logs",
        start_api=True,
        start_mcp=True,
    )
    supervisor = FakeSupervisor()
    wake_word = FakeWakeWord()
    status_client = FakeStatusClient()
    daemon = VegasDaemon(
        config,
        supervisor=supervisor,  # type: ignore[arg-type]
        wake_word_monitor=wake_word,  # type: ignore[arg-type]
        status_client=status_client,  # type: ignore[arg-type]
    )

    async def scenario() -> None:
        task = asyncio.create_task(daemon.run_forever())
        await asyncio.sleep(0.03)
        daemon.request_shutdown()
        await task

    asyncio.run(scenario())

    assert supervisor.started and supervisor.stopped
    assert wake_word.started and wake_word.stopped
    assert status_client.published == 2
    assert daemon.status.snapshot()["state"] == "stopped"
    assert daemon.status.snapshot()["wake_word"]["detections"] == 1


def test_fastapi_ingests_and_streams_daemon_status(monkeypatch) -> None:
    """Exercise the actual FastAPI websocket routes on a loopback client."""
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "")

    from fastapi.testclient import TestClient
    import api

    api.daemon_status_hub = DashboardStatusHub(stale_after_seconds=60)
    with TestClient(api.app, client=("127.0.0.1", 51234)) as client:
        with client.websocket_connect("/api/daemon/ws") as daemon_socket:
            assert daemon_socket.receive_json()["type"] == "connected"
            daemon_socket.send_json(
                {
                    "type": "status",
                    "payload": {
                        "state": "running",
                        "wake_word": {"state": "listening", "detections": 3},
                        "services": {"fastapi": {"state": "running"}},
                    },
                }
            )
            assert daemon_socket.receive_json()["type"] == "ack"

            response = client.get("/api/daemon/status")
            assert response.status_code == 200
            assert response.json()["wake_word"]["detections"] == 3

            with client.websocket_connect("/api/daemon/status/ws") as dashboard_socket:
                update = dashboard_socket.receive_json()
                assert update["type"] == "daemon_status"
                assert update["payload"]["state"] == "running"
