"""Local speech capture using faster-whisper and a bounded PortAudio queue."""

from __future__ import annotations

import math
import queue
import threading
import time
from typing import Any

from .config import VoiceConfig


def _rms_pcm16(pcm: bytes) -> int:
    """Return the RMS energy for a little-endian mono PCM16 frame."""
    if len(pcm) < 2:
        return 0
    samples = memoryview(pcm).cast("h")
    total = sum(sample * sample for sample in samples)
    return int(math.sqrt(total / len(samples))) if samples else 0


class FasterWhisperSpeechCapture:
    """Record one utterance and transcribe it locally after end-of-speech.

    The audio callback only enqueues PCM frames. Voice activity detection and
    model inference run in the caller's worker thread, so the always-running
    daemon remains quiet and low-CPU while waiting for ``Hey Vegas``.
    """

    backend_name = "faster-whisper"

    def __init__(self, config: VoiceConfig) -> None:
        self._config = config
        self._model: Any | None = None
        self._sounddevice: Any | None = None
        self._numpy: Any | None = None
        self._stream: Any | None = None
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=160)
        self._cancelled = threading.Event()
        self._stream_lock = threading.RLock()

    def prepare(self) -> None:
        """Load the local model once before the first spoken request."""
        error = self._config.validation_error()
        if error:
            raise RuntimeError(error)
        if self._model is not None:
            return
        try:
            import numpy  # type: ignore[import-not-found]
            import sounddevice  # type: ignore[import-not-found]
            from faster_whisper import WhisperModel  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                f"Install VEGAS voice dependencies to enable local speech-to-text ({exc.name} is missing)."
            ) from exc

        self._model = WhisperModel(
            self._config.whisper_model,
            device=self._config.whisper_device,
            compute_type=self._config.whisper_compute_type,
        )
        self._sounddevice = sounddevice
        self._numpy = numpy

    def capture_utterance(
        self,
        *,
        activation_timeout_seconds: float,
        on_partial: Any | None = None,
    ) -> str | None:
        """Block until the speaker pauses, then return its final transcript."""
        self.prepare()
        assert self._sounddevice is not None
        self._cancelled.clear()
        self._queue = queue.Queue(maxsize=160)
        recorded_pcm = bytearray()
        started_at = time.monotonic()
        last_voice_at: float | None = None
        speech_seconds = 0.0

        def audio_callback(indata: Any, _frames: int, _time_info: Any, _status: Any) -> None:
            pcm = bytes(indata)
            try:
                self._queue.put_nowait(pcm)
            except queue.Full:
                try:
                    self._queue.get_nowait()
                    self._queue.put_nowait(pcm)
                except queue.Empty:
                    pass

        stream = self._sounddevice.RawInputStream(
            samplerate=self._config.sample_rate,
            blocksize=max(160, self._config.sample_rate // 50),  # 20 ms frames
            dtype="int16",
            channels=1,
            device=self._config.input_device,
            callback=audio_callback,
        )
        with self._stream_lock:
            self._stream = stream
        try:
            stream.start()
            while not self._cancelled.is_set():
                now = time.monotonic()
                elapsed = now - started_at
                if elapsed >= self._config.max_utterance_seconds:
                    break
                if last_voice_at is None and elapsed >= activation_timeout_seconds:
                    return None
                if (
                    last_voice_at is not None
                    and speech_seconds >= self._config.min_speech_seconds
                    and now - last_voice_at >= self._config.silence_seconds
                ):
                    break
                try:
                    pcm = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                frame_seconds = len(pcm) / (2 * self._config.sample_rate)
                if _rms_pcm16(pcm) >= self._config.speech_threshold:
                    last_voice_at = time.monotonic()
                    speech_seconds += frame_seconds
                # Keep a small leading window so the first phoneme is not
                # clipped when VAD crosses its speech threshold.
                recorded_pcm.extend(pcm)

            if self._cancelled.is_set() or speech_seconds < self._config.min_speech_seconds:
                return None
            if on_partial is not None:
                on_partial("Transcribing locally…")
            return self._transcribe(bytes(recorded_pcm))
        finally:
            self._close_stream(stream)

    def cancel(self) -> None:
        self._cancelled.set()
        with self._stream_lock:
            stream = self._stream
        if stream is not None:
            self._close_stream(stream)

    def close(self) -> None:
        self.cancel()
        self._model = None
        self._sounddevice = None
        self._numpy = None

    def _transcribe(self, pcm: bytes) -> str | None:
        assert self._model is not None
        assert self._numpy is not None
        audio = self._numpy.frombuffer(pcm, dtype=self._numpy.int16).astype(self._numpy.float32) / 32768.0
        segments, _info = self._model.transcribe(
            audio,
            language=self._config.whisper_language,
            beam_size=1,
            best_of=1,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
        return text or None

    def _close_stream(self, stream: Any) -> None:
        with self._stream_lock:
            if self._stream is stream:
                self._stream = None
        try:
            stream.stop()
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass
