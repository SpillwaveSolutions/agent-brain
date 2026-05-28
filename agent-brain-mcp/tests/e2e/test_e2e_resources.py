"""Phase 4 E2E: every resource read end-to-end.

Maps to plan §6.5 + §12.3 acceptance #17.
"""

from __future__ import annotations

import pytest


def test_corpus_config_returns_documented_fields(mcp_client: object) -> None:
    """``resources/read corpus://config`` returns the ConfigStatus shape
    (Phase 2 endpoint, Phase 4 wire-up)."""
    pytest.skip("Phase 4 implementation pending.")


def test_corpus_status_returns_chunk_counts(mcp_client: object) -> None:
    """``resources/read corpus://status`` exposes total_chunks, total_documents,
    indexing state, graph index counters, cache hit rates."""
    pytest.skip("Phase 4 implementation pending.")


def test_corpus_health_returns_server_info(mcp_client: object) -> None:
    """``resources/read corpus://health`` returns HealthStatus."""
    pytest.skip("Phase 4 implementation pending.")


def test_corpus_providers_lists_active_providers(mcp_client: object) -> None:
    """``resources/read corpus://providers`` lists embedding/summarization/
    reranker providers with model + healthy/degraded/unavailable status."""
    pytest.skip("Phase 4 implementation pending.")


def test_corpus_folders_includes_watch_state(mcp_client: object) -> None:
    """``resources/read corpus://folders`` returns each folder's watch_mode
    and watch_debounce_seconds (so the user can answer 'what's auto-watched')."""
    pytest.skip("Phase 4 implementation pending.")


def test_resources_subscribe_returns_method_not_found(mcp_client: object) -> None:
    """v1 capability advertises ``subscribe: false`` → ``resources/subscribe``
    must return ``Method not found`` (plan §6.1)."""
    pytest.skip("Phase 4 implementation pending.")
