"""Unit tests for OpenAI summarization provider."""

from unittest.mock import patch

import pytest

from agent_brain_server.config.provider_config import SummarizationConfig
from agent_brain_server.providers.exceptions import AuthenticationError
from agent_brain_server.providers.summarization.openai import (
    OpenAISummarizationProvider,
)


class TestOpenAISummarizationProvider:
    """Tests for OpenAISummarizationProvider."""

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_initialization(self) -> None:
        """Test provider initialization."""
        config = SummarizationConfig(provider="openai", model="gpt-5-mini")
        provider = OpenAISummarizationProvider(config)

        assert provider.provider_name == "OpenAI"
        assert provider.model_name == "gpt-5-mini"

    def test_initialization_missing_key(self) -> None:
        """Test error when API key is missing."""
        with patch.dict("os.environ", {}, clear=True):
            config = SummarizationConfig(
                provider="openai",
                api_key_env="MISSING_KEY",
            )
            with pytest.raises(AuthenticationError):
                OpenAISummarizationProvider(config)


class TestOpenAISummarizationBaseUrl:
    """Tests for OpenAI-compatible endpoint support (issue #222)."""

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_configured_base_url_is_passed_to_client(self) -> None:
        """A configured base_url must reach the AsyncOpenAI client."""
        config = SummarizationConfig(
            provider="openai",
            model="gpt-5-mini",
            base_url="https://gateway.internal/v1",
        )
        provider = OpenAISummarizationProvider(config)

        assert str(provider._client.base_url).rstrip("/") == (
            "https://gateway.internal/v1"
        )

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_no_base_url_keeps_openai_default(self) -> None:
        """Without base_url the client keeps the standard OpenAI endpoint."""
        config = SummarizationConfig(provider="openai", model="gpt-5-mini")
        provider = OpenAISummarizationProvider(config)

        assert "api.openai.com" in str(provider._client.base_url)
