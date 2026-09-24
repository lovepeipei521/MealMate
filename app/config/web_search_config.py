# app/config/web_search_config.py
"""
Web Search configuration for MealMate.
Uses You.com Search API for web search.
"""

from typing import Optional

from pydantic import BaseModel


class WebSearchConfig(BaseModel):
    """
    Configuration for web search functionality using You.com Search API.
    """

    enabled: bool = True
    api_key: Optional[str] = None  # Loaded from .env (YOUCOM_API_KEY)
    max_results: int = 5


class DeepResearchConfig(BaseModel):
    """
    Configuration for deep research functionality.

    Tavily Research is the default provider. You.com Research remains available
    as a backward-compatible fallback.
    """

    enabled: bool = True
    provider: str = "tavily"  # tavily, youcom
    model: Optional[str] = None  # Tavily override: mini, pro, auto
    research_effort: str = "standard"  # lite, standard, deep, exhaustive
    timeout_seconds: int = 300
    poll_interval_seconds: float = 2.0
    api_key: Optional[str] = None
