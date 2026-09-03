"""FastAPI tests for ``POST /graph/project`` and ``DELETE /graph/project``.

Pins the #235 surface: additive endpoint, 503 when GraphRAG is off,
400 on unknown types / dangling relation endpoints, isolated-worker
crash maps to 503 ``kuzu_unavailable`` (#178), and namespaced OKF types
are accepted. The store contract is covered by
``tests/unit/storage/test_graph_project.py``; isolation by
``tests/indexing/test_graph_project_isolation.py``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_brain_server.storage.graph_errors import GraphBuildFailedError


@pytest.fixture
def app() -> FastAPI:
    from agent_brain_server.api.routers.graph import router as graph_router

    app = FastAPI()
    app.include_router(graph_router, prefix="/graph", tags=["Graph"])
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


_OKF_PAYLOAD: dict[str, Any] = {
    "entities": [
        {
            "type": "okf:Finding",
            "id": "finding.loop-policy.0001",
            "properties": {"status": "accepted"},
        },
        {
            "type": "okf:Claim",
            "id": "claim.loop-policy.0003",
            "properties": {},
        },
        {
            "type": "okf:Evidence",
            "id": "evidence.loop-policy.0007",
            "properties": {},
        },
    ],
    "relations": [
        {
            "src": "finding.loop-policy.0001",
            "predicate": "asserts",
            "dst": "claim.loop-policy.0003",
        },
        {
            "src": "claim.loop-policy.0003",
            "predicate": "evidenced_by",
            "dst": "evidence.loop-policy.0007",
        },
    ],
    "source_tag": "research-graph",
}


def _ok_counts(**overrides: int) -> dict[str, int]:
    counts = {
        "entities_upserted": 3,
        "relations_upserted": 2,
        "entities_deleted": 0,
        "relations_deleted": 0,
    }
    counts.update(overrides)
    return counts


class TestProjectDisabled:
    def test_returns_503_when_graphrag_off(self, client: TestClient) -> None:
        with patch(
            "agent_brain_server.api.routers.graph._graphrag_enabled",
            return_value=False,
        ):
            r = client.post("/graph/project", json=_OKF_PAYLOAD)
        assert r.status_code == 503
        assert r.json()["detail"]["error"] == "graphrag_disabled"


class TestProjectValidation:
    def test_unknown_unnamespaced_type_is_422(self, client: TestClient) -> None:
        """Invented types without a namespace never reach the store."""
        body = {
            "entities": [{"type": "NotARealType", "id": "x"}],
            "relations": [],
            "source_tag": "research-graph",
        }
        with patch(
            "agent_brain_server.api.routers.graph._graphrag_enabled",
            return_value=True,
        ):
            r = client.post("/graph/project", json=body)
        assert r.status_code == 422

    def test_dangling_relation_endpoint_is_400(self, client: TestClient) -> None:
        body = {
            "entities": [{"type": "okf:Claim", "id": "claim.1"}],
            "relations": [
                {"src": "claim.1", "predicate": "asserts", "dst": "missing"}
            ],
            "source_tag": "research-graph",
        }
        with (
            patch(
                "agent_brain_server.api.routers.graph._graphrag_enabled",
                return_value=True,
            ),
            patch(
                "agent_brain_server.indexing.graph_index.project_isolated",
            ) as isolated,
        ):
            r = client.post("/graph/project", json=body)
        assert r.status_code == 400
        detail = r.json()["detail"]
        assert detail["error"] == "unknown_relation_endpoint"
        assert "missing" in detail["missing_ids"]
        isolated.assert_not_called()

    def test_schema_01_type_is_accepted(self, client: TestClient) -> None:
        body = {
            "entities": [{"type": "Function", "id": "login"}],
            "relations": [],
            "source_tag": "research-graph",
        }
        with (
            patch(
                "agent_brain_server.api.routers.graph._graphrag_enabled",
                return_value=True,
            ),
            patch(
                "agent_brain_server.indexing.graph_index.project_isolated",
                return_value=_ok_counts(entities_upserted=1, relations_upserted=0),
            ),
        ):
            r = client.post("/graph/project", json=body)
        assert r.status_code == 200
        assert r.json()["entities_upserted"] == 1


class TestProjectHappyPath:
    def test_okf_payload_calls_isolated_worker(self, client: TestClient) -> None:
        with (
            patch(
                "agent_brain_server.api.routers.graph._graphrag_enabled",
                return_value=True,
            ),
            patch(
                "agent_brain_server.indexing.graph_index.project_isolated",
                return_value=_ok_counts(),
            ) as isolated,
        ):
            r = client.post("/graph/project", json=_OKF_PAYLOAD)

        assert r.status_code == 200
        body = r.json()
        assert body["entities_upserted"] == 3
        assert body["relations_upserted"] == 2
        assert body["source_tag"] == "research-graph"
        isolated.assert_called_once()
        args, kwargs = isolated.call_args
        assert args[2] == "research-graph"
        assert kwargs["replace"] is False
        assert args[0][0]["type"] == "okf:Finding"
        assert args[1][0]["predicate"] == "asserts"

    def test_replace_true_forwarded(self, client: TestClient) -> None:
        payload = {**_OKF_PAYLOAD, "replace": True}
        with (
            patch(
                "agent_brain_server.api.routers.graph._graphrag_enabled",
                return_value=True,
            ),
            patch(
                "agent_brain_server.indexing.graph_index.project_isolated",
                return_value=_ok_counts(entities_deleted=3, relations_deleted=2),
            ) as isolated,
        ):
            r = client.post("/graph/project", json=payload)
        assert r.status_code == 200
        assert r.json()["entities_deleted"] == 3
        assert isolated.call_args.kwargs["replace"] is True


class TestProjectIsolationFailure:
    def test_isolated_crash_returns_503(self, client: TestClient) -> None:
        with (
            patch(
                "agent_brain_server.api.routers.graph._graphrag_enabled",
                return_value=True,
            ),
            patch(
                "agent_brain_server.indexing.graph_index.project_isolated",
                side_effect=GraphBuildFailedError("boom", exit_code=139),
            ),
        ):
            r = client.post("/graph/project", json=_OKF_PAYLOAD)
        assert r.status_code == 503
        assert r.json()["detail"]["error"] == "kuzu_unavailable"
        assert "graphrag.store_type=simple" in r.json()["detail"]["hint"]


class TestDeleteBySourceTag:
    def test_delete_calls_isolated_replace(self, client: TestClient) -> None:
        with (
            patch(
                "agent_brain_server.api.routers.graph._graphrag_enabled",
                return_value=True,
            ),
            patch(
                "agent_brain_server.indexing.graph_index.project_isolated",
                return_value=_ok_counts(
                    entities_upserted=0,
                    relations_upserted=0,
                    entities_deleted=3,
                    relations_deleted=2,
                ),
            ) as isolated,
        ):
            r = client.delete("/graph/project", params={"source_tag": "research-graph"})
        assert r.status_code == 200
        body = r.json()
        assert body["entities_deleted"] == 3
        assert body["entities_upserted"] == 0
        isolated.assert_called_once()
        assert isolated.call_args.kwargs["replace"] is True
        assert isolated.call_args.args[2] == "research-graph"

    def test_delete_disabled_is_503(self, client: TestClient) -> None:
        with patch(
            "agent_brain_server.api.routers.graph._graphrag_enabled",
            return_value=False,
        ):
            r = client.delete("/graph/project", params={"source_tag": "research-graph"})
        assert r.status_code == 503


class TestOpenAPI:
    def test_project_route_in_openapi(self, app: FastAPI) -> None:
        spec: dict[str, Any] = app.openapi()
        paths = spec.get("paths", {})
        assert "/graph/project" in paths
        assert "post" in paths["/graph/project"]
        assert "delete" in paths["/graph/project"]
