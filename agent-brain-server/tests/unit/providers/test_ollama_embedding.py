"""Unit tests for Ollama embedding provider."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_brain_server.config.provider_config import EmbeddingConfig
from agent_brain_server.providers.embedding.ollama import (
    OLLAMA_MODEL_DIMENSIONS,
    OllamaEmbeddingProvider,
)
from agent_brain_server.providers.exceptions import OllamaConnectionError


class TestOllamaEmbeddingProvider:
    """Tests for OllamaEmbeddingProvider."""

    def test_initialization(self) -> None:
        """Test provider initialization."""
        config = EmbeddingConfig(provider="ollama", model="nomic-embed-text")
        provider = OllamaEmbeddingProvider(config)

        assert provider.provider_name == "Ollama"
        assert provider.model_name == "nomic-embed-text"

    def test_initialization_no_api_key_needed(self) -> None:
        """Test Ollama doesn't require API key."""
        config = EmbeddingConfig(provider="ollama", model="nomic-embed-text")
        # Should not raise even without API key
        provider = OllamaEmbeddingProvider(config)
        assert provider is not None

    def test_default_base_url(self) -> None:
        """Test default base URL for Ollama."""
        config = EmbeddingConfig(provider="ollama")
        provider = OllamaEmbeddingProvider(config)
        assert provider._base_url == "http://localhost:11434/v1"

    def test_custom_base_url(self) -> None:
        """Test custom base URL."""
        config = EmbeddingConfig(
            provider="ollama",
            base_url="http://remote:11434/v1",
        )
        provider = OllamaEmbeddingProvider(config)
        assert provider._base_url == "http://remote:11434/v1"

    def test_get_dimensions(self) -> None:
        """Test dimension retrieval for known models."""
        config = EmbeddingConfig(provider="ollama", model="nomic-embed-text")
        provider = OllamaEmbeddingProvider(config)
        assert provider.get_dimensions() == 768

        config_large = EmbeddingConfig(provider="ollama", model="mxbai-embed-large")
        provider_large = OllamaEmbeddingProvider(config_large)
        assert provider_large.get_dimensions() == 1024

    def test_get_dimensions_unknown_model(self) -> None:
        """Test default dimensions for unknown models."""
        config = EmbeddingConfig(provider="ollama", model="unknown-model")
        provider = OllamaEmbeddingProvider(config)
        assert provider.get_dimensions() == 768  # Default

    @pytest.mark.asyncio
    async def test_embed_text(self) -> None:
        """Test single text embedding."""
        config = EmbeddingConfig(provider="ollama")
        provider = OllamaEmbeddingProvider(config)

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        provider._client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await provider.embed_text("test text")
        assert result == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_embed_text_connection_error(self) -> None:
        """Test connection error handling."""
        config = EmbeddingConfig(provider="ollama")
        provider = OllamaEmbeddingProvider(config)

        provider._client.embeddings.create = AsyncMock(
            side_effect=Exception("Connection refused"),
        )

        with pytest.raises(OllamaConnectionError) as exc_info:
            await provider.embed_text("test text")

        assert "Ollama" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_embed_batch(self) -> None:
        """Test batch embedding."""
        config = EmbeddingConfig(provider="ollama")
        provider = OllamaEmbeddingProvider(config)

        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1, 0.2]),
            MagicMock(embedding=[0.3, 0.4]),
        ]
        provider._client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await provider._embed_batch(["text1", "text2"])
        assert result == [[0.1, 0.2], [0.3, 0.4]]

    @pytest.mark.asyncio
    async def test_health_check_success(self) -> None:
        """Test successful health check."""
        config = EmbeddingConfig(provider="ollama")
        provider = OllamaEmbeddingProvider(config)

        provider._client.models.list = AsyncMock(return_value=[])
        result = await provider.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self) -> None:
        """Test failed health check."""
        config = EmbeddingConfig(provider="ollama")
        provider = OllamaEmbeddingProvider(config)

        provider._client.models.list = AsyncMock(side_effect=Exception("Failed"))
        result = await provider.health_check()
        assert result is False


class TestModelDimensions:
    """Tests for Ollama model dimension mappings."""

    def test_known_models_have_dimensions(self) -> None:
        """Test that known models have dimension mappings."""
        assert "nomic-embed-text" in OLLAMA_MODEL_DIMENSIONS
        assert "mxbai-embed-large" in OLLAMA_MODEL_DIMENSIONS
        assert "all-minilm" in OLLAMA_MODEL_DIMENSIONS

    def test_dimension_values(self) -> None:
        """Test dimension values are correct."""
        assert OLLAMA_MODEL_DIMENSIONS["nomic-embed-text"] == 768
        assert OLLAMA_MODEL_DIMENSIONS["mxbai-embed-large"] == 1024
        assert OLLAMA_MODEL_DIMENSIONS["all-minilm"] == 384
