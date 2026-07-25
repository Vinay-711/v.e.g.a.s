"""
Multi-Agent Collaboration Engine for VEGAS AIOS.
Allows the main agent to delegate tasks to specialized sub-agents.
"""

from typing import Dict, Any, List, Optional
import os
from google import genai
from google.genai import types

class SpecializedSubAgent:
    def __init__(self, role_name: str, system_instructions: str, allowed_tools: List[str]):
        self.role_name = role_name
        self.system_instructions = system_instructions
        self.allowed_tools = allowed_tools
        self.api_key = os.environ.get("GOOGLE_API_KEY", "")
        self.client = None
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)

    def execute_delegated_task(self, task: str) -> str:
        """
        Executes a task autonomously in a dedicated session and returns the summary response.
        """
        if not self.client:
            return f"SubAgent Error: Specialized agent '{self.role_name}' lacks API Key config."
            
        print(f"Collaboration: Specialized Agent '{self.role_name}' activated for task: {task}", flush=True)
        
        # Build prompt
        prompt = (
            f"You are a specialized sub-agent with role: '{self.role_name}'.\n"
            f"Your instructions are:\n{self.system_instructions}\n"
            f"Your task is:\n{task}\n"
            f"Complete it efficiently and return the output summary."
        )
        
        try:
            # Call Gemini directly for task execution
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3
                )
            )
            return response.text
        except Exception as e:
            return f"SubAgent '{self.role_name}' failed to execute: {str(e)}"

class CollaborationManager:
    def __init__(self):
        # Default specialized profiles
        self.profiles = {
            "developer": SpecializedSubAgent(
                role_name="DeveloperAgent",
                system_instructions="You write clean, verified python scripts, debug code structures, and run syntax checks.",
                allowed_tools=["run_command_in_sandbox", "execute_python_code_in_sandbox", "write_file", "edit_file"]
            ),
            "researcher": SpecializedSubAgent(
                role_name="ResearchAgent",
                system_instructions="You scour web search details, clean text documents, and summarize global facts.",
                allowed_tools=["search_web", "fetch_url"]
            )
        }

    def delegate_task(self, agent_role: str, task_description: str) -> str:
        """Delegates a workflow task to a specialized agent role."""
        role = agent_role.lower().strip()
        if role not in self.profiles:
            return f"Collaboration Error: Agent role '{agent_role}' is not defined. Choose from: {list(self.profiles.keys())}"
            
        sub_agent = self.profiles[role]
        result = sub_agent.execute_delegated_task(task_description)
        return result

# Global collaboration manager
collaboration = CollaborationManager()
