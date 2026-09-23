from app.integrations.youcom import client as client_module
from app.integrations.youcom.client import YoucomClient


class FakeResponse:
    def __init__(self, status_code, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text if text is not None else str(self._payload)

    def json(self):
        return self._payload


def test_search_parses_nested_web_and_news_results(monkeypatch):
    client = YoucomClient(api_key="test-key")
    response = FakeResponse(
        200,
        {
            "results": {
                "web": [
                    {
                        "title": "Web result",
                        "url": "https://example.com/web",
                        "description": "Web description",
                    }
                ],
                "news": [
                    {
                        "title": "News result",
                        "url": "https://example.com/news",
                        "contents": {"highlights": ["News highlight"]},
                    }
                ],
            }
        },
    )
    monkeypatch.setattr(client._session, "post", lambda *args, **kwargs: response)

    result = client.search("上海 健康饮食", count=2)

    assert result == {
        "results": [
            {
                "title": "Web result",
                "url": "https://example.com/web",
                "snippet": "Web description",
            },
            {
                "title": "News result",
                "url": "https://example.com/news",
                "snippet": "News highlight",
            },
        ]
    }


def test_search_supports_legacy_list_and_deduplicates_urls(monkeypatch):
    client = YoucomClient(api_key="test-key")
    response = FakeResponse(
        200,
        {
            "results": [
                {
                    "title": "Legacy result",
                    "url": "https://example.com/recipe",
                    "snippets": ["Legacy snippet"],
                },
                {
                    "title": "Duplicate",
                    "url": "https://example.com/recipe",
                    "description": "Duplicate",
                },
            ]
        },
    )
    monkeypatch.setattr(client._session, "post", lambda *args, **kwargs: response)

    result = client.search("番茄炒蛋", count=5)

    assert result["results"] == [
        {
            "title": "Legacy result",
            "url": "https://example.com/recipe",
            "snippet": "Legacy snippet",
        }
    ]


def test_research_parses_nested_output(monkeypatch):
    client = YoucomClient(api_key="test-key")
    response = FakeResponse(
        200,
        {
            "output": {
                "content": "# Research report",
                "sources": [
                    {
                        "title": "Source",
                        "url": "https://example.com/source",
                        "contents": {"highlights": ["Source highlight"]},
                    }
                ],
            }
        },
    )
    monkeypatch.setattr(client._session, "post", lambda *args, **kwargs: response)

    result = client.research("分析减脂饮食", research_effort="standard")

    assert result == {
        "content": "# Research report",
        "sources": [
            {
                "title": "Source",
                "url": "https://example.com/source",
                "snippet": "Source highlight",
            }
        ],
    }


def test_auth_error_includes_response_detail(monkeypatch):
    client = YoucomClient(api_key="wrong-key")
    response = FakeResponse(403, text="insufficient permissions")
    monkeypatch.setattr(client._session, "post", lambda *args, **kwargs: response)

    result = client.search("测试", count=1)

    assert "Status 403" in result["error"]
    assert "insufficient permissions" in result["error"]


def test_singleton_replaces_client_when_api_key_changes(monkeypatch):
    monkeypatch.setattr(client_module, "_youcom_client", None)
    monkeypatch.setattr(client_module, "youcom_client", None)

    first = client_module.get_youcom_client("first-key")
    second = client_module.get_youcom_client("second-key")

    assert first.api_key == "first-key"
    assert second.api_key == "second-key"
    assert second is not first
    assert client_module.youcom_client is second
