import pytest

from app.config.llm_config import LLMConfig, LLMProfileConfig
from app.llm.provider import LLMProvider, is_retryable_provider_error


class FakeProviderError(Exception):
    status_code = 429


class FakeLLM:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error
        self.calls = 0

    async def ainvoke(self, messages, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return self.value


def test_insufficient_balance_is_retryable():
    error = RuntimeError("Error 429: insufficient balance")
    assert is_retryable_provider_error(error)


@pytest.mark.asyncio
async def test_ainvoke_falls_back_for_retryable_error(monkeypatch):
    config = LLMConfig(
        fast=LLMProfileConfig(
            api_key="primary-key",
            base_url="https://primary.example/v1",
            model_names=["primary-model"],
        ),
        fallback=LLMProfileConfig(
            api_key="fallback-key",
            base_url="https://fallback.example/v1",
            model_names=["fallback-model"],
        ),
    )
    provider = LLMProvider(config)
    invoker = provider.create_invoker("fast")
    primary = FakeLLM(error=FakeProviderError("insufficient balance"))
    fallback = FakeLLM(value="fallback answer")
    monkeypatch.setattr(invoker, "_get_llm_with_model", lambda tools=None: primary)
    monkeypatch.setattr(invoker, "_create_fallback_llm", lambda tools=None: fallback)

    result = await invoker.ainvoke(["hello"])

    assert result == "fallback answer"
    assert primary.calls == 1
    assert fallback.calls == 1
