# app/integrations/tavily/client.py
"""
Tavily Research API client for MealMate.

Tavily Research is asynchronous:
1. POST /research starts a research task.
2. GET /research/{request_id} polls until the task completes or fails.
"""

import json
import logging
import os
import time
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

TAVILY_RESEARCH_URL = "https://api.tavily.com/research"


class TavilyResearchClient:
    """Client for Tavily's asynchronous Research API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: int = 300,
        poll_interval_seconds: float = 2.0,
    ):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY", "")
        self.model = model
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.poll_interval_seconds = max(0.1, float(poll_interval_seconds))
        self._session = requests.Session()

    def _get_headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    @staticmethod
    def _error_detail(response: requests.Response) -> str:
        """Return a concise, useful error detail from a response."""
        detail: Any = ""
        try:
            payload = response.json()
            if isinstance(payload, dict):
                detail = payload.get("detail") or payload.get("error") or ""
                if isinstance(detail, dict):
                    detail = detail.get("error") or detail
        except Exception:
            detail = ""

        if not detail:
            detail = (response.text or "").strip().replace("\n", " ")

        detail = str(detail).strip()
        return f": {detail[:500]}" if detail else ""

    def _request_error(
        self, response: requests.Response, operation: str = "Research"
    ) -> dict:
        """Build a consistent error payload."""
        detail = self._error_detail(response)

        if response.status_code in (401, 403):
            reason = "API Key is invalid, expired, or has insufficient permissions"
        elif response.status_code == 429:
            reason = "rate limit exceeded"
        elif response.status_code in (432, 433):
            reason = "account or pay-as-you-go limit exceeded"
        elif response.status_code == 404:
            reason = "research task was not found"
        else:
            reason = "request failed"

        return {
            "error": (
                f"Tavily {operation} {reason} "
                f"(Status {response.status_code}){detail}"
            )
        }

    @staticmethod
    def _parse_json(response: requests.Response, operation: str) -> tuple[dict, Optional[dict]]:
        """Parse a JSON response and return a normalized error when invalid."""
        try:
            payload = response.json()
        except Exception:
            return {}, {"error": f"Tavily {operation} returned a non-JSON response"}

        if not isinstance(payload, dict):
            return {}, {"error": f"Tavily {operation} returned an unexpected response"}

        return payload, None

    @staticmethod
    def _format_content(content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        return json.dumps(content, ensure_ascii=False, default=str)

    @staticmethod
    def _format_sources(sources: Any) -> list[dict]:
        """Normalize Tavily source entries to title/url/snippet."""
        if not isinstance(sources, list):
            return []

        formatted: list[dict] = []
        seen: set[str] = set()

        for source in sources:
            if isinstance(source, str):
                title, url, snippet = "Unknown source", source, ""
            elif isinstance(source, dict):
                title = source.get("title") or source.get("name") or "Unknown source"
                url = source.get("url") or ""
                snippet = (
                    source.get("snippet")
                    or source.get("content")
                    or source.get("description")
                    or ""
                )
            else:
                continue

            key = url or f"{title}:{snippet}"
            if key in seen:
                continue
            seen.add(key)

            formatted.append(
                {
                    "title": str(title),
                    "url": str(url),
                    "snippet": str(snippet),
                }
            )

        return formatted

    def _resolve_model(self, research_effort: str) -> str:
        """Map MealMate research depth to a supported Tavily model."""
        if self.model:
            model = self.model.strip().lower()
            if model in {"mini", "pro", "auto"}:
                return model

        effort = (research_effort or "standard").strip().lower()
        if effort == "lite":
            return "mini"
        if effort in {"deep", "exhaustive"}:
            return "pro"
        return "auto"

    def _completed_result(self, payload: dict) -> dict:
        content = self._format_content(payload.get("content"))
        if not content:
            return {"error": "Tavily Research completed without report content"}

        return {
            "content": content,
            "sources": self._format_sources(payload.get("sources")),
        }

    def _poll(self, request_id: str) -> dict:
        """Poll a Tavily research task until it completes, fails, or times out."""
        deadline = time.monotonic() + self.timeout_seconds
        url = f"{TAVILY_RESEARCH_URL}/{request_id}"

        while time.monotonic() < deadline:
            try:
                response = self._session.get(
                    url,
                    headers=self._get_headers(),
                    timeout=30,
                )
            except Exception as exc:
                return {"error": f"Tavily Research polling failed: {exc}"}

            if response.status_code not in (200, 202):
                return self._request_error(response, operation="Research polling")

            payload, error = self._parse_json(response, "Research polling")
            if error:
                return error

            status = str(payload.get("status", "")).strip().lower()
            if status == "completed":
                return self._completed_result(payload)
            if status == "failed":
                return {"error": "Tavily Research task failed"}

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(self.poll_interval_seconds, remaining))

        return {
            "error": (
                f"Tavily Research timed out after {self.timeout_seconds} seconds "
                f"(request_id={request_id})"
            )
        }

    def research(self, query: str, research_effort: str = "standard") -> dict:
        """
        Perform deep research via Tavily Research.

        Args:
            query: Research topic or question.
            research_effort: lite, standard, deep, or exhaustive. This is
                mapped to Tavily mini, auto, or pro when no model override is set.

        Returns:
            Dict containing content and sources, or an error field on failure.
        """
        if not self.api_key:
            return {"error": "TAVILY_API_KEY is not configured"}
        if not query or not query.strip():
            return {"error": "Research query cannot be empty"}

        model = self._resolve_model(research_effort)
        payload = {
            "input": query.strip(),
            "model": model,
            "stream": False,
        }

        try:
            response = self._session.post(
                TAVILY_RESEARCH_URL,
                headers=self._get_headers(),
                json=payload,
                timeout=30,
            )
        except Exception as exc:
            return {"error": f"Tavily Research request failed: {exc}"}

        if response.status_code not in (200, 201, 202):
            return self._request_error(response)

        data, error = self._parse_json(response, "Research")
        if error:
            return error

        status = str(data.get("status", "")).strip().lower()
        if status == "completed":
            return self._completed_result(data)
        if status == "failed":
            return {"error": "Tavily Research task failed"}

        request_id = data.get("request_id")
        if not isinstance(request_id, str) or not request_id.strip():
            if data.get("content") is not None:
                return self._completed_result(data)
            return {"error": "Tavily Research did not return a request_id"}

        return self._poll(request_id.strip())


_research_client: Optional[TavilyResearchClient] = None


def get_tavily_research_client(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout_seconds: int = 300,
    poll_interval_seconds: float = 2.0,
) -> TavilyResearchClient:
    """Get or create the Tavily research client singleton."""
    global _research_client

    if _research_client is None or (
        api_key
        and _research_client.api_key != api_key
    ) or (
        _research_client.model != model
        or _research_client.timeout_seconds != max(1, int(timeout_seconds))
        or _research_client.poll_interval_seconds != max(0.1, float(poll_interval_seconds))
    ):
        _research_client = TavilyResearchClient(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )

    return _research_client
