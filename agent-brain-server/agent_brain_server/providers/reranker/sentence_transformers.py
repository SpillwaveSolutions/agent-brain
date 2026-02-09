"""SentenceTransformer CrossEncoder reranking provider."""

import asyncio
import logging
from typing import TYPE_CHECKING

from sentence_transformers import CrossEncoder

from agent_brain_server.providers.factory import ProviderRegistry
from agent_brain_server.providers.reranker.base import BaseRerankerProvider

if TYPE_CHECKING:
    from agent_brain_server.config.provider_config import RerankerConfig

logger = logging.getLogger(__name__)


class SentenceTransformerRerankerProvider(BaseRerankerProvider):
    """Reranker using sentence-transformers CrossEncoder.

    Uses pre-trained cross-encoder models for accurate document reranking.
    The CrossEncoder scores query-document pairs directly, providing
    more accurate relevance scores than bi-encoder similarity.

    Default model: cross-encoder/ms-marco-MiniLM-L-6-v2 (fast, good accuracy)
    Alternative: cross-encoder/ms-marco-MiniLM-L-12-v2 (slower, better accuracy)
    """

    def __init__(self, config: "RerankerConfig") -> None:
        """Initialize the CrossEncoder reranker.

        Args:
            config: Reranker configuration.
        """
        super().__init__(config)
        self._cross_encoder: CrossEncoder | None = None
        self._model_loaded = False
        self._availability_checked = False
        self._is_available_cached = False

    def _ensure_model_loaded(self) -> CrossEncoder:
        """Lazy-load the CrossEncoder model.

        Returns:
            Loaded CrossEncoder instance.
        """
        if self._cross_encoder is None:
            logger.info(f"Loading CrossEncoder model: {self._model}")
            self._cross_encoder = CrossEncoder(self._model)
            self._model_loaded = True
            self._availability_checked = True
            self._is_available_cached = True
            logger.info(f"CrossEncoder model loaded: {self._model}")
        return self._cross_encoder

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[tuple[int, float]]:
        """Rerank documents using CrossEncoder.

        Uses CrossEncoder.rank() for efficient batch scoring and sorting.
        Runs in thread pool to avoid blocking the async event loop.

        Args:
            query: The search query.
            documents: List of document texts to rerank.
            top_k: Number of top results to return.

        Returns:
            List of (original_index, score) tuples, sorted by score descending.
        """
        if not documents:
            return []

        # Limit top_k to document count
        effective_top_k = min(top_k, len(documents))

        # Run CrossEncoder in thread pool (CPU-bound operation)
        results = await asyncio.to_thread(
            self._rerank_sync,
            query,
            documents,
            effective_top_k,
        )

        logger.debug(
            f"Reranked {len(documents)} documents, returning top {effective_top_k}"
        )

        return results

    def _rerank_sync(
        self,
        query: str,
        documents: list[str],
        top_k: int,
    ) -> list[tuple[int, float]]:
        """Synchronous reranking implementation.

        Args:
            query: The search query.
            documents: List of document texts.
            top_k: Number of results to return.

        Returns:
            List of (corpus_id, score) tuples.
        """
        model = self._ensure_model_loaded()

        # CrossEncoder.rank() returns sorted results with corpus_id and score
        # return_documents=False for efficiency (we don't need the text back)
        ranked = model.rank(
            query,
            documents,
            top_k=top_k,
            return_documents=False,
        )

        # Convert to (index, score) tuples
        # corpus_id is always int from CrossEncoder.rank()
        return [(int(r["corpus_id"]), float(r["score"])) for r in ranked]

    @property
    def provider_name(self) -> str:
        """Human-readable provider name."""
        return "SentenceTransformers"

    def is_available(self) -> bool:
        """Check if CrossEncoder can be loaded.

        Uses cached result after first check to avoid model loading
        during query path. Call warm_up() at startup to preload.

        Returns:
            True if model can be loaded, False otherwise.
        """
        # Return cached result if already checked
        if self._availability_checked:
            return self._is_available_cached

        # If model already loaded, it's available
        if self._model_loaded:
            self._availability_checked = True
            self._is_available_cached = True
            return True

        # First check - just verify the model name is valid without loading
        # This avoids loading the model in the query path
        try:
            # Check if model exists by trying to get config (lighter than full load)
            from huggingface_hub import hf_hub_download

            try:
                # Try to check if the model repo exists
                hf_hub_download(
                    self._model,
                    "config.json",
                    local_files_only=True,
                )
                self._availability_checked = True
                self._is_available_cached = True
                return True
            except Exception:
                # Model not cached locally, assume it's available for download
                # The actual download will happen on first use
                self._availability_checked = True
                self._is_available_cached = True
                return True
        except Exception as e:
            logger.warning(f"CrossEncoder availability check failed: {e}")
            self._availability_checked = True
            self._is_available_cached = False
            return False

    def warm_up(self) -> bool:
        """Pre-load the model at startup to avoid first-query latency.

        Call this during application startup if reranking is enabled.

        Returns:
            True if model loaded successfully, False otherwise.
        """
        try:
            self._ensure_model_loaded()
            return True
        except Exception as e:
            logger.warning(f"CrossEncoder warm-up failed: {e}")
            self._availability_checked = True
            self._is_available_cached = False
            return False


# Register provider on import
ProviderRegistry.register_reranker_provider(
    "sentence-transformers",
    SentenceTransformerRerankerProvider,
)
