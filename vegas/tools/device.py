"""
Cross-Device Ecosystem and Mobile Control Bridge for VEGAS AIOS.

Enables seamless host-to-mobile automation via ADB (USB & Wireless ADB).
Allows VEGAS to control phone applications, open maps, manage media playback,
check battery telemetry, capture device screenshots, and send SMS/calls.
"""

import os
import re
import subprocess
import shutil
import urllib.parse
from vegas.safety import requires_confirmation
from vegas.memory import log_event
from vegas.tools.files import _verify_sandbox_path

# Common Android App Package Mappings
KNOWN_PACKAGES = {
    "youtube": "com.google.android.youtube",
    "spotify": "com.spotify.music",
    "whatsapp": "com.whatsapp",
    "maps": "com.google.android.apps.maps",
    "google maps": "com.google.android.apps.maps",
    "chrome": "com.android.chrome",
    "camera": "com.android.camera",
    "settings": "com.android.settings",
    "calculator": "com.google.android.calculator",
    "clock": "com.google.android.deskclock",
    "gmail": "com.google.android.gm",
    "photos": "com.google.android.apps.photos",
    "instagram": "com.instagram.android",
    "telegram": "org.telegram.messenger",
}

def _get_adb_binary() -> str:
    """Finds the absolute path to the adb binary."""
    adb_path = shutil.which("adb")
    if adb_path:
        return adb_path
    if os.path.exists("/opt/homebrew/bin/adb"):
        return "/opt/homebrew/bin/adb"
    if os.path.exists("/usr/local/bin/adb"):
        return "/usr/local/bin/adb"
    return "adb"

def _run_adb_command(args: list[str], timeout: int = 15) -> tuple[int, str]:
    """Helper to execute an ADB command and return returncode, output."""
    adb_bin = _get_adb_binary()
    cmd = [adb_bin] + args
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return res.returncode, (res.stdout or "") + (res.stderr or "")
    except FileNotFoundError:
        return 127, "Error: ADB binary not found on host system."
    except Exception as e:
        return 1, f"Error executing ADB command: {str(e)}"

def list_connected_devices() -> str:
    """
    Lists all connected Android mobile devices (USB or Wireless ADB) and their status.
    Returns device IDs, models, connection types, and battery percentage.
    """
    log_event("device", "List connected devices")
    code, output = _run_adb_command(["devices", "-l"])
    if code != 0:
        return f"VEGAS Mobile Ecosystem Error: {output}"

    lines = output.strip().splitlines()
    device_lines = [l for l in lines[1:] if l.strip()]

    if not device_lines:
        return (
            "📱 VEGAS Mobile Ecosystem: No connected mobile devices detected.\n"
            "Tip: Connect your Android phone via USB with USB Debugging enabled, "
            "or pair wirelessly using pair_wireless_device(ip_address='<phone_ip>')."
        )

    formatted = ["📱 VEGAS Mobile Ecosystem — Connected Devices:"]
    for line in device_lines:
        parts = line.split()
        if len(parts) >= 2:
            dev_id = parts[0]
            dev_state = parts[1]

            model = "Android Device"
            model_match = re.search(r'model:(\S+)', line)
            if model_match:
                model = model_match.group(1).replace("_", " ")

            conn_type = "Wi-Fi (Wireless)" if ":" in dev_id else "USB Cable"

            # Get battery info if device is authorized
            battery_str = "Unknown"
            if dev_state == "device":
                b_code, b_out = _run_adb_command(["-s", dev_id, "shell", "dumpsys", "battery"])
                if b_code == 0:
                    level_m = re.search(r'level:\s*(\d+)', b_out)
                    if level_m:
                        battery_str = f"{level_m.group(1)}%"

            formatted.append(
                f"- ID: {dev_id} | Model: {model} | State: {dev_state} | Connection: {conn_type} | Battery: {battery_str}"
            )

    return "\n".join(formatted)

def pair_wireless_device(ip_address: str, port: int = 5555) -> str:
    """
    Connects to a phone wirelessly over local Wi-Fi via Wireless ADB.

    Args:
        ip_address: The local IP address of your phone (e.g. "192.168.1.5").
        port: The ADB port number (default 5555).
    """
    log_event("device", f"Pair wireless device: {ip_address}:{port}")
    target = f"{ip_address}:{port}"
    code, output = _run_adb_command(["connect", target])
    if code == 0 and "connected to" in output.lower():
        return f"✅ Wireless Ecosystem Connected! Successfully paired with phone at {target}."
    return f"VEGAS Mobile Ecosystem: Failed to connect to wireless device at {target}.\nDetails: {output}"

@requires_confirmation
def send_phone_sms(number: str, text: str, device_id: str = None) -> str:
    """
    Drafts and opens SMS text message on connected phone.
    Gated by @requires_confirmation for safety.

    Args:
        number: Target recipient phone number (e.g. "+1234567890").
        text: SMS message text content.
        device_id: Optional specific device ID (defaults to first connected device).
    """
    log_event("device", "Send SMS", f"to={number}")
    dev_flag = ["-s", device_id] if device_id else []
    encoded_text = urllib.parse.quote_plus(text)
    cmd = dev_flag + [
        "shell", "am", "start", "-a", "android.intent.action.SENDTO",
        "-d", f"sms:{number}", "--es", "sms_body", text
    ]
    code, output = _run_adb_command(cmd)
    if code == 0:
        return f"📲 Opened SMS draft on phone to {number} with message: '{text}'."
    return f"VEGAS Mobile Ecosystem Error: Failed to draft SMS: {output}"

@requires_confirmation
def make_phone_call(number: str, device_id: str = None) -> str:
    """
    Dials a phone number on the connected mobile device.
    Gated by @requires_confirmation for safety.

    Args:
        number: Target phone number to call (e.g. "+1234567890").
        device_id: Optional specific device ID.
    """
    log_event("device", "Make phone call", number)
    dev_flag = ["-s", device_id] if device_id else []
    cmd = dev_flag + [
        "shell", "am", "start", "-a", "android.intent.action.CALL",
        "-d", f"tel:{number}"
    ]
    code, output = _run_adb_command(cmd)
    if code == 0:
        return f"📞 Initiating call on phone to number: {number}."
    return f"VEGAS Mobile Ecosystem Error: Failed to initiate call: {output}"

def execute_phone_command(action: str, target: str = None, text: str = None, device_id: str = None) -> str:
    """
    Executes natural language actions directly on the user's connected phone.

    Args:
        action: The action type. Supported actions:
            - "open_app": Opens an app by name (e.g. "youtube", "spotify", "whatsapp", "maps", "chrome", "camera", "settings").
            - "open_url": Opens a URL in the phone's browser (e.g. "https://wikipedia.org").
            - "open_map": Opens location or search query in Google Maps on phone (e.g. "Ramanagara" or "Eiffel Tower").
            - "media_control": Controls media playback on phone ("play_pause", "next", "prev", "volume_up", "volume_down").
            - "battery_status": Checks battery level, temperature, and charging state.
            - "take_screenshot": Captures phone screen and saves to workspace.
        target: Target app name, URL, location query, or media command (depending on action).
        text: Optional additional text parameter.
        device_id: Optional specific device ID (defaults to primary connected device).
    """
    log_event("device", f"Execute phone command: {action}", f"target={target}")
    dev_flag = ["-s", device_id] if device_id else []
    action_lower = action.lower().strip()

    # 1. Open App
    if action_lower == "open_app":
        if not target:
            return "VEGAS Mobile Ecosystem Error: Please specify an app name (e.g., target='youtube')."

        app_key = target.lower().strip()
        pkg = KNOWN_PACKAGES.get(app_key, app_key)

        # Try launching via monkey launcher
        cmd = dev_flag + ["shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"]
        code, output = _run_adb_command(cmd)

        if code == 0 and "No activities found" not in output:
            return f"📱 Opening app '{target}' ({pkg}) on your connected phone!"

        # Fallback: am start intent
        cmd_fallback = dev_flag + ["shell", "am", "start", "-n", f"{pkg}"]
        f_code, f_out = _run_adb_command(cmd_fallback)
        if f_code == 0:
            return f"📱 Launched application '{target}' on phone."
        return f"VEGAS Mobile Ecosystem: Could not launch app '{target}'. Output: {output}"

    # 2. Open URL on Phone Browser
    elif action_lower == "open_url":
        if not target:
            return "VEGAS Mobile Ecosystem Error: Please specify a URL (e.g., target='https://google.com')."
        url = target if target.startswith("http") else f"https://{target}"
        cmd = dev_flag + ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url]
        code, output = _run_adb_command(cmd)
        if code == 0:
            return f"🌐 Opening web page '{url}' on your phone browser!"
        return f"VEGAS Mobile Ecosystem Error: {output}"

    # 3. Open Map Location on Phone
    elif action_lower == "open_map":
        if not target:
            return "VEGAS Mobile Ecosystem Error: Please specify a location (e.g., target='Ramanagara')."
        encoded = urllib.parse.quote_plus(target)
        geo_uri = f"geo:0,0?q={encoded}"
        cmd = dev_flag + ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", geo_uri]
        code, output = _run_adb_command(cmd)
        if code == 0:
            return f"🗺️ Opening location '{target}' in Google Maps on your phone!"
        return f"VEGAS Mobile Ecosystem Error: {output}"

    # 4. Media Control on Phone
    elif action_lower == "media_control":
        cmd_map = {
            "play_pause": "85",
            "play": "126",
            "pause": "127",
            "next": "87",
            "prev": "88",
            "previous": "88",
            "volume_up": "24",
            "volume_down": "25",
            "mute": "164"
        }
        key = cmd_map.get((target or "play_pause").lower().strip(), "85")
        cmd = dev_flag + ["shell", "input", "keyevent", key]
        code, output = _run_adb_command(cmd)
        if code == 0:
            return f"🎵 Executed phone media control '{target or 'play_pause'}'."
        return f"VEGAS Mobile Ecosystem Error: {output}"

    # 5. Battery Status
    elif action_lower == "battery_status":
        cmd = dev_flag + ["shell", "dumpsys", "battery"]
        code, output = _run_adb_command(cmd)
        if code != 0:
            return f"VEGAS Mobile Ecosystem Error: {output}"

        level = re.search(r'level:\s*(\d+)', output)
        status = re.search(r'status:\s*(\d+)', output)
        health = re.search(r'health:\s*(\d+)', output)
        temp = re.search(r'temperature:\s*(\d+)', output)

        battery_pct = level.group(1) + "%" if level else "Unknown"
        is_charging = "Plugged In / Charging" if (status and status.group(1) == "2") else "Discharging / On Battery"
        temperature_c = str(round(int(temp.group(1)) / 10, 1)) + "°C" if temp else "Normal"

        return (
            f"🔋 Mobile Phone Battery Telemetry:\n"
            f"- Charge Level: {battery_pct}\n"
            f"- Power Status: {is_charging}\n"
            f"- Temperature: {temperature_c}"
        )

    # 6. Take Screenshot of Phone
    elif action_lower == "take_screenshot":
        save_path = os.path.join(os.getcwd(), "phone_screenshot.png")
        verified_path = _verify_sandbox_path(save_path)

        adb_bin = _get_adb_binary()
        exec_cmd = [adb_bin] + dev_flag + ["exec-out", "screencap", "-p"]

        try:
            with open(verified_path, "wb") as f:
                res = subprocess.run(exec_cmd, stdout=f, stderr=subprocess.PIPE, timeout=15)
            if res.returncode == 0 and os.path.getsize(verified_path) > 0:
                return f"📸 Captured phone screen! Screenshot saved to workspace: {verified_path}"
            return f"VEGAS Mobile Ecosystem Error: Failed to capture screenshot. Stderr: {res.stderr.decode()}"
        except Exception as e:
            return f"VEGAS Mobile Ecosystem Error capturing screenshot: {str(e)}"

    return f"VEGAS Mobile Ecosystem Error: Unknown action '{action}'. Supported actions: open_app, open_url, open_map, media_control, battery_status, take_screenshot."

def register(mcp) -> None:
    """Registers Ecosystem & Device tools with FastMCP server instance."""
    mcp.tool()(list_connected_devices)
    mcp.tool()(execute_phone_command)
    mcp.tool()(send_phone_sms)
    mcp.tool()(make_phone_call)
    mcp.tool()(pair_wireless_device)
