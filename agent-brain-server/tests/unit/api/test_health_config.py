"""Phase 2 TDD: ``GET /health/config`` endpoint.

Maps to plan §12.3 acceptance #16 — endpoint returns valid ``ConfigStatus``
JSON with the documented fields and reflects ``AGENT_BRAIN_STORAGE_BACKEND``
env override.

Mirrors the conventions in ``tests/unit/api/test_health_postgres.py`` so a
future reader can recognize the pattern. RED until Phase 2 adds the route.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_brain_server.api.routers.health import router


def _create_app(
    *,
    graph_enabled: bool = False,
    watcher_running: bool = False,
    embedding_model: str = "text-embedding-3-large",
    reranker_enabled: bool = False,
    rerank_model: str | None = None,
    graph_extractor: str | None = None,
) -> FastAPI:
    """Create a stub FastAPI app with ``app.state`` populated for /health/config.

    Mirrors ``_create_app`` in ``test_health_postgres.py``. We attach mocks
    to ``app.state`` so the endpoint can read configuration without booting
    the real services.
    """
    app = FastAPI()
    app.include_router(router, prefix="/health")

    indexing_service = MagicMock()
    indexing_service.is_graph_enabled = MagicMock(return_value=graph_enabled)
    indexing_service.watcher_running = watcher_running

    app.state.indexing_service = indexing_service
    app.state.embedding_model = embedding_model
    app.state.reranker_enabled = reranker_enabled
    app.state.rerank_model = rerank_model
    app.state.graph_extractor = graph_extractor

    return app


class TestHealthConfigEndpoint:
    """GET /health/config should expose what's configured (not what's running)."""

    @patch(
        "agent_brain_server.api.routers.health.get_effective_backend_type",
        return_value="chroma",
    )
    def test_returns_200(self, _mock_backend: MagicMock) -> None:
        app = _create_app()
        client = TestClient(app)
        response = client.get("/health/config")
        assert response.status_code == 200

    @patch(
        "agent_brain_server.api.routers.health.get_effective_backend_type",
        return_value="chroma",
    )
    def test_body_matches_documented_keys(self, _mock_backend: MagicMock) -> None:
        app = _create_app()
        client = TestClient(app)
        response = client.get("/health/config")
        data: dict[str, Any] = response.json()
        # Plan §4.3 declares these top-level keys
        assert set(data.keys()) == {
            "storage_backend",
            "stores",
            "reranker_enabled",
            "embedding_model",
            "rerank_model",
            "graph_extractor",
            "watcher_running",
        }
        assert set(data["stores"].keys()) == {"vector", "bm25", "graph"}

    @patch(
        "agent_brain_server.api.routers.health.get_effective_backend_type",
        return_value="chroma",
    )
    def test_default_storage_backend_is_chroma(self, _mock_backend: MagicMock) -> None:
        app = _create_app()
        client = TestClient(app)
        response = client.get("/health/config")
        assert response.json()["storage_backend"] == "chroma"

    @patch(
        "agent_brain_server.api.routers.health.get_effective_backend_type",
        return_value="postgres",
    )
    def test_storage_backend_reflects_env_override(
        self, _mock_backend: MagicMock
    ) -> None:
        """``AGENT_BRAIN_STORAGE_BACKEND=postgres`` reaches the endpoint via
        ``get_effective_backend_type`` (the same function /health/postgres uses).
        """
        app = _create_app()
        client = TestClient(app)
        response = client.get("/health/config")
        assert response.json()["storage_backend"] == "postgres"

    @patch(
        "agent_brain_server.api.routers.health.get_effective_backend_type",
        return_value="chroma",
    )
    def test_stores_vector_and_bm25_always_true_in_v1(
        self, _mock_backend: MagicMock
    ) -> None:
        """v1 always runs both vector and BM25 alongside each other."""
        app = _create_app()
        client = TestClient(app)
        response = client.get("/health/config")
        stores = response.json()["stores"]
        assert stores["vector"] is True
        assert stores["bm25"] is True

    @patch(
        "agent_brain_server.api.routers.health.get_effective_backend_type",
        return_value="chroma",
    )
    def test_stores_graph_reflects_indexing_service(
        self, _mock_backend: MagicMock
    ) -> None:
        """When graph indexing is enabled, ``stores.graph`` is True."""
        app_off = _create_app(graph_enabled=False)
        app_on = _create_app(graph_enabled=True)

        client_off = TestClient(app_off)
        client_on = TestClient(app_on)

        assert client_off.get("/health/config").json()["stores"]["graph"] is False
        assert client_on.get("/health/config").json()["stores"]["graph"] is True

    @patch(
        "agent_brain_server.api.routers.health.get_effective_backend_type",
        return_value="chroma",
    )
    def test_reranker_fields_round_trip(self, _mock_backend: MagicMock) -> None:
        app = _create_app(reranker_enabled=True, rerank_model="bge-reranker-v2-m3")
        client = TestClient(app)
        data = client.get("/health/config").json()
        assert data["reranker_enabled"] is True
        assert data["rerank_model"] == "bge-reranker-v2-m3"

    @patch(
        "agent_brain_server.api.routers.health.get_effective_backend_type",
        return_value="chroma",
    )
    def test_graph_extractor_optional(self, _mock_backend: MagicMock) -> None:
        app = _create_app(graph_enabled=True, graph_extractor="anthropic")
        client = TestClient(app)
        data = client.get("/health/config").json()
        assert data["graph_extractor"] == "anthropic"

    @patch(
        "agent_brain_server.api.routers.health.get_effective_backend_type",
        return_value="chroma",
    )
    def test_watcher_running_reflects_indexing_service(
        self, _mock_backend: MagicMock
    ) -> None:
        app = _create_app(watcher_running=True)
        client = TestClient(app)
        assert client.get("/health/config").json()["watcher_running"] is True
