import json
from types import SimpleNamespace

import pytest

from app.agent.context import AgentContextCompressor


class FakeRepository:
    def __init__(self):
        self.update_calls = []

    async def get_message_count(self, session_id):
        return 3

    async def get_compressed_summary(self, session_id):
        return None, 0

    async def get_recent_messages(self, session_id, skip, limit):
        return [
            {"role": "user", "content": "第一条消息"},
            {"role": "assistant", "content": "第二条消息"},
        ]

    async def update_compressed_summary(self, session_id, summary, message_count):
        self.update_calls.append((session_id, summary, message_count))
        return True


class FakeInvoker:
    def __init__(self, result):
        self.result = result

    async def ainvoke(self, messages, **kwargs):
        if isinstance(self.result, Exception):
            raise self.result
        return SimpleNamespace(content=self.result)


class FakeProvider:
    def __init__(self, calls, responses):
        self.calls = calls
        self.responses = responses

    def create_invoker(self, llm_type):
        self.calls.append(llm_type)
        return FakeInvoker(self.responses[llm_type])


@pytest.mark.asyncio
async def test_context_compression_retries_with_normal_model(monkeypatch):
    import app.llm.provider as provider_module

    calls = []
    provider = FakeProvider(
        calls,
        {
            "fast": json.JSONDecodeError("Extra data", "{}", 171),
            "normal": "  新摘要  ",
        },
    )
    monkeypatch.setattr(provider_module, "LLMProvider", lambda config: provider)

    repository = FakeRepository()
    compressor = AgentContextCompressor(
        compression_threshold=2,
        recent_messages_limit=0,
    )

    result = await compressor.maybe_compress("session-1", repository)

    assert result is True
    assert calls == ["fast", "normal"]
    assert repository.update_calls == [("session-1", "新摘要", 2)]


@pytest.mark.asyncio
async def test_context_compression_does_not_update_count_on_failure(monkeypatch):
    import app.llm.provider as provider_module

    calls = []
    provider = FakeProvider(
        calls,
        {
            "fast": json.JSONDecodeError("Extra data", "{}", 171),
            "normal": "   ",
        },
    )
    monkeypatch.setattr(provider_module, "LLMProvider", lambda config: provider)

    repository = FakeRepository()
    compressor = AgentContextCompressor(
        compression_threshold=2,
        recent_messages_limit=0,
    )

    result = await compressor.maybe_compress("session-1", repository)

    assert result is False
    assert calls == ["fast", "normal"]
    assert repository.update_calls == []