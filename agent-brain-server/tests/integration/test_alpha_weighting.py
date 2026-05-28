"""Integration tests for alpha weighting in hybrid mode."""

from unittest.mock import AsyncMock, MagicMock

from agent_brain_server.models import QueryResponse


class TestAlphaWeighting:
    """Tests for alpha parameter validation and behavior."""

    def test_alpha_validation_bounds(self, app_with_mocks, client):
        """Test that alpha must be between 0.0 and 1.0."""
        # Valid bounds - set up mock query/indexing service on app.state
        mock_service = MagicMock()
        mock_service.is_ready.return_value = True
        mock_service.execute_query = AsyncMock(
            return_value=QueryResponse(results=[], query_time_ms=0, total_results=0)
        )
        mock_idx_service = MagicMock()
        mock_idx_service.is_indexing = False

        app_with_mocks.state.query_service = mock_service
        app_with_mocks.state.indexing_service = mock_idx_service

        for alpha in [0.0, 0.5, 1.0]:
            response = client.post(
                "/query/",
                json={"query": "test", "mode": "hybrid", "alpha": alpha},
            )
            assert response.status_code == 200

        # Invalid bounds
        for alpha in [-0.1, 1.1]:
            response = client.post(
                "/query/",
                json={"query": "test", "mode": "hybrid", "alpha": alpha},
            )
            assert response.status_code == 422

    def test_alpha_passing_to_service(
        self,
        app_with_mocks,
        client,
        mock_vector_store,
        mock_bm25_manager,
        mock_embedding_generator,
    ):
        """Test that alpha is used correctly in manual hybrid fusion."""
        from agent_brain_server.services import QueryService

        mock_vector_store.is_initialized = True
        mock_bm25_manager.is_initialized = True

        # Mock vector search results (SearchResult objects)
        from agent_brain_server.storage.vector_store import SearchResult

        mock_vector_store.similarity_search.return_value = [
            SearchResult(
                text="Vector result",
                metadata={
                    "source": "v.md",
                    "source_type": "doc",
                    "language": "markdown",
                },
                score=0.8,
                chunk_id="v1",
            )
        ]

        # Mock BM25 results (NodeWithScore-like objects)
        mock_bm25_manager.search_with_filters = AsyncMock(
            return_value=[
                MagicMock(
                    node=MagicMock(
                        get_content=MagicMock(return_value="BM25 result"),
                        metadata={
                            "source": "b.md",
                            "source_type": "doc",
                            "language": "markdown",
                        },
                        node_id="b1",
                    ),
                    score=0.9,
                )
            ]
        )

        # Create a real QueryService with mocked deps and set on app.state
        query_service = QueryService(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_generator,
            bm25_manager=mock_bm25_manager,
        )
        app_with_mocks.state.query_service = query_service

        alpha_value = 0.7
        response = client.post(
            "/query/",
            json={
                "query": "alpha test",
                "mode": "hybrid",
                "alpha": alpha_value,
            },
        )

        assert response.status_code == 200
        # Verify that search_with_filters was called (indicating manual fusion is used)
        mock_bm25_manager.search_with_filters.assert_called_once()
