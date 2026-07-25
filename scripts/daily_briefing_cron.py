#!/usr/bin/env python3
"""
Daily Briefing Cron Script for VEGAS AIOS.

Connects to the running VEGAS MCP server over SSE, calls the morning_briefing
tool, and either:
  (a) Synthesises spoken audio via the OpenAI TTS API and saves it to
      ~/.vegas/briefings/YYYY-MM-DD.mp3, or
  (b) Prints the text to stdout (when --text-only is passed).

Usage:
    # Spoken audio (requires OPENAI_API_KEY in environment / .env)
    uv run python scripts/daily_briefing_cron.py

    # Text-only (no TTS)
    uv run python scripts/daily_briefing_cron.py --text-only

Crontab entry (7 AM daily):
    0 7 * * * cd /Users/vinxy/VEGAS/vegas-assistant && uv run python scripts/daily_briefing_cron.py >> ~/.vegas/briefing_cron.log 2>&1
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load project .env so OPENAI_API_KEY etc. are available
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


# ---------------------------------------------------------------------------
# 1.  Fetch the briefing text from the MCP server
# ---------------------------------------------------------------------------

async def fetch_briefing(mcp_url: str) -> str:
    """Connects to the VEGAS MCP server and calls morning_briefing."""
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    async with sse_client(mcp_url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool("morning_briefing", arguments={})
            parts = []
            for content in result.content:
                if hasattr(content, "text"):
                    parts.append(content.text)
                elif isinstance(content, dict) and "text" in content:
                    parts.append(content["text"])
            return "\n".join(parts) if parts else str(result)


# ---------------------------------------------------------------------------
# 2.  Synthesise speech via the OpenAI TTS API (same provider as agent_vegas)
# ---------------------------------------------------------------------------

def synthesise_audio(text: str, output_path: Path) -> None:
    """
    Calls the OpenAI TTS REST API (model=tts-1, voice=nova) and writes the
    resulting MP3 to *output_path*.
    """
    import requests

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print(
            "WARNING: OPENAI_API_KEY not set — skipping TTS. "
            "Set it in .env or export it before running this script.",
            file=sys.stderr,
        )
        return

    # OpenAI TTS endpoint
    url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "tts-1",
        "voice": "nova",       # same voice used in agent_vegas.py
        "input": text[:4096],  # API limit per call
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(resp.content)
    print(f"Audio saved to {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="VEGAS Daily Briefing")
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="Print the briefing text without generating audio.",
    )
    parser.add_argument(
        "--mcp-url",
        default="http://127.0.0.1:8000/sse",
        help="URL of the running VEGAS MCP server (default: http://127.0.0.1:8000/sse).",
    )
    args = parser.parse_args()

    print(f"[{datetime.now().isoformat()}] Fetching morning briefing…")
    briefing_text = asyncio.run(fetch_briefing(args.mcp_url))

    if not briefing_text.strip():
        print("ERROR: Received empty briefing.", file=sys.stderr)
        sys.exit(1)

    print(briefing_text)

    if not args.text_only:
        today = datetime.now().strftime("%Y-%m-%d")
        audio_path = Path.home() / ".vegas" / "briefings" / f"{today}.mp3"
        synthesise_audio(briefing_text, audio_path)


if __name__ == "__main__":
    main()
