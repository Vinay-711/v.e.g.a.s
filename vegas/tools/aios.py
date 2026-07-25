"""
FastMCP tool interfaces for VEGAS AIOS Core components.
Exposes Sandboxed runtimes, Planner, Memory, Dynamic Skills compilation, and Scheduling to LLMs.
"""

from typing import List, Optional
import json
from vegas.core.kernel import kernel
from vegas.core.memory import memory
from vegas.core.planner import planner
from vegas.runtime.sandbox import sandbox
from vegas.skills.manager import skill_manager
from vegas.scheduler.engine import scheduler

def run_command_in_sandbox(command: str, cwd: str = ".") -> str:
    """
    Executes a shell command inside the sandboxed environment with guardrail protection.
    Use this to execute tests, compile programs, or manage workspace structures.

    Args:
        command: The terminal command statement.
        cwd: The working directory (defaults to ".").
    """
    res = sandbox.run_command(command, cwd=cwd)
    if res["error"]:
        return f"VEGAS Sandbox Execution Failed:\nError: {res['error']}\nStdout: {res['stdout']}\nStderr: {res['stderr']}"
    
    output = []
    if res["stdout"]:
        output.append(f"[STDOUT]\n{res['stdout']}")
    if res["stderr"]:
        output.append(f"[STDERR]\n{res['stderr']}")
    return f"Exit Code: {res['exit_code']}\n" + "\n".join(output)

def execute_python_code_in_sandbox(code: str) -> str:
    """
    Compiles and executes a raw Python block inside an isolated temporary file runtime.
    Use this to run algorithms, verify code logic, or execute script snippets.

    Args:
        code: The Python script string.
    """
    res = sandbox.execute_python_code(code)
    if res["error"]:
        return f"VEGAS Sandbox Python Failed:\nError: {res['error']}\nStdout: {res['stdout']}\nStderr: {res['stderr']}"
    
    output = []
    if res["stdout"]:
        output.append(f"[STDOUT]\n{res['stdout']}")
    if res["stderr"]:
        output.append(f"[STDERR]\n{res['stderr']}")
    return f"Exit Code: {res['exit_code']}\n" + "\n".join(output)

def submit_goal(goal: str) -> str:
    """
    Submits a complex goal to the Autonomous AI Agent ReAct loop.
    The agent will plan, run shell commands, write code, search the web, and verify success in the background.

    Args:
        goal: The goal description (e.g. 'Create a scraping script that fetches news from HN and saves it to a file').
    """
    from vegas.core.agent import agent_orchestrator
    res = agent_orchestrator.start_goal(goal)
    return res

def get_agent_status() -> str:
    """
    Returns the current execution state, goal, and logs of the active background autonomous agent.
    """
    from vegas.core.agent import agent_orchestrator
    res = agent_orchestrator.get_status()
    log_lines = "\n".join(agent_orchestrator.logs[-15:])
    return f"Status: {res['status']}\nGoal: {res['goal']}\nRecent Logs:\n{log_lines}"

def plan_goal(goal: str) -> str:
    """
    Creates a structured V.E.G.A.S. execution plan without executing any tools.

    Args:
        goal: The user objective to understand, break down, and route to agents.
    """
    res = kernel.process_system_command(goal)
    return json.dumps(res, indent=2)

def get_planner_status() -> str:
    """
    Returns the active planner state, registered specialist agents, and known plan count.
    """
    return json.dumps(planner.status(), indent=2)

def execute_next_planner_step() -> str:
    """
    Delegates the next active plan step to the selected specialist agent.
    The planner coordinates only; the assigned agent performs execution.
    """
    res = kernel.execute_next_plan_step()
    return json.dumps(res, indent=2)

def execute_active_plan(max_steps: int = 20) -> str:
    """
    Delegates active plan steps until completion, failure, confirmation, or max_steps.

    Args:
        max_steps: Hard cap on coordinated steps for this execution pass.
    """
    max_steps = max(1, min(int(max_steps), 50))
    res = planner.execute_all(kernel.executor, max_steps=max_steps)
    return json.dumps(res, indent=2)

def get_execution_summary() -> str:
    """
    Returns a concise summary of the active execution plan and latest result.
    """
    return planner.execution_summary()

def reflect_on_execution() -> str:
    """
    Triggers post-execution reflection on the active plan.
    The Brain analyzes execution history and extracts lessons learned,
    patterns detected, and recommendations for future runs.
    Results are persisted to memory automatically.
    """
    result = planner.post_execution_reflect()
    if result is None:
        return json.dumps({
            "status": "skipped",
            "message": "No active plan or Brain is unavailable for reflection."
        }, indent=2)
    return json.dumps({
        "status": "reflected",
        "lessons_learned": result.get("lessons_learned", []),
        "patterns_detected": result.get("patterns_detected", []),
        "recommendations": result.get("recommendations", []),
    }, indent=2)

def create_new_skill(name: str, code: str, docstring: str) -> str:
    """
    Compiles, tests, and injects a new Python function tool dynamically into the FastMCP registry.
    Ensures self-evolution of the operating system.

    Args:
        name: The name of the new tool (must be a valid Python identifier, e.g. 'fetch_github_repo').
        code: The Python source code containing the tool function definition.
        docstring: The system description of the tool parameters and return type.
    """
    res = skill_manager.create_skill(name, code, docstring)
    if res["success"]:
        return f"Self-Evolution Complete: Tool '{name}' has been compiled and injected into FastMCP registry at {res['path']}."
    return f"Self-Evolution Failed: {res['error']}"

def register_cron_job(job_id: str, interval_seconds: int, command: str) -> str:
    """
    Schedules a shell command to execute periodically in the background.

    Args:
        job_id: Unique label identifier for the job.
        interval_seconds: Execution frequency in seconds.
        command: The shell command to run periodically.
    """
    def job_wrapper():
        sandbox.run_command(command)
        
    scheduler.register_job(job_id, interval_seconds, job_wrapper)
    return f"Job '{job_id}' registered successfully to run every {interval_seconds}s."

def list_memory(section: str = "semantic") -> str:
    """
    Queries the persistent episodic, semantic, or working memory of VEGAS.

    Args:
        section: Memory category ('episodic', 'semantic', 'working').
    """
    if section == "episodic":
        history = memory.get_conversation_history(30)
        return json.dumps(history, indent=2)
    elif section == "working":
        return json.dumps(memory.data["working"], indent=2)
    else:
        return json.dumps(memory.data["semantic"], indent=2)

def store_memory_fact(key: str, value: str) -> str:
    """
    Stores a key-value semantic fact or snippet in the database.

    Args:
        key: Unique dictionary lookup name.
        value: Fact or text snippet string.
    """
    memory.store_fact(key, value)
    return f"Fact '{key}' successfully recorded to semantic memory database."

from vegas.core.planner import tree_planner
from vegas.core.collaboration import collaboration

def store_graph_relation(subject: str, predicate: str, obj: str) -> str:
    """
    Stores a semantic link/relation (subject -> predicate -> object) in the Knowledge Graph.
    Use this to build structural links between files, dependencies, and objectives.

    Args:
        subject: The starting node entity.
        predicate: The relationship label.
        obj: The target node entity.
    """
    memory.store_graph_link(subject, predicate, obj)
    return f"Knowledge Graph link successfully recorded: '{subject}' --({predicate})--> '{obj}'"

def query_graph_relations(node: str) -> str:
    """
    Queries all connection triples matching a node name in the Knowledge Graph.

    Args:
        node: The entity name to look up.
    """
    res = memory.query_graph_relations(node)
    return json.dumps(res, indent=2)

def search_codebase_rag(query: str, workspace_path: str = ".") -> str:
    """
    Performs local Codebase RAG context search over python, md, and configuration files.

    Args:
        query: Semantic query or keyword search string.
        workspace_path: Workspace directory path (defaults to ".").
    """
    res = memory.query_codebase_rag(query, workspace_path)
    return json.dumps(res, indent=2)

def delegate_workflow_task(agent_role: str, task: str) -> str:
    """
    Delegates a specialized subtask to a dedicated agent profile (e.g. 'developer', 'researcher').

    Args:
        agent_role: The role name.
        task: The task description.
    """
    res = collaboration.delegate_task(agent_role, task)
    return f"Delegation Result from '{agent_role}':\n{res}"

def propose_thoughts_for_goal(parent_id: str, thoughts: List[str]) -> str:
    """
    Registers parallel thought branches stemming from a parent node in the Tree of Thoughts (ToT) planner.

    Args:
        parent_id: The ID of the parent thought node (e.g. 'root').
        thoughts: List of thought option descriptions.
    """
    res = tree_planner.propose_thoughts(parent_id, thoughts)
    return f"Thoughts proposed. Registered IDs: {res}"

def evaluate_thought_branch(node_id: str, score: float, feedback: str = "") -> str:
    """
    Evaluates and sets a score for a thought branch (0.0 = failure, 1.0 = optimal).

    Args:
        node_id: The thought node ID.
        score: Score between 0.0 and 1.0.
        feedback: Notes/reflection feedback.
    """
    tree_planner.evaluate_thought(node_id, score, feedback)
    return f"Thought branch '{node_id}' evaluated with score {score}."

def get_best_thought_path() -> str:
    """
    Queries the optimal thought trajectory in the Tree of Thoughts.
    """
    res = tree_planner.get_best_thought_path()
    return " -> ".join(res)

def register(mcp) -> None:
    """
    Registers AIOS system tools.
    """
    mcp.tool()(run_command_in_sandbox)
    mcp.tool()(execute_python_code_in_sandbox)
    mcp.tool()(submit_goal)
    mcp.tool()(get_agent_status)
    mcp.tool()(plan_goal)
    mcp.tool()(get_planner_status)
    mcp.tool()(execute_next_planner_step)
    mcp.tool()(execute_active_plan)
    mcp.tool()(get_execution_summary)
    mcp.tool()(reflect_on_execution)
    mcp.tool()(create_new_skill)
    mcp.tool()(register_cron_job)
    mcp.tool()(list_memory)
    mcp.tool()(store_memory_fact)
    mcp.tool()(store_graph_relation)
    mcp.tool()(query_graph_relations)
    mcp.tool()(search_codebase_rag)
    mcp.tool()(delegate_workflow_task)
    mcp.tool()(propose_thoughts_for_goal)
    mcp.tool()(evaluate_thought_branch)
    mcp.tool()(get_best_thought_path)
