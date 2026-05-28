"""Query service for executing semantic search queries."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

# Import reranker module to trigger provider registration
import agent_brain_server.providers.reranker  # noqa: F401
from agent_brain_server.config import settings

if TYPE_CHECKING:
    from agent_brain_server.services.query_cache import QueryCacheService
from agent_brain_server.config.provider_config import load_provider_settings
from agent_brain_server.indexing import EmbeddingGenerator, get_embedding_generator
from agent_brain_server.indexing.bm25_index import BM25IndexManager, get_bm25_manager
from agent_brain_server.indexing.graph_index import (
    GraphIndexManager,
    get_graph_index_manager,
)
from agent_brain_server.models import (
    QueryMode,
    QueryRequest,
    QueryResponse,
    QueryResult,
    ResultExplanation,
)
from agent_brain_server.providers import ProviderRegistry
from agent_brain_server.storage import (
    StorageBackendProtocol,
    VectorStoreManager,
    get_storage_backend,
    get_vector_store,
)

logger = logging.getLogger(__name__)


def _graphrag_enabled() -> bool:
    """YAML-aware enable check; honors test patches of module-level ``settings``."""
    try:
        yaml_value = load_provider_settings().graphrag.enabled
    except Exception:
        yaml_value = None
    if yaml_value is not None:
        return bool(yaml_value)
    return bool(settings.ENABLE_GRAPH_INDEX)


def _graphrag_rrf_k() -> int:
    """YAML-aware RRF k; falls back to env-var setting."""
    try:
        yaml_value = load_provider_settings().graphrag.rrf_k
    except Exception:
        yaml_value = None
    if yaml_value is not None:
        return int(yaml_value)
    return int(settings.GRAPH_RRF_K)


# Issue #159: explain=true support.
# Each mode handler stashes intermediate data in
# `QueryResult.metadata["_explain_scratch"]` (a transient dict) so that
# `_drain_explain_scratch` can rebuild a `ResultExplanation` at the end of
# `execute_query` — after reranking, which would otherwise discard
# per-retriever ranks and fusion weights.
EXPLAIN_SCRATCH_KEY = "_explain_scratch"


def _build_reason(
    result: QueryResult,
    scratch: dict[str, Any],
    mode: QueryMode,
) -> str:
    """Build the deterministic 'why this rank' one-liner.

    Priority order (first match wins):
      1. Rerank movement — cross-encoder changed the order (highest signal)
      2. Graph fallback — rare path that must be announced
      3. Top-of-mode summary for the active retrieval mode
    """
    movement = scratch.get("rerank_movement")
    if movement is not None and result.rerank_score is not None:
        if movement == 0:
            return (
                f"Reranker confirmed position #{result.original_rank} "
                f"(cross-encoder score {result.rerank_score:.2f})"
            )
        direction = "up" if movement > 0 else "down"
        plural = "" if abs(movement) == 1 else "s"
        return (
            f"Reranked {direction} {abs(movement)} place{plural} from "
            f"#{result.original_rank} (cross-encoder score "
            f"{result.rerank_score:.2f})"
        )

    if mode == QueryMode.GRAPH and scratch.get("graph_fallback"):
        score = result.vector_score if result.vector_score is not None else result.score
        return (
            f"Graph returned no hits; fell back to vector search "
            f"(score {score:.2f})"
        )

    if mode == QueryMode.HYBRID and "fused_score" in scratch:
        return (
            f"Hybrid match (alpha={scratch.get('alpha', 0.0):.2f}): "
            f"vector {scratch.get('vector_score_weighted', 0.0):.2f} + "
            f"BM25 {scratch.get('bm25_score_weighted', 0.0):.2f} -> "
            f"fused {scratch.get('fused_score', 0.0):.2f}"
        )

    if mode == QueryMode.MULTI and "rrf_score" in scratch:
        sources = []
        if scratch.get("vector_rank") is not None:
            sources.append(f"vector #{scratch['vector_rank']}")
        if scratch.get("bm25_rank") is not None:
            sources.append(f"BM25 #{scratch['bm25_rank']}")
        if scratch.get("graph_rank") is not None:
            sources.append(f"graph #{scratch['graph_rank']}")
        joined = ", ".join(sources) if sources else "no retrievers"
        return f"RRF fusion ({joined}); rrf_score={scratch.get('rrf_score', 0.0):.4f}"

    if mode == QueryMode.GRAPH and result.graph_score is not None:
        return f"Graph match (score {result.graph_score:.2f})"

    if mode == QueryMode.BM25 and result.bm25_score is not None:
        terms = scratch.get("matched_terms") or []
        if terms:
            term_str = ", ".join(terms[:5])
            return f"BM25 keyword match (score {result.bm25_score:.2f}): {term_str}"
        return f"BM25 keyword match (score {result.bm25_score:.2f})"

    if mode == QueryMode.VECTOR and result.vector_score is not None:
        return f"Vector similarity match (score {result.vector_score:.2f})"

    return f"Retrieved by {mode.value} (score {result.score:.2f})"


def _build_explanation_for_result(
    result: QueryResult,
    scratch: dict[str, Any],
    mode: QueryMode,
) -> ResultExplanation:
    """Assemble a ResultExplanation from a result's fields and its scratch dict."""
    fusion: dict[str, float] | None = None
    if mode == QueryMode.HYBRID and "fused_score" in scratch:
        fusion = {
            "vector_score_weighted": float(scratch.get("vector_score_weighted", 0.0)),
            "bm25_score_weighted": float(scratch.get("bm25_score_weighted", 0.0)),
            "alpha": float(scratch.get("alpha", 0.0)),
            "fused_score": float(scratch.get("fused_score", 0.0)),
        }
    elif mode == QueryMode.MULTI and "rrf_score" in scratch:
        fusion = {"rrf_score": float(scratch["rrf_score"])}
        for key in ("vector_rank", "bm25_rank", "graph_rank", "fused_rank"):
            val = scratch.get(key)
            if val is not None:
                fusion[key] = float(val)

    graph_path: list[str] | None = None
    if result.relationship_path:
        graph_path = [str(p) for p in result.relationship_path if p]
        if not graph_path:
            graph_path = None

    graph_fallback: bool | None = None
    if mode == QueryMode.GRAPH:
        graph_fallback = bool(scratch.get("graph_fallback", False))

    rerank_movement = scratch.get("rerank_movement")
    if rerank_movement is not None:
        rerank_movement = int(rerank_movement)

    matched_terms = scratch.get("matched_terms")
    if matched_terms is not None:
        matched_terms = [str(t) for t in matched_terms]
        if not matched_terms:
            matched_terms = None

    return ResultExplanation(
        reason=_build_reason(result, scratch, mode),
        matched_terms=matched_terms,
        fusion=fusion,
        graph_path=graph_path,
        rerank_movement=rerank_movement,
        graph_fallback=graph_fallback,
    )


def _drain_explain_scratch(
    results: list[QueryResult],
    request: QueryRequest,
) -> None:
    """Pop `_explain_scratch` from each result's metadata.

    Always called, regardless of `request.explain`, so the scratch never
    leaks into the wire format. When `request.explain=True`, also build
    and attach a `ResultExplanation` before clearing.
    """
    for result in results:
        scratch = result.metadata.pop(EXPLAIN_SCRATCH_KEY, {})
        if request.explain:
            result.explanation = _build_explanation_for_result(
                result, scratch, request.mode
            )


class VectorManagerRetriever(BaseRetriever):
    """LlamaIndex retriever wrapper for storage backend vector search."""

    def __init__(
        self,
        service: QueryService,
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
        results = await self.service.storage_backend.vector_search(
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
        vector_store: VectorStoreManager | None = None,
        embedding_generator: EmbeddingGenerator | None = None,
        bm25_manager: BM25IndexManager | None = None,
        graph_index_manager: GraphIndexManager | None = None,
        storage_backend: StorageBackendProtocol | None = None,
        query_cache: QueryCacheService | None = None,
    ):
        """
        Initialize the query service.

        Args:
            vector_store: [DEPRECATED] Vector store manager
                (for backward compat).
            embedding_generator: Embedding generator instance.
            bm25_manager: [DEPRECATED] BM25 index manager
                (for backward compat).
            graph_index_manager: Graph index manager instance (Feature 113).
            storage_backend: Storage backend implementing protocol (preferred).
        """
        # Resolve storage_backend with backward compatibility
        if storage_backend is not None:
            self.storage_backend = storage_backend
        elif vector_store is not None or bm25_manager is not None:
            # Legacy path: wrap provided stores in ChromaBackend
            from agent_brain_server.storage.chroma.backend import ChromaBackend

            self.storage_backend = ChromaBackend(
                vector_store=vector_store,
                bm25_manager=bm25_manager,
            )
        else:
            # New path: use factory
            self.storage_backend = get_storage_backend()

        # Maintain backward-compatible aliases for code that accesses them directly
        # Extract from ChromaBackend if possible, otherwise set to None
        if hasattr(self.storage_backend, "vector_store"):
            self.vector_store = self.storage_backend.vector_store
        else:
            self.vector_store = vector_store or get_vector_store()

        if hasattr(self.storage_backend, "bm25_manager"):
            self.bm25_manager = self.storage_backend.bm25_manager
        else:
            self.bm25_manager = bm25_manager or get_bm25_manager()

        self.embedding_generator = embedding_generator or get_embedding_generator()
        self.graph_index_manager = graph_index_manager or get_graph_index_manager()
        self.query_cache = query_cache

    def is_ready(self) -> bool:
        """
        Check if the service is ready to process queries.

        Returns:
            True if the storage backend is initialized and has documents.
        """
        return self.storage_backend.is_initialized

    async def execute_query(self, request: QueryRequest) -> QueryResponse:
        """
        Execute a search query based on the requested mode.

        Supports optional two-stage reranking when ENABLE_RERANKING=True.
        Stage 1: Broad retrieval with expanded top_k
        Stage 2: Cross-encoder reranking for precision

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

        # Query cache check (Phase 17 — QCACHE-01, QCACHE-03)
        from agent_brain_server.services.query_cache import (
            QueryCacheService,
        )

        cache = self.query_cache
        cache_key: str | None = None
        # Issue #159: explain=true requests bypass the cache. The explanation
        # payload is debugging output that shouldn't share cache entries with
        # ordinary requests, and re-running the query on each call avoids
        # having to fabricate explanations from cached responses.
        if (
            cache is not None
            and not request.explain
            and QueryCacheService.is_cacheable_mode(request.mode.value)
        ):
            cache_params: dict[str, Any] = {
                "query": request.query,
                "mode": request.mode.value,
                "top_k": request.top_k,
                "similarity_threshold": request.similarity_threshold,
                "alpha": request.alpha,
                "source_types": sorted(request.source_types or []),
                "languages": sorted(request.languages or []),
                "file_paths": sorted(request.file_paths or []),
            }
            cache_key = cache.make_cache_key(cache_params)
            cached = cache.get(cache_key)
            if cached is not None:
                return cached  # type: ignore[no-any-return]

        # Early return for empty index — avoids top_k=0 errors downstream
        corpus_size = await self.storage_backend.get_count()
        if corpus_size == 0:
            elapsed = (time.time() - start_time) * 1000
            return QueryResponse(
                results=[],
                query_time_ms=elapsed,
                total_results=0,
            )

        # Determine if reranking is enabled
        # Use getattr with default False to handle mocked settings in tests
        enable_reranking = getattr(settings, "ENABLE_RERANKING", False)
        if not isinstance(enable_reranking, bool):
            enable_reranking = False
        original_top_k = request.top_k

        # Stage 1: Adjust top_k for reranking if enabled
        if enable_reranking:
            # Calculate stage 1 candidates: top_k * multiplier, capped at max_candidates
            multiplier = getattr(settings, "RERANKER_TOP_K_MULTIPLIER", 10)
            max_candidates = getattr(settings, "RERANKER_MAX_CANDIDATES", 100)
            stage1_top_k = min(
                request.top_k * multiplier,
                max_candidates,
            )
            logger.debug(
                f"Reranking enabled: Stage 1 retrieving {stage1_top_k} candidates "
                f"for final top_k={original_top_k}"
            )
            # Create modified request with expanded top_k for Stage 1
            stage1_request = QueryRequest(
                query=request.query,
                top_k=stage1_top_k,
                similarity_threshold=request.similarity_threshold,
                mode=request.mode,
                alpha=request.alpha,
                source_types=request.source_types,
                languages=request.languages,
                file_paths=request.file_paths,
                entity_types=request.entity_types,
                relationship_types=request.relationship_types,
                explain=request.explain,
            )
        else:
            stage1_request = request

        # Execute Stage 1 retrieval
        if stage1_request.mode == QueryMode.BM25:
            results = await self._execute_bm25_query(stage1_request)
        elif stage1_request.mode == QueryMode.VECTOR:
            results = await self._execute_vector_query(stage1_request)
        elif stage1_request.mode == QueryMode.GRAPH:
            results = await self._execute_graph_query(stage1_request)
        elif stage1_request.mode == QueryMode.MULTI:
            results = await self._execute_multi_query(stage1_request)
        else:  # HYBRID
            results = await self._execute_hybrid_query(stage1_request)

        # Apply content filters if specified
        if any([request.source_types, request.languages, request.file_paths]):
            results = self._filter_results(results, request)

        # Stage 2: Apply reranking if enabled and we have more results than requested
        if enable_reranking and len(results) > original_top_k:
            results = await self._rerank_results(
                results=results,
                query=request.query,
                top_k=original_top_k,
            )
        elif enable_reranking:
            # Not enough results to warrant reranking, just truncate
            logger.debug(
                f"Skipping reranking: only {len(results)} results, "
                f"need more than {original_top_k}"
            )
            results = results[:original_top_k]
        # else: reranking disabled, results already at correct size

        # Issue #159: always drain the _explain_scratch metadata so it never
        # leaks into the wire format. When request.explain=True the drain
        # also builds and attaches the structured ResultExplanation to each
        # result.
        _drain_explain_scratch(results, request)

        query_time_ms = (time.time() - start_time) * 1000

        logger.debug(
            f"Query ({request.mode}) '{request.query[:50]}...' returned "
            f"{len(results)} results in {query_time_ms:.2f}ms"
            f"{' (reranked)' if enable_reranking else ''}"
        )

        response = QueryResponse(
            results=results,
            query_time_ms=query_time_ms,
            total_results=len(results),
        )

        # Store in query cache (Phase 17 — QCACHE-01)
        if cache is not None and cache_key is not None:
            await cache.put(cache_key, response)

        return response

    async def _execute_vector_query(self, request: QueryRequest) -> list[QueryResult]:
        """Execute pure semantic search."""
        query_embedding = await self.embedding_generator.embed_query(request.query)
        where_clause = self._build_where_clause(request.source_types, request.languages)
        search_results = await self.storage_backend.vector_search(
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

        # Use storage backend's keyword_search (scores already normalized 0-1)
        search_results = await self.storage_backend.keyword_search(
            query=request.query,
            top_k=request.top_k,
            source_types=request.source_types,
            languages=request.languages,
            explain=request.explain,
        )

        results: list[QueryResult] = []
        for res in search_results:
            clean_metadata = {
                k: v
                for k, v in res.metadata.items()
                if k not in ("source", "file_path", "source_type", "language")
            }
            # Issue #159: stash matched_terms into the explain scratch dict
            # so the final ResultExplanation can surface them. Always stash
            # when explain=True so the drain pass finds the data.
            if request.explain and res.matched_terms is not None:
                clean_metadata[EXPLAIN_SCRATCH_KEY] = {
                    "matched_terms": list(res.matched_terms)
                }
            results.append(
                QueryResult(
                    text=res.text,
                    source=res.metadata.get(
                        "source", res.metadata.get("file_path", "unknown")
                    ),
                    score=res.score,
                    bm25_score=res.score,  # Already normalized 0-1
                    chunk_id=res.chunk_id,
                    source_type=res.metadata.get("source_type", "doc"),
                    language=res.metadata.get("language"),
                    metadata=clean_metadata,
                )
            )
        return results

    async def _execute_hybrid_query(self, request: QueryRequest) -> list[QueryResult]:
        """Execute hybrid search using Relative Score Fusion."""
        # For US5, we want to provide individual scores.
        # We'll perform the individual searches first to get the scores.

        # Get corpus size to avoid requesting more than available
        corpus_size = await self.storage_backend.get_count()
        effective_top_k = min(request.top_k, corpus_size)

        # Build ChromaDB where clause for filtering
        where_clause = self._build_where_clause(request.source_types, request.languages)

        # 1. Vector Search
        query_embedding = await self.embedding_generator.embed_query(request.query)
        vector_results = await self.storage_backend.vector_search(
            query_embedding=query_embedding,
            top_k=effective_top_k,
            similarity_threshold=request.similarity_threshold,
            where=where_clause,
        )

        # 2. BM25 Search (scores already normalized 0-1 by ChromaBackend)
        bm25_search_results = []
        # Issue #159: build a chunk_id -> matched_terms map so we can
        # attach BM25 matched terms to results that came in via the
        # vector retriever too (a chunk can be in both result sets).
        matched_terms_by_chunk: dict[str, list[str]] = {}
        if self.bm25_manager.is_initialized:
            # Use storage backend's keyword_search
            # (returns SearchResult with normalized scores)
            bm25_search_results = await self.storage_backend.keyword_search(
                query=request.query,
                top_k=effective_top_k,
                source_types=request.source_types,
                languages=request.languages,
                explain=request.explain,
            )
            if request.explain:
                for res in bm25_search_results:
                    if res.matched_terms:
                        matched_terms_by_chunk[res.chunk_id] = list(res.matched_terms)

        # Convert BM25 SearchResults to QueryResults
        bm25_query_results = []
        for res in bm25_search_results:
            bm25_query_results.append(
                QueryResult(
                    text=res.text,
                    source=res.metadata.get(
                        "source", res.metadata.get("file_path", "unknown")
                    ),
                    score=res.score,  # Already normalized 0-1
                    bm25_score=res.score,
                    chunk_id=res.chunk_id,
                    source_type=res.metadata.get("source_type", "doc"),
                    language=res.metadata.get("language"),
                    metadata={
                        k: v
                        for k, v in res.metadata.items()
                        if k not in ("source", "file_path", "source_type", "language")
                    },
                )
            )

        # 3. Simple hybrid fusion for small corpora
        # Combine vector and BM25 results manually to avoid retriever complexity

        # Score normalization: both already in 0-1 range from backend
        # Vector scores are cosine similarity (0-1)
        # BM25 scores are normalized to 0-1 by ChromaBackend.keyword_search
        max_vector_score = max((r.score for r in vector_results), default=1.0) or 1.0
        max_bm25_score = (
            max((r.bm25_score or 0.0 for r in bm25_query_results), default=1.0) or 1.0
        )

        # Create combined results map
        combined_results: dict[str, dict[str, Any]] = {}

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
                    k: v
                    for k, v in res.metadata.items()
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
        for bm25_res in bm25_query_results:
            chunk_id = bm25_res.chunk_id
            bm25_normalized = (bm25_res.bm25_score or 0.0) / max_bm25_score
            bm25_weighted = (1.0 - request.alpha) * bm25_normalized

            if chunk_id in combined_results:
                combined_results[chunk_id]["bm25_score"] = bm25_normalized
                combined_results[chunk_id]["total_score"] += bm25_weighted
                # Update BM25 score on existing result
                combined_results[chunk_id]["result"].bm25_score = bm25_res.bm25_score
            else:
                combined_results[chunk_id] = {
                    "result": bm25_res,
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
            # Issue #159: stash the fusion breakdown so _drain_explain_scratch
            # can rebuild a structured explanation after rerank. Values are
            # already in the local dict — we just persist them onto the
            # result before returning.
            scratch: dict[str, Any] = {
                "vector_score_weighted": request.alpha * data["vector_score"],
                "bm25_score_weighted": (1.0 - request.alpha) * data["bm25_score"],
                "alpha": request.alpha,
                "fused_score": data["total_score"],
            }
            if request.explain:
                terms = matched_terms_by_chunk.get(_chunk_id)
                if terms:
                    scratch["matched_terms"] = terms
            result.metadata[EXPLAIN_SCRATCH_KEY] = scratch
            fused_nodes.append(result)

        # Sort by combined score and take top_k
        fused_nodes.sort(key=lambda x: x.score, reverse=True)
        fused_nodes = fused_nodes[: request.top_k]

        return fused_nodes

    async def _execute_graph_query(
        self,
        request: QueryRequest,
        traversal_depth: int = 2,
    ) -> list[QueryResult]:
        """Execute graph-only query using entity relationships.

        Uses the knowledge graph to find documents related to
        entities mentioned in the query.

        Args:
            request: Query request.
            traversal_depth: How many hops to traverse in graph.

        Returns:
            List of QueryResult from graph retrieval.

        Raises:
            ValueError: If GraphRAG is not enabled or backend is incompatible.
        """
        # Check backend compatibility for graph queries
        from agent_brain_server.storage import get_effective_backend_type

        backend_type = get_effective_backend_type()
        if backend_type != "chroma":
            raise ValueError(
                f"Graph queries (mode='graph') require ChromaDB backend. "
                f"Current backend: '{backend_type}'. "
                f"To use graph queries, set AGENT_BRAIN_STORAGE_BACKEND=chroma."
            )

        if not _graphrag_enabled():
            raise ValueError(
                "GraphRAG not enabled. Set graphrag.enabled: true in config.yaml "
                "or ENABLE_GRAPH_INDEX=true in the environment."
            )

        # Get filter parameters (use getattr for backward compat with test mocks)
        entity_types = getattr(request, "entity_types", None)
        relationship_types = getattr(request, "relationship_types", None)

        # Query the graph for related entities (with type filters if provided)
        if entity_types or relationship_types:
            graph_results = self.graph_index_manager.query_by_type(
                query_text=request.query,
                entity_types=entity_types,
                relationship_types=relationship_types,
                top_k=request.top_k,
                traversal_depth=traversal_depth,
            )
        else:
            graph_results = self.graph_index_manager.query(
                query_text=request.query,
                top_k=request.top_k,
                traversal_depth=traversal_depth,
            )

        if not graph_results:
            logger.debug("No graph results found, falling back to vector search")
            fallback = await self._execute_vector_query(request)
            for r in fallback:
                r.metadata[EXPLAIN_SCRATCH_KEY] = {"graph_fallback": True}
            return fallback

        # Convert graph results to QueryResults
        results: list[QueryResult] = []
        chunk_ids = [
            r.get("source_chunk_id") for r in graph_results if r.get("source_chunk_id")
        ]

        if not chunk_ids:
            # No source chunks in graph, fall back to vector search
            fallback = await self._execute_vector_query(request)
            for r in fallback:
                r.metadata[EXPLAIN_SCRATCH_KEY] = {"graph_fallback": True}
            return fallback

        # Look up the actual documents from vector store
        for graph_result in graph_results:
            chunk_id = graph_result.get("source_chunk_id")
            if not chunk_id:
                continue

            # Get document from storage backend by ID
            try:
                doc = await self.storage_backend.get_by_id(chunk_id)
                if doc:
                    result = QueryResult(
                        text=doc.get("text", ""),
                        source=doc.get("metadata", {}).get(
                            "source",
                            doc.get("metadata", {}).get("file_path", "unknown"),
                        ),
                        score=graph_result.get("graph_score", 0.5),
                        graph_score=graph_result.get("graph_score", 0.5),
                        chunk_id=chunk_id,
                        source_type=doc.get("metadata", {}).get("source_type", "doc"),
                        language=doc.get("metadata", {}).get("language"),
                        related_entities=[
                            graph_result.get("subject", ""),
                            graph_result.get("object", ""),
                        ],
                        relationship_path=[graph_result.get("relationship_path", "")],
                        metadata={
                            k: v
                            for k, v in doc.get("metadata", {}).items()
                            if k
                            not in ("source", "file_path", "source_type", "language")
                        },
                    )
                    results.append(result)
            except Exception as e:
                logger.debug(f"Failed to retrieve chunk {chunk_id}: {e}")
                continue

        # If no results from graph, fall back to vector search
        if not results:
            logger.debug("No documents found from graph, falling back to vector search")
            fallback = await self._execute_vector_query(request)
            for r in fallback:
                r.metadata[EXPLAIN_SCRATCH_KEY] = {"graph_fallback": True}
            return fallback

        return results[: request.top_k]

    async def _execute_multi_query(self, request: QueryRequest) -> list[QueryResult]:
        """Execute multi-retrieval query combining vector, BM25, and graph.

        Uses Reciprocal Rank Fusion (RRF) to combine results from
        all three retrieval methods.

        Args:
            request: Query request.

        Returns:
            List of QueryResult with combined scores.
        """
        # Get results from each retriever
        vector_results = await self._execute_vector_query(request)
        bm25_results = await self._execute_bm25_query(request)

        # Issue #159: harvest matched_terms from the BM25 sub-results before
        # the multi handler overwrites scratch with per-retriever ranks.
        # We re-stash matched_terms when we finalize the multi result below.
        matched_terms_by_chunk: dict[str, list[str]] = {}
        if request.explain:
            for r in bm25_results:
                upstream_scratch = r.metadata.get(EXPLAIN_SCRATCH_KEY, {})
                terms = upstream_scratch.get("matched_terms")
                if terms:
                    matched_terms_by_chunk[r.chunk_id] = list(terms)

        # Get graph results if enabled and backend supports it
        graph_results: list[QueryResult] = []
        from agent_brain_server.storage import get_effective_backend_type

        backend_type = get_effective_backend_type()
        if _graphrag_enabled() and backend_type == "chroma":
            try:
                graph_results = await self._execute_graph_query(request)
            except ValueError:
                pass  # Graph not enabled or not available, skip
        elif backend_type != "chroma":
            logger.info(
                "Graph component skipped in multi-mode: "
                "graph queries require ChromaDB backend "
                f"(current: {backend_type})"
            )

        # Apply Reciprocal Rank Fusion
        rrf_k = _graphrag_rrf_k()  # Typical value is 60
        combined_scores: dict[str, dict[str, Any]] = {}

        # Process vector results
        for rank, result in enumerate(vector_results):
            chunk_id = result.chunk_id
            rrf_score = 1.0 / (rrf_k + rank + 1)
            if chunk_id not in combined_scores:
                combined_scores[chunk_id] = {
                    "result": result,
                    "rrf_score": 0.0,
                    "vector_rank": None,
                    "bm25_rank": None,
                    "graph_rank": None,
                }
            combined_scores[chunk_id]["rrf_score"] += rrf_score
            combined_scores[chunk_id]["vector_rank"] = rank + 1

        # Process BM25 results
        for rank, result in enumerate(bm25_results):
            chunk_id = result.chunk_id
            rrf_score = 1.0 / (rrf_k + rank + 1)
            if chunk_id not in combined_scores:
                combined_scores[chunk_id] = {
                    "result": result,
                    "rrf_score": 0.0,
                    "vector_rank": None,
                    "bm25_rank": None,
                    "graph_rank": None,
                }
            combined_scores[chunk_id]["rrf_score"] += rrf_score
            combined_scores[chunk_id]["bm25_rank"] = rank + 1

        # Process graph results
        for rank, result in enumerate(graph_results):
            chunk_id = result.chunk_id
            rrf_score = 1.0 / (rrf_k + rank + 1)
            if chunk_id not in combined_scores:
                combined_scores[chunk_id] = {
                    "result": result,
                    "rrf_score": 0.0,
                    "vector_rank": None,
                    "bm25_rank": None,
                    "graph_rank": None,
                }
            combined_scores[chunk_id]["rrf_score"] += rrf_score
            combined_scores[chunk_id]["graph_rank"] = rank + 1
            # Preserve graph-specific fields
            if result.related_entities:
                combined_scores[chunk_id][
                    "result"
                ].related_entities = result.related_entities
            if result.relationship_path:
                combined_scores[chunk_id][
                    "result"
                ].relationship_path = result.relationship_path
            if result.graph_score:
                combined_scores[chunk_id]["result"].graph_score = result.graph_score

        # Sort by RRF score and take top_k
        sorted_results = sorted(
            combined_scores.values(),
            key=lambda x: x["rrf_score"],
            reverse=True,
        )

        # Update scores and return
        final_results: list[QueryResult] = []
        for fused_idx, data in enumerate(sorted_results[: request.top_k]):
            result = data["result"]
            result.score = data["rrf_score"]
            # Issue #159: stash per-retriever ranks + RRF score so the final
            # explanation can describe which retrievers contributed. Without
            # this stash, the per-retriever ranks die when this method
            # returns (they only existed in the local combined_scores dict).
            scratch: dict[str, Any] = {
                "rrf_score": data["rrf_score"],
                "vector_rank": data.get("vector_rank"),
                "bm25_rank": data.get("bm25_rank"),
                "graph_rank": data.get("graph_rank"),
                "fused_rank": fused_idx + 1,
            }
            terms = matched_terms_by_chunk.get(result.chunk_id)
            if terms:
                scratch["matched_terms"] = terms
            result.metadata[EXPLAIN_SCRATCH_KEY] = scratch
            final_results.append(result)

        return final_results

    async def get_document_count(self) -> int:
        """
        Get the total number of indexed documents.

        Returns:
            Number of documents in the vector store.
        """
        if not self.is_ready():
            return 0
        return await self.storage_backend.get_count()

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
        self, source_types: list[str] | None, languages: list[str] | None
    ) -> dict[str, Any] | None:
        """
        Build ChromaDB where clause from filter parameters.

        Args:
            source_types: List of source types to filter by.
            languages: List of languages to filter by.

        Returns:
            ChromaDB where clause dict or None.
        """
        conditions: list[dict[str, Any]] = []

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

    async def _rerank_results(
        self,
        results: list[QueryResult],
        query: str,
        top_k: int,
    ) -> list[QueryResult]:
        """Rerank results using a cross-encoder model.

        Two-stage retrieval: Stage 1 returns broad candidates, Stage 2 reranks
        using a more accurate cross-encoder model.

        Args:
            results: List of QueryResult from Stage 1 retrieval.
            query: The original query text.
            top_k: Number of final results to return.

        Returns:
            Reranked list of QueryResult with updated scores and reranking metadata.
            Falls back to original results (truncated to top_k) on any failure.
        """
        if not results:
            return results

        start_time = time.time()

        try:
            # Get reranker configuration
            provider_settings = load_provider_settings()
            reranker = ProviderRegistry.get_reranker_provider(
                provider_settings.reranker
            )

            # Check if reranker is available
            if not reranker.is_available():
                logger.warning(
                    f"Reranker {reranker.provider_name} not available, "
                    "falling back to stage 1 results"
                )
                return results[:top_k]

            # Extract document texts for reranking
            documents = [r.text for r in results]

            # Perform reranking
            reranked = await reranker.rerank(
                query=query,
                documents=documents,
                top_k=top_k,
            )

            # If reranker returned nothing, fall back gracefully
            if not reranked:
                logger.warning(
                    "Reranker returned no results, falling back to stage 1 results"
                )
                return results[:top_k]

            # Build reranked results with updated scores and metadata
            reranked_results: list[QueryResult] = []
            for new_index, (original_index, rerank_score) in enumerate(reranked):
                result = results[original_index]
                # Issue #159: rerank_movement is signed — positive = moved up
                # (better rank). Build a fresh metadata dict so we can merge
                # the upstream scratch (e.g., hybrid fusion) with the rerank
                # marker without mutating the source result's metadata.
                new_metadata = dict(result.metadata)
                upstream_scratch = dict(new_metadata.get(EXPLAIN_SCRATCH_KEY, {}))
                upstream_scratch["rerank_movement"] = original_index - new_index
                new_metadata[EXPLAIN_SCRATCH_KEY] = upstream_scratch
                # Create new result with reranking metadata
                reranked_result = QueryResult(
                    text=result.text,
                    source=result.source,
                    score=rerank_score,  # Update main score to rerank score
                    vector_score=result.vector_score,
                    bm25_score=result.bm25_score,
                    chunk_id=result.chunk_id,
                    source_type=result.source_type,
                    language=result.language,
                    graph_score=result.graph_score,
                    related_entities=result.related_entities,
                    relationship_path=result.relationship_path,
                    rerank_score=rerank_score,
                    original_rank=original_index + 1,  # 1-indexed
                    metadata=new_metadata,
                )
                reranked_results.append(reranked_result)

            rerank_time_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Reranked {len(results)} -> {len(reranked_results)} results "
                f"in {rerank_time_ms:.2f}ms using {reranker.provider_name}"
            )

            return reranked_results

        except Exception as e:
            rerank_time_ms = (time.time() - start_time) * 1000
            logger.warning(
                f"Reranking failed after {rerank_time_ms:.2f}ms: {e}, "
                "falling back to stage 1 results"
            )
            # Graceful fallback: return stage 1 results truncated to top_k
            return results[:top_k]


# Singleton instance
_query_service: QueryService | None = None


def get_query_service() -> QueryService:
    """Get the global query service instance."""
    global _query_service
    if _query_service is None:
        _query_service = QueryService()
    return _query_service
