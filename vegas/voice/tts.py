"""Interruptible, sentence-buffered macOS text-to-speech output."""

from __future__ import annotations

import asyncio
import os
import re
import signal
import subprocess
import sys
from collections import deque

from .config import VoiceConfig


class SentenceChunker:
    """Turn LLM token deltas into natural chunks that can be spoken early."""

    _boundary = re.compile(r"(?<=[.!?])(?:[\]\)\"']+)?(?=\s|$)")

    def __init__(self, *, max_characters: int = 180) -> None:
        self._buffer = ""
        self._max_characters = max_characters

    def push(self, delta: str) -> list[str]:
        self._buffer += delta
        chunks: list[str] = []
        last_end = 0
        for match in self._boundary.finditer(self._buffer):
            candidate = self._clean(self._buffer[last_end : match.end()])
            if candidate:
                chunks.append(candidate)
            last_end = match.end()
        if last_end:
            self._buffer = self._buffer[last_end:].lstrip()

        # Do not hold a long run-on answer indefinitely just because the model
        # has not emitted punctuation yet. Split at the latest word boundary.
        if len(self._buffer) >= self._max_characters:
            boundary = self._buffer.rfind(" ", 0, self._max_characters)
            boundary = boundary if boundary > 40 else self._max_characters
            candidate = self._clean(self._buffer[:boundary])
            self._buffer = self._buffer[boundary:].lstrip()
            if candidate:
                chunks.append(candidate)
        return chunks

    def flush(self) -> list[str]:
        candidate = self._clean(self._buffer)
        self._buffer = ""
        return [candidate] if candidate else []

    @staticmethod
    def _clean(text: str) -> str:
        # TTS should not read Markdown syntax or empty whitespace aloud.
        clean = re.sub(r"`([^`]*)`", r"\1", text)
        clean = re.sub(r"[*_#]", "", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean


class MacOSSaySpeaker:
    """Queue short spoken chunks and stop them immediately on interruption."""

    def __init__(self, config: VoiceConfig) -> None:
        self._config = config
        self._queue: asyncio.Queue[str | None] | None = None
        self._worker: asyncio.Task[None] | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._process_lock = asyncio.Lock()
        self._stopped = False

    @property
    def available(self) -> bool:
        return self._config.tts_enabled and sys.platform == "darwin"

    async def start(self) -> None:
        if not self.available or self._worker is not None:
            return
        self._stopped = False
        self._queue = asyncio.Queue()
        self._worker = asyncio.create_task(self._run(), name="vegas-voice-tts")

    async def enqueue(self, text: str) -> None:
        if not self.available or not text.strip():
            return
        await self.start()
        assert self._queue is not None
        await self._queue.put(text.strip())

    async def drain(self) -> None:
        if self._queue is not None:
            await self._queue.join()

    async def interrupt(self) -> None:
        """Stop current speech and discard unsaid chunks without blocking."""
        self._clear_queue()
        async with self._process_lock:
            process = self._process
            if process is None or process.poll() is not None:
                return
            try:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.terminate()
            except (OSError, ProcessLookupError):
                return

    async def close(self) -> None:
        self._stopped = True
        await self.interrupt()
        if self._queue is not None:
            await self._queue.put(None)
        if self._worker is not None:
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
        self._worker = None
        self._queue = None

    async def _run(self) -> None:
        assert self._queue is not None
        while True:
            text = await self._queue.get()
            try:
                if text is None:
                    return
                if not self._stopped:
                    await self._speak(text)
            finally:
                self._queue.task_done()

    async def _speak(self, text: str) -> None:
        command = ["say", "-v", self._config.tts_voice, "-r", str(self._config.tts_rate), text]
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            return

        async with self._process_lock:
            self._process = process
        try:
            try:
                await asyncio.wait_for(asyncio.to_thread(process.wait), timeout=120)
            except TimeoutError:
                try:
                    process.kill()
                except OSError:
                    pass
                await asyncio.to_thread(process.wait)
        finally:
            async with self._process_lock:
                if self._process is process:
                    self._process = None

    def _clear_queue(self) -> None:
        if self._queue is None:
            return
        # asyncio.Queue has no public drain API. This task owns the queue and
        # runs on one event loop, so a short non-blocking drain is safe here.
        drained: deque[str | None] = deque()
        while True:
            try:
                item = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                self._queue.task_done()
                if item is None:
                    drained.append(item)
        for item in drained:
            self._queue.put_nowait(item)
