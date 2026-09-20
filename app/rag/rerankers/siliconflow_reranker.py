# app/rag/rerankers/siliconflow_reranker.py
import logging
import httpx
from typing import List

from app.rag.rerankers.base import BaseReranker
from langchain_core.documents import Document
from app.config.rag_config import RerankerConfig

logger = logging.getLogger(__name__)

class SiliconFlowReranker(BaseReranker):
    """
    A reranker that uses the dedicated SiliconFlow rerank API endpoint.
    """

    def __init__(self, reranker_config: RerankerConfig):
        """
        Initializes the SiliconFlow Reranker.
        Args:
            reranker_config: The configuration for the reranker.
        """
        self.config = reranker_config
        self.api_url = self.config.base_url
        self.headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    async def rerank(self, query: str, documents: List[Document]) -> List[Document]:
        """
        Reranks and filters documents using the SiliconFlow API.

        Args:
            query: The user's query.
            documents: The list of documents to rerank.

        Returns:
            A filtered and sorted list of documents deemed most relevant.
        """
        if not documents:
            return []

        logger.info(f"Reranking {len(documents)} documents with SiliconFlow API...")
        
        doc_contents = [doc.page_content for doc in documents]
        
        payload = {
            "model": self.config.model_name,
            "query": query,
            "documents": doc_contents,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.api_url, headers=self.headers, json=payload, timeout=30.0)  # type: ignore
                response.raise_for_status()
                api_results = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred during rerank API call: {e}")
            logger.error(f"Response content: {e.response.text}")
            # Fallback: return original documents on API error
            return documents
        except Exception as e:
            logger.error(f"An unexpected error occurred during rerank API call: {e}")
            # Fallback: return original documents
            return documents

        # Process results
        results = api_results.get("results", [])
        if not results:
            logger.warning("Rerank API returned no results.")
            return []

        # Filter and sort documents based on reranker scores
        ranked_docs = []
        for res in results:
            score = res.get("relevance_score", 0.0)
            index = res.get("index")

            logger.info(f"Document {documents[index].metadata.get('dish_name', 'unknown')} received rerank score: {score}")

            if score >= self.config.score_threshold * 0.9:
                # The index from the API corresponds to the original documents list
                original_doc = documents[index]
                # Store the score in metadata for potential downstream use
                original_doc.metadata["rerank_score"] = score
                ranked_docs.append(original_doc)
        
        # Sort the final list by the new rerank score in descending order
        ranked_docs.sort(key=lambda doc: doc.metadata.get("rerank_score", 0.0), reverse=True)

        logger.info(f"Reranking complete. {len(documents)} -> {len(ranked_docs)} documents.")
        
        return ranked_docs
