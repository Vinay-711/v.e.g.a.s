"""
ReAct Autonomous Agent loop engine for VEGAS AIOS.
Uses the official google-genai SDK to run a Plan-Act-Reflect loop.
"""

import os
import sys
import json
import threading
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types

# Import local tools for execution mapping
from vegas.runtime.sandbox import sandbox
from vegas.core.memory import memory
from vegas.tools import web, system, utils, developer, aios

class VegasAgentOrchestrator:
    def __init__(self):
        self.api_key = os.environ.get("GOOGLE_API_KEY", "")
        self.client = None
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
            
        self.status = "idle"  # idle | running | success | failed
        self.last_log = ""
        self.logs: List[str] = []
        self._thread: Optional[threading.Thread] = None
        self.current_goal = ""

        # Map function names to actual callables
        self.tool_map = {
            "run_command_in_sandbox": aios.run_command_in_sandbox,
            "execute_python_code_in_sandbox": aios.execute_python_code_in_sandbox,
            "list_directory": developer.list_directory,
            "view_file": developer.view_file,
            "write_file": developer.write_file,
            "edit_file": developer.edit_file,
            "search_directory": developer.search_directory,
            "search_web": web.search_web,
            "fetch_url": web.fetch_url,
            "list_memory": aios.list_memory,
            "store_memory_fact": aios.store_memory_fact,
            "get_current_time": system.get_current_time,
            "get_system_info": system.get_system_info
        }

    def log(self, message: str):
        print(f"[VEGAS Agent] {message}", flush=True)
        self.last_log = message
        self.logs.append(message)

    def start_goal(self, goal: str):
        """Starts the autonomous execution loop in a background thread."""
        if self.status == "running":
            return "VEGAS: Agent is already running an active goal."
            
        self.status = "running"
        self.current_goal = goal
        self.logs.clear()
        
        self._thread = threading.Thread(target=self._run_loop, args=(goal,), daemon=True)
        self._thread.start()
        return f"Autonomous agent started successfully for goal: '{goal}'"

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "goal": self.current_goal,
            "last_log": self.last_log,
            "logs_count": len(self.logs)
        }

    def _run_loop(self, goal: str):
        self.log(f"Initializing ReAct reasoning engine for goal: {goal}")
        
        if not self.client:
            self.status = "failed"
            self.log("Initialization aborted: GOOGLE_API_KEY environment variable is not configured.")
            return

        # Prepare instructions
        system_instruction = (
            "You are VEGAS, the world's most advanced Autonomous AI Operating System.\n"
            "Your objective is to accomplish the user's goal autonomously.\n"
            "You have access to terminal commands, Python execution, file management, and search tools.\n"
            "Rules:\n"
            "1. Plan your actions step-by-step.\n"
            "2. Execute commands/scripts inside the sandbox and verify outputs.\n"
            "3. If a tool execution fails, reflect on the error and correct your script or command. Do not repeat failed statements.\n"
            "4. Once the goal is completed, explain the output clearly and state that the goal has been successfully accomplished.\n"
        )

        try:
            # Create tool definitions list for Gemini
            tools_list = list(self.tool_map.values())
            
            # Start chat session
            chat = self.client.chats.create(
                model='gemini-2.5-flash',
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=tools_list,
                    temperature=0.2
                )
            )
            
            # Send initial goal
            prompt = f"Goal to accomplish: {goal}\nBegin planning and execution."
            self.log("Sending goal to Gemini API...")
            response = chat.send_message(prompt)
            
            # Limit loop iterations to prevent infinite runaways
            max_turns = 15
            turn = 0
            
            while turn < max_turns:
                turn += 1
                self.log(f"Reasoning turn {turn}/{max_turns}...")
                
                # Check for tool calls
                tool_calls = response.function_calls
                if not tool_calls:
                    # Model returned text response without tool calls
                    text_content = response.text
                    self.log(f"Model response:\n{text_content}")
                    
                    if "goal" in text_content.lower() and ("accomplished" in text_content.lower() or "completed" in text_content.lower()):
                        self.status = "success"
                        self.log("Goal successfully completed!")
                        memory.record_turn("agent", text_content, thoughts="Goal accomplished.")
                        return
                        
                    # If model returned text but didn't finish, prompt it to continue or conclude
                    response = chat.send_message("Proceed with next steps or conclude if accomplished.")
                    continue
                
                # Process tool calls
                tool_responses = []
                for call in tool_calls:
                    name = call.name
                    args = call.args
                    self.log(f"Executing Tool '{name}' with arguments: {args}")
                    
                    if name in self.tool_map:
                        try:
                            # Run tool
                            result = self.tool_map[name](**args)
                            self.log(f"Tool '{name}' execution complete.")
                            
                            # Format response back to Gemini
                            tool_responses.append(
                                types.Part.from_function_response(
                                    name=name,
                                    response={"result": result}
                                )
                            )
                        except Exception as e:
                            self.log(f"Error invoking tool '{name}': {e}")
                            tool_responses.append(
                                types.Part.from_function_response(
                                    name=name,
                                    response={"result": f"Execution Error: {str(e)}"}
                                )
                            )
                    else:
                        self.log(f"Error: Tool '{name}' is not registered in VEGAS registry.")
                        tool_responses.append(
                            types.Part.from_function_response(
                                name=name,
                                response={"result": f"Error: Tool '{name}' not found."}
                            )
                        )
                
                # Send tool responses back to Gemini
                self.log("Sending tool results back to Gemini...")
                response = chat.send_message(tool_responses)
                
            self.status = "failed"
            self.log(f"Agent stopped: Exceeded maximum turn limit of {max_turns} without completing the goal.")
            
        except Exception as e:
            self.status = "failed"
            self.log(f"Execution crashed: {str(e)}")

# Global agent loop instance
agent_orchestrator = VegasAgentOrchestrator()
