"""Google Gemini summarization provider implementation."""

import logging
from typing import TYPE_CHECKING

import google.genai as genai
from google.genai.types import GenerateContentConfig

from agent_brain_server.providers.base import BaseSummarizationProvider
from agent_brain_server.providers.exceptions import AuthenticationError, ProviderError

if TYPE_CHECKING:
    from agent_brain_server.config.provider_config import SummarizationConfig

logger = logging.getLogger(__name__)


class GeminiSummarizationProvider(BaseSummarizationProvider):
    """Google Gemini summarization provider.

    Supports:
    - gemini-2.0-flash (fast, cost-effective)
    - gemini-2.0-pro (highest quality)
    - And other Gemini models
    """

    def __init__(self, config: "SummarizationConfig") -> None:
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
        self._top_p = config.params.get("top_p", 0.95)

        super().__init__(
            model=config.model,
            max_tokens=max_tokens,
            temperature=temperature,
            prompt_template=prompt_template,
        )

        self._client = genai.Client(api_key=api_key)
        self._generation_config = GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
            top_p=self._top_p,
        )

    @property
    def provider_name(self) -> str:
        """Human-readable provider name."""
        return "Gemini"

    async def generate(self, prompt: str) -> str:
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=self._generation_config,
            )
            return str(response.text)
        except Exception as e:
            raise ProviderError(
                f"Failed to generate text: {e}",
                self.provider_name,
                cause=e,
            ) from e
