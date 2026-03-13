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
        assert QueryCacheService.is_cacheable_mode(mode) is True, (
            f"Expected {mode} to be cacheable"
        )


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
