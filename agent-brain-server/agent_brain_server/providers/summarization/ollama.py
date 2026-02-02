"""Ollama summarization provider implementation."""

import logging
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from agent_brain_server.providers.base import BaseSummarizationProvider
from agent_brain_server.providers.exceptions import (
    OllamaConnectionError,
    ProviderError,
)

if TYPE_CHECKING:
    from agent_brain_server.config.provider_config import SummarizationConfig

logger = logging.getLogger(__name__)


class OllamaSummarizationProvider(BaseSummarizationProvider):
    """Ollama summarization provider using local models.

    Uses OpenAI-compatible API endpoint provided by Ollama.

    Supports:
    - llama3.2 (Meta's Llama 3.2)
    - llama3.1 (Meta's Llama 3.1)
    - mistral (Mistral 7B)
    - codellama (Code Llama)
    - deepseek-coder (DeepSeek Coder)
    - And any other chat model available in Ollama
    """

    def __init__(self, config: "SummarizationConfig") -> None:
        """Initialize Ollama summarization provider.

        Args:
            config: Summarization configuration

        Note:
            Ollama does not require an API key as it runs locally.
        """
        max_tokens = config.params.get("max_tokens", 300)
        temperature = config.params.get("temperature", 0.1)
        prompt_template = config.params.get("prompt_template")

        super().__init__(
            model=config.model,
            max_tokens=max_tokens,
            temperature=temperature,
            prompt_template=prompt_template,
        )

        # Ollama uses OpenAI-compatible API
        base_url = config.get_base_url() or "http://localhost:11434/v1"
        self._base_url = base_url
        self._client = AsyncOpenAI(
            api_key="ollama",  # Ollama doesn't need real key
            base_url=base_url,
        )

        # Optional parameters
        self._num_ctx = config.params.get("num_ctx", 4096)

    @property
    def provider_name(self) -> str:
        """Human-readable provider name."""
        return "Ollama"

    async def generate(self, prompt: str) -> str:
        """Generate text based on prompt using Ollama.

        Args:
            prompt: The prompt to send to Ollama

        Returns:
            Generated text response

        Raises:
            OllamaConnectionError: If Ollama is not running
            ProviderError: If generation fails
        """
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            # Extract text from response
            content = response.choices[0].message.content
            return content if content else ""
        except Exception as e:
            if "connection" in str(e).lower() or "refused" in str(e).lower():
                raise OllamaConnectionError(self._base_url, cause=e) from e
            raise ProviderError(
                f"Failed to generate text: {e}",
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
