"""Always-running local runtime for the VEGAS desktop assistant.

The daemon owns process supervision, wake-word monitoring, and the durable
status connection back to the existing FastAPI application.  It deliberately
does not import the tool registry at module import time, so it can report
actionable startup diagnostics even when an optional integration is missing.
"""

from .runtime import VegasDaemon, VegasDaemonConfig

__all__ = ["VegasDaemon", "VegasDaemonConfig"]
