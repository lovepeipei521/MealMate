# app/database/conversation_repository.py
"""
Repository layer for conversation persistence using PostgreSQL.
Provides async CRUD operations for conversations and messages.
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload

from app.database.models import ConversationModel, MessageModel
from app.database.session import get_session_context

logger = logging.getLogger(__name__)


class ConversationRepository:
    """
    Async repository for conversation persistence.
    Replaces in-memory ConversationStore for production use.
    """

    async def get_or_create(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> ConversationModel:
        """Get existing conversation or create a new one."""
        async with get_session_context() as session:
            if conversation_id:
                try:
                    conv_uuid = uuid.UUID(conversation_id)
                    stmt = (
                        select(ConversationModel)
                        .options(selectinload(ConversationModel.messages))
                        .where(ConversationModel.id == conv_uuid)
                    )
                    result = await session.execute(stmt)
                    conversation = result.scalar_one_or_none()
                    if conversation:
                        return conversation
                except ValueError:
                    logger.warning(f"Invalid conversation_id format: {conversation_id}")

            # Create new conversation
            conversation = ConversationModel(user_id=user_id)
            session.add(conversation)
            await session.flush()
            return conversation

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        sources: Optional[list] = None,
        intent: Optional[str] = None,
        thinking: Optional[list] = None,
        thinking_duration_ms: Optional[int] = None,
        answer_duration_ms: Optional[int] = None,
    ) -> MessageModel:
        """Add a message to a conversation."""
        async with get_session_context() as session:
            conv_uuid = uuid.UUID(conversation_id)

            # Update conversation timestamp
            stmt = select(ConversationModel).where(ConversationModel.id == conv_uuid)
            result = await session.execute(stmt)
            conversation = result.scalar_one_or_none()

            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")

            conversation.updated_at = datetime.now()

            # Create message
            message = MessageModel(
                conversation_id=conv_uuid,
                role=role,
                content=content,
                sources=sources,
                intent=intent,
                thinking=thinking,
                thinking_duration_ms=thinking_duration_ms,
                answer_duration_ms=answer_duration_ms,
            )
            session.add(message)
            await session.flush()
            return message

    async def get_history(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> Optional[List[dict]]:
        """Get conversation history as list of dicts."""
        async with get_session_context() as session:
            try:
                conv_uuid = uuid.UUID(conversation_id)
            except ValueError:
                return None

            stmt = (
                select(MessageModel)
                .where(MessageModel.conversation_id == conv_uuid)
                .order_by(MessageModel.created_at)
            )
            if limit:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            messages = result.scalars().all()

            if not messages:
                # Check if conversation exists
                conv_stmt = select(ConversationModel).where(
                    ConversationModel.id == conv_uuid
                )
                conv_result = await session.execute(conv_stmt)
                if not conv_result.scalar_one_or_none():
                    return None
                return []

            return [msg.to_dict() for msg in messages]

    async def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> List[MessageModel]:
        """Get message models for a conversation."""
        async with get_session_context() as session:
            conv_uuid = uuid.UUID(conversation_id)
            stmt = (
                select(MessageModel)
                .where(MessageModel.conversation_id == conv_uuid)
                .order_by(MessageModel.created_at)
            )
            if limit:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def clear(self, conversation_id: str) -> bool:
        """Delete a conversation and all its messages."""
        async with get_session_context() as session:
            try:
                conv_uuid = uuid.UUID(conversation_id)
            except ValueError:
                return False

            stmt = delete(ConversationModel).where(ConversationModel.id == conv_uuid)
            result = await session.execute(stmt)
            return result.rowcount > 0  # type: ignore

    async def update_title(self, conversation_id: str, title: str) -> bool:
        """Update the title of a conversation."""
        async with get_session_context() as session:
            try:
                conv_uuid = uuid.UUID(conversation_id)
            except ValueError:
                return False

            stmt = select(ConversationModel).where(ConversationModel.id == conv_uuid)
            result = await session.execute(stmt)
            conversation = result.scalar_one_or_none()

            if not conversation:
                return False

            conversation.title = title
            await session.flush()

            logger.info(
                "Updated title for conversation %s to '%s'",
                conversation_id,
                title,
            )
            return True

    async def list_conversations(
        self,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[dict], int]:
        """List conversations with metadata, ordered by updated_at desc.

        Returns:
            Tuple of (conversations list, total count)
        """
        async with get_session_context() as session:
            # Base query for filtering
            base_filter = []
            if user_id:
                base_filter.append(ConversationModel.user_id == user_id)

            # Get total count
            count_stmt = select(func.count(ConversationModel.id))
            if base_filter:
                count_stmt = count_stmt.where(*base_filter)
            count_result = await session.execute(count_stmt)
            total_count = count_result.scalar() or 0

            # Get paginated conversations
            stmt = (
                select(ConversationModel)
                .options(selectinload(ConversationModel.messages))
                .order_by(ConversationModel.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )

            if base_filter:
                stmt = stmt.where(*base_filter)

            result = await session.execute(stmt)
            conversations = result.scalars().all()

            return [conv.to_dict() for conv in conversations], total_count

    async def get_conversation(
        self, conversation_id: str
    ) -> Optional[ConversationModel]:
        """Get a single conversation by ID."""
        async with get_session_context() as session:
            try:
                conv_uuid = uuid.UUID(conversation_id)
            except ValueError:
                return None

            stmt = (
                select(ConversationModel)
                .options(selectinload(ConversationModel.messages))
                .where(ConversationModel.id == conv_uuid)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_compressed_summary(
        self, conversation_id: str
    ) -> tuple[Optional[str], int]:
        """
        Get the compressed summary and count for a conversation.

        Returns:
            Tuple of (compressed_summary, compressed_message_count)
        """
        async with get_session_context() as session:
            try:
                conv_uuid = uuid.UUID(conversation_id)
            except ValueError:
                return None, 0

            stmt = select(
                ConversationModel.compressed_summary,
                ConversationModel.compressed_message_count,
            ).where(ConversationModel.id == conv_uuid)

            result = await session.execute(stmt)
            row = result.one_or_none()

            if row:
                return row[0], row[1]
            return None, 0

    async def update_compressed_summary(
        self,
        conversation_id: str,
        summary: str,
        message_count: int,
    ) -> bool:
        """
        Update the compressed summary for a conversation.

        Args:
            conversation_id: The conversation ID
            summary: The new compressed summary
            message_count: Number of messages included in the summary

        Returns:
            True if update was successful
        """
        async with get_session_context() as session:
            try:
                conv_uuid = uuid.UUID(conversation_id)
            except ValueError:
                return False

            stmt = select(ConversationModel).where(ConversationModel.id == conv_uuid)
            result = await session.execute(stmt)
            conversation = result.scalar_one_or_none()

            if not conversation:
                return False

            conversation.compressed_summary = summary
            conversation.compressed_message_count = message_count
            await session.flush()

            logger.info(
                "Updated compressed summary for conversation %s (messages: %d)",
                conversation_id,
                message_count,
            )
            return True

    async def get_message_count(self, conversation_id: str) -> int:
        """Get the total number of messages in a conversation."""
        async with get_session_context() as session:
            try:
                conv_uuid = uuid.UUID(conversation_id)
            except ValueError:
                return 0

            stmt = select(func.count(MessageModel.id)).where(
                MessageModel.conversation_id == conv_uuid
            )
            result = await session.execute(stmt)
            return result.scalar() or 0


# Singleton instance
conversation_repository = ConversationRepository()
