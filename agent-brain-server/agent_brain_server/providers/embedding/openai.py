"""OpenAI embedding provider implementation."""

import logging
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from agent_brain_server.providers.base import BaseEmbeddingProvider
from agent_brain_server.providers.exceptions import AuthenticationError, ProviderError

if TYPE_CHECKING:
    from agent_brain_server.config.provider_config import EmbeddingConfig

logger = logging.getLogger(__name__)

# Model dimension mappings for OpenAI embedding models
OPENAI_MODEL_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-large": 3072,
    "text-embedding-3-small": 1536,
    "text-embedding-ada-002": 1536,
}


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI embedding provider using text-embedding models.

    Supports:
    - text-embedding-3-large (3072 dimensions, highest quality)
    - text-embedding-3-small (1536 dimensions, faster)
    - text-embedding-ada-002 (1536 dimensions, legacy)
    """

    def __init__(self, config: "EmbeddingConfig") -> None:
        """Initialize OpenAI embedding provider.

        Args:
            config: Embedding configuration

        Raises:
            AuthenticationError: If API key is not available
        """
        api_key = config.get_api_key()
        if not api_key:
            raise AuthenticationError(
                f"Missing API key. Set {config.api_key_env} environment variable.",
                self.provider_name,
            )

        batch_size = config.params.get("batch_size", 100)
        super().__init__(model=config.model, batch_size=batch_size)

        self._client = AsyncOpenAI(api_key=api_key)
        self._dimensions_override = config.params.get("dimensions")

    @property
    def provider_name(self) -> str:
        """Human-readable provider name."""
        return "OpenAI"

    def get_dimensions(self) -> int:
        """Get embedding dimensions for current model.

        Returns:
            Number of dimensions in embedding vector
        """
        if self._dimensions_override:
            return int(self._dimensions_override)
        return OPENAI_MODEL_DIMENSIONS.get(self._model, 3072)

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats

        Raises:
            ProviderError: If embedding generation fails
        """
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
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
            ProviderError: If embedding generation fails
        """
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            raise ProviderError(
                f"Failed to generate batch embeddings: {e}",
                self.provider_name,
                cause=e,
            ) from e
