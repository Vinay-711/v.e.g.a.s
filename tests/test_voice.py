"""Focused tests for the additive VEGAS voice interface."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from pathlib import Path

from vegas.voice.config import HEY_VEGAS, VoiceConfig
from vegas.voice.session import VoiceSessionManager
from vegas.voice.tts import SentenceChunker


def _voice_config(model_path: Path, **overrides) -> VoiceConfig:
    values = {
        "enabled": True,
        "whisper_model": str(model_path),
        "whisper_device": "cpu",
        "whisper_compute_type": "int8",
        "whisper_language": "en",
        "api_url": "http://127.0.0.1:8001/api/voice/stream",
        "input_device": None,
        "sample_rate": 16000,
        "speech_threshold": 350,
        "silence_seconds": 0.8,
        "activation_timeout_seconds": 0.01,
        "continuation_seconds": 0.01,
        "max_utterance_seconds": 30.0,
        "min_speech_seconds": 0.25,
        "max_continuous_turns": 3,
        "tts_enabled": True,
        "tts_voice": "Samantha",
        "tts_rate": 205,
    }
    values.update(overrides)
    return VoiceConfig(**values)


def test_voice_config_uses_fixed_hey_vegas_phrase(tmp_path: Path) -> None:
    config = _voice_config(tmp_path)

    assert HEY_VEGAS == "Hey Vegas"
    assert config.validation_error() is None


def test_sentence_chunker_starts_speech_before_the_full_response_arrives() -> None:
    chunker = SentenceChunker(max_characters=30)

    assert chunker.push("Hello there. I can") == ["Hello there."]
    assert chunker.push(" help with that now.") == ["I can help with that now."]
    assert chunker.flush() == []


def test_voice_session_streams_response_and_keeps_one_follow_up_turn(tmp_path: Path) -> None:
    class FakeCapture:
        backend_name = "fake-stt"

        def __init__(self) -> None:
            self.results = deque(["open the calculator", None])
            self.prepared = False
            self.cancelled = 0
            self.closed = False

        def prepare(self) -> None:
            self.prepared = True

        def capture_utterance(self, *, activation_timeout_seconds: float, on_partial):
            result = self.results.popleft()
            if result:
                on_partial(result[:8])
            return result

        def cancel(self) -> None:
            self.cancelled += 1

        def close(self) -> None:
            self.closed = True

    class FakeSpeaker:
        available = True

        def __init__(self) -> None:
            self.spoken: list[str] = []
            self.interrupts = 0

        async def enqueue(self, text: str) -> None:
            self.spoken.append(text)

        async def drain(self) -> None:
            return None

        async def interrupt(self) -> None:
            self.interrupts += 1

        async def close(self) -> None:
            return None

    class FakePlanner:
        async def stream_command(self, transcript: str, conversation_id: str):
            yield {"type": "plan", "payload": {"action": "complete"}}
            yield {"type": "delta", "text": "Opening "}
            yield {"type": "delta", "text": "Calculator."}
            yield {"type": "final", "text": "Opening Calculator."}

    updates: list[tuple[str, dict]] = []
    pause_count = 0
    resume_count = 0

    def pause() -> None:
        nonlocal pause_count
        pause_count += 1

    def resume() -> None:
        nonlocal resume_count
        resume_count += 1

    capture = FakeCapture()
    speaker = FakeSpeaker()
    manager = VoiceSessionManager(
        _voice_config(tmp_path),
        status_callback=lambda state, values: updates.append((state, values)),
        pause_wake_word=pause,
        resume_wake_word=resume,
        capture=capture,  # type: ignore[arg-type]
        speaker=speaker,  # type: ignore[arg-type]
        planner_client=FakePlanner(),  # type: ignore[arg-type]
    )

    async def scenario() -> None:
        await manager.start()
        await manager.handle_wake_word()
        for _ in range(20):
            if any(state == "speaking" for state, _ in updates) and updates[-1][0] == "idle":
                break
            await asyncio.sleep(0.01)
        await manager.stop()

    asyncio.run(scenario())

    assert capture.prepared and capture.closed
    assert pause_count == 2 and resume_count >= 2
    assert speaker.spoken == ["Opening Calculator."]
    assert any(state == "planning" for state, _ in updates)
    assert any(state == "speaking" for state, _ in updates)


def test_repeated_wake_phrase_interrupts_active_voice_response(tmp_path: Path) -> None:
    class FakeCapture:
        backend_name = "fake-stt"

        def __init__(self) -> None:
            self.results = deque(["first request", "second request", None])
            self.cancelled = 0

        def prepare(self) -> None:
            return None

        def capture_utterance(self, *, activation_timeout_seconds: float, on_partial):
            result = self.results.popleft()
            if result:
                on_partial(result)
            return result

        def cancel(self) -> None:
            self.cancelled += 1

        def close(self) -> None:
            return None

    class FakeSpeaker:
        available = True

        def __init__(self) -> None:
            self.interrupts = 0

        async def enqueue(self, text: str) -> None:
            return None

        async def drain(self) -> None:
            return None

        async def interrupt(self) -> None:
            self.interrupts += 1

        async def close(self) -> None:
            return None

    class SlowPlanner:
        def __init__(self) -> None:
            self.requests: list[str] = []

        async def stream_command(self, transcript: str, conversation_id: str):
            self.requests.append(transcript)
            yield {"type": "delta", "text": f"Working on {transcript}."}
            if transcript == "first request":
                await asyncio.sleep(60)
            yield {"type": "final", "text": f"Working on {transcript}."}

    updates: list[tuple[str, dict]] = []
    capture = FakeCapture()
    speaker = FakeSpeaker()
    planner = SlowPlanner()
    manager = VoiceSessionManager(
        _voice_config(tmp_path),
        status_callback=lambda state, values: updates.append((state, values)),
        pause_wake_word=lambda: None,
        resume_wake_word=lambda: None,
        capture=capture,  # type: ignore[arg-type]
        speaker=speaker,  # type: ignore[arg-type]
        planner_client=planner,  # type: ignore[arg-type]
    )

    async def scenario() -> None:
        await manager.start()
        await manager.handle_wake_word()
        await asyncio.sleep(0.03)
        await manager.handle_wake_word()
        for _ in range(50):
            if "second request" in planner.requests and updates and updates[-1][0] == "idle":
                break
            await asyncio.sleep(0.01)
        await manager.stop()

    asyncio.run(scenario())

    assert planner.requests == ["first request", "second request"]
    assert speaker.interrupts >= 1
    assert capture.cancelled >= 1
    assert any(state == "interrupted" for state, _ in updates)


def test_api_voice_stream_plans_and_emits_response_deltas(monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

    class FakeChat:
        def send_message_stream(self, prompt: str):
            assert "voice" in prompt.lower()
            yield FakeResponse("Good ")
            yield FakeResponse("morning.")

    class FakeChats:
        def create(self, **_kwargs):
            return FakeChat()

    class FakeClient:
        chats = FakeChats()

    class FakeKernel:
        def process_system_command(self, message: str):
            return {"action": "complete", "response": message}

    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    import api

    monkeypatch.setattr(api, "client", FakeClient())
    monkeypatch.setattr(api, "kernel", FakeKernel())
    with api.chat_sessions_lock:
        api.chat_sessions.clear()

    events = [
        json.loads(line)
        for line in api._stream_voice_command(api.VoiceCommandRequest(message="say hello", conversation_id="voice-test"))
    ]

    assert [event["type"] for event in events] == ["plan", "delta", "delta", "final"]
    assert events[-1]["text"] == "Good morning."
