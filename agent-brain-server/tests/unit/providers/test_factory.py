"""Unit tests for provider factory."""

from unittest.mock import MagicMock, patch

import pytest

from agent_brain_server.config.provider_config import (
    EmbeddingConfig,
    SummarizationConfig,
)
from agent_brain_server.providers.exceptions import ProviderNotFoundError
from agent_brain_server.providers.factory import ProviderRegistry


class TestProviderRegistry:
    """Tests for ProviderRegistry."""

    def setup_method(self) -> None:
        """Clear cache before each test."""
        ProviderRegistry.clear_cache()

    def test_register_embedding_provider(self) -> None:
        """Test embedding provider registration."""
        mock_class = MagicMock()
        ProviderRegistry.register_embedding_provider("test-embed", mock_class)
        assert "test-embed" in ProviderRegistry.get_available_embedding_providers()

    def test_register_summarization_provider(self) -> None:
        """Test summarization provider registration."""
        mock_class = MagicMock()
        ProviderRegistry.register_summarization_provider("test-summ", mock_class)
        assert "test-summ" in ProviderRegistry.get_available_summarization_providers()

    def test_get_embedding_provider_not_found(self) -> None:
        """Test error when embedding provider not registered."""
        config = EmbeddingConfig(provider="openai")
        # Remove the openai provider temporarily to test not found
        original = ProviderRegistry._embedding_providers.pop("openai", None)
        try:
            with pytest.raises(ProviderNotFoundError) as exc_info:
                ProviderRegistry.get_embedding_provider(config)
            assert "openai" in str(exc_info.value).lower()
        finally:
            if original:
                ProviderRegistry._embedding_providers["openai"] = original

    def test_get_summarization_provider_not_found(self) -> None:
        """Test error when summarization provider not registered."""
        config = SummarizationConfig(provider="anthropic")
        # Remove the anthropic provider temporarily to test not found
        original = ProviderRegistry._summarization_providers.pop("anthropic", None)
        try:
            with pytest.raises(ProviderNotFoundError) as exc_info:
                ProviderRegistry.get_summarization_provider(config)
            assert "anthropic" in str(exc_info.value).lower()
        finally:
            if original:
                ProviderRegistry._summarization_providers["anthropic"] = original

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_get_embedding_provider_caches_instance(self) -> None:
        """Test that providers are cached."""
        config = EmbeddingConfig(provider="openai", model="text-embedding-3-large")
        # Get provider twice
        provider1 = ProviderRegistry.get_embedding_provider(config)
        provider2 = ProviderRegistry.get_embedding_provider(config)
        # Should be same instance
        assert provider1 is provider2

    def test_clear_cache(self) -> None:
        """Test cache clearing."""
        # Add something to cache
        ProviderRegistry._instances["test"] = "value"
        # Clear cache
        ProviderRegistry.clear_cache()
        # Verify empty
        assert ProviderRegistry._instances == {}

    def test_get_available_providers(self) -> None:
        """Test listing available providers."""
        # Built-in providers should be registered
        embedding_providers = ProviderRegistry.get_available_embedding_providers()
        summarization_providers = (
            ProviderRegistry.get_available_summarization_providers()
        )

        # Should have OpenAI at minimum (registered by import)
        assert "openai" in embedding_providers
        assert "ollama" in embedding_providers
        assert "cohere" in embedding_providers

        assert "anthropic" in summarization_providers
        assert "openai" in summarization_providers
        assert "gemini" in summarization_providers
        assert "grok" in summarization_providers
        assert "ollama" in summarization_providers

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_different_models_get_different_instances(self) -> None:
        """Test that different models create different instances."""
        config1 = EmbeddingConfig(provider="openai", model="text-embedding-3-large")
        config2 = EmbeddingConfig(provider="openai", model="text-embedding-3-small")

        provider1 = ProviderRegistry.get_embedding_provider(config1)
        provider2 = ProviderRegistry.get_embedding_provider(config2)

        # Should be different instances
        assert provider1 is not provider2
        assert provider1.model_name == "text-embedding-3-large"
        assert provider2.model_name == "text-embedding-3-small"
