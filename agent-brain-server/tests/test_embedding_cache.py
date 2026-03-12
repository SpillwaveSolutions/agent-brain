"""Unit tests for EmbeddingCacheService.

Tests cover:
1. make_cache_key determinism and SHA-256 format
2. get() returns None on miss, increments _misses
3. put() then get() returns cached embedding, increments _hits
4. In-memory LRU eviction when over max_mem_entries
5. clear() returns correct count and empties both layers
6. Provider fingerprint mismatch triggers auto-wipe
7. get_batch() returns dict of only hits
8. Float32 round-trip: values match within 1e-6 tolerance
"""

from __future__ import annotations

import hashlib
import math

import pytest

from agent_brain_server.services.embedding_cache import (
    EmbeddingCacheService,
    get_embedding_cache,
    reset_embedding_cache,
    set_embedding_cache,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_service(tmp_path, max_mem=10, max_disk_mb=10):
    """Create a fresh EmbeddingCacheService backed by a tmp SQLite file."""
    db_path = tmp_path / "test_cache.db"
    return EmbeddingCacheService(
        db_path=db_path,
        max_mem_entries=max_mem,
        max_disk_mb=max_disk_mb,
        persist_stats=False,
    )


FINGERPRINT = "openai:text-embedding-3-large:3072"


# ---------------------------------------------------------------------------
# Test 1: make_cache_key determinism and format
# ---------------------------------------------------------------------------


def test_make_cache_key_deterministic():
    """Same inputs always produce the same key."""
    key1 = EmbeddingCacheService.make_cache_key(
        "hello world", "openai", "text-embedding-3-large", 3072
    )
    key2 = EmbeddingCacheService.make_cache_key(
        "hello world", "openai", "text-embedding-3-large", 3072
    )
    assert key1 == key2


def test_make_cache_key_format():
    """Key starts with SHA-256 hex (64 chars) followed by :provider:model:dims."""
    text = "test content"
    key = EmbeddingCacheService.make_cache_key(text, "openai", "ada", 1536)
    expected_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert key == f"{expected_hash}:openai:ada:1536"
    # SHA-256 hex is exactly 64 chars
    parts = key.split(":")
    assert len(parts[0]) == 64


def test_make_cache_key_different_inputs_produce_different_keys():
    """Different text, provider, model, or dims produce distinct keys."""
    k1 = EmbeddingCacheService.make_cache_key("foo", "openai", "ada", 1536)
    k2 = EmbeddingCacheService.make_cache_key("bar", "openai", "ada", 1536)
    k3 = EmbeddingCacheService.make_cache_key("foo", "anthropic", "ada", 1536)
    k4 = EmbeddingCacheService.make_cache_key("foo", "openai", "large", 1536)
    k5 = EmbeddingCacheService.make_cache_key("foo", "openai", "ada", 3072)
    keys = {k1, k2, k3, k4, k5}
    assert len(keys) == 5, "All five keys must be distinct"


# ---------------------------------------------------------------------------
# Test 2: get() returns None on miss, increments _misses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_none_on_miss(tmp_path):
    """get() returns None for an unknown cache key and increments _misses."""
    svc = make_service(tmp_path)
    await svc.initialize(FINGERPRINT)

    result = await svc.get("nonexistent_key")

    assert result is None
    assert svc._misses == 1
    assert svc._hits == 0


# ---------------------------------------------------------------------------
# Test 3: put() then get() returns cached embedding, increments _hits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_and_get_round_trip(tmp_path):
    """put() then get() returns the same embedding; hits counter increments."""
    svc = make_service(tmp_path)
    await svc.initialize(FINGERPRINT)

    embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
    key = EmbeddingCacheService.make_cache_key("text", "openai", "ada", 5)
    await svc.put(key, embedding)

    result = await svc.get(key)

    assert result is not None
    assert len(result) == len(embedding)
    for a, b in zip(result, embedding):
        assert abs(a - b) < 1e-6, f"Mismatch: {a} vs {b}"
    assert svc._hits == 1
    assert svc._misses == 0


@pytest.mark.asyncio
async def test_get_increments_hits_on_memory_hit(tmp_path):
    """Repeated get() on a key already in _mem increments _hits each time."""
    svc = make_service(tmp_path)
    await svc.initialize(FINGERPRINT)

    embedding = [1.0, 2.0, 3.0]
    key = EmbeddingCacheService.make_cache_key("x", "p", "m", 3)
    await svc.put(key, embedding)

    # First get (from disk or memory)
    await svc.get(key)
    # Second get (from memory)
    await svc.get(key)

    assert svc._hits == 2


# ---------------------------------------------------------------------------
# Test 4: In-memory LRU eviction when over max_mem_entries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lru_eviction_when_over_max_mem_entries(tmp_path):
    """With max_mem_entries=2, inserting 3 items evicts the oldest from _mem."""
    svc = make_service(tmp_path, max_mem=2)
    await svc.initialize(FINGERPRINT)

    k1 = EmbeddingCacheService.make_cache_key("a", "p", "m", 2)
    k2 = EmbeddingCacheService.make_cache_key("b", "p", "m", 2)
    k3 = EmbeddingCacheService.make_cache_key("c", "p", "m", 2)

    await svc.put(k1, [1.0, 1.0])
    await svc.put(k2, [2.0, 2.0])
    await svc.put(k3, [3.0, 3.0])

    # After 3 inserts with max_mem=2, k1 (oldest) must be evicted from _mem
    assert len(svc._mem) == 2
    assert k1 not in svc._mem, "k1 (oldest) should have been evicted"
    assert k2 in svc._mem
    assert k3 in svc._mem


@pytest.mark.asyncio
async def test_lru_eviction_does_not_lose_data_from_disk(tmp_path):
    """LRU eviction from memory does not delete the entry from disk."""
    svc = make_service(tmp_path, max_mem=2)
    await svc.initialize(FINGERPRINT)

    k1 = EmbeddingCacheService.make_cache_key("a", "p", "m", 2)
    k2 = EmbeddingCacheService.make_cache_key("b", "p", "m", 2)
    k3 = EmbeddingCacheService.make_cache_key("c", "p", "m", 2)

    await svc.put(k1, [1.0, 2.0])
    await svc.put(k2, [2.0, 3.0])
    await svc.put(k3, [3.0, 4.0])

    # k1 should have been evicted from memory but still be on disk
    assert k1 not in svc._mem
    result = await svc.get(k1)
    assert result is not None, "k1 should still be retrievable from disk"
    assert abs(result[0] - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# Test 5: clear() empties both layers and returns correct counts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_empties_both_layers(tmp_path):
    """clear() empties _mem and the SQLite table, returning correct count."""
    svc = make_service(tmp_path)
    await svc.initialize(FINGERPRINT)

    for i in range(5):
        key = EmbeddingCacheService.make_cache_key(f"text{i}", "p", "m", 3)
        await svc.put(key, [float(i), float(i), float(i)])

    disk_stats_before = await svc.get_disk_stats()
    assert disk_stats_before["entry_count"] == 5

    count, size_bytes = await svc.clear()

    assert count == 5
    assert size_bytes > 0
    assert len(svc._mem) == 0
    assert svc._hits == 0
    assert svc._misses == 0

    disk_stats_after = await svc.get_disk_stats()
    assert disk_stats_after["entry_count"] == 0


@pytest.mark.asyncio
async def test_clear_returns_zero_for_empty_cache(tmp_path):
    """clear() returns (0, ...) when called on an already empty cache."""
    svc = make_service(tmp_path)
    await svc.initialize(FINGERPRINT)

    count, _ = await svc.clear()
    assert count == 0


# ---------------------------------------------------------------------------
# Test 6: Provider fingerprint mismatch triggers auto-wipe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provider_fingerprint_mismatch_clears_cache(tmp_path):
    """Initializing with a different fingerprint wipes all existing entries."""
    db_path = tmp_path / "fp_test.db"

    # First init with fingerprint A; insert an entry
    svc_a = EmbeddingCacheService(db_path=db_path, max_mem_entries=100, max_disk_mb=10)
    await svc_a.initialize("openai:small:1536")

    key = EmbeddingCacheService.make_cache_key("data", "openai", "small", 1536)
    await svc_a.put(key, [0.5, 0.6, 0.7])

    disk_stats = await svc_a.get_disk_stats()
    assert disk_stats["entry_count"] == 1

    # Re-initialize with a different fingerprint B
    svc_b = EmbeddingCacheService(db_path=db_path, max_mem_entries=100, max_disk_mb=10)
    await svc_b.initialize("openai:large:3072")  # different fingerprint

    # All entries should be wiped
    disk_stats_after = await svc_b.get_disk_stats()
    assert (
        disk_stats_after["entry_count"] == 0
    ), "All cached embeddings should be wiped on fingerprint mismatch"


@pytest.mark.asyncio
async def test_provider_fingerprint_same_no_wipe(tmp_path):
    """Initializing with the same fingerprint preserves existing entries."""
    db_path = tmp_path / "fp_same.db"

    svc_a = EmbeddingCacheService(db_path=db_path, max_mem_entries=100, max_disk_mb=10)
    await svc_a.initialize("openai:large:3072")

    key = EmbeddingCacheService.make_cache_key("data", "openai", "large", 3072)
    await svc_a.put(key, [1.0, 2.0, 3.0])

    # Re-initialize with SAME fingerprint
    svc_b = EmbeddingCacheService(db_path=db_path, max_mem_entries=100, max_disk_mb=10)
    await svc_b.initialize("openai:large:3072")

    disk_stats = await svc_b.get_disk_stats()
    assert (
        disk_stats["entry_count"] == 1
    ), "Entry should survive same-fingerprint re-init"


# ---------------------------------------------------------------------------
# Test 7: get_batch() returns dict of only hits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_batch_returns_only_hits(tmp_path):
    """get_batch() includes only cache hits; misses are absent from result."""
    svc = make_service(tmp_path)
    await svc.initialize(FINGERPRINT)

    k_hit1 = EmbeddingCacheService.make_cache_key("alpha", "p", "m", 3)
    k_hit2 = EmbeddingCacheService.make_cache_key("beta", "p", "m", 3)
    k_miss = EmbeddingCacheService.make_cache_key("gamma", "p", "m", 3)

    await svc.put(k_hit1, [1.0, 2.0, 3.0])
    await svc.put(k_hit2, [4.0, 5.0, 6.0])

    result = await svc.get_batch([k_hit1, k_miss, k_hit2])

    assert k_hit1 in result
    assert k_hit2 in result
    assert k_miss not in result
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_batch_empty_input(tmp_path):
    """get_batch([]) returns an empty dict without touching the DB."""
    svc = make_service(tmp_path)
    await svc.initialize(FINGERPRINT)

    result = await svc.get_batch([])
    assert result == {}


@pytest.mark.asyncio
async def test_get_batch_increments_hits_and_misses(tmp_path):
    """get_batch() correctly increments hit/miss counters."""
    svc = make_service(tmp_path)
    await svc.initialize(FINGERPRINT)

    k1 = EmbeddingCacheService.make_cache_key("x", "p", "m", 2)
    k2 = EmbeddingCacheService.make_cache_key("y", "p", "m", 2)  # miss

    await svc.put(k1, [1.0, 2.0])

    await svc.get_batch([k1, k2])

    assert svc._hits == 1  # k1 is a hit
    assert svc._misses == 1  # k2 is a miss


# ---------------------------------------------------------------------------
# Test 8: Float32 round-trip within 1e-6 tolerance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_float32_round_trip(tmp_path):
    """Stored and retrieved embedding values match within 1e-6 tolerance."""
    svc = make_service(tmp_path)
    await svc.initialize(FINGERPRINT)

    # Use a realistic 3072-dim-like embedding (but smaller for test speed)
    dims = 64
    embedding = [float(i) / dims for i in range(dims)]
    key = EmbeddingCacheService.make_cache_key("round_trip", "openai", "large", dims)
    await svc.put(key, embedding)

    # Clear memory to force disk read
    svc._mem.clear()

    result = await svc.get(key)

    assert result is not None
    assert len(result) == dims
    for orig, recovered in zip(embedding, result):
        assert (
            abs(orig - recovered) < 1e-6
        ), f"float32 round-trip failed: original={orig}, recovered={recovered}"


@pytest.mark.asyncio
async def test_float32_cosine_similarity_preserved(tmp_path):
    """Cosine similarity between original and recovered embedding is ~1.0."""
    svc = make_service(tmp_path)
    await svc.initialize(FINGERPRINT)

    dims = 128
    import random

    random.seed(42)
    embedding = [random.gauss(0.0, 1.0) for _ in range(dims)]
    key = EmbeddingCacheService.make_cache_key("cosine_test", "p", "m", dims)
    await svc.put(key, embedding)

    svc._mem.clear()
    result = await svc.get(key)

    assert result is not None
    dot = sum(a * b for a, b in zip(embedding, result))
    mag_a = math.sqrt(sum(x**2 for x in embedding))
    mag_b = math.sqrt(sum(x**2 for x in result))
    cos_sim = dot / (mag_a * mag_b)
    assert abs(cos_sim - 1.0) < 1e-6, f"Cosine similarity too low: {cos_sim}"


# ---------------------------------------------------------------------------
# Test: get_stats() and get_disk_stats()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_stats_initial(tmp_path):
    """get_stats() returns zero counters on a fresh cache."""
    svc = make_service(tmp_path)
    await svc.initialize(FINGERPRINT)

    stats = svc.get_stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert stats["hit_rate"] == 0.0
    assert stats["mem_entries"] == 0


@pytest.mark.asyncio
async def test_get_disk_stats(tmp_path):
    """get_disk_stats() returns accurate entry count and positive size_bytes."""
    svc = make_service(tmp_path)
    await svc.initialize(FINGERPRINT)

    for i in range(3):
        key = EmbeddingCacheService.make_cache_key(f"t{i}", "p", "m", 4)
        await svc.put(key, [float(i)] * 4)

    disk_stats = await svc.get_disk_stats()
    assert disk_stats["entry_count"] == 3
    assert disk_stats["size_bytes"] > 0


# ---------------------------------------------------------------------------
# Test: Singleton functions
# ---------------------------------------------------------------------------


def test_singleton_get_returns_none_before_set():
    """get_embedding_cache() returns None before set_embedding_cache is called."""
    reset_embedding_cache()
    assert get_embedding_cache() is None


def test_singleton_set_and_get(tmp_path):
    """set_embedding_cache() stores instance; get_embedding_cache() retrieves it."""
    reset_embedding_cache()
    svc = make_service(tmp_path)
    set_embedding_cache(svc)
    assert get_embedding_cache() is svc
    reset_embedding_cache()


def test_singleton_reset():
    """reset_embedding_cache() clears the global instance."""
    reset_embedding_cache()
    assert get_embedding_cache() is None


# ---------------------------------------------------------------------------
# Test: Health endpoint omits embedding_cache when cache is empty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_status_omits_embedding_cache_when_empty(tmp_path):
    """GET /health/status omits 'embedding_cache' key for fresh/empty cache.

    Regression test for Issue 11: response_model=IndexingStatus was
    re-serializing the dict through Pydantic and re-adding the field as null.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from fastapi.testclient import TestClient

    # Create a real (empty) cache service
    svc = make_service(tmp_path)
    await svc.initialize(FINGERPRINT)

    with (
        patch(
            "agent_brain_server.storage.get_vector_store",
            return_value=MagicMock(is_initialized=True),
        ),
        patch(
            "agent_brain_server.storage.initialize_vector_store",
            new_callable=AsyncMock,
        ),
        patch(
            "agent_brain_server.indexing.get_embedding_generator",
            return_value=AsyncMock(),
        ),
        patch(
            "agent_brain_server.indexing.get_bm25_manager",
            return_value=MagicMock(is_initialized=True),
        ),
    ):
        from agent_brain_server.api.main import app
        from agent_brain_server.services import IndexingService, QueryService

        mock_vs = MagicMock(is_initialized=True)
        mock_vs.get_count = AsyncMock(return_value=0)
        mock_bm25 = MagicMock(is_initialized=True)

        app.state.vector_store = mock_vs
        app.state.bm25_manager = mock_bm25
        app.state.storage_backend = MagicMock(
            is_initialized=True,
            get_count=AsyncMock(return_value=0),
        )
        app.state.indexing_service = IndexingService(
            vector_store=mock_vs, bm25_manager=mock_bm25
        )
        app.state.query_service = QueryService(
            vector_store=mock_vs,
            embedding_generator=AsyncMock(),
            bm25_manager=mock_bm25,
        )
        app.state.mode = "project"
        app.state.instance_id = None
        app.state.project_id = None
        app.state.active_projects = None
        app.state.job_service = None
        app.state.file_watcher_service = None
        # Empty cache — 0 entries → should be omitted
        app.state.embedding_cache = svc

        with TestClient(app) as client:
            resp = client.get("/health/status")
            assert resp.status_code == 200
            data = resp.json()
            assert "embedding_cache" not in data, (
                "embedding_cache should be omitted when cache is empty, "
                f"but got: {data.get('embedding_cache')}"
            )
