"""ChromaDB backend adapter implementing StorageBackendProtocol.

This adapter wraps the existing VectorStoreManager and BM25IndexManager
to provide a unified storage interface. It preserves all existing ChromaDB
functionality while conforming to the protocol interface.
"""

import asyncio
import logging
from typing import Any

from agent_brain_server.indexing.bm25_index import BM25IndexManager, get_bm25_manager
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
    ) -> list[SearchResult]:
        """Perform BM25 keyword search with score normalization.

        Args:
            query: Search query string
            top_k: Maximum number of results
            source_types: Optional filter by source_type
            languages: Optional filter by language

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

            # Normalize BM25 scores to 0-1 range (per-query normalization)
            max_score = max(node.score or 0.0 for node in nodes_with_score)
            if max_score == 0.0:
                # All scores are zero, return with zero scores
                return [
                    SearchResult(
                        text=node.node.get_content(),
                        metadata=dict(node.node.metadata),
                        score=0.0,
                        chunk_id=node.node.node_id or "",
                    )
                    for node in nodes_with_score
                ]

            # Normalize to 0-1 by dividing by max
            return [
                SearchResult(
                    text=node.node.get_content(),
                    metadata=dict(node.node.metadata),
                    score=(node.score or 0.0) / max_score,
                    chunk_id=node.node.node_id or "",
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
