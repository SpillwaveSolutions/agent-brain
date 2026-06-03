"""ChromaDB backend adapter implementing StorageBackendProtocol.

This adapter wraps the existing VectorStoreManager and BM25IndexManager
to provide a unified storage interface. It preserves all existing ChromaDB
functionality while conforming to the protocol interface.
"""

import asyncio
import logging
import os
from typing import Any

from agent_brain_server.indexing.bm25_index import BM25IndexManager, get_bm25_manager
from agent_brain_server.models.query import ChunkRecord
from agent_brain_server.storage.protocol import (
    EmbeddingMetadata,
    SearchResult,
    StorageError,
)
from agent_brain_server.storage.vector_store import (
    VectorStoreManager,
    get_vector_store,
)

logger = logging.getLogger(__name__)


# Issue #159: matched_terms support.
# Tokenization mirrors LlamaIndex BM25Retriever's default: lowercase the
# input, ASCII-word split, strip English stopwords. We avoid stemming
# because the indexer doesn't stem either — keeping the two sides
# symmetric is what makes the intersection meaningful.
def _bm25_tokens(text: str) -> list[str]:
    """Return BM25-relevant tokens in ``text`` (in occurrence order)."""
    try:
        import bm25s
    except ImportError:
        # bm25s ships transitively with llama-index-retrievers-bm25; the
        # safety net below means a packaging glitch degrades to "no
        # matched_terms" rather than a 500.
        return []
    try:
        tokens_lists = bm25s.tokenize(
            text,
            return_ids=False,
            stopwords="english",
            show_progress=False,
        )
    except Exception:
        return []
    if not tokens_lists:
        return []
    return list(tokens_lists[0]) if tokens_lists[0] else []


def _build_chunk_record(
    chunk_id: str,
    text: str,
    metadata: dict[str, Any] | None,
) -> ChunkRecord:
    """Map raw chunk content + metadata into a v2-spec ``ChunkRecord``.

    The chunk metadata dict written by ``IndexingService`` does not yet
    have explicit ``parent_doc_id`` and ``folder_id`` fields (the v2
    spec was just locked); fall back to deriving them from ``source``:

    - ``parent_doc_id`` falls back to ``source`` (one chunk-per-doc
      semantics is a reasonable approximation until indexing surfaces
      an explicit field).
    - ``folder_id`` falls back to ``dirname(source)`` so the value lines
      up with the path stored by ``FolderManager``.

    Args:
        chunk_id: Primary key.
        text: Chunk content.
        metadata: Backend-stored metadata dict (may be ``None``).

    Returns:
        Fully populated ``ChunkRecord`` per the v2 design doc shape.
    """
    meta = metadata or {}
    source = str(meta.get("source", ""))
    parent_doc_id = str(meta.get("parent_doc_id") or source)
    folder_id = str(
        meta.get("folder_id") or (os.path.dirname(source) if source else "")
    )

    summary_val = meta.get("summary") or meta.get("section_summary")
    summary: str | None = str(summary_val) if summary_val else None

    token_count_raw = meta.get("token_count")
    try:
        token_count = int(token_count_raw) if token_count_raw is not None else 0
    except (TypeError, ValueError):
        token_count = 0

    language_val = meta.get("language")
    language: str | None = str(language_val) if language_val else None

    return ChunkRecord(
        chunk_id=chunk_id,
        parent_doc_id=parent_doc_id,
        source=source,
        content=text,
        summary=summary,
        folder_id=folder_id,
        token_count=token_count,
        language=language,
    )


def _intersect_tokens(query_tokens: list[str], doc_text: str) -> list[str]:
    """Return query tokens that appear in ``doc_text``, in query order.

    Deduplicates so a user query like ``"auth auth setup"`` produces
    ``["auth", "setup"]`` rather than repeating the same term.
    """
    doc_token_set = set(_bm25_tokens(doc_text))
    seen: set[str] = set()
    ordered: list[str] = []
    for token in query_tokens:
        if token in doc_token_set and token not in seen:
            seen.add(token)
            ordered.append(token)
    return ordered


class ChromaBackend:
    """ChromaDB storage backend implementing StorageBackendProtocol.

    Wraps VectorStoreManager and BM25IndexManager to provide async-first
    storage operations with normalized scores and consistent error handling.
    """

    def __init__(
        self,
        vector_store: VectorStoreManager | None = None,
        bm25_manager: BM25IndexManager | None = None,
    ):
        """Initialize ChromaBackend with existing managers.

        Args:
            vector_store: VectorStoreManager instance (or None to use singleton)
            bm25_manager: BM25IndexManager instance (or None to use singleton)
        """
        # Use provided instances or get singletons
        self.vector_store = vector_store or get_vector_store()
        self.bm25_manager = bm25_manager or get_bm25_manager()

    @property
    def is_initialized(self) -> bool:
        """Check if the storage backend is initialized.

        Returns:
            True if backend is ready for operations
        """
        return self.vector_store.is_initialized

    async def initialize(self) -> None:
        """Initialize the storage backend.

        Initializes both vector store and BM25 index (if persistent index exists).

        Raises:
            StorageError: If initialization fails
        """
        try:
            # Initialize vector store (async)
            await self.vector_store.initialize()

            # Initialize BM25 index (sync, wrap in thread)
            await asyncio.to_thread(self.bm25_manager.initialize)

            logger.info("ChromaBackend initialized successfully")
        except Exception as e:
            raise StorageError(
                f"Failed to initialize ChromaBackend: {e}",
                backend="chroma",
            ) from e

    async def upsert_documents(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> int:
        """Upsert documents with embeddings to vector store.

        IMPORTANT: This method ONLY upserts to the vector store. BM25 index
        rebuilding is handled by IndexingService after all chunks are created,
        since BM25 requires a full-corpus rebuild (not incremental updates).

        Args:
            ids: Unique chunk identifiers
            embeddings: Embedding vectors
            documents: Text content
            metadatas: JSON-compatible metadata dicts

        Returns:
            Number of documents upserted

        Raises:
            StorageError: If upsert operation fails
        """
        try:
            count = await self.vector_store.upsert_documents(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
            return count
        except Exception as e:
            raise StorageError(
                f"Failed to upsert documents: {e}",
                backend="chroma",
            ) from e

    async def vector_search(
        self,
        query_embedding: list[float],
        top_k: int,
        similarity_threshold: float,
        where: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Perform vector similarity search.

        Args:
            query_embedding: Query embedding vector
            top_k: Maximum number of results
            similarity_threshold: Minimum similarity (0-1, higher=better)
            where: Optional metadata filter

        Returns:
            List of SearchResult with scores normalized to 0-1

        Raises:
            StorageError: If search fails
        """
        try:
            # VectorStoreManager.similarity_search already returns SearchResult
            # with scores normalized to 0-1 (cosine similarity)
            results = await self.vector_store.similarity_search(
                query_embedding=query_embedding,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                where=where,
            )
            # Convert vector_store.SearchResult to protocol.SearchResult
            # (they have identical structure, but are different dataclasses)
            return [
                SearchResult(
                    text=r.text,
                    metadata=r.metadata,
                    score=r.score,
                    chunk_id=r.chunk_id,
                )
                for r in results
            ]
        except Exception as e:
            raise StorageError(
                f"Vector search failed: {e}",
                backend="chroma",
            ) from e

    async def keyword_search(
        self,
        query: str,
        top_k: int,
        source_types: list[str] | None = None,
        languages: list[str] | None = None,
        explain: bool = False,
    ) -> list[SearchResult]:
        """Perform BM25 keyword search with score normalization.

        Args:
            query: Search query string
            top_k: Maximum number of results
            source_types: Optional filter by source_type
            languages: Optional filter by language
            explain: When True, populate ``SearchResult.matched_terms``
                for each result (issue #159).

        Returns:
            List of SearchResult with scores normalized to 0-1 range

        Raises:
            StorageError: If search fails
        """
        try:
            # BM25IndexManager.search_with_filters is already async
            nodes_with_score = await self.bm25_manager.search_with_filters(
                query=query,
                top_k=top_k,
                source_types=source_types,
                languages=languages,
            )

            if not nodes_with_score:
                return []

            # Issue #159: precompute the stopword-stripped query tokens once;
            # we'll intersect them with each document's tokens to derive
            # matched_terms. The tokenizer matches LlamaIndex BM25Retriever's
            # default (lowercase, ASCII-word split, English stopword filter).
            query_tokens: list[str] | None = None
            if explain:
                query_tokens = _bm25_tokens(query)

            # Normalize BM25 scores to 0-1 range (per-query normalization)
            max_score = max(node.score or 0.0 for node in nodes_with_score)
            divisor = max_score if max_score > 0.0 else 1.0

            return [
                SearchResult(
                    text=node.node.get_content(),
                    metadata=dict(node.node.metadata),
                    score=(node.score or 0.0) / divisor if max_score > 0.0 else 0.0,
                    chunk_id=node.node.node_id or "",
                    matched_terms=(
                        _intersect_tokens(query_tokens, node.node.get_content())
                        if query_tokens is not None
                        else None
                    ),
                )
                for node in nodes_with_score
            ]

        except Exception as e:
            raise StorageError(
                f"Keyword search failed: {e}",
                backend="chroma",
            ) from e

    async def get_count(self, where: dict[str, Any] | None = None) -> int:
        """Get document count, optionally filtered.

        Args:
            where: Optional metadata filter

        Returns:
            Number of documents

        Raises:
            StorageError: If count operation fails
        """
        try:
            return await self.vector_store.get_count(where=where)
        except Exception as e:
            raise StorageError(
                f"Get count failed: {e}",
                backend="chroma",
            ) from e

    async def get_by_id(self, chunk_id: str) -> dict[str, Any] | None:
        """Get document by chunk ID.

        Args:
            chunk_id: Unique chunk identifier

        Returns:
            Dictionary with 'text' and 'metadata', or None if not found

        Raises:
            StorageError: If retrieval fails
        """
        try:
            return await self.vector_store.get_by_id(chunk_id)
        except Exception as e:
            raise StorageError(
                f"Get by ID failed: {e}",
                backend="chroma",
            ) from e

    async def reset(self) -> None:
        """Reset storage backend by clearing all data.

        Raises:
            StorageError: If reset fails
        """
        try:
            # Reset vector store (async)
            await self.vector_store.reset()

            # Reset BM25 index (sync, wrap in thread)
            await asyncio.to_thread(self.bm25_manager.reset)

            logger.info("ChromaBackend reset complete")
        except Exception as e:
            raise StorageError(
                f"Reset failed: {e}",
                backend="chroma",
            ) from e

    async def get_embedding_metadata(self) -> EmbeddingMetadata | None:
        """Get stored embedding metadata.

        Returns:
            EmbeddingMetadata if stored, None otherwise

        Raises:
            StorageError: If retrieval fails
        """
        try:
            # VectorStoreManager returns vector_store.EmbeddingMetadata
            metadata = await self.vector_store.get_embedding_metadata()
            if metadata is None:
                return None

            # Convert to protocol.EmbeddingMetadata
            return EmbeddingMetadata(
                provider=metadata.provider,
                model=metadata.model,
                dimensions=metadata.dimensions,
            )
        except Exception as e:
            raise StorageError(
                f"Get embedding metadata failed: {e}",
                backend="chroma",
            ) from e

    async def set_embedding_metadata(
        self,
        provider: str,
        model: str,
        dimensions: int,
    ) -> None:
        """Store embedding metadata.

        Args:
            provider: Embedding provider name
            model: Model name
            dimensions: Embedding dimensions

        Raises:
            StorageError: If storage fails
        """
        try:
            await self.vector_store.set_embedding_metadata(
                provider=provider,
                model=model,
                dimensions=dimensions,
            )
        except Exception as e:
            raise StorageError(
                f"Set embedding metadata failed: {e}",
                backend="chroma",
            ) from e

    async def delete_by_metadata(
        self,
        where: dict[str, Any],
    ) -> int:
        """Delete documents matching a metadata filter.

        Delegates to VectorStoreManager.delete_by_where which queries for
        matching IDs then deletes them.  The two-step approach avoids the
        ChromaDB pitfall of wiping the entire collection when
        ``ids=[]`` is passed to ``collection.delete()``.

        Args:
            where: ChromaDB ``where`` metadata filter dict.

        Returns:
            Number of documents deleted.

        Raises:
            StorageError: If the delete operation fails.
        """
        try:
            return await self.vector_store.delete_by_where(where=where)
        except Exception as e:
            raise StorageError(
                f"Delete by metadata failed: {e}",
                backend="chroma",
            ) from e

    async def delete_by_ids(
        self,
        ids: list[str],
    ) -> int:
        """Delete documents by their chunk IDs.

        Guards against empty ID list to prevent accidental bulk deletion
        (ChromaDB wipes entire collection when ids=[] is passed to delete()).

        Args:
            ids: List of chunk IDs to delete. Returns 0 immediately if empty.

        Returns:
            Number of documents deleted.

        Raises:
            StorageError: If the delete operation fails.
        """
        if not ids:
            return 0

        try:
            return await self.vector_store.delete_by_ids(ids=ids)
        except Exception as e:
            raise StorageError(
                f"Delete by IDs failed: {e}",
                backend="chroma",
            ) from e

    async def get_chunk_by_id(self, chunk_id: str) -> ChunkRecord | None:
        """O(1) lookup of a single chunk by primary key.

        Delegates to ``VectorStoreManager.get_by_id`` which uses
        ``collection.get(ids=[chunk_id], include=["documents", "metadatas"])``
        — embeddings are NOT requested. The returned dict is then mapped
        to the v2-spec :class:`ChunkRecord` shape.

        Args:
            chunk_id: Unique chunk identifier.

        Returns:
            :class:`ChunkRecord` if found, ``None`` otherwise.

        Raises:
            StorageError: If the underlying lookup fails.
        """
        try:
            raw = await self.vector_store.get_by_id(chunk_id)
        except Exception as e:
            raise StorageError(
                f"Get chunk by ID failed: {e}",
                backend="chroma",
            ) from e

        if raw is None:
            return None

        return _build_chunk_record(
            chunk_id=chunk_id,
            text=str(raw.get("text", "")),
            metadata=raw.get("metadata") or {},
        )

    def validate_embedding_compatibility(
        self,
        provider: str,
        model: str,
        dimensions: int,
        stored_metadata: EmbeddingMetadata | None,
    ) -> None:
        """Validate embedding compatibility (synchronous).

        Args:
            provider: Current provider
            model: Current model
            dimensions: Current dimensions
            stored_metadata: Previously stored metadata

        Raises:
            ProviderMismatchError: If incompatible
        """
        # Convert protocol.EmbeddingMetadata back to vector_store.EmbeddingMetadata
        # for VectorStoreManager validation
        from agent_brain_server.storage.vector_store import (
            EmbeddingMetadata as VectorStoreEmbeddingMetadata,
        )

        vs_metadata = None
        if stored_metadata is not None:
            vs_metadata = VectorStoreEmbeddingMetadata(
                provider=stored_metadata.provider,
                model=stored_metadata.model,
                dimensions=stored_metadata.dimensions,
            )

        # Delegate to VectorStoreManager (raises ProviderMismatchError on failure)
        self.vector_store.validate_embedding_compatibility(
            provider=provider,
            model=model,
            dimensions=dimensions,
            stored_metadata=vs_metadata,
        )
