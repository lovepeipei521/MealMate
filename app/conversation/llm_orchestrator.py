from typing import AsyncGenerator, List, Optional

from langchain_core.messages import BaseMessage

from app.config import settings, LLMType
from app.llm import LLMProvider, llm_context


class LLMOrchestrator:
    """Handles LLM invocation and streaming responses."""

    MODULE_NAME = "main_response"

    def __init__(
        self,
        llm_type: LLMType | str = LLMType.NORMAL,
        provider: LLMProvider | None = None,
    ):
        self._llm_type = llm_type
        self._provider = provider or LLMProvider(settings.llm)
        # Use tracked invoker for usage statistics
        self._llm = self._provider.create_invoker(llm_type, streaming=True)

    async def stream(
        self,
        messages: List[BaseMessage],
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        # Use llm_context for usage tracking
        with llm_context(self.MODULE_NAME, user_id, conversation_id):
            async for chunk in self._llm.astream(messages):
                if chunk.content:
                    yield str(chunk.content)
