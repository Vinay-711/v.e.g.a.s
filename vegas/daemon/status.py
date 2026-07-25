"""Status models shared by the daemon and the FastAPI dashboard adapter."""

from __future__ import annotations

import copy
import json
import threading
import time
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    """Return an RFC 3339 timestamp suitable for dashboard payloads."""
    return datetime.now(timezone.utc).isoformat()


class DaemonStatus:
    """Thread-safe, serialisable status owned by one daemon process.

    Wake-word audio callbacks run on a PortAudio thread while service
    supervision runs on the asyncio loop.  A small lock keeps dashboard
    snapshots consistent without introducing a polling thread.
    """

    def __init__(self, *, version: str = "0.1.0") -> None:
        self._lock = threading.RLock()
        self._payload: dict[str, Any] = {
            "state": "starting",
            "version": version,
            "started_at": utc_now(),
            "last_heartbeat": None,
            "services": {},
            "wake_word": {
                "state": "initializing",
                "backend": None,
                "detections": 0,
                "last_detected_at": None,
                "detail": None,
            },
            "voice": {
                "state": "initializing",
                "stt_backend": None,
                "tts_backend": None,
                "wake_phrase": "Hey Vegas",
                "conversation_active": False,
                "partial_transcript": "",
                "transcript": None,
                "response_text": "",
                "interruption_count": 0,
                "detail": None,
            },
            "websocket": {
                "state": "connecting",
                "reconnect_attempts": 0,
                "last_connected_at": None,
                "last_error": None,
            },
            "recent_events": [],
        }

    def set_state(self, state: str, *, detail: str | None = None) -> None:
        with self._lock:
            self._payload["state"] = state
            if detail is not None:
                self._payload["detail"] = detail
            self._touch_locked()

    def update_service(self, name: str, **values: Any) -> None:
        with self._lock:
            service = self._payload["services"].setdefault(name, {})
            service.update(values)
            service["updated_at"] = utc_now()
            self._touch_locked()

    def update_wake_word(
        self,
        state: str,
        *,
        backend: str | None = None,
        detail: str | None = None,
    ) -> None:
        with self._lock:
            wake_word = self._payload["wake_word"]
            wake_word["state"] = state
            if backend is not None:
                wake_word["backend"] = backend
            wake_word["detail"] = detail
            self._touch_locked()

    def note_wake_word(self) -> None:
        with self._lock:
            wake_word = self._payload["wake_word"]
            wake_word["detections"] += 1
            wake_word["last_detected_at"] = utc_now()
            wake_word["state"] = "detected"
            self._append_event_locked("wake_word_detected", "Wake word detected")
            self._touch_locked()

    def update_voice(self, state: str, **values: Any) -> None:
        """Record streaming voice session state for FastAPI and the dashboard."""
        with self._lock:
            voice = self._payload["voice"]
            voice["state"] = state
            voice.update(values)
            voice["updated_at"] = utc_now()
            self._touch_locked()

    def set_websocket(
        self,
        state: str,
        *,
        reconnect_attempts: int | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            websocket = self._payload["websocket"]
            websocket["state"] = state
            if reconnect_attempts is not None:
                websocket["reconnect_attempts"] = reconnect_attempts
            if state == "connected":
                websocket["last_connected_at"] = utc_now()
                websocket["last_error"] = None
            elif error is not None:
                websocket["last_error"] = error[:500]
            self._touch_locked()

    def add_event(self, kind: str, message: str) -> None:
        with self._lock:
            self._append_event_locked(kind, message)
            self._touch_locked()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            payload = copy.deepcopy(self._payload)
            payload["last_heartbeat"] = utc_now()
            return payload

    def _touch_locked(self) -> None:
        self._payload["updated_at"] = utc_now()

    def _append_event_locked(self, kind: str, message: str) -> None:
        events: list[dict[str, str]] = self._payload["recent_events"]
        events.append({"kind": kind, "message": message, "timestamp": utc_now()})
        del events[:-20]


class DashboardStatusHub:
    """In-process status hub used by FastAPI websocket and REST endpoints.

    The daemon reconnects to this hub after FastAPI restarts.  Dashboard
    clients receive the last status immediately and later status changes as
    websocket messages.  The REST snapshot remains available to existing
    polling dashboards.
    """

    def __init__(self, *, stale_after_seconds: float = 20.0) -> None:
        self._lock = threading.RLock()
        self._snapshot: dict[str, Any] = {
            "state": "offline",
            "services": {},
            "wake_word": {"state": "unknown", "detections": 0},
            "voice": {"state": "unknown", "conversation_active": False},
            "websocket": {"state": "disconnected", "reconnect_attempts": 0},
            "recent_events": [],
        }
        self._last_update_monotonic: float | None = None
        self._stale_after_seconds = stale_after_seconds
        self._subscribers: set[Any] = set()

    async def update(self, payload: dict[str, Any]) -> None:
        """Replace the current snapshot and fan it out to dashboard clients."""
        clean_payload = self._json_safe(payload)
        with self._lock:
            self._snapshot = clean_payload
            self._last_update_monotonic = time.monotonic()
            snapshot = self._snapshot_locked()
        await self._broadcast(snapshot)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._snapshot_locked()

    async def add_dashboard(self, websocket: Any) -> None:
        await websocket.accept()
        with self._lock:
            self._subscribers.add(websocket)
            snapshot = self._snapshot_locked()
        await websocket.send_json({"type": "daemon_status", "payload": snapshot})

    def remove_dashboard(self, websocket: Any) -> None:
        with self._lock:
            self._subscribers.discard(websocket)

    async def _broadcast(self, snapshot: dict[str, Any]) -> None:
        with self._lock:
            subscribers = list(self._subscribers)

        failed: list[Any] = []
        for websocket in subscribers:
            try:
                await websocket.send_json({"type": "daemon_status", "payload": snapshot})
            except Exception:
                failed.append(websocket)

        if failed:
            with self._lock:
                for websocket in failed:
                    self._subscribers.discard(websocket)

    def _snapshot_locked(self) -> dict[str, Any]:
        snapshot = copy.deepcopy(self._snapshot)
        if self._last_update_monotonic is None:
            snapshot["stale"] = True
            return snapshot

        age = max(0.0, time.monotonic() - self._last_update_monotonic)
        snapshot["age_seconds"] = round(age, 1)
        snapshot["stale"] = age > self._stale_after_seconds
        if snapshot["stale"] and snapshot.get("state") not in {"stopping", "stopped"}:
            snapshot["state"] = "offline"
        return snapshot

    @staticmethod
    def _json_safe(payload: dict[str, Any]) -> dict[str, Any]:
        """Detach caller-owned objects and guarantee a JSON websocket payload."""
        encoded = json.dumps(payload, default=str, ensure_ascii=False)
        decoded = json.loads(encoded)
        if not isinstance(decoded, dict):
            raise ValueError("Daemon status payload must be a JSON object.")
        return decoded
