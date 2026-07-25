"""Low-overhead supervision for the existing VEGAS backend processes."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class ServiceSpec:
    """Description of one backend process managed by the daemon."""

    name: str
    command: Sequence[str]
    port: int
    health_url: str | None = None
    enabled: bool = True
    environment: Mapping[str, str] = field(default_factory=dict)


@dataclass
class ManagedService:
    spec: ServiceSpec
    process: subprocess.Popen[bytes] | None = None
    log_handle: Any | None = None
    externally_managed: bool = False
    restart_count: int = 0
    next_restart_at: float = 0.0
    started_at: float | None = None
    last_error: str | None = None
    state: str = "stopped"


class ServiceSupervisor:
    """Supervise API and MCP child processes without a tight polling loop.

    Existing manually started services are detected by their loopback port and
    are never terminated by the daemon.  Services spawned by the daemon run in
    their own process groups so shutdown can be graceful and contained.
    """

    def __init__(
        self,
        specs: Sequence[ServiceSpec],
        *,
        project_root: Path,
        log_dir: Path,
        environment: Mapping[str, str] | None = None,
        status_callback: Callable[[str, dict[str, Any]], None] | None = None,
        popen_factory: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
        clock: Callable[[], float] = time.monotonic,
        startup_timeout_seconds: float = 30.0,
        restart_base_delay_seconds: float = 2.0,
        restart_max_delay_seconds: float = 60.0,
    ) -> None:
        self._services = {spec.name: ManagedService(spec) for spec in specs}
        self._project_root = project_root
        self._log_dir = log_dir
        self._environment = dict(environment or os.environ)
        self._status_callback = status_callback or (lambda _name, _payload: None)
        self._popen_factory = popen_factory
        self._clock = clock
        self._startup_timeout_seconds = startup_timeout_seconds
        self._restart_base_delay_seconds = restart_base_delay_seconds
        self._restart_max_delay_seconds = restart_max_delay_seconds
        self._stopping = False

    def start_all(self) -> None:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        for runtime in self._services.values():
            if not runtime.spec.enabled:
                runtime.state = "disabled"
                self._publish(runtime)
                continue
            self._start_or_adopt(runtime)

    def tick(self) -> None:
        """Refresh services and restart daemon-owned failures when due."""
        if self._stopping:
            return

        now = self._clock()
        for runtime in self._services.values():
            if not runtime.spec.enabled:
                continue

            if runtime.externally_managed:
                if self._is_ready(runtime.spec):
                    runtime.state = "external"
                else:
                    runtime.externally_managed = False
                    runtime.state = "stopped"
                    runtime.next_restart_at = now
                self._publish(runtime)
                continue

            process = runtime.process
            if process is None:
                if now >= runtime.next_restart_at:
                    self._start_or_adopt(runtime)
                continue

            exit_code = process.poll()
            if exit_code is not None:
                runtime.last_error = f"Process exited with code {exit_code}."
                self._close_log(runtime)
                runtime.process = None
                runtime.state = "failed"
                runtime.restart_count += 1
                runtime.next_restart_at = now + self._restart_delay(runtime.restart_count)
                self._publish(runtime)
                continue

            if self._is_ready(runtime.spec):
                runtime.state = "running"
                runtime.last_error = None
            elif runtime.started_at is not None and now - runtime.started_at > self._startup_timeout_seconds:
                runtime.last_error = f"Service did not become ready within {self._startup_timeout_seconds:.0f}s."
                runtime.state = "degraded"
            else:
                runtime.state = "starting"
            self._publish(runtime)

    def stop_all(self, *, timeout_seconds: float = 10.0) -> None:
        """Stop only child processes that this daemon created."""
        self._stopping = True
        for runtime in self._services.values():
            if runtime.process is None:
                continue
            runtime.state = "stopping"
            self._publish(runtime)
            self._terminate_process_group(runtime.process, timeout_seconds)
            self._close_log(runtime)
            runtime.process = None
            runtime.state = "stopped"
            self._publish(runtime)

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "state": runtime.state,
                "pid": runtime.process.pid if runtime.process is not None else None,
                "managed": runtime.process is not None,
                "externally_managed": runtime.externally_managed,
                "port": runtime.spec.port,
                "restart_count": runtime.restart_count,
                "last_error": runtime.last_error,
            }
            for name, runtime in self._services.items()
        }

    def _start_or_adopt(self, runtime: ManagedService) -> None:
        if self._is_port_open(runtime.spec.port):
            runtime.externally_managed = True
            runtime.state = "external"
            runtime.last_error = None
            self._publish(runtime)
            return

        try:
            log_path = self._log_dir / f"{runtime.spec.name}.log"
            runtime.log_handle = log_path.open("ab", buffering=0)
            environment = dict(self._environment)
            environment.update(runtime.spec.environment)
            environment["PYTHONUNBUFFERED"] = "1"
            existing_pythonpath = environment.get("PYTHONPATH")
            environment["PYTHONPATH"] = (
                f"{self._project_root}{os.pathsep}{existing_pythonpath}"
                if existing_pythonpath
                else str(self._project_root)
            )
            runtime.process = self._popen_factory(
                list(runtime.spec.command),
                cwd=str(self._project_root),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=runtime.log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            runtime.externally_managed = False
            runtime.started_at = self._clock()
            runtime.state = "starting"
            runtime.last_error = None
        except OSError as exc:
            runtime.process = None
            self._close_log(runtime)
            runtime.state = "failed"
            runtime.last_error = str(exc)
            runtime.restart_count += 1
            runtime.next_restart_at = self._clock() + self._restart_delay(runtime.restart_count)
        self._publish(runtime)

    def _publish(self, runtime: ManagedService) -> None:
        self._status_callback(
            runtime.spec.name,
            {
                "state": runtime.state,
                "pid": runtime.process.pid if runtime.process is not None else None,
                "managed": runtime.process is not None,
                "externally_managed": runtime.externally_managed,
                "port": runtime.spec.port,
                "restart_count": runtime.restart_count,
                "last_error": runtime.last_error,
            },
        )

    def _restart_delay(self, restart_count: int) -> float:
        return min(
            self._restart_max_delay_seconds,
            self._restart_base_delay_seconds * (2 ** max(0, restart_count - 1)),
        )

    @staticmethod
    def _is_port_open(port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return True
        except OSError:
            return False

    def _is_ready(self, spec: ServiceSpec) -> bool:
        if not self._is_port_open(spec.port):
            return False
        if not spec.health_url:
            return True
        try:
            with urllib.request.urlopen(spec.health_url, timeout=0.75) as response:
                return 200 <= response.status < 500
        except (OSError, urllib.error.URLError, ValueError):
            return False

    @staticmethod
    def _terminate_process_group(process: subprocess.Popen[bytes], timeout_seconds: float) -> None:
        if process.poll() is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.wait(timeout=5)
        except ProcessLookupError:
            return
        except OSError:
            # A child can exit between poll() and signal delivery.  It is
            # already gone, so there is nothing further to terminate.
            return

    @staticmethod
    def _close_log(runtime: ManagedService) -> None:
        if runtime.log_handle is not None:
            try:
                runtime.log_handle.close()
            finally:
                runtime.log_handle = None
