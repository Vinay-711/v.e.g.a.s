"""
System operations and environment tools for the Vegas Assistant.
Exposes tools for timezone-aware current time and system resource overview.
"""

from datetime import datetime
import os
import sys
import platform
try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo  # Fallback for older python, though >= 3.11 has it built-in

def get_current_time(timezone: str = "local") -> str:
    """
    Returns the current date/time. Supports 'local' and standard IANA timezone names.

    Args:
        timezone: The IANA timezone name (e.g., 'America/New_York', 'UTC', 'Asia/Kolkata') or 'local'.
    """
    try:
        if timezone.lower() == "local":
            dt = datetime.now()
            tz_name = "local"
            return f"Current time ({tz_name}): {dt.strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            tz = zoneinfo.ZoneInfo(timezone)
            dt = datetime.now(tz)
            tz_name = timezone
            return f"Current time ({tz_name}): {dt.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    except zoneinfo.ZoneInfoNotFoundError:
        return f"VEGAS: Timezone '{timezone}' was not found. Please provide a valid IANA timezone name."
    except Exception as e:
        return f"VEGAS: Failed to retrieve current time: {str(e)}"

def get_system_info() -> str:
    """
    Returns basic operating system, CPU count, memory usage, and Python version details.
    """
    try:
        os_name = f"{platform.system()} {platform.release()}"
        cpu_count = os.cpu_count() or "Unknown"
        python_ver = sys.version.split()[0]
        
        # Attempt to retrieve memory info with psutil
        try:
            import psutil
            virtual_mem = psutil.virtual_memory()
            total_gb = virtual_mem.total / (1024 ** 3)
            used_gb = virtual_mem.used / (1024 ** 3)
            percent = virtual_mem.percent
            memory_info = f"{used_gb:.2f} GB used / {total_gb:.2f} GB total ({percent}%)"
        except ImportError:
            memory_info = "Memory usage details require 'psutil' to be installed."
            
        info = [
            f"OS: {os_name}",
            f"CPU Count: {cpu_count}",
            f"Memory: {memory_info}",
            f"Python Version: {python_ver}"
        ]
        return "\n".join(info)
    except Exception as e:
        return f"VEGAS: Failed to retrieve system info: {str(e)}"

def register(mcp) -> None:
    """
    Registers the system tools with the provided FastMCP server instance.
    """
    mcp.tool()(get_current_time)
    mcp.tool()(get_system_info)
