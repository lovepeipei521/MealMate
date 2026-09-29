"""
LLM Provider - 统一的 LLM 初始化和调用入口

核心概念:
1. LLMProvider - 全局 LLM 提供者，管理配置和创建 LLM 实例
2. LLMInvoker - LLM 调用器，封装了调用逻辑和 usage tracking
"""

from __future__ import annotations

import random
import logging
from typing import Any, AsyncIterator, List, Optional

from langchain_core.callbacks import BaseCallbackHandler
from langchain_openai import ChatOpenAI

from app.config.llm_config import LLMConfig, LLMProfileConfig, LLMType

logger = logging.getLogger(__name__)


def is_retryable_provider_error(exc: BaseException) -> bool:
    """Return whether a provider failure is suitable for one fallback attempt."""
    status_code = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if status_code is None and response is not None:
        status_code = getattr(response, "status_code", None)
    if status_code is not None:
        try:
            return int(status_code) in {408, 425, 429, 500, 502, 503, 504}
        except (TypeError, ValueError):
            pass

    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "insufficient balance",
            "insufficient funds",
            "quota",
            "rate limit",
            "timed out",
            "timeout",
            "connection error",
            "connection reset",
            "temporarily unavailable",
        )
    )


class LLMProvider:
    """
    LLM 提供者 - 统一的 LLM 创建和管理入口

    使用方式:
        provider = LLMProvider(settings.llm)

        # 创建带 usage tracking 的 invoker（推荐）
        invoker = provider.create_invoker("fast")
        response = await invoker.ainvoke(messages)

        # 直接创建 ChatOpenAI 实例（不推荐，除非有特殊需求）
        llm = provider.create_llm("normal", streaming=True)
    """

    def __init__(self, config: LLMConfig):
        """
        初始化 LLM Provider

        Args:
            config: LLM 配置（通常来自 settings.llm）
        """
        self._config = config

    def get_profile(self, llm_type: LLMType | str | None = None) -> LLMProfileConfig:
        """获取指定类型的 LLM 配置 profile"""
        return self._config.get_profile(llm_type)

    def get_fallback_profile(self) -> LLMProfileConfig | None:
        """Return the explicitly configured fallback provider, if any."""
        return self._config.fallback

    def pick_model(self, llm_type: LLMType | str | None = None) -> str:
        """
        随机选择一个模型名称（用于负载均衡）

        Args:
            llm_type: LLM 类型 (fast/normal)

        Returns:
            选中的模型名称
        """
        profile = self.get_profile(llm_type)
        if not profile.model_names:
            raise ValueError("model_names cannot be empty")
        return random.choice(profile.model_names)

    def create_llm(
        self,
        llm_type: LLMType | str | None = None,
        *,
        streaming: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: int | None = None,
        **kwargs: Any,
    ) -> ChatOpenAI:
        """
        创建原生 ChatOpenAI 实例

        注意: 此方法创建的实例不包含 usage tracking，
        推荐使用 create_invoker() 方法获取带 tracking 的调用器

        Args:
            llm_type: LLM 类型 (fast/normal/vision)
            streaming: 是否启用流式输出
            temperature: 温度参数（可选覆盖配置）
            max_tokens: 最大 tokens（可选覆盖配置）
            timeout: 请求超时时间（可选，vision profile 默认 120s）
            **kwargs: 其他 ChatOpenAI 参数

        Returns:
            ChatOpenAI 实例
        """
        profile = self.get_profile(llm_type)

        # Handle timeout - use profile's request_timeout if available
        effective_timeout = timeout
        if effective_timeout is None and hasattr(profile, "request_timeout"):
            effective_timeout = profile.request_timeout # type: ignore

        llm_kwargs = {
            "model": profile.pick_default_model(),
            "api_key": profile.api_key,
            "base_url": profile.base_url,
            "temperature": temperature if temperature is not None else profile.temperature,
            "max_completion_tokens": max_tokens if max_tokens is not None else profile.max_tokens,
            "streaming": streaming,
            "stream_usage": True,
            **kwargs,
        }

        if effective_timeout is not None:
            llm_kwargs["timeout"] = effective_timeout

        return ChatOpenAI(**llm_kwargs)  # type: ignore

    def create_invoker(
        self,
        llm_type: LLMType | str | None = None,
        *,
        streaming: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> "LLMInvoker":
        """
        创建带 usage tracking 的 LLM 调用器（推荐使用）

        Args:
            llm_type: LLM 类型 (fast/normal)
            streaming: 是否启用流式输出
            temperature: 温度参数（可选覆盖配置）
            max_tokens: 最大 tokens（可选覆盖配置）
            **kwargs: 其他 ChatOpenAI 参数

        Returns:
            LLMInvoker 实例
        """
        from app.llm.callbacks import get_usage_callbacks

        base_llm = self.create_llm(
            llm_type,
            streaming=streaming,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        return LLMInvoker(
            provider=self,
            llm_type=llm_type,
            base_llm=base_llm,
            callbacks=get_usage_callbacks(),
        )



class LLMInvoker:
    """
    LLM 调用器 - 封装 LLM 调用逻辑

    特性:
    - 自动附加 usage tracking callbacks
    - 支持动态模型选择（每次调用可选择不同模型）
    - 支持 tool calling
    - 支持流式输出

    使用方式:
        # 普通调用
        response = await invoker.ainvoke(messages)

        # 流式调用
        async for chunk in invoker.astream(messages):
            print(chunk.content)

        # 带 tools 调用
        response = await invoker.ainvoke_with_tools(messages, tools)
    """

    def __init__(
        self,
        provider: LLMProvider,
        llm_type: LLMType | str | None,
        base_llm: ChatOpenAI,
        callbacks: List[BaseCallbackHandler] | None = None,
    ):
        self._provider = provider
        self._llm_type = llm_type
        self._base_llm = base_llm
        self._callbacks = callbacks or []

    def _create_fallback_llm(self, tools: list[Any] | None = None) -> ChatOpenAI | None:
        profile = self._provider.get_fallback_profile()
        if (
            profile is None
            or not profile.api_key
            or not profile.base_url
            or not profile.model_names
        ):
            return None
        llm = ChatOpenAI(
            model=profile.pick_default_model(),
            api_key=profile.api_key,
            base_url=profile.base_url,
            temperature=profile.temperature,
            max_completion_tokens=profile.max_tokens,
            streaming=getattr(self._base_llm, "streaming", False),
            stream_usage=True,
        )
        if tools:
            llm = llm.bind(tools=tools)  # type: ignore
        return llm  # type: ignore

    def _fallback_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Copy invocation kwargs, preserving usage callbacks for fallback calls."""
        return dict(kwargs)

    async def _run_with_fallback(self, operation: str, primary_call, fallback_call):
        try:
            return await primary_call()
        except Exception as exc:
            fallback_llm = self._create_fallback_llm()
            if fallback_llm is None or not is_retryable_provider_error(exc):
                raise
            logger.warning(
                "Primary LLM provider failed; retrying with configured fallback: "
                "operation=%s error=%s",
                operation,
                exc,
            )
            return await fallback_call(fallback_llm)

    def _get_llm_with_model(self, tools: list[Any] | None = None) -> ChatOpenAI:
        """
        获取绑定了随机模型的 LLM 实例

        每次调用都会随机选择一个模型，实现负载均衡
        """
        model = self._provider.pick_model(self._llm_type)
        llm = self._base_llm.bind(model=model)

        if tools:
            llm = llm.bind(tools=tools)  # type: ignore

        return llm  # type: ignore

    def _prepare_config(self, kwargs: dict) -> dict:
        """准备调用配置，合并 callbacks"""
        # 提取已有的 callbacks
        call_callbacks = kwargs.pop("callbacks", None) or []
        config = kwargs.pop("config", None) or {}

        if isinstance(config, dict):
            config_callbacks = config.get("callbacks", []) or []
        else:
            config_callbacks = []

        # 合并所有 callbacks
        merged = list(call_callbacks) + list(config_callbacks) + self._callbacks
        if merged:
            kwargs["config"] = {"callbacks": merged}

        return kwargs
    
    async def ainvoke(self, messages: list, **kwargs: Any) -> Any:
        """异步调用 LLM"""
        kwargs = self._prepare_config(kwargs)
        primary = self._get_llm_with_model()
        return await self._run_with_fallback(
            "ainvoke",
            lambda: primary.ainvoke(messages, **kwargs),
            lambda fallback: fallback.ainvoke(messages, **kwargs),
        )

    async def ainvoke_with_tools(
        self, messages: list, tools: list, **kwargs: Any
    ) -> Any:
        """异步调用 LLM（带 tools）"""
        kwargs = self._prepare_config(kwargs)
        primary = self._get_llm_with_model(tools=tools)
        fallback = self._create_fallback_llm(tools=tools)
        try:
            return await primary.ainvoke(messages, **kwargs)
        except Exception as exc:
            if fallback is None or not is_retryable_provider_error(exc):
                raise
            logger.warning("Primary LLM provider failed; retrying tool call with fallback: %s", exc)
            return await fallback.ainvoke(messages, **kwargs)

    def astream(self, messages: list, **kwargs: Any) -> AsyncIterator[Any]:
        """流式调用 LLM"""
        kwargs = self._prepare_config(kwargs)
        return self._stream_with_fallback(messages, kwargs)

    async def _stream_with_fallback(
        self, messages: list, kwargs: dict[str, Any]
    ) -> AsyncIterator[Any]:
        primary = self._get_llm_with_model()
        fallback = self._create_fallback_llm()
        emitted = False
        try:
            async for chunk in primary.astream(messages, **kwargs):
                emitted = True
                yield chunk
            return
        except Exception as exc:
            if emitted or fallback is None or not is_retryable_provider_error(exc):
                raise
            logger.warning("Primary LLM provider failed; retrying stream with fallback: %s", exc)
            async for chunk in fallback.astream(
                messages, **self._fallback_kwargs(kwargs)
            ):
                yield chunk

    async def astream_with_tools(
        self, messages: list, tools: list, **kwargs: Any
    ) -> AsyncIterator[Any]:
        """流式调用 LLM（带 tools）"""
        kwargs = self._prepare_config(kwargs)
        primary = self._get_llm_with_model(tools=tools)
        fallback = self._create_fallback_llm(tools=tools)
        emitted = False
        try:
            async for chunk in primary.astream(messages, **kwargs):
                emitted = True
                yield chunk
            return
        except Exception as exc:
            if emitted or fallback is None or not is_retryable_provider_error(exc):
                raise
            logger.warning("Primary LLM provider failed; retrying stream with fallback: %s", exc)
            async for chunk in fallback.astream(
                messages, **self._fallback_kwargs(kwargs)
            ):
                yield chunk
