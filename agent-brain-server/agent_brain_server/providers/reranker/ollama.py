"""Ollama-based reranking provider using chat completions."""

import asyncio
import logging
import re
import time
from typing import TYPE_CHECKING

import httpx

from agent_brain_server.providers.factory import ProviderRegistry
from agent_brain_server.providers.reranker.base import BaseRerankerProvider

if TYPE_CHECKING:
    from agent_brain_server.config.provider_config import RerankerConfig

logger = logging.getLogger(__name__)


class OllamaRerankerProvider(BaseRerankerProvider):
    """Reranker using Ollama chat completions for relevance scoring.

    Uses prompt-based scoring to rank documents by relevance to the query.
    This approach works with any Ollama model but is slower than CrossEncoder.

    Includes circuit breaker pattern to skip reranking when Ollama is down,
    preventing all-zero scoring that would silently degrade results.

    Recommended models:
    - qwen3:0.6b-reranker (if available)
    - llama3.2:1b (general purpose, good for scoring)
    - gemma2:2b (good instruction following)

    Note: This is slower than sentence-transformers but fully local without
    needing to download HuggingFace models.
    """

    RERANK_PROMPT = (
        "You are a relevance scoring system. "
        "Score how relevant the document is to the query.\n\n"
        "Query: {query}\n\n"
        "Document: {document}\n\n"
        "Instructions:\n"
        "- Output ONLY a single number from 0 to 10\n"
        "- 10 = perfectly relevant, directly answers the query\n"
        "- 5 = somewhat relevant, related topic\n"
        "- 0 = completely irrelevant\n"
        "- Do not output any other text, just the number\n\n"
        "Score:"
    )

    # Circuit breaker settings
    FAILURE_THRESHOLD = 3  # Consecutive failures before opening circuit
    CIRCUIT_RESET_TIME = 60.0  # Seconds before trying again after circuit opens

    def __init__(self, config: "RerankerConfig") -> None:
        """Initialize the Ollama reranker.

        Args:
            config: Reranker configuration.
        """
        super().__init__(config)
        self._base_url = config.get_base_url() or "http://localhost:11434"
        self._timeout = config.params.get("timeout", 30.0)
        self._max_concurrent = config.params.get("max_concurrent", 5)
        self._client: httpx.AsyncClient | None = None

        # Circuit breaker state
        self._consecutive_failures = 0
        self._circuit_open = False
        self._circuit_opened_at: float = 0.0

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    def _check_circuit(self) -> bool:
        """Check if circuit breaker allows requests.

        Returns:
            True if requests should proceed, False if circuit is open.
        """
        if not self._circuit_open:
            return True

        # Check if enough time has passed to try again
        elapsed = time.time() - self._circuit_opened_at
        if elapsed >= self.CIRCUIT_RESET_TIME:
            logger.info("Ollama circuit breaker: attempting reset after timeout")
            self._circuit_open = False
            self._consecutive_failures = 0
            return True

        return False

    def _record_success(self) -> None:
        """Record a successful request, resetting failure count."""
        self._consecutive_failures = 0
        if self._circuit_open:
            logger.info("Ollama circuit breaker: closed after successful request")
            self._circuit_open = False

    def _record_failure(self) -> None:
        """Record a failed request, potentially opening circuit."""
        self._consecutive_failures += 1
        if (
            self._consecutive_failures >= self.FAILURE_THRESHOLD
            and not self._circuit_open
        ):
            logger.warning(
                f"Ollama circuit breaker: OPEN after {self._consecutive_failures} "
                f"consecutive failures. Skipping rerank for {self.CIRCUIT_RESET_TIME}s"
            )
            self._circuit_open = True
            self._circuit_opened_at = time.time()

    async def _score_document(
        self,
        query: str,
        document: str,
        doc_index: int,
    ) -> tuple[int, float]:
        """Score a single document for relevance.

        Args:
            query: The search query.
            document: Document text to score.
            doc_index: Original index in the document list.

        Returns:
            Tuple of (doc_index, score).
        """
        # Truncate document to avoid context overflow
        max_doc_len = 2000
        doc_text = document[:max_doc_len] if len(document) > max_doc_len else document

        prompt = self.RERANK_PROMPT.format(query=query, document=doc_text)

        try:
            client = self._get_client()
            response = await client.post(
                "/api/chat",
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.0},
                },
            )
            response.raise_for_status()
            result = response.json()

            # Parse score from response
            content = result.get("message", {}).get("content", "").strip()
            score = self._parse_score(content)
            self._record_success()
            return (doc_index, score)

        except httpx.HTTPError as e:
            logger.warning(f"Ollama request failed for doc {doc_index}: {e}")
            self._record_failure()
            return (doc_index, 0.0)
        except Exception as e:
            logger.warning(f"Error scoring doc {doc_index}: {e}")
            self._record_failure()
            return (doc_index, 0.0)

    def _parse_score(self, content: str) -> float:
        """Parse numeric score from model output.

        Args:
            content: Raw model response.

        Returns:
            Parsed score (0-10), or 0.0 on failure.
        """
        try:
            # Try to extract first number from response
            match = re.search(r"(\d+(?:\.\d+)?)", content)
            if match:
                score = float(match.group(1))
                # Clamp to 0-10 range
                return min(max(score, 0.0), 10.0)
            return 0.0
        except (ValueError, AttributeError):
            return 0.0

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[tuple[int, float]]:
        """Rerank documents using Ollama chat completions.

        Scores each document concurrently with rate limiting.
        Uses circuit breaker to skip reranking when Ollama is down.

        Args:
            query: The search query.
            documents: List of document texts to rerank.
            top_k: Number of top results to return.

        Returns:
            List of (original_index, score) tuples, sorted by score descending.
            Returns empty list if circuit breaker is open (caller should fallback).
        """
        if not documents:
            return []

        # Check circuit breaker - if open, signal caller to use fallback
        if not self._check_circuit():
            logger.warning(
                "Ollama circuit breaker open - skipping rerank, using stage 1"
            )
            # Raise to trigger fallback in caller
            raise RuntimeError("Ollama circuit breaker open - reranking unavailable")

        # Create scoring tasks with semaphore for rate limiting
        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def score_with_limit(idx: int, doc: str) -> tuple[int, float]:
            async with semaphore:
                return await self._score_document(query, doc, idx)

        # Score all documents concurrently
        tasks = [score_with_limit(i, doc) for i, doc in enumerate(documents)]
        scores = await asyncio.gather(*tasks)

        # Check if all scores are zero (likely Ollama failure)
        if all(score == 0.0 for _, score in scores):
            logger.warning("All Ollama scores are 0.0 - possible endpoint failure")
            # Don't raise here, let caller decide based on results

        # Sort by score descending and take top_k
        sorted_scores = sorted(scores, key=lambda x: x[1], reverse=True)

        logger.debug(
            f"Ollama reranked {len(documents)} documents, returning top {top_k}"
        )

        return sorted_scores[:top_k]

    @property
    def provider_name(self) -> str:
        """Human-readable provider name."""
        return "Ollama"

    def is_available(self) -> bool:
        """Check if Ollama is running and model is available.

        Also checks circuit breaker state.

        Returns:
            True if Ollama responds to health check, False otherwise.
        """
        # If circuit is open, report unavailable
        if self._circuit_open and not self._check_circuit():
            return False

        try:
            import httpx as sync_httpx

            with sync_httpx.Client(base_url=self._base_url, timeout=5.0) as client:
                response = client.get("/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.debug(f"Ollama not available: {e}")
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Register provider on import
ProviderRegistry.register_reranker_provider(
    "ollama",
    OllamaRerankerProvider,
)
