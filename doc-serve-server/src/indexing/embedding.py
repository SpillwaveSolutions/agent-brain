"""Embedding generation using OpenAI's text-embedding models."""

import logging
import asyncio
from typing import List, Optional

from openai import AsyncOpenAI

from .chunking import TextChunk
from ..config import settings

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Generates embeddings using OpenAI's embedding models.

    Supports batch processing with configurable batch sizes
    and automatic retry on rate limits.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: int = None,
    ):
        """
        Initialize the embedding generator.

        Args:
            api_key: OpenAI API key. Defaults to config value.
            model: Embedding model name. Defaults to config value.
            batch_size: Number of texts to embed per API call. Defaults to 100.
        """
        self.model = model or settings.EMBEDDING_MODEL
        self.batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE

        # Initialize OpenAI async client
        self.client = AsyncOpenAI(
            api_key=api_key or settings.OPENAI_API_KEY,
        )

    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector as list of floats.
        """
        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding

    async def embed_texts(
        self,
        texts: List[str],
        progress_callback: Optional[callable] = None,
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.
            progress_callback: Optional callback(processed, total) for progress.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        all_embeddings: List[List[float]] = []

        # Process in batches to respect API limits
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]

            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                )

                # Extract embeddings in order
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)

                if progress_callback:
                    await progress_callback(
                        min(i + self.batch_size, len(texts)),
                        len(texts),
                    )

                logger.debug(
                    f"Generated embeddings for batch {i // self.batch_size + 1} "
                    f"({len(batch)} texts)"
                )

            except Exception as e:
                logger.error(f"Failed to generate embeddings for batch: {e}")
                raise

        return all_embeddings

    async def embed_chunks(
        self,
        chunks: List[TextChunk],
        progress_callback: Optional[callable] = None,
    ) -> List[List[float]]:
        """
        Generate embeddings for a list of text chunks.

        Args:
            chunks: List of TextChunk objects.
            progress_callback: Optional callback for progress updates.

        Returns:
            List of embedding vectors corresponding to each chunk.
        """
        texts = [chunk.text for chunk in chunks]
        return await self.embed_texts(texts, progress_callback)

    async def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a search query.

        This is a convenience wrapper around embed_text for queries.

        Args:
            query: The search query text.

        Returns:
            Query embedding vector.
        """
        return await self.embed_text(query)

    def get_embedding_dimensions(self) -> int:
        """
        Get the expected embedding dimensions for the current model.

        Returns:
            Number of dimensions in the embedding vector.
        """
        # Known dimensions for OpenAI models
        model_dimensions = {
            "text-embedding-3-large": 3072,
            "text-embedding-3-small": 1536,
            "text-embedding-ada-002": 1536,
        }
        return model_dimensions.get(self.model, settings.EMBEDDING_DIMENSIONS)


# Singleton instance
_embedding_generator: Optional[EmbeddingGenerator] = None


def get_embedding_generator() -> EmbeddingGenerator:
    """Get the global embedding generator instance."""
    global _embedding_generator
    if _embedding_generator is None:
        _embedding_generator = EmbeddingGenerator()
    return _embedding_generator
