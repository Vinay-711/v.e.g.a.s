"""Streaming control-plane client from the local daemon to FastAPI."""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import AsyncIterator
from typing import Any

import requests


class VoicePlannerClient:
    """Read newline-delimited voice events without blocking the daemon loop."""

    def __init__(self, api_url: str) -> None:
        self._api_url = api_url

    async def stream_command(
        self,
        transcript: str,
        conversation_id: str,
    ) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=128)
        cancelled = threading.Event()
        response_holder: list[requests.Response] = []
        loop = asyncio.get_running_loop()

        def submit(event: dict[str, Any] | None) -> None:
            # This runs on the asyncio loop after call_soon_threadsafe(). Drop
            # only non-terminal status noise if the UI/voice consumer is slow.
            if event is not None and queue.full() and event.get("type") not in {"error", "final"}:
                return
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)

        def worker() -> None:
            try:
                with requests.post(
                    self._api_url,
                    json={"message": transcript, "conversation_id": conversation_id},
                    headers={"Accept": "application/x-ndjson"},
                    stream=True,
                    timeout=(4, 120),
                ) as response:
                    response_holder.append(response)
                    response.raise_for_status()
                    for raw_line in response.iter_lines(decode_unicode=True):
                        if cancelled.is_set():
                            break
                        if not raw_line:
                            continue
                        try:
                            event = json.loads(raw_line)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(event, dict):
                            loop.call_soon_threadsafe(submit, event)
            except Exception as exc:
                loop.call_soon_threadsafe(
                    submit,
                    {"type": "error", "detail": f"Voice planner connection failed: {exc}"},
                )
            finally:
                # Calls scheduled from a single worker thread preserve order,
                # so all events are consumed before this terminal sentinel.
                loop.call_soon_threadsafe(submit, None)

        thread = threading.Thread(target=worker, name="vegas-voice-planner", daemon=True)
        thread.start()
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        finally:
            cancelled.set()
            if response_holder:
                response_holder[0].close()
