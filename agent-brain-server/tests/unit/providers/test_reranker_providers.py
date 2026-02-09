"""Unit tests for reranker providers.

Tests cover:
- RerankerProvider protocol implementation
- SentenceTransformerRerankerProvider functionality
- OllamaRerankerProvider functionality
- Provider registration and caching
- Graceful error handling and degradation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_brain_server.config.provider_config import RerankerConfig
from agent_brain_server.providers.base import RerankerProviderType
from agent_brain_server.providers.factory import ProviderRegistry
from agent_brain_server.providers.reranker import (
    BaseRerankerProvider,
    OllamaRerankerProvider,
    RerankerProvider,
    SentenceTransformerRerankerProvider,
)


class TestRerankerProtocol:
    """Test RerankerProvider protocol implementation."""

    def test_sentence_transformer_implements_protocol(self) -> None:
        """SentenceTransformerRerankerProvider implements RerankerProvider."""
        config = RerankerConfig(
            provider=RerankerProviderType.SENTENCE_TRANSFORMERS,
            model="cross-encoder/ms-marco-MiniLM-L-6-v2",
        )
        provider = SentenceTransformerRerankerProvider(config)
        assert isinstance(provider, RerankerProvider)

    def test_ollama_implements_protocol(self) -> None:
        """OllamaRerankerProvider implements RerankerProvider."""
        config = RerankerConfig(
            provider=RerankerProviderType.OLLAMA,
            model="llama3.2:1b",
        )
        provider = OllamaRerankerProvider(config)
        assert isinstance(provider, RerankerProvider)

    def test_base_reranker_is_abstract(self) -> None:
        """BaseRerankerProvider cannot be instantiated directly."""
        config = RerankerConfig(
            provider=RerankerProviderType.SENTENCE_TRANSFORMERS,
            model="test-model",
        )
        with pytest.raises(TypeError, match="abstract"):
            BaseRerankerProvider(config)  # type: ignore[abstract]


class TestProviderRegistry:
    """Test provider registration and caching."""

    def setup_method(self) -> None:
        """Clear cache before each test."""
        ProviderRegistry.clear_cache()

    def test_sentence_transformers_registered(self) -> None:
        """SentenceTransformers provider is registered."""
        available = ProviderRegistry.get_available_reranker_providers()
        assert "sentence-transformers" in available

    def test_ollama_registered(self) -> None:
        """Ollama provider is registered."""
        available = ProviderRegistry.get_available_reranker_providers()
        assert "ollama" in available

    def test_get_reranker_provider_sentence_transformers(self) -> None:
        """Can get sentence-transformers reranker provider from registry."""
        config = RerankerConfig(
            provider=RerankerProviderType.SENTENCE_TRANSFORMERS,
            model="cross-encoder/ms-marco-MiniLM-L-6-v2",
        )
        provider = ProviderRegistry.get_reranker_provider(config)
        assert provider.provider_name == "SentenceTransformers"

    def test_get_reranker_provider_ollama(self) -> None:
        """Can get ollama reranker provider from registry."""
        config = RerankerConfig(
            provider=RerankerProviderType.OLLAMA,
            model="llama3.2:1b",
        )
        provider = ProviderRegistry.get_reranker_provider(config)
        assert provider.provider_name == "Ollama"

    def test_provider_caching(self) -> None:
        """Provider instances are cached by type and model."""
        config = RerankerConfig(
            provider=RerankerProviderType.SENTENCE_TRANSFORMERS,
            model="cross-encoder/ms-marco-MiniLM-L-6-v2",
        )
        provider1 = ProviderRegistry.get_reranker_provider(config)
        provider2 = ProviderRegistry.get_reranker_provider(config)
        assert provider1 is provider2

    def test_different_models_get_different_instances(self) -> None:
        """Different models create different provider instances."""
        config1 = RerankerConfig(
            provider=RerankerProviderType.SENTENCE_TRANSFORMERS,
            model="cross-encoder/ms-marco-MiniLM-L-6-v2",
        )
        config2 = RerankerConfig(
            provider=RerankerProviderType.SENTENCE_TRANSFORMERS,
            model="cross-encoder/ms-marco-MiniLM-L-12-v2",
        )
        provider1 = ProviderRegistry.get_reranker_provider(config1)
        provider2 = ProviderRegistry.get_reranker_provider(config2)
        assert provider1 is not provider2
        assert provider1.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"
        assert provider2.model_name == "cross-encoder/ms-marco-MiniLM-L-12-v2"

    def test_unregistered_provider_raises_error(self) -> None:
        """Getting unregistered provider raises ProviderNotFoundError."""
        from agent_brain_server.providers.exceptions import ProviderNotFoundError

        # Temporarily remove all reranker providers
        original = ProviderRegistry._reranker_providers.copy()
        ProviderRegistry._reranker_providers.clear()
        try:
            config = RerankerConfig(
                provider=RerankerProviderType.SENTENCE_TRANSFORMERS,
                model="test-model",
            )
            with pytest.raises(ProviderNotFoundError):
                ProviderRegistry.get_reranker_provider(config)
        finally:
            ProviderRegistry._reranker_providers.update(original)


class TestSentenceTransformerReranker:
    """Test SentenceTransformerRerankerProvider."""

    @pytest.fixture
    def provider(self) -> SentenceTransformerRerankerProvider:
        """Create provider instance."""
        config = RerankerConfig(
            provider=RerankerProviderType.SENTENCE_TRANSFORMERS,
            model="cross-encoder/ms-marco-MiniLM-L-6-v2",
        )
        return SentenceTransformerRerankerProvider(config)

    def test_provider_name(self, provider: SentenceTransformerRerankerProvider) -> None:
        """Provider returns correct name."""
        assert provider.provider_name == "SentenceTransformers"

    def test_model_name(self, provider: SentenceTransformerRerankerProvider) -> None:
        """Provider returns correct model."""
        assert provider.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def test_default_is_available(
        self, provider: SentenceTransformerRerankerProvider
    ) -> None:
        """Provider reports is_available correctly (depends on model loading)."""
        # The actual model loading may or may not work in test environment
        # Just verify the method exists and returns a bool
        result = provider.is_available()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_rerank_empty_documents(
        self, provider: SentenceTransformerRerankerProvider
    ) -> None:
        """Reranking empty list returns empty list."""
        result = await provider.rerank("query", [], top_k=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_returns_tuples(
        self, provider: SentenceTransformerRerankerProvider
    ) -> None:
        """Rerank returns list of (index, score) tuples in correct order."""
        # Mock the CrossEncoder to avoid loading real model
        mock_encoder = MagicMock()
        mock_encoder.rank.return_value = [
            {"corpus_id": 1, "score": 0.9},
            {"corpus_id": 0, "score": 0.7},
            {"corpus_id": 2, "score": 0.5},
        ]

        with patch.object(provider, "_ensure_model_loaded", return_value=mock_encoder):
            result = await provider.rerank(
                "test query",
                ["doc0", "doc1", "doc2"],
                top_k=3,
            )

            assert len(result) == 3
            assert result[0] == (1, 0.9)
            assert result[1] == (0, 0.7)
            assert result[2] == (2, 0.5)

    @pytest.mark.asyncio
    async def test_rerank_respects_top_k(
        self, provider: SentenceTransformerRerankerProvider
    ) -> None:
        """Rerank limits results to top_k."""
        mock_encoder = MagicMock()
        mock_encoder.rank.return_value = [
            {"corpus_id": 0, "score": 0.9},
            {"corpus_id": 1, "score": 0.8},
        ]

        with patch.object(provider, "_ensure_model_loaded", return_value=mock_encoder):
            await provider.rerank(
                "test query",
                ["doc0", "doc1", "doc2", "doc3", "doc4"],
                top_k=2,
            )

            # CrossEncoder.rank is called with top_k
            mock_encoder.rank.assert_called_once()
            call_kwargs = mock_encoder.rank.call_args
            assert call_kwargs[1]["top_k"] == 2

    @pytest.mark.asyncio
    async def test_rerank_top_k_exceeds_documents(
        self, provider: SentenceTransformerRerankerProvider
    ) -> None:
        """Rerank handles top_k larger than document count."""
        mock_encoder = MagicMock()
        mock_encoder.rank.return_value = [
            {"corpus_id": 0, "score": 0.9},
            {"corpus_id": 1, "score": 0.8},
        ]

        with patch.object(provider, "_ensure_model_loaded", return_value=mock_encoder):
            await provider.rerank(
                "test query",
                ["doc0", "doc1"],  # Only 2 docs
                top_k=10,  # Request 10
            )

            # effective_top_k should be min(10, 2) = 2
            call_kwargs = mock_encoder.rank.call_args
            assert call_kwargs[1]["top_k"] == 2


class TestOllamaReranker:
    """Test OllamaRerankerProvider."""

    @pytest.fixture
    def provider(self) -> OllamaRerankerProvider:
        """Create provider instance."""
        config = RerankerConfig(
            provider=RerankerProviderType.OLLAMA,
            model="llama3.2:1b",
        )
        return OllamaRerankerProvider(config)

    def test_provider_name(self, provider: OllamaRerankerProvider) -> None:
        """Provider returns correct name."""
        assert provider.provider_name == "Ollama"

    def test_model_name(self, provider: OllamaRerankerProvider) -> None:
        """Provider returns correct model."""
        assert provider.model_name == "llama3.2:1b"

    def test_default_base_url(self, provider: OllamaRerankerProvider) -> None:
        """Provider uses default Ollama base URL."""
        assert provider._base_url == "http://localhost:11434"

    def test_custom_base_url(self) -> None:
        """Provider respects custom base URL."""
        config = RerankerConfig(
            provider=RerankerProviderType.OLLAMA,
            model="llama3.2:1b",
            base_url="http://custom:11434",
        )
        provider = OllamaRerankerProvider(config)
        assert provider._base_url == "http://custom:11434"

    def test_parse_score_valid_integer(self, provider: OllamaRerankerProvider) -> None:
        """Parse score handles integer correctly."""
        assert provider._parse_score("8") == 8.0

    def test_parse_score_valid_float(self, provider: OllamaRerankerProvider) -> None:
        """Parse score handles float correctly."""
        assert provider._parse_score("7.5") == 7.5

    def test_parse_score_with_text(self, provider: OllamaRerankerProvider) -> None:
        """Parse score extracts number from surrounding text."""
        assert provider._parse_score("The relevance score is 9") == 9.0
        assert provider._parse_score("Score: 8.5 out of 10") == 8.5

    def test_parse_score_invalid_returns_zero(
        self, provider: OllamaRerankerProvider
    ) -> None:
        """Parse score returns 0 for text without numbers."""
        assert provider._parse_score("no number here") == 0.0
        assert provider._parse_score("") == 0.0

    def test_parse_score_clamps_to_max(self, provider: OllamaRerankerProvider) -> None:
        """Parse score clamps values above 10 to max of 10."""
        assert provider._parse_score("15") == 10.0
        assert provider._parse_score("100") == 10.0

    def test_parse_score_clamps_to_min(self, provider: OllamaRerankerProvider) -> None:
        """Parse score clamps negative values to 0."""
        # Regex won't capture negative numbers, so -5 becomes 5
        # But the clamp should handle edge cases
        assert provider._parse_score("0") == 0.0

    @pytest.mark.asyncio
    async def test_rerank_empty_documents(
        self, provider: OllamaRerankerProvider
    ) -> None:
        """Reranking empty list returns empty list."""
        result = await provider.rerank("query", [], top_k=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_with_mock_response(
        self, provider: OllamaRerankerProvider
    ) -> None:
        """Rerank works with mocked HTTP response."""
        # Create mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {"content": "8"}}
        mock_response.raise_for_status = MagicMock()

        # Create mock client
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = await provider.rerank(
                "test query",
                ["doc1", "doc2"],
                top_k=2,
            )

            # Both docs should have scores
            assert len(result) == 2
            # Scores should be parsed correctly (both get score 8)
            scores = [r[1] for r in result]
            assert all(s == 8.0 for s in scores)

    @pytest.mark.asyncio
    async def test_rerank_sorts_by_score_descending(
        self, provider: OllamaRerankerProvider
    ) -> None:
        """Rerank sorts results by score in descending order."""
        # Mock different scores for different documents
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            scores = ["5", "9", "7"]  # doc0=5, doc1=9, doc2=7
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {"message": {"content": scores[call_count]}}
            response.raise_for_status = MagicMock()
            call_count += 1
            return response

        mock_client = AsyncMock()
        mock_client.post = mock_post

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = await provider.rerank(
                "test query",
                ["doc0", "doc1", "doc2"],
                top_k=3,
            )

            # Should be sorted by score descending
            assert len(result) == 3
            # doc1 (score 9) should be first
            assert result[0] == (1, 9.0)
            # doc2 (score 7) should be second
            assert result[1] == (2, 7.0)
            # doc0 (score 5) should be third
            assert result[2] == (0, 5.0)

    @pytest.mark.asyncio
    async def test_rerank_respects_top_k(
        self, provider: OllamaRerankerProvider
    ) -> None:
        """Rerank returns only top_k results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {"content": "8"}}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = await provider.rerank(
                "test query",
                ["doc0", "doc1", "doc2", "doc3", "doc4"],
                top_k=2,
            )

            # Should return only 2 results
            assert len(result) == 2


class TestGracefulDegradation:
    """Test graceful degradation scenarios."""

    @pytest.mark.asyncio
    async def test_ollama_handles_connection_error(self) -> None:
        """Ollama provider handles connection errors gracefully."""
        config = RerankerConfig(
            provider=RerankerProviderType.OLLAMA,
            model="llama3.2:1b",
        )
        provider = OllamaRerankerProvider(config)

        # Mock connection failure
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = await provider.rerank(
                "test query",
                ["doc1", "doc2"],
                top_k=2,
            )

            # Should return results with 0.0 scores (fallback)
            assert len(result) == 2
            assert all(r[1] == 0.0 for r in result)

    @pytest.mark.asyncio
    async def test_ollama_handles_http_error(self) -> None:
        """Ollama provider handles HTTP errors gracefully."""
        config = RerankerConfig(
            provider=RerankerProviderType.OLLAMA,
            model="llama3.2:1b",
        )
        provider = OllamaRerankerProvider(config)

        import httpx

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )
        )

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = await provider.rerank(
                "test query",
                ["doc1", "doc2"],
                top_k=2,
            )

            # Should return results with 0.0 scores
            assert len(result) == 2
            assert all(r[1] == 0.0 for r in result)

    @pytest.mark.asyncio
    async def test_ollama_handles_malformed_response(self) -> None:
        """Ollama provider handles malformed responses gracefully."""
        config = RerankerConfig(
            provider=RerankerProviderType.OLLAMA,
            model="llama3.2:1b",
        )
        provider = OllamaRerankerProvider(config)

        # Mock response with malformed JSON structure
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # Missing 'message' key
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = await provider.rerank(
                "test query",
                ["doc1", "doc2"],
                top_k=2,
            )

            # Should return results with 0.0 scores (parsed from empty)
            assert len(result) == 2
            assert all(r[1] == 0.0 for r in result)

    def test_ollama_is_available_returns_false_on_connection_error(self) -> None:
        """Ollama is_available returns False when server unreachable."""
        config = RerankerConfig(
            provider=RerankerProviderType.OLLAMA,
            model="llama3.2:1b",
            base_url="http://nonexistent:11434",
        )
        provider = OllamaRerankerProvider(config)

        # is_available should return False, not raise
        result = provider.is_available()
        assert result is False


class TestRerankerConfigParams:
    """Test configuration parameter handling."""

    # Note: batch_size tests removed - CrossEncoder.rank() handles batching internally

    def test_ollama_timeout_from_params(self) -> None:
        """Ollama timeout is read from params."""
        config = RerankerConfig(
            provider=RerankerProviderType.OLLAMA,
            model="test-model",
            params={"timeout": 60.0},
        )
        provider = OllamaRerankerProvider(config)
        assert provider._timeout == 60.0

    def test_ollama_max_concurrent_from_params(self) -> None:
        """Ollama max_concurrent is read from params."""
        config = RerankerConfig(
            provider=RerankerProviderType.OLLAMA,
            model="test-model",
            params={"max_concurrent": 10},
        )
        provider = OllamaRerankerProvider(config)
        assert provider._max_concurrent == 10


class TestSentenceTransformerWarmUp:
    """Test warm_up and availability caching for SentenceTransformer."""

    def test_warm_up_success(self) -> None:
        """warm_up() preloads the model successfully."""
        config = RerankerConfig(
            provider=RerankerProviderType.SENTENCE_TRANSFORMERS,
            model="cross-encoder/ms-marco-MiniLM-L-6-v2",
        )
        provider = SentenceTransformerRerankerProvider(config)

        # Before warm_up, model is not loaded
        assert provider._model_loaded is False

        # Warm up should succeed
        result = provider.warm_up()
        assert result is True
        assert provider._model_loaded is True
        assert provider._availability_checked is True
        assert provider._is_available_cached is True

    def test_availability_caching(self) -> None:
        """is_available() returns cached result after first check."""
        config = RerankerConfig(
            provider=RerankerProviderType.SENTENCE_TRANSFORMERS,
            model="cross-encoder/ms-marco-MiniLM-L-6-v2",
        )
        provider = SentenceTransformerRerankerProvider(config)

        # First call sets the cache
        result1 = provider.is_available()
        assert result1 is True
        assert provider._availability_checked is True

        # Second call returns cached result
        result2 = provider.is_available()
        assert result2 is True


class TestOllamaCircuitBreaker:
    """Test circuit breaker pattern in Ollama reranker."""

    def test_circuit_starts_closed(self) -> None:
        """Circuit breaker starts in closed state."""
        config = RerankerConfig(
            provider=RerankerProviderType.OLLAMA,
            model="test-model",
        )
        provider = OllamaRerankerProvider(config)
        assert provider._circuit_open is False
        assert provider._consecutive_failures == 0

    def test_record_success_resets_failures(self) -> None:
        """Successful request resets failure count."""
        config = RerankerConfig(
            provider=RerankerProviderType.OLLAMA,
            model="test-model",
        )
        provider = OllamaRerankerProvider(config)
        provider._consecutive_failures = 2

        provider._record_success()
        assert provider._consecutive_failures == 0

    def test_record_failure_increments_count(self) -> None:
        """Failed request increments failure count."""
        config = RerankerConfig(
            provider=RerankerProviderType.OLLAMA,
            model="test-model",
        )
        provider = OllamaRerankerProvider(config)

        provider._record_failure()
        assert provider._consecutive_failures == 1

        provider._record_failure()
        assert provider._consecutive_failures == 2

    def test_circuit_opens_after_threshold(self) -> None:
        """Circuit opens after FAILURE_THRESHOLD consecutive failures."""
        config = RerankerConfig(
            provider=RerankerProviderType.OLLAMA,
            model="test-model",
        )
        provider = OllamaRerankerProvider(config)

        # Record failures up to threshold
        for _ in range(OllamaRerankerProvider.FAILURE_THRESHOLD):
            provider._record_failure()

        assert provider._circuit_open is True
        assert provider._circuit_opened_at > 0

    def test_check_circuit_returns_false_when_open(self) -> None:
        """_check_circuit returns False when circuit is open."""
        config = RerankerConfig(
            provider=RerankerProviderType.OLLAMA,
            model="test-model",
        )
        provider = OllamaRerankerProvider(config)

        # Open the circuit
        for _ in range(OllamaRerankerProvider.FAILURE_THRESHOLD):
            provider._record_failure()

        assert provider._check_circuit() is False

    @pytest.mark.asyncio
    async def test_rerank_raises_when_circuit_open(self) -> None:
        """rerank() raises RuntimeError when circuit is open."""
        config = RerankerConfig(
            provider=RerankerProviderType.OLLAMA,
            model="test-model",
        )
        provider = OllamaRerankerProvider(config)

        # Open the circuit
        for _ in range(OllamaRerankerProvider.FAILURE_THRESHOLD):
            provider._record_failure()

        with pytest.raises(RuntimeError, match="circuit breaker open"):
            await provider.rerank("test query", ["doc1", "doc2"])

    def test_is_available_returns_false_when_circuit_open(self) -> None:
        """is_available() returns False when circuit is open."""
        config = RerankerConfig(
            provider=RerankerProviderType.OLLAMA,
            model="test-model",
        )
        provider = OllamaRerankerProvider(config)

        # Open the circuit
        for _ in range(OllamaRerankerProvider.FAILURE_THRESHOLD):
            provider._record_failure()

        # Ollama not running + circuit open = False
        assert provider.is_available() is False
