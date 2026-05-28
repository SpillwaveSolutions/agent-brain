"""Tests for the --explain flag on `agent-brain query` (issue #159).

These exercise the CLI render path via Click's CliRunner with a mocked
DocServeClient. The --explain block should only appear when the flag is
set; without it the output is byte-identical to the existing behavior.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from agent_brain_cli.client.api_client import (
    QueryResponse,
    QueryResult,
    ResultExplanation,
)
from agent_brain_cli.commands.query import query_command


def _make_response(with_explanation: bool) -> QueryResponse:
    explanation = None
    if with_explanation:
        explanation = ResultExplanation(
            reason="Hybrid match (alpha=0.50): vector 0.44 + BM25 0.41 -> fused 0.85",
            matched_terms=["authentication", "setup"],
            fusion={
                "vector_score_weighted": 0.44,
                "bm25_score_weighted": 0.41,
                "alpha": 0.5,
                "fused_score": 0.85,
            },
            graph_path=None,
            rerank_movement=None,
            graph_fallback=None,
        )
    return QueryResponse(
        results=[
            QueryResult(
                text="Authentication setup is documented in the README.",
                source="docs/setup.md",
                score=0.85,
                chunk_id="chunk_abc",
                metadata={},
                vector_score=0.88,
                bm25_score=0.82,
                explanation=explanation,
            )
        ],
        query_time_ms=12.5,
        total_results=1,
    )


def _patch_client(response: QueryResponse):
    """Build a context manager that patches DocServeClient.query."""
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.query = MagicMock(return_value=response)
    return patch(
        "agent_brain_cli.commands.query.DocServeClient",
        return_value=mock_client,
    )


class TestExplainRender:
    def test_explain_block_absent_by_default(self) -> None:
        """Without --explain, the CLI output omits the explanation rows."""
        runner = CliRunner()
        with _patch_client(_make_response(with_explanation=False)):
            result = runner.invoke(query_command, ["test query"])
        assert result.exit_code == 0
        # Explanation labels must not appear.
        assert "Why:" not in result.output
        assert "Matched:" not in result.output
        assert "Fusion:" not in result.output

    def test_explain_block_renders_with_flag(self) -> None:
        """With --explain, the CLI shows the structured explanation rows."""
        runner = CliRunner()
        with _patch_client(_make_response(with_explanation=True)):
            result = runner.invoke(query_command, ["test query", "--explain"])
        assert result.exit_code == 0
        assert "Why:" in result.output
        assert "Hybrid match" in result.output
        assert "Matched:" in result.output
        assert "authentication" in result.output
        assert "setup" in result.output
        assert "Fusion:" in result.output
        assert "fused_score=0.8500" in result.output

    def test_explain_renders_graph_path_when_present(self) -> None:
        """Graph mode results: graph_path joined with arrows."""
        response = _make_response(with_explanation=False)
        response.results[0].explanation = ResultExplanation(
            reason="Graph match (score 0.70)",
            matched_terms=None,
            fusion=None,
            graph_path=["AuthManager", "contains", "authenticate"],
            rerank_movement=None,
            graph_fallback=False,
        )
        runner = CliRunner()
        with _patch_client(response):
            result = runner.invoke(query_command, ["test", "--explain"])
        assert result.exit_code == 0
        assert "Graph:" in result.output
        assert "AuthManager -> contains -> authenticate" in result.output

    def test_explain_renders_rerank_movement(self) -> None:
        """Positive movement is reported as 'moved up'."""
        response = _make_response(with_explanation=False)
        response.results[0].explanation = ResultExplanation(
            reason="Reranked up 2 places from #5 (cross-encoder score 0.95)",
            matched_terms=None,
            fusion=None,
            graph_path=None,
            rerank_movement=2,
            graph_fallback=None,
        )
        runner = CliRunner()
        with _patch_client(response):
            result = runner.invoke(query_command, ["test", "--explain"])
        assert result.exit_code == 0
        assert "Rerank:" in result.output
        assert "+2 (moved up)" in result.output

    def test_explain_omits_rows_when_data_missing(self) -> None:
        """Only populated rows show — sparse explanations don't pad output."""
        response = _make_response(with_explanation=False)
        response.results[0].explanation = ResultExplanation(
            reason="Vector similarity match (score 0.88)",
            matched_terms=None,
            fusion=None,
            graph_path=None,
            rerank_movement=None,
            graph_fallback=None,
        )
        runner = CliRunner()
        with _patch_client(response):
            result = runner.invoke(query_command, ["test", "--explain"])
        assert result.exit_code == 0
        assert "Why:" in result.output
        # These should not appear since the corresponding fields are None.
        assert "Matched:" not in result.output
        assert "Fusion:" not in result.output
        assert "Graph:" not in result.output
        assert "Rerank:" not in result.output
        assert "Fallback:" not in result.output
