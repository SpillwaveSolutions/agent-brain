"""Unit tests for OpenAI embedding provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_brain_server.config.provider_config import EmbeddingConfig
from agent_brain_server.providers.embedding.openai import (
    OPENAI_MODEL_DIMENSIONS,
    OpenAIEmbeddingProvider,
)
from agent_brain_server.providers.exceptions import AuthenticationError, ProviderError


class TestOpenAIEmbeddingProvider:
    """Tests for OpenAIEmbeddingProvider."""

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_initialization(self) -> None:
        """Test provider initialization."""
        config = EmbeddingConfig(provider="openai", model="text-embedding-3-large")
        provider = OpenAIEmbeddingProvider(config)

        assert provider.provider_name == "OpenAI"
        assert provider.model_name == "text-embedding-3-large"

    def test_initialization_missing_key(self) -> None:
        """Test error when API key is missing."""
        with patch.dict("os.environ", {}, clear=True):
            config = EmbeddingConfig(
                provider="openai",
                api_key_env="MISSING_KEY",
            )
            with pytest.raises(AuthenticationError):
                OpenAIEmbeddingProvider(config)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_get_dimensions(self) -> None:
        """Test dimension retrieval for known models."""
        config = EmbeddingConfig(provider="openai", model="text-embedding-3-large")
        provider = OpenAIEmbeddingProvider(config)
        assert provider.get_dimensions() == 3072

        config_small = EmbeddingConfig(
            provider="openai", model="text-embedding-3-small"
        )
        provider_small = OpenAIEmbeddingProvider(config_small)
        assert provider_small.get_dimensions() == 1536

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_get_dimensions_with_override(self) -> None:
        """Test dimension override via params."""
        config = EmbeddingConfig(
            provider="openai",
            model="text-embedding-3-large",
            params={"dimensions": 1024},
        )
        provider = OpenAIEmbeddingProvider(config)
        assert provider.get_dimensions() == 1024

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    async def test_embed_text(self) -> None:
        """Test single text embedding."""
        config = EmbeddingConfig(provider="openai")
        provider = OpenAIEmbeddingProvider(config)

        # Mock the OpenAI client
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        provider._client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await provider.embed_text("test text")

        assert result == [0.1, 0.2, 0.3]
        provider._client.embeddings.create.assert_called_once()

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    async def test_embed_text_error(self) -> None:
        """Test error handling in embed_text."""
        config = EmbeddingConfig(provider="openai")
        provider = OpenAIEmbeddingProvider(config)

        provider._client.embeddings.create = AsyncMock(
            side_effect=Exception("API error"),
        )

        with pytest.raises(ProviderError) as exc_info:
            await provider.embed_text("test text")

        assert "API error" in str(exc_info.value)
        assert exc_info.value.provider == "OpenAI"

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    async def test_embed_batch(self) -> None:
        """Test batch embedding."""
        config = EmbeddingConfig(provider="openai")
        provider = OpenAIEmbeddingProvider(config)

        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1, 0.2]),
            MagicMock(embedding=[0.3, 0.4]),
        ]
        provider._client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await provider._embed_batch(["text1", "text2"])

        assert result == [[0.1, 0.2], [0.3, 0.4]]

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    async def test_embed_texts_with_progress(self) -> None:
        """Test batch embedding with progress callback."""
        config = EmbeddingConfig(
            provider="openai",
            params={"batch_size": 2},
        )
        provider = OpenAIEmbeddingProvider(config)

        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1]),
            MagicMock(embedding=[0.2]),
        ]
        provider._client.embeddings.create = AsyncMock(return_value=mock_response)

        progress_calls: list[tuple[int, int]] = []

        async def progress_callback(processed: int, total: int) -> None:
            progress_calls.append((processed, total))

        result = await provider.embed_texts(
            ["text1", "text2", "text3", "text4"],
            progress_callback=progress_callback,
        )

        # Should have multiple progress calls
        assert len(progress_calls) > 0
        # Should have embeddings for all texts
        assert len(result) == 4


class TestModelDimensions:
    """Tests for model dimension mappings."""

    def test_known_models_have_dimensions(self) -> None:
        """Test that known models have dimension mappings."""
        assert "text-embedding-3-large" in OPENAI_MODEL_DIMENSIONS
        assert "text-embedding-3-small" in OPENAI_MODEL_DIMENSIONS
        assert "text-embedding-ada-002" in OPENAI_MODEL_DIMENSIONS

    def test_dimension_values(self) -> None:
        """Test dimension values are correct."""
        assert OPENAI_MODEL_DIMENSIONS["text-embedding-3-large"] == 3072
        assert OPENAI_MODEL_DIMENSIONS["text-embedding-3-small"] == 1536
        assert OPENAI_MODEL_DIMENSIONS["text-embedding-ada-002"] == 1536
