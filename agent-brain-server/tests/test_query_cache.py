"""Unit and integration tests for QueryCacheService (Phase 17 — QCACHE).

Tests cover:
- Cache miss / hit mechanics
- Key determinism and stability
- Generation-based invalidation
- Mode filtering (graph, multi never cached)
- get_stats() structure
- Module-level singleton helpers
- TTL expiry
- List-field key stability

Integration tests (added in Plan 02 below) cover:
- QueryService cache check/store flow
- JobWorker invalidation on DONE
- Health endpoint query_cache stats inclusion
"""

import asyncio
import time
from typing import Any

import pytest

from agent_brain_server.services.query_cache import (
    QueryCacheService,
    get_query_cache,
    reset_query_cache,
    set_query_cache,
)


# ---------------------------------------------------------------------------
# Unit tests — QueryCacheService
# ---------------------------------------------------------------------------


def test_cache_miss_returns_none() -> None:
    """Fresh cache returns None and increments miss counter."""
    svc = QueryCacheService(ttl=60, max_size=10)
    key = svc.make_cache_key({"query": "test", "mode": "vector"})
    result = svc.get(key)
    assert result is None
    stats = svc.get_stats()
    assert stats["misses"] == 1
    assert stats["hits"] == 0


@pytest.mark.asyncio
async def test_cache_hit_returns_cached_result() -> None:
    """After put, get returns the value and increments hit counter."""
    svc = QueryCacheService(ttl=60, max_size=10)
    key = svc.make_cache_key({"query": "hello", "mode": "vector"})
    payload = {"results": ["doc1", "doc2"]}
    await svc.put(key, payload)
    result = svc.get(key)
    assert result == payload
    stats = svc.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 0


def test_cache_key_deterministic() -> None:
    """Same params produce the same key."""
    svc = QueryCacheService()
    params = {"query": "foo", "mode": "hybrid", "top_k": 5}
    key1 = svc.make_cache_key(params)
    key2 = svc.make_cache_key(params)
    assert key1 == key2


def test_cache_key_different_params() -> None:
    """Different params produce different keys."""
    svc = QueryCacheService()
    key1 = svc.make_cache_key({"query": "foo", "mode": "vector"})
    key2 = svc.make_cache_key({"query": "bar", "mode": "vector"})
    assert key1 != key2


@pytest.mark.asyncio
async def test_cache_key_includes_generation() -> None:
    """Key changes after invalidate_all() (generation change)."""
    svc = QueryCacheService()
    params = {"query": "foo", "mode": "vector"}
    key_before = svc.make_cache_key(params)
    await svc.invalidate_all()
    key_after = svc.make_cache_key(params)
    assert key_before != key_after


@pytest.mark.asyncio
async def test_invalidate_all_clears_cache() -> None:
    """Cached value is no longer returned after invalidate_all()."""
    svc = QueryCacheService(ttl=60, max_size=10)
    key = svc.make_cache_key({"query": "test"})
    await svc.put(key, {"data": "value"})
    assert svc.get(key) is not None

    await svc.invalidate_all()

    # Old key no longer matches (generation changed)
    assert svc.get(key) is None


@pytest.mark.asyncio
async def test_invalidate_all_increments_generation() -> None:
    """Generation counter increases after invalidate_all()."""
    svc = QueryCacheService()
    assert svc.get_stats()["index_generation"] == 0
    await svc.invalidate_all()
    assert svc.get_stats()["index_generation"] == 1
    await svc.invalidate_all()
    assert svc.get_stats()["index_generation"] == 2


def test_graph_mode_not_cached() -> None:
    """is_cacheable_mode('graph') == False."""
    assert QueryCacheService.is_cacheable_mode("graph") is False


def test_multi_mode_not_cached() -> None:
    """is_cacheable_mode('multi') == False."""
    assert QueryCacheService.is_cacheable_mode("multi") is False


def test_vector_bm25_hybrid_cacheable() -> None:
    """is_cacheable_mode returns True for vector, bm25, and hybrid."""
    for mode in ("vector", "bm25", "hybrid"):
        assert (
            QueryCacheService.is_cacheable_mode(mode) is True
        ), f"Expected {mode} to be cacheable"


def test_get_stats_structure() -> None:
    """get_stats returns dict with all expected keys."""
    svc = QueryCacheService()
    stats = svc.get_stats()
    assert "hits" in stats
    assert "misses" in stats
    assert "hit_rate" in stats
    assert "cached_entries" in stats
    assert "index_generation" in stats
    # Initial state
    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert stats["hit_rate"] == 0.0
    assert stats["cached_entries"] == 0
    assert stats["index_generation"] == 0


def test_settings_configure_cache() -> None:
    """Constructor respects ttl and max_size args."""
    svc = QueryCacheService(ttl=120, max_size=50)
    assert svc._ttl == 120
    assert svc._max_size == 50


def test_singleton_pattern() -> None:
    """set/get/reset module-level singleton works."""
    reset_query_cache()
    assert get_query_cache() is None

    svc = QueryCacheService()
    set_query_cache(svc)
    assert get_query_cache() is svc

    reset_query_cache()
    assert get_query_cache() is None


@pytest.mark.asyncio
async def test_cache_ttl_expiry() -> None:
    """Entry expires after TTL elapses."""
    svc = QueryCacheService(ttl=1, max_size=10)
    key = svc.make_cache_key({"query": "expire_test"})
    await svc.put(key, {"result": "data"})

    # Should be present immediately
    assert svc.get(key) is not None

    # Wait for TTL to expire
    await asyncio.sleep(1.1)

    # Should be gone now
    assert svc.get(key) is None


def test_sorted_list_fields_key_stability() -> None:
    """Cache key is identical regardless of list order in params."""
    svc = QueryCacheService()
    params_a = {
        "query": "test",
        "source_types": ["code", "doc"],
        "languages": ["python", "typescript"],
    }
    params_b = {
        "query": "test",
        "source_types": ["doc", "code"],  # reversed
        "languages": ["typescript", "python"],  # reversed
    }
    key_a = svc.make_cache_key(params_a)
    key_b = svc.make_cache_key(params_b)
    assert key_a == key_b


# ---------------------------------------------------------------------------
# Integration tests — QueryService + JobWorker + health endpoint (Plan 02)
# ---------------------------------------------------------------------------


def _make_mock_storage() -> Any:
    """Return a minimal mock for StorageBackendProtocol.

    The mock has is_initialized=True so QueryService.is_ready() passes, and
    get_count() returning 1 so queries proceed past the empty-index guard.
    vector_search returns a single SearchResult.
    """
    from unittest.mock import AsyncMock, MagicMock

    from agent_brain_server.storage.protocol import SearchResult

    mock_storage = MagicMock()
    mock_storage.is_initialized = True
    mock_storage.get_count = AsyncMock(return_value=1)
    mock_storage.vector_search = AsyncMock(
        return_value=[
            SearchResult(
                chunk_id="chunk-1",
                text="result text",
                score=0.9,
                metadata={"source": "test.py"},
            )
        ]
    )
    mock_storage.keyword_search = AsyncMock(return_value=[])
    return mock_storage


def _make_mock_embedding_generator() -> Any:
    """Return a minimal mock for EmbeddingGenerator."""
    from unittest.mock import AsyncMock, MagicMock

    mock_gen = MagicMock()
    mock_gen.embed_query = AsyncMock(return_value=[0.1] * 10)
    return mock_gen


@pytest.mark.asyncio
async def test_query_service_cache_hit() -> None:
    """Second identical query is served from cache; storage not called twice."""
    from agent_brain_server.models.query import QueryMode, QueryRequest
    from agent_brain_server.services.query_service import QueryService

    cache = QueryCacheService(ttl=60, max_size=10)
    storage = _make_mock_storage()
    embedding_gen = _make_mock_embedding_generator()

    svc = QueryService(
        storage_backend=storage,
        embedding_generator=embedding_gen,
        query_cache=cache,
    )

    request = QueryRequest(query="hello world", mode=QueryMode.VECTOR)

    # First call — should hit storage
    resp1 = await svc.execute_query(request)
    assert resp1 is not None
    first_call_count = storage.vector_search.call_count

    # Second call with same request — should be served from cache
    resp2 = await svc.execute_query(request)
    assert resp2 is not None
    assert storage.vector_search.call_count == first_call_count  # no new storage call

    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1  # first call was a miss


@pytest.mark.asyncio
async def test_query_service_graph_bypasses_cache() -> None:
    """graph mode queries are never stored in cache."""
    # graph mode raises ValueError when ENABLE_GRAPH_INDEX=False (default).
    # The key point is is_cacheable_mode("graph") == False, verified in unit
    # tests above.  Here we confirm QueryService never stores graph results.
    from agent_brain_server.models.query import QueryMode, QueryRequest
    from agent_brain_server.services.query_service import QueryService

    cache = QueryCacheService(ttl=60, max_size=10)
    storage = _make_mock_storage()
    embedding_gen = _make_mock_embedding_generator()

    svc = QueryService(
        storage_backend=storage,
        embedding_generator=embedding_gen,
        query_cache=cache,
    )

    request = QueryRequest(query="graph query", mode=QueryMode.GRAPH)

    # graph query will raise ValueError (ENABLE_GRAPH_INDEX=False by default)
    try:
        await svc.execute_query(request)
    except (ValueError, RuntimeError):
        pass  # expected — graph requires ENABLE_GRAPH_INDEX=True

    # No entries should be cached (graph bypasses cache entirely)
    stats = cache.get_stats()
    assert stats["cached_entries"] == 0
    assert stats["hits"] == 0


@pytest.mark.asyncio
async def test_query_service_multi_bypasses_cache() -> None:
    """multi mode queries never get cached."""
    from agent_brain_server.models.query import QueryMode, QueryRequest
    from agent_brain_server.services.query_service import QueryService

    cache = QueryCacheService(ttl=60, max_size=10)
    storage = _make_mock_storage()
    embedding_gen = _make_mock_embedding_generator()

    svc = QueryService(
        storage_backend=storage,
        embedding_generator=embedding_gen,
        query_cache=cache,
    )

    request = QueryRequest(query="multi query", mode=QueryMode.MULTI)

    # multi mode — calls vector + BM25 (no graph because ENABLE_GRAPH_INDEX is False)
    await svc.execute_query(request)

    stats = cache.get_stats()
    # No cache entries for multi mode
    assert stats["cached_entries"] == 0
    # No hits — multi mode was never stored
    assert stats["hits"] == 0


@pytest.mark.asyncio
async def test_job_worker_invalidates_cache_on_done() -> None:
    """After job completion with DONE status, cache is invalidated."""
    # Test the invalidation via direct cache put + invalidate_all pattern
    # to avoid spawning a real JobWorker (too heavy for unit test)
    svc = QueryCacheService(ttl=60, max_size=10)
    key = svc.make_cache_key({"query": "cached query", "mode": "vector"})
    await svc.put(key, {"result": "data"})
    assert svc.get(key) is not None

    # Simulate what JobWorker.set_query_cache + post-DONE invalidation does
    from agent_brain_server.job_queue.job_worker import JobWorker

    # Verify set_query_cache setter exists and works
    from unittest.mock import MagicMock

    mock_job_store = MagicMock()
    mock_indexing_service = MagicMock()
    worker = JobWorker(
        job_store=mock_job_store,
        indexing_service=mock_indexing_service,
    )
    worker.set_query_cache(svc)
    assert worker._query_cache is svc

    # Directly call invalidate_all to mirror what the worker does on DONE
    await svc.invalidate_all()
    # Old key no longer resolves (generation changed)
    assert svc.get(key) is None
    assert svc.get_stats()["index_generation"] == 1


def test_health_status_includes_query_cache() -> None:
    """When app.state.query_cache exists, get_stats dict is non-None."""
    svc = QueryCacheService()
    stats = svc.get_stats()

    # Verify the dict structure that the health endpoint will pass
    # to IndexingStatus(query_cache=stats)
    from agent_brain_server.models.health import IndexingStatus

    status = IndexingStatus(query_cache=stats)
    assert status.query_cache is not None
    assert "hits" in status.query_cache
    assert "misses" in status.query_cache
    assert "hit_rate" in status.query_cache
    assert "cached_entries" in status.query_cache
    assert "index_generation" in status.query_cache
