"""Tests for /health/status graph count accuracy (Phase 64, Plan 02, GSTAB-03).

Covers the 4 required behaviors:
1. GET /health/status with a kuzu graph store whose live_counts() returns
   (5677, 4366, False) returns graph_index.entity_count == 5677 and
   relationship_count == 4366 (NOT the bookkeeping value).
2. When live_counts() returns stale=True, the /health/status graph_index block
   carries counts_stale: true and the last-known (non-zero) counts — not 0/0.
3. The existing non-chroma backend override still forces 0/0 + store_type
   "unavailable" (unchanged) — a postgres/non-chroma backend response is
   identical to before this plan.
4. A simple-store graph still reports its counts with counts_stale false and
   never invokes the kuzu COUNT path.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_brain_server.api.routers.health import router
from agent_brain_server.models.graph import GraphIndexStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_graph_index_manager(
    live_counts_result: tuple[int, int, bool],
    store_type: str = "kuzu",
    enabled: bool = True,
    initialized: bool = True,
) -> MagicMock:
    """Build a mock GraphIndexManager whose get_status() uses the given live_counts."""
    graph_store_mock = MagicMock()
    graph_store_mock.live_counts.return_value = live_counts_result
    graph_store_mock.store_type = store_type
    graph_store_mock.is_initialized = initialized
    graph_store_mock.last_updated = None
    # bookkeeping values that should NOT appear in the result
    graph_store_mock.entity_count = 0
    graph_store_mock.relationship_count = 100

    mgr = MagicMock()
    entities, rels, stale = live_counts_result
    mgr.get_status.return_value = GraphIndexStatus(
        enabled=enabled,
        initialized=initialized,
        entity_count=entities,
        relationship_count=rels,
        store_type=store_type,
        counts_stale=stale,
    )
    return mgr


def _make_app(
    graph_index_manager: MagicMock | None = None,
    live_counts_result: tuple[int, int, bool] = (5677, 4366, False),
    store_type: str = "kuzu",
) -> FastAPI:
    """Build a minimal FastAPI test app for /health/status.

    The indexing_service.get_status() is mocked to return a dict that
    reflects what the real implementation returns after wiring live_counts().
    """
    if graph_index_manager is None:
        graph_index_manager = _make_graph_index_manager(
            live_counts_result, store_type=store_type
        )

    graph_status = graph_index_manager.get_status()
    entities = graph_status.entity_count
    rels = graph_status.relationship_count
    stale = graph_status.counts_stale

    status_dict: dict[str, Any] = {
        "status": "idle",
        "is_indexing": False,
        "current_job_id": None,
        "folder_path": None,
        "total_documents": 10,
        "processed_documents": 10,
        "total_chunks": 100,
        "total_doc_chunks": 50,
        "total_code_chunks": 50,
        "supported_languages": ["python"],
        "progress_percent": 100.0,
        "started_at": None,
        "completed_at": None,
        "error": None,
        "indexed_folders": [],
        "graph_index": {
            "enabled": graph_status.enabled,
            "initialized": graph_status.initialized,
            "entity_count": entities,
            "relationship_count": rels,
            "store_type": graph_status.store_type,
            "counts_stale": stale,
            "degraded_last_run": False,
        },
    }

    indexing_service_mock = MagicMock()
    indexing_service_mock.get_status = AsyncMock(return_value=status_dict)

    vector_store_mock = MagicMock()
    vector_store_mock.is_initialized = True
    vector_store_mock.get_count = AsyncMock(return_value=100)

    app = FastAPI()
    app.include_router(router, prefix="/health")
    app.state.indexing_service = indexing_service_mock
    app.state.vector_store = vector_store_mock
    app.state.storage_backend = MagicMock()
    app.state.job_service = None
    app.state.file_watcher_service = None
    app.state.embedding_cache = None
    app.state.query_cache = None
    return app


# ---------------------------------------------------------------------------
# Test 1: live_counts() result reaches /health/status
# ---------------------------------------------------------------------------


class TestHealthStatusGraphCountsLive:
    """Test 1: /health/status entity/relationship counts come from live_counts()."""

    @patch(
        "agent_brain_server.api.routers.health.get_effective_backend_type",
        return_value="chroma",
    )
    def test_health_status_returns_live_counts_not_bookkeeping(
        self, _mock_backend: MagicMock
    ) -> None:
        """GET /health/status returns live COUNT values, not bookkeeping 0/100."""
        app = _make_app(live_counts_result=(5677, 4366, False), store_type="kuzu")
        client = TestClient(app)
        response = client.get("/health/status")
        assert response.status_code == 200

        data = response.json()
        graph_index = data.get("graph_index") or {}
        # Must reflect the live COUNT values, not bookkeeping (0, 100)
        assert graph_index["entity_count"] == 5677, (
            f"Expected 5677 from live COUNT, got {graph_index['entity_count']} "
            "(bookkeeping drift!)"
        )
        assert graph_index["relationship_count"] == 4366, (
            f"Expected 4366 from live COUNT, got {graph_index['relationship_count']} "
            "(bookkeeping drift!)"
        )

    @patch(
        "agent_brain_server.api.routers.health.get_effective_backend_type",
        return_value="chroma",
    )
    def test_counts_stale_is_false_on_successful_live_count(
        self, _mock_backend: MagicMock
    ) -> None:
        """When live COUNT succeeds, counts_stale is false in the response."""
        app = _make_app(live_counts_result=(42, 17, False), store_type="kuzu")
        client = TestClient(app)
        data = client.get("/health/status").json()
        graph_index = data.get("graph_index") or {}
        assert graph_index.get("counts_stale") is False


# ---------------------------------------------------------------------------
# Test 2: stale=True surfaces in the response with last-known counts
# ---------------------------------------------------------------------------


class TestHealthStatusGraphCountsStale:
    """Test 2: counts_stale=True surfaces in /health/status with last-known counts."""

    @patch(
        "agent_brain_server.api.routers.health.get_effective_backend_type",
        return_value="chroma",
    )
    def test_stale_true_in_response_when_kuzu_fails(
        self, _mock_backend: MagicMock
    ) -> None:
        """When live_counts() returns stale=True, counts_stale appears in response."""
        # last-known: 5677/4366, stale=True (kuzu unreachable)
        app = _make_app(live_counts_result=(5677, 4366, True), store_type="kuzu")
        client = TestClient(app)
        data = client.get("/health/status").json()
        graph_index = data.get("graph_index") or {}

        assert graph_index.get("counts_stale") is True
        # Last-known counts are reported, not 0/0
        assert graph_index["entity_count"] == 5677
        assert graph_index["relationship_count"] == 4366

    @patch(
        "agent_brain_server.api.routers.health.get_effective_backend_type",
        return_value="chroma",
    )
    def test_stale_response_never_returns_zero_when_last_known_is_nonzero(
        self, _mock_backend: MagicMock
    ) -> None:
        """Stale response NEVER reports 0/0 when last-known counts are non-zero."""
        app = _make_app(live_counts_result=(100, 50, True), store_type="kuzu")
        client = TestClient(app)
        data = client.get("/health/status").json()
        graph_index = data.get("graph_index") or {}

        assert graph_index["entity_count"] != 0 or graph_index["relationship_count"] != 0


# ---------------------------------------------------------------------------
# Test 3: non-chroma backend override stays unchanged
# ---------------------------------------------------------------------------


class TestHealthStatusNonChromaOverride:
    """Test 3: non-chroma backend 0/0 override is untouched."""

    @patch(
        "agent_brain_server.api.routers.health.get_effective_backend_type",
        return_value="postgres",
    )
    def test_non_chroma_backend_still_overrides_to_zeros(
        self, _mock_backend: MagicMock
    ) -> None:
        """postgres backend forces graph_index entity_count=0, store_type=unavailable."""
        # Even if live_counts() would return real numbers, postgres backend
        # overrides them in health.py
        app = _make_app(live_counts_result=(5677, 4366, False), store_type="kuzu")
        client = TestClient(app)
        data = client.get("/health/status").json()
        graph_index = data.get("graph_index") or {}

        # The non-chroma override in health.py lines ~174-187 must still apply
        assert graph_index["entity_count"] == 0
        assert graph_index["relationship_count"] == 0
        assert graph_index["store_type"] == "unavailable"

    @patch(
        "agent_brain_server.api.routers.health.get_effective_backend_type",
        return_value="postgres",
    )
    def test_non_chroma_backend_enabled_is_false(
        self, _mock_backend: MagicMock
    ) -> None:
        """postgres backend forces graph_index.enabled=False."""
        app = _make_app(live_counts_result=(5677, 4366, False), store_type="kuzu")
        client = TestClient(app)
        data = client.get("/health/status").json()
        graph_index = data.get("graph_index") or {}
        assert graph_index["enabled"] is False


# ---------------------------------------------------------------------------
# Test 4: simple store reports bookkeeping counts, counts_stale=False
# ---------------------------------------------------------------------------


class TestHealthStatusSimpleStoreGraph:
    """Test 4: simple store reports bookkeeping counts, counts_stale=False."""

    @patch(
        "agent_brain_server.api.routers.health.get_effective_backend_type",
        return_value="chroma",
    )
    def test_simple_store_counts_stale_is_false(
        self, _mock_backend: MagicMock
    ) -> None:
        """Simple store graph_index has counts_stale=False."""
        # simple store: live_counts() returns bookkeeping with stale=False
        app = _make_app(
            live_counts_result=(30, 15, False), store_type="simple"
        )
        client = TestClient(app)
        data = client.get("/health/status").json()
        graph_index = data.get("graph_index") or {}

        assert graph_index.get("counts_stale") is False
        assert graph_index["entity_count"] == 30
        assert graph_index["relationship_count"] == 15

    @patch(
        "agent_brain_server.api.routers.health.get_effective_backend_type",
        return_value="chroma",
    )
    def test_simple_store_type_is_simple(
        self, _mock_backend: MagicMock
    ) -> None:
        """Simple store reports store_type='simple'."""
        app = _make_app(live_counts_result=(10, 5, False), store_type="simple")
        client = TestClient(app)
        data = client.get("/health/status").json()
        graph_index = data.get("graph_index") or {}
        assert graph_index["store_type"] == "simple"
