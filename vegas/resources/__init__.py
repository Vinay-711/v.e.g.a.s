"""
Resource definitions for the Vegas Assistant.
Exposes register_all_resources(mcp) to register resources with FastMCP.
"""

import json

def get_vegas_info() -> str:
    """
    Returns a short JSON description of VEGAS, its capabilities, and registered tools.
    """
    info = {
        "name": "vegas-assistant",
        "version": "0.1.0",
        "description": "Versatile Executive Guardian & Assistant System",
        "available_tools": [
            "search_web",
            "fetch_url",
            "get_world_news",
            "open_world_monitor",
            "get_current_time",
            "get_system_info",
            "format_json",
            "word_count",
            "run_command",
            "list_directory",
            "view_file",
            "write_file",
            "edit_file",
            "search_directory",
            "run_command_in_sandbox",
            "execute_python_code_in_sandbox",
            "submit_goal",
            "get_agent_status",
            "plan_goal",
            "get_planner_status",
            "execute_next_planner_step",
            "execute_active_plan",
            "get_execution_summary",
            "create_new_skill",
            "register_cron_job",
            "list_memory",
            "store_memory_fact",
            "scan_page_elements",
            "store_graph_relation",
            "query_graph_relations",
            "search_codebase_rag",
            "delegate_workflow_task",
            "propose_thoughts_for_goal",
            "evaluate_thought_branch",
            "get_best_thought_path",
            "browse_and_extract",
            "fill_web_form",
            "remember",
            "recall",
            "whats_pending",
            "confirm_task",
            "cancel_task",
            "send_email_stub",
            "dispatch_coding_task",
            "list_todays_events",
            "draft_email",
            "morning_briefing",
            "read_file",
            "delete_file",
            "git_status",
            "git_diff",
            "git_commit",
            "git_create_branch",
            "set_system_volume",
            "play_pause_media",
            "speak_text",
            "query_sqlite",
            "make_http_request"
        ]
    }
    return json.dumps(info, indent=2)

def register_all_resources(mcp) -> None:
    """
    Registers the resource endpoints with the provided FastMCP server instance.
    """
    mcp.resource("vegas://info")(get_vegas_info)
