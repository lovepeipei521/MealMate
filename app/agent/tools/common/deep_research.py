# app/agent/tools/common/deep_research.py
"""
深度研究 Tool

使用 You.com Research API 进行深度研究，返回结构化报告和引用来源。
"""

import asyncio
import logging
from typing import Optional

from app.agent.tools.base import BaseTool
from app.agent.types import ToolResult

logger = logging.getLogger(__name__)


class DeepResearchTool(BaseTool):
    """
    深度研究 Tool。

    使用 You.com Research API 进行深度研究，适合需要深入分析复杂问题。
    支持四种研究深度：lite, standard, deep, exhaustive。
    """

    name = "deep_research"
    description = "对复杂问题进行深度研究，返回结构化报告和引用来源。适合需要全面分析、多角度探讨的问题。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "研究主题或问题"},
            "research_effort": {
                "type": "string",
                "enum": ["lite", "standard", "deep", "exhaustive"],
                "default": "standard",
                "description": "研究深度：lite（快速）、standard（标准）、deep（深入）、exhaustive（全面）",
            },
        },
        "required": ["query"],
    }

    async def execute(
        self,
        query: str = "",
        research_effort: str = "standard",
        **kwargs,
    ) -> ToolResult:
        """执行深度研究。"""
        if not query:
            return ToolResult(success=False, error="Query is required")

        try:
            from app.integrations.youcom import get_youcom_client
            from app.config import settings

            api_key = settings.web_search.api_key
            if not api_key:
                return ToolResult(
                    success=False,
                    error="Deep research API key is not configured. Set YOUCOM_API_KEY in .env",
                )

            client = get_youcom_client(api_key=api_key)

            # Run blocking API call in thread pool
            def do_research():
                return client.research(query=query, research_effort=research_effort)

            response = await asyncio.to_thread(do_research)

            if "error" in response:
                return ToolResult(success=False, error=response["error"])

            content = response.get("content", "")
            sources = response.get("sources", [])

            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "research_effort": research_effort,
                    "content": content,
                    "sources": sources,
                },
            )

        except ImportError:
            return ToolResult(
                success=False,
                error="app.integrations.youcom is not available",
            )
        except Exception as e:
            logger.exception(f"Deep research failed: {e}")
            return ToolResult(success=False, error=f"Deep research failed: {str(e)}")


__all__ = ["DeepResearchTool"]
