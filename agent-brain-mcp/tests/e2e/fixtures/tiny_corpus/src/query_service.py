"""Fictional QueryService used only by the E2E tiny-corpus fixture."""

from __future__ import annotations


class QueryService:
    """Resolves queries against the fictional storage backend."""

    def verify_token(self, token: str) -> str | None:
        """Return the user_id for a token, or None if unknown."""
        # Stub — the E2E tests only care that the symbol exists in the corpus.
        return None

    def search(self, query: str, *, top_k: int = 5) -> list[dict[str, object]]:
        """Return the top-K results for a query."""
        return []
