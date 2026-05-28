"""Tests for the explain=true service-layer builder (issue #159).

These tests exercise the explanation builder helpers directly (no storage
fixtures) and verify that each retrieval mode produces an explanation
with the right shape and a deterministic `reason` string.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_brain_server.models import QueryMode, QueryRequest, QueryResult
from agent_brain_server.services.query_service import (
    EXPLAIN_SCRATCH_KEY,
    QueryService,
    _build_explanation_for_result,
    _build_reason,
    _drain_explain_scratch,
)


def _result(**overrides: object) -> QueryResult:
    """Build a default QueryResult; allow per-test overrides."""
    defaults: dict[str, object] = {
        "text": "sample text",
        "source": "docs/x.md",
        "score": 0.9,
        "chunk_id": "chunk_x",
    }
    defaults.update(overrides)
    return QueryResult(**defaults)  # type: ignore[arg-type]


class TestBuildReason:
    """Verify the deterministic priority order in _build_reason."""

    def test_rerank_movement_wins_over_mode(self) -> None:
        """Rerank movement is the highest-priority signal."""
        result = _result(
            vector_score=0.5,
            rerank_score=0.95,
            original_rank=5,
        )
        scratch = {"rerank_movement": 4}
        # Even though we're in vector mode, rerank takes precedence.
        reason = _build_reason(result, scratch, QueryMode.VECTOR)
        assert "Reranked up 4 places" in reason
        assert "#5" in reason
        assert "0.95" in reason

    def test_rerank_movement_zero_says_confirmed(self) -> None:
        """A rerank that didn't move the result still gets called out."""
        result = _result(rerank_score=0.88, original_rank=2)
        reason = _build_reason(result, {"rerank_movement": 0}, QueryMode.HYBRID)
        assert "confirmed position #2" in reason

    def test_rerank_movement_singular(self) -> None:
        """Singular vs plural: 1 place, 2 places."""
        result = _result(rerank_score=0.88, original_rank=3)
        reason_up = _build_reason(result, {"rerank_movement": 1}, QueryMode.HYBRID)
        reason_down = _build_reason(result, {"rerank_movement": -2}, QueryMode.HYBRID)
        assert "1 place from" in reason_up
        assert "2 places from" in reason_down
        assert "down" in reason_down

    def test_graph_fallback_announced(self) -> None:
        """When graph found no hits and we fell back to vector, say so."""
        result = _result(vector_score=0.72, score=0.72)
        reason = _build_reason(result, {"graph_fallback": True}, QueryMode.GRAPH)
        assert "Graph returned no hits" in reason
        assert "fell back to vector" in reason
        assert "0.72" in reason

    def test_hybrid_reason_has_alpha_and_components(self) -> None:
        result = _result(vector_score=0.8, bm25_score=0.6)
        scratch = {
            "vector_score_weighted": 0.4,
            "bm25_score_weighted": 0.3,
            "alpha": 0.5,
            "fused_score": 0.7,
        }
        reason = _build_reason(result, scratch, QueryMode.HYBRID)
        assert "alpha=0.50" in reason
        assert "vector 0.40" in reason
        assert "BM25 0.30" in reason
        assert "fused 0.70" in reason

    def test_multi_reason_lists_contributing_retrievers(self) -> None:
        result = _result()
        scratch = {
            "rrf_score": 0.0163,
            "vector_rank": 2,
            "bm25_rank": None,
            "graph_rank": 1,
        }
        reason = _build_reason(result, scratch, QueryMode.MULTI)
        assert "vector #2" in reason
        assert "graph #1" in reason
        # BM25 didn't contribute — must not be listed.
        assert "BM25" not in reason
        assert "0.0163" in reason

    def test_bm25_mode_reason(self) -> None:
        result = _result(bm25_score=0.91)
        reason = _build_reason(result, {}, QueryMode.BM25)
        assert reason == "BM25 keyword match (score 0.91)"

    def test_vector_mode_reason(self) -> None:
        result = _result(vector_score=0.88)
        reason = _build_reason(result, {}, QueryMode.VECTOR)
        assert reason == "Vector similarity match (score 0.88)"

    def test_graph_mode_reason_with_score(self) -> None:
        result = _result(graph_score=0.65)
        reason = _build_reason(result, {}, QueryMode.GRAPH)
        assert reason == "Graph match (score 0.65)"


class TestBuildExplanation:
    """Verify _build_explanation_for_result assembles the correct fields per mode."""

    def test_hybrid_fusion_block(self) -> None:
        result = _result(vector_score=0.8, bm25_score=0.6)
        scratch = {
            "vector_score_weighted": 0.4,
            "bm25_score_weighted": 0.3,
            "alpha": 0.5,
            "fused_score": 0.7,
        }
        explanation = _build_explanation_for_result(result, scratch, QueryMode.HYBRID)
        assert explanation.fusion == {
            "vector_score_weighted": 0.4,
            "bm25_score_weighted": 0.3,
            "alpha": 0.5,
            "fused_score": 0.7,
        }
        assert explanation.graph_path is None
        assert explanation.graph_fallback is None
        assert explanation.rerank_movement is None

    def test_multi_fusion_skips_none_ranks(self) -> None:
        result = _result()
        scratch = {
            "rrf_score": 0.05,
            "vector_rank": 1,
            "bm25_rank": None,
            "graph_rank": 2,
            "fused_rank": 1,
        }
        explanation = _build_explanation_for_result(result, scratch, QueryMode.MULTI)
        assert explanation.fusion == {
            "rrf_score": 0.05,
            "vector_rank": 1.0,
            "graph_rank": 2.0,
            "fused_rank": 1.0,
        }
        # bm25_rank is None — must be excluded from the dict.
        assert "bm25_rank" not in (explanation.fusion or {})

    def test_graph_path_from_relationship_path(self) -> None:
        result = _result(
            graph_score=0.7,
            relationship_path=["AuthManager", "contains", "authenticate"],
        )
        explanation = _build_explanation_for_result(result, {}, QueryMode.GRAPH)
        assert explanation.graph_path == [
            "AuthManager",
            "contains",
            "authenticate",
        ]
        assert explanation.graph_fallback is False

    def test_graph_fallback_flag(self) -> None:
        result = _result(vector_score=0.5)
        explanation = _build_explanation_for_result(
            result, {"graph_fallback": True}, QueryMode.GRAPH
        )
        assert explanation.graph_fallback is True
        assert "fell back to vector" in explanation.reason

    def test_rerank_movement_propagated(self) -> None:
        result = _result(rerank_score=0.95, original_rank=4)
        explanation = _build_explanation_for_result(
            result, {"rerank_movement": 3}, QueryMode.HYBRID
        )
        assert explanation.rerank_movement == 3

    def test_bm25_mode_no_fusion(self) -> None:
        result = _result(bm25_score=0.91)
        explanation = _build_explanation_for_result(result, {}, QueryMode.BM25)
        assert explanation.fusion is None
        assert explanation.matched_terms is None  # nothing stashed -> None
        assert "BM25" in explanation.reason

    def test_bm25_mode_with_matched_terms(self) -> None:
        """When the backend supplied matched_terms, they appear in the payload
        and the reason string mentions them."""
        result = _result(bm25_score=0.91)
        explanation = _build_explanation_for_result(
            result,
            {"matched_terms": ["authentication", "setup"]},
            QueryMode.BM25,
        )
        assert explanation.matched_terms == ["authentication", "setup"]
        assert "authentication" in explanation.reason
        assert "setup" in explanation.reason

    def test_matched_terms_empty_list_becomes_none(self) -> None:
        """An empty matched_terms list normalizes to None — clients can rely
        on `None` meaning 'no BM25 contribution' without checking length."""
        result = _result(bm25_score=0.91)
        explanation = _build_explanation_for_result(
            result, {"matched_terms": []}, QueryMode.BM25
        )
        assert explanation.matched_terms is None


class TestDrainScratch:
    """Verify _drain_explain_scratch's contract."""

    def test_always_pops_scratch_from_metadata(self) -> None:
        """The scratch must never leak into the final response."""
        result = _result(
            metadata={
                "chunk_index": 3,
                EXPLAIN_SCRATCH_KEY: {"alpha": 0.5},
            }
        )
        request = QueryRequest(query="q", mode=QueryMode.HYBRID, explain=False)
        _drain_explain_scratch([result], request)
        assert EXPLAIN_SCRATCH_KEY not in result.metadata
        assert "chunk_index" in result.metadata  # other keys preserved
        assert result.explanation is None  # explain=false -> no build

    def test_builds_explanation_when_explain_true(self) -> None:
        result = _result(
            vector_score=0.8,
            bm25_score=0.6,
            metadata={
                EXPLAIN_SCRATCH_KEY: {
                    "vector_score_weighted": 0.4,
                    "bm25_score_weighted": 0.3,
                    "alpha": 0.5,
                    "fused_score": 0.7,
                },
            },
        )
        request = QueryRequest(query="q", mode=QueryMode.HYBRID, explain=True)
        _drain_explain_scratch([result], request)
        assert result.explanation is not None
        assert result.explanation.fusion is not None
        assert result.explanation.fusion["fused_score"] == 0.7
        assert EXPLAIN_SCRATCH_KEY not in result.metadata


class TestRerankMovementIntegration:
    """End-to-end test of the rerank movement marker through _rerank_results."""

    @pytest.fixture
    def sample_results(self) -> list[QueryResult]:
        return [
            QueryResult(
                text=f"Doc {i}",
                source=f"d{i}.md",
                score=1.0 - i * 0.1,
                chunk_id=f"c{i}",
            )
            for i in range(5)
        ]

    @pytest.mark.asyncio
    async def test_rerank_stashes_movement(self, sample_results) -> None:
        """The rerank step must annotate each result with its movement."""
        service = QueryService(
            vector_store=MagicMock(),
            embedding_generator=MagicMock(),
            bm25_manager=MagicMock(),
            graph_index_manager=MagicMock(),
        )

        mock_reranker = MagicMock()
        mock_reranker.is_available.return_value = True
        mock_reranker.provider_name = "Mock"
        # Reorder: doc3 wins, then doc1, then doc0.
        mock_reranker.rerank = AsyncMock(return_value=[(3, 0.95), (1, 0.85), (0, 0.75)])

        with (
            patch(
                "agent_brain_server.services.query_service.load_provider_settings",
                return_value=MagicMock(reranker=MagicMock()),
            ),
            patch(
                "agent_brain_server.services.query_service.ProviderRegistry"
            ) as mock_registry,
        ):
            mock_registry.get_reranker_provider.return_value = mock_reranker
            result = await service._rerank_results(sample_results, "q", top_k=3)

        # doc3: original_index=3, new_index=0 -> movement=+3
        assert result[0].metadata[EXPLAIN_SCRATCH_KEY]["rerank_movement"] == 3
        # doc1: original_index=1, new_index=1 -> movement=0
        assert result[1].metadata[EXPLAIN_SCRATCH_KEY]["rerank_movement"] == 0
        # doc0: original_index=0, new_index=2 -> movement=-2
        assert result[2].metadata[EXPLAIN_SCRATCH_KEY]["rerank_movement"] == -2

    @pytest.mark.asyncio
    async def test_rerank_preserves_upstream_scratch(self, sample_results) -> None:
        """Rerank must MERGE its movement into existing scratch, not overwrite."""
        sample_results[0].metadata[EXPLAIN_SCRATCH_KEY] = {"alpha": 0.5}

        service = QueryService(
            vector_store=MagicMock(),
            embedding_generator=MagicMock(),
            bm25_manager=MagicMock(),
            graph_index_manager=MagicMock(),
        )
        mock_reranker = MagicMock()
        mock_reranker.is_available.return_value = True
        mock_reranker.provider_name = "Mock"
        mock_reranker.rerank = AsyncMock(return_value=[(0, 0.95)])

        with (
            patch(
                "agent_brain_server.services.query_service.load_provider_settings",
                return_value=MagicMock(reranker=MagicMock()),
            ),
            patch(
                "agent_brain_server.services.query_service.ProviderRegistry"
            ) as mock_registry,
        ):
            mock_registry.get_reranker_provider.return_value = mock_reranker
            result = await service._rerank_results(sample_results, "q", top_k=1)

        scratch = result[0].metadata[EXPLAIN_SCRATCH_KEY]
        assert scratch["alpha"] == 0.5  # upstream preserved
        assert scratch["rerank_movement"] == 0  # rerank added
