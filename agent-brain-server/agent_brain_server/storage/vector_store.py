"""Chroma vector store manager with thread-safe operations."""

import asyncio
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from agent_brain_server.config import settings
from agent_brain_server.providers.exceptions import ProviderMismatchError

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from a similarity search."""

    text: str
    metadata: dict[str, Any]
    score: float
    chunk_id: str


@dataclass
class EmbeddingMetadata:
    """Metadata about the embedding provider used for this collection."""

    provider: str
    model: str
    dimensions: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for ChromaDB metadata."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmbeddingMetadata":
        """Create from dictionary (ChromaDB metadata)."""
        return cls(
            provider=data.get("embedding_provider", "unknown"),
            model=data.get("embedding_model", "unknown"),
            dimensions=data.get("embedding_dimensions", 0),
        )


class VectorStoreManager:
    """
    Manages Chroma vector store operations with thread-safe access.

    This class provides a high-level interface for storing and retrieving
    document embeddings using Chroma as the backend.
    """

    def __init__(
        self,
        persist_dir: str | None = None,
        collection_name: str | None = None,
    ):
        """
        Initialize the vector store manager.

        Args:
            persist_dir: Directory for persistent storage. Defaults to config value.
            collection_name: Name of the collection. Defaults to config value.
        """
        self.persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR
        self.collection_name = collection_name or settings.COLLECTION_NAME
        self._client: chromadb.PersistentClient | None = None  # type: ignore[valid-type]
        self._collection: chromadb.Collection | None = None
        self._lock = asyncio.Lock()
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """Check if the vector store is initialized."""
        return self._initialized and self._collection is not None

    async def initialize(self) -> None:
        """
        Initialize the Chroma client and collection.

        Creates the persistence directory if it doesn't exist and
        initializes or loads the existing collection.
        """
        async with self._lock:
            if self._initialized:
                return

            # Ensure persistence directory exists
            persist_path = Path(self.persist_dir)
            persist_path.mkdir(parents=True, exist_ok=True)

            # Initialize Chroma client
            self._client = chromadb.PersistentClient(
                path=str(persist_path),
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                ),
            )

            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )

            self._initialized = True
            logger.info(
                f"Vector store initialized: {self.collection_name} "
                f"({self._collection.count()} existing documents)"
            )

    async def get_embedding_metadata(self) -> EmbeddingMetadata | None:
        """Get stored embedding metadata from collection.

        Returns:
            EmbeddingMetadata if collection has metadata, None otherwise.
        """
        if not self.is_initialized or self._collection is None:
            return None

        async with self._lock:
            metadata = self._collection.metadata
            if metadata and "embedding_provider" in metadata:
                return EmbeddingMetadata.from_dict(metadata)
            return None

    async def set_embedding_metadata(
        self,
        provider: str,
        model: str,
        dimensions: int,
    ) -> None:
        """Store embedding metadata in collection.

        Args:
            provider: Embedding provider name (e.g., "openai", "ollama")
            model: Model name (e.g., "text-embedding-3-large")
            dimensions: Embedding vector dimensions
        """
        if not self.is_initialized or self._collection is None:
            raise RuntimeError("Vector store not initialized")

        async with self._lock:
            assert self._client is not None
            # ChromaDB requires recreating collection to update metadata
            # Get existing metadata and merge
            existing_meta = dict(self._collection.metadata or {})
            existing_meta.update(
                {
                    "embedding_provider": provider,
                    "embedding_model": model,
                    "embedding_dimensions": dimensions,
                    "hnsw:space": "cosine",
                }
            )

            # Modify collection metadata
            self._collection.modify(metadata=existing_meta)

            logger.info(
                f"Stored embedding metadata: {provider}/{model} "
                f"({dimensions} dimensions)"
            )

    def validate_embedding_compatibility(
        self,
        provider: str,
        model: str,
        dimensions: int,
        stored_metadata: EmbeddingMetadata | None,
    ) -> None:
        """Validate current embedding config against stored metadata.

        Args:
            provider: Current provider name
            model: Current model name
            dimensions: Current embedding dimensions
            stored_metadata: Previously stored metadata (or None if new index)

        Raises:
            ProviderMismatchError: If dimensions or provider/model don't match
        """
        if stored_metadata is None:
            return  # New index, no validation needed

        # Check dimension mismatch first (critical)
        if stored_metadata.dimensions != dimensions:
            raise ProviderMismatchError(
                current_provider=provider,
                current_model=model,
                indexed_provider=stored_metadata.provider,
                indexed_model=stored_metadata.model,
            )

        # Check provider/model mismatch (even same dimensions can be incompatible)
        if stored_metadata.provider != provider or stored_metadata.model != model:
            raise ProviderMismatchError(
                current_provider=provider,
                current_model=model,
                indexed_provider=stored_metadata.provider,
                indexed_model=stored_metadata.model,
            )

    async def add_documents(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> int:
        """
        Add documents with embeddings to the vector store.

        Args:
            ids: Unique identifiers for each document.
            embeddings: Embedding vectors for each document.
            documents: Text content of each document.
            metadatas: Optional metadata for each document.

        Returns:
            Number of documents added.
        """
        if not self.is_initialized:
            raise RuntimeError("Vector store not initialized. Call initialize() first.")

        if not (len(ids) == len(embeddings) == len(documents)):
            raise ValueError("ids, embeddings, and documents must have the same length")

        async with self._lock:
            assert self._collection is not None
            self._collection.add(
                ids=ids,
                embeddings=embeddings,  # type: ignore[arg-type]
                documents=documents,
                metadatas=metadatas or [{}] * len(ids),  # type: ignore[arg-type]
            )

        logger.debug(f"Added {len(ids)} documents to vector store")
        return len(ids)

    async def upsert_documents(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> int:
        """
        Upsert documents with embeddings to the vector store.
        If IDs already exist, the content and embeddings will be updated.

        Args:
            ids: Unique identifiers for each document.
            embeddings: Embedding vectors for each document.
            documents: Text content of each document.
            metadatas: Optional metadata for each document.

        Returns:
            Number of documents upserted.
        """
        if not self.is_initialized:
            raise RuntimeError("Vector store not initialized. Call initialize() first.")

        if not (len(ids) == len(embeddings) == len(documents)):
            raise ValueError("ids, embeddings, and documents must have the same length")

        async with self._lock:
            assert self._collection is not None
            self._collection.upsert(
                ids=ids,
                embeddings=embeddings,  # type: ignore[arg-type]
                documents=documents,
                metadatas=metadatas or [{}] * len(ids),  # type: ignore[arg-type]
            )

        logger.debug(f"Upserted {len(ids)} documents to vector store")
        return len(ids)

    async def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        similarity_threshold: float = 0.0,
        where: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """
        Perform similarity search on the vector store.

        Args:
            query_embedding: Embedding vector to search for.
            top_k: Maximum number of results to return.
            similarity_threshold: Minimum similarity score (0-1).
            where: Optional metadata filter.

        Returns:
            List of SearchResult objects sorted by score descending.

        Raises:
            RuntimeError: If the store is not initialized.
        """
        if not self.is_initialized:
            raise RuntimeError("Vector store not initialized. Call initialize() first.")

        async with self._lock:
            assert self._collection is not None
            results = self._collection.query(
                query_embeddings=[query_embedding],  # type: ignore[arg-type]
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"],  # type: ignore[list-item]
            )

        # Convert Chroma results to SearchResult objects
        search_results: list[SearchResult] = []

        if results["ids"] and results["ids"][0]:
            for idx, chunk_id in enumerate(results["ids"][0]):
                # Chroma returns distances, convert to similarity (cosine)
                distances = results["distances"]
                distance = distances[0][idx] if distances else 0.0
                similarity = 1 - distance  # Cosine distance to similarity

                if similarity >= similarity_threshold:
                    documents = results["documents"]
                    metadatas = results["metadatas"]
                    text_val = documents[0][idx] if documents else ""
                    meta_val: dict[str, Any] = {}
                    if metadatas and metadatas[0][idx]:
                        meta_val = dict(metadatas[0][idx])
                    search_results.append(
                        SearchResult(
                            text=text_val,
                            metadata=meta_val,
                            score=similarity,
                            chunk_id=chunk_id,
                        )
                    )

        # Sort by score descending
        search_results.sort(key=lambda x: x.score, reverse=True)

        logger.debug(
            f"Similarity search returned {len(search_results)} results "
            f"(threshold: {similarity_threshold})"
        )
        return search_results

    async def get_count(self, where: dict[str, Any] | None = None) -> int:
        """
        Get the number of documents in the collection, optionally filtered.

        Args:
            where: Optional metadata filter.

        Returns:
            Number of documents stored.
        """
        if not self.is_initialized:
            return 0

        async with self._lock:
            assert self._collection is not None
            if where:
                # get() is the only way to filter for counts in some Chroma versions
                # include=[] to minimize data transfer
                results = self._collection.get(where=where, include=[])
                if results and "ids" in results:
                    return len(results["ids"])
                return 0
            return self._collection.count()

    async def get_by_id(self, chunk_id: str) -> dict[str, Any] | None:
        """
        Get a document by its chunk ID.

        Args:
            chunk_id: The unique identifier of the chunk.

        Returns:
            Dictionary with 'text' and 'metadata' keys, or None if not found.
        """
        if not self.is_initialized:
            return None

        async with self._lock:
            assert self._collection is not None
            try:
                results = self._collection.get(
                    ids=[chunk_id],
                    include=["documents", "metadatas"],  # type: ignore[list-item]
                )

                if results["ids"] and results["ids"]:
                    documents = results.get("documents", [[]])
                    metadatas = results.get("metadatas", [[]])
                    text = documents[0] if documents else ""
                    metadata = metadatas[0] if metadatas else {}
                    return {
                        "text": text,
                        "metadata": metadata if metadata else {},
                    }
            except Exception as e:
                logger.warning(f"Failed to get document by ID {chunk_id}: {e}")

            return None

    async def delete_collection(self) -> None:
        """
        Delete the entire collection.

        Warning: This permanently removes all stored documents and embeddings.
        """
        if not self._client:
            return

        async with self._lock:
            try:
                assert self._client is not None
                self._client.delete_collection(self.collection_name)
                self._collection = None
                self._initialized = False
                logger.warning(f"Deleted collection: {self.collection_name}")
            except Exception as e:
                logger.error(f"Failed to delete collection: {e}")
                raise

    async def reset(self) -> None:
        """
        Reset the vector store by deleting and recreating the collection.

        Note: Embedding metadata is stored in collection metadata,
        so it will be cleared when collection is reset.
        """
        await self.delete_collection()
        self._initialized = False
        await self.initialize()

    async def close(self) -> None:
        """
        Close the vector store connection.

        Should be called during application shutdown.
        """
        async with self._lock:
            self._collection = None
            self._client = None
            self._initialized = False
            logger.info("Vector store connection closed")


# Global singleton instance
_vector_store: VectorStoreManager | None = None


def get_vector_store() -> VectorStoreManager:
    """Get the global vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStoreManager()
    return _vector_store


async def initialize_vector_store() -> VectorStoreManager:
    """Initialize and return the global vector store instance."""
    store = get_vector_store()
    await store.initialize()
    return store
