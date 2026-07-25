"""
V.E.G.A.S. Autonomous Agent powered by Google Antigravity SDK.
Capable of running coding tasks, system actions, and daily workflows autonomously.
"""

import os
import sys
import asyncio
from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig
from google.antigravity.hooks import policy
from dotenv import load_dotenv

# Load credentials
load_dotenv()

# Antigravity SDK specifically requires GEMINI_API_KEY
if "GOOGLE_API_KEY" in os.environ and "GEMINI_API_KEY" not in os.environ:
    os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]


async def run_one_shot(task: str):
    """
    Executes a single instruction autonomously and prints the result.
    """
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
        response = await agent.chat(task)
        print(await response.text())

async def main_async():
    """
    Main asynchronous CLI router.
    """
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        print(f"VEGAS: Initiating autonomous execution of task: '{task}'")
        await run_one_shot(task)
    else:
        # Launch interactive loop in terminal
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
            await agent.run_interactive_loop()

def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nVEGAS: Interaction aborted.")
        sys.exit(0)

if __name__ == "__main__":
    main()
