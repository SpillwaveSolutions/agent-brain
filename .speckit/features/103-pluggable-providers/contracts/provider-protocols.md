# Provider Protocols

**Feature**: 103-pluggable-providers
**Date**: 2026-02-01
**Status**: Complete

## Overview

This document defines the Python Protocols (interfaces) for pluggable model providers. These protocols establish the contract that all provider implementations must follow.

## Protocol Definitions

### EmbeddingProvider Protocol

```python
from typing import Protocol, Optional
from collections.abc import Awaitable, Callable


class EmbeddingProvider(Protocol):
    """
    Protocol for embedding providers.

    All embedding providers must implement this interface to be usable
    by the Agent Brain indexing and query systems.
    """

    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector as list of floats.

        Raises:
            ProviderError: If embedding generation fails.
        """
        ...

    async def embed_texts(
        self,
        texts: list[str],
        progress_callback: Optional[Callable[[int, int], Awaitable[None]]] = None,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.
            progress_callback: Optional callback(processed, total) for progress.

        Returns:
            List of embedding vectors, one per input text.

        Raises:
            ProviderError: If embedding generation fails.
        """
        ...

    def get_dimensions(self) -> int:
        """
        Get the embedding vector dimensions for the current model.

        Returns:
            Number of dimensions in the embedding vector.
        """
        ...

    @property
    def provider_name(self) -> str:
        """Human-readable provider name for logging."""
        ...

    @property
    def model_name(self) -> str:
        """Model identifier being used."""
        ...
```

---

### SummarizationProvider Protocol

```python
class SummarizationProvider(Protocol):
    """
    Protocol for summarization/LLM providers.

    All summarization providers must implement this interface to be usable
    by the Agent Brain code summarization system.
    """

    async def summarize(self, text: str) -> str:
        """
        Generate a summary of the given text.

        Args:
            text: Text to summarize (typically source code).

        Returns:
            Natural language summary of the text.

        Raises:
            ProviderError: If summarization fails.
        """
        ...

    async def generate(self, prompt: str) -> str:
        """
        Generate text based on a prompt (generic LLM call).

        Args:
            prompt: The prompt to send to the LLM.

        Returns:
            Generated text response.

        Raises:
            ProviderError: If generation fails.
        """
        ...

    @property
    def provider_name(self) -> str:
        """Human-readable provider name for logging."""
        ...

    @property
    def model_name(self) -> str:
        """Model identifier being used."""
        ...
```

---

### ProviderFactory Protocol

```python
from typing import Optional

class ProviderFactory(Protocol):
    """
    Factory for creating provider instances from configuration.
    """

    def get_embedding_provider(
        self,
        config: Optional["EmbeddingConfig"] = None,
    ) -> EmbeddingProvider:
        """
        Get or create an embedding provider instance.

        Args:
            config: Optional configuration override. Uses default if None.

        Returns:
            Configured EmbeddingProvider instance.

        Raises:
            ConfigurationError: If configuration is invalid.
            ProviderNotFoundError: If provider type is not registered.
        """
        ...

    def get_summarization_provider(
        self,
        config: Optional["SummarizationConfig"] = None,
    ) -> SummarizationProvider:
        """
        Get or create a summarization provider instance.

        Args:
            config: Optional configuration override. Uses default if None.

        Returns:
            Configured SummarizationProvider instance.

        Raises:
            ConfigurationError: If configuration is invalid.
            ProviderNotFoundError: If provider type is not registered.
        """
        ...

    def validate_configuration(self) -> list[str]:
        """
        Validate the current provider configuration.

        Returns:
            List of validation errors (empty if valid).
        """
        ...
```

---

## Exception Hierarchy

```python
class ProviderError(Exception):
    """Base exception for provider errors."""

    def __init__(self, message: str, provider: str, cause: Optional[Exception] = None):
        self.provider = provider
        self.cause = cause
        super().__init__(f"[{provider}] {message}")


class ConfigurationError(ProviderError):
    """Raised when provider configuration is invalid."""
    pass


class AuthenticationError(ProviderError):
    """Raised when API key is missing or invalid."""
    pass


class ProviderNotFoundError(ProviderError):
    """Raised when requested provider type is not registered."""
    pass


class ProviderMismatchError(ProviderError):
    """Raised when current provider doesn't match indexed data."""

    def __init__(
        self,
        current_provider: str,
        current_model: str,
        indexed_provider: str,
        indexed_model: str,
    ):
        message = (
            f"Provider mismatch: index was created with {indexed_provider}/{indexed_model}, "
            f"but current config uses {current_provider}/{current_model}. "
            f"Re-index with --force to update."
        )
        super().__init__(message, current_provider)
        self.indexed_provider = indexed_provider
        self.indexed_model = indexed_model


class RateLimitError(ProviderError):
    """Raised when provider rate limit is hit."""

    def __init__(self, provider: str, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        message = f"Rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after}s"
        super().__init__(message, provider)


class ModelNotFoundError(ProviderError):
    """Raised when specified model is not available."""

    def __init__(self, provider: str, model: str, available_models: list[str]):
        self.model = model
        self.available_models = available_models
        message = f"Model '{model}' not found. Available: {', '.join(available_models[:5])}"
        super().__init__(message, provider)
```

---

## Base Implementation Classes

### BaseEmbeddingProvider

```python
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class BaseEmbeddingProvider(ABC):
    """
    Base class for embedding providers with common functionality.
    """

    def __init__(self, model: str, batch_size: int = 100):
        self._model = model
        self._batch_size = batch_size
        logger.info(f"Initialized {self.provider_name} embedding provider with model {model}")

    @property
    def model_name(self) -> str:
        return self._model

    async def embed_texts(
        self,
        texts: list[str],
        progress_callback: Optional[Callable[[int, int], Awaitable[None]]] = None,
    ) -> list[list[float]]:
        """Default batch implementation using embed_text."""
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            batch_embeddings = await self._embed_batch(batch)
            all_embeddings.extend(batch_embeddings)

            if progress_callback:
                await progress_callback(
                    min(i + self._batch_size, len(texts)),
                    len(texts),
                )

        return all_embeddings

    @abstractmethod
    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Provider-specific batch embedding implementation."""
        ...

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Provider-specific single text embedding."""
        ...

    @abstractmethod
    def get_dimensions(self) -> int:
        """Provider-specific dimension lookup."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...
```

### BaseSummarizationProvider

```python
class BaseSummarizationProvider(ABC):
    """
    Base class for summarization providers with common functionality.
    """

    DEFAULT_PROMPT_TEMPLATE = (
        "You are an expert software engineer analyzing source code. "
        "Provide a concise 1-2 sentence summary of what this code does. "
        "Focus on the functionality, purpose, and behavior. "
        "Be specific about inputs, outputs, and side effects. "
        "Ignore implementation details and focus on what the code accomplishes.\n\n"
        "Code to summarize:\n{code}\n\n"
        "Summary:"
    )

    def __init__(
        self,
        model: str,
        max_tokens: int = 300,
        temperature: float = 0.1,
        prompt_template: Optional[str] = None,
    ):
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._prompt_template = prompt_template or self.DEFAULT_PROMPT_TEMPLATE
        logger.info(f"Initialized {self.provider_name} summarization provider with model {model}")

    @property
    def model_name(self) -> str:
        return self._model

    async def summarize(self, text: str) -> str:
        """Generate summary using the prompt template."""
        prompt = self._prompt_template.format(code=text)
        return await self.generate(prompt)

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """Provider-specific text generation."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...
```

---

## Factory Implementation Pattern

```python
from typing import Type

class ProviderRegistry:
    """
    Registry for provider implementations.

    Allows dynamic registration of providers and lazy instantiation.
    """

    _embedding_providers: dict[str, Type[EmbeddingProvider]] = {}
    _summarization_providers: dict[str, Type[SummarizationProvider]] = {}
    _instances: dict[str, object] = {}

    @classmethod
    def register_embedding_provider(
        cls,
        provider_type: str,
        provider_class: Type[EmbeddingProvider],
    ) -> None:
        """Register an embedding provider class."""
        cls._embedding_providers[provider_type] = provider_class

    @classmethod
    def register_summarization_provider(
        cls,
        provider_type: str,
        provider_class: Type[SummarizationProvider],
    ) -> None:
        """Register a summarization provider class."""
        cls._summarization_providers[provider_type] = provider_class

    @classmethod
    def get_embedding_provider(cls, config: EmbeddingConfig) -> EmbeddingProvider:
        """Get or create embedding provider instance."""
        cache_key = f"embed:{config.provider}:{config.model}"

        if cache_key not in cls._instances:
            provider_class = cls._embedding_providers.get(config.provider)
            if not provider_class:
                raise ProviderNotFoundError(
                    f"Unknown embedding provider: {config.provider}",
                    config.provider,
                )
            cls._instances[cache_key] = provider_class(config)

        return cls._instances[cache_key]

    @classmethod
    def get_summarization_provider(cls, config: SummarizationConfig) -> SummarizationProvider:
        """Get or create summarization provider instance."""
        cache_key = f"summ:{config.provider}:{config.model}"

        if cache_key not in cls._instances:
            provider_class = cls._summarization_providers.get(config.provider)
            if not provider_class:
                raise ProviderNotFoundError(
                    f"Unknown summarization provider: {config.provider}",
                    config.provider,
                )
            cls._instances[cache_key] = provider_class(config)

        return cls._instances[cache_key]

    @classmethod
    def clear_cache(cls) -> None:
        """Clear provider instance cache (for testing)."""
        cls._instances.clear()
```

---

## Registration Example

```python
# In providers/__init__.py

from .embedding.openai import OpenAIEmbeddingProvider
from .embedding.ollama import OllamaEmbeddingProvider
from .embedding.cohere import CohereEmbeddingProvider
from .summarization.anthropic import AnthropicSummarizationProvider
from .summarization.openai import OpenAISummarizationProvider
from .summarization.gemini import GeminiSummarizationProvider
from .summarization.grok import GrokSummarizationProvider
from .summarization.ollama import OllamaSummarizationProvider
from .factory import ProviderRegistry

# Register embedding providers
ProviderRegistry.register_embedding_provider("openai", OpenAIEmbeddingProvider)
ProviderRegistry.register_embedding_provider("ollama", OllamaEmbeddingProvider)
ProviderRegistry.register_embedding_provider("cohere", CohereEmbeddingProvider)

# Register summarization providers
ProviderRegistry.register_summarization_provider("anthropic", AnthropicSummarizationProvider)
ProviderRegistry.register_summarization_provider("openai", OpenAISummarizationProvider)
ProviderRegistry.register_summarization_provider("gemini", GeminiSummarizationProvider)
ProviderRegistry.register_summarization_provider("grok", GrokSummarizationProvider)
ProviderRegistry.register_summarization_provider("ollama", OllamaSummarizationProvider)
```

---

## Usage in Services

```python
# In services/indexing_service.py

from agent_brain_server.providers import ProviderRegistry
from agent_brain_server.config.provider_config import load_provider_settings

class IndexingService:
    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        summarization_provider: Optional[SummarizationProvider] = None,
    ):
        settings = load_provider_settings()

        self.embedding_provider = (
            embedding_provider or
            ProviderRegistry.get_embedding_provider(settings.embedding)
        )
        self.summarization_provider = (
            summarization_provider or
            ProviderRegistry.get_summarization_provider(settings.summarization)
        )
```
