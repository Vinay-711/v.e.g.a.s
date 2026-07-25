"""
Phone Agent for VEGAS AIOS.

Owns mobile device ecosystem: ADB mobile control, encrypted Wi-Fi Android Companion,
telemetry, clipboard sync, camera streaming, voice forwarding, notifications, SMS, calls, and shared memory.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from vegas.agents.base import AgentResult, BaseAgent
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
from vegas.tools.device import (
    execute_phone_command,
    list_connected_devices,
    make_phone_call,
    pair_wireless_device,
    send_phone_sms,
)


class PhoneAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Phone Agent",
            role="phone",
            description="Manages Android ecosystem via ADB & encrypted Wi-Fi Companion: telemetry, battery, clipboard, files, camera stream, voice mic forwarding, notifications, SMS, calls, and shared memory.",
        )
        # ADB Tools
        self.register_tool("list_connected_devices", list_connected_devices)
        self.register_tool("execute_phone_command", execute_phone_command)
        self.register_tool("send_phone_sms", send_phone_sms)
        self.register_tool("make_phone_call", make_phone_call)
        self.register_tool("pair_wireless_device", pair_wireless_device)

        # Encrypted Wi-Fi Companion Tools
        self.register_tool("get_companion_telemetry", get_companion_telemetry)
        self.register_tool("sync_phone_clipboard", sync_phone_clipboard)
        self.register_tool("transfer_phone_file", transfer_phone_file)
        self.register_tool("capture_companion_camera_frame", capture_companion_camera_frame)
        self.register_tool("forward_phone_voice", forward_phone_voice)
        self.register_tool("sync_phone_shared_memory", sync_phone_shared_memory)
        self.register_tool("send_companion_sms", send_companion_sms)
        self.register_tool("make_companion_call", make_companion_call)

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        start_time = time.time()
        ctx = context or {}
        lowered = task.lower()
        device_id = ctx.get("device_id")

        try:
            if "telemetry" in lowered or "battery" in lowered or "wifi" in lowered:
                output = self.tools["get_companion_telemetry"]()
            elif "camera" in lowered or "snapshot" in lowered or "camera stream" in lowered:
                output = self.tools["capture_companion_camera_frame"]()
            elif "mic" in lowered or "voice" in lowered or "forward voice" in lowered:
                text = ctx.get("text")
                output = self.tools["forward_phone_voice"](text=text)
            elif "clipboard" in lowered:
                text = ctx.get("text")
                output = self.tools["sync_phone_clipboard"](text=text)
            elif "transfer" in lowered or "file" in lowered:
                path = ctx.get("file_path", "data.bin")
                direction = ctx.get("direction", "download")
                output = self.tools["transfer_phone_file"](file_path=path, direction=direction)
            elif "memory" in lowered:
                key = ctx.get("key", "status")
                val = ctx.get("value")
                output = self.tools["sync_phone_shared_memory"](key=key, value=val)
            elif "sms" in lowered or "text" in lowered:
                number = ctx.get("number", "1234567890")
                text = ctx.get("text", task)
                output = self.tools["send_companion_sms"](number=number, text=text)
            elif "call" in lowered or "dial" in lowered:
                number = ctx.get("number", "1234567890")
                output = self.tools["make_companion_call"](number=number)
            elif "pair" in lowered or "wireless" in lowered:
                ip = ctx.get("ip_address", "192.168.1.100")
                port = int(ctx.get("port", 5555))
                output = self.tools["pair_wireless_device"](ip_address=ip, port=port)
            elif "list" in lowered or "devices" in lowered:
                output = self.tools["list_connected_devices"]()
            else:
                action = ctx.get("action", "home")
                output = self.tools["execute_phone_command"](action=action, device_id=device_id)

            duration = (time.time() - start_time) * 1000
            status = "failed" if "error" in output.lower() or "failed" in output.lower() else "success"

            if "requires your confirmation" in output.lower():
                status = "blocked"

            return AgentResult(
                agent_role=self.role,
                status=status,
                result=output,
                duration_ms=duration,
            )
        except Exception as e:
            return AgentResult(
                agent_role=self.role,
                status="failed",
                result=f"PhoneAgent execution error: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
            )
