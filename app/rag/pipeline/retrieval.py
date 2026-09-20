# app/rag/pipeline/retrieval.py
import asyncio
import logging
from typing import List, Tuple, Optional

from langchain_milvus import Milvus
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

class RetrievalOptimizationModule:
    """
    Handles advanced retrieval strategies using Milvus built-in hybrid search.
    Combines dense vector search with sparse BM25 search using Milvus native capabilities.
    """
    def __init__(
        self, 
        vectorstore: Milvus, 
        score_threshold: float = 0.0,
        default_ranker_type: str = "rrf",
        default_ranker_weights: List[float] = [0.5, 0.5]
    ):
        """
        Initializes the retrieval optimization module.
        Args:
            vectorstore: The Milvus vectorstore with BM25 built-in function enabled.
            score_threshold: Minimum score threshold for filtering low-quality results.
            default_ranker_type: Default ranker type ("rrf" or "weighted").
            default_ranker_weights: Default weights for [dense, sparse] when using weighted ranker.
        """
        if not vectorstore:
            raise ValueError("Vectorstore must be provided.")
            
        self.vectorstore = vectorstore
        self.score_threshold = score_threshold
        self.default_ranker_type = default_ranker_type
        self.default_ranker_weights = default_ranker_weights
        
        logger.info("Retrieval module initialized with Milvus hybrid search")
        
    async def hybrid_search(
        self, 
        query: str, 
        top_k: int,
        ranker_type: Optional[str] = None,
        ranker_weights: Optional[List[float]] = None,
        score_threshold: Optional[float] = None,
        expr: Optional[str] = None,
    ) -> Tuple[List[Document], List[float]]:
        """
        Performs hybrid search using Milvus built-in BM25 and dense vector search.
        Supports dynamic ranker configuration and score-based filtering.
        
        Args:
            query: The user's search query.
            top_k: The number of documents to retrieve (before filtering).
            ranker_type: Ranker type ("rrf" or "weighted"). Uses default if None.
            ranker_weights: Weights for [dense, sparse] when using weighted ranker. Uses default if None.
            score_threshold: Minimum score threshold. Uses instance default if None.
            
        Returns:
            A tuple of (documents, scores) where both lists have the same length.
        """
        # Use defaults if not specified
        ranker_type = ranker_type or self.default_ranker_type
        ranker_weights = ranker_weights or self.default_ranker_weights
        score_threshold = score_threshold if score_threshold is not None else self.score_threshold
        
        logger.info(
            "hybrid search top_k=%d ranker=%s threshold=%s",
            top_k,
            ranker_type,
            score_threshold,
        )
        
        # Prepare ranker parameters
        ranker_params = {"norm_score": True}
        if ranker_type == "weighted":
            ranker_params = {"weights": ranker_weights, "norm_score": True}
        
        # Milvus hybrid search with configurable ranker
        # Use asyncio.to_thread to avoid blocking the event loop
        results = await asyncio.to_thread(
            self.vectorstore.similarity_search_with_score,
            query=query,
            k=top_k,
            fetch_k=int(top_k * 4),
            ranker_type=ranker_type,
            ranker_params=ranker_params if ranker_params else None,
            expr=expr,
        )
        
        # Extract documents and scores
        docs, scores = [], []
        for doc, score in results:
            docs.append(doc)
            scores.append(score)
        
        logger.info("hybrid search docs=%d", len(docs))
        
        # Apply score threshold filtering
        if score_threshold > 0 and ranker_type == "weighted":
            filtered_results = [(doc, score) for doc, score in zip(docs, scores) if score >= score_threshold]
            filtered_docs, filtered_scores = [], []
            for doc, score in filtered_results:
                filtered_docs.append(doc)
                filtered_scores.append(score)
            
            logger.info(
                "score filtering %d -> %d (threshold=%s)",
                len(docs),
                len(filtered_docs),
                score_threshold,
            )
            
            return filtered_docs, filtered_scores
        
        return docs, scores
    
    def intelligent_ranker_selection(self, query: str) -> Tuple[str, List[float]]:
        """
        Intelligently selects ranker type and weights based on query characteristics.
        This can be extended with more sophisticated logic or ML models.
        
        Args:
            query: The user's search query.
            
        Returns:
            A tuple of (ranker_type, weights).
        """
        query_lower = query.lower()
        
        # Keyword-heavy queries (with specific terms) → favor BM25
        keyword_indicators = ["怎么做", "如何", "步骤", "方法", "做法", "recipe", "how to"]
        if any(indicator in query_lower for indicator in keyword_indicators):
            logger.debug("keyword indicators detected; weighted ranker BM25 bias")
            return "weighted", [0.4, 0.6]  # Favor sparse/BM25
        
        # Semantic/conceptual queries → favor dense embeddings
        # Expanded indicators to include recommendation queries
        semantic_indicators = [
            "推荐", "类似", "什么菜", "有哪些", "有什么", "适合", "建议", 
            "recommend", "similar", "suggest", "what", "which",
        ]
        if any(indicator in query_lower for indicator in semantic_indicators):
            logger.debug("semantic indicators detected; weighted ranker dense bias")
            return "weighted", [0.6, 0.4]  # Favor dense/semantic
        
        # Balanced queries
        return "weighted", [0.5, 0.5]
