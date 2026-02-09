"""Base protocol and class for reranking providers."""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from agent_brain_server.config.provider_config import RerankerConfig

logger = logging.getLogger(__name__)


@runtime_checkable
class RerankerProvider(Protocol):
    """Protocol for reranking providers.

    All reranking providers must implement this interface to be usable
    by the Agent Brain query system for two-stage retrieval.
    """

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[tuple[int, float]]:
        """Rerank documents for a query.

        Args:
            query: The search query.
            documents: List of document texts to rerank.
            top_k: Number of top results to return.

        Returns:
            List of (original_index, score) tuples, sorted by score descending.
            The original_index refers to the position in the input documents list.

        Raises:
            ProviderError: If reranking fails.
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

    def is_available(self) -> bool:
        """Check if the provider is available and ready.

        Returns:
            True if provider can perform reranking, False otherwise.
        """
        ...


class BaseRerankerProvider(ABC):
    """Base class for reranking providers with common functionality."""

    def __init__(self, config: "RerankerConfig") -> None:
        """Initialize the reranker provider.

        Args:
            config: Reranker configuration.
        """
        self._model = config.model
        self._config = config
        logger.info(
            f"Initialized {self.provider_name} reranker with model {self._model}"
        )

    def warm_up(self) -> bool:
        """Pre-load resources at startup to avoid first-query latency.

        Override in subclasses that need startup initialization.
        Default implementation returns True (no warm-up needed).

        Returns:
            True if warm-up successful, False otherwise.
        """
        return True

    @property
    def model_name(self) -> str:
        """Model identifier being used."""
        return self._model

    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[tuple[int, float]]:
        """Provider-specific reranking implementation."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name for logging."""
        ...

    def is_available(self) -> bool:
        """Default implementation - override if availability check needed."""
        return True
