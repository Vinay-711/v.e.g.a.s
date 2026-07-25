"""
Memory Agent for VEGAS AIOS.

Owns episodic, semantic, knowledge graph, and working memory persistence and recall.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from vegas.agents.base import AgentResult, BaseAgent
from vegas.core.memory import memory


class MemoryAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Memory Agent",
            role="memory",
            description="Stores and recalls episodic turns, semantic facts, knowledge graph triples, and working execution context.",
        )
        self.register_tool("store_fact", memory.store_fact)
        self.register_tool("retrieve_fact", memory.retrieve_fact)
        self.register_tool("search_facts", memory.search_facts)
        self.register_tool("record_turn", memory.record_turn)
        self.register_tool("store_graph_link", memory.store_graph_link)
        self.register_tool("query_graph_relations", memory.query_graph_relations)

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        start_time = time.time()
        ctx = context or {}
        lowered = task.lower()

        try:
            if "search" in lowered or "recall" in lowered or "find" in lowered:
                facts = self.tools["search_facts"](task)
                graph = self.tools["query_graph_relations"](task)
                output = f"Found {len(facts)} semantic fact(s) and {len(graph)} graph relation(s)."
            else:
                # Store execution context or fact
                key = ctx.get("key", f"context:{int(time.time())}")
                value = ctx.get("value", {"task": task, "context": ctx})
                self.tools["store_fact"](key, value)
                output = f"Persisted memory fact under key '{key}'."

            duration = (time.time() - start_time) * 1000
            return AgentResult(
                agent_role=self.role,
                status="success",
                result=output,
                duration_ms=duration,
            )
        except Exception as e:
            return AgentResult(
                agent_role=self.role,
                status="failed",
                result=f"MemoryAgent execution error: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
            )
