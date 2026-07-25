"""
Native macOS Computer Control tools for VEGAS AIOS.

Uses native macOS APIs and system CLI tools:
  - AppleScript / osascript (App launch, quit, focus, notifications, brightness)
  - screencapture (Desktop screenshots)
  - pbcopy / pbpaste (Clipboard get/set)
  - open / Finder integration
  - pmset, networksetup, system_profiler (Battery, Wi-Fi, Bluetooth telemetry)
"""

from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from vegas.safety import requires_confirmation

_SCREENSHOTS_DIR = Path.home() / ".vegas" / "screenshots"


def _run_cmd(cmd: list[str] | str, timeout: int = 10, shell: bool = False) -> tuple[int, str, str]:
    """Helper to execute system command and return (code, stdout, stderr)."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=shell)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return -1, "", str(e)


def launch_application(app_name: str) -> str:
    """
    Launches or opens a macOS application by name.

    Args:
        app_name: Name of the application (e.g., 'Safari', 'Terminal', 'System Settings', 'Calculator').
    """
    code, out, err = _run_cmd(["open", "-a", app_name])
    if code == 0:
        return f"Successfully launched application '{app_name}'."

    # Fallback to osascript
    script = f'tell application "{app_name}" to activate'
    code_osa, out_osa, err_osa = _run_cmd(["osascript", "-e", script])
    if code_osa == 0:
        return f"Successfully activated application '{app_name}'."
    return f"Failed to launch '{app_name}': {err or err_osa or 'Application not found'}"


@requires_confirmation
def quit_application(app_name: str, force: bool = False) -> str:
    """
    Quits or closes a running macOS application.
    Requires user confirmation before execution for system safety.

    Args:
        app_name: Name of the application to quit (e.g., 'Safari', 'Music').
        force: If True, force-kills the process using pkill.
    """
    if force:
        code, out, err = _run_cmd(["pkill", "-9", "-f", app_name])
        if code == 0:
            return f"Force-closed application matching '{app_name}'."
        return f"Failed to force-close '{app_name}': {err or 'Process not found'}"

    script = f'tell application "{app_name}" to quit'
    code, out, err = _run_cmd(["osascript", "-e", script])
    if code == 0:
        return f"Quit application '{app_name}' successfully."
    return f"Failed to quit '{app_name}': {err or 'App may not be running'}"


def focus_window(app_name: str) -> str:
    """
    Brings an open application window to the foreground on macOS.

    Args:
        app_name: Name of the application window to focus.
    """
    script = f'tell application "{app_name}" to activate'
    code, out, err = _run_cmd(["osascript", "-e", script])
    if code == 0:
        return f"Focused window for application '{app_name}'."
    return f"Failed to focus window for '{app_name}': {err}"


def take_screenshot(output_path: Optional[str] = None) -> str:
    """
    Captures a full screenshot of the macOS desktop.

    Args:
        output_path: Optional file path. Defaults to ~/.vegas/screenshots/screenshot_<timestamp>.png.
    """
    _SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    if not output_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = _SCREENSHOTS_DIR / f"screenshot_{ts}.png"
    else:
        target = Path(output_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

    code, out, err = _run_cmd(["screencapture", "-x", str(target)])
    if code == 0 and target.exists():
        return f"Screenshot saved to: {target}"
    return f"Failed to capture screenshot: {err or 'screencapture returned non-zero exit code'}"


def manage_clipboard(action: str = "get", text: Optional[str] = None) -> str:
    """
    Reads from or writes text to the macOS system clipboard using pbcopy/pbpaste.

    Args:
        action: 'get' to read clipboard, 'set' to copy text to clipboard.
        text: Text string to copy when action is 'set'.
    """
    act = action.lower().strip()
    if act == "get":
        code, out, err = _run_cmd(["pbpaste"])
        if code == 0:
            return f"Clipboard contents:\n{out}" if out else "(Clipboard is empty)"
        return f"Failed to read clipboard: {err}"

    if act == "set":
        if text is None:
            return "Error: Must provide 'text' argument when action='set'."
        try:
            proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
            proc.communicate(input=text, timeout=5)
            return f"Copied {len(text)} character(s) to system clipboard."
        except Exception as e:
            return f"Failed to set clipboard: {str(e)}"

    return f"Unknown clipboard action '{action}'. Supported values: 'get', 'set'."


def send_system_notification(title: str, message: str) -> str:
    """
    Displays a native macOS system banner notification.

    Args:
        title: Title header for the notification.
        message: Body text for the notification.
    """
    safe_title = title.replace('"', '\\"')
    safe_msg = message.replace('"', '\\"')
    script = f'display notification "{safe_msg}" with title "{safe_title}"'
    code, out, err = _run_cmd(["osascript", "-e", script])
    if code == 0:
        return f"Notification sent: [{title}] {message}"
    return f"Failed to send notification: {err}"


def open_in_finder(path: str = ".", reveal: bool = True) -> str:
    """
    Opens a file or directory in Finder on macOS.

    Args:
        path: Absolute or relative path to file or directory.
        reveal: If True, reveals the file inside Finder. If False, opens it directly.
    """
    target = Path(path).expanduser().resolve()
    if not target.exists():
        return f"Error: Path '{path}' does not exist."

    cmd = ["open", "-R", str(target)] if reveal else ["open", str(target)]
    code, out, err = _run_cmd(cmd)
    if code == 0:
        verb = "Revealed" if reveal else "Opened"
        return f"{verb} '{target.name}' in Finder."
    return f"Failed to open in Finder: {err}"


def open_system_settings(pane: Optional[str] = None) -> str:
    """
    Opens System Settings (formerly System Preferences) on macOS.

    Args:
        pane: Optional pane name ('displays', 'sound', 'wifi', 'bluetooth', 'battery', 'network').
    """
    pane_map = {
        "displays": "x-apple.systempreferences:com.apple.preference.displays",
        "sound": "x-apple.systempreferences:com.apple.preference.sound",
        "wifi": "x-apple.systempreferences:com.apple.netpref",
        "bluetooth": "x-apple.systempreferences:com.apple.preferences.Bluetooth",
        "battery": "x-apple.systempreferences:com.apple.preference.battery",
        "network": "x-apple.systempreferences:com.apple.preference.network",
    }
    target_url = pane_map.get((pane or "").lower(), "x-apple.systempreferences:")
    code, out, err = _run_cmd(["open", target_url])
    if code == 0:
        return f"Opened System Settings (pane: '{pane or 'main'}')."
    return f"Failed to open System Settings: {err}"


def get_battery_status() -> str:
    """
    Retrieves macOS battery telemetry (percentage, charging state, remaining time).
    """
    code, out, err = _run_cmd(["pmset", "-g", "batt"])
    if code == 0 and out:
        return f"Battery Telemetry:\n{out}"
    return f"Failed to query battery telemetry: {err or 'pmset unavailable'}"


def get_wifi_status() -> str:
    """
    Retrieves current macOS Wi-Fi connection details and active network SSID.
    """
    # Attempt networksetup
    code, out, err = _run_cmd(["networksetup", "-getairportnetwork", "en0"])
    if code == 0 and out:
        return f"Wi-Fi Status:\n{out}"

    # Fallback to ifconfig
    code2, out2, err2 = _run_cmd(["ifconfig", "en0"])
    if code2 == 0 and out2:
        ssid_match = re.search(r"status: (\w+)", out2)
        status_str = ssid_match.group(1) if ssid_match else "unknown"
        return f"Wi-Fi Hardware (en0) status: {status_str}"

    return "Wi-Fi status could not be retrieved."


def get_bluetooth_status() -> str:
    """
    Queries macOS Bluetooth controller power state and connected devices.
    """
    code, out, err = _run_cmd(["system_profiler", "SPBluetoothDataType"], timeout=10)
    if code == 0 and out:
        # Extract power state and connected devices for a concise summary
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        relevant = [line for line in lines if any(k in line.lower() for k in ("state:", "power:", "connected:", "devices"))]
        summary = "\n".join(relevant[:10]) if relevant else out[:500]
        return f"Bluetooth Status:\n{summary}"
    return f"Failed to query Bluetooth status: {err}"


def set_display_brightness(level: int) -> str:
    """
    Sets macOS display brightness (0 to 100%).

    Args:
        level: Target brightness level percentage (0 - 100).
    """
    target_pct = max(0, min(100, int(level)))
    # Try brightness CLI tool if installed
    code, out, err = _run_cmd(["brightness", str(target_pct / 100.0)])
    if code == 0:
        return f"Display brightness set to {target_pct}%."

    # AppleScript key code fallback simulation
    return f"Display brightness requested: {target_pct}%. (For precise hardware control, install 'brightness' via brew install brightness)."


def register(mcp) -> None:
    """Registers native macOS control tools with FastMCP."""
    mcp.tool()(launch_application)
    mcp.tool()(quit_application)
    mcp.tool()(focus_window)
    mcp.tool()(take_screenshot)
    mcp.tool()(manage_clipboard)
    mcp.tool()(send_system_notification)
    mcp.tool()(open_in_finder)
    mcp.tool()(open_system_settings)
    mcp.tool()(get_battery_status)
    mcp.tool()(get_wifi_status)
    mcp.tool()(get_bluetooth_status)
    mcp.tool()(set_display_brightness)
