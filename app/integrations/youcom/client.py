# app/integrations/youcom/client.py
"""
You.com API Client for MealMate.

Provides Search and Research API integration:
- Search API: Real-time web search with title/URL/snippet
- Research API: Deep research with markdown report and citations
"""

import os
import logging
from typing import Any, Optional

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

    @staticmethod
    def _error_detail(response: requests.Response) -> str:
        """Return a short response body excerpt for troubleshooting."""
        detail = (response.text or "").strip().replace("\n", " ")
        return f": {detail[:300]}" if detail else ""

    def _request_error(self, api_name: str, response: requests.Response) -> dict:
        """Build a consistent, diagnosable API error payload."""
        detail = self._error_detail(response)

        if response.status_code == 401:
            reason = "API Key is invalid or expired"
        elif response.status_code == 403:
            reason = "API Key has insufficient permissions or the request is forbidden"
        elif response.status_code == 429:
            reason = "rate limit exceeded"
        else:
            reason = "request failed"

        return {
            "error": (
                f"You.com {api_name} {reason} "
                f"(Status {response.status_code}){detail}"
            )
        }

    @staticmethod
    def _extract_snippet(item: Any) -> str:
        """Extract a readable snippet from current and legacy response fields."""
        if not isinstance(item, dict):
            return ""

        candidates = [item.get("snippets")]

        contents = item.get("contents")
        if isinstance(contents, dict):
            candidates.extend(
                [
                    contents.get("highlights"),
                    contents.get("snippets"),
                ]
            )

        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
            if not isinstance(candidate, list):
                continue

            for value in candidate:
                if isinstance(value, str) and value.strip():
                    return value.strip()
                if isinstance(value, dict):
                    text = (
                        value.get("text")
                        or value.get("content")
                        or value.get("snippet")
                    )
                    if isinstance(text, str) and text.strip():
                        return text.strip()

        description = item.get("description") or item.get("snippet") or ""
        return description.strip() if isinstance(description, str) else str(description)

    @classmethod
    def _format_items(cls, items: Any, count: Optional[int] = None) -> list[dict]:
        """Normalize You.com result items and remove duplicate URLs."""
        if isinstance(items, dict):
            flattened = []
            for key in ("web", "news"):
                value = items.get(key)
                if isinstance(value, list):
                    flattened.extend(value)
            items = flattened

        if not isinstance(items, list):
            return []

        formatted = []
        seen = set()

        for item in items:
            if not isinstance(item, dict):
                continue

            title = item.get("title") or "Unknown source"
            url = item.get("url") or ""
            snippet = cls._extract_snippet(item)
            key = url or f"{title}:{snippet}"

            if key in seen:
                continue
            seen.add(key)

            formatted.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                }
            )

            if count is not None and len(formatted) >= count:
                break

        return formatted

    @staticmethod
    def _extract_search_items(data: Any) -> list:
        """Support current nested results and the legacy top-level list format."""
        if not isinstance(data, dict):
            return []

        raw_results = data.get("results")

        if isinstance(raw_results, dict):
            items = []
            for key in ("web", "news"):
                value = raw_results.get(key)
                if isinstance(value, list):
                    items.extend(value)
            return items

        if isinstance(raw_results, list):
            return raw_results

        # Tolerate providers that expose web/news directly at the top level.
        items = []
        for key in ("web", "news"):
            value = data.get(key)
            if isinstance(value, list):
                items.extend(value)
        return items

    def search(self, query: str, count: int = 10) -> dict:
        """
        Perform web search via You.com Search API.

        Args:
            query: Search query string
            count: Number of results (1-20), default 10

        Returns:
            Dict with keys:
            - results: list of dicts with title, url, snippet
            - error: error message if failed
        """
        if not self.api_key:
            return {"error": "YOUCOM_API_KEY is not configured"}

        if not query or not query.strip():
            return {"error": "Search query cannot be empty"}

        count = min(max(count, 1), 20)
        headers = self._get_headers()
        payload = {"query": query, "count": count}

        try:
            response = self._session.post(
                YOUCOM_SEARCH_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )
        except Exception as e:
            return {"error": f"You.com Search request failed: {e}"}

        if response.status_code != 200:
            return self._request_error("Search", response)

        try:
            data = response.json()
        except Exception:
            return {"error": "You.com Search returned non-JSON response"}

        return {"results": self._format_items(self._extract_search_items(data), count)}

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

        if response.status_code != 200:
            return self._request_error("Research", response)

        try:
            data = response.json()
        except Exception:
            return {"error": "You.com Research returned non-JSON response"}

        if not isinstance(data, dict):
            return {"error": "You.com Research returned an unexpected response"}

        output = data.get("output")
        if not isinstance(output, dict):
            output = {}

        content = output.get("content") or data.get("content") or ""
        if not isinstance(content, str):
            content = str(content)

        sources = output.get("sources") or data.get("sources") or []
        return {
            "content": content,
            "sources": self._format_items(sources),
        }


# Singleton instance
_youcom_client: Optional[YoucomClient] = None
youcom_client: Optional[YoucomClient] = None


def get_youcom_client(api_key: Optional[str] = None) -> YoucomClient:
    """Get or create the You.com client singleton."""
    global _youcom_client, youcom_client

    if _youcom_client is None or (
        api_key and _youcom_client.api_key != api_key
    ):
        _youcom_client = YoucomClient(api_key=api_key)
        youcom_client = _youcom_client

    return _youcom_client


# Convenience singleton for backward compatibility
youcom_client = get_youcom_client()
