"""Integration tests for Hybrid retrieval mode."""

from unittest.mock import AsyncMock, MagicMock


class TestHybridQueryEndpoint:
    """Tests for hybrid query mode via API."""

    def test_query_hybrid_mode(
        self, client, mock_vector_store, mock_bm25_manager, mock_embedding_generator
    ):
        """Test querying with mode=hybrid."""
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
                    "source": "docs/vector.md",
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
                        "source": "docs/bm25.md",
                        "source_type": "doc",
                        "language": "markdown"
                    },
                    node_id="b1"
                ),
                score=0.9
            )
        ])

        response = client.post(
            "/query/",
            json={
                "query": "hybrid query",
                "mode": "hybrid",
                "alpha": 0.3,
            },
        )

        assert response.status_code == 200, f"Error: {response.json()}"
        data = response.json()
        assert data["total_results"] == 2  # Both vector and BM25 results
        # Check that both search methods were called
        mock_vector_store.similarity_search.assert_called_once()
        mock_bm25_manager.search_with_filters.assert_called_once()
