"""Provider factory and registry for dynamic provider instantiation."""

import logging
from typing import TYPE_CHECKING, Any, cast

from agent_brain_server.providers.exceptions import ProviderNotFoundError

if TYPE_CHECKING:
    from agent_brain_server.config.provider_config import (
        EmbeddingConfig,
        RerankerConfig,
        SummarizationConfig,
    )
    from agent_brain_server.providers.base import (
        EmbeddingProvider,
        SummarizationProvider,
    )
    from agent_brain_server.providers.reranker.base import RerankerProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Registry for provider implementations.

    Allows dynamic registration of providers and lazy instantiation.
    Implements singleton pattern for provider instance caching.
    """

    _embedding_providers: dict[str, type[Any]] = {}
    _summarization_providers: dict[str, type[Any]] = {}
    _reranker_providers: dict[str, type[Any]] = {}
    _instances: dict[str, Any] = {}

    @classmethod
    def register_embedding_provider(
        cls,
        provider_type: str,
        provider_class: type["EmbeddingProvider"],
    ) -> None:
        """Register an embedding provider class.

        Args:
            provider_type: Provider identifier (e.g., 'openai', 'ollama')
            provider_class: Provider class implementing EmbeddingProvider protocol
        """
        cls._embedding_providers[provider_type] = provider_class
        logger.debug(f"Registered embedding provider: {provider_type}")

    @classmethod
    def register_summarization_provider(
        cls,
        provider_type: str,
        provider_class: type["SummarizationProvider"],
    ) -> None:
        """Register a summarization provider class.

        Args:
            provider_type: Provider identifier (e.g., 'anthropic', 'openai')
            provider_class: Provider class implementing SummarizationProvider protocol
        """
        cls._summarization_providers[provider_type] = provider_class
        logger.debug(f"Registered summarization provider: {provider_type}")

    @classmethod
    def get_embedding_provider(cls, config: "EmbeddingConfig") -> "EmbeddingProvider":
        """Get or create embedding provider instance.

        Args:
            config: Embedding provider configuration

        Returns:
            Configured EmbeddingProvider instance

        Raises:
            ProviderNotFoundError: If provider type is not registered
        """
        # Get provider type as string value
        provider_type = (
            config.provider.value
            if hasattr(config.provider, "value")
            else str(config.provider)
        )
        cache_key = f"embed:{provider_type}:{config.model}"

        if cache_key not in cls._instances:
            provider_class = cls._embedding_providers.get(provider_type)
            if not provider_class:
                available = list(cls._embedding_providers.keys())
                raise ProviderNotFoundError(
                    f"Unknown embedding provider: {provider_type}. "
                    f"Available: {', '.join(available)}",
                    provider_type,
                )
            cls._instances[cache_key] = provider_class(config)
            logger.info(
                f"Created {provider_type} embedding provider with model {config.model}"
            )

        from agent_brain_server.providers.base import EmbeddingProvider

        return cast(EmbeddingProvider, cls._instances[cache_key])

    @classmethod
    def get_summarization_provider(
        cls, config: "SummarizationConfig"
    ) -> "SummarizationProvider":
        """Get or create summarization provider instance.

        Args:
            config: Summarization provider configuration

        Returns:
            Configured SummarizationProvider instance

        Raises:
            ProviderNotFoundError: If provider type is not registered
        """
        # Get provider type as string value
        provider_type = (
            config.provider.value
            if hasattr(config.provider, "value")
            else str(config.provider)
        )
        cache_key = f"summ:{provider_type}:{config.model}"

        if cache_key not in cls._instances:
            provider_class = cls._summarization_providers.get(provider_type)
            if not provider_class:
                available = list(cls._summarization_providers.keys())
                raise ProviderNotFoundError(
                    f"Unknown summarization provider: {provider_type}. "
                    f"Available: {', '.join(available)}",
                    provider_type,
                )
            cls._instances[cache_key] = provider_class(config)
            logger.info(
                f"Created {provider_type} summarization provider "
                f"with model {config.model}"
            )

        from agent_brain_server.providers.base import SummarizationProvider

        return cast(SummarizationProvider, cls._instances[cache_key])

    @classmethod
    def register_reranker_provider(
        cls,
        provider_type: str,
        provider_class: type["RerankerProvider"],
    ) -> None:
        """Register a reranking provider class.

        Args:
            provider_type: Provider identifier (e.g., 'sentence-transformers', 'ollama')
            provider_class: Provider class implementing RerankerProvider protocol
        """
        cls._reranker_providers[provider_type] = provider_class
        logger.debug(f"Registered reranker provider: {provider_type}")

    @classmethod
    def get_reranker_provider(cls, config: "RerankerConfig") -> "RerankerProvider":
        """Get or create reranker provider instance.

        Args:
            config: Reranker provider configuration

        Returns:
            Configured RerankerProvider instance

        Raises:
            ProviderNotFoundError: If provider type is not registered
        """
        # Get provider type as string value
        provider_type = (
            config.provider.value
            if hasattr(config.provider, "value")
            else str(config.provider)
        )
        cache_key = f"rerank:{provider_type}:{config.model}"

        if cache_key not in cls._instances:
            provider_class = cls._reranker_providers.get(provider_type)
            if not provider_class:
                available = list(cls._reranker_providers.keys())
                raise ProviderNotFoundError(
                    f"Unknown reranker provider: {provider_type}. "
                    f"Available: {', '.join(available) if available else 'none'}",
                    provider_type,
                )
            cls._instances[cache_key] = provider_class(config)
            logger.info(
                f"Created {provider_type} reranker provider with model {config.model}"
            )

        from agent_brain_server.providers.reranker.base import RerankerProvider

        return cast(RerankerProvider, cls._instances[cache_key])

    @classmethod
    def clear_cache(cls) -> None:
        """Clear provider instance cache (for testing)."""
        cls._instances.clear()
        logger.debug("Cleared provider instance cache")

    @classmethod
    def get_available_embedding_providers(cls) -> list[str]:
        """Get list of registered embedding provider types."""
        return list(cls._embedding_providers.keys())

    @classmethod
    def get_available_summarization_providers(cls) -> list[str]:
        """Get list of registered summarization provider types."""
        return list(cls._summarization_providers.keys())

    @classmethod
    def get_available_reranker_providers(cls) -> list[str]:
        """Get list of registered reranker provider types."""
        return list(cls._reranker_providers.keys())
