import pytest

from app.agent.tools.common.deep_research import DeepResearchTool
from app.config import settings


class FakeTavilyClient:
    def __init__(self):
        self.calls = []

    def research(self, query, research_effort):
        self.calls.append((query, research_effort))
        return {
            "content": "# Report",
            "sources": [{"title": "Source", "url": "https://example.com", "snippet": ""}],
        }


@pytest.mark.asyncio
async def test_deep_research_tool_uses_tavily_provider(monkeypatch):
    fake_client = FakeTavilyClient()
    captured_init = {}

    def fake_get_client(**kwargs):
        captured_init.update(kwargs)
        return fake_client

    import app.integrations.tavily as tavily_module

    monkeypatch.setattr(settings.deep_research, "enabled", True)
    monkeypatch.setattr(settings.deep_research, "provider", "tavily")
    monkeypatch.setattr(settings.deep_research, "api_key", "tvly-test-key")
    monkeypatch.setattr(settings.deep_research, "model", "pro")
    monkeypatch.setattr(settings.deep_research, "timeout_seconds", 120)
    monkeypatch.setattr(settings.deep_research, "poll_interval_seconds", 1.5)
    monkeypatch.setattr(tavily_module, "get_tavily_research_client", fake_get_client)

    result = await DeepResearchTool().execute(
        query="分析减脂饮食",
        research_effort="deep",
    )

    assert result.success is True
    assert result.data["provider"] == "tavily"
    assert result.data["content"] == "# Report"
    assert fake_client.calls == [("分析减脂饮食", "deep")]
    assert captured_init == {
        "api_key": "tvly-test-key",
        "model": "pro",
        "timeout_seconds": 120,
        "poll_interval_seconds": 1.5,
    }
