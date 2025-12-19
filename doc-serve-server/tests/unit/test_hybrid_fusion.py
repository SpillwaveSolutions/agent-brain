"""Unit tests for Hybrid retrieval functionality."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from doc_serve_server.models.query import QueryMode, QueryRequest
from doc_serve_server.services.query_service import QueryService


class TestHybridRetrieval:
    """Tests for hybrid retrieval logic."""

    @pytest.mark.asyncio
    async def test_hybrid_query_logic(
        self, mock_vector_store, mock_bm25_manager, mock_embedding_generator
    ):
        """Test the hybrid query execution logic."""
        # Setup mocks
        service = QueryService(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_generator,
            bm25_manager=mock_bm25_manager,
        )

        mock_vector_store.is_initialized = True
        mock_bm25_manager.is_initialized = True

        # Mock vector search results (SearchResult objects)
        from doc_serve_server.storage.vector_store import SearchResult
        mock_vector_store.similarity_search.return_value = [
            SearchResult(
                text="Vector Result",
                metadata={
                    "source": "v.md",
                    "source_type": "doc",
                    "language": "markdown"
                },
                score=0.8,
                chunk_id="v1"
            )
        ]

        # Mock BM25 search_with_filters method
        mock_bm25_manager.search_with_filters = AsyncMock(return_value=[
            MagicMock(
                node=MagicMock(
                    get_content=MagicMock(return_value="BM25 Result"),
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

        # Mock get_count for corpus size
        mock_vector_store.get_count.return_value = 10

        request = QueryRequest(query="test query", mode=QueryMode.HYBRID, alpha=0.5)

        response = await service.execute_query(request)

        assert response.total_results == 2  # Both vector and BM25 results
        assert len(response.results) == 2
        # Check that manual fusion was used (both search methods called)
        mock_vector_store.similarity_search.assert_called_once()
        mock_bm25_manager.search_with_filters.assert_called_once()
