"""
Vision Model Provider
Provides vision model access using the unified LLMProvider infrastructure.
"""

import base64
import logging
from dataclasses import dataclass
from typing import List, Optional, Union

from langchain_core.messages import BaseMessage, HumanMessage

from app.config import settings
from app.config.llm_config import VisionLLMConfig
from app.llm import get_usage_callbacks, llm_context

logger = logging.getLogger(__name__)


@dataclass
class ImageInput:
    """
    Represents an image input for vision processing.

    Supports two modes:
    - URL mode: image_url is a direct URL to the image
    - Base64 mode: image_data is base64-encoded image bytes with mime_type
    """

    image_url: Optional[str] = None
    image_data: Optional[str] = None  # Base64 encoded
    mime_type: str = "image/jpeg"

    def to_message_content(self) -> dict:
        """Convert to LangChain message content format."""
        if self.image_url:
            return {"type": "image_url", "image_url": {"url": self.image_url}}
        elif self.image_data:
            # Use data URL format for base64 images
            data_url = f"data:{self.mime_type};base64,{self.image_data}"
            return {"type": "image_url", "image_url": {"url": data_url}}
        else:
            raise ValueError("Either image_url or image_data must be provided")

    @classmethod
    def from_url(cls, url: str) -> "ImageInput":
        """Create from URL."""
        return cls(image_url=url)

    @classmethod
    def from_base64(cls, data: str, mime_type: str = "image/jpeg") -> "ImageInput":
        """Create from base64 encoded data."""
        return cls(image_data=data, mime_type=mime_type)

    @classmethod
    def from_bytes(cls, data: bytes, mime_type: str = "image/jpeg") -> "ImageInput":
        """Create from raw bytes."""
        encoded = base64.b64encode(data).decode("utf-8")
        return cls(image_data=encoded, mime_type=mime_type)


class VisionProvider:
    """
    Provider for vision/multimodal model access.
    Uses the unified LLMProvider infrastructure with llm_type="vision".
    """

    MODULE_NAME = "vision_understanding"

    def __init__(self):
        """
        Initialize vision provider using LLMProvider.
        """
        from app.llm.provider import LLMProvider

        self._provider = LLMProvider(settings.llm)
        self._invoker = self._provider.create_invoker(llm_type="vision")
        self._callbacks = get_usage_callbacks()

    @property
    def config(self) -> VisionLLMConfig:
        """Get vision configuration."""
        profile = self._provider.get_profile("vision")
        # Cast to VisionLLMConfig since we know it's the vision profile
        return profile  # type: ignore

    @property
    def is_enabled(self) -> bool:
        """Check if vision is enabled."""
        return bool(self.config.api_key)

    def build_multimodal_message(
        self,
        text: str,
        images: List[ImageInput],
    ) -> HumanMessage:
        """
        Build a multimodal message with text and images.

        Args:
            text: Text prompt/question
            images: List of image inputs

        Returns:
            HumanMessage with multimodal content
        """
        content: List[Union[str, dict]] = []

        # Add text content first
        if text:
            content.append({"type": "text", "text": text})

        # Add image contents
        for image in images:
            content.append(image.to_message_content())

        return HumanMessage(content=content)  # type: ignore

    async def analyze(
        self,
        text: str,
        images: List[ImageInput],
        system_prompt: Optional[str] = None,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> str:
        """
        Analyze images with text prompt.

        Args:
            text: Text prompt/question about the images
            images: List of images to analyze
            system_prompt: Optional system prompt for context
            user_id: User ID for tracking (optional)
            conversation_id: Conversation ID for tracking (optional)

        Returns:
            Model's response as string
        """
        if not self.is_enabled:
            raise RuntimeError("Vision module is not enabled or API key is missing")

        if not images:
            raise ValueError("At least one image is required")

        # Build messages
        messages: List[BaseMessage] = []

        # Add system message if provided
        if system_prompt:
            from langchain_core.messages import SystemMessage

            messages.append(SystemMessage(content=system_prompt))

        # Build multimodal human message
        human_msg = self.build_multimodal_message(text, images)
        messages.append(human_msg)

        logger.info(
            f"Vision analysis: text='{text[:50]}...', images={len(images)}, "
            f"model={self.config.model_names[0]}"
        )

        try:
            # Use llm_context for usage tracking
            with llm_context(self.MODULE_NAME, user_id, conversation_id):
                response = await self._invoker.ainvoke(
                    messages,
                    response_format={
                        "type": "json_object"
                    },  # Best effort; ignored if unsupported
                )
            result = str(response.content)
            logger.debug(f"Vision response: {result[:200]}...")
            return result
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}", exc_info=True)
            raise

    def validate_image(
        self, mime_type: str, size_bytes: int
    ) -> tuple[bool, Optional[str]]:
        """
        Validate image format and size.

        Args:
            mime_type: MIME type of the image
            size_bytes: Size of the image in bytes

        Returns:
            Tuple of (is_valid, error_message)
        """
        config = self.config

        # Check format
        if mime_type not in config.supported_formats:
            return (
                False,
                f"Unsupported image format: {mime_type}. Supported: {config.supported_formats}",
            )

        # Check size
        max_size_bytes = config.max_image_size_mb * 1024 * 1024
        if size_bytes > max_size_bytes:
            return (
                False,
                f"Image too large: {size_bytes / 1024 / 1024:.2f}MB. Maximum: {config.max_image_size_mb}MB",
            )

        return True, None


# Global instance
vision_provider = VisionProvider()
