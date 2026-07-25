"""Conversation state machine connecting wake-word, STT, planning, and TTS."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from typing import Any

from .client import VoicePlannerClient
from .config import HEY_VEGAS, VoiceConfig
from .stt import FasterWhisperSpeechCapture
from .tts import MacOSSaySpeaker, SentenceChunker


VoiceStatusCallback = Callable[[str, dict[str, Any]], None]
WakeControl = Callable[[], None]


class VoiceSessionManager:
    """Run short, interruptible, multi-turn voice conversations.

    The daemon leaves Porcupine active while VEGAS is thinking or speaking. A
    repeated ``Hey Vegas`` immediately cancels the current synthesis/response
    and begins a new capture. During capture, Porcupine is paused so a single
    microphone device is never opened by two backends at once.
    """

    def __init__(
        self,
        config: VoiceConfig,
        *,
        status_callback: VoiceStatusCallback,
        pause_wake_word: WakeControl,
        resume_wake_word: WakeControl,
        capture: FasterWhisperSpeechCapture | None = None,
        speaker: MacOSSaySpeaker | None = None,
        planner_client: VoicePlannerClient | None = None,
    ) -> None:
        self.config = config
        self._status_callback = status_callback
        self._pause_wake_word = pause_wake_word
        self._resume_wake_word = resume_wake_word
        self._capture = capture or FasterWhisperSpeechCapture(config)
        self._speaker = speaker or MacOSSaySpeaker(config)
        self._planner_client = planner_client or VoicePlannerClient(config.api_url)
        self._active_task: asyncio.Task[None] | None = None
        self._restart_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._ready = False
        self._stopping = False
        self._interruption_count = 0
        self._conversation_id: str | None = None

    async def start(self) -> None:
        """Warm the local speech recognizer without blocking daemon startup."""
        if not self.config.enabled:
            self._status("disabled", detail="Voice interface is disabled by configuration.")
            return
        error = self.config.validation_error()
        if error:
            self._status("unavailable", detail=error)
            return
        try:
            await asyncio.to_thread(self._capture.prepare)
        except Exception as exc:
            self._status("unavailable", detail=f"Offline speech-to-text could not start: {exc}")
            return

        self._ready = True
        output_detail = "macOS speech output ready" if self._speaker.available else "Speech output unavailable on this host"
        self._status(
            "idle",
            detail=f"Ready for '{HEY_VEGAS}'. {output_detail}.",
            stt_backend=self._capture.backend_name,
            tts_backend="macos-say" if self._speaker.available else None,
            wake_phrase=HEY_VEGAS,
        )

    async def handle_wake_word(self) -> None:
        """Start a new session or barge into a currently spoken response."""
        if not self._ready or self._stopping:
            return

        async with self._lock:
            active = self._active_task
            if active is not None and not active.done():
                if self._restart_task is not None and not self._restart_task.done():
                    return
                self._interruption_count += 1
                self._status(
                    "interrupted",
                    detail=f"'{HEY_VEGAS}' interrupted the active response.",
                    interruption_count=self._interruption_count,
                )
                self._capture.cancel()
                await self._speaker.interrupt()
                self._restart_task = asyncio.create_task(
                    self._restart_after(active, self._conversation_id), name="vegas-voice-restart"
                )
                active.cancel()
                return

            self._conversation_id = str(uuid.uuid4())
            self._active_task = asyncio.create_task(
                self._run_conversation(self._conversation_id), name="vegas-voice-session"
            )

    async def stop(self) -> None:
        """Cancel capture, streaming request, and synthesis during daemon shutdown."""
        self._stopping = True
        self._capture.cancel()
        await self._speaker.interrupt()
        tasks = [task for task in (self._active_task, self._restart_task) if task is not None and not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await self._speaker.close()
        await asyncio.to_thread(self._capture.close)
        self._status("stopped", detail="Voice interface stopped.")

    async def _restart_after(self, active: asyncio.Task[None], conversation_id: str | None) -> None:
        await asyncio.gather(active, return_exceptions=True)
        if self._stopping or not self._ready:
            return
        async with self._lock:
            if self._active_task is None or self._active_task is active or self._active_task.done():
                self._conversation_id = conversation_id or str(uuid.uuid4())
                self._restart_task = None
                self._active_task = asyncio.create_task(
                    self._run_conversation(self._conversation_id), name="vegas-voice-session"
                )

    async def _run_conversation(self, conversation_id: str) -> None:
        try:
            for turn in range(self.config.max_continuous_turns):
                timeout = (
                    self.config.activation_timeout_seconds
                    if turn == 0
                    else self.config.continuation_seconds
                )
                transcript = await self._listen(timeout, conversation_id, continuation=turn > 0)
                if not transcript:
                    break
                await self._execute_turn(transcript, conversation_id, turn + 1)
        except asyncio.CancelledError:
            await self._speaker.interrupt()
            raise
        except Exception as exc:
            self._status("error", detail=f"Voice session failed: {exc}")
        finally:
            self._resume_wake_word()
            if not self._stopping:
                self._status("idle", detail=f"Ready for '{HEY_VEGAS}'.", conversation_active=False)
            current = asyncio.current_task()
            async with self._lock:
                if self._active_task is current:
                    self._active_task = None
                    if self._restart_task is None:
                        self._conversation_id = None

    async def _listen(self, timeout_seconds: float, conversation_id: str, *, continuation: bool) -> str | None:
        self._pause_wake_word()
        self._status(
            "listening",
            detail="Listening for a follow-up." if continuation else "Listening for your request.",
            conversation_id=conversation_id,
            conversation_active=True,
            partial_transcript="",
        )

        def on_partial(text: str) -> None:
            self._status(
                "listening",
                partial_transcript=text,
                conversation_id=conversation_id,
                conversation_active=True,
            )

        try:
            transcript = await asyncio.to_thread(
                self._capture.capture_utterance,
                activation_timeout_seconds=timeout_seconds,
                on_partial=on_partial,
            )
        finally:
            self._resume_wake_word()

        if transcript:
            self._status(
                "transcribed",
                transcript=transcript,
                partial_transcript="",
                conversation_id=conversation_id,
                conversation_active=True,
            )
        return transcript

    async def _execute_turn(self, transcript: str, conversation_id: str, turn: int) -> None:
        self._status(
            "planning",
            detail="Passing the spoken request to the planner.",
            transcript=transcript,
            conversation_id=conversation_id,
            turn=turn,
            conversation_active=True,
            response_text="",
        )
        chunker = SentenceChunker()
        streamed_text = ""
        final_text = ""
        async for event in self._planner_client.stream_command(transcript, conversation_id):
            event_type = event.get("type")
            if event_type == "plan":
                payload = event.get("payload")
                self._status(
                    "planning",
                    detail="Planner accepted the spoken request.",
                    planner=payload if isinstance(payload, dict) else None,
                    conversation_active=True,
                )
            elif event_type == "delta":
                text = event.get("text")
                if not isinstance(text, str) or not text:
                    continue
                streamed_text += text
                self._status(
                    "speaking",
                    response_text=streamed_text[-800:],
                    conversation_active=True,
                )
                for sentence in chunker.push(text):
                    await self._speaker.enqueue(sentence)
            elif event_type == "final":
                value = event.get("text")
                final_text = value if isinstance(value, str) else streamed_text
            elif event_type == "error":
                detail = str(event.get("detail", "Voice execution failed."))
                self._status("error", detail=detail, conversation_active=True)
                await self._speaker.enqueue("I ran into a problem while processing that request.")
                return

        if not streamed_text and final_text:
            streamed_text = final_text
            for sentence in chunker.push(final_text):
                await self._speaker.enqueue(sentence)
        for sentence in chunker.flush():
            await self._speaker.enqueue(sentence)
        if streamed_text:
            self._status("speaking", response_text=streamed_text[-800:], conversation_active=True)
        await self._speaker.drain()

    def _status(self, state: str, **values: Any) -> None:
        values.setdefault("interruption_count", self._interruption_count)
        self._status_callback(state, values)
