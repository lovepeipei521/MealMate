# app/integrations/youcom/client.py
"""
You.com API Client for CookHero.

Provides Search and Research API integration:
- Search API: Real-time web search with title/URL/snippet
- Research API: Deep research with markdown report and citations
"""

import os
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

YOUCOM_SEARCH_URL = "https://ydc-index.io/v1/search"
YOUCOM_RESEARCH_URL = "https://ydc-index.io/v1/research"


class YoucomClient:
    """
    You.com API Client.

    Supports:
    - search(): Web search with results (title, url, snippets)
    - research(): Deep research with markdown report and citations
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize You.com client.

        Args:
            api_key: You.com API key. Falls back to YOUCOM_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("YOUCOM_API_KEY", "")
        self._session = requests.Session()

    def _get_headers(self) -> dict:
        return {
            "Accept": "application/json",
            "X-API-Key": self.api_key,
        }

    def search(self, query: str, count: int = 10) -> dict:
        """
        Perform web search via You.com Search API.

        Args:
            query: Search query string
            count: Number of results (1-20), default 10

        Returns:
            Dict with keys:
            - results: list of dicts with title, url, snippets
            - error: error message if failed
        """
        if not self.api_key:
            return {"error": "YOUCOM_API_KEY is not configured"}

        if not query or not query.strip():
            return {"error": "Search query cannot be empty"}

        headers = self._get_headers()
        payload = {"query": query, "count": min(max(count, 1), 20)}

        try:
            response = self._session.post(
                YOUCOM_SEARCH_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )
        except Exception as e:
            return {"error": f"You.com Search request failed: {e}"}

        if response.status_code == 429:
            return {"error": "You.com Search rate limit exceeded (429)"}
        if response.status_code == 401:
            return {"error": "You.com API Key is invalid or expired"}
        if response.status_code == 403:
            return {"error": "You.com API Key has insufficient permissions"}
        if response.status_code != 200:
            return {"error": f"You.com Search request failed (Status {response.status_code})"}

        try:
            data = response.json()
        except Exception:
            return {"error": "You.com Search returned non-JSON response"}

        results = data.get("results", [])
        if not results:
            return {"results": []}

        formatted = []
        for item in results[:count]:
            title = item.get("title", "")
            url = item.get("url", "")
            snippets = item.get("snippets", [])
            snippet = (
                snippets[0]
                if isinstance(snippets, list) and snippets
                else item.get("description", "")
            )
            formatted.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                }
            )

        return {"results": formatted}

    def research(self, query: str, research_effort: str = "standard") -> dict:
        """
        Perform deep research via You.com Research API.

        Args:
            query: Research topic or question
            research_effort: lite, standard, deep, or exhaustive

        Returns:
            Dict with keys:
            - content: Markdown-formatted research report
            - sources: list of citation dicts with title, url, snippets
            - error: error message if failed
        """
        if not self.api_key:
            return {"error": "YOUCOM_API_KEY is not configured"}

        if not query or not query.strip():
            return {"error": "Research query cannot be empty"}

        allowed = {"lite", "standard", "deep", "exhaustive"}
        if research_effort not in allowed:
            research_effort = "standard"

        headers = self._get_headers()
        payload = {"input": query, "research_effort": research_effort}

        try:
            response = self._session.post(
                YOUCOM_RESEARCH_URL,
                headers=headers,
                json=payload,
                timeout=120,
            )
        except Exception as e:
            return {"error": f"You.com Research request failed: {e}"}

        if response.status_code == 429:
            return {"error": "You.com Research rate limit exceeded (429)"}
        if response.status_code == 401:
            return {"error": "You.com API Key is invalid or expired"}
        if response.status_code == 403:
            return {"error": "You.com API Key has insufficient permissions"}
        if response.status_code != 200:
            return {"error": f"You.com Research request failed (Status {response.status_code})"}

        try:
            data = response.json()
        except Exception:
            return {"error": "You.com Research returned non-JSON response"}

        content = data.get("content", "")
        sources = data.get("sources", [])

        formatted_sources = []
        for source in sources:
            snippets = source.get("snippets", [])
            snippet = (
                snippets[0]
                if isinstance(snippets, list) and snippets
                else ""
            )
            formatted_sources.append(
                {
                    "title": source.get("title", "Unknown source"),
                    "url": source.get("url", ""),
                    "snippet": snippet,
                }
            )

        return {
            "content": content,
            "sources": formatted_sources,
        }


# Singleton instance
_youcom_client: Optional[YoucomClient] = None


def get_youcom_client(api_key: Optional[str] = None) -> YoucomClient:
    """Get or create the You.com client singleton."""
    global _youcom_client
    if _youcom_client is None:
        _youcom_client = YoucomClient(api_key=api_key)
    return _youcom_client


# Convenience singleton for backward compatibility
youcom_client = get_youcom_client()
