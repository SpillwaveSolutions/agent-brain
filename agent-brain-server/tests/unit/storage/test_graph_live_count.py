"""Tests for GraphStoreManager.live_counts() (Phase 64, Plan 02, GSTAB-03).

Covers all 5 required behaviors:
1. live_counts() on a kuzu store with N/M entities/relationships returns (N, M, False)
   from a real COUNT(*) — bookkeeping values are ignored.
2. TTL cache: two calls within the TTL window issue only ONE underlying COUNT query;
   a call after TTL expires issues a fresh query.
3. store_type == "simple" never issues a kuzu COUNT — returns bookkeeping counts
   with stale=False and does NOT touch _kuzu_db.
4. kuzu COUNT raises (IndexError/RuntimeError/OSError) -> last-known counts returned
   with stale=True, NEVER 0/0 when a prior known count existed.
5. Regression guard for #184: bookkeeping says (0, 100) but live kuzu COUNT returns
   (5677, 4366) -> live_counts() returns (5677, 4366, False), NOT (0, 100).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agent_brain_server.storage.graph_store import (
    LIVE_COUNT_TTL_SECONDS,
    GraphStoreManager,
    reset_graph_store_manager,
)


# ---------------------------------------------------------------------------
# Fake kuzu infrastructure
# ---------------------------------------------------------------------------


class _FakeQueryResult:
    """Minimal stand-in for kuzu.QueryResult with a single scalar row."""

    def __init__(self, value: int) -> None:
        self._value = value
        self._consumed = False

    def has_next(self) -> bool:
        return not self._consumed

    def get_next(self) -> list[Any]:
        self._consumed = True
        return [self._value]


class _FakeConnection:
    """Stand-in for kuzu.Connection whose execute() returns known COUNTs.

    The first call returns entity_count, the second returns relationship_count,
    matching the live_counts() calling pattern:
      1. MATCH (n) RETURN COUNT(n)     -> entity_count
      2. MATCH ()-[r]->() RETURN COUNT(r) -> relationship_count
    """

    def __init__(self, entity_count: int, rel_count: int) -> None:
        self._entity_count = entity_count
        self._rel_count = rel_count
        self.execute_calls: list[str] = []

    def execute(self, cypher: str, params: dict[str, Any] | None = None) -> Any:
        self.execute_calls.append(cypher)
        if "COUNT(n)" in cypher:
            return _FakeQueryResult(self._entity_count)
        if "COUNT(r)" in cypher:
            return _FakeQueryResult(self._rel_count)
        raise ValueError(f"Unexpected cypher in fake connection: {cypher!r}")


class _RaisingConnection:
    """Stand-in for kuzu.Connection that raises on execute (kuzu unreachable)."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def execute(self, cypher: str, params: dict[str, Any] | None = None) -> Any:
        raise self._exc


def _make_fake_kuzu_module(conn_factory: Any) -> ModuleType:
    """Build a fake kuzu module whose Connection(...) calls conn_factory."""
    mod = ModuleType("kuzu")
    mod.Connection = conn_factory  # type: ignore[attr-defined]
    return mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:  # type: ignore[return]
    reset_graph_store_manager()
    yield
    reset_graph_store_manager()


@pytest.fixture
def persist_dir(tmp_path: Path) -> Path:
    d = tmp_path / "graph_index"
    d.mkdir()
    return d


def _make_kuzu_manager(
    persist_dir: Path,
    entity_count: int = 0,
    rel_count: int = 0,
    kuzu_db: Any = "fake_db_sentinel",
) -> GraphStoreManager:
    """Create a GraphStoreManager configured as a kuzu store with a fake _kuzu_db."""
    mgr = GraphStoreManager(persist_dir, store_type="kuzu")
    mgr._initialized = True
    mgr._graph_store = MagicMock()
    mgr._kuzu_db = kuzu_db
    mgr._entity_count = entity_count
    mgr._relationship_count = rel_count
    return mgr


# ---------------------------------------------------------------------------
# Test 1: Live COUNT returns real counts (not bookkeeping)
# ---------------------------------------------------------------------------


class TestLiveCountsFromKuzu:
    """Test 1: live_counts() on a kuzu store returns (N, M, False) from COUNT(*)."""

    def test_live_counts_returns_real_counts_not_bookkeeping(
        self, persist_dir: Path
    ) -> None:
        """live_counts() on a kuzu store returns counts from the kuzu COUNT query."""
        # Bookkeeping says 0/0 but the real graph has 42/17
        mgr = _make_kuzu_manager(persist_dir, entity_count=0, rel_count=0)
        fake_conn = _FakeConnection(entity_count=42, rel_count=17)
        fake_kuzu = _make_fake_kuzu_module(lambda db: fake_conn)

        with patch(
            "agent_brain_server.storage.graph_store._graphrag_enabled",
            return_value=True,
        ), patch.dict(sys.modules, {"kuzu": fake_kuzu}):
            entities, rels, stale = mgr.live_counts()

        assert entities == 42
        assert rels == 17
        assert stale is False

    def test_live_counts_ignores_bookkeeping_on_kuzu(
        self, persist_dir: Path
    ) -> None:
        """#184 regression: bookkeeping 0/100 but live 5677/4366 -> returns live."""
        mgr = _make_kuzu_manager(persist_dir, entity_count=0, rel_count=100)
        fake_conn = _FakeConnection(entity_count=5677, rel_count=4366)
        fake_kuzu = _make_fake_kuzu_module(lambda db: fake_conn)

        with patch(
            "agent_brain_server.storage.graph_store._graphrag_enabled",
            return_value=True,
        ), patch.dict(sys.modules, {"kuzu": fake_kuzu}):
            entities, rels, stale = mgr.live_counts()

        assert entities == 5677
        assert rels == 4366
        assert stale is False


# ---------------------------------------------------------------------------
# Test 2: TTL cache — second call within TTL uses cache; post-TTL re-queries
# ---------------------------------------------------------------------------


class TestLiveCountsTTLCache:
    """Test 2: TTL cache prevents repeated COUNT queries within the window."""

    def test_two_calls_within_ttl_issue_only_one_count_query(
        self, persist_dir: Path
    ) -> None:
        """Two live_counts() calls within the TTL issue only ONE kuzu execute pair."""
        mgr = _make_kuzu_manager(persist_dir)
        fake_conn = _FakeConnection(entity_count=10, rel_count=5)
        connection_call_count = 0

        def conn_factory(db: Any) -> _FakeConnection:
            nonlocal connection_call_count
            connection_call_count += 1
            return fake_conn

        fake_kuzu = _make_fake_kuzu_module(conn_factory)

        with patch(
            "agent_brain_server.storage.graph_store._graphrag_enabled",
            return_value=True,
        ), patch.dict(sys.modules, {"kuzu": fake_kuzu}):
            # First call — issues the COUNT queries
            result1 = mgr.live_counts()
            # Second call within TTL — should use cached result
            result2 = mgr.live_counts()

        assert result1 == (10, 5, False)
        assert result2 == (10, 5, False)
        # The connection was only created once (one pair of COUNT queries)
        assert connection_call_count == 1

    def test_call_after_ttl_expires_issues_fresh_query(
        self, persist_dir: Path
    ) -> None:
        """A live_counts() call after the TTL expires issues a fresh COUNT query."""
        mgr = _make_kuzu_manager(persist_dir)
        fake_conn1 = _FakeConnection(entity_count=10, rel_count=5)
        fake_conn2 = _FakeConnection(entity_count=20, rel_count=8)
        conns = [fake_conn1, fake_conn2]
        call_idx = 0

        def conn_factory(db: Any) -> _FakeConnection:
            nonlocal call_idx
            conn = conns[call_idx]
            call_idx += 1
            return conn

        fake_kuzu = _make_fake_kuzu_module(conn_factory)

        with patch(
            "agent_brain_server.storage.graph_store._graphrag_enabled",
            return_value=True,
        ), patch.dict(sys.modules, {"kuzu": fake_kuzu}):
            # First call — issues the COUNT queries
            result1 = mgr.live_counts()
            # Expire the cache by back-dating cached_at
            mgr._live_count_cached_at = (
                time.monotonic() - LIVE_COUNT_TTL_SECONDS - 1.0
            )
            # Second call after TTL — should issue fresh COUNT queries
            result2 = mgr.live_counts()

        assert result1 == (10, 5, False)
        assert result2 == (20, 8, False)
        assert call_idx == 2

    def test_ttl_constant_is_approximately_five_seconds(self) -> None:
        """LIVE_COUNT_TTL_SECONDS is defined and is approximately 5 seconds."""
        assert isinstance(LIVE_COUNT_TTL_SECONDS, float)
        # Allow anywhere from 3 to 30 seconds — the spec says "~5s"
        assert 3.0 <= LIVE_COUNT_TTL_SECONDS <= 30.0


# ---------------------------------------------------------------------------
# Test 3: Simple store never issues a kuzu COUNT
# ---------------------------------------------------------------------------


class TestLiveCountsSimpleStore:
    """Test 3: simple store returns bookkeeping counts, never touches _kuzu_db."""

    def test_simple_store_returns_bookkeeping_counts(
        self, persist_dir: Path
    ) -> None:
        """live_counts() on a simple store returns (entity_count, rel_count, False)."""
        mgr = GraphStoreManager(persist_dir, store_type="simple")
        mgr._initialized = True
        mgr._entity_count = 30
        mgr._relationship_count = 15
        mgr._kuzu_db = None  # simple stores never have a kuzu handle
        connection_call_count = 0

        def conn_factory(db: Any) -> _FakeConnection:
            nonlocal connection_call_count
            connection_call_count += 1
            return _FakeConnection(0, 0)

        fake_kuzu = _make_fake_kuzu_module(conn_factory)

        with patch(
            "agent_brain_server.storage.graph_store._graphrag_enabled",
            return_value=True,
        ), patch.dict(sys.modules, {"kuzu": fake_kuzu}):
            result = mgr.live_counts()

        assert result == (30, 15, False)
        # The kuzu module was never used
        assert connection_call_count == 0

    def test_simple_store_stale_is_false(self, persist_dir: Path) -> None:
        """stale is False for simple stores (no live COUNT to fail)."""
        mgr = GraphStoreManager(persist_dir, store_type="simple")
        mgr._initialized = True
        mgr._entity_count = 5
        mgr._relationship_count = 3

        with patch(
            "agent_brain_server.storage.graph_store._graphrag_enabled",
            return_value=True,
        ):
            _, _, stale = mgr.live_counts()

        assert stale is False


# ---------------------------------------------------------------------------
# Test 4: kuzu COUNT raises -> last-known counts with stale=True, never 0/0
# ---------------------------------------------------------------------------


class TestLiveCountsDegradedFallback:
    """Test 4: kuzu unreachable -> last-known counts with stale=True, NEVER 0/0."""

    @pytest.mark.parametrize(
        "exc_type",
        [IndexError, RuntimeError, OSError],
    )
    def test_kuzu_raises_returns_last_known_counts_stale(
        self, persist_dir: Path, exc_type: type[Exception]
    ) -> None:
        """When kuzu raises, last-known counts are returned with stale=True."""
        mgr = _make_kuzu_manager(persist_dir, entity_count=100, rel_count=50)
        # Populate the live-count cache first so there's a "last-known" value
        mgr._live_count_cache = (100, 50)
        mgr._live_count_cached_at = time.monotonic() - LIVE_COUNT_TTL_SECONDS - 1.0

        def raising_conn_factory(db: Any) -> _RaisingConnection:
            return _RaisingConnection(exc_type("simulated kuzu failure"))

        fake_kuzu = _make_fake_kuzu_module(raising_conn_factory)

        with patch(
            "agent_brain_server.storage.graph_store._graphrag_enabled",
            return_value=True,
        ), patch.dict(sys.modules, {"kuzu": fake_kuzu}):
            entities, rels, stale = mgr.live_counts()

        assert entities == 100
        assert rels == 50
        assert stale is True

    def test_kuzu_raises_never_returns_zero_when_prior_count_known(
        self, persist_dir: Path
    ) -> None:
        """NEVER returns 0/0 when a prior known count exists and kuzu fails."""
        mgr = _make_kuzu_manager(persist_dir, entity_count=5677, rel_count=4366)
        mgr._live_count_cache = (5677, 4366)
        mgr._live_count_cached_at = time.monotonic() - LIVE_COUNT_TTL_SECONDS - 1.0

        def raising_conn_factory(db: Any) -> _RaisingConnection:
            return _RaisingConnection(RuntimeError("kuzu db corrupted"))

        fake_kuzu = _make_fake_kuzu_module(raising_conn_factory)

        with patch(
            "agent_brain_server.storage.graph_store._graphrag_enabled",
            return_value=True,
        ), patch.dict(sys.modules, {"kuzu": fake_kuzu}):
            entities, rels, stale = mgr.live_counts()

        # Must NOT return 0/0 when prior counts are known
        assert entities != 0 or rels != 0
        assert stale is True

    def test_kuzu_raises_with_no_prior_cache_falls_back_to_bookkeeping(
        self, persist_dir: Path
    ) -> None:
        """When kuzu raises and no prior cache, falls back to bookkeeping counts."""
        mgr = _make_kuzu_manager(persist_dir, entity_count=200, rel_count=80)
        # No prior live cache — _live_count_cache stays None
        mgr._live_count_cache = None
        mgr._live_count_cached_at = 0.0

        def raising_conn_factory(db: Any) -> _RaisingConnection:
            return _RaisingConnection(IndexError("key not found"))

        fake_kuzu = _make_fake_kuzu_module(raising_conn_factory)

        with patch(
            "agent_brain_server.storage.graph_store._graphrag_enabled",
            return_value=True,
        ), patch.dict(sys.modules, {"kuzu": fake_kuzu}):
            entities, rels, stale = mgr.live_counts()

        # Falls back to bookkeeping values
        assert entities == 200
        assert rels == 80
        assert stale is True


# ---------------------------------------------------------------------------
# Test 5: #184 regression guard
# ---------------------------------------------------------------------------


class TestLiveCountsRegression184:
    """Test 5: #184 regression — bookkeeping 0/100, live 5677/4366 -> live wins."""

    def test_live_beats_bookkeeping_regression_184(self, persist_dir: Path) -> None:
        """#184 regression guard: live COUNT always wins over stale bookkeeping."""
        # This is the exact discrepancy from issue #184
        mgr = _make_kuzu_manager(persist_dir, entity_count=0, rel_count=100)
        # No prior live cache
        mgr._live_count_cache = None
        mgr._live_count_cached_at = 0.0

        fake_conn = _FakeConnection(entity_count=5677, rel_count=4366)
        fake_kuzu = _make_fake_kuzu_module(lambda db: fake_conn)

        with patch(
            "agent_brain_server.storage.graph_store._graphrag_enabled",
            return_value=True,
        ), patch.dict(sys.modules, {"kuzu": fake_kuzu}):
            entities, rels, stale = mgr.live_counts()

        # Must return the live COUNT values, not the bookkeeping (0, 100)
        assert entities == 5677, (
            f"Expected 5677 entities, got {entities} (bookkeeping drift!)"
        )
        assert rels == 4366, (
            f"Expected 4366 rels, got {rels} (bookkeeping drift!)"
        )
        assert stale is False

    def test_graphrag_disabled_returns_zeros(self, persist_dir: Path) -> None:
        """When graphrag is disabled, live_counts() returns (0, 0, False) fast."""
        mgr = _make_kuzu_manager(persist_dir, entity_count=999, rel_count=888)

        with patch(
            "agent_brain_server.storage.graph_store._graphrag_enabled",
            return_value=False,
        ):
            entities, rels, stale = mgr.live_counts()

        assert entities == 0
        assert rels == 0
        assert stale is False
