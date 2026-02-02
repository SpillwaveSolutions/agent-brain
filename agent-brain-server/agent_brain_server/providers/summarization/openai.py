"""OpenAI (GPT) summarization provider implementation."""

import logging
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from agent_brain_server.providers.base import BaseSummarizationProvider
from agent_brain_server.providers.exceptions import AuthenticationError, ProviderError

if TYPE_CHECKING:
    from agent_brain_server.config.provider_config import SummarizationConfig

logger = logging.getLogger(__name__)


class OpenAISummarizationProvider(BaseSummarizationProvider):
    """OpenAI (GPT) summarization provider.

    Supports:
    - gpt-5 (most capable)
    - gpt-5-mini (fast, cost-effective)
    - And other OpenAI chat models
    """

    def __init__(self, config: "SummarizationConfig") -> None:
        """Initialize OpenAI summarization provider.

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

        self._client = AsyncOpenAI(api_key=api_key)

    @property
    def provider_name(self) -> str:
        """Human-readable provider name."""
        return "OpenAI"

    async def generate(self, prompt: str) -> str:
        """Generate text based on prompt using GPT.

        Args:
            prompt: The prompt to send to GPT

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
