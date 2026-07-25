"""
Unit tests for V.E.G.A.S. Android Companion protocol, security guardrails, hub, and tools.
"""

import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from vegas.mobile.companion import AndroidCompanionHub, companion_hub
from vegas.mobile.protocol import AuthSecurityManager, CompanionFrame, CompanionMessageType
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


# ---------------------------------------------------------------------------
# 1. Protocol & HMAC Security Tests
# ---------------------------------------------------------------------------

def test_auth_security_manager_generates_and_verifies_signature():
    sec = AuthSecurityManager(secret_key="test_secret_key")
    sig = sec.generate_signature("device123", "telemetry", 1000.0)

    frame = CompanionFrame(
        msg_type="telemetry",
        device_id="device123",
        payload={"battery_level": 88},
        timestamp=1000.0,
        signature=sig,
    )

    assert sec.verify_frame(frame) is True


def test_auth_security_manager_rejects_invalid_signature():
    sec = AuthSecurityManager(secret_key="test_secret_key")
    frame = CompanionFrame(
        msg_type="telemetry",
        device_id="device123",
        payload={"battery_level": 88},
        timestamp=1000.0,
        signature="invalid_fake_signature",
    )

    assert sec.verify_frame(frame) is False


def test_security_policy_blocks_unsupported_lockscreen_bypass():
    sec = AuthSecurityManager()

    allowed_1, reason_1 = sec.check_security_policy("Check battery status")
    assert allowed_1 is True

    allowed_2, reason_2 = sec.check_security_policy("Unlock phone bypassing PIN")
    assert allowed_2 is False
    assert "SECURITY GUARDRAIL BLOCKED" in reason_2
    assert "unsupported security bypass" in reason_2


# ---------------------------------------------------------------------------
# 2. Android Companion Hub Tests
# ---------------------------------------------------------------------------

def test_companion_hub_handshake_and_telemetry():
    hub = AndroidCompanionHub(secret_key="test_secret")

    # Handshake
    handshake_frame = CompanionFrame(
        msg_type=CompanionMessageType.HANDSHAKE.value,
        device_id="phone_001",
        payload={"device_id": "phone_001", "device_name": "Galaxy S24"},
    ).serialize()

    res1 = hub.process_incoming_frame(handshake_frame)
    assert res1["status"] == "ok"
    assert hub.is_connected() is True

    # Telemetry
    sig = hub.security.generate_signature("phone_001", CompanionMessageType.TELEMETRY.value, 2000.0)
    telemetry_frame = CompanionFrame(
        msg_type=CompanionMessageType.TELEMETRY.value,
        device_id="phone_001",
        payload={"battery_level": 92, "charging": True, "wifi_ssid": "VegasHomeWiFi"},
        timestamp=2000.0,
        signature=sig,
    ).serialize()

    res2 = hub.process_incoming_frame(telemetry_frame)
    assert res2["status"] == "ok"

    status = hub.get_status()
    assert status["battery_level"] == 92
    assert status["charging"] is True
    assert status["wifi_ssid"] == "VegasHomeWiFi"


def test_companion_hub_clipboard_and_notifications():
    hub = AndroidCompanionHub(secret_key="test_secret")
    hub.register_connection("phone_001", "Pixel 8", None)

    # Clipboard sync
    sig1 = hub.security.generate_signature("phone_001", CompanionMessageType.CLIPBOARD_SYNC.value, 2000.0)
    clip_frame = CompanionFrame(
        msg_type=CompanionMessageType.CLIPBOARD_SYNC.value,
        device_id="phone_001",
        payload={"text": "Phone OTP Code 4921"},
        timestamp=2000.0,
        signature=sig1,
    ).serialize()

    hub.process_incoming_frame(clip_frame)
    assert hub.get_clipboard() == "Phone OTP Code 4921"

    # Notification mirroring
    sig2 = hub.security.generate_signature("phone_001", CompanionMessageType.NOTIFICATION_SYNC.value, 2000.0)
    notif_frame = CompanionFrame(
        msg_type=CompanionMessageType.NOTIFICATION_SYNC.value,
        device_id="phone_001",
        payload={"title": "WhatsApp Message", "text": "Meeting at 5 PM", "app": "WhatsApp"},
        timestamp=2000.0,
        signature=sig2,
    ).serialize()

    hub.process_incoming_frame(notif_frame)
    notifs = hub.get_notifications()
    assert len(notifs) == 1
    assert notifs[0]["title"] == "WhatsApp Message"


def test_companion_hub_rejects_lockscreen_remote_command():
    hub = AndroidCompanionHub(secret_key="test_secret")
    hub.register_connection("phone_001", "Pixel 8", None)

    sig = hub.security.generate_signature("phone_001", CompanionMessageType.REMOTE_COMMAND.value, 2000.0)
    cmd_frame = CompanionFrame(
        msg_type=CompanionMessageType.REMOTE_COMMAND.value,
        device_id="phone_001",
        payload={"command": "bypass lockscreen pin"},
        timestamp=2000.0,
        signature=sig,
    ).serialize()

    res = hub.process_incoming_frame(cmd_frame)
    assert res["status"] == "blocked"
    assert "SECURITY GUARDRAIL BLOCKED" in res["message"]


# ---------------------------------------------------------------------------
# 3. Companion Tools Tests
# ---------------------------------------------------------------------------

def test_companion_tools_when_disconnected():
    companion_hub._telemetry["connected"] = False

    res = get_companion_telemetry()
    assert "No Android phone connected over Wi-Fi" in res


def test_companion_tools_when_connected():
    companion_hub.register_connection("test_dev", "Android Test Phone", None)
    companion_hub.update_telemetry({"battery_level": 77, "wifi_ssid": "VegasWiFi"})

    telemetry_res = get_companion_telemetry()
    assert "77%" in telemetry_res
    assert "VegasWiFi" in telemetry_res

    # Clipboard tool
    clip_res = sync_phone_clipboard("Copied from Laptop")
    assert "Pushed text" in clip_res

    # Voice forwarding
    voice_res = forward_phone_voice("Turn on living room lights")
    assert "mic transcript" in voice_res.lower()


def test_companion_sms_and_call_require_confirmation():
    companion_hub.register_connection("test_dev", "Android Test Phone", None)

    sms_res = send_companion_sms("1234567890", "Hello via Wi-Fi")
    assert "requires your confirmation" in sms_res.lower()

    call_res = make_companion_call("1234567890")
    assert "requires your confirmation" in call_res.lower()


# ---------------------------------------------------------------------------
# 4. API Endpoints Tests
# ---------------------------------------------------------------------------

def test_api_companion_status_endpoint():
    import api

    client = TestClient(api.app)

    companion_hub.register_connection("dev_api", "Pixel 9", None)
    companion_hub.update_telemetry({"battery_level": 95, "wifi_ssid": "ApiWiFi"})

    res = client.get("/api/companion/status")
    assert res.status_code == 200
    data = res.json()
    assert data["connected"] is True
    assert data["battery_level"] == 95
    assert data["wifi_ssid"] == "ApiWiFi"
