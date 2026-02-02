"""xAI Grok summarization provider implementation."""

import logging
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from agent_brain_server.providers.base import BaseSummarizationProvider
from agent_brain_server.providers.exceptions import AuthenticationError, ProviderError

if TYPE_CHECKING:
    from agent_brain_server.config.provider_config import SummarizationConfig

logger = logging.getLogger(__name__)


class GrokSummarizationProvider(BaseSummarizationProvider):
    """xAI Grok summarization provider.

    Uses OpenAI-compatible API at https://api.x.ai/v1

    Supports:
    - grok-beta (current beta model)
    - grok-2 (when available)
    - And other Grok models as they become available
    """

    def __init__(self, config: "SummarizationConfig") -> None:
        """Initialize Grok summarization provider.

        Args:
            config: Summarization configuration

        Raises:
            AuthenticationError: If API key is not available
        """
        api_key = config.get_api_key()
        if not api_key:
            raise AuthenticationError(
                f"Missing API key. Set {config.api_key_env} environment variable.",
                self.provider_name,
            )

        max_tokens = config.params.get("max_tokens", 300)
        temperature = config.params.get("temperature", 0.1)
        prompt_template = config.params.get("prompt_template")

        super().__init__(
            model=config.model,
            max_tokens=max_tokens,
            temperature=temperature,
            prompt_template=prompt_template,
        )

        # Grok uses OpenAI-compatible API
        base_url = config.get_base_url() or "https://api.x.ai/v1"
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    @property
    def provider_name(self) -> str:
        """Human-readable provider name."""
        return "Grok"

    async def generate(self, prompt: str) -> str:
        """Generate text based on prompt using Grok.

        Args:
            prompt: The prompt to send to Grok

        Returns:
            Generated text response

        Raises:
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
            raise ProviderError(
                f"Failed to generate text: {e}",
                self.provider_name,
                cause=e,
            ) from e
