"""Query service for executing semantic search queries."""

import logging
import time
from typing import Any, Optional

from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

from doc_serve_server.indexing import EmbeddingGenerator, get_embedding_generator
from doc_serve_server.indexing.bm25_index import BM25IndexManager, get_bm25_manager
from doc_serve_server.models import QueryMode, QueryRequest, QueryResponse, QueryResult
from doc_serve_server.storage import VectorStoreManager, get_vector_store

logger = logging.getLogger(__name__)


class VectorManagerRetriever(BaseRetriever):
    """LlamaIndex retriever wrapper for VectorStoreManager."""

    def __init__(
        self,
        service: "QueryService",
        top_k: int,
        threshold: float,
    ):
        super().__init__()
        self.service = service
        self.top_k = top_k
        self.threshold = threshold

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        # Synchronous retrieve not supported, use aretrieve
        return []

    async def _aretrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        query_embedding = await self.service.embedding_generator.embed_query(
            query_bundle.query_str
        )
        results = await self.service.vector_store.similarity_search(
            query_embedding=query_embedding,
            top_k=self.top_k,
            similarity_threshold=self.threshold,
        )
        return [
            NodeWithScore(
                node=TextNode(text=res.text, id_=res.chunk_id, metadata=res.metadata),
                score=res.score,
            )
            for res in results
        ]


class QueryService:
    """
    Executes semantic, keyword, and hybrid search queries.

    Coordinates embedding generation, vector similarity search,
    and BM25 retrieval with result fusion.
    """

    def __init__(
        self,
        vector_store: Optional[VectorStoreManager] = None,
        embedding_generator: Optional[EmbeddingGenerator] = None,
        bm25_manager: Optional[BM25IndexManager] = None,
    ):
        """
        Initialize the query service.

        Args:
            vector_store: Vector store manager instance.
            embedding_generator: Embedding generator instance.
            bm25_manager: BM25 index manager instance.
        """
        self.vector_store = vector_store or get_vector_store()
        self.embedding_generator = embedding_generator or get_embedding_generator()
        self.bm25_manager = bm25_manager or get_bm25_manager()

    def is_ready(self) -> bool:
        """
        Check if the service is ready to process queries.

        Returns:
            True if the vector store is initialized and has documents.
        """
        return self.vector_store.is_initialized

    async def execute_query(self, request: QueryRequest) -> QueryResponse:
        """
        Execute a search query based on the requested mode.

        Args:
            request: QueryRequest with query text and parameters.

        Returns:
            QueryResponse with ranked results.

        Raises:
            RuntimeError: If the service is not ready.
        """
        if not self.is_ready():
            raise RuntimeError(
                "Query service not ready. Please wait for indexing to complete."
            )

        start_time = time.time()

        if request.mode == QueryMode.BM25:
            results = await self._execute_bm25_query(request)
        elif request.mode == QueryMode.VECTOR:
            results = await self._execute_vector_query(request)
        else:  # HYBRID
            results = await self._execute_hybrid_query(request)

        # Apply content filters if specified
        if any([request.source_types, request.languages, request.file_paths]):
            results = self._filter_results(results, request)

        query_time_ms = (time.time() - start_time) * 1000

        logger.debug(
            f"Query ({request.mode}) '{request.query[:50]}...' returned "
            f"{len(results)} results in {query_time_ms:.2f}ms"
        )

        return QueryResponse(
            results=results,
            query_time_ms=query_time_ms,
            total_results=len(results),
        )

    async def _execute_vector_query(self, request: QueryRequest) -> list[QueryResult]:
        """Execute pure semantic search."""
        query_embedding = await self.embedding_generator.embed_query(request.query)
        where_clause = self._build_where_clause(request.source_types, request.languages)
        search_results = await self.vector_store.similarity_search(
            query_embedding=query_embedding,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
            where=where_clause,
        )

        return [
            QueryResult(
                text=res.text,
                source=res.metadata.get(
                    "source", res.metadata.get("file_path", "unknown")
                ),
                score=res.score,
                vector_score=res.score,
                chunk_id=res.chunk_id,
                source_type=res.metadata.get("source_type", "doc"),
                language=res.metadata.get("language"),
                metadata={
                    k: v
                    for k, v in res.metadata.items()
                    if k not in ("source", "file_path", "source_type", "language")
                },
            )
            for res in search_results
        ]

    async def _execute_bm25_query(self, request: QueryRequest) -> list[QueryResult]:
        """Execute pure keyword search."""
        if not self.bm25_manager.is_initialized:
            raise RuntimeError("BM25 index not initialized")

        retriever = self.bm25_manager.get_retriever(top_k=request.top_k)
        nodes = await retriever.aretrieve(request.query)

        return [
            QueryResult(
                text=node.node.get_content(),
                source=node.node.metadata.get(
                    "source", node.node.metadata.get("file_path", "unknown")
                ),
                score=node.score or 0.0,
                bm25_score=node.score,
                chunk_id=node.node.node_id,
                source_type=node.node.metadata.get("source_type", "doc"),
                language=node.node.metadata.get("language"),
                metadata={
                    k: v
                    for k, v in node.node.metadata.items()
                    if k not in ("source", "file_path", "source_type", "language")
                },
            )
            for node in nodes
        ]

    async def _execute_hybrid_query(self, request: QueryRequest) -> list[QueryResult]:
        """Execute hybrid search using Relative Score Fusion."""
        # For US5, we want to provide individual scores.
        # We'll perform the individual searches first to get the scores.

        # Get corpus size to avoid requesting more than available
        corpus_size = await self.vector_store.get_count()
        effective_top_k = min(request.top_k, corpus_size)

        # Build ChromaDB where clause for filtering
        where_clause = self._build_where_clause(request.source_types, request.languages)

        # 1. Vector Search
        query_embedding = await self.embedding_generator.embed_query(request.query)
        vector_results = await self.vector_store.similarity_search(
            query_embedding=query_embedding,
            top_k=effective_top_k,
            similarity_threshold=request.similarity_threshold,
            where=where_clause,
        )


        # 2. BM25 Search
        bm25_results = []
        if self.bm25_manager.is_initialized:
            # Use the new filtered search method
            bm25_results = await self.bm25_manager.search_with_filters(
                query=request.query,
                top_k=effective_top_k,
                source_types=request.source_types,
                languages=request.languages,
                max_results=corpus_size,
            )
        # Convert BM25 results to same format as vector results
        bm25_query_results = []
        for node in bm25_results:
            bm25_query_results.append(QueryResult(
                text=node.node.get_content(),
                source=node.node.metadata.get(
                    "source", node.node.metadata.get("file_path", "unknown")
                ),
                score=node.score or 0.0,
                bm25_score=node.score,
                chunk_id=node.node.node_id,
                source_type=node.node.metadata.get("source_type", "doc"),
                language=node.node.metadata.get("language"),
                metadata={
                    k: v for k, v in node.node.metadata.items()
                    if k not in ("source", "file_path", "source_type", "language")
                },
            ))


        # 3. Simple hybrid fusion for small corpora
        # Combine vector and BM25 results manually to avoid retriever complexity

        # Score normalization: bring both to 0-1 range
        max_vector_score = max((r.score for r in vector_results), default=1.0) or 1.0
        max_bm25_score = max(
            (r.bm25_score or 0.0 for r in bm25_query_results), default=1.0
        ) or 1.0

        # Create combined results map
        combined_results = {}

        # Add vector results (convert SearchResult to QueryResult)
        for res in vector_results:
            query_result = QueryResult(
                text=res.text,
                source=res.metadata.get(
                    "source", res.metadata.get("file_path", "unknown")
                ),
                score=res.score,
                vector_score=res.score,
                chunk_id=res.chunk_id,
                source_type=res.metadata.get("source_type", "doc"),
                language=res.metadata.get("language"),
                metadata={
                    k: v for k, v in res.metadata.items()
                    if k not in ("source", "file_path", "source_type", "language")
                },
            )
            combined_results[res.chunk_id] = {
                "result": query_result,
                "vector_score": res.score / max_vector_score,
                "bm25_score": 0.0,
                "total_score": request.alpha * (res.score / max_vector_score),
            }

        # Add/merge BM25 results
        for res in bm25_query_results:
            chunk_id = res.chunk_id
            bm25_normalized = (res.bm25_score or 0.0) / max_bm25_score
            bm25_weighted = (1.0 - request.alpha) * bm25_normalized

            if chunk_id in combined_results:
                combined_results[chunk_id]["bm25_score"] = bm25_normalized
                combined_results[chunk_id]["total_score"] += bm25_weighted
                # Update BM25 score on existing result
                combined_results[chunk_id]["result"].bm25_score = res.bm25_score
            else:
                combined_results[chunk_id] = {
                    "result": res,
                    "vector_score": 0.0,
                    "bm25_score": bm25_normalized,
                    "total_score": bm25_weighted,
                }

        # Convert to final results
        fused_nodes = []
        for _chunk_id, data in combined_results.items():
            result = data["result"]
            # Update score with combined score
            result.score = data["total_score"]
            fused_nodes.append(result)

        # Sort by combined score and take top_k
        fused_nodes.sort(key=lambda x: x.score, reverse=True)
        fused_nodes = fused_nodes[:request.top_k]

        return fused_nodes

    async def get_document_count(self) -> int:
        """
        Get the total number of indexed documents.

        Returns:
            Number of documents in the vector store.
        """
        if not self.is_ready():
            return 0
        return await self.vector_store.get_count()

    def _filter_results(
        self, results: list[QueryResult], request: QueryRequest
    ) -> list[QueryResult]:
        """
        Filter query results based on request parameters.

        Args:
            results: List of query results to filter.
            request: Query request with filter parameters.

        Returns:
            Filtered list of results.
        """
        filtered_results = results

        # Filter by source types
        if request.source_types:
            filtered_results = [
                r for r in filtered_results if r.source_type in request.source_types
            ]

        # Filter by languages
        if request.languages:
            filtered_results = [
                r
                for r in filtered_results
                if r.language and r.language in request.languages
            ]

        # Filter by file paths (with wildcard support)
        if request.file_paths:
            import fnmatch

            filtered_results = [
                r
                for r in filtered_results
                if any(
                    fnmatch.fnmatch(r.source, pattern) for pattern in request.file_paths
                )
            ]

        return filtered_results

    def _build_where_clause(
        self,
        source_types: list[str] | None,
        languages: list[str] | None
    ) -> dict[str, Any] | None:
        """
        Build ChromaDB where clause from filter parameters.

        Args:
            source_types: List of source types to filter by.
            languages: List of languages to filter by.

        Returns:
            ChromaDB where clause dict or None.
        """
        conditions = []

        if source_types:
            if len(source_types) == 1:
                conditions.append({"source_type": source_types[0]})
            else:
                conditions.append({"source_type": {"$in": source_types}})

        if languages:
            if len(languages) == 1:
                conditions.append({"language": languages[0]})
            else:
                conditions.append({"language": {"$in": languages}})

        if not conditions:
            return None
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return {"$and": conditions}


# Singleton instance
_query_service: Optional[QueryService] = None


def get_query_service() -> QueryService:
    """Get the global query service instance."""
    global _query_service
    if _query_service is None:
        _query_service = QueryService()
    return _query_service
