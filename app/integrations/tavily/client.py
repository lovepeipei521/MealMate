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
RETRYABLE_POLL_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
MAX_POLL_INTERVAL_SECONDS = 10.0


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
        self,
        response: requests.Response,
        operation: str = "Research",
        request_id: Optional[str] = None,
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

        request_suffix = f" (request_id={request_id})" if request_id else ""
        return {
            "error": (
                f"Tavily {operation} {reason} "
                f"(Status {response.status_code}){detail}{request_suffix}"
            ),
            "request_id": request_id,
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

    def _completed_result(
        self, payload: dict, request_id: Optional[str] = None
    ) -> dict:
        content = self._format_content(payload.get("content"))
        if not content:
            return {
                "error": "Tavily Research completed without report content",
                "request_id": request_id,
            }

        result = {
            "content": content,
            "sources": self._format_sources(payload.get("sources")),
        }
        if request_id:
            result["request_id"] = request_id
        return result

    @staticmethod
    def _retry_after_seconds(response: requests.Response) -> Optional[float]:
        """Parse a numeric Retry-After header when the provider supplies one."""
        value = getattr(response, "headers", {}).get("Retry-After")
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return None

    def _sleep_before_poll(
        self,
        delay_seconds: float,
        deadline: float,
        *,
        retry_after: Optional[float] = None,
    ) -> bool:
        """Sleep without exceeding the overall research deadline."""
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        delay = retry_after if retry_after is not None else delay_seconds
        time.sleep(min(max(0.0, delay), remaining))
        return True

    def _poll(self, request_id: str) -> dict:
        """Poll a Tavily task with retry and backoff until it finishes."""
        deadline = time.monotonic() + self.timeout_seconds
        url = f"{TAVILY_RESEARCH_URL}/{request_id}"
        poll_delay = self.poll_interval_seconds
        last_transient_error: Optional[str] = None
        poll_attempt = 0

        while time.monotonic() < deadline:
            poll_attempt += 1
            try:
                response = self._session.get(
                    url,
                    headers=self._get_headers(),
                    timeout=30,
                )
            except requests.RequestException as exc:
                last_transient_error = str(exc) or type(exc).__name__
                logger.warning(
                    "Tavily Research polling request failed; retrying "
                    "request_id=%s attempt=%s error=%s",
                    request_id,
                    poll_attempt,
                    last_transient_error,
                )
                if not self._sleep_before_poll(poll_delay, deadline):
                    break
                poll_delay = min(poll_delay * 2, MAX_POLL_INTERVAL_SECONDS)
                continue
            except Exception as exc:
                # Keep unexpected client/adapter errors visible, but treat them
                # as transient here so one polling failure does not discard the
                # already-created research task.
                last_transient_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "Unexpected Tavily polling error; retrying "
                    "request_id=%s attempt=%s error=%s",
                    request_id,
                    poll_attempt,
                    last_transient_error,
                )
                if not self._sleep_before_poll(poll_delay, deadline):
                    break
                poll_delay = min(poll_delay * 2, MAX_POLL_INTERVAL_SECONDS)
                continue

            if response.status_code in RETRYABLE_POLL_STATUS_CODES:
                last_transient_error = (
                    f"HTTP {response.status_code}{self._error_detail(response)}"
                )
                logger.warning(
                    "Tavily Research polling returned a retryable response; "
                    "retrying request_id=%s attempt=%s error=%s",
                    request_id,
                    poll_attempt,
                    last_transient_error,
                )
                if not self._sleep_before_poll(
                    poll_delay,
                    deadline,
                    retry_after=self._retry_after_seconds(response),
                ):
                    break
                poll_delay = min(poll_delay * 2, MAX_POLL_INTERVAL_SECONDS)
                continue

            if response.status_code not in (200, 202):
                return self._request_error(
                    response,
                    operation="Research polling",
                    request_id=request_id,
                )

            payload, error = self._parse_json(response, "Research polling")
            if error:
                last_transient_error = error.get("error")
                logger.warning(
                    "Tavily Research polling returned invalid JSON; retrying "
                    "request_id=%s attempt=%s error=%s",
                    request_id,
                    poll_attempt,
                    last_transient_error,
                )
                if not self._sleep_before_poll(poll_delay, deadline):
                    break
                poll_delay = min(poll_delay * 2, MAX_POLL_INTERVAL_SECONDS)
                continue

            status = str(payload.get("status", "")).strip().lower()
            if status == "completed":
                return self._completed_result(payload, request_id=request_id)
            if status == "failed":
                detail = payload.get("error") or payload.get("detail") or "unknown provider error"
                if isinstance(detail, dict):
                    detail = detail.get("error") or detail
                return {
                    "error": (
                        f"Tavily Research task failed: {detail} "
                        f"(request_id={request_id})"
                    ),
                    "request_id": request_id,
                }
            if status in {"cancelled", "canceled"}:
                return {
                    "error": f"Tavily Research task was cancelled (request_id={request_id})",
                    "request_id": request_id,
                }

            if not self._sleep_before_poll(poll_delay, deadline):
                break
            poll_delay = min(poll_delay * 2, MAX_POLL_INTERVAL_SECONDS)

        detail = (
            f"; last polling error: {last_transient_error}"
            if last_transient_error
            else ""
        )
        return {
            "error": (
                f"Tavily Research timed out after {self.timeout_seconds} seconds "
                f"(request_id={request_id}){detail}"
            ),
            "request_id": request_id,
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
            return self._completed_result(data, request_id=data.get("request_id"))
        if status == "failed":
            detail = data.get("error") or data.get("detail") or "unknown provider error"
            if isinstance(detail, dict):
                detail = detail.get("error") or detail
            request_id = data.get("request_id")
            return {
                "error": f"Tavily Research task failed: {detail}",
                "request_id": request_id,
            }

        request_id = data.get("request_id")
        if not isinstance(request_id, str) or not request_id.strip():
            if data.get("content") is not None:
                return self._completed_result(data, request_id=data.get("request_id"))
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
