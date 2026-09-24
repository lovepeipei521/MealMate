# app/agent/tools/common/deep_research.py
"""
深度研究 Tool

默认使用 Tavily Research API，也保留 You.com Research API 兼容支持。
返回结构化报告和引用来源。
"""

import asyncio
import logging

from app.agent.tools.base import BaseTool
from app.agent.types import ToolResult

logger = logging.getLogger(__name__)


class DeepResearchTool(BaseTool):
    """
    深度研究 Tool。

    默认使用 Tavily Research API，适合需要深入分析复杂问题。
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
            from app.config import settings

            config = settings.deep_research
            if not config.enabled:
                return ToolResult(
                    success=False,
                    error="Deep research is disabled in config.yml",
                )

            provider = str(config.provider or "tavily").strip().lower()
            effort = str(research_effort or config.research_effort or "standard").strip().lower()

            if provider == "tavily":
                if not config.api_key:
                    return ToolResult(
                        success=False,
                        error="Deep research API key is not configured. Set TAVILY_API_KEY in .env",
                    )

                from app.integrations.tavily import get_tavily_research_client

                client = get_tavily_research_client(
                    api_key=config.api_key,
                    model=config.model,
                    timeout_seconds=config.timeout_seconds,
                    poll_interval_seconds=config.poll_interval_seconds,
                )
            elif provider == "youcom":
                if not config.api_key:
                    return ToolResult(
                        success=False,
                        error="Deep research API key is not configured. Set YOUCOM_API_KEY in .env",
                    )

                from app.integrations.youcom import get_youcom_client

                client = get_youcom_client(api_key=config.api_key)
            else:
                return ToolResult(
                    success=False,
                    error=(
                        f"Unsupported deep research provider: {provider}. "
                        "Use 'tavily' or 'youcom'."
                    ),
                )

            logger.info(
                "Deep research request: provider=%s effort=%s query=%s",
                provider,
                effort,
                query[:120],
            )

            response = await asyncio.to_thread(
                client.research,
                query=query,
                research_effort=effort,
            )

            if "error" in response:
                return ToolResult(success=False, error=response["error"])

            content = response.get("content", "")
            sources = response.get("sources", [])

            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "research_effort": effort,
                    "provider": provider,
                    "content": content,
                    "sources": sources,
                },
            )

        except ImportError as exc:
            logger.exception("Deep research integration import failed")
            return ToolResult(
                success=False,
                error=f"Deep research integration is not available: {exc}",
            )
        except Exception as exc:
            logger.exception("Deep research failed: %s", exc)
            return ToolResult(success=False, error=f"Deep research failed: {exc}")


__all__ = ["DeepResearchTool"]
