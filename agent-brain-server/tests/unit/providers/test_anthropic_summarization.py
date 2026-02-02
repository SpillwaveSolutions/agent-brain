"""Unit tests for Anthropic summarization provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_brain_server.config.provider_config import SummarizationConfig
from agent_brain_server.providers.exceptions import AuthenticationError, ProviderError
from agent_brain_server.providers.summarization.anthropic import (
    AnthropicSummarizationProvider,
)


class TestAnthropicSummarizationProvider:
    """Tests for AnthropicSummarizationProvider."""

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    def test_initialization(self) -> None:
        """Test provider initialization."""
        config = SummarizationConfig(
            provider="anthropic",
            model="claude-3-5-haiku-20241022",
        )
        provider = AnthropicSummarizationProvider(config)

        assert provider.provider_name == "Anthropic"
        assert provider.model_name == "claude-3-5-haiku-20241022"

    def test_initialization_missing_key(self) -> None:
        """Test error when API key is missing."""
        with patch.dict("os.environ", {}, clear=True):
            config = SummarizationConfig(
                provider="anthropic",
                api_key_env="MISSING_KEY",
            )
            with pytest.raises(AuthenticationError):
                AnthropicSummarizationProvider(config)

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    def test_custom_params(self) -> None:
        """Test custom parameters."""
        config = SummarizationConfig(
            provider="anthropic",
            params={"max_tokens": 500, "temperature": 0.2},
        )
        provider = AnthropicSummarizationProvider(config)
        assert provider._max_tokens == 500
        assert provider._temperature == 0.2

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate(self) -> None:
        """Test text generation."""
        config = SummarizationConfig(provider="anthropic")
        provider = AnthropicSummarizationProvider(config)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Generated text")]
        provider._client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.generate("Test prompt")

        assert result == "Generated text"
        provider._client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_summarize(self) -> None:
        """Test code summarization."""
        config = SummarizationConfig(provider="anthropic")
        provider = AnthropicSummarizationProvider(config)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This code does X")]
        provider._client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.summarize("def foo(): return 1")

        assert result == "This code does X"
        # Verify the prompt contains the code
        call_args = provider._client.messages.create.call_args
        messages = call_args.kwargs["messages"]
        assert "def foo(): return 1" in messages[0]["content"]

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_error(self) -> None:
        """Test error handling in generate."""
        config = SummarizationConfig(provider="anthropic")
        provider = AnthropicSummarizationProvider(config)

        provider._client.messages.create = AsyncMock(
            side_effect=Exception("API error"),
        )

        with pytest.raises(ProviderError) as exc_info:
            await provider.generate("Test prompt")

        assert "API error" in str(exc_info.value)
        assert exc_info.value.provider == "Anthropic"
