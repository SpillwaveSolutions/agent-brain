"""Query service for executing semantic search queries."""

import logging
import time
from typing import Optional, List

from ..models import QueryRequest, QueryResponse, QueryResult
from ..indexing import EmbeddingGenerator, get_embedding_generator
from ..storage import VectorStoreManager, get_vector_store

logger = logging.getLogger(__name__)


class QueryService:
    """
    Executes semantic search queries against the vector store.

    Coordinates embedding generation and similarity search
    with result filtering and formatting.
    """

    def __init__(
        self,
        vector_store: Optional[VectorStoreManager] = None,
        embedding_generator: Optional[EmbeddingGenerator] = None,
    ):
        """
        Initialize the query service.

        Args:
            vector_store: Vector store manager instance.
            embedding_generator: Embedding generator instance.
        """
        self.vector_store = vector_store or get_vector_store()
        self.embedding_generator = embedding_generator or get_embedding_generator()

    def is_ready(self) -> bool:
        """
        Check if the service is ready to process queries.

        Returns:
            True if the vector store is initialized and has documents.
        """
        return self.vector_store.is_initialized

    async def execute_query(self, request: QueryRequest) -> QueryResponse:
        """
        Execute a semantic search query.

        Args:
            request: QueryRequest with query text and parameters.

        Returns:
            QueryResponse with ranked results.

        Raises:
            RuntimeError: If the service is not ready.
        """
        if not self.is_ready():
            raise RuntimeError(
                "Query service not ready. "
                "Please wait for indexing to complete."
            )

        start_time = time.time()

        # Generate query embedding
        query_embedding = await self.embedding_generator.embed_query(request.query)

        # Search vector store
        search_results = await self.vector_store.similarity_search(
            query_embedding=query_embedding,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
        )

        # Convert to response format
        results: List[QueryResult] = [
            QueryResult(
                text=result.text,
                source=result.metadata.get("source", result.metadata.get("file_path", "unknown")),
                score=result.score,
                chunk_id=result.chunk_id,
                metadata={
                    k: v for k, v in result.metadata.items()
                    if k not in ("source", "file_path")
                },
            )
            for result in search_results
        ]

        query_time_ms = (time.time() - start_time) * 1000

        logger.debug(
            f"Query '{request.query[:50]}...' returned {len(results)} results "
            f"in {query_time_ms:.2f}ms"
        )

        return QueryResponse(
            results=results,
            query_time_ms=query_time_ms,
            total_results=len(results),
        )

    async def get_document_count(self) -> int:
        """
        Get the total number of indexed documents.

        Returns:
            Number of documents in the vector store.
        """
        if not self.is_ready():
            return 0
        return await self.vector_store.get_count()


# Singleton instance
_query_service: Optional[QueryService] = None


def get_query_service() -> QueryService:
    """Get the global query service instance."""
    global _query_service
    if _query_service is None:
        _query_service = QueryService()
    return _query_service
