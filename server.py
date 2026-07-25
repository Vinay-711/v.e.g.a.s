"""
Server entry point for the Vegas Assistant.
Runs the FastMCP server over SSE.
"""

import os

from mcp.server.fastmcp import FastMCP
from vegas.config import config
from vegas.tools import register_all_tools
from vegas.prompts import register_all_prompts
from vegas.resources import register_all_resources
from vegas.skills.manager import skill_manager
from vegas.scheduler.engine import scheduler

def _mcp_port() -> int:
    """Read the daemon-compatible MCP port without failing on bad config."""
    try:
        port = int(os.getenv("VEGAS_MCP_PORT", "8000"))
    except ValueError:
        return 8000
    return port if 1 <= port <= 65535 else 8000


# Initialize FastMCP server with custom instructions
mcp = FastMCP(
    name=config.SERVER_NAME,
    host=os.getenv("VEGAS_MCP_HOST", "127.0.0.1"),
    port=_mcp_port(),
    instructions=(
        "You are VEGAS, the world's most advanced Autonomous AI Operating System. "
        "You run locally on the user's host machine as a system kernel. "
        "You can execute commands, edit code, register dynamic skills, and execute periodic jobs. "
        "Work autonomously to accomplish complex goals. Be concise, highly competent, and witty. "
        "When the user asks you to write code, fix a bug, build a feature, or do anything involving "
        "an actual codebase, use the dispatch_coding_task tool rather than writing full source files "
        "yourself in conversation. Ask which repo_path to use if it isn't obvious from context.\n\n"
        "Here are the tools available to you by category:\n"
        "- Web Research & API: search_web, fetch_url, get_world_news, open_world_monitor\n"
        "- System & Info: get_current_time, get_system_info\n"
        "- Utilities: format_json, word_count\n"
        "- Host Development: run_command, list_directory, view_file, write_file, edit_file, search_directory\n"
        "- Sandboxed AIOS Core: run_command_in_sandbox, execute_python_code_in_sandbox, submit_goal, "
        "get_agent_status, plan_goal, get_planner_status, execute_next_planner_step, execute_active_plan, "
        "get_execution_summary, create_new_skill, register_cron_job, list_memory, store_memory_fact, "
        "store_graph_relation, query_graph_relations, search_codebase_rag, delegate_workflow_task, "
        "propose_thoughts_for_goal, evaluate_thought_branch, get_best_thought_path\n"
        "- Web Browser: browse_and_extract, fill_web_form\n"
        "- Memory Management: remember, recall, whats_pending, confirm_task, cancel_task, send_email_stub\n"
        "- Coding Task Delegation: dispatch_coding_task\n"
        "- Google Workflow integration: list_todays_events, draft_email, morning_briefing\n"
        "- Cross-Device Mobile Ecosystem: list_connected_devices, execute_phone_command, send_phone_sms, make_phone_call, pair_wireless_device\n"
        "- Sandboxed File Access: read_file, list_directory, write_file, delete_file (restricted to sandbox root)\n\n"
        "Some tools require user confirmation before they take effect — you'll see this in the tool's return value. "
        "Relay the confirmation request to the user clearly and wait for their explicit 'confirm' or 'cancel' "
        "before proceeding. Never attempt to bypass or auto-confirm."
    )
)

# Bind MCP instance to dynamic skill compiler
skill_manager.mcp_server = mcp

# Register tools, prompts, and resources
register_all_tools(mcp)
register_all_prompts(mcp)
register_all_resources(mcp)

def main() -> None:
    """
    Main entry point for running the Vegas Assistant server.
    Starts the server using the SSE transport.
    """
    # Pre-load dynamically compiled skills
    print("VEGAS Core: Pre-loading custom skills...", flush=True)
    skills = skill_manager.load_existing_skills()
    if skills:
        print(f"VEGAS Core: Loaded skills: {', '.join(skills)}", flush=True)
        
    # Start scheduler
    scheduler.start()
    
    try:
        mcp.run(transport='sse')
    finally:
        print("VEGAS Core: Shutting down background processes...", flush=True)
        scheduler.stop()

if __name__ == "__main__":
    main()
