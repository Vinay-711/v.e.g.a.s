"""Voice interface components for the VEGAS desktop daemon.

The package intentionally keeps microphone capture in the local daemon and
task execution in the existing FastAPI application.  Text chat remains a
separate, unchanged interface.
"""

from .config import HEY_VEGAS, VoiceConfig
from .session import VoiceSessionManager

__all__ = ["HEY_VEGAS", "VoiceConfig", "VoiceSessionManager"]
