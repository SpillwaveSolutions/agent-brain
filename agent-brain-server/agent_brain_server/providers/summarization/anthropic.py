"""Anthropic (Claude) summarization provider implementation."""

import logging
from typing import TYPE_CHECKING

from anthropic import AsyncAnthropic

from agent_brain_server.providers.base import BaseSummarizationProvider
from agent_brain_server.providers.exceptions import AuthenticationError, ProviderError

if TYPE_CHECKING:
    from agent_brain_server.config.provider_config import SummarizationConfig

logger = logging.getLogger(__name__)


class AnthropicSummarizationProvider(BaseSummarizationProvider):
    """Anthropic (Claude) summarization provider.

    Supports:
    - claude-3-5-haiku-20241022 (fast, cost-effective)
    - claude-3-5-sonnet-20241022 (balanced)
    - claude-3-opus-20240229 (highest quality)
    - And other Claude models
    """

    def __init__(self, config: "SummarizationConfig") -> None:
        """Initialize Anthropic summarization provider.

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

        self._client = AsyncAnthropic(api_key=api_key)

    @property
    def provider_name(self) -> str:
        """Human-readable provider name."""
        return "Anthropic"

    async def generate(self, prompt: str) -> str:
        """Generate text based on prompt using Claude.

        Args:
            prompt: The prompt to send to Claude

        Returns:
            Generated text response

        Raises:
            ProviderError: If generation fails
        """
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            # Extract text from response
            return response.content[0].text  # type: ignore[union-attr]
        except Exception as e:
            raise ProviderError(
                f"Failed to generate text: {e}",
                self.provider_name,
                cause=e,
            ) from e
