"""Dependency-light fallback smoke test for the configured LLM provider."""

from __future__ import annotations

import asyncio

from app.config.llm_config import LLMConfig, LLMProfileConfig
from app.llm.provider import LLMProvider


class FakeProviderError(Exception):
    status_code = 429


class FakeLLM:
    def __init__(self, *, value=None, error=None):
        self.value = value
        self.error = error
        self.calls = 0

    async def ainvoke(self, messages, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return self.value


async def main() -> None:
    config = LLMConfig(
        fast=LLMProfileConfig(
            api_key="primary-test-key",
            base_url="https://primary.invalid/v1",
            model_names=["primary-model"],
        ),
        fallback=LLMProfileConfig(
            api_key="fallback-test-key",
            base_url="https://fallback.invalid/v1",
            model_names=["fallback-model"],
        ),
    )
    provider = LLMProvider(config)
    invoker = provider.create_invoker("fast")
    primary = FakeLLM(error=FakeProviderError("insufficient balance"))
    fallback = FakeLLM(value="fallback answer")

    invoker._get_llm_with_model = lambda tools=None: primary
    invoker._create_fallback_llm = lambda tools=None: fallback
    result = await invoker.ainvoke(["test"])

    assert result == "fallback answer"
    assert primary.calls == 1
    assert fallback.calls == 1
    print("[PASS] primary provider failure triggered fallback")
    print("primary_calls =", primary.calls)
    print("fallback_calls =", fallback.calls)
    print("result =", result)


if __name__ == "__main__":
    asyncio.run(main())
