"""Ollama embedding provider implementation."""

import logging
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from agent_brain_server.providers.base import BaseEmbeddingProvider
from agent_brain_server.providers.exceptions import (
    OllamaConnectionError,
    ProviderError,
)

if TYPE_CHECKING:
    from agent_brain_server.config.provider_config import EmbeddingConfig

logger = logging.getLogger(__name__)

# Model dimension mappings for common Ollama embedding models
OLLAMA_MODEL_DIMENSIONS: dict[str, int] = {
    "nomic-embed-text": 768,
    "mxbai-embed-large": 1024,
    "all-minilm": 384,
    "snowflake-arctic-embed": 1024,
    "bge-m3": 1024,
    "bge-large": 1024,
}

DEFAULT_OLLAMA_DIMENSIONS = 768


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """Ollama embedding provider using local models.

    Uses OpenAI-compatible API endpoint provided by Ollama.

    Supports:
    - nomic-embed-text (768 dimensions, general purpose)
    - mxbai-embed-large (1024 dimensions, multilingual)
    - all-minilm (384 dimensions, lightweight)
    - snowflake-arctic-embed (1024 dimensions, high quality)
    - And any other embedding model available in Ollama
    """

    def __init__(self, config: "EmbeddingConfig") -> None:
        """Initialize Ollama embedding provider.

        Args:
            config: Embedding configuration

        Note:
            Ollama does not require an API key as it runs locally.
        """
        batch_size = config.params.get("batch_size", 100)
        super().__init__(model=config.model, batch_size=batch_size)

        # Ollama uses OpenAI-compatible API
        base_url = config.get_base_url() or "http://localhost:11434/v1"
        self._base_url = base_url
        self._client = AsyncOpenAI(
            api_key="ollama",  # Ollama doesn't need real key
            base_url=base_url,
        )

        # Optional parameters
        self._num_ctx = config.params.get("num_ctx", 2048)
        self._num_threads = config.params.get("num_threads")

    @property
    def provider_name(self) -> str:
        """Human-readable provider name."""
        return "Ollama"

    def get_dimensions(self) -> int:
        """Get embedding dimensions for current model.

        Returns:
            Number of dimensions in embedding vector
        """
        return OLLAMA_MODEL_DIMENSIONS.get(self._model, DEFAULT_OLLAMA_DIMENSIONS)

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats

        Raises:
            OllamaConnectionError: If Ollama is not running
            ProviderError: If embedding generation fails
        """
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            if "connection" in str(e).lower() or "refused" in str(e).lower():
                raise OllamaConnectionError(self._base_url, cause=e) from e
            raise ProviderError(
                f"Failed to generate embedding: {e}",
                self.provider_name,
                cause=e,
            ) from e

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors

        Raises:
            OllamaConnectionError: If Ollama is not running
            ProviderError: If embedding generation fails
        """
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            if "connection" in str(e).lower() or "refused" in str(e).lower():
                raise OllamaConnectionError(self._base_url, cause=e) from e
            raise ProviderError(
                f"Failed to generate batch embeddings: {e}",
                self.provider_name,
                cause=e,
            ) from e

    async def health_check(self) -> bool:
        """Check if Ollama is running and accessible.

        Returns:
            True if Ollama is healthy, False otherwise
        """
        try:
            # Try to list models to verify connection
            await self._client.models.list()
            return True
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False
