"""BM25 index manager for persistence and retrieval."""

import logging
from collections.abc import Sequence
from pathlib import Path

from llama_index.core.schema import BaseNode, NodeWithScore
from llama_index.retrievers.bm25 import BM25Retriever

from agent_brain_server.config import settings

logger = logging.getLogger(__name__)


class BM25IndexManager:
    """
    Manages the lifecycle of the BM25 index.

    Handles building the index from nodes, persisting it to disk,
    and loading it for retrieval.
    """

    def __init__(self, persist_dir: str | None = None):
        """
        Initialize the BM25 index manager.

        Args:
            persist_dir: Directory for index persistence.
        """
        self.persist_dir = persist_dir or settings.BM25_INDEX_PATH
        self._retriever: BM25Retriever | None = None

    @property
    def is_initialized(self) -> bool:
        """Check if the index is initialized."""
        return self._retriever is not None

    def initialize(self) -> None:
        """
        Load the index from disk if it exists.
        """
        persist_path = Path(self.persist_dir)
        if (persist_path / "retriever.json").exists():
            try:
                self._retriever = BM25Retriever.from_persist_dir(str(persist_path))
                logger.info(f"BM25 index loaded from {self.persist_dir}")
            except Exception as e:
                logger.error(f"Failed to load BM25 index: {e}")
                self._retriever = None
        else:
            logger.info("No existing BM25 index found")

    def build_index(self, nodes: Sequence[BaseNode]) -> None:
        """
        Build a new BM25 index from nodes and persist it.

        Args:
            nodes: List of LlamaIndex nodes.
        """
        logger.info(f"Building BM25 index with {len(nodes)} nodes")
        self._retriever = BM25Retriever.from_defaults(nodes=nodes)
        self.persist()

    def persist(self) -> None:
        """Persist the current index to disk."""
        if not self._retriever:
            logger.warning("No BM25 index to persist")
            return

        persist_path = Path(self.persist_dir)
        persist_path.mkdir(parents=True, exist_ok=True)
        self._retriever.persist(str(persist_path))
        logger.info(f"BM25 index persisted to {self.persist_dir}")

    def get_retriever(self, top_k: int = 5) -> BM25Retriever:
        """
        Get the BM25 retriever instance.

        Args:
            top_k: Number of results to return.

        Returns:
            The BM25Retriever instance.

        Raises:
            RuntimeError: If the index is not initialized.
        """
        if not self._retriever:
            raise RuntimeError("BM25 index not initialized")

        # Cap top_k to corpus size to avoid bm25s "k larger than available scores" error
        corpus_size = len(self._retriever.corpus) if self._retriever.corpus else 0
        if corpus_size > 0:
            effective_top_k = min(top_k, corpus_size)
        else:
            effective_top_k = top_k

        self._retriever.similarity_top_k = effective_top_k
        return self._retriever

    @property
    def corpus_size(self) -> int:
        """Get the number of documents in the BM25 index."""
        if not self._retriever or not self._retriever.corpus:
            return 0
        return len(self._retriever.corpus)

    async def search_with_filters(
        self,
        query: str,
        top_k: int = 5,
        source_types: list[str] | None = None,
        languages: list[str] | None = None,
        max_results: int | None = None,
    ) -> list[NodeWithScore]:
        """
        Search the BM25 index with metadata filtering.

        Args:
            query: Search query string.
            top_k: Number of results to return.
            source_types: Filter by source types (doc, code, test).
            languages: Filter by programming languages.

        Returns:
            List of NodeWithScore objects, filtered by metadata.
        """
        if not self._retriever:
            raise RuntimeError("BM25 index not initialized")

        # Get results for filtering
        retriever_top_k = max_results if max_results is not None else (top_k * 3)
        retriever = self.get_retriever(top_k=retriever_top_k)
        nodes = await retriever.aretrieve(query)

        # Apply metadata filtering
        filtered_nodes = []
        for node in nodes:
            metadata = node.node.metadata

            # Check source type filter
            if source_types:
                source_type = metadata.get("source_type", "doc")
                if source_type not in source_types:
                    continue

            # Check language filter
            if languages:
                language = metadata.get("language")
                if not language or language not in languages:
                    continue

            filtered_nodes.append(node)

        # Return top_k results after filtering
        return filtered_nodes[:top_k]

    def reset(self) -> None:
        """Reset the BM25 index by deleting persistent files."""
        self._retriever = None
        persist_path = Path(self.persist_dir)
        if persist_path.exists():
            for file in persist_path.glob("*"):
                file.unlink()
            persist_path.rmdir()
        logger.info("BM25 index reset")


# Global singleton instance
_bm25_manager: BM25IndexManager | None = None


def get_bm25_manager() -> BM25IndexManager:
    """Get the global BM25 manager instance."""
    global _bm25_manager
    if _bm25_manager is None:
        _bm25_manager = BM25IndexManager()
    return _bm25_manager
