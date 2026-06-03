"""Phase 54 Plan 02 — handler tests for ``explain_result`` (TOOL-01).

Coverage:
    * Happy path: the requested chunk is present in the explained pool
      and ``handle_explain_result`` returns a fully populated
      :class:`ExplainResultOutput`.
    * Missing-chunk path: the chunk isn't in the top-``top_k`` pool;
      handler raises :class:`McpError(INVALID_PARAMS)` with the
      CONTEXT-F mandated guidance message.
    * Request-shape pin: the handler sends the original query, mode,
      top_k, alpha, AND ``explain=True`` through to ``POST /query/``
      so the server's explanation pipeline runs.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from mcp import McpError

from agent_brain_mcp.client import ApiClient
from agent_brain_mcp.errors import INVALID_PARAMS
from agent_brain_mcp.schemas import ExplainResultInput
from agent_brain_mcp.tools.explain import handle_explain_result


def _make_capturing_client(
    response_body: dict[str, Any],
) -> tuple[ApiClient, list[httpx.Request]]:
    """Return (ApiClient, captured_requests) — same pattern as
    :func:`tests.test_client_phase54._make_capturing_client`.
    """
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=response_body)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="http://test-agent-brain")
    return ApiClient(client), captured


class TestExplainResultSuccess:
    def test_returns_explanation_for_matching_chunk_id(self) -> None:
        explanation = {
            "reason": "matched on 'auth' (BM25)",
            "matched_terms": ["auth", "token"],
            "fusion": {"bm25_score_weighted": 0.4, "vector_score_weighted": 0.6},
            "graph_path": None,
            "rerank_movement": 2,
            "graph_fallback": False,
        }
        api, _captured = _make_capturing_client(
            {
                "query": "authentication token",
                "mode": "hybrid",
                "total_results": 1,
                "results": [
                    {
                        "text": "def issue_token(...): ...",
                        "source": "src/auth.py",
                        "score": 0.87,
                        "chunk_id": "chunk_42",
                        "metadata": {},
                        "explanation": explanation,
                    }
                ],
            }
        )

        args = ExplainResultInput(
            query="authentication token",
            chunk_id="chunk_42",
            mode="hybrid",
            top_k=50,
            alpha=0.5,
        )
        out = handle_explain_result(api, args)

        assert out.chunk_id == "chunk_42"
        assert out.text == "def issue_token(...): ..."
        assert out.source == "src/auth.py"
        assert out.score == pytest.approx(0.87)
        assert out.reason == "matched on 'auth' (BM25)"
        assert out.matched_terms == ["auth", "token"]
        assert out.fusion == {
            "bm25_score_weighted": 0.4,
            "vector_score_weighted": 0.6,
        }
        assert out.graph_path is None
        assert out.rerank_movement == 2
        assert out.graph_fallback is False


class TestExplainResultMissingChunk:
    def test_chunk_not_in_results_raises_invalid_params(self) -> None:
        # Response contains a different chunk_id than the one we ask about.
        api, _captured = _make_capturing_client(
            {
                "query": "authentication token",
                "mode": "hybrid",
                "total_results": 1,
                "results": [
                    {
                        "text": "other chunk",
                        "source": "src/other.py",
                        "score": 0.5,
                        "chunk_id": "chunk_99",
                        "metadata": {},
                        "explanation": {"reason": "other"},
                    }
                ],
            }
        )

        args = ExplainResultInput(
            query="authentication token",
            chunk_id="chunk_42",
            mode="hybrid",
            top_k=50,
            alpha=0.5,
        )
        with pytest.raises(McpError) as excinfo:
            handle_explain_result(api, args)

        err = excinfo.value.error
        assert err.code == INVALID_PARAMS
        # Message text must guide the caller — pin the load-bearing phrases.
        assert "chunk_42" in err.message
        assert "top-50" in err.message
        assert "higher top_k" in err.message or "closer query" in err.message
        assert err.data == {"chunk_id": "chunk_42", "top_k": 50}

    def test_empty_results_raises_invalid_params(self) -> None:
        api, _captured = _make_capturing_client(
            {
                "query": "no hits",
                "mode": "hybrid",
                "total_results": 0,
                "results": [],
            }
        )
        args = ExplainResultInput(
            query="no hits",
            chunk_id="chunk_42",
            mode="hybrid",
        )
        with pytest.raises(McpError) as excinfo:
            handle_explain_result(api, args)
        assert excinfo.value.error.code == INVALID_PARAMS


class TestExplainResultRequestShape:
    def test_propagates_mode_top_k_alpha_and_sets_explain_true(self) -> None:
        api, captured = _make_capturing_client(
            {
                "query": "x",
                "mode": "semantic",
                "total_results": 1,
                "results": [
                    {
                        "text": "t",
                        "source": "s",
                        "score": 0.1,
                        "chunk_id": "c1",
                        "metadata": {},
                        "explanation": {"reason": "r"},
                    }
                ],
            }
        )
        args = ExplainResultInput(
            query="x",
            chunk_id="c1",
            mode="semantic",
            top_k=75,
            alpha=0.25,
        )
        handle_explain_result(api, args)

        assert len(captured) == 1
        req = captured[0]
        assert req.method == "POST"
        assert req.url.path == "/query/"
        sent = json.loads(req.content)
        assert sent == {
            "query": "x",
            "mode": "semantic",
            "top_k": 75,
            "alpha": 0.25,
            "explain": True,
        }

    def test_defaults_send_hybrid_top_k_50_alpha_0_5(self) -> None:
        """When the caller omits mode/top_k/alpha, the schema defaults
        flow through verbatim — hybrid / 50 / 0.5 — and ``explain=True``
        is always set.
        """
        api, captured = _make_capturing_client(
            {
                "query": "y",
                "mode": "hybrid",
                "total_results": 1,
                "results": [
                    {
                        "text": "t",
                        "source": "s",
                        "score": 0.1,
                        "chunk_id": "c1",
                        "metadata": {},
                        "explanation": {"reason": "r"},
                    }
                ],
            }
        )
        args = ExplainResultInput(query="y", chunk_id="c1")
        handle_explain_result(api, args)
        sent = json.loads(captured[0].content)
        assert sent["mode"] == "hybrid"
        assert sent["top_k"] == 50
        assert sent["alpha"] == 0.5
        assert sent["explain"] is True
