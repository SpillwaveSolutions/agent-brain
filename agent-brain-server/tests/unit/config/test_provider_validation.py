"""Tests for provider configuration validation with severity levels."""

import os
from unittest.mock import patch

from agent_brain_server.config.provider_config import (
    EmbeddingConfig,
    ProviderSettings,
    SummarizationConfig,
    ValidationError,
    ValidationSeverity,
    has_critical_errors,
    validate_provider_config,
)
from agent_brain_server.providers.base import (
    EmbeddingProviderType,
    SummarizationProviderType,
)


class TestValidationError:
    """Tests for ValidationError class."""

    def test_critical_error_string(self) -> None:
        """Test CRITICAL error string representation."""
        error = ValidationError(
            message="Missing API key",
            severity=ValidationSeverity.CRITICAL,
            provider_type="embedding",
            field="api_key",
        )
        result = str(error)
        assert "[CRITICAL]" in result
        assert "embedding" in result
        assert "Missing API key" in result

    def test_warning_error_string(self) -> None:
        """Test WARNING error string representation."""
        error = ValidationError(
            message="Provider may be unavailable",
            severity=ValidationSeverity.WARNING,
            provider_type="summarization",
        )
        result = str(error)
        assert "[WARNING]" in result
        assert "summarization" in result


class TestValidateProviderConfig:
    """Tests for validate_provider_config function."""

    def test_valid_config_with_env_keys(self) -> None:
        """Test validation passes when env vars are set."""
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test-key",
                "ANTHROPIC_API_KEY": "sk-ant-test",
            },
        ):
            settings = ProviderSettings()
            errors = validate_provider_config(settings)
            assert len(errors) == 0

    def test_missing_embedding_key_is_critical(self) -> None:
        """Test missing embedding API key is CRITICAL severity."""
        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "sk-ant-test",
            },
            clear=True,
        ):
            # Clear OPENAI_API_KEY
            os.environ.pop("OPENAI_API_KEY", None)

            settings = ProviderSettings(
                embedding=EmbeddingConfig(
                    provider=EmbeddingProviderType.OPENAI,
                    api_key=None,
                    api_key_env="OPENAI_API_KEY",
                ),
            )
            errors = validate_provider_config(settings)

            embedding_errors = [e for e in errors if e.provider_type == "embedding"]
            assert len(embedding_errors) == 1
            assert embedding_errors[0].severity == ValidationSeverity.CRITICAL

    def test_ollama_no_key_required(self) -> None:
        """Test Ollama provider doesn't require API key."""
        settings = ProviderSettings(
            embedding=EmbeddingConfig(
                provider=EmbeddingProviderType.OLLAMA,
                model="nomic-embed-text",
            ),
            summarization=SummarizationConfig(
                provider=SummarizationProviderType.OLLAMA,
                model="llama3.2",
            ),
        )
        errors = validate_provider_config(settings)
        # Should have no CRITICAL errors for missing keys
        critical = [e for e in errors if e.severity == ValidationSeverity.CRITICAL]
        assert len(critical) == 0


class TestHasCriticalErrors:
    """Tests for has_critical_errors function."""

    def test_returns_true_with_critical(self) -> None:
        """Test returns True when critical error present."""
        errors = [
            ValidationError("warn", ValidationSeverity.WARNING, "test"),
            ValidationError("crit", ValidationSeverity.CRITICAL, "test"),
        ]
        assert has_critical_errors(errors) is True

    def test_returns_false_with_only_warnings(self) -> None:
        """Test returns False when only warnings present."""
        errors = [
            ValidationError("warn1", ValidationSeverity.WARNING, "test"),
            ValidationError("warn2", ValidationSeverity.WARNING, "test"),
        ]
        assert has_critical_errors(errors) is False

    def test_returns_false_with_empty_list(self) -> None:
        """Test returns False with empty list."""
        assert has_critical_errors([]) is False
