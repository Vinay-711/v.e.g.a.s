"""
Browser Agent for VEGAS AIOS.

Owns web search, scraping, form automation, page extraction, and web research.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from vegas.agents.base import AgentResult, BaseAgent
from vegas.tools.browser import browse_and_extract, fill_web_form
from vegas.tools.web import fetch_url, get_world_news, open_in_browser, search_web


class BrowserAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Browser Agent",
            role="browser",
            description="Navigates websites, extracts page text, searches the web, and fills forms using Playwright.",
        )
        self.register_tool("browse_and_extract", browse_and_extract)
        self.register_tool("fill_web_form", fill_web_form)
        self.register_tool("search_web", search_web)
        self.register_tool("fetch_url", fetch_url)
        self.register_tool("get_world_news", get_world_news)
        self.register_tool("open_in_browser", open_in_browser)

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        start_time = time.time()
        lowered = task.lower()

        try:
            if "news" in lowered:
                output = self.tools["get_world_news"]()
            elif "search" in lowered:
                output = self.tools["search_web"](task)
            elif "http://" in task or "https://" in task:
                # Extract URL from task string
                import re
                urls = re.findall(r"https?://\S+", task)
                url = urls[0] if urls else task
                if "fill" in lowered or "form" in lowered:
                    output = self.tools["fill_web_form"](url, {})
                else:
                    output = self.tools["browse_and_extract"](url)
            else:
                output = self.tools["search_web"](task)

            duration = (time.time() - start_time) * 1000
            status = "failed" if "error" in output.lower() or "failed" in output.lower() else "success"
            return AgentResult(
                agent_role=self.role,
                status=status,
                result=output,
                duration_ms=duration,
            )
        except Exception as e:
            return AgentResult(
                agent_role=self.role,
                status="failed",
                result=f"BrowserAgent execution error: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
            )
