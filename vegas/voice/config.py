"""Configuration for VEGAS's local, always-on voice interface."""

from __future__ import annotations

import os
from dataclasses import dataclass


HEY_VEGAS = "Hey Vegas"


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return min(maximum, max(minimum, value))


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return min(maximum, max(minimum, value))


@dataclass(frozen=True)
class VoiceConfig:
    """Explicit, local-only settings for voice capture, STT, and TTS.

    faster-whisper is deliberately used for speech-to-text because it runs
    locally on Apple Silicon and can load a cached CTranslate2 model from the
    Mac. The wake phrase is fixed to ``Hey Vegas``; the Porcupine ``.ppn``
    configured for the daemon must be trained for that phrase.
    """

    enabled: bool
    whisper_model: str | None
    whisper_device: str
    whisper_compute_type: str
    whisper_language: str | None
    api_url: str
    input_device: str | int | None
    sample_rate: int
    speech_threshold: int
    silence_seconds: float
    activation_timeout_seconds: float
    continuation_seconds: float
    max_utterance_seconds: float
    min_speech_seconds: float
    max_continuous_turns: int
    tts_enabled: bool
    tts_voice: str
    tts_rate: int

    @classmethod
    def from_environment(cls, *, api_host: str = "127.0.0.1", api_port: int = 8001) -> "VoiceConfig":
        raw_device = os.getenv("VEGAS_VOICE_INPUT_DEVICE")
        device: str | int | None = raw_device
        if raw_device and raw_device.isdigit():
            device = int(raw_device)

        whisper_model = os.getenv("VEGAS_WHISPER_MODEL") or None
        return cls(
            enabled=_env_flag("VEGAS_VOICE_ENABLED", True),
            whisper_model=whisper_model,
            whisper_device=os.getenv("VEGAS_WHISPER_DEVICE", "auto"),
            whisper_compute_type=os.getenv("VEGAS_WHISPER_COMPUTE_TYPE", "int8"),
            whisper_language=os.getenv("VEGAS_WHISPER_LANGUAGE", "en") or None,
            api_url=os.getenv("VEGAS_VOICE_API_URL", f"http://{api_host}:{api_port}/api/voice/stream"),
            input_device=device,
            sample_rate=_env_int("VEGAS_VOICE_SAMPLE_RATE", 16000, minimum=8000, maximum=48000),
            speech_threshold=_env_int("VEGAS_VOICE_SPEECH_THRESHOLD", 350, minimum=20, maximum=30000),
            silence_seconds=_env_float("VEGAS_VOICE_SILENCE_SECONDS", 0.8, minimum=0.2, maximum=5.0),
            activation_timeout_seconds=_env_float(
                "VEGAS_VOICE_ACTIVATION_TIMEOUT_SECONDS", 7.0, minimum=1.0, maximum=30.0
            ),
            continuation_seconds=_env_float(
                "VEGAS_VOICE_CONTINUATION_SECONDS", 12.0, minimum=2.0, maximum=60.0
            ),
            max_utterance_seconds=_env_float(
                "VEGAS_VOICE_MAX_UTTERANCE_SECONDS", 30.0, minimum=3.0, maximum=120.0
            ),
            min_speech_seconds=_env_float(
                "VEGAS_VOICE_MIN_SPEECH_SECONDS", 0.25, minimum=0.05, maximum=3.0
            ),
            max_continuous_turns=_env_int("VEGAS_VOICE_MAX_CONTINUOUS_TURNS", 5, minimum=1, maximum=20),
            tts_enabled=_env_flag("VEGAS_VOICE_TTS_ENABLED", True),
            tts_voice=os.getenv("VEGAS_VOICE_TTS_VOICE", "Samantha"),
            tts_rate=_env_int("VEGAS_VOICE_TTS_RATE", 205, minimum=80, maximum=450),
        )

    def validation_error(self) -> str | None:
        if not self.enabled:
            return None
        if not self.whisper_model:
            return "VEGAS_WHISPER_MODEL must name a cached model or local faster-whisper model directory."
        if not self.api_url.startswith(("http://", "https://")):
            return "VEGAS_VOICE_API_URL must use http:// or https://."
        return None
