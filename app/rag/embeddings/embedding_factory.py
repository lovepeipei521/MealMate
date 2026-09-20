# app/rag/embeddings/embedding_factory.py
import logging
from langchain_core.embeddings import Embeddings
from app.config import RAGConfig

logger = logging.getLogger(__name__)

def get_embedding_model(config: RAGConfig) -> Embeddings:
    """
    Factory function to create and return a local embedding model based on the config.
    Args:
        config: The RAG configuration object.
    Returns:
        An instance of a local embedding model.
    """
    from langchain_huggingface import HuggingFaceEmbeddings
    logger.info(f"Initializing local embedding model: {config.embedding.model_name}")
    return HuggingFaceEmbeddings(
        model_name=config.embedding.model_name,
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )
