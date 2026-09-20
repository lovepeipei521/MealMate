# app/agent/tools/common/websearch.py
"""
网络搜索 Tool

使用 You.com Search API 搜索互联网获取最新信息。
"""

import asyncio
import logging
from typing import Optional

from app.agent.tools.base import BaseTool
from app.agent.types import ToolResult

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    """
    网络搜索 Tool。

    使用 You.com Search API 搜索互联网获取最新信息。
    """

    name = "web_search"
    description = "搜索互联网获取最新信息。适合需要实时数据、新闻或外部来源时使用。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词或问题"},
            "max_results": {
                "type": "integer",
                "description": "返回结果数量 (1-20)",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    async def execute(
        self,
        query: str = "",
        max_results: int = 5,
        **kwargs,
    ) -> ToolResult:
        """执行网络搜索。"""
        if not query:
            return ToolResult(success=False, error="Query is required")

        try:
            from app.integrations.youcom import get_youcom_client
            from app.config import settings

            api_key = settings.web_search.api_key
            if not api_key:
                return ToolResult(
                    success=False,
                    error="Web search API key is not configured. Set YOUCOM_API_KEY in .env",
                )

            client = get_youcom_client(api_key=api_key)

            # Run blocking API call in thread pool
            def do_search():
                return client.search(query=query, count=min(max(1, max_results), 20))

            response = await asyncio.to_thread(do_search)

            if "error" in response:
                return ToolResult(success=False, error=response["error"])

            results = response.get("results", [])
            if not results:
                return ToolResult(success=True, data={"query": query, "results": [], "answer": None})

            # Format results
            formatted = []
            for item in results:
                formatted.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "content": item.get("snippet", ""),
                        "score": 0,
                    }
                )

            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": formatted,
                    "answer": None,
                },
            )

        except ImportError:
            return ToolResult(
                success=False,
                error="youcom package is not installed or app.integrations.youcom is not available",
            )
        except Exception as e:
            logger.exception(f"Web search failed: {e}")
            return ToolResult(success=False, error=f"Web search failed: {str(e)}")


__all__ = ["WebSearchTool"]
