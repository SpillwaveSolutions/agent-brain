"""Wire-format tests for the explain=true query parameter (issue #159).

Verifies the backward-compatibility contract: when `explain` is unset or
false on the request, the `explanation` key MUST NOT appear in any result.
When `explain=true`, the key MUST appear (the service layer populates it).

These tests run against a TestClient with a mocked QueryService, so they
isolate the router's serialization behavior from retrieval logic.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_brain_server.api.routers.query import router
from agent_brain_server.models import (
    QueryResponse,
    QueryResult,
    ResultExplanation,
)


def _make_result(with_explanation: bool = False) -> QueryResult:
    """Build a QueryResult, optionally with an explanation block."""
    explanation = None
    if with_explanation:
        explanation = ResultExplanation(
            reason="Top BM25 hit (score 0.91)",
            matched_terms=["authentication", "setup"],
            fusion=None,
            graph_path=None,
            rerank_movement=None,
            graph_fallback=None,
        )
    return QueryResult(
        text="Authentication is configured via OAuth2.",
        source="docs/auth.md",
        score=0.91,
        chunk_id="chunk_abc123",
        vector_score=0.88,
        bm25_score=0.91,
        explanation=explanation,
    )


def _create_app(response: QueryResponse) -> FastAPI:
    """Build a FastAPI app with the query router and a mocked service."""
    app = FastAPI()
    app.include_router(router, prefix="/query")

    mock_query_service = MagicMock()
    mock_query_service.is_ready = MagicMock(return_value=True)
    mock_query_service.execute_query = AsyncMock(return_value=response)

    mock_indexing_service = MagicMock()
    mock_indexing_service.is_indexing = False

    app.state.query_service = mock_query_service
    app.state.indexing_service = mock_indexing_service
    app.state.embedding_warning = None
    return app


class TestExplainWireFormat:
    """Verify the explain field's effect on response serialization."""

    def test_default_omits_explanation_key(self) -> None:
        """Without explain, results MUST NOT contain an 'explanation' key.

        This is the backward-compat contract from issue #159: the default
        wire format must be byte-identical to historical responses, so
        existing clients with strict schema validation don't see `null`
        or any unexpected field.
        """
        response = QueryResponse(
            results=[_make_result(with_explanation=False)],
            query_time_ms=10.0,
            total_results=1,
        )
        app = _create_app(response)
        client = TestClient(app)

        http_response = client.post("/query/", json={"query": "auth"})

        assert http_response.status_code == 200
        data = http_response.json()
        assert len(data["results"]) == 1
        # The key must be absent, not present-with-null.
        assert "explanation" not in data["results"][0]

    def test_explicit_false_omits_explanation_key(self) -> None:
        """Passing explain=false explicitly behaves the same as omitting it."""
        response = QueryResponse(
            results=[_make_result(with_explanation=False)],
            query_time_ms=10.0,
            total_results=1,
        )
        app = _create_app(response)
        client = TestClient(app)

        http_response = client.post("/query/", json={"query": "auth", "explain": False})

        assert http_response.status_code == 200
        assert "explanation" not in http_response.json()["results"][0]

    def test_explain_true_includes_explanation_key(self) -> None:
        """With explain=true, results MUST include the explanation block."""
        response = QueryResponse(
            results=[_make_result(with_explanation=True)],
            query_time_ms=10.0,
            total_results=1,
        )
        app = _create_app(response)
        client = TestClient(app)

        http_response = client.post("/query/", json={"query": "auth", "explain": True})

        assert http_response.status_code == 200
        data = http_response.json()
        result = data["results"][0]
        assert "explanation" in result
        assert result["explanation"]["reason"] == "Top BM25 hit (score 0.91)"
        assert result["explanation"]["matched_terms"] == [
            "authentication",
            "setup",
        ]
        # Null inner fields are preserved as explicit signals.
        assert result["explanation"]["fusion"] is None
        assert result["explanation"]["graph_path"] is None

    def test_explain_true_with_no_explanation_object(self) -> None:
        """Edge case: explain=true requested but service returned None.

        This shouldn't happen in practice once commit 2 lands, but verify
        the router doesn't crash if the service hasn't populated the field.
        """
        response = QueryResponse(
            results=[_make_result(with_explanation=False)],
            query_time_ms=10.0,
            total_results=1,
        )
        app = _create_app(response)
        client = TestClient(app)

        http_response = client.post("/query/", json={"query": "auth", "explain": True})

        assert http_response.status_code == 200
        # When explain=true and the result has explanation=None, the field
        # is still in the payload as null (so the client can tell that
        # explain was honored but the service produced no payload).
        assert http_response.json()["results"][0]["explanation"] is None
