"""Service layer for managing user-owned knowledge documents."""

import logging
from typing import Dict, List, Optional

from app.database.document_repository import document_repository
from app.database.models import KnowledgeDocumentModel
from app.services.rag_service import rag_service_instance

logger = logging.getLogger(__name__)


class PersonalDocumentService:
    """
    Manages user-owned personal knowledge documents.
    All database operations are delegated to DocumentRepository.
    """
    
    ALLOWED_SOURCES = {"recipes", "tips", "personal"}

    async def create_document(
        self,
        *,
        user_id: str,
        dish_name: str,
        category: str,
        difficulty: str,
        data_source: str,
        content: str,
    ) -> KnowledgeDocumentModel:
        """Create a new personal document."""
        if data_source not in self.ALLOWED_SOURCES:
            raise ValueError(f"data_source must be one of: {', '.join(self.ALLOWED_SOURCES)}")

        # Create document via repository
        doc = await document_repository.create(
            user_id=user_id,
            dish_name=dish_name,
            category=category,
            difficulty=difficulty,
            data_source="personal",  # Always personal for user-created docs
            source_type=data_source,  # The type selected by user
            source=f"personal::{user_id}",
            is_dish_index=False,
            content=content,
        )

        # Index in vector store
        await rag_service_instance.add_personal_document(
            user_id=user_id,
            document_id=str(doc.id),
            dish_name=doc.dish_name,
            category=doc.category,
            difficulty=doc.difficulty,
            data_source=data_source,
            content=doc.content,
        )

        logger.info("Personal document created id=%s user=%s", doc.id, user_id)
        return doc

    async def get_document(self, user_id: str, document_id: str) -> Optional[dict]:
        """Get a single document by ID for the given user."""
        doc = await document_repository.get_by_id_for_user(document_id, user_id)
        return doc.to_dict() if doc else None

    async def update_document(
        self,
        *,
        user_id: str,
        document_id: str,
        dish_name: str,
        category: str,
        difficulty: str,
        data_source: str,
        content: str,
    ) -> Optional[KnowledgeDocumentModel]:
        """Update an existing document."""
        if data_source not in self.ALLOWED_SOURCES:
            raise ValueError(f"data_source must be one of: {', '.join(self.ALLOWED_SOURCES)}")

        # Update document via repository
        await self.delete_document(user_id, document_id)

        doc = await document_repository.create(
            doc_id=document_id,
            user_id=user_id,
            dish_name=dish_name,
            category=category,
            difficulty=difficulty,
            data_source="personal",  # Always personal for user-created docs
            source_type=data_source,  # The type selected by user
            source=f"personal::{user_id}",
            is_dish_index=False,
            content=content,
        )
        
        if not doc:
            return None

        # Update in vector store
        await rag_service_instance.update_personal_document(
            user_id=user_id,
            document_id=document_id,
            dish_name=doc.dish_name,
            category=doc.category,
            difficulty=doc.difficulty,
            data_source=data_source,
            content=doc.content,
        )

        logger.info("Personal document updated id=%s user=%s", doc.id, user_id)
        return doc

    async def delete_document(self, user_id: str, document_id: str) -> bool:
        """Delete a document by ID for the given user."""
        deleted = await document_repository.delete(document_id, user_id)

        if deleted:
            # Remove from vector store
            await rag_service_instance.delete_personal_document(
                user_id=user_id,
                document_id=document_id,
            )
            logger.info("Personal document deleted id=%s user=%s", document_id, user_id)

        return deleted

    async def list_documents(self, user_id: str, limit: int = 50, offset: int = 0) -> List[dict]:
        """List documents for a user."""
        docs = await document_repository.list_by_user(user_id, limit=limit, offset=offset)
        return [doc.to_dict() for doc in docs]

    def get_available_options(self, user_id: str) -> Dict[str, List[str]]:
        """Get available metadata options (merged global + personal). No DB access."""
        return document_repository.get_metadata_options(user_id)


personal_document_service = PersonalDocumentService()
