# app/rag/__init__.py
"""
RAG (Retrieval-Augmented Generation) module for CookHero.

This module provides the core RAG pipeline functionality including:
- Document processing and chunking
- Vector embeddings and storage
- Retrieval optimization
- Caching for performance
- Reranking for relevance
"""

from app.rag.cache import CacheManager
from app.rag.pipeline.document_processor import document_processor
from app.rag.pipeline.retrieval import RetrievalOptimizationModule
from app.rag.pipeline.generation import GenerationIntegrationModule
from app.rag.pipeline.metadata_filter import MetadataFilterExtractor

__all__ = [
    # Cache
    "CacheManager",
    # Pipeline
    "document_processor",
    "RetrievalOptimizationModule",
    "GenerationIntegrationModule",
    "MetadataFilterExtractor",
]
