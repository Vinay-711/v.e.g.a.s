"""
Custom tools registry for the Vegas Assistant.
Exposes a function to register all tools (web, system, utils, etc.) onto an MCP server instance.
"""

from . import web
from . import system
from . import utils
from . import developer
from . import aios
from . import browser
from . import memory as memory_tools
from . import coding
from . import workflow
from . import files
from . import git_ops
from . import media
from . import db_client
from . import api_client
from . import autonomous
from . import device
from . import macos
from . import companion

def register_all_tools(mcp) -> None:
    """
    Imports and registers all tools with the provided MCP server.
    """
    web.register(mcp)
    system.register(mcp)
    utils.register(mcp)
    developer.register(mcp)
    aios.register(mcp)
    browser.register(mcp)
    memory_tools.register(mcp)
    coding.register(mcp)
    workflow.register(mcp)
    files.register(mcp)
    git_ops.register(mcp)
    media.register(mcp)
    db_client.register(mcp)
    api_client.register(mcp)
    autonomous.register(mcp)
    device.register(mcp)
    macos.register(mcp)
    companion.register(mcp)



