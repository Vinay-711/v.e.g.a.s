import os
import asyncio
from threading import Thread

def _run_async_in_thread(coro):
    """Runs a coroutine in a new event loop on a separate thread and returns the result."""
    result = []
    exception = []

    def target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            res = loop.run_until_complete(coro)
            result.append(res)
        except Exception as e:
            exception.append(e)
        finally:
            loop.close()

    thread = Thread(target=target)
    thread.start()
    thread.join()

    if exception:
        raise exception[0]
    return result[0]

def delegate_autonomous_task(task_description: str) -> str:
    """
    Spins up a fully autonomous V.E.G.A.S. agent in the background to execute
    a complex, multi-step task (e.g. coding, file creation, terminal execution, etc.)
    and returns the final execution report.

    Args:
        task_description: The detailed task description for the autonomous agent.
    """
    async def _impl():
        # Ensure GEMINI_API_KEY is populated for the SDK connection
        if "GOOGLE_API_KEY" in os.environ and "GEMINI_API_KEY" not in os.environ:
            os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]

        from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig
        from google.antigravity.hooks import policy

        config = LocalAgentConfig(
            system_instructions=(
                "You are VEGAS, a highly intelligent autonomous assistant. "
                "You have full tool capabilities including terminal command execution, "
                "file viewing, file editing, and file creation. "
                "Use these tools autonomously to fulfill the user's request. "
                "Always check your output, verify execution, and communicate clearly."
            ),
            capabilities=CapabilitiesConfig(
                enable_subagents=True,
            ),
            policies=[policy.allow_all()]
        )
        async with Agent(config=config) as agent:
            response = await agent.chat(task_description)
            return await response.text()

    try:
        return _run_async_in_thread(_impl())
    except Exception as e:
        return f"VEGAS: Delegation of autonomous task failed: {str(e)}"

def register(mcp) -> None:
    """
    Registers the delegation tool with the provided FastMCP server instance.
    """
    mcp.tool()(delegate_autonomous_task)

