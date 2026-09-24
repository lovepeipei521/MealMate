# app/integrations/tavily/__init__.py
"""
Tavily Research API integration for MealMate.
"""

from app.integrations.tavily.client import (
    TavilyResearchClient,
    get_tavily_research_client,
)

__all__ = ["TavilyResearchClient", "get_tavily_research_client"]
