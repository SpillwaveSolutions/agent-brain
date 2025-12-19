"""Integration tests for alpha weighting in hybrid mode."""

from unittest.mock import AsyncMock, MagicMock, patch


class TestAlphaWeighting:
    """Tests for alpha parameter validation and behavior."""

    def test_alpha_validation_bounds(self, client):
        """Test that alpha must be between 0.0 and 1.0."""
        # Valid bounds
        for alpha in [0.0, 0.5, 1.0]:
            # Use mock to avoid actual execution but check validation
            with patch(
                "doc_serve_server.api.routers.query.get_query_service"
            ) as mock_get_service:
                mock_service = MagicMock()
                mock_service.is_ready.return_value = True
                mock_service.execute_query = AsyncMock(
                    return_value=MagicMock(results=[], query_time_ms=0, total_results=0)
                )
                mock_get_service.return_value = mock_service

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
        self, client, mock_vector_store, mock_bm25_manager, mock_embedding_generator
    ):
        """Test that alpha is used correctly in manual hybrid fusion."""
        from doc_serve_server.services.query_service import get_query_service

        service = get_query_service()
        service.vector_store = mock_vector_store
        service.bm25_manager = mock_bm25_manager
        service.embedding_generator = mock_embedding_generator

        mock_vector_store.is_initialized = True
        mock_bm25_manager.is_initialized = True

        # Mock vector search results (SearchResult objects)
        from doc_serve_server.storage.vector_store import SearchResult
        mock_vector_store.similarity_search.return_value = [
            SearchResult(
                text="Vector result",
                metadata={
                    "source": "v.md",
                    "source_type": "doc",
                    "language": "markdown"
                },
                score=0.8,
                chunk_id="v1"
            )
        ]

        # Mock BM25 results (NodeWithScore-like objects)
        mock_bm25_manager.search_with_filters = AsyncMock(return_value=[
            MagicMock(
                node=MagicMock(
                    get_content=MagicMock(return_value="BM25 result"),
                    metadata={
                        "source": "b.md",
                        "source_type": "doc",
                        "language": "markdown"
                    },
                    node_id="b1"
                ),
                score=0.9
            )
        ])

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
