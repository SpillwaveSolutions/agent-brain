"""FastAPI integration tests for ``GET /graph/entity/{type}/{id}``.

Covers the four response paths locked by Phase 50 design doc §2.4 / CONTEXT
decision B:

- 200: GraphRAG enabled, valid type, existing entity → ``GraphEntityRecord``
- 503: GraphRAG disabled → ``error: graphrag_disabled`` + hint
- 503: Kuzu unhealthy → ``error: kuzu_unavailable`` + hint (#178)
- 400: unknown entity type → ``error: invalid_entity_type`` + ``valid_types``
- 404: type valid, no matching entity → ``error: entity_not_found``

These tests pin the FastAPI surface only — the graph-store contract is
checked by ``tests/unit/storage/test_get_entity_by_id.py``. We mount only
the new graph router (rather than the full app) to keep the test fast and
isolated from the heavy lifespan.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_brain_server.models import (
    ENTITY_TYPES,
    GraphEntityRecord,
    GraphEntityRecordNeighbor,
    GraphEntityRecordNeighbors,
    GraphEntityRecordNode,
)
from agent_brain_server.storage.graph_store import KuzuUnavailableError


@pytest.fixture
def app() -> FastAPI:
    """Build a minimal FastAPI app mounting only the graph router.

    Mirrors how ``main.py`` registers it (``prefix='/graph'``).
    """
    from agent_brain_server.api.routers.graph import router as graph_router

    app = FastAPI()
    app.include_router(graph_router, prefix="/graph", tags=["Graph"])
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# 503: GraphRAG disabled — distinct from 404 (config state, not data state).
# ---------------------------------------------------------------------------


class TestGraphRAGDisabled:
    def test_returns_503_with_structured_body(self, client: TestClient) -> None:
        with patch(
            "agent_brain_server.api.routers.graph._graphrag_enabled",
            return_value=False,
        ):
            r = client.get("/graph/entity/Function/anything")
        assert r.status_code == 503
        body = r.json()
        assert body["detail"]["error"] == "graphrag_disabled"
        assert "hint" in body["detail"]
        assert "graphrag.enabled" in body["detail"]["hint"]

    def test_503_takes_precedence_over_invalid_type(self, client: TestClient) -> None:
        """Decision B: disabled-state is checked BEFORE type validation.

        Otherwise an operator could distinguish "graphrag is off" from
        "your type is bogus" — minor info leak, but spec is unambiguous.
        """
        with patch(
            "agent_brain_server.api.routers.graph._graphrag_enabled",
            return_value=False,
        ):
            r = client.get("/graph/entity/NotARealType/anything")
        assert r.status_code == 503
        assert r.json()["detail"]["error"] == "graphrag_disabled"


# ---------------------------------------------------------------------------
# 400: invalid entity type — must list the SCHEMA-01 vocabulary.
# ---------------------------------------------------------------------------


class TestInvalidEntityType:
    def test_unknown_type_returns_400(self, client: TestClient) -> None:
        with patch(
            "agent_brain_server.api.routers.graph._graphrag_enabled",
            return_value=True,
        ):
            r = client.get("/graph/entity/NotARealType/foo")
        assert r.status_code == 400
        body = r.json()["detail"]
        assert body["error"] == "invalid_entity_type"
        assert body["type"] == "NotARealType"
        assert isinstance(body["valid_types"], list)

    def test_valid_types_matches_schema_01_vocabulary(self, client: TestClient) -> None:
        """The 400 body's ``valid_types`` is the SCHEMA-01 vocabulary.

        Drift guard: if SCHEMA-01 grows from 17 to 18 entity types, this
        test passes automatically (both sides come from ``ENTITY_TYPES``).
        """
        with patch(
            "agent_brain_server.api.routers.graph._graphrag_enabled",
            return_value=True,
        ):
            r = client.get("/graph/entity/NotARealType/foo")
        body = r.json()["detail"]
        assert set(body["valid_types"]) == set(ENTITY_TYPES)
        # Currently 17 per SCHEMA-01 — this assertion will need to flip
        # alongside the vocabulary if the schema grows.
        assert len(ENTITY_TYPES) == 17

    def test_case_sensitive_validation(self, client: TestClient) -> None:
        """``function`` (lowercase) is NOT one of the 17 — must 400.

        We deliberately don't auto-normalize at the endpoint boundary so
        URLs are unambiguous: each (type, id) maps to exactly one entity.
        Normalization happens upstream in the extraction pipeline.
        """
        with patch(
            "agent_brain_server.api.routers.graph._graphrag_enabled",
            return_value=True,
        ):
            r = client.get("/graph/entity/function/foo")
        assert r.status_code == 400
        assert r.json()["detail"]["error"] == "invalid_entity_type"


# ---------------------------------------------------------------------------
# 200 / 404 — the happy paths and entity-not-found.
# ---------------------------------------------------------------------------


class TestEntityLookup:
    @staticmethod
    def _mock_graph_manager(record: GraphEntityRecord | None) -> MagicMock:
        """Build a mock GraphStoreManager that returns the given record."""
        mgr = MagicMock()
        mgr.is_initialized = True
        mgr.get_entity_by_id.return_value = record
        return mgr

    def test_200_returns_graph_entity_record(self, client: TestClient) -> None:
        record = GraphEntityRecord(
            entity=GraphEntityRecordNode(
                type="Function",
                id="authenticate_user",
                properties={"module": "auth.handlers"},
            ),
            neighbors=GraphEntityRecordNeighbors(
                incoming=[
                    GraphEntityRecordNeighbor(
                        type="Class",
                        id="AuthController",
                        predicate="calls",
                        properties={},
                    )
                ],
                outgoing=[
                    GraphEntityRecordNeighbor(
                        type="Function",
                        id="verify_password",
                        predicate="calls",
                        properties={"source_chunk_id": "chunk_42"},
                    )
                ],
            ),
        )
        mgr = self._mock_graph_manager(record)
        with (
            patch(
                "agent_brain_server.api.routers.graph._graphrag_enabled",
                return_value=True,
            ),
            patch(
                "agent_brain_server.api.routers.graph.get_graph_store_manager",
                return_value=mgr,
            ),
        ):
            r = client.get("/graph/entity/Function/authenticate_user")

        assert r.status_code == 200
        body = r.json()
        # Top-level shape locked by design doc §2.4.
        assert set(body.keys()) == {"entity", "neighbors"}
        assert body["entity"]["type"] == "Function"
        assert body["entity"]["id"] == "authenticate_user"
        assert body["entity"]["properties"]["module"] == "auth.handlers"
        assert set(body["neighbors"].keys()) == {"incoming", "outgoing"}
        assert len(body["neighbors"]["incoming"]) == 1
        assert len(body["neighbors"]["outgoing"]) == 1
        assert body["neighbors"]["incoming"][0]["predicate"] == "calls"
        # Empty arrays come through as [] not None.
        for neighbor in body["neighbors"]["incoming"] + body["neighbors"]["outgoing"]:
            assert set(neighbor.keys()) == {"type", "id", "predicate", "properties"}

        # Verify the manager was called with the URL path components.
        mgr.get_entity_by_id.assert_called_once_with("Function", "authenticate_user")

    def test_404_entity_not_found(self, client: TestClient) -> None:
        mgr = self._mock_graph_manager(None)
        with (
            patch(
                "agent_brain_server.api.routers.graph._graphrag_enabled",
                return_value=True,
            ),
            patch(
                "agent_brain_server.api.routers.graph.get_graph_store_manager",
                return_value=mgr,
            ),
        ):
            r = client.get("/graph/entity/Function/does_not_exist")
        assert r.status_code == 404
        body = r.json()["detail"]
        assert body["error"] == "entity_not_found"
        assert body["type"] == "Function"
        assert body["id"] == "does_not_exist"


# ---------------------------------------------------------------------------
# 503 kuzu_unavailable — the #178 path (Kuzu corruption mid-request).
# ---------------------------------------------------------------------------


class TestKuzuUnavailable:
    def test_kuzu_unavailable_during_lookup_returns_503(
        self, client: TestClient
    ) -> None:
        mgr = MagicMock()
        mgr.is_initialized = True
        mgr.get_entity_by_id.side_effect = KuzuUnavailableError(
            "Kuzu corrupted mid-write"
        )
        with (
            patch(
                "agent_brain_server.api.routers.graph._graphrag_enabled",
                return_value=True,
            ),
            patch(
                "agent_brain_server.api.routers.graph.get_graph_store_manager",
                return_value=mgr,
            ),
        ):
            r = client.get("/graph/entity/Function/foo")
        assert r.status_code == 503
        body = r.json()["detail"]
        assert body["error"] == "kuzu_unavailable"
        # The hint must reference the operator workaround (#178 R1).
        assert "graphrag.store_type=simple" in body["hint"]

    def test_kuzu_unavailable_during_init_returns_503(self, client: TestClient) -> None:
        """Lazy-init path: if the first request triggers init and Kuzu
        raises, we surface 503 rather than crashing the worker."""
        mgr = MagicMock()
        mgr.is_initialized = False
        mgr.initialize.side_effect = KuzuUnavailableError("init failed")
        with (
            patch(
                "agent_brain_server.api.routers.graph._graphrag_enabled",
                return_value=True,
            ),
            patch(
                "agent_brain_server.api.routers.graph.get_graph_store_manager",
                return_value=mgr,
            ),
        ):
            r = client.get("/graph/entity/Function/foo")
        assert r.status_code == 503
        body = r.json()["detail"]
        assert body["error"] == "kuzu_unavailable"


# ---------------------------------------------------------------------------
# Path-parameter robustness — special characters in the entity id.
# ---------------------------------------------------------------------------


class TestPathHandling:
    def test_url_encoded_id_round_trips(self, client: TestClient) -> None:
        """Entity ids with URL-encodable chars (``.``, ``::``, etc.) pass
        through to the manager unchanged."""
        mgr = MagicMock()
        mgr.is_initialized = True
        mgr.get_entity_by_id.return_value = None
        with (
            patch(
                "agent_brain_server.api.routers.graph._graphrag_enabled",
                return_value=True,
            ),
            patch(
                "agent_brain_server.api.routers.graph.get_graph_store_manager",
                return_value=mgr,
            ),
        ):
            # ``Foo.bar::baz`` is a plausible module-qualified entity id.
            r = client.get("/graph/entity/Function/Foo.bar%3A%3Abaz")
        assert r.status_code == 404  # not found is fine — id was decoded
        mgr.get_entity_by_id.assert_called_once_with("Function", "Foo.bar::baz")


# ---------------------------------------------------------------------------
# OpenAPI: the route appears in the schema with the right shape.
# ---------------------------------------------------------------------------


class TestOpenAPI:
    def test_route_in_openapi(self, app: FastAPI) -> None:
        spec: dict[str, Any] = app.openapi()
        paths = spec.get("paths", {})
        assert "/graph/entity/{entity_type}/{entity_id}" in paths
        op = paths["/graph/entity/{entity_type}/{entity_id}"]["get"]
        # Response schema references the locked GraphEntityRecord model.
        ok = op["responses"]["200"]
        ref = ok["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("/GraphEntityRecord")

    def test_graph_entity_record_components(self, app: FastAPI) -> None:
        """The locked model + its nested neighbor model appear in components."""
        spec: dict[str, Any] = app.openapi()
        schemas = spec["components"]["schemas"]
        assert "GraphEntityRecord" in schemas
        assert "GraphEntityRecordNeighbor" in schemas
        assert "GraphEntityRecordNeighbors" in schemas
        assert "GraphEntityRecordNode" in schemas
