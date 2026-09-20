# app/config/__init__.py
"""
Configuration module for CookHero.
Provides unified access to all configuration settings.

Usage:
    from app.config import settings, DefaultRAGConfig, LLMType

    # Access global settings
    print(settings.PROJECT_NAME)

    # Access global LLM configuration (layered: fast/normal)
    print(settings.llm.fast.model_names)
    print(settings.llm.normal.model_names)

    # Access database configurations
    print(settings.database.postgres.host)
    print(settings.database.redis.host)
    print(settings.database.milvus.host)

    # Access RAG configuration
    print(settings.rag.vector_store.collection_names)
    # or use the alias:
    print(DefaultRAGConfig.vector_store.collection_names)

    # Access MCP configuration
    print(settings.mcp.amap_api_key)

    # Access Image Generation configuration
    print(settings.image_generation.model)
"""

from app.config.config import settings, Settings, DefaultRAGConfig
from app.config.database_config import (
    DatabaseConfig,
    PostgresConfig,
    RedisConfig,
    MilvusConfig,
)
from app.config.llm_config import LLMConfig, LLMType, LLMProfileConfig, VisionLLMConfig
from app.config.rag_config import (
    RAGConfig,
    PathsConfig,
    VectorStoreConfig,
    EmbeddingConfig,
    RetrievalConfig,
    RerankerConfig,
    CacheConfig,
    DataSourceConfig,
    HowToCookConfig,
)
from app.config.web_search_config import WebSearchConfig, DeepResearchConfig
from app.config.vision_config import VisionConfig, ImageGenerationConfig, ImageStorageConfig
from app.config.mcp_config import MCPConfig, MCPServerConfig

__all__ = [
    # Main settings
    "settings",
    "Settings",
    "DefaultRAGConfig",
    # Database configuration classes
    "DatabaseConfig",
    "PostgresConfig",
    "RedisConfig",
    "MilvusConfig",
    # LLM configuration
    "LLMConfig",
    "LLMType",
    "LLMProfileConfig",
    "VisionLLMConfig",
    # RAG configuration classes
    "RAGConfig",
    "PathsConfig",
    "VectorStoreConfig",
    "EmbeddingConfig",
    "RetrievalConfig",
    "RerankerConfig",
    "CacheConfig",
    "DataSourceConfig",
    "HowToCookConfig",
    # Web Search configuration
    "WebSearchConfig",
    "DeepResearchConfig",
    # Vision configuration
    "VisionConfig",
    # MCP configuration
    "MCPConfig",
    "MCPServerConfig",
    "ImageGenerationConfig",
    "ImageStorageConfig",
]
