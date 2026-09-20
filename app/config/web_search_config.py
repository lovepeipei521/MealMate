# app/config/web_search_config.py
"""
Web Search configuration for CookHero.
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
    Configuration for deep research functionality using You.com Research API.
    """

    enabled: bool = True
    research_effort: str = "standard"  # lite, standard, deep, exhaustive
