"""
System media and speech automation tools for VEGAS AIOS.

Uses macOS AppleScript (osascript) and system speech utilities.
Changes to system volume or media state require confirmation.
"""

import subprocess
import sys
import urllib.parse
from vegas.safety import requires_confirmation
from vegas.memory import log_event

def _run_osascript(script: str) -> tuple[int, str]:
    """Helper to run AppleScript commands on macOS."""
    if sys.platform != "darwin":
        return 1, "Error: Media tools are only supported on macOS."
    try:
        res = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10
        )
        return res.returncode, (res.stdout or "") + (res.stderr or "")
    except Exception as e:
        return 1, str(e)

@requires_confirmation
def set_system_volume(level: int) -> str:
    """
    Sets the host system audio output volume level (0 to 100).
    Gated by @requires_confirmation.

    Args:
        level: Audio volume level from 0 (muted) to 100 (maximum).
    """
    log_event("media", f"Set volume to {level}")
    level = max(0, min(100, level))
    # Convert level 0-100 to AppleScript output volume level
    code, out = _run_osascript(f"set volume output volume {level}")
    if code != 0:
        return f"Failed to set volume: {out}"
    return f"Successfully set system audio volume to {level}%."

@requires_confirmation
def play_pause_media() -> str:
    """
    Toggles play/pause state for system media player (Music, Spotify, Safari, etc.).
    Gated by @requires_confirmation.
    """
    log_event("media", "Toggle play/pause")
    code, out = _run_osascript('tell application "System Events" to key code 16')
    if code != 0:
        return f"Failed to toggle media play/pause: {out}"
    return "Toggled play/pause media playback state."

def speak_text(text: str) -> str:
    """
    Synthesizes and speaks text aloud using the host system's built-in text-to-speech tool.
    Does not require confirmation (safe output-only operation).

    Args:
        text: The text string to read aloud.
    """
    log_event("media", "Speak text", text)
    if sys.platform != "darwin":
        return "Speech output is only supported on macOS using the 'say' command."
    try:
        subprocess.run(["say", text], timeout=15)
        return f"Spoke text aloud: '{text}'"
    except Exception as e:
        return f"Failed to speak text: {e}"

def play_music(query: str) -> str:
    """
    Finds and plays a song or video by opening the first YouTube result directly in the user's default browser.
    Use this whenever the user asks to play music, a song, a video, or any audio content.

    Args:
        query: The song name, artist, or search query (e.g. "Blinding Lights The Weeknd").
    """
    import urllib.request
    import json
    import re
    try:
        log_event("media", "Play music", query)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        encoded = urllib.parse.quote_plus(query)
        search_url = f"https://www.youtube.com/results?search_query={encoded}"
        
        # Default fallback is search results page
        target_url = search_url
        video_title = "Search Results"
        
        req = urllib.request.Request(search_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                html = response.read().decode('utf-8')
            
            # Find ytInitialData script JSON
            match = re.search(r'var ytInitialData\s*=\s*({.*?});', html)
            if match:
                data = json.loads(match.group(1))
                contents = data['contents']['twoColumnSearchResultsRenderer']['primaryContents']['sectionListRenderer']['contents']
                video_id = None
                for item in contents:
                    if 'itemSectionRenderer' in item:
                        section_contents = item['itemSectionRenderer']['contents']
                        for content in section_contents:
                            if 'videoRenderer' in content:
                                video_id = content['videoRenderer']['videoId']
                                video_title = content['videoRenderer']['title']['runs'][0]['text']
                                break
                        if video_id:
                            break
                if video_id:
                    target_url = f"https://www.youtube.com/watch?v={video_id}"
            else:
                # Regex fallback
                video_ids = re.findall(r'/watch\?v=([a-zA-Z0-9_-]{11})', html)
                if video_ids:
                    target_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
                    video_title = "First Result"
        except Exception as api_err:
            # If fetch fails, keep search_url
            pass

        subprocess.Popen(["open", target_url])
        if target_url != search_url:
            return f"🎵 Found and playing: \"{video_title}\" on YouTube! Opening in your browser..."
        else:
            return f"🎵 Opening YouTube search for: \"{query}\" in your browser."
    except Exception as e:
        return f"VEGAS: Failed to play music: {str(e)}"


def open_youtube_video(url: str) -> str:
    """
    Opens a specific YouTube video URL in the user's default browser.
    Use this when the user provides a direct YouTube link.

    Args:
        url: The full YouTube video URL (e.g. "https://www.youtube.com/watch?v=...").
    """
    try:
        log_event("media", "Open YouTube video", url)
        subprocess.Popen(["open", url])
        return f"🎬 Opening video: {url}"
    except Exception as e:
        return f"VEGAS: Failed to open video: {str(e)}"


def register(mcp) -> None:
    """Registers media tools with FastMCP."""
    mcp.tool()(set_system_volume)
    mcp.tool()(play_pause_media)
    mcp.tool()(speak_text)
    mcp.tool()(play_music)
    mcp.tool()(open_youtube_video)

