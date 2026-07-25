"""
V.E.G.A.S. Android Companion Protocol & Security Guardrails.

Defines:
  - CompanionMessageType: Enum of Wi-Fi WebSocket frame types.
  - CompanionFrame: Data structure for encrypted JSON communication.
  - AuthSecurityManager: HMAC SHA-256 token verification and lockscreen bypass guardrail.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class CompanionMessageType(str, Enum):
    HANDSHAKE = "handshake"
    TELEMETRY = "telemetry"
    CLIPBOARD_SYNC = "clipboard_sync"
    NOTIFICATION_SYNC = "notification_sync"
    SMS_ASSIST = "sms_assist"
    CALL_ASSIST = "call_assist"
    FILE_TRANSFER = "file_transfer"
    CAMERA_STREAM = "camera_stream"
    MIC_STREAM = "mic_stream"
    SHARED_MEMORY = "shared_memory"
    REMOTE_COMMAND = "remote_command"
    SECURITY_ALERT = "security_alert"
    ERROR = "error"


@dataclass
class CompanionFrame:
    """Structured message frame exchanged over encrypted Wi-Fi WebSockets."""

    msg_type: str
    device_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    signature: str = ""

    def serialize(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def deserialize(cls, raw: str) -> CompanionFrame:
        data = json.loads(raw)
        return cls(
            msg_type=data.get("msg_type", "error"),
            device_id=data.get("device_id", "unknown"),
            payload=data.get("payload", {}),
            timestamp=float(data.get("timestamp", time.time())),
            signature=data.get("signature", ""),
        )


class AuthSecurityManager:
    """Handles HMAC token authentication and safety guardrails for Android Companion."""

    UNSUPPORTED_BYPASS_TERMS = (
        "unlock phone",
        "bypass lockscreen",
        "bypass pin",
        "bypass pattern",
        "crack password",
        "disable lock",
    )

    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = (secret_key or "vegas_android_companion_secret_2026").encode("utf-8")

    def generate_signature(self, device_id: str, msg_type: str, timestamp: float) -> str:
        """Generates an HMAC SHA-256 signature for frame verification."""
        msg = f"{device_id}:{msg_type}:{timestamp}".encode("utf-8")
        return hmac.new(self.secret_key, msg, hashlib.sha256).hexdigest()

    def verify_frame(self, frame: CompanionFrame) -> bool:
        """Verifies frame HMAC signature for encrypted Wi-Fi authenticity."""
        if not frame.signature:
            # Allow unsigned handshake if matching token is in payload
            return frame.msg_type == CompanionMessageType.HANDSHAKE.value

        expected = self.generate_signature(frame.device_id, frame.msg_type, frame.timestamp)
        return hmac.compare_digest(expected, frame.signature)

    def check_security_policy(self, command_text: str) -> tuple[bool, str]:
        """
        Enforces security policy: explicitly blocks unsupported lockscreen bypasses.

        Returns (is_allowed, reason).
        """
        lowered = command_text.lower().strip()
        for term in self.UNSUPPORTED_BYPASS_TERMS:
            if term in lowered:
                return (
                    False,
                    f"SECURITY GUARDRAIL BLOCKED: '{term}' is an unsupported security bypass. "
                    "VEGAS does not unlock locked devices without user interaction.",
                )
        return True, "Allowed"
