"""Base protocols and classes for pluggable providers."""

import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class EmbeddingProviderType(str, Enum):
    """Supported embedding providers."""

    OPENAI = "openai"
    OLLAMA = "ollama"
    COHERE = "cohere"


class SummarizationProviderType(str, Enum):
    """Supported summarization providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"
    GROK = "grok"
    OLLAMA = "ollama"


class RerankerProviderType(str, Enum):
    """Supported reranking providers."""

    SENTENCE_TRANSFORMERS = "sentence-transformers"
    OLLAMA = "ollama"


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding providers.

    All embedding providers must implement this interface to be usable
    by the Agent Brain indexing and query systems.
    """

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text.

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
        progress_callback: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts.

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
        """Get the embedding vector dimensions for the current model.

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


@runtime_checkable
class SummarizationProvider(Protocol):
    """Protocol for summarization/LLM providers.

    All summarization providers must implement this interface to be usable
    by the Agent Brain code summarization system.
    """

    async def summarize(self, text: str) -> str:
        """Generate a summary of the given text.

        Args:
            text: Text to summarize (typically source code).

        Returns:
            Natural language summary of the text.

        Raises:
            ProviderError: If summarization fails.
        """
        ...

    async def generate(self, prompt: str) -> str:
        """Generate text based on a prompt (generic LLM call).

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


class BaseEmbeddingProvider(ABC):
    """Base class for embedding providers with common functionality."""

    def __init__(self, model: str, batch_size: int = 100) -> None:
        self._model = model
        self._batch_size = batch_size
        logger.info(
            f"Initialized {self.provider_name} embedding provider with model {model}"
        )

    @property
    def model_name(self) -> str:
        """Model identifier being used."""
        return self._model

    async def embed_texts(
        self,
        texts: list[str],
        progress_callback: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> list[list[float]]:
        """Default batch implementation using _embed_batch."""
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

            logger.debug(
                f"Generated embeddings for batch {i // self._batch_size + 1} "
                f"({len(batch)} texts)"
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
        """Human-readable provider name for logging."""
        ...


class BaseSummarizationProvider(ABC):
    """Base class for summarization providers with common functionality."""

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
        prompt_template: str | None = None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._prompt_template = prompt_template or self.DEFAULT_PROMPT_TEMPLATE
        logger.info(
            f"Initialized {self.provider_name} summarization provider "
            f"with model {model}"
        )

    @property
    def model_name(self) -> str:
        """Model identifier being used."""
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
        """Human-readable provider name for logging."""
        ...
