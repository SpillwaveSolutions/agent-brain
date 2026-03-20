"""Unit tests for Ollama embedding provider."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

from agent_brain_server.config.provider_config import EmbeddingConfig
from agent_brain_server.providers.embedding.ollama import (
    OLLAMA_MODEL_DIMENSIONS,
    OllamaEmbeddingProvider,
)
from agent_brain_server.providers.exceptions import OllamaConnectionError, ProviderError


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


class TestOllamaRetryLogic:
    """Tests for retry/backoff behavior in Ollama provider."""

    @staticmethod
    def _mock_batch_response() -> MagicMock:
        response = MagicMock()
        response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        return response

    @pytest.mark.asyncio
    async def test_embed_batch_retries_on_broken_pipe(self) -> None:
        """_embed_batch retries broken pipe and succeeds on second attempt."""
        config = EmbeddingConfig(provider="ollama")
        provider = OllamaEmbeddingProvider(config)
        provider._client.embeddings.create = AsyncMock(
            side_effect=[BrokenPipeError("Broken pipe"), self._mock_batch_response()]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await provider._embed_batch(["text"])

        assert result == [[0.1, 0.2, 0.3]]
        assert provider._client.embeddings.create.call_count == 2
        mock_sleep.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_embed_batch_raises_after_retries_exhausted(self) -> None:
        """_embed_batch raises ProviderError when retries are exhausted."""
        config = EmbeddingConfig(
            provider="ollama", params={"max_retries": 3}
        )
        provider = OllamaEmbeddingProvider(config)
        provider._client.embeddings.create = AsyncMock(
            side_effect=BrokenPipeError("Broken pipe")
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(ProviderError):
                await provider._embed_batch(["text"])

        assert provider._client.embeddings.create.call_count == 4
        assert mock_sleep.call_args_list == [call(1), call(2), call(4)]

    @pytest.mark.asyncio
    async def test_connection_refused_raises_immediately(self) -> None:
        """ConnectionRefusedError raises OllamaConnectionError without retry."""
        config = EmbeddingConfig(provider="ollama")
        provider = OllamaEmbeddingProvider(config)
        provider._client.embeddings.create = AsyncMock(
            side_effect=ConnectionRefusedError("Connection refused")
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(OllamaConnectionError):
                await provider._embed_batch(["text"])

        assert provider._client.embeddings.create.call_count == 1
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_httpx_connect_error_refused_raises_immediately(self) -> None:
        """httpx ConnectError with refused message raises immediately."""
        config = EmbeddingConfig(provider="ollama")
        provider = OllamaEmbeddingProvider(config)
        request = httpx.Request("POST", "http://localhost:11434/v1/embeddings")
        provider._client.embeddings.create = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused", request=request)
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(OllamaConnectionError):
                await provider._embed_batch(["text"])

        assert provider._client.embeddings.create.call_count == 1
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_model_not_found_not_retried(self) -> None:
        """Model not found errors should not be retried."""
        config = EmbeddingConfig(provider="ollama")
        provider = OllamaEmbeddingProvider(config)
        provider._client.embeddings.create = AsyncMock(
            side_effect=Exception("model not found")
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(ProviderError):
                await provider._embed_batch(["text"])

        assert provider._client.embeddings.create.call_count == 1
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_embed_batch_backoff_sequence(self) -> None:
        """Retries use exponential backoff sequence 1, 2, 4."""
        config = EmbeddingConfig(
            provider="ollama", params={"max_retries": 3}
        )
        provider = OllamaEmbeddingProvider(config)
        provider._client.embeddings.create = AsyncMock(
            side_effect=BrokenPipeError("Broken pipe")
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(ProviderError):
                await provider._embed_batch(["text"])

        assert mock_sleep.call_args_list == [call(1), call(2), call(4)]

    @pytest.mark.asyncio
    async def test_request_delay_sleep_after_successful_batch(self) -> None:
        """request_delay_ms causes post-batch sleep after success."""
        config = EmbeddingConfig(
            provider="ollama", params={"request_delay_ms": 100}
        )
        provider = OllamaEmbeddingProvider(config)
        provider._client.embeddings.create = AsyncMock(
            return_value=self._mock_batch_response()
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await provider._embed_batch(["text"])

        mock_sleep.assert_called_once_with(0.1)

    def test_request_delay_invalid_string_raises_value_error(self) -> None:
        """Invalid request_delay_ms value raises ValueError at construction."""
        config = EmbeddingConfig(
            provider="ollama", params={"request_delay_ms": "200ms"}
        )

        with pytest.raises(ValueError):
            OllamaEmbeddingProvider(config)

    def test_default_batch_size_is_10(self) -> None:
        """Ollama default batch size should be 10."""
        config = EmbeddingConfig(provider="ollama")
        provider = OllamaEmbeddingProvider(config)
        assert provider._batch_size == 10

    @pytest.mark.asyncio
    async def test_max_retries_zero_fails_immediately(self) -> None:
        """max_retries=0 should fail on first retryable error with no sleep."""
        config = EmbeddingConfig(
            provider="ollama", params={"max_retries": 0}
        )
        provider = OllamaEmbeddingProvider(config)
        provider._client.embeddings.create = AsyncMock(
            side_effect=BrokenPipeError("Broken pipe")
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(ProviderError):
                await provider._embed_batch(["text"])

        assert provider._client.embeddings.create.call_count == 1
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_embed_text_retries_on_broken_pipe(self) -> None:
        """embed_text retries broken pipe and succeeds on second attempt."""
        config = EmbeddingConfig(provider="ollama")
        provider = OllamaEmbeddingProvider(config)
        response = MagicMock()
        response.data = [MagicMock(embedding=[0.4, 0.5, 0.6])]
        provider._client.embeddings.create = AsyncMock(
            side_effect=[BrokenPipeError("Broken pipe"), response]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await provider.embed_text("text")

        assert result == [0.4, 0.5, 0.6]
        assert provider._client.embeddings.create.call_count == 2
        mock_sleep.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_embed_text_connection_refused_raises_immediately(self) -> None:
        """embed_text raises OllamaConnectionError immediately on refused."""
        config = EmbeddingConfig(provider="ollama")
        provider = OllamaEmbeddingProvider(config)
        provider._client.embeddings.create = AsyncMock(
            side_effect=ConnectionRefusedError("Connection refused")
        )

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(OllamaConnectionError):
                await provider.embed_text("text")

        assert provider._client.embeddings.create.call_count == 1
        mock_sleep.assert_not_called()
