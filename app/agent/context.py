"""
Agent 上下文组装

简化版上下文组装，不包含 RAG 和 Web Search。
"""

import json
import logging
import time
from typing import Optional

from app.agent.types import AgentContext, AgentConfig
from app.agent.database.repository import AgentRepository
from app.agent.database.models import AgentSessionModel
from app.agent.registry import AgentHub
from app.services.user_service import user_service
from app.agent.prompts import (
    USER_ID_PROMPT_TEMPLATE,
    COMPRESS_SYSTEM_PROMPT,
    COMPRESS_USER_PROMPT_TEMPLATE,
)
from app.agent.evaluation_profiles import (
    get_compression_strategy,
    get_evaluation_prompt_suffix,
)

logger = logging.getLogger(__name__)


class AgentContextBuilder:
    """
    Agent 上下文构建器。

    负责组装 Agent 执行所需的完整上下文。
    """

    def __init__(
        self,
        repository: Optional[AgentRepository] = None,
        recent_messages_limit: int = 20,
    ):
        """
        初始化构建器。

        Args:
            repository: Agent 仓库实例
            recent_messages_limit: 近期消息数量限制
        """
        from app.agent.database.repository import agent_repository

        self.repository = repository or agent_repository
        self.recent_messages_limit = recent_messages_limit

    async def build(
        self,
        session: AgentSessionModel,
        current_message: str,
        user_id: str,
        agent_name: str = "default",
        selected_tools: Optional[list[str]] = None,
        images: Optional[list[dict]] = None,
    ) -> AgentContext:
        """
        构建 Agent 上下文。

        Args:
            session: Agent Session 模型
            current_message: 当前用户消息
            user_id: 用户 ID
            agent_name: Agent 名称（用于选择 Agent 配置）
            selected_tools: 用户选择的工具列表（为空则使用 Agent 默认工具）
            images: 用户上传的图片列表 [{data, mime_type}]

        Returns:
            完整的 Agent 上下文
        """
        session_id = str(session.id)

        # 1. 获取 Agent 配置
        try:
            config = AgentHub.get_agent_config(agent_name)
        except KeyError:
            logger.warning(f"Agent {agent_name} not found, using default config")
            config = AgentConfig(
                name=agent_name,
                description="Default agent",
                system_prompt="You are a helpful assistant.",
            )

        # 2. 获取历史摘要
        (
            compressed_summary,
            compressed_count,
        ) = await self.repository.get_compressed_summary(session_id)

        # 3. 获取近期消息（跳过已压缩的）
        _, profile_recent_limit, profile_name, _ = get_compression_strategy()
        recent_messages = await self.repository.get_recent_messages(
            session_id,
            skip=compressed_count,
            limit=(
                profile_recent_limit
                if profile_name != "default"
                else self.recent_messages_limit
            ),
        )

        # 4. 获取可用 Tool schemas
        # Use selected_tools if provided, otherwise get all available tools
        # 传入 user_id 以支持 Subagent Tools
        tools_to_use = selected_tools
        if user_id:
            from app.services.subagent_service import subagent_service

            await subagent_service.sync_user_subagents(user_id)
        available_tools = AgentHub.get_tool_schemas(tools_to_use, user_id=user_id)

        # 5. user_profile user_instruction
        user_profile = None
        user_instruction = None
        if user_id:
            user_data = await user_service.get_user_by_id(user_id)
            if user_data:
                user_profile = user_data.profile
                user_instruction = user_data.user_instruction

        # 6. Process images if provided
        processed_images = None
        if images:
            processed_images = await self._process_images(images)

        return AgentContext(
            system_prompt=config.system_prompt,
            user_id=session.user_id,
            session_id=session_id,
            user_profile=user_profile,
            user_instruction=user_instruction,
            history_summary=compressed_summary,
            recent_messages=recent_messages,
            available_tools=available_tools,
            current_message=current_message,
            images=processed_images,
        )

    async def _process_images(self, images: list[dict]) -> list[dict]:
        """
        Process images by uploading to imgbb for persistent URLs.

        Args:
            images: List of images [{data, mime_type}]

        Returns:
            List of processed images [{data, mime_type, url}]
        """
        from app.utils.image_storage import upload_to_imgbb

        processed = []
        for img in images:
            result = {
                "data": img["data"],
                "mime_type": img["mime_type"],
                "url": None,
            }

            # Upload to imgbb for persistent URL
            try:
                upload_result = await upload_to_imgbb(
                    img["data"],
                    img["mime_type"],
                )
                if upload_result:
                    result["url"] = upload_result.get("url")
                    result["display_url"] = upload_result.get("display_url")
                    result["thumb_url"] = upload_result.get("thumb_url")
            except Exception as e:
                logger.warning(f"Failed to upload image to imgbb: {e}")

            processed.append(result)

        return processed

    def build_messages(self, context: AgentContext) -> list[dict]:
        """
        从上下文构建 LLM 输入消息列表。

        Args:
            context: Agent 上下文

        Returns:
            消息列表（符合 OpenAI 格式）
        """
        messages = []

        # 1. System prompt（含用户画像和指令）
        system_content = context.system_prompt

        system_content += get_evaluation_prompt_suffix()

        if context.user_id:
            system_content += USER_ID_PROMPT_TEMPLATE.format(user_id=context.user_id)

        if context.user_profile:
            system_content += f"\n\n## 用户画像\n{context.user_profile}"

        if context.user_instruction:
            system_content += f"\n\n## 用户指令\n{context.user_instruction}"

        messages.append({"role": "system", "content": system_content})

        # 2. 历史摘要
        if context.history_summary:
            messages.append(
                {
                    "role": "system",
                    "content": f"## 历史对话摘要\n{context.history_summary}",
                }
            )

        # 3. 近期消息
        messages.extend(context.recent_messages)

        # 4. 当前消息（可能包含图片）
        if context.images:
            # Build multimodal content with images
            content_parts = []
            content_parts.append(
                {
                    "type": "text",
                    "text": context.current_message,
                }
            )

            # Add image content
            for img in context.images:
                if img.get("url"):
                    # Use imgbb URL
                    content_parts.append(
                        {"type": "image_url", "image_url": {"url": img["url"]}}
                    )

            messages.append({"role": "user", "content": content_parts})
        else:
            # Plain text message
            messages.append({"role": "user", "content": context.current_message})

        if context.vision_analysis and context.vision_tool_call_id:
            tool_call = {
                "id": context.vision_tool_call_id,
                "type": "function",
                "function": {
                    "name": "vision_analysis",
                    "arguments": json.dumps(
                        {"image_count": len(context.images or [])},
                        ensure_ascii=False,
                    ),
                },
            }
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tool_call],
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": context.vision_tool_call_id,
                    "name": "vision_analysis",
                    "content": json.dumps(
                        context.vision_analysis,
                        ensure_ascii=False,
                        default=str,
                    ),
                }
            )

        return messages


class AgentContextCompressor:
    """
    Agent 上下文压缩器。

    负责压缩历史消息为摘要。
    """

    def __init__(
        self,
        compression_threshold: int = 10,
        recent_messages_limit: int = 20,
    ):
        """
        初始化压缩器。

        Args:
            compression_threshold: 触发压缩的消息数阈值
            recent_messages_limit: 保留的未压缩消息数
        """
        self.compression_threshold = compression_threshold
        self.recent_messages_limit = recent_messages_limit

    async def maybe_compress(
        self,
        session_id: str,
        repository: AgentRepository,
        user_id: Optional[str] = None,
        *,
        run_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        evaluation_profile: Optional[str] = None,
    ) -> bool:
        """
        检查并执行压缩（如需要）。

        Args:
            session_id: Session ID
            repository: Agent 仓库
            user_id: 用户 ID（用于 LLM 上下文）

        Returns:
            是否执行了压缩
        """
        from app.llm.provider import LLMProvider
        from app.llm.context import llm_context
        from app.config import settings
        from app.agent.tracing import (
            create_trace_state,
            reset_trace_state,
            set_trace_state,
            span_context,
        )

        provider = LLMProvider(settings.llm)

        # Evaluation profiles override the defaults only for evaluation calls.
        # Online traffic keeps the original 10/20 message policy.
        profile_threshold = self.compression_threshold
        profile_recent_limit = self.recent_messages_limit
        profile_name = evaluation_profile or "default"
        prompt_suffix = ""
        if evaluation_profile:
            from app.agent.evaluation_profiles import PROFILES

            profile = PROFILES.get(evaluation_profile)
            if profile:
                profile_threshold = profile.compression_threshold
                profile_recent_limit = profile.recent_messages_limit
                prompt_suffix = profile.compression_prompt_suffix

        started = time.perf_counter()
        compression_state = create_trace_state(
            trace_id=trace_id,
            run_id=run_id,
            user_id=user_id,
            session_id=session_id,
            source="compression",
        )
        compression_token = set_trace_state(compression_state)
        attempts: list[str] = []
        fallback_used = False

        async def persist_event(event: dict) -> None:
            if run_id:
                try:
                    await repository.append_run_trace(run_id, event)
                except Exception:
                    logger.warning(
                        "Failed to persist compression metrics for run %s",
                        run_id,
                        exc_info=True,
                    )

        try:
            # 获取当前状态
            total_count = await repository.get_message_count(session_id)
            compressed_summary, compressed_count = await repository.get_compressed_summary(
                session_id
            )

            uncompressed_count = total_count - compressed_count
            trigger_threshold = profile_threshold + profile_recent_limit

            # 检查是否需要压缩
            if uncompressed_count < trigger_threshold:
                await persist_event(
                    {
                        "event_type": "context_compression",
                        "action": "compression_check",
                        "status": "skipped",
                        "run_id": run_id,
                        "session_id": session_id,
                        "profile": profile_name,
                        "triggered": False,
                        "total_messages": total_count,
                        "compressed_count_before": compressed_count,
                        "compressed_count_after": compressed_count,
                        "uncompressed_count_before": uncompressed_count,
                        "uncompressed_count_after": uncompressed_count,
                        "compression_threshold": profile_threshold,
                        "recent_messages_limit": profile_recent_limit,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    }
                )
                return False

            # 获取需要压缩的消息
            messages_to_compress = await repository.get_recent_messages(
                session_id,
                skip=compressed_count,
                limit=profile_threshold,
            )

            if not messages_to_compress:
                await persist_event(
                    {
                        "event_type": "context_compression",
                        "action": "compression",
                        "status": "failed",
                        "run_id": run_id,
                        "session_id": session_id,
                        "profile": profile_name,
                        "triggered": True,
                        "total_messages": total_count,
                        "compressed_count_before": compressed_count,
                        "compressed_count_after": compressed_count,
                        "uncompressed_count_before": uncompressed_count,
                        "uncompressed_count_after": uncompressed_count,
                        "messages_compressed": 0,
                        "error": "no messages available to compress",
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    }
                )
                return False

            # 构建压缩提示
            messages_text = "\n".join(
                [f"{msg['role']}: {msg['content']}" for msg in messages_to_compress]
            )

            previous_summary = (
                f"之前的摘要：{compressed_summary}" if compressed_summary else ""
            )
            prompt = COMPRESS_USER_PROMPT_TEMPLATE.format(
                messages_text=messages_text,
                previous_summary=previous_summary,
            )

            new_summary: Optional[str] = None

            for index, llm_type in enumerate(("fast", "normal")):
                attempts.append(llm_type)
                try:
                    invoker = provider.create_invoker(llm_type=llm_type)

                    with span_context() as compression_span_id:
                        with llm_context(
                            "agent:compressor",
                            user_id,
                            session_id,
                            trace_id=compression_state.trace_id,
                            run_id=compression_state.run_id,
                            span_id=compression_span_id,
                        ):
                            response = await invoker.ainvoke(
                                [
                                    {
                                        "role": "system",
                                        "content": COMPRESS_SYSTEM_PROMPT + prompt_suffix,
                                    },
                                    {"role": "user", "content": prompt},
                                ]
                            )

                    summary_text = getattr(response, "content", None)
                    if not isinstance(summary_text, str) or not summary_text.strip():
                        raise ValueError("LLM returned an empty compression summary")

                    new_summary = summary_text.strip()
                    break
                except Exception:
                    if index == 0:
                        fallback_used = True
                        logger.warning(
                            "Failed to compress context with fast model; retrying with normal model",
                            exc_info=True,
                        )
                    else:
                        logger.exception(
                            "Failed to compress context after retrying with normal model"
                        )

            if not new_summary:
                await persist_event(
                    {
                        "event_type": "context_compression",
                        "action": "compression",
                        "status": "failed",
                        "run_id": run_id,
                        "session_id": session_id,
                        "profile": profile_name,
                        "triggered": True,
                        "total_messages": total_count,
                        "compressed_count_before": compressed_count,
                        "compressed_count_after": compressed_count,
                        "uncompressed_count_before": uncompressed_count,
                        "uncompressed_count_after": uncompressed_count,
                        "messages_compressed": 0,
                        "compression_threshold": profile_threshold,
                        "recent_messages_limit": profile_recent_limit,
                        "compression_llm_attempts": attempts,
                        "fallback_used": fallback_used,
                        "compression_input_tokens": compression_state.input_tokens,
                        "compression_output_tokens": compression_state.output_tokens,
                        "compression_total_tokens": compression_state.total_tokens,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    }
                )
                return False

            new_count = compressed_count + len(messages_to_compress)

            # 更新数据库
            updated = await repository.update_compressed_summary(
                session_id,
                new_summary,
                new_count,
            )
            if not updated:
                logger.error(
                    "Failed to persist compressed summary for session %s",
                    session_id,
                )
                await persist_event(
                    {
                        "event_type": "context_compression",
                        "action": "compression",
                        "status": "failed",
                        "run_id": run_id,
                        "session_id": session_id,
                        "profile": profile_name,
                        "triggered": True,
                        "total_messages": total_count,
                        "compressed_count_before": compressed_count,
                        "compressed_count_after": compressed_count,
                        "uncompressed_count_before": uncompressed_count,
                        "uncompressed_count_after": uncompressed_count,
                        "messages_compressed": len(messages_to_compress),
                        "error": "compressed summary persistence failed",
                        "compression_input_tokens": compression_state.input_tokens,
                        "compression_output_tokens": compression_state.output_tokens,
                        "compression_total_tokens": compression_state.total_tokens,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    }
                )
                return False

            logger.info(
                f"Compressed {len(messages_to_compress)} messages for session {session_id}"
            )
            await persist_event(
                {
                    "event_type": "context_compression",
                    "action": "compression",
                    "status": "success",
                    "run_id": run_id,
                    "session_id": session_id,
                    "profile": profile_name,
                    "triggered": True,
                    "total_messages": total_count,
                    "compressed_count_before": compressed_count,
                    "compressed_count_after": new_count,
                    "uncompressed_count_before": uncompressed_count,
                    "uncompressed_count_after": total_count - new_count,
                    "messages_compressed": len(messages_to_compress),
                    "compression_threshold": profile_threshold,
                    "recent_messages_limit": profile_recent_limit,
                    "compression_llm_attempts": attempts,
                    "fallback_used": fallback_used,
                    "compression_input_tokens": compression_state.input_tokens,
                    "compression_output_tokens": compression_state.output_tokens,
                    "compression_total_tokens": compression_state.total_tokens,
                    "compression_llm_calls": compression_state.llm_call_count,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            )
            return True

        except Exception as e:
            logger.exception(f"Failed to compress context: {e}")
            await persist_event(
                {
                    "event_type": "context_compression",
                    "action": "compression",
                    "status": "failed",
                    "run_id": run_id,
                    "session_id": session_id,
                    "profile": profile_name,
                    "triggered": True,
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "compression_llm_attempts": attempts,
                    "fallback_used": fallback_used,
                    "compression_input_tokens": compression_state.input_tokens,
                    "compression_output_tokens": compression_state.output_tokens,
                    "compression_total_tokens": compression_state.total_tokens,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            )
            return False
        finally:
            reset_trace_state(compression_token)


# 单例
agent_context_builder = AgentContextBuilder()
agent_context_compressor = AgentContextCompressor()
