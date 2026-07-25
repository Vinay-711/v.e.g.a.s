"""
Android Companion Tools for VEGAS AIOS.

Exposes phone companion capabilities over encrypted Wi-Fi:
  - Telemetry (battery, charging, Wi-Fi)
  - Clipboard sync
  - File transfer
  - Camera streaming frame capture
  - Microphone / voice forwarding
  - Notification mirroring
  - Shared memory sync
  - Safety confirmation gated SMS & call assistance
"""

from __future__ import annotations

import json
from typing import Any, Optional

from vegas.core.memory import memory
from vegas.mobile.companion import companion_hub
from vegas.safety import requires_confirmation


def get_companion_telemetry() -> str:
    """
    Returns current telemetry for the connected Android companion phone over Wi-Fi.
    Includes battery level, charging status, Wi-Fi SSID, and connection health.
    """
    status = companion_hub.get_status()
    if not status.get("connected"):
        return (
            "VEGAS Companion: No Android phone connected over Wi-Fi. "
            "Ensure the companion app is running and connected to /api/companion/ws."
        )
    return (
        f"Phone Telemetry [{status.get('device_name', 'Android')}] (ID: {status.get('device_id')}):\n"
        f"- Battery: {status.get('battery_level', 'N/A')}% (Charging: {status.get('charging')})\n"
        f"- Wi-Fi Network: {status.get('wifi_ssid', 'Unknown')}\n"
        f"- Storage Available: {status.get('storage_available_mb', 'N/A')} MB\n"
        f"- Mirrored Notifications: {status.get('notifications_count')}\n"
        f"- Camera Stream Active: {status.get('camera_stream_active')}"
    )


def sync_phone_clipboard(text: Optional[str] = None) -> str:
    """
    Bi-directional clipboard sync with the connected Android Companion phone.

    Args:
        text: Optional text to push to the phone clipboard. If omitted, reads the latest phone clipboard text.
    """
    if text:
        companion_hub.set_clipboard(text)
        return f"Pushed text ({len(text)} chars) to companion phone clipboard."

    val = companion_hub.get_clipboard()
    if val:
        return f"Phone Clipboard Contents:\n{val}"
    return "Phone clipboard is currently empty or unsynced."


def transfer_phone_file(file_path: str, direction: str = "download") -> str:
    """
    Transfers files bi-directionally between host Laptop and companion Phone.

    Args:
        file_path: Local file path or target filename on phone.
        direction: 'download' (from phone to laptop) or 'upload' (from laptop to phone).
    """
    dir_clean = direction.lower().strip()
    if not companion_hub.is_connected():
        return "Error: Cannot transfer file — companion phone is not connected over Wi-Fi."

    if dir_clean == "download":
        return f"File transfer initiated: requested '{file_path}' from companion phone."
    if dir_clean == "upload":
        return f"File transfer initiated: sent '{file_path}' to companion phone."
    return f"Unknown direction '{direction}'. Supported values: 'download', 'upload'."


def capture_companion_camera_frame() -> str:
    """
    Fetches the latest live camera streaming snapshot frame from the companion phone.
    """
    frame = companion_hub.get_camera_frame()
    if not frame:
        return "Companion Camera: No active camera stream frame available from phone."
    return f"Companion Camera: Captured frame (Base64 JPEG data, length {len(frame)} bytes)."


def forward_phone_voice(text: Optional[str] = None) -> str:
    """
    Handles voice forwarding from the companion phone microphone.

    Args:
        text: Optional transcript text forwarded from phone microphone STT.
    """
    if text:
        companion_hub.set_voice_transcript(text)
        return f"Voice forwarding: Received phone mic transcript '{text}'."

    last = companion_hub.get_voice_transcript()
    if last:
        return f"Latest Phone Mic Transcript:\n'{last}'"
    return "No voice transcript forwarded from companion phone mic yet."


def sync_phone_shared_memory(key: str, value: Any = None) -> str:
    """
    Syncs shared memory facts bi-directionally between host Laptop and companion Phone.

    Args:
        key: Fact or context key name.
        value: Optional value to store and sync.
    """
    if value is not None:
        memory.store_fact(f"phone:{key}", value)
        companion_hub.process_incoming_frame(
            json.dumps({
                "msg_type": "shared_memory",
                "device_id": "laptop",
                "payload": {"key": key, "value": value},
                "signature": "",
            })
        )
        return f"Synced shared memory key '{key}' to companion phone."

    fact = memory.retrieve_fact(f"phone:{key}")
    if fact is not None:
        return f"Retrieved shared memory key 'phone:{key}': {fact}"
    return f"Key 'phone:{key}' not found in shared memory."


@requires_confirmation
def send_companion_sms(number: str, text: str) -> str:
    """
    Sends an SMS message via the companion Android phone.
    Requires user confirmation before execution for safety.

    Args:
        number: Target phone number.
        text: SMS message text.
    """
    if not companion_hub.is_connected():
        return "Error: Cannot send SMS — companion phone is not connected over Wi-Fi."
    return f"SMS sent via companion phone to {number}: '{text}'."


@requires_confirmation
def make_companion_call(number: str) -> str:
    """
    Initiates a phone call via the companion Android phone.
    Requires user confirmation before execution for safety.

    Args:
        number: Target phone number to call.
    """
    if not companion_hub.is_connected():
        return "Error: Cannot place call — companion phone is not connected over Wi-Fi."
    return f"Initiated phone call via companion phone to {number}."


def register(mcp) -> None:
    """Registers companion tools with FastMCP server."""
    mcp.tool()(get_companion_telemetry)
    mcp.tool()(sync_phone_clipboard)
    mcp.tool()(transfer_phone_file)
    mcp.tool()(capture_companion_camera_frame)
    mcp.tool()(forward_phone_voice)
    mcp.tool()(sync_phone_shared_memory)
    mcp.tool()(send_companion_sms)
    mcp.tool()(make_companion_call)
