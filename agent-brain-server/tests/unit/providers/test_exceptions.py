"""Unit tests for provider exceptions."""

from agent_brain_server.providers.exceptions import (
    AuthenticationError,
    ConfigurationError,
    ModelNotFoundError,
    OllamaConnectionError,
    ProviderError,
    ProviderMismatchError,
    ProviderNotFoundError,
    RateLimitError,
)


class TestProviderError:
    """Tests for base ProviderError."""

    def test_basic_error(self) -> None:
        """Test basic error creation."""
        error = ProviderError("Test message", "test-provider")
        assert "Test message" in str(error)
        assert "test-provider" in str(error)
        assert error.provider == "test-provider"
        assert error.cause is None

    def test_error_with_cause(self) -> None:
        """Test error with cause exception."""
        cause = ValueError("Original error")
        error = ProviderError("Test message", "test-provider", cause=cause)
        assert error.cause is cause


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_configuration_error(self) -> None:
        """Test configuration error."""
        error = ConfigurationError("Invalid config", "test-provider")
        assert isinstance(error, ProviderError)
        assert "Invalid config" in str(error)


class TestAuthenticationError:
    """Tests for AuthenticationError."""

    def test_authentication_error(self) -> None:
        """Test authentication error."""
        error = AuthenticationError("Missing API key", "test-provider")
        assert isinstance(error, ProviderError)
        assert "Missing API key" in str(error)


class TestProviderNotFoundError:
    """Tests for ProviderNotFoundError."""

    def test_provider_not_found(self) -> None:
        """Test provider not found error."""
        error = ProviderNotFoundError("Unknown provider: foo", "foo")
        assert isinstance(error, ProviderError)
        assert "foo" in str(error)


class TestProviderMismatchError:
    """Tests for ProviderMismatchError."""

    def test_provider_mismatch(self) -> None:
        """Test provider mismatch error."""
        error = ProviderMismatchError(
            current_provider="openai",
            current_model="text-embedding-3-large",
            indexed_provider="cohere",
            indexed_model="embed-english-v3.0",
        )
        assert isinstance(error, ProviderError)
        assert "openai" in str(error)
        assert "cohere" in str(error)
        assert "mismatch" in str(error).lower()
        assert error.indexed_provider == "cohere"
        assert error.indexed_model == "embed-english-v3.0"


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_rate_limit_without_retry(self) -> None:
        """Test rate limit error without retry time."""
        error = RateLimitError("test-provider")
        assert isinstance(error, ProviderError)
        assert "Rate limit" in str(error)
        assert error.retry_after is None

    def test_rate_limit_with_retry(self) -> None:
        """Test rate limit error with retry time."""
        error = RateLimitError("test-provider", retry_after=30)
        assert "30" in str(error)
        assert error.retry_after == 30


class TestModelNotFoundError:
    """Tests for ModelNotFoundError."""

    def test_model_not_found_with_available(self) -> None:
        """Test model not found with available models."""
        error = ModelNotFoundError(
            "test-provider",
            "unknown-model",
            available_models=["model-a", "model-b"],
        )
        assert isinstance(error, ProviderError)
        assert "unknown-model" in str(error)
        assert "model-a" in str(error)
        assert error.model == "unknown-model"
        assert error.available_models == ["model-a", "model-b"]

    def test_model_not_found_without_available(self) -> None:
        """Test model not found without available models."""
        error = ModelNotFoundError("test-provider", "unknown-model")
        assert "unknown-model" in str(error)
        assert error.available_models == []


class TestOllamaConnectionError:
    """Tests for OllamaConnectionError."""

    def test_ollama_connection_error(self) -> None:
        """Test Ollama connection error."""
        error = OllamaConnectionError("http://localhost:11434/v1")
        assert isinstance(error, ProviderError)
        assert "Ollama" in str(error)
        assert "localhost:11434" in str(error)
        assert error.base_url == "http://localhost:11434/v1"

    def test_ollama_connection_error_with_cause(self) -> None:
        """Test Ollama connection error with cause."""
        cause = ConnectionError("Connection refused")
        error = OllamaConnectionError("http://localhost:11434/v1", cause=cause)
        assert error.cause is cause
