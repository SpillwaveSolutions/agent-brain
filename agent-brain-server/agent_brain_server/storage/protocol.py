"""Storage backend protocol and types.

This module defines the async-first protocol that all storage backends
must implement, along with backend-agnostic data types.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class SearchResult:
    """Backend-agnostic search result.

    All scores are normalized to 0-1 range where higher values indicate
    better matches. This ensures consistent behavior across different
    storage backends (ChromaDB, PostgreSQL).
    """

    text: str
    metadata: dict[str, Any]
    score: float  # Normalized 0-1, higher=better
    chunk_id: str


@dataclass
class EmbeddingMetadata:
    """Metadata about the embedding provider used for this collection.

    This metadata is stored alongside the collection to ensure that
    subsequent queries use compatible embeddings.
    """

    provider: str
    model: str
    dimensions: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for backend storage.

        Returns:
            JSON-compatible dictionary with embedding metadata
        """
        return {
            "embedding_provider": self.provider,
            "embedding_model": self.model,
            "embedding_dimensions": self.dimensions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EmbeddingMetadata:
        """Create from dictionary (backend metadata).

        Args:
            data: Dictionary containing embedding metadata keys

        Returns:
            EmbeddingMetadata instance
        """
        return cls(
            provider=data.get("embedding_provider", "unknown"),
            model=data.get("embedding_model", "unknown"),
            dimensions=data.get("embedding_dimensions", 0),
        )


class StorageError(Exception):
    """Base exception for storage backend operations.

    All backend-specific exceptions should be caught and re-raised as
    StorageError to provide a consistent error interface.
    """

    def __init__(self, message: str, backend: str | None = None):
        """Initialize storage error.

        Args:
            message: Human-readable error message
            backend: Optional backend identifier (e.g., "chroma", "postgres")
        """
        self.message = message
        self.backend = backend
        super().__init__(message)


@runtime_checkable
class StorageBackendProtocol(Protocol):
    """Protocol defining the interface for storage backends.

    All storage backends must implement this async-first protocol to ensure
    consistent behavior across ChromaDB, PostgreSQL, and future backends.

    Key requirements:
    - All methods are async (except validate_embedding_compatibility)
    - All scores normalized to 0-1 range (higher = better)
    - All exceptions normalized to StorageError
    - Metadata is JSON-compatible dicts only
    """

    @property
    def is_initialized(self) -> bool:
        """Check if the storage backend is initialized.

        Returns:
            True if backend is ready for operations, False otherwise
        """
        ...

    async def initialize(self) -> None:
        """Initialize the storage backend.

        This should:
        - Create necessary collections/tables/indexes
        - Validate schema compatibility
        - Prepare the backend for operations

        Raises:
            StorageError: If initialization fails
        """
        ...

    async def upsert_documents(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> int:
        """Upsert documents with embeddings.

        If IDs already exist, content and embeddings are updated.
        All input lists must have the same length.

        Args:
            ids: Unique chunk identifiers
            embeddings: Embedding vectors (must match stored dimensions)
            documents: Text content of chunks
            metadatas: JSON-compatible metadata dicts

        Returns:
            Number of documents upserted

        Raises:
            StorageError: If upsert operation fails
            ValueError: If input list lengths don't match
        """
        ...

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
            top_k: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0-1, higher=better)
            where: Optional metadata filter (backend-specific syntax)

        Returns:
            List of SearchResult objects sorted by score descending.
            All scores normalized to 0-1 range (higher=better).

        Raises:
            StorageError: If search operation fails
        """
        ...

    async def keyword_search(
        self,
        query: str,
        top_k: int,
        source_types: list[str] | None = None,
        languages: list[str] | None = None,
    ) -> list[SearchResult]:
        """Perform keyword search (BM25 or tsvector).

        Args:
            query: Search query string
            top_k: Maximum number of results to return
            source_types: Optional filter by source_type metadata
            languages: Optional filter by language metadata

        Returns:
            List of SearchResult objects sorted by score descending.
            All scores normalized to 0-1 range (higher=better).

        Raises:
            StorageError: If search operation fails
        """
        ...

    async def get_count(self, where: dict[str, Any] | None = None) -> int:
        """Get count of documents, optionally filtered.

        Args:
            where: Optional metadata filter (backend-specific syntax)

        Returns:
            Number of documents matching filter (or total if no filter)

        Raises:
            StorageError: If count operation fails
        """
        ...

    async def get_by_id(self, chunk_id: str) -> dict[str, Any] | None:
        """Get document by chunk ID.

        Args:
            chunk_id: Unique chunk identifier

        Returns:
            Dictionary with 'text' and 'metadata' keys, or None if not found

        Raises:
            StorageError: If retrieval operation fails
        """
        ...

    async def reset(self) -> None:
        """Reset the storage backend.

        This should:
        - Delete all documents
        - Clear embedding metadata
        - Reinitialize to clean state

        Raises:
            StorageError: If reset operation fails
        """
        ...

    async def get_embedding_metadata(self) -> EmbeddingMetadata | None:
        """Get stored embedding metadata.

        Returns:
            EmbeddingMetadata if stored, None if not set

        Raises:
            StorageError: If metadata retrieval fails
        """
        ...

    async def set_embedding_metadata(
        self,
        provider: str,
        model: str,
        dimensions: int,
    ) -> None:
        """Store embedding metadata.

        Args:
            provider: Embedding provider name (e.g., "openai", "ollama")
            model: Model name (e.g., "text-embedding-3-large")
            dimensions: Embedding vector dimensions

        Raises:
            StorageError: If metadata storage fails
        """
        ...

    def validate_embedding_compatibility(
        self,
        provider: str,
        model: str,
        dimensions: int,
        stored_metadata: EmbeddingMetadata | None,
    ) -> None:
        """Validate current embedding config against stored metadata.

        This is a synchronous validation method that checks if the current
        embedding configuration is compatible with what's stored in the backend.

        Args:
            provider: Current provider name
            model: Current model name
            dimensions: Current embedding dimensions
            stored_metadata: Previously stored metadata (or None if new index)

        Raises:
            ProviderMismatchError: If dimensions or provider/model don't match
        """
        ...

    async def delete_by_metadata(
        self,
        where: dict[str, Any],
    ) -> int:
        """Delete documents matching a metadata filter.

        Used for targeted folder removal: delete all chunks whose metadata
        matches the given filter (e.g., ``{"source": "/path/to/folder"}``).

        IMPORTANT for ChromaDB callers: always guard against empty ``where``
        dicts — passing an empty filter may delete the entire collection on
        some backends.

        Args:
            where: Metadata filter dict. For ChromaDB uses native ``where``
                syntax (e.g., ``{"source": {"$contains": "/path"}}``).
                For PostgreSQL uses JSONB containment.

        Returns:
            Number of documents deleted.

        Raises:
            StorageError: If the delete operation fails.
        """
        ...
