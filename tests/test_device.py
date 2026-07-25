"""
Unit tests for VEGAS Cross-Device Ecosystem and Phone Control Bridge.
"""

import pytest
from unittest.mock import patch
from vegas.tools.device import (
    list_connected_devices,
    execute_phone_command,
    send_phone_sms,
    make_phone_call,
    pair_wireless_device,
)

def test_list_connected_devices_empty():
    with patch("vegas.tools.device._run_adb_command") as mock_adb:
        mock_adb.return_value = (0, "List of devices attached\n\n")
        res = list_connected_devices()
        assert "No connected mobile devices detected" in res

def test_list_connected_devices_found():
    with patch("vegas.tools.device._run_adb_command") as mock_adb:
        def side_effect(args, **kwargs):
            if args == ["devices", "-l"]:
                return (0, "List of devices attached\nemulator-5554 device product:sdk_gphone64_arm64 model:Pixel_7_Pro transport_id:1\n")
            if "dumpsys" in args:
                return (0, "Current Battery Service state:\n  level: 95\n  status: 2\n")
            return (0, "")

        mock_adb.side_effect = side_effect
        res = list_connected_devices()
        assert "emulator-5554" in res
        assert "Pixel 7 Pro" in res
        assert "95%" in res

def test_pair_wireless_device_success():
    with patch("vegas.tools.device._run_adb_command") as mock_adb:
        mock_adb.return_value = (0, "connected to 192.168.1.50:5555")
        res = pair_wireless_device("192.168.1.50")
        assert "Successfully paired with phone" in res

def test_execute_phone_command_open_app():
    with patch("vegas.tools.device._run_adb_command") as mock_adb:
        mock_adb.return_value = (0, "Events injected: 1")
        res = execute_phone_command(action="open_app", target="youtube")
        assert "Opening app 'youtube'" in res
        assert "com.google.android.youtube" in res

def test_execute_phone_command_open_url():
    with patch("vegas.tools.device._run_adb_command") as mock_adb:
        mock_adb.return_value = (0, "Starting: Intent { act=android.intent.action.VIEW dat=https://wikipedia.org }")
        res = execute_phone_command(action="open_url", target="https://wikipedia.org")
        assert "Opening web page 'https://wikipedia.org'" in res

def test_execute_phone_command_open_map():
    with patch("vegas.tools.device._run_adb_command") as mock_adb:
        mock_adb.return_value = (0, "Starting: Intent { act=android.intent.action.VIEW dat=geo:0,0?q=Ramanagara }")
        res = execute_phone_command(action="open_map", target="Ramanagara")
        assert "Opening location 'Ramanagara' in Google Maps on your phone" in res

def test_execute_phone_command_media_control():
    with patch("vegas.tools.device._run_adb_command") as mock_adb:
        mock_adb.return_value = (0, "")
        res = execute_phone_command(action="media_control", target="play_pause")
        assert "Executed phone media control 'play_pause'" in res

def test_execute_phone_command_battery_status():
    with patch("vegas.tools.device._run_adb_command") as mock_adb:
        mock_adb.return_value = (0, "Current Battery Service state:\n  level: 88\n  status: 2\n  temperature: 295\n")
        res = execute_phone_command(action="battery_status")
        assert "88%" in res
        assert "29.5°C" in res

def test_safety_gating_sms_and_call():
    # Both send_phone_sms and make_phone_call should return safety confirmation prompt
    sms_res = send_phone_sms(number="+123456789", text="Hello")
    assert "VEGAS: This action requires your confirmation" in sms_res

    call_res = make_phone_call(number="+123456789")
    assert "VEGAS: This action requires your confirmation" in call_res
