"""Embedding generation using pluggable providers.

This module provides embedding and summarization functionality using
the configurable provider system. Providers are selected based on
config.yaml or environment defaults.
"""

import logging
import re
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Optional

from agent_brain_server.config.provider_config import load_provider_settings
from agent_brain_server.providers.factory import ProviderRegistry

if TYPE_CHECKING:
    from agent_brain_server.providers.base import (
        EmbeddingProvider,
        SummarizationProvider,
    )

from .chunking import TextChunk

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generates embeddings and summaries using pluggable providers.

    Supports batch processing with configurable batch sizes
    and automatic provider selection based on configuration.
    """

    def __init__(
        self,
        embedding_provider: Optional["EmbeddingProvider"] = None,
        summarization_provider: Optional["SummarizationProvider"] = None,
    ):
        """Initialize the embedding generator.

        Args:
            embedding_provider: Optional embedding provider. If not provided,
                creates one from configuration.
            summarization_provider: Optional summarization provider. If not
                provided, creates one from configuration.
        """
        # Load configuration
        settings = load_provider_settings()

        # Initialize providers from config or use provided ones
        if embedding_provider is not None:
            self._embedding_provider = embedding_provider
        else:
            self._embedding_provider = ProviderRegistry.get_embedding_provider(
                settings.embedding
            )

        if summarization_provider is not None:
            self._summarization_provider = summarization_provider
        else:
            self._summarization_provider = ProviderRegistry.get_summarization_provider(
                settings.summarization
            )

        logger.info(
            f"EmbeddingGenerator initialized with "
            f"{self._embedding_provider.provider_name} embeddings "
            f"({self._embedding_provider.model_name}) and "
            f"{self._summarization_provider.provider_name} summarization "
            f"({self._summarization_provider.model_name})"
        )

    @property
    def model(self) -> str:
        """Get the embedding model name."""
        return self._embedding_provider.model_name

    @property
    def embedding_provider(self) -> "EmbeddingProvider":
        """Get the embedding provider."""
        return self._embedding_provider

    @property
    def summarization_provider(self) -> "SummarizationProvider":
        """Get the summarization provider."""
        return self._summarization_provider

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text (cache-intercepted).

        Checks the embedding cache before calling the provider. On a cache
        miss, calls the provider and stores the result for future requests.
        If the cache is not initialised, delegates directly to the provider
        for backward compatibility.

        Lazy-imports the cache module to avoid a circular import between
        ``indexing`` and ``services`` packages (both loaded at startup).

        Args:
            text: Text to embed.

        Returns:
            Embedding vector as list of floats.
        """
        # Lazy import to avoid circular import at module init time:
        #   indexing.__init__ -> embedding -> services.embedding_cache ->
        #   services.__init__ -> indexing_service -> indexing.__init__
        from agent_brain_server.services.embedding_cache import (  # noqa: PLC0415
            EmbeddingCacheService,
            get_embedding_cache,
        )

        cache = get_embedding_cache()
        if cache is not None:
            key = EmbeddingCacheService.make_cache_key(
                text,
                self._embedding_provider.provider_name,
                self._embedding_provider.model_name,
                self._embedding_provider.get_dimensions(),
            )
            cached = await cache.get(key)
            if cached is not None:
                return cached
            result = await self._embedding_provider.embed_text(text)
            await cache.put(key, result)
            return result
        return await self._embedding_provider.embed_text(text)

    async def embed_texts(
        self,
        texts: list[str],
        progress_callback: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts (batch cache-intercepted).

        Performs a batch cache lookup for all texts, then calls the provider
        only for cache misses. Results are stored in the cache before
        returning. Order is preserved in the output list.

        If the cache is not initialised, delegates directly to the provider
        for backward compatibility.

        Args:
            texts: List of texts to embed.
            progress_callback: Optional callback(processed, total) for
                progress reporting. Passed only to the provider call for
                miss texts.

        Returns:
            List of embedding vectors in the same order as ``texts``.
        """
        # Lazy import to break circular import (see embed_text for details)
        from agent_brain_server.services.embedding_cache import (  # noqa: PLC0415
            EmbeddingCacheService,
            get_embedding_cache,
        )

        cache = get_embedding_cache()
        if cache is None:
            return await self._embedding_provider.embed_texts(texts, progress_callback)

        dims = self._embedding_provider.get_dimensions()
        provider = self._embedding_provider.provider_name
        model = self._embedding_provider.model_name

        # Build cache keys for all texts
        keys = [
            EmbeddingCacheService.make_cache_key(t, provider, model, dims)
            for t in texts
        ]

        # Batch lookup: one SQL query for all keys
        hits = await cache.get_batch(keys)

        # Assemble results list; identify miss indices
        results: list[list[float] | None] = [hits.get(k) for k in keys]
        miss_indices = [i for i, r in enumerate(results) if r is None]

        if miss_indices:
            miss_texts = [texts[i] for i in miss_indices]
            miss_embeddings = await self._embedding_provider.embed_texts(
                miss_texts, progress_callback
            )
            # Collect results and batch-write to cache in one transaction
            cache_items: list[tuple[str, list[float]]] = []
            for idx, embedding in zip(miss_indices, miss_embeddings):
                results[idx] = embedding
                cache_items.append((keys[idx], embedding))
            await cache.put_many(cache_items)

        # All results are now populated (no Nones remain)
        return [r for r in results if r is not None]

    async def embed_chunks(
        self,
        chunks: list[TextChunk],
        progress_callback: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> list[list[float]]:
        """Generate embeddings for a list of text chunks.

        Args:
            chunks: List of TextChunk objects.
            progress_callback: Optional callback for progress updates.

        Returns:
            List of embedding vectors corresponding to each chunk.
        """
        texts = [chunk.text for chunk in chunks]
        return await self.embed_texts(texts, progress_callback)

    async def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a search query.

        This is a convenience wrapper around embed_text for queries.

        Args:
            query: The search query text.

        Returns:
            Query embedding vector.
        """
        return await self.embed_text(query)

    def get_embedding_dimensions(self) -> int:
        """Get the expected embedding dimensions for the current model.

        Returns:
            Number of dimensions in the embedding vector.
        """
        return self._embedding_provider.get_dimensions()

    async def generate_summary(self, code_text: str) -> str:
        """Generate a natural language summary of code.

        Args:
            code_text: The source code to summarize.

        Returns:
            Natural language summary of the code's functionality.
        """
        try:
            summary = await self._summarization_provider.summarize(code_text)

            if summary and len(summary) > 10:
                return summary
            else:
                logger.warning(
                    f"{self._summarization_provider.provider_name} "
                    "returned empty or too short summary"
                )
                return self._extract_fallback_summary(code_text)

        except Exception as e:
            logger.error(f"Failed to generate code summary: {e}")
            return self._extract_fallback_summary(code_text)

    def _extract_fallback_summary(self, code_text: str) -> str:
        """Extract summary from docstrings or comments as fallback.

        Args:
            code_text: Source code to analyze.

        Returns:
            Extracted summary or empty string.
        """
        # Try to find Python docstrings
        docstring_match = re.search(r'""".*?"""', code_text, re.DOTALL)
        if docstring_match:
            docstring = docstring_match.group(0)[3:-3]
            if len(docstring) > 10:
                return docstring[:200] + "..." if len(docstring) > 200 else docstring

        # Try to find function/class comments
        comment_match = re.search(
            r"#.*(?:function|class|method|def)", code_text, re.IGNORECASE
        )
        if comment_match:
            return comment_match.group(0).strip("#").strip()

        # Last resort: first line if it looks like a comment
        lines = code_text.strip().split("\n")
        first_line = lines[0].strip()
        if first_line.startswith(("#", "//", "/*")):
            return first_line.lstrip("#/*").strip()

        return ""


# Singleton instance
_embedding_generator: EmbeddingGenerator | None = None


def get_embedding_generator() -> EmbeddingGenerator:
    """Get the global embedding generator instance."""
    global _embedding_generator
    if _embedding_generator is None:
        _embedding_generator = EmbeddingGenerator()
    return _embedding_generator


def reset_embedding_generator() -> None:
    """Reset the global embedding generator (for testing)."""
    global _embedding_generator
    _embedding_generator = None
