"""Provider configuration models and YAML loader.

This module provides Pydantic models for embedding and summarization
provider configuration, and functions to load configuration from YAML files.
"""

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, field_validator

from agent_brain_server.providers.base import (
    EmbeddingProviderType,
    SummarizationProviderType,
)

logger = logging.getLogger(__name__)


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
    api_key_env: Optional[str] = Field(
        default="OPENAI_API_KEY",
        description="Environment variable name containing API key",
    )
    base_url: Optional[str] = Field(
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

    def get_api_key(self) -> Optional[str]:
        """Resolve API key from environment variable.

        Returns:
            API key value or None if not found/not needed
        """
        if self.provider == EmbeddingProviderType.OLLAMA:
            return None  # Ollama doesn't need API key
        if self.api_key_env:
            return os.getenv(self.api_key_env)
        return None

    def get_base_url(self) -> Optional[str]:
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
        default="claude-3-5-haiku-20241022",
        description="Model name for summarization",
    )
    api_key_env: Optional[str] = Field(
        default="ANTHROPIC_API_KEY",
        description="Environment variable name containing API key",
    )
    base_url: Optional[str] = Field(
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

    def get_api_key(self) -> Optional[str]:
        """Resolve API key from environment variable.

        Returns:
            API key value or None if not found/not needed
        """
        if self.provider == SummarizationProviderType.OLLAMA:
            return None  # Ollama doesn't need API key
        if self.api_key_env:
            return os.getenv(self.api_key_env)
        return None

    def get_base_url(self) -> Optional[str]:
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


def _find_config_file() -> Optional[Path]:
    """Find the configuration file in standard locations.

    Search order:
    1. DOC_SERVE_CONFIG environment variable
    2. Current directory config.yaml
    3. State directory config.yaml (if DOC_SERVE_STATE_DIR set)
    4. Project root config.yaml

    Returns:
        Path to config file or None if not found
    """
    # 1. Environment variable override
    env_config = os.getenv("DOC_SERVE_CONFIG")
    if env_config:
        path = Path(env_config)
        if path.exists():
            return path
        logger.warning(f"DOC_SERVE_CONFIG points to non-existent file: {env_config}")

    # 2. Current directory
    cwd_config = Path.cwd() / "config.yaml"
    if cwd_config.exists():
        return cwd_config

    # 3. State directory
    state_dir = os.getenv("DOC_SERVE_STATE_DIR")
    if state_dir:
        state_config = Path(state_dir) / "config.yaml"
        if state_config.exists():
            return state_config

    # 4. .claude/doc-serve directory (project root pattern)
    claude_dir = Path.cwd() / ".claude" / "doc-serve"
    if claude_dir.exists():
        claude_config = claude_dir / "config.yaml"
        if claude_config.exists():
            return claude_config

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

    return settings


def clear_settings_cache() -> None:
    """Clear the cached provider settings (for testing)."""
    load_provider_settings.cache_clear()


def validate_provider_config(settings: ProviderSettings) -> list[str]:
    """Validate provider configuration and return list of errors.

    Checks:
    - API keys are available for providers that need them
    - Models are known for the selected provider

    Args:
        settings: Provider settings to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    errors: list[str] = []

    # Validate embedding provider
    if settings.embedding.provider != EmbeddingProviderType.OLLAMA:
        api_key = settings.embedding.get_api_key()
        if not api_key:
            env_var = settings.embedding.api_key_env or "OPENAI_API_KEY"
            errors.append(
                f"Missing API key for {settings.embedding.provider} embeddings. "
                f"Set {env_var} environment variable."
            )

    # Validate summarization provider
    if settings.summarization.provider != SummarizationProviderType.OLLAMA:
        api_key = settings.summarization.get_api_key()
        if not api_key:
            env_var = settings.summarization.api_key_env or "ANTHROPIC_API_KEY"
            errors.append(
                f"Missing API key for {settings.summarization.provider} summarization. "
                f"Set {env_var} environment variable."
            )

    return errors
