"""Integration tests for BM25 retrieval mode."""

from unittest.mock import AsyncMock, MagicMock


class TestBM25QueryEndpoint:
    """Tests for BM25 query mode via API."""

    def test_query_bm25_mode(
        self, app_with_mocks, client, mock_vector_store, mock_bm25_manager
    ):
        """Test querying with mode=bm25."""
        from llama_index.core.schema import NodeWithScore, TextNode

        from agent_brain_server.services import QueryService

        mock_vector_store.is_initialized = True
        mock_bm25_manager.is_initialized = True

        # Setup mock search_with_filters results (new path via ChromaBackend)
        node_mock = NodeWithScore(
            node=TextNode(
                text="Exact keyword match",
                id_="chunk_bm25",
                metadata={"source": "docs/keyword.md"},
            ),
            score=10.0,  # Raw BM25 score (will be normalized to 1.0)
        )
        mock_bm25_manager.search_with_filters = AsyncMock(return_value=[node_mock])

        # Create QueryService with mocked deps and set on app.state
        query_service = QueryService(
            vector_store=mock_vector_store,
            bm25_manager=mock_bm25_manager,
        )
        app_with_mocks.state.query_service = query_service

        response = client.post(
            "/query/",
            json={
                "query": "specific_keyword",
                "mode": "bm25",
                "top_k": 5,
            },
        )

        assert response.status_code == 200, f"Error: {response.json()}"
        data = response.json()
        assert data["total_results"] == 1
        assert data["results"][0]["bm25_score"] == 1.0
        assert data["results"][0]["text"] == "Exact keyword match"

    def test_query_invalid_mode(self, client):
        """Test querying with an invalid mode."""
        response = client.post(
            "/query/",
            json={
                "query": "test",
                "mode": "invalid_mode",
            },
        )
        assert response.status_code == 422  # Pydantic validation error
