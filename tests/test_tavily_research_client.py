import json

import pytest

from app.integrations.tavily import client as client_module
from app.integrations.tavily.client import TavilyResearchClient


class FakeResponse:
    def __init__(self, status_code, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text if text is not None else str(self._payload)

    def json(self):
        return self._payload


@pytest.mark.parametrize(
    ("effort", "expected_model"),
    [
        ("lite", "mini"),
        ("standard", "auto"),
        ("deep", "pro"),
        ("exhaustive", "pro"),
    ],
)
def test_research_effort_maps_to_tavily_model(effort, expected_model):
    client = TavilyResearchClient(api_key="test-key")

    assert client._resolve_model(effort) == expected_model


def test_explicit_model_override_wins(monkeypatch):
    client = TavilyResearchClient(api_key="test-key", model="pro")

    assert client._resolve_model("lite") == "pro"


def test_pending_research_is_polled_until_completed(monkeypatch):
    client = TavilyResearchClient(
        api_key="test-key",
        poll_interval_seconds=0.1,
    )
    post_calls = []
    get_calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        post_calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return FakeResponse(202, {"request_id": "req-1", "status": "pending"})

    def fake_get(url, headers=None, timeout=None):
        get_calls.append({"url": url, "headers": headers, "timeout": timeout})
        return FakeResponse(
            200,
            {
                "status": "completed",
                "content": "# Research report",
                "sources": [
                    {
                        "title": "Source",
                        "url": "https://example.com/source",
                        "favicon": "https://example.com/favicon.ico",
                    }
                ],
            },
        )

    monkeypatch.setattr(client._session, "post", fake_post)
    monkeypatch.setattr(client._session, "get", fake_get)

    result = client.research("分析减脂饮食", research_effort="standard")

    assert result == {
        "content": "# Research report",
        "sources": [
            {
                "title": "Source",
                "url": "https://example.com/source",
                "snippet": "",
            }
        ],
    }
    assert post_calls[0]["url"] == client_module.TAVILY_RESEARCH_URL
    assert post_calls[0]["headers"]["Authorization"] == "Bearer test-key"
    assert post_calls[0]["json"] == {
        "input": "分析减脂饮食",
        "model": "auto",
        "stream": False,
    }
    assert get_calls[0]["url"] == f"{client_module.TAVILY_RESEARCH_URL}/req-1"


def test_completed_content_and_sources_are_normalized(monkeypatch):
    client = TavilyResearchClient(api_key="test-key")
    response = FakeResponse(
        200,
        {
            "status": "completed",
            "content": {"summary": "结构化报告"},
            "sources": [
                {
                    "title": "Source",
                    "url": "https://example.com/source",
                    "content": "First snippet",
                },
                {
                    "title": "Duplicate",
                    "url": "https://example.com/source",
                    "content": "Duplicate snippet",
                },
                "https://example.com/string-source",
            ],
        },
    )
    monkeypatch.setattr(client._session, "post", lambda *args, **kwargs: response)

    result = client.research("结构化输出")

    assert json.loads(result["content"]) == {"summary": "结构化报告"}
    assert result["sources"] == [
        {
            "title": "Source",
            "url": "https://example.com/source",
            "snippet": "First snippet",
        },
        {
            "title": "Unknown source",
            "url": "https://example.com/string-source",
            "snippet": "",
        },
    ]


def test_failed_research_status_returns_error(monkeypatch):
    client = TavilyResearchClient(api_key="test-key")
    responses = [
        FakeResponse(202, {"request_id": "req-failed", "status": "pending"}),
        FakeResponse(200, {"status": "failed", "error": "provider failed"}),
    ]

    monkeypatch.setattr(client._session, "post", lambda *args, **kwargs: responses[0])
    monkeypatch.setattr(client._session, "get", lambda *args, **kwargs: responses[1])

    result = client.research("测试失败")

    assert "failed" in result["error"].lower()


def test_auth_error_includes_response_detail(monkeypatch):
    client = TavilyResearchClient(api_key="wrong-key")
    response = FakeResponse(403, {"detail": "invalid api key"})
    monkeypatch.setattr(client._session, "post", lambda *args, **kwargs: response)

    result = client.research("测试鉴权")

    assert "Status 403" in result["error"]
    assert "invalid api key" in result["error"]


def test_research_timeout_returns_request_id(monkeypatch):
    client = TavilyResearchClient(api_key="test-key", timeout_seconds=1)
    monkeypatch.setattr(
        client._session,
        "get",
        lambda *args, **kwargs: FakeResponse(202, {"status": "pending"}),
    )
    clock = iter([0.0, 2.0])
    monkeypatch.setattr(client_module.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(client_module.time, "sleep", lambda _seconds: None)

    result = client._poll("req-timeout")

    assert "timed out after 1 seconds" in result["error"]
    assert "req-timeout" in result["error"]
