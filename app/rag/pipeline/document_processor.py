# app/rag/data_sources/document_processor.py
"""
Unified document processor for RAG pipeline.
Handles chunk splitting and post-processing of retrieved documents.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter

from app.database.document_repository import document_repository

logger = logging.getLogger(__name__)


# Metadata keys required for all documents
REQUIRED_METADATA_KEYS = (
    "source",
    "parent_id",
    "dish_name",
    "category",
    "difficulty",
    "is_dish_index",
    "data_source",
    "user_id",
    "source_type",
)


class DocumentProcessor:
    """
    Unified processor for document operations:
    - Splitting documents into chunks
    - Post-processing retrieved chunks (fetching parent documents from DB)
    """

    def __init__(self, headers_to_split_on: List[tuple] | None = None):
        self.headers_to_split_on = headers_to_split_on or [
            ("#", "header_1"),
            ("##", "header_2"),
        ]
        self._splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=self.headers_to_split_on,
            strip_headers=False,
        )

    def create_chunks(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any],
    ) -> List[Document]:
        """
        Split a document into chunks for vector indexing.
        
        Args:
            doc_id: The parent document ID (will be stored in chunk metadata as parent_id)
            content: The document content to split
            metadata: Base metadata (will be copied to each chunk)
            
        Returns:
            List of chunk Documents with parent_id set
        """
        chunks: List[Document] = []
        
        # Regular markdown splitting
        md_chunks = self._splitter.split_text(content)
        
        for chunk_doc in md_chunks:
            chunk_metadata = self._clone_metadata(metadata, parent_id=doc_id)
            chunks.append(Document(
                id=str(uuid.uuid4()),
                page_content=chunk_doc.page_content,
                metadata=chunk_metadata,
            ))
        
        return chunks

    async def post_process_retrieval(
        self,
        retrieved_chunks: List[Document],
    ) -> List[Document]:
        """
        Convert retrieved chunks back to full parent documents.
        Fetches parent documents from the database.
        
        Implements the "small to large" retrieval pattern:
        - Groups chunks by parent_id
        - Fetches full parent content from PostgreSQL
        - Preserves the highest retrieval/rerank score for each parent
        
        Args:
            retrieved_chunks: List of chunk Documents from vector search
            
        Returns:
            List of parent Documents with full content
        """
        if not retrieved_chunks:
            return []

        # Collect all parent_ids and best scores
        parent_scores: Dict[str, Dict[str, float]] = {}
        
        for chunk in retrieved_chunks:
            parent_id = chunk.metadata.get("parent_id")
            if not parent_id:
                continue
            
            retrieval_score = chunk.metadata.get("retrieval_score", 0.0)
            rerank_score = chunk.metadata.get("rerank_score")
            
            if parent_id not in parent_scores:
                parent_scores[parent_id] = {
                    "retrieval_score": retrieval_score,
                    "rerank_score": rerank_score if rerank_score is not None else 0.0,
                    "is_index": chunk.metadata.get("is_dish_index", False),
                }
            else:
                # Keep the highest scores
                if retrieval_score > parent_scores[parent_id]["retrieval_score"]:
                    parent_scores[parent_id]["retrieval_score"] = retrieval_score
                if rerank_score is not None and rerank_score > parent_scores[parent_id].get("rerank_score", 0.0):
                    parent_scores[parent_id]["rerank_score"] = rerank_score

        # Fetch parent documents from database
        parent_ids = list(parent_scores.keys())
        parent_docs = await document_repository.get_parent_documents(parent_ids)

        # Build final documents with scores
        final_docs: List[Document] = []
        
        for parent_id, scores in parent_scores.items():
            if parent_id not in parent_docs:
                logger.warning("Parent document not found in database: %s", parent_id)
                continue
            
            parent_doc = parent_docs[parent_id]
            
            # Create a copy with scores
            doc_copy = Document(
                id=parent_doc.id,
                page_content=parent_doc.page_content,
                metadata=parent_doc.metadata.copy(),
            )
            doc_copy.metadata["retrieval_score"] = scores["retrieval_score"]
            if scores.get("rerank_score"):
                doc_copy.metadata["rerank_score"] = scores["rerank_score"]
            
            final_docs.append(doc_copy)
    
        # Sort by rerank_score (if available) or retrieval_score
        final_docs.sort(
            key=lambda d: (
                d.metadata.get("rerank_score", 0.0),
                d.metadata.get("retrieval_score", 0.0),
            ),
            reverse=True,
        )

        logger.info(
            "Post-processed %d chunks -> %d parent documents",
            len(retrieved_chunks),
            len(final_docs),
        )
        
        return final_docs

    def _clone_metadata(
        self,
        metadata: Dict[str, Any],
        *,
        parent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Clone metadata and optionally set parent_id."""
        cloned = {key: metadata.get(key) for key in REQUIRED_METADATA_KEYS}
        if parent_id is not None:
            cloned["parent_id"] = parent_id
        return cloned

    def _create_index_chunk_content(self, index_metadata: Dict[str, Any]) -> str:
        """
        Creates chunk content for dish index documents.
        Focuses on recommendation keywords for better semantic matching.
        """
        content_parts = ["推荐菜,菜谱列表,菜品,食谱,有哪些菜品推荐"]
        
        source = index_metadata.get("source", "")
        category = index_metadata.get("category", "")
        difficulty = index_metadata.get("difficulty", "")

        if "category" in source and category:
            content_parts.append(f"{category}推荐，")
        elif "difficulty" in source and difficulty:
            content_parts.append(f"{difficulty}难度推荐，")

        content_parts.append("欢迎根据口味挑选合适的菜谱")
        return "".join(content_parts)


# Singleton instance
document_processor = DocumentProcessor()
