"""
Persistent Memory Engine for VEGAS AIOS.

Manages:
  - Dialogue & Conversation Memory (Episodic)
  - Project Architecture & Tech Stack Memory
  - Coding Preferences & Style Rules
  - Tool Execution Analytics & History
  - Knowledge Graph & Semantic Fact Memory
  - Semantic Retrieval (TF-IDF / Vector ranking across stores)
  - Context Awareness Prompt Synthesis
  - Long-Term Summarization
"""

from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import vegas.memory as sqlite_mem


class MemoryEngine:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.db_path = os.path.join(base_dir, ".vegas_memory.json")
        else:
            self.db_path = db_path

        self.data = {
            "episodic": [],
            "semantic": {},
            "knowledge_graph": [],
            "working": {
                "active_tasks": [],
                "current_objective": "",
                "variables": {},
            },
        }
        self.load()

    def load(self):
        """Loads in-memory cache state from disk."""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    disk_data = json.load(f)
                    for key in ["episodic", "semantic", "knowledge_graph", "working"]:
                        if key in disk_data:
                            self.data[key] = disk_data[key]
            except Exception as e:
                print(f"MemoryEngine Error: Failed to read JSON database: {e}", flush=True)

    def save(self):
        """Saves in-memory cache state to disk."""
        def _safe_default(obj):
            """Fallback encoder for objects that aren't JSON-serializable."""
            if hasattr(obj, "serialize"):
                return obj.serialize()
            if hasattr(obj, "__dict__"):
                return obj.__dict__
            return str(obj)

        try:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, default=_safe_default)
        except Exception as e:
            print(f"MemoryEngine Error: Failed to write JSON database: {e}", flush=True)

    # ------------------------------------------------------------------
    # Dialogue & Conversation Memory
    # ------------------------------------------------------------------

    def record_turn(self, role: str, message: str, thoughts: Optional[str] = None, session_id: str = "default_session"):
        """Records a user/agent chat message in both in-memory cache and SQLite."""
        turn = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "message": message,
            "thoughts": thoughts,
            "session_id": session_id,
        }
        self.data["episodic"].append(turn)
        if len(self.data["episodic"]) > 200:
            self.data["episodic"].pop(0)
        self.save()

        # Persist to SQLite
        try:
            sqlite_mem.record_conversation_turn(session_id=session_id, role=role, message=message, thoughts=thoughts)
        except Exception:
            pass

    def get_conversation_history(self, limit: int = 20, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns recent dialogue turns."""
        try:
            sqlite_turns = sqlite_mem.get_session_turns(session_id=session_id, limit=limit)
            if sqlite_turns:
                return sqlite_turns
        except Exception:
            pass
        return self.data["episodic"][-limit:]

    # ------------------------------------------------------------------
    # Project Memory
    # ------------------------------------------------------------------

    def store_project_info(self, project_path: str, name: str, tech_stack: str = "", architecture_summary: str = ""):
        """Stores repository structure and tech stack facts."""
        try:
            sqlite_mem.store_project_memory(project_path, name, tech_stack, architecture_summary)
        except Exception:
            pass
        self.store_fact(f"project:{project_path}", {
            "name": name,
            "tech_stack": tech_stack,
            "architecture_summary": architecture_summary,
        })

    def get_project_info(self, project_path: str) -> Optional[Dict[str, Any]]:
        """Retrieves project memory."""
        try:
            info = sqlite_mem.get_project_memory(project_path)
            if info:
                return info
        except Exception:
            pass
        return self.retrieve_fact(f"project:{project_path}")

    # ------------------------------------------------------------------
    # Coding Preferences
    # ------------------------------------------------------------------

    def set_coding_pref(self, key: str, value: str, category: str = "general", confidence: float = 1.0):
        """Stores user coding style and formatting preferences."""
        try:
            sqlite_mem.set_coding_preference(key, value, category, confidence)
        except Exception:
            pass
        self.store_fact(f"pref:{category}:{key}", {"value": value, "confidence": confidence})

    def get_coding_prefs(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves user coding preferences."""
        try:
            prefs = sqlite_mem.get_coding_preferences(category)
            if prefs:
                return prefs
        except Exception:
            pass
        results = []
        for k, v in self.data["semantic"].items():
            if k.startswith("pref:"):
                results.append({"key": k, "value": str(v.get("value")), "category": "general"})
        return results

    # ------------------------------------------------------------------
    # Tool Execution Analytics & History
    # ------------------------------------------------------------------

    def record_tool_execution(self, tool_name: str, agent_role: str, status: str, duration_ms: float = 0.0, result_summary: str = ""):
        """Logs a tool execution into execution history."""
        try:
            sqlite_mem.log_tool_execution(tool_name, agent_role, status, duration_ms, result_summary)
        except Exception:
            pass

    def get_recent_tool_stats(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Returns recent tool execution stats."""
        try:
            return sqlite_mem.get_tool_performance_stats(limit=limit)
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Semantic Memory & Knowledge Graph
    # ------------------------------------------------------------------

    def store_fact(self, key: str, value: Any):
        """Stores a persistent fact, configuration item, or code snippet."""
        self.data["semantic"][key] = {
            "value": value,
            "updated_at": datetime.now().isoformat(),
        }
        self.save()

    def retrieve_fact(self, key: str) -> Optional[Any]:
        """Retrieves a stored fact."""
        item = self.data["semantic"].get(key)
        return item["value"] if item else None

    def search_facts(self, query: str) -> List[Dict[str, Any]]:
        """Performs keyword matching over semantic facts."""
        results = []
        q = query.lower()
        for key, item in self.data["semantic"].items():
            val_str = str(item["value"]).lower()
            if q in key.lower() or q in val_str:
                results.append({"key": key, "value": item["value"], "updated_at": item["updated_at"]})
        return results

    def store_graph_link(self, subject: str, predicate: str, obj: str):
        """Stores a semantic relation (triple) in the Knowledge Graph."""
        link = {
            "subject": subject.strip(),
            "predicate": predicate.strip(),
            "object": obj.strip(),
            "timestamp": datetime.now().isoformat(),
        }
        if "knowledge_graph" not in self.data:
            self.data["knowledge_graph"] = []
        exists = any(
            e["subject"] == link["subject"] and e["predicate"] == link["predicate"] and e["object"] == link["object"]
            for e in self.data["knowledge_graph"]
        )
        if not exists:
            self.data["knowledge_graph"].append(link)
            self.save()

    def query_graph_relations(self, node: str) -> List[Dict[str, Any]]:
        """Queries all triples relating to a specific node."""
        results = []
        n = node.strip().lower()
        if "knowledge_graph" not in self.data:
            self.data["knowledge_graph"] = []
        for link in self.data["knowledge_graph"]:
            if n in link["subject"].lower() or n in link["object"].lower() or n in link["predicate"].lower():
                results.append(link)
        return results

    # ------------------------------------------------------------------
    # Semantic Retrieval Engine (Vector / BM25 Ranking across all stores)
    # ------------------------------------------------------------------

    def semantic_search(self, query: str, limit: int = 5, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Ranks relevance across conversations, project facts, coding preferences,
        tool history, semantic facts, and long-term summaries.
        """
        terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
        if not terms:
            return []

        candidates = []

        # 1. Search Semantic Facts
        for k, v in self.data["semantic"].items():
            text = f"{k} {json.dumps(v.get('value', ''))}"
            score = self._score_text(terms, text)
            if score > 0:
                candidates.append({"store": "semantic_facts", "key": k, "content": str(v.get("value")), "score": score * 1.5})

        # 2. Search Conversations
        history = self.get_conversation_history(limit=50)
        for turn in history:
            text = f"{turn.get('role')} {turn.get('message', '')} {turn.get('thoughts', '')}"
            score = self._score_text(terms, text)
            if score > 0:
                candidates.append({"store": "conversations", "key": turn.get("timestamp"), "content": turn.get("message"), "score": score})

        # 3. Search Long-Term Summaries
        try:
            summaries = sqlite_mem.get_long_term_summaries(limit=20)
            for s in summaries:
                text = f"{s.get('scope')} {s.get('summary_text')}"
                score = self._score_text(terms, text)
                if score > 0:
                    candidates.append({"store": "long_term_summaries", "key": s.get("id"), "content": s.get("summary_text"), "score": score * 2.0})
        except Exception:
            pass

        # 4. Search Coding Preferences
        prefs = self.get_coding_prefs()
        for p in prefs:
            text = f"{p.get('key')} {p.get('category')} {p.get('value')}"
            score = self._score_text(terms, text)
            if score > 0:
                candidates.append({"store": "coding_preferences", "key": p.get("key"), "content": f"{p.get('key')}: {p.get('value')}", "score": score * 1.2})

        # Filter by category if specified
        if category:
            candidates = [c for c in candidates if c["store"] == category]

        # Sort descending by score
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:limit]

    def _score_text(self, terms: List[str], text: str) -> float:
        lowered = text.lower()
        score = 0.0
        for term in terms:
            count = lowered.count(term)
            if count > 0:
                # TF-IDF style logarithmic scaling
                score += (1.0 + math.log(count))
        return score

    # ------------------------------------------------------------------
    # Context Awareness Prompt Generator
    # ------------------------------------------------------------------

    def build_context_block(self, query: str, project_path: Optional[str] = None) -> str:
        """
        Synthesizes user coding preferences, project memory, relevant past search,
        and tool history into a single enriched context block for the Planner.
        """
        sections = []

        # 1. User Coding Preferences
        prefs = self.get_coding_prefs()
        if prefs:
            pref_lines = [f"- {p.get('key')}: {p.get('value')}" for p in prefs[:5]]
            sections.append("### User Coding Preferences\n" + "\n".join(pref_lines))

        # 2. Project Memory
        if project_path:
            p_info = self.get_project_info(project_path)
            if p_info:
                sections.append(
                    f"### Project Memory [{p_info.get('name')}]\n"
                    f"- Tech Stack: {p_info.get('tech_stack', 'Unknown')}\n"
                    f"- Architecture: {p_info.get('architecture_summary', 'N/A')}"
                )

        # 3. Semantic Memory Matches
        matches = self.semantic_search(query, limit=3)
        if matches:
            match_lines = [f"- [{m['store']}] {m['content'][:150]}" for m in matches]
            sections.append("### Relevant Past Memories\n" + "\n".join(match_lines))

        # 4. Working Objective
        obj = self.get_objective()
        if obj:
            sections.append(f"### Current Objective\n{obj}")

        return "\n\n".join(sections) if sections else "No prior context stored."

    # ------------------------------------------------------------------
    # Long-Term Summarization
    # ------------------------------------------------------------------

    def summarize_long_term_memory(self, scope: str = "session") -> str:
        """Consolidates conversation dialogue turns into a persistent milestone summary."""
        turns = self.get_conversation_history(limit=30)
        if not turns:
            return "No conversation history available to summarize."

        dialogue = "\n".join([f"{t.get('role')}: {t.get('message')}" for t in turns])
        summary_text = f"Consolidated {len(turns)} turn(s). Recent focus: {dialogue[-300:]}"

        try:
            summary_id = sqlite_mem.store_long_term_summary(scope=scope, summary_text=summary_text)
            return f"Long-term summary stored (ID: {summary_id})."
        except Exception:
            return summary_text

    # ------------------------------------------------------------------
    # Codebase RAG & Working Memory
    # ------------------------------------------------------------------

    def query_codebase_rag(self, query: str, workspace_path: str = ".") -> List[Dict[str, Any]]:
        abs_workspace = os.path.abspath(workspace_path)
        chunks = []
        terms = [t.lower() for t in query.split() if len(t) > 2]
        if not terms:
            return []

        for root, dirs, files in os.walk(abs_workspace):
            if any(folder in root for folder in [".git", "__pycache__", ".venv", "node_modules", "dist"]):
                continue
            for file in files:
                if not file.endswith((".py", ".md", ".toml", ".txt", ".json", ".yaml", ".sh")):
                    continue
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    lines = content.splitlines()
                    chunk_size = 20
                    for i in range(0, len(lines), chunk_size):
                        chunk_lines = lines[i:i + chunk_size]
                        chunk_text = "\n".join(chunk_lines)
                        score = sum(chunk_text.lower().count(term) for term in terms)
                        if score > 0:
                            chunks.append({
                                "file": os.path.relpath(file_path, abs_workspace),
                                "start_line": i + 1,
                                "content": chunk_text,
                                "score": score,
                            })
                except Exception:
                    pass

        chunks.sort(key=lambda x: x["score"], reverse=True)
        return chunks[:5]

    def set_objective(self, objective: str):
        self.data["working"]["current_objective"] = objective
        self.save()

    def get_objective(self) -> str:
        return self.data["working"].get("current_objective", "")

    def update_task_list(self, tasks: List[str]):
        self.data["working"]["active_tasks"] = tasks
        self.save()

    def get_tasks(self) -> List[str]:
        return self.data["working"].get("active_tasks", [])

    def set_variable(self, name: str, val: Any):
        self.data["working"]["variables"][name] = val
        self.save()

    def get_variable(self, name: str) -> Optional[Any]:
        return self.data["working"]["variables"].get(name)


# Global memory registry
memory = MemoryEngine()
