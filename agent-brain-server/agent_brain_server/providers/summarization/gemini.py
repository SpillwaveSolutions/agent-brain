"""Google Gemini summarization provider implementation."""

import logging
from typing import TYPE_CHECKING

import google.generativeai as genai

from agent_brain_server.providers.base import BaseSummarizationProvider
from agent_brain_server.providers.exceptions import AuthenticationError, ProviderError

if TYPE_CHECKING:
    from agent_brain_server.config.provider_config import SummarizationConfig

logger = logging.getLogger(__name__)


class GeminiSummarizationProvider(BaseSummarizationProvider):
    """Google Gemini summarization provider.

    Supports:
    - gemini-3-flash (fast, cost-effective)
    - gemini-3-pro (highest quality)
    - And other Gemini models
    """

    def __init__(self, config: "SummarizationConfig") -> None:
        """Initialize Gemini summarization provider.

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

        max_tokens = config.params.get(
            "max_output_tokens", config.params.get("max_tokens", 300)
        )
        temperature = config.params.get("temperature", 0.1)
        prompt_template = config.params.get("prompt_template")
        top_p = config.params.get("top_p", 0.95)

        super().__init__(
            model=config.model,
            max_tokens=max_tokens,
            temperature=temperature,
            prompt_template=prompt_template,
        )

        # Configure Gemini with API key
        genai.configure(api_key=api_key)  # type: ignore[attr-defined]

        # Create model with generation config
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )
        self._model_instance = genai.GenerativeModel(  # type: ignore[attr-defined]
            model_name=config.model,
            generation_config=generation_config,
        )

    @property
    def provider_name(self) -> str:
        """Human-readable provider name."""
        return "Gemini"

    async def generate(self, prompt: str) -> str:
        """Generate text based on prompt using Gemini.

        Args:
            prompt: The prompt to send to Gemini

        Returns:
            Generated text response

        Raises:
            ProviderError: If generation fails
        """
        try:
            # Use async generation
            response = await self._model_instance.generate_content_async(prompt)
            return str(response.text)
        except Exception as e:
            raise ProviderError(
                f"Failed to generate text: {e}",
                self.provider_name,
                cause=e,
            ) from e
