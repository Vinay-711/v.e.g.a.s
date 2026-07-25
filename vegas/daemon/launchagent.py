"""macOS LaunchAgent installation for the user-scoped VEGAS daemon."""

from __future__ import annotations

import os
import platform
import plistlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


LAUNCH_AGENT_LABEL = "com.vegas.daemon"


@dataclass(frozen=True)
class LaunchAgentPaths:
    project_root: Path
    plist_path: Path
    log_dir: Path


class MacOSLaunchAgent:
    """Install and control a LaunchAgent without requiring root privileges.

    A LaunchAgent is deliberately used instead of a system LaunchDaemon: macOS
    microphone and Accessibility permissions belong to the signed-in user, not
    root. `RunAtLoad` starts it at login and `SuccessfulExit=false` restarts
    crashes while allowing an intentional graceful exit to remain stopped.
    """

    def __init__(self, project_root: Path) -> None:
        self.paths = LaunchAgentPaths(
            project_root=project_root.resolve(),
            plist_path=Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist",
            log_dir=Path.home() / "Library" / "Logs" / "VEGAS",
        )

    def plist_payload(self, *, python_executable: Path | None = None) -> dict[str, object]:
        # Preserve a virtualenv interpreter path. Resolving its symlink would
        # make LaunchAgent run the base Python without project dependencies.
        executable = (python_executable or Path(sys.executable)).absolute()
        stdout_path = self.paths.log_dir / "daemon.log"
        stderr_path = self.paths.log_dir / "daemon.error.log"
        return {
            "Label": LAUNCH_AGENT_LABEL,
            "ProgramArguments": [
                str(executable),
                "-m",
                "vegas.daemon",
                "run",
                "--project-root",
                str(self.paths.project_root),
            ],
            "WorkingDirectory": str(self.paths.project_root),
            "RunAtLoad": True,
            "KeepAlive": {"SuccessfulExit": False},
            "ThrottleInterval": 10,
            "ProcessType": "Background",
            "StandardOutPath": str(stdout_path),
            "StandardErrorPath": str(stderr_path),
            "EnvironmentVariables": {
                "VEGAS_PROJECT_ROOT": str(self.paths.project_root),
                "PYTHONUNBUFFERED": "1",
            },
        }

    def install(self, *, start: bool = True, python_executable: Path | None = None) -> Path:
        self._require_macos()
        self.paths.plist_path.parent.mkdir(parents=True, exist_ok=True)
        self.paths.log_dir.mkdir(parents=True, exist_ok=True)
        with self.paths.plist_path.open("wb") as stream:
            plistlib.dump(self.plist_payload(python_executable=python_executable), stream, sort_keys=False)
        os.chmod(self.paths.plist_path, 0o600)

        if start:
            self.start()
        return self.paths.plist_path

    def uninstall(self) -> None:
        self._require_macos()
        self.stop(ignore_missing=True)
        try:
            self.paths.plist_path.unlink()
        except FileNotFoundError:
            return

    def start(self) -> None:
        self._require_macos()
        if not self.paths.plist_path.is_file():
            raise FileNotFoundError(f"LaunchAgent is not installed: {self.paths.plist_path}")
        self.stop(ignore_missing=True)
        self._run_launchctl("bootstrap", self._domain(), str(self.paths.plist_path))

    def stop(self, *, ignore_missing: bool = False) -> None:
        self._require_macos()
        result = subprocess.run(
            ["launchctl", "bootout", self._domain(), str(self.paths.plist_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 and not ignore_missing:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"Could not stop {LAUNCH_AGENT_LABEL}: {detail}")

    def status(self) -> str:
        self._require_macos()
        result = subprocess.run(
            ["launchctl", "print", f"{self._domain()}/{LAUNCH_AGENT_LABEL}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout
        return result.stderr.strip() or "not loaded"

    @staticmethod
    def _run_launchctl(*args: str) -> None:
        result = subprocess.run(["launchctl", *args], capture_output=True, text=True, check=False)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"launchctl {' '.join(args)} failed: {detail}")

    @staticmethod
    def _domain() -> str:
        return f"gui/{os.getuid()}"

    @staticmethod
    def _require_macos() -> None:
        if platform.system() != "Darwin":
            raise RuntimeError("The VEGAS LaunchAgent is available only on macOS.")
