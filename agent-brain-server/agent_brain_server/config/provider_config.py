"""Provider configuration models and YAML loader.

This module provides Pydantic models for embedding and summarization
provider configuration, and functions to load configuration from YAML files.
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from agent_brain_server.providers.base import (
    EmbeddingProviderType,
    RerankerProviderType,
    SummarizationProviderType,
)

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    """Severity level for validation errors."""

    CRITICAL = "critical"  # Blocks startup in strict mode
    WARNING = "warning"  # Logged but doesn't block startup


@dataclass
class ValidationError:
    """A validation error with severity and details."""

    message: str
    severity: ValidationSeverity
    provider_type: str  # "embedding", "summarization", "reranker"
    field: str = ""  # Optional field name

    def __str__(self) -> str:
        prefix = (
            "[CRITICAL]"
            if self.severity == ValidationSeverity.CRITICAL
            else "[WARNING]"
        )
        return f"{prefix} {self.provider_type}: {self.message}"


class EmbeddingConfig(BaseModel):
    """Configuration for embedding provider."""

    provider: EmbeddingProviderType = Field(
        default=EmbeddingProviderType.OPENAI,
        description="Embedding provider to use",
    )
    model: str = Field(
        default="text-embedding-3-large",
        description="Model name for embeddings",
    )
    api_key: str | None = Field(
        default=None,
        description="API key (alternative to api_key_env for local config files)",
    )
    api_key_env: str | None = Field(
        default="OPENAI_API_KEY",
        description="Environment variable name containing API key",
    )
    base_url: str | None = Field(
        default=None,
        description="Custom base URL (for Ollama or compatible APIs)",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific parameters",
    )

    model_config = {"use_enum_values": True}

    @field_validator("provider", mode="before")
    @classmethod
    def validate_provider(cls, v: Any) -> EmbeddingProviderType:
        """Convert string to enum if needed."""
        if isinstance(v, str):
            return EmbeddingProviderType(v.lower())
        if isinstance(v, EmbeddingProviderType):
            return v
        return EmbeddingProviderType(v)

    def get_api_key(self) -> str | None:
        """Resolve API key from config or environment variable.

        Resolution order:
        1. api_key field in config (direct value)
        2. Environment variable specified by api_key_env

        Returns:
            API key value or None if not found/not needed
        """
        if self.provider == EmbeddingProviderType.OLLAMA:
            return None  # Ollama doesn't need API key
        # Check direct api_key first
        if self.api_key:
            return self.api_key
        # Fall back to environment variable
        if self.api_key_env:
            return os.getenv(self.api_key_env)
        return None

    def get_base_url(self) -> str | None:
        """Get base URL with defaults for specific providers.

        Returns:
            Base URL for the provider
        """
        if self.base_url:
            return self.base_url
        if self.provider == EmbeddingProviderType.OLLAMA:
            return "http://localhost:11434/v1"
        return None


class SummarizationConfig(BaseModel):
    """Configuration for summarization provider."""

    provider: SummarizationProviderType = Field(
        default=SummarizationProviderType.ANTHROPIC,
        description="Summarization provider to use",
    )
    model: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Model name for summarization",
    )
    api_key: str | None = Field(
        default=None,
        description="API key (alternative to api_key_env for local config files)",
    )
    api_key_env: str | None = Field(
        default="ANTHROPIC_API_KEY",
        description="Environment variable name containing API key",
    )
    base_url: str | None = Field(
        default=None,
        description="Custom base URL (for Grok or Ollama)",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific parameters (max_tokens, temperature)",
    )

    model_config = {"use_enum_values": True}

    @field_validator("provider", mode="before")
    @classmethod
    def validate_provider(cls, v: Any) -> SummarizationProviderType:
        """Convert string to enum if needed."""
        if isinstance(v, str):
            return SummarizationProviderType(v.lower())
        if isinstance(v, SummarizationProviderType):
            return v
        return SummarizationProviderType(v)

    def get_api_key(self) -> str | None:
        """Resolve API key from config or environment variable.

        Resolution order:
        1. api_key field in config (direct value)
        2. Environment variable specified by api_key_env

        Returns:
            API key value or None if not found/not needed
        """
        if self.provider == SummarizationProviderType.OLLAMA:
            return None  # Ollama doesn't need API key
        # Check direct api_key first
        if self.api_key:
            return self.api_key
        # Fall back to environment variable
        if self.api_key_env:
            return os.getenv(self.api_key_env)
        return None

    def get_base_url(self) -> str | None:
        """Get base URL with defaults for specific providers.

        Returns:
            Base URL for the provider
        """
        if self.base_url:
            return self.base_url
        if self.provider == SummarizationProviderType.OLLAMA:
            return "http://localhost:11434/v1"
        if self.provider == SummarizationProviderType.GROK:
            return "https://api.x.ai/v1"
        return None


class RerankerConfig(BaseModel):
    """Configuration for reranking provider."""

    provider: RerankerProviderType = Field(
        default=RerankerProviderType.SENTENCE_TRANSFORMERS,
        description="Reranking provider to use",
    )
    model: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        description="Model name for reranking",
    )
    base_url: str | None = Field(
        default=None,
        description="Custom base URL (for Ollama)",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific parameters (batch_size, etc.)",
    )

    model_config = {"use_enum_values": True}

    @field_validator("provider", mode="before")
    @classmethod
    def validate_provider(cls, v: Any) -> RerankerProviderType:
        """Convert string to enum if needed."""
        if isinstance(v, str):
            return RerankerProviderType(v.lower())
        if isinstance(v, RerankerProviderType):
            return v
        return RerankerProviderType(v)

    def get_base_url(self) -> str | None:
        """Get base URL with defaults for specific providers.

        Returns:
            Base URL for the provider
        """
        if self.base_url:
            return self.base_url
        if self.provider == RerankerProviderType.OLLAMA:
            return "http://localhost:11434"
        return None


class ProviderSettings(BaseModel):
    """Top-level provider configuration."""

    embedding: EmbeddingConfig = Field(
        default_factory=EmbeddingConfig,
        description="Embedding provider configuration",
    )
    summarization: SummarizationConfig = Field(
        default_factory=SummarizationConfig,
        description="Summarization provider configuration",
    )
    reranker: RerankerConfig = Field(
        default_factory=RerankerConfig,
        description="Reranking provider configuration (optional)",
    )


def _find_config_file() -> Path | None:
    """Find the configuration file in standard locations.

    Search order:
    1. AGENT_BRAIN_CONFIG environment variable
    2. State directory config.yaml (if AGENT_BRAIN_STATE_DIR or DOC_SERVE_STATE_DIR set)
    3. Current directory config.yaml
    4. Walk up from CWD looking for .claude/agent-brain/config.yaml
    5. User home ~/.agent-brain/config.yaml
    6. XDG config ~/.config/agent-brain/config.yaml

    Returns:
        Path to config file or None if not found
    """
    # 1. Environment variable override
    env_config = os.getenv("AGENT_BRAIN_CONFIG")
    if env_config:
        path = Path(env_config)
        if path.exists():
            logger.debug(f"Found config via AGENT_BRAIN_CONFIG: {path}")
            return path
        logger.warning(f"AGENT_BRAIN_CONFIG points to non-existent file: {env_config}")

    # 2. State directory (check both new and legacy env vars)
    state_dir = os.getenv("AGENT_BRAIN_STATE_DIR") or os.getenv("DOC_SERVE_STATE_DIR")
    if state_dir:
        state_config = Path(state_dir) / "config.yaml"
        if state_config.exists():
            logger.debug(f"Found config in state directory: {state_config}")
            return state_config

    # 3. Current directory
    cwd_config = Path.cwd() / "config.yaml"
    if cwd_config.exists():
        logger.debug(f"Found config in current directory: {cwd_config}")
        return cwd_config

    # 4. Walk up from CWD looking for .claude/agent-brain/config.yaml
    current = Path.cwd()
    root = Path(current.anchor)
    while current != root:
        claude_config = current / ".claude" / "agent-brain" / "config.yaml"
        if claude_config.exists():
            logger.debug(f"Found config walking up from CWD: {claude_config}")
            return claude_config
        current = current.parent

    # 5. User home directory ~/.agent-brain/config.yaml
    home_config = Path.home() / ".agent-brain" / "config.yaml"
    if home_config.exists():
        logger.debug(f"Found config in home directory: {home_config}")
        return home_config

    # 6. XDG config directory ~/.config/agent-brain/config.yaml
    xdg_config = Path.home() / ".config" / "agent-brain" / "config.yaml"
    if xdg_config.exists():
        logger.debug(f"Found config in XDG config directory: {xdg_config}")
        return xdg_config

    return None


def _load_yaml_config(path: Path) -> dict[str, Any]:
    """Load YAML configuration from file.

    Args:
        path: Path to YAML config file

    Returns:
        Configuration dictionary

    Raises:
        ConfigurationError: If YAML parsing fails
    """
    from agent_brain_server.providers.exceptions import ConfigurationError

    try:
        with open(path) as f:
            config = yaml.safe_load(f)
            return config if config else {}
    except yaml.YAMLError as e:
        raise ConfigurationError(
            f"Failed to parse config file {path}: {e}",
            "config",
        ) from e
    except OSError as e:
        raise ConfigurationError(
            f"Failed to read config file {path}: {e}",
            "config",
        ) from e


@lru_cache
def load_provider_settings() -> ProviderSettings:
    """Load provider settings from YAML config or defaults.

    This function:
    1. Searches for config.yaml in standard locations
    2. Parses YAML and validates against Pydantic models
    3. Falls back to defaults (OpenAI embeddings + Anthropic summarization)

    Returns:
        Validated ProviderSettings instance
    """
    config_path = _find_config_file()

    if config_path:
        logger.info(f"Loading provider config from {config_path}")
        raw_config = _load_yaml_config(config_path)
        settings = ProviderSettings(**raw_config)
    else:
        logger.info("No config file found, using default providers")
        settings = ProviderSettings()

    # Log active configuration
    logger.info(
        f"Active embedding provider: {settings.embedding.provider} "
        f"(model: {settings.embedding.model})"
    )
    logger.info(
        f"Active summarization provider: {settings.summarization.provider} "
        f"(model: {settings.summarization.model})"
    )
    logger.info(
        f"Active reranker provider: {settings.reranker.provider} "
        f"(model: {settings.reranker.model})"
    )

    return settings


def clear_settings_cache() -> None:
    """Clear the cached provider settings (for testing)."""
    load_provider_settings.cache_clear()


def validate_provider_config(
    settings: ProviderSettings,
    reranking_enabled: bool = False,
) -> list[ValidationError]:
    """Validate provider configuration and return list of errors.

    Checks:
    - API keys are available for providers that need them (CRITICAL)
    - Reranker base_url is set for Ollama reranker when enabled (WARNING)

    Args:
        settings: Provider settings to validate
        reranking_enabled: Whether reranking is enabled (from app settings)

    Returns:
        List of ValidationError objects (empty if valid)
    """
    errors: list[ValidationError] = []

    # Validate embedding provider
    if settings.embedding.provider != EmbeddingProviderType.OLLAMA:
        api_key = settings.embedding.get_api_key()
        if not api_key:
            env_var = settings.embedding.api_key_env or "OPENAI_API_KEY"
            errors.append(
                ValidationError(
                    message=(
                        f"Missing API key for {settings.embedding.provider} "
                        f"embeddings. Set {env_var} environment variable."
                    ),
                    severity=ValidationSeverity.CRITICAL,
                    provider_type="embedding",
                    field="api_key",
                )
            )

    # Validate summarization provider
    if settings.summarization.provider != SummarizationProviderType.OLLAMA:
        api_key = settings.summarization.get_api_key()
        if not api_key:
            env_var = settings.summarization.api_key_env or "ANTHROPIC_API_KEY"
            errors.append(
                ValidationError(
                    message=(
                        f"Missing API key for {settings.summarization.provider} "
                        f"summarization. Set {env_var} environment variable."
                    ),
                    severity=ValidationSeverity.CRITICAL,
                    provider_type="summarization",
                    field="api_key",
                )
            )

    # Validate reranker provider (when reranking is enabled)
    if reranking_enabled:
        if settings.reranker.provider == RerankerProviderType.OLLAMA:
            base_url = settings.reranker.get_base_url()
            if not base_url:
                errors.append(
                    ValidationError(
                        message=(
                            "Ollama reranker enabled but no base_url configured. "
                            "Set reranker.base_url in config.yaml or use "
                            "default (http://localhost:11434)."
                        ),
                        severity=ValidationSeverity.WARNING,
                        provider_type="reranker",
                        field="base_url",
                    )
                )

    return errors


def has_critical_errors(errors: list[ValidationError]) -> bool:
    """Check if any validation errors are critical.

    Args:
        errors: List of validation errors

    Returns:
        True if any error has CRITICAL severity
    """
    return any(e.severity == ValidationSeverity.CRITICAL for e in errors)
