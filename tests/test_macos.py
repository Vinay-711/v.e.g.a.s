"""
Unit tests for native macOS Computer Control tools and ComputerAgent integration.
"""

from unittest.mock import MagicMock, patch

import pytest

from vegas.agents.computer import ComputerAgent
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


# ---------------------------------------------------------------------------
# 1. macOS Native Control Tools Tests
# ---------------------------------------------------------------------------

def test_launch_application_success(monkeypatch):
    monkeypatch.setattr("vegas.tools.macos._run_cmd", lambda cmd, **kw: (0, "ok", ""))
    res = launch_application("Safari")
    assert "Successfully launched" in res
    assert "Safari" in res


def test_focus_window_success(monkeypatch):
    monkeypatch.setattr("vegas.tools.macos._run_cmd", lambda cmd, **kw: (0, "ok", ""))
    res = focus_window("Terminal")
    assert "Focused window" in res
    assert "Terminal" in res


def test_quit_application_requires_confirmation():
    # Calling quit_application directly without confirmation should park the task
    res = quit_application("Music")
    assert "requires your confirmation" in res.lower()
    assert "quit_application" in res


def test_take_screenshot(tmp_path, monkeypatch):
    target = tmp_path / "test_shot.png"

    def mock_run(cmd, **kw):
        # Simulate screencapture creating file
        target.write_bytes(b"fake_png_data")
        return (0, "", "")

    monkeypatch.setattr("vegas.tools.macos._run_cmd", mock_run)
    res = take_screenshot(str(target))
    assert "Screenshot saved to" in res
    assert target.exists()


def test_manage_clipboard_get_set(monkeypatch):
    clip_store = {"content": "hello vegas"}

    def mock_run(cmd, **kw):
        if cmd[0] == "pbpaste":
            return (0, clip_store["content"], "")
        return (0, "", "")

    monkeypatch.setattr("vegas.tools.macos._run_cmd", mock_run)

    # Test GET
    get_res = manage_clipboard(action="get")
    assert "hello vegas" in get_res

    # Test SET
    set_res = manage_clipboard(action="set", text="new item")
    assert "Copied" in set_res


def test_send_system_notification(monkeypatch):
    monkeypatch.setattr("vegas.tools.macos._run_cmd", lambda cmd, **kw: (0, "", ""))
    res = send_system_notification("VEGAS Alert", "Build completed")
    assert "Notification sent" in res
    assert "VEGAS Alert" in res


def test_open_in_finder(tmp_path, monkeypatch):
    test_dir = tmp_path / "my_folder"
    test_dir.mkdir()

    monkeypatch.setattr("vegas.tools.macos._run_cmd", lambda cmd, **kw: (0, "", ""))
    res = open_in_finder(str(test_dir), reveal=True)
    assert "Revealed" in res
    assert "my_folder" in res


def test_open_system_settings(monkeypatch):
    monkeypatch.setattr("vegas.tools.macos._run_cmd", lambda cmd, **kw: (0, "", ""))
    res = open_system_settings(pane="wifi")
    assert "Opened System Settings" in res
    assert "wifi" in res


def test_get_battery_status(monkeypatch):
    monkeypatch.setattr("vegas.tools.macos._run_cmd", lambda cmd, **kw: (0, "InternalBattery-0 85%; discharging", ""))
    res = get_battery_status()
    assert "Battery Telemetry" in res
    assert "85%" in res


def test_get_wifi_status(monkeypatch):
    monkeypatch.setattr("vegas.tools.macos._run_cmd", lambda cmd, **kw: (0, "Current Wi-Fi Network: VegasWiFi", ""))
    res = get_wifi_status()
    assert "VegasWiFi" in res


def test_get_bluetooth_status(monkeypatch):
    monkeypatch.setattr("vegas.tools.macos._run_cmd", lambda cmd, **kw: (0, "Bluetooth:\n  State: On", ""))
    res = get_bluetooth_status()
    assert "Bluetooth Status" in res


def test_set_display_brightness(monkeypatch):
    monkeypatch.setattr("vegas.tools.macos._run_cmd", lambda cmd, **kw: (0, "", ""))
    res = set_display_brightness(75)
    assert "75%" in res


# ---------------------------------------------------------------------------
# 2. Computer Agent Integration Tests
# ---------------------------------------------------------------------------

def test_computer_agent_registers_all_macos_tools():
    agent = ComputerAgent()
    expected_tools = [
        "run_command", "get_system_info", "get_current_time",
        "launch_application", "quit_application", "focus_window",
        "take_screenshot", "manage_clipboard", "send_system_notification",
        "open_in_finder", "open_system_settings", "get_battery_status",
        "get_wifi_status", "get_bluetooth_status", "set_display_brightness",
        "set_system_volume", "play_music", "speak_text",
    ]
    for tool_name in expected_tools:
        assert tool_name in agent.tools, f"Tool '{tool_name}' missing from ComputerAgent."


def test_computer_agent_executes_screenshot(monkeypatch):
    agent = ComputerAgent()
    monkeypatch.setattr("vegas.tools.macos._run_cmd", lambda cmd, **kw: (0, "", ""))
    with patch("pathlib.Path.exists", return_value=True):
        res = agent.execute("Take a screenshot of my screen")
        assert res.status == "success"


def test_computer_agent_executes_battery_check(monkeypatch):
    agent = ComputerAgent()
    monkeypatch.setattr("vegas.tools.macos._run_cmd", lambda cmd, **kw: (0, "85%; discharging", ""))
    res = agent.execute("Check battery status")
    assert res.status == "success"
    assert "85%" in res.result


def test_computer_agent_executes_launch_app(monkeypatch):
    agent = ComputerAgent()
    monkeypatch.setattr("vegas.tools.macos._run_cmd", lambda cmd, **kw: (0, "ok", ""))
    res = agent.execute("Launch application Calculator")
    assert res.status == "success"
    assert "Calculator" in res.result


def test_computer_agent_handles_confirmation_gated_quit():
    agent = ComputerAgent()
    res = agent.execute("Quit application Safari")
    assert res.status == "blocked"
    assert "requires your confirmation" in res.result.lower()
