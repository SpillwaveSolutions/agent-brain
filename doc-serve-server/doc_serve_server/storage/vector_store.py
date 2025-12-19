"""Chroma vector store manager with thread-safe operations."""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from doc_serve_server.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from a similarity search."""

    text: str
    metadata: dict[str, Any]
    score: float
    chunk_id: str


class VectorStoreManager:
    """
    Manages Chroma vector store operations with thread-safe access.

    This class provides a high-level interface for storing and retrieving
    document embeddings using Chroma as the backend.
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection_name: Optional[str] = None,
    ):
        """
        Initialize the vector store manager.

        Args:
            persist_dir: Directory for persistent storage. Defaults to config value.
            collection_name: Name of the collection. Defaults to config value.
        """
        self.persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR
        self.collection_name = collection_name or settings.COLLECTION_NAME
        self._client: Optional[chromadb.PersistentClient] = None  # type: ignore[valid-type]
        self._collection: Optional[chromadb.Collection] = None
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

    async def add_documents(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: Optional[list[dict[str, Any]]] = None,
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
        metadatas: Optional[list[dict[str, Any]]] = None,
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
        where: Optional[dict[str, Any]] = None,
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

    async def get_count(self, where: Optional[dict[str, Any]] = None) -> int:
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
_vector_store: Optional[VectorStoreManager] = None


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
