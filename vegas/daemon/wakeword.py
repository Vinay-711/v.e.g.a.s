"""Low-CPU ``Hey Vegas`` wake-word monitoring with Porcupine."""

from __future__ import annotations

import os
import queue
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from vegas.voice.config import HEY_VEGAS


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class WakeWordConfig:
    """Configuration for the custom ``Hey Vegas`` Porcupine wake-word model."""

    enabled: bool
    access_key: str | None
    keyword_path: Path | None
    sensitivity: float = 0.55
    input_device: str | int | None = None

    @classmethod
    def from_environment(cls) -> "WakeWordConfig":
        raw_device = os.getenv("VEGAS_WAKE_WORD_DEVICE")
        device: str | int | None = raw_device
        if raw_device and raw_device.isdigit():
            device = int(raw_device)

        raw_sensitivity = os.getenv("VEGAS_WAKE_WORD_SENSITIVITY", "0.55")
        try:
            sensitivity = float(raw_sensitivity)
        except ValueError:
            sensitivity = 0.55

        return cls(
            enabled=_env_flag("VEGAS_WAKE_WORD_ENABLED", True),
            access_key=os.getenv("VEGAS_PORCUPINE_ACCESS_KEY"),
            keyword_path=(Path(os.environ["VEGAS_WAKE_WORD_KEYWORD_PATH"]).expanduser()
                          if os.getenv("VEGAS_WAKE_WORD_KEYWORD_PATH") else None),
            sensitivity=min(1.0, max(0.0, sensitivity)),
            input_device=device,
        )

    def validation_error(self) -> str | None:
        if not self.enabled:
            return None
        if not self.access_key:
            return "VEGAS_PORCUPINE_ACCESS_KEY is not configured."
        if self.keyword_path is None:
            return f"VEGAS_WAKE_WORD_KEYWORD_PATH must point to the custom '{HEY_VEGAS}' .ppn model."
        if not self.keyword_path.is_file():
            return f"Wake-word model was not found: {self.keyword_path}"
        return None


class PorcupineWakeWordMonitor:
    """Capture microphone frames through PortAudio without a Python spin loop.

    `sounddevice.RawInputStream` blocks inside PortAudio.  Its callback only
    performs the inexpensive native Porcupine frame check and queues a small
    event; the daemon consumes queued detections on its regular service tick.
    """

    backend_name = "porcupine"

    def __init__(
        self,
        config: WakeWordConfig,
        *,
        status_callback: Callable[[str, str | None, str | None], None],
    ) -> None:
        self._config = config
        self._status_callback = status_callback
        self._porcupine = None
        self._sounddevice = None
        self._stream = None
        self._detections: queue.SimpleQueue[None] = queue.SimpleQueue()
        self._running = False

    def start(self) -> None:
        """Start or resume microphone monitoring for the fixed Hey Vegas phrase."""
        self.resume()

    def resume(self) -> None:
        """Reopen capture after a voice utterance without rebuilding Porcupine."""
        if not self._config.enabled:
            self._status_callback(
                "disabled", self.backend_name, "Wake-word monitoring is disabled by configuration."
            )
            return

        if self._running:
            return

        validation_error = self._config.validation_error()
        if validation_error:
            self._status_callback("unavailable", self.backend_name, validation_error)
            return

        try:
            if self._porcupine is None:
                try:
                    import pvporcupine  # type: ignore[import-not-found]
                    import sounddevice  # type: ignore[import-not-found]
                except ImportError as exc:
                    self._status_callback(
                        "unavailable",
                        self.backend_name,
                        f"Install the voice extra to enable wake-word monitoring ({exc.name} is missing).",
                    )
                    return
                self._porcupine = pvporcupine.create(
                    access_key=self._config.access_key,
                    keyword_paths=[str(self._config.keyword_path)],
                    sensitivities=[self._config.sensitivity],
                )
                self._sounddevice = sounddevice

            assert self._sounddevice is not None
            self._stream = self._sounddevice.RawInputStream(
                samplerate=self._porcupine.sample_rate,
                blocksize=self._porcupine.frame_length,
                dtype="int16",
                channels=1,
                device=self._config.input_device,
                callback=self._audio_callback,
            )
            self._stream.start()
            self._running = True
            self._status_callback("listening", self.backend_name, f"Listening for '{HEY_VEGAS}'.")
        except Exception as exc:
            self.stop()
            self._status_callback("unavailable", self.backend_name, f"Could not start microphone monitoring: {exc}")

    def pause(self) -> None:
        """Release the microphone briefly while the STT recorder owns it."""
        self._running = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
        if self._config.enabled and self._porcupine is not None:
            self._status_callback("paused", self.backend_name, "Paused while VEGAS captures your request.")

    def stop(self) -> None:
        """Permanently release microphone and Porcupine resources."""
        self.pause()
        if self._porcupine is not None:
            try:
                self._porcupine.delete()
            finally:
                self._porcupine = None
        self._sounddevice = None

    def drain_detections(self) -> int:
        count = 0
        while True:
            try:
                self._detections.get_nowait()
            except queue.Empty:
                return count
            else:
                count += 1

    def _audio_callback(self, indata, frames, _time_info, status) -> None:  # type: ignore[no-untyped-def]
        if not self._running or self._porcupine is None:
            return
        if status or frames != self._porcupine.frame_length:
            return
        try:
            pcm = struct.unpack_from(f"{frames}h", indata)
            if self._porcupine.process(pcm) >= 0:
                self._detections.put(None)
        except Exception:
            # Audio callbacks must never raise into PortAudio.  A subsequent
            # status tick keeps the rest of the assistant available.
            return
