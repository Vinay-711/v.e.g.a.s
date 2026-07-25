"""
Android Companion Hub for VEGAS AIOS.

Manages encrypted Wi-Fi WebSocket connections with Android Companion devices.
Tracks telemetry, syncs clipboard, mirrors notifications, buffers camera streams,
processes voice forwarding, handles file transfers, and syncs shared memory.
"""

from __future__ import annotations

import copy
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from vegas.core.memory import memory
from vegas.mobile.protocol import AuthSecurityManager, CompanionFrame, CompanionMessageType

_FILES_DIR = Path.home() / ".vegas" / "transfers"


class AndroidCompanionHub:
    """Thread-safe state hub for active Android Companion connections over Wi-Fi."""

    def __init__(self, secret_key: Optional[str] = None):
        self._lock = threading.RLock()
        self.security = AuthSecurityManager(secret_key=secret_key)

        self._active_connections: Dict[str, Any] = {}  # device_id -> ws
        self._telemetry: Dict[str, Any] = {
            "connected": False,
            "device_id": None,
            "device_name": None,
            "battery_level": None,
            "charging": False,
            "wifi_ssid": None,
            "storage_available_mb": None,
            "last_seen": None,
        }
        self._clipboard_content: str = ""
        self._notifications: List[Dict[str, Any]] = []
        self._latest_camera_frame: Optional[str] = None  # Base64 JPEG frame
        self._latest_voice_transcript: Optional[str] = None
        self._transferred_files: List[str] = []

    # ------------------------------------------------------------------
    # Connection Management
    # ------------------------------------------------------------------

    def register_connection(self, device_id: str, device_name: str, ws: Any) -> None:
        with self._lock:
            self._active_connections[device_id] = ws
            self._telemetry["connected"] = True
            self._telemetry["device_id"] = device_id
            self._telemetry["device_name"] = device_name
            self._telemetry["last_seen"] = datetime.now(timezone.utc).isoformat()

    def unregister_connection(self, device_id: str) -> None:
        with self._lock:
            self._active_connections.pop(device_id, None)
            if not self._active_connections:
                self._telemetry["connected"] = False

    def is_connected(self) -> bool:
        with self._lock:
            return self._telemetry.get("connected", False)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            snap = copy.deepcopy(self._telemetry)
            snap["notifications_count"] = len(self._notifications)
            snap["clipboard_synced"] = bool(self._clipboard_content)
            snap["camera_stream_active"] = self._latest_camera_frame is not None
            return snap

    # ------------------------------------------------------------------
    # Frame Processing
    # ------------------------------------------------------------------

    def process_incoming_frame(self, raw_frame: str) -> Dict[str, Any]:
        """Processes an incoming JSON frame from the companion phone."""
        try:
            frame = CompanionFrame.deserialize(raw_frame)
        except Exception as e:
            return {"status": "error", "message": f"Malformed frame: {str(e)}"}

        # Verify frame security signature
        if not self.security.verify_frame(frame):
            return {"status": "error", "message": "Invalid HMAC security signature"}

        msg_type = frame.msg_type
        payload = frame.payload

        if msg_type == CompanionMessageType.HANDSHAKE.value:
            dev_id = payload.get("device_id", frame.device_id)
            dev_name = payload.get("device_name", "Android Phone")
            self.register_connection(dev_id, dev_name, None)
            return {"status": "ok", "message": f"Handshake verified for {dev_name}"}

        elif msg_type == CompanionMessageType.TELEMETRY.value:
            self.update_telemetry(payload)
            return {"status": "ok", "message": "Telemetry updated"}

        elif msg_type == CompanionMessageType.CLIPBOARD_SYNC.value:
            text = payload.get("text", "")
            self.set_clipboard(text)
            return {"status": "ok", "message": f"Clipboard synced ({len(text)} chars)"}

        elif msg_type == CompanionMessageType.NOTIFICATION_SYNC.value:
            self.add_notification(payload)
            return {"status": "ok", "message": "Notification mirrored"}

        elif msg_type == CompanionMessageType.FILE_TRANSFER.value:
            filename = payload.get("filename", "file.bin")
            data_b64 = payload.get("data_b64", "")
            saved_path = self.save_transferred_file(filename, data_b64)
            return {"status": "ok", "message": f"File saved to {saved_path}"}

        elif msg_type == CompanionMessageType.CAMERA_STREAM.value:
            frame_b64 = payload.get("frame_b64", "")
            self.set_camera_frame(frame_b64)
            return {"status": "ok", "message": "Camera frame updated"}

        elif msg_type == CompanionMessageType.MIC_STREAM.value:
            transcript = payload.get("transcript", "")
            self.set_voice_transcript(transcript)
            return {"status": "ok", "message": "Voice forwarding updated"}

        elif msg_type == CompanionMessageType.SHARED_MEMORY.value:
            key = payload.get("key", "")
            val = payload.get("value")
            if key:
                memory.store_fact(f"phone:{key}", val)
            return {"status": "ok", "message": f"Shared memory synced key '{key}'"}

        elif msg_type == CompanionMessageType.REMOTE_COMMAND.value:
            cmd = payload.get("command", "")
            allowed, reason = self.security.check_security_policy(cmd)
            if not allowed:
                return {"status": "blocked", "message": reason}
            return {"status": "ok", "message": f"Remote command '{cmd}' approved for execution"}

        return {"status": "unknown_type", "message": f"Unhandled msg_type '{msg_type}'"}

    # ------------------------------------------------------------------
    # Telemetry & Feature Handlers
    # ------------------------------------------------------------------

    def update_telemetry(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._telemetry.update({
                "battery_level": payload.get("battery_level", self._telemetry.get("battery_level")),
                "charging": payload.get("charging", self._telemetry.get("charging")),
                "wifi_ssid": payload.get("wifi_ssid", self._telemetry.get("wifi_ssid")),
                "storage_available_mb": payload.get("storage_available_mb", self._telemetry.get("storage_available_mb")),
                "last_seen": datetime.now(timezone.utc).isoformat(),
            })

    def set_clipboard(self, text: str) -> None:
        with self._lock:
            self._clipboard_content = text
            memory.store_fact("phone_clipboard", text)

    def get_clipboard(self) -> str:
        with self._lock:
            return self._clipboard_content

    def add_notification(self, notif: Dict[str, Any]) -> None:
        with self._lock:
            item = {
                "id": notif.get("id", str(time.time())),
                "title": notif.get("title", "Android Notification"),
                "text": notif.get("text", ""),
                "app": notif.get("app", "Phone"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._notifications.append(item)
            if len(self._notifications) > 50:
                self._notifications.pop(0)

    def get_notifications(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._notifications)

    def set_camera_frame(self, frame_b64: str) -> None:
        with self._lock:
            self._latest_camera_frame = frame_b64

    def get_camera_frame(self) -> Optional[str]:
        with self._lock:
            return self._latest_camera_frame

    def set_voice_transcript(self, transcript: str) -> None:
        with self._lock:
            self._latest_voice_transcript = transcript
            memory.record_turn("user_phone_voice", transcript)

    def get_voice_transcript(self) -> Optional[str]:
        with self._lock:
            return self._latest_voice_transcript

    def save_transferred_file(self, filename: str, data_b64: str) -> str:
        import base64

        _FILES_DIR.mkdir(parents=True, exist_ok=True)
        target = _FILES_DIR / filename
        raw_bytes = base64.b64decode(data_b64) if data_b64 else b""
        target.write_bytes(raw_bytes)
        with self._lock:
            self._transferred_files.append(str(target))
        return str(target)


# Global singleton hub
companion_hub = AndroidCompanionHub()
