"""
Computer Agent for VEGAS AIOS.

Owns native macOS computer control: application lifecycle (launch/quit/focus),
terminal commands, screenshots, system clipboard, notifications, Finder operations,
System Settings, battery/Wi-Fi/Bluetooth telemetry, volume, and display brightness.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, Optional

from vegas.agents.base import AgentResult, BaseAgent
from vegas.tools.developer import run_command
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
from vegas.tools.media import play_music, set_system_volume, speak_text
from vegas.tools.system import get_current_time, get_system_info


class ComputerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Computer Agent",
            role="computer",
            description="Controls native macOS desktop: app launch/quit/focus, shell commands, screenshots, clipboard, notifications, Finder, Settings, battery, Wi-Fi, Bluetooth, volume, and brightness.",
        )
        # System & Shell
        self.register_tool("run_command", run_command)
        self.register_tool("get_system_info", get_system_info)
        self.register_tool("get_current_time", get_current_time)

        # macOS Desktop Control
        self.register_tool("launch_application", launch_application)
        self.register_tool("quit_application", quit_application)
        self.register_tool("focus_window", focus_window)
        self.register_tool("take_screenshot", take_screenshot)
        self.register_tool("manage_clipboard", manage_clipboard)
        self.register_tool("send_system_notification", send_system_notification)
        self.register_tool("open_in_finder", open_in_finder)
        self.register_tool("open_system_settings", open_system_settings)

        # Hardware Telemetry & Media
        self.register_tool("get_battery_status", get_battery_status)
        self.register_tool("get_wifi_status", get_wifi_status)
        self.register_tool("get_bluetooth_status", get_bluetooth_status)
        self.register_tool("set_display_brightness", set_display_brightness)
        self.register_tool("set_system_volume", set_system_volume)
        self.register_tool("play_music", play_music)
        self.register_tool("speak_text", speak_text)

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        start_time = time.time()
        ctx = context or {}
        lowered = task.lower().strip()

        try:
            # 1. Screenshot
            if "screenshot" in lowered or "screen capture" in lowered:
                out_path = ctx.get("output_path")
                output = self.tools["take_screenshot"](output_path=out_path)

            # 2. Battery telemetry
            elif "battery" in lowered or "charge" in lowered or "power state" in lowered:
                output = self.tools["get_battery_status"]()

            # 3. Wi-Fi status
            elif "wifi" in lowered or "wi-fi" in lowered or "network status" in lowered:
                output = self.tools["get_wifi_status"]()

            # 4. Bluetooth status
            elif "bluetooth" in lowered or "bt status" in lowered:
                output = self.tools["get_bluetooth_status"]()

            # 5. Clipboard operations
            elif "clipboard" in lowered or "copy to clipboard" in lowered or "paste" in lowered:
                action = ctx.get("action", "set" if "copy" in lowered else "get")
                text = ctx.get("text", task if action == "set" else None)
                output = self.tools["manage_clipboard"](action=action, text=text)

            # 6. Notification
            elif "notify" in lowered or "notification" in lowered or "alert user" in lowered:
                title = ctx.get("title", "V.E.G.A.S.")
                msg = ctx.get("message", task)
                output = self.tools["send_system_notification"](title=title, message=msg)

            # 7. System Settings
            elif "settings" in lowered or "preferences" in lowered:
                pane = ctx.get("pane")
                output = self.tools["open_system_settings"](pane=pane)

            # 8. Finder integration
            elif "finder" in lowered or "reveal in finder" in lowered or "open folder" in lowered:
                path = ctx.get("path", ".")
                reveal = ctx.get("reveal", True)
                output = self.tools["open_in_finder"](path=path, reveal=reveal)

            # 9. App Quit / Close
            elif "quit app" in lowered or "close app" in lowered or "quit " in lowered or "close " in lowered:
                app_name = ctx.get("app_name") or self._extract_app_name(task, ["quit", "close", "stop"])
                force = bool(ctx.get("force", False))
                output = self.tools["quit_application"](app_name=app_name, force=force)

            # 10. App Focus / Switch Window
            elif "focus" in lowered or "switch window" in lowered or "bring to front" in lowered:
                app_name = ctx.get("app_name") or self._extract_app_name(task, ["focus", "switch", "bring to front"])
                output = self.tools["focus_window"](app_name=app_name)

            # 11. App Launch / Open
            elif "launch" in lowered or "open app" in lowered or "open application" in lowered or "start " in lowered:
                app_name = ctx.get("app_name") or self._extract_app_name(task, ["launch", "open", "start"])
                output = self.tools["launch_application"](app_name=app_name)

            # 12. Volume / Brightness / Info / Shell
            elif "brightness" in lowered:
                level = int(ctx.get("level", 80))
                output = self.tools["set_display_brightness"](level=level)
            elif "volume" in lowered:
                level = int(ctx.get("level", 50))
                output = self.tools["set_system_volume"](level)
            elif "time" in lowered or "date" in lowered or "clock" in lowered:
                output = self.tools["get_current_time"]()
            elif "system info" in lowered or "specs" in lowered or "memory" in lowered or "cpu" in lowered:
                output = self.tools["get_system_info"]()
            elif "play" in lowered or "music" in lowered:
                output = self.tools["play_music"](task)
            elif self.role in {"reporting", "safety"} or "summary" in lowered or "recommend next steps" in lowered:
                output = f"📊 [{self.role.upper()} AGENT]: Task step execution completed successfully."
            else:
                cwd = ctx.get("cwd", ".")
                output = self.tools["run_command"](task, cwd=cwd)

            duration = (time.time() - start_time) * 1000
            status = "failed" if "failed" in output.lower() or "error" in output.lower() else "success"

            # Check confirmation gate response
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
                result=f"ComputerAgent execution error: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
            )

    def _extract_app_name(self, task: str, action_words: list[str]) -> str:
        """Extract application name from natural language prompt."""
        text = task
        for word in action_words:
            pattern = re.compile(rf"\b{word}\b\s+(?:application\s+|app\s+)?([A-Za-z0-9\s]+)", re.IGNORECASE)
            match = pattern.search(text)
            if match:
                return match.group(1).strip()
        # Fallback to simple clean string
        return text.replace("launch", "").replace("open", "").replace("quit", "").replace("close", "").replace("app", "").strip() or "Safari"
