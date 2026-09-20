# app/tools/__init__.py
"""
Tools module for MealMate.
Contains external service integrations like web search.
"""

from app.tools.web_search import (
    WebSearchDecision,
    WebSearchResult,
    WebSearchParams,
    WebSearchTool,
    web_search_tool,
)

__all__ = [
    "WebSearchDecision",
    "WebSearchResult",
    "WebSearchParams",
    "WebSearchTool",
    "web_search_tool",
]
