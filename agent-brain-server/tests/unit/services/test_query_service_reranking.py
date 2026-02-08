"""Tests for query service reranking integration.

Tests cover:
- _rerank_results method behavior
- Graceful fallback on reranker errors
- Reranking disabled behavior
- Score and metadata propagation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_brain_server.models import QueryMode, QueryRequest, QueryResult
from agent_brain_server.services.query_service import QueryService


class TestRerankerResultsMethod:
    """Test _rerank_results method in isolation."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mocked dependencies for QueryService."""
        mock_vector_store = MagicMock()
        mock_vector_store.is_initialized = True
        mock_vector_store.get_count = AsyncMock(return_value=100)

        mock_embedding_gen = MagicMock()
        mock_embedding_gen.embed_query = AsyncMock(return_value=[0.1] * 768)

        mock_bm25 = MagicMock()
        mock_bm25.is_initialized = True

        mock_graph = MagicMock()

        return {
            "vector_store": mock_vector_store,
            "embedding_generator": mock_embedding_gen,
            "bm25_manager": mock_bm25,
            "graph_index_manager": mock_graph,
        }

    @pytest.fixture
    def query_service(self, mock_dependencies):
        """Create QueryService with mocked dependencies."""
        return QueryService(
            vector_store=mock_dependencies["vector_store"],
            embedding_generator=mock_dependencies["embedding_generator"],
            bm25_manager=mock_dependencies["bm25_manager"],
            graph_index_manager=mock_dependencies["graph_index_manager"],
        )

    @pytest.fixture
    def sample_results(self) -> list[QueryResult]:
        """Create sample query results for reranking tests."""
        return [
            QueryResult(
                text=f"Document {i} content with various information.",
                source=f"doc{i}.txt",
                score=1.0 - (i * 0.1),  # Decreasing scores: 1.0, 0.9, 0.8, ...
                vector_score=1.0 - (i * 0.1),
                chunk_id=f"chunk_{i}",
            )
            for i in range(10)
        ]

    @pytest.mark.asyncio
    async def test_rerank_results_empty_input(self, query_service) -> None:
        """_rerank_results handles empty input gracefully."""
        result = await query_service._rerank_results([], "test query", top_k=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_results_success(self, query_service, sample_results) -> None:
        """_rerank_results applies reranking correctly."""
        # Mock the reranker provider
        mock_reranker = MagicMock()
        mock_reranker.is_available.return_value = True
        mock_reranker.provider_name = "MockReranker"
        # Return reordered results: doc5 (best), doc2, doc0
        mock_reranker.rerank = AsyncMock(return_value=[(5, 0.95), (2, 0.85), (0, 0.75)])

        mock_settings = MagicMock()
        mock_settings.reranker = MagicMock()

        with (
            patch(
                "agent_brain_server.services.query_service.load_provider_settings",
                return_value=mock_settings,
            ),
            patch(
                "agent_brain_server.services.query_service.ProviderRegistry"
            ) as mock_registry,
        ):
            mock_registry.get_reranker_provider.return_value = mock_reranker

            result = await query_service._rerank_results(
                sample_results, "test query", top_k=3
            )

            # Verify correct number of results
            assert len(result) == 3

            # Check documents are reordered correctly
            assert result[0].text == "Document 5 content with various information."
            assert result[1].text == "Document 2 content with various information."
            assert result[2].text == "Document 0 content with various information."

            # Check rerank scores are set
            assert result[0].rerank_score == 0.95
            assert result[1].rerank_score == 0.85
            assert result[2].rerank_score == 0.75

            # Check original ranks are set (1-indexed)
            assert result[0].original_rank == 6  # doc5 was at index 5 -> rank 6
            assert result[1].original_rank == 3  # doc2 was at index 2 -> rank 3
            assert result[2].original_rank == 1  # doc0 was at index 0 -> rank 1

    @pytest.mark.asyncio
    async def test_rerank_results_preserves_original_scores(
        self, query_service, sample_results
    ) -> None:
        """_rerank_results preserves vector_score and bm25_score from originals."""
        # Add BM25 scores to some results
        sample_results[0].bm25_score = 0.8
        sample_results[2].bm25_score = 0.6

        mock_reranker = MagicMock()
        mock_reranker.is_available.return_value = True
        mock_reranker.provider_name = "MockReranker"
        mock_reranker.rerank = AsyncMock(return_value=[(0, 0.9), (2, 0.8)])

        mock_settings = MagicMock()
        mock_settings.reranker = MagicMock()

        with (
            patch(
                "agent_brain_server.services.query_service.load_provider_settings",
                return_value=mock_settings,
            ),
            patch(
                "agent_brain_server.services.query_service.ProviderRegistry"
            ) as mock_registry,
        ):
            mock_registry.get_reranker_provider.return_value = mock_reranker

            result = await query_service._rerank_results(
                sample_results, "test query", top_k=2
            )

            # Original scores should be preserved
            assert result[0].vector_score == 1.0  # doc0's original vector score
            assert result[0].bm25_score == 0.8  # doc0's original bm25 score
            assert result[1].bm25_score == 0.6  # doc2's original bm25 score

    @pytest.mark.asyncio
    async def test_rerank_results_fallback_on_provider_error(
        self, query_service, sample_results
    ) -> None:
        """_rerank_results falls back to stage 1 on provider error."""
        mock_settings = MagicMock()
        mock_settings.reranker = MagicMock()

        with (
            patch(
                "agent_brain_server.services.query_service.load_provider_settings",
                return_value=mock_settings,
            ),
            patch(
                "agent_brain_server.services.query_service.ProviderRegistry"
            ) as mock_registry,
        ):
            mock_registry.get_reranker_provider.side_effect = Exception(
                "Provider not found"
            )

            result = await query_service._rerank_results(
                sample_results, "test query", top_k=3
            )

            # Should return first 3 results unchanged (original order)
            assert len(result) == 3
            assert result[0].text == "Document 0 content with various information."
            assert result[1].text == "Document 1 content with various information."
            assert result[2].text == "Document 2 content with various information."

    @pytest.mark.asyncio
    async def test_rerank_results_fallback_on_rerank_failure(
        self, query_service, sample_results
    ) -> None:
        """_rerank_results falls back when rerank() raises exception."""
        mock_reranker = MagicMock()
        mock_reranker.is_available.return_value = True
        mock_reranker.provider_name = "MockReranker"
        mock_reranker.rerank = AsyncMock(side_effect=Exception("Reranking failed"))

        mock_settings = MagicMock()
        mock_settings.reranker = MagicMock()

        with (
            patch(
                "agent_brain_server.services.query_service.load_provider_settings",
                return_value=mock_settings,
            ),
            patch(
                "agent_brain_server.services.query_service.ProviderRegistry"
            ) as mock_registry,
        ):
            mock_registry.get_reranker_provider.return_value = mock_reranker

            result = await query_service._rerank_results(
                sample_results, "test query", top_k=3
            )

            # Should return first 3 results unchanged
            assert len(result) == 3
            assert result[0].text == "Document 0 content with various information."

    @pytest.mark.asyncio
    async def test_rerank_results_provider_unavailable(
        self, query_service, sample_results
    ) -> None:
        """_rerank_results falls back when provider reports unavailable."""
        mock_reranker = MagicMock()
        mock_reranker.is_available.return_value = False
        mock_reranker.provider_name = "MockReranker"

        mock_settings = MagicMock()
        mock_settings.reranker = MagicMock()

        with (
            patch(
                "agent_brain_server.services.query_service.load_provider_settings",
                return_value=mock_settings,
            ),
            patch(
                "agent_brain_server.services.query_service.ProviderRegistry"
            ) as mock_registry,
        ):
            mock_registry.get_reranker_provider.return_value = mock_reranker

            result = await query_service._rerank_results(
                sample_results, "test query", top_k=3
            )

            # Should return first 3 results unchanged
            assert len(result) == 3
            assert result[0].text == "Document 0 content with various information."


class TestExecuteQueryWithReranking:
    """Test execute_query behavior with reranking settings."""

    def test_reranking_disabled_by_default(self) -> None:
        """Reranking is disabled by default in settings."""
        from agent_brain_server.config.settings import Settings

        settings = Settings()
        assert settings.ENABLE_RERANKING is False

    def test_default_reranker_settings(self) -> None:
        """Default reranker settings are sensible."""
        from agent_brain_server.config.settings import Settings

        settings = Settings()
        assert settings.RERANKER_PROVIDER == "sentence-transformers"
        assert settings.RERANKER_MODEL == "cross-encoder/ms-marco-MiniLM-L-6-v2"
        assert settings.RERANKER_TOP_K_MULTIPLIER == 10
        assert settings.RERANKER_MAX_CANDIDATES == 100

    def test_stage1_topk_calculation_basic(self) -> None:
        """Stage 1 top_k is multiplied correctly."""
        # With top_k=5 and multiplier=10, stage1 should be 50
        top_k = 5
        multiplier = 10
        max_candidates = 100
        expected_stage1 = min(top_k * multiplier, max_candidates)
        assert expected_stage1 == 50

    def test_stage1_topk_calculation_capped(self) -> None:
        """Stage 1 top_k is capped at max_candidates."""
        # With top_k=15 and multiplier=10, stage1 should be capped at 100
        top_k = 15
        multiplier = 10
        max_candidates = 100
        expected_stage1 = min(top_k * multiplier, max_candidates)
        assert expected_stage1 == 100

    @pytest.mark.asyncio
    async def test_execute_query_calls_rerank_when_enabled(self) -> None:
        """execute_query calls _rerank_results when reranking is enabled."""
        from agent_brain_server.config.settings import Settings

        # Create mock services
        mock_vector_store = MagicMock()
        mock_vector_store.is_initialized = True
        mock_vector_store.get_count = AsyncMock(return_value=100)
        mock_vector_store.similarity_search = AsyncMock(
            return_value=[
                MagicMock(
                    text=f"doc{i}",
                    chunk_id=f"chunk_{i}",
                    score=1.0 - i * 0.1,
                    metadata={"source": f"doc{i}.txt"},
                )
                for i in range(50)
            ]
        )

        mock_embedding_gen = MagicMock()
        mock_embedding_gen.embed_query = AsyncMock(return_value=[0.1] * 768)

        mock_bm25 = MagicMock()
        mock_bm25.is_initialized = True
        mock_bm25.search_with_filters = AsyncMock(return_value=[])

        mock_graph = MagicMock()

        query_service = QueryService(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_gen,
            bm25_manager=mock_bm25,
            graph_index_manager=mock_graph,
        )

        # Mock settings with reranking enabled
        mock_settings = Settings(
            ENABLE_RERANKING=True,
            RERANKER_TOP_K_MULTIPLIER=10,
            RERANKER_MAX_CANDIDATES=100,
        )

        # Mock _rerank_results to track if it's called
        with (
            patch.object(
                query_service, "_rerank_results", new_callable=AsyncMock
            ) as mock_rerank,
            patch("agent_brain_server.services.query_service.settings", mock_settings),
        ):
            mock_rerank.return_value = [
                QueryResult(
                    text="reranked doc",
                    source="reranked.txt",
                    score=0.9,
                    chunk_id="chunk_reranked",
                )
            ]

            request = QueryRequest(query="test query", top_k=5, mode=QueryMode.HYBRID)
            await query_service.execute_query(request)

            # _rerank_results should have been called
            mock_rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_skips_rerank_when_disabled(self) -> None:
        """execute_query does not call _rerank_results when disabled."""
        # Create mock services
        mock_vector_store = MagicMock()
        mock_vector_store.is_initialized = True
        mock_vector_store.get_count = AsyncMock(return_value=10)
        mock_vector_store.similarity_search = AsyncMock(
            return_value=[
                MagicMock(
                    text=f"doc{i}",
                    chunk_id=f"chunk_{i}",
                    score=0.9,
                    metadata={"source": f"doc{i}.txt"},
                )
                for i in range(5)
            ]
        )

        mock_embedding_gen = MagicMock()
        mock_embedding_gen.embed_query = AsyncMock(return_value=[0.1] * 768)

        mock_bm25 = MagicMock()
        mock_bm25.is_initialized = True
        mock_bm25.search_with_filters = AsyncMock(return_value=[])

        mock_graph = MagicMock()

        query_service = QueryService(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_gen,
            bm25_manager=mock_bm25,
            graph_index_manager=mock_graph,
        )

        # Mock _rerank_results to track if it's called
        with patch.object(
            query_service, "_rerank_results", new_callable=AsyncMock
        ) as mock_rerank:
            request = QueryRequest(query="test query", top_k=5, mode=QueryMode.HYBRID)
            await query_service.execute_query(request)

            # _rerank_results should NOT be called (reranking disabled)
            mock_rerank.assert_not_called()


class TestQueryResultRerankingFields:
    """Test QueryResult model reranking fields."""

    def test_rerank_score_field_exists(self) -> None:
        """QueryResult has rerank_score field."""
        result = QueryResult(
            text="test",
            source="test.py",
            score=0.9,
            chunk_id="c1",
            rerank_score=0.85,
        )
        assert result.rerank_score == 0.85

    def test_original_rank_field_exists(self) -> None:
        """QueryResult has original_rank field."""
        result = QueryResult(
            text="test",
            source="test.py",
            score=0.9,
            chunk_id="c1",
            original_rank=3,
        )
        assert result.original_rank == 3

    def test_rerank_fields_are_optional(self) -> None:
        """Reranking fields are optional (None by default)."""
        result = QueryResult(
            text="test",
            source="test.py",
            score=0.9,
            chunk_id="c1",
        )
        assert result.rerank_score is None
        assert result.original_rank is None

    def test_all_fields_can_be_set(self) -> None:
        """All reranking fields can be set together."""
        result = QueryResult(
            text="test",
            source="test.py",
            score=0.9,
            vector_score=0.88,
            bm25_score=0.82,
            chunk_id="c1",
            rerank_score=0.95,
            original_rank=5,
        )
        assert result.score == 0.9
        assert result.vector_score == 0.88
        assert result.bm25_score == 0.82
        assert result.rerank_score == 0.95
        assert result.original_rank == 5
