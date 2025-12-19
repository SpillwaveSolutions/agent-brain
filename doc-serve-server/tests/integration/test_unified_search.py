"""Integration tests for unified search functionality across docs and code."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from doc_serve_server.models.query import QueryMode, QueryRequest
from doc_serve_server.services.query_service import QueryService


class TestUnifiedSearch:
    """Test unified search across documentation and source code."""

    @pytest.mark.asyncio
    async def test_sdk_cross_reference_search(
        self,
        mock_vector_store,
        mock_bm25_manager,
        mock_embedding_generator,
    ):
        """Test cross-reference search with SDK documentation and code.

        This simulates indexing AWS CDK docs + source and querying for patterns.
        """
        # Setup service
        service = QueryService(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_generator,
            bm25_manager=mock_bm25_manager,
        )

        mock_vector_store.is_initialized = True
        mock_bm25_manager.is_initialized = True

        # Mock AWS CDK-like content: docs + code
        # Simulate indexing CDK documentation + source code

        # Mock vector results (from documentation)
        mock_vector_store.similarity_search.return_value = [
            type('SearchResult', (), {
                'text': (
                    "S3 bucket with versioning can be created using the Bucket "
                    "construct with versioned=True parameter."
                ),
                'metadata': {
                    'source': 'docs/aws-cdk/s3.md',
                    'source_type': 'doc',
                    'language': 'markdown',
                    'section_title': 'S3 Bucket Versioning'
                },
                'score': 0.85,
                'chunk_id': 'doc_chunk_1'
            })()
        ]

        # Mock BM25 results (from source code)
        mock_bm25_manager.search_with_filters = AsyncMock(return_value=[
            type('NodeWithScore', (), {
                'node': type('TextNode', (), {
                    'get_content': MagicMock(
                        return_value=(
                            "const bucket = new s3.Bucket(this, "
                            "'MyBucket', { versioned: true });"
                        )
                    ),
                    'metadata': {
                        'source': 'src/aws-cdk-lib/aws-s3/lib/bucket.ts',
                        'source_type': 'code',
                        'language': 'typescript',
                        'symbol_name': 'Bucket.constructor'
                    },
                    'node_id': 'code_chunk_1'
                })(),
                'score': 0.92
            })()
        ])

        # Mock corpus size
        mock_vector_store.get_count.return_value = 100

        # Test cross-reference query
        request = QueryRequest(
            query="S3 bucket with versioning",
            mode=QueryMode.HYBRID,
            top_k=5
        )

        response = await service.execute_query(request)

        # Verify results include both docs and code
        assert response.total_results == 2

        # Check documentation result
        doc_result = next(r for r in response.results if r.source_type == 'doc')
        assert 'S3 bucket with versioning' in doc_result.text
        assert doc_result.source == 'docs/aws-cdk/s3.md'
        assert doc_result.language == 'markdown'

        # Check code result
        code_result = next(r for r in response.results if r.source_type == 'code')
        assert 'versioned: true' in code_result.text
        assert code_result.source == 'src/aws-cdk-lib/aws-s3/lib/bucket.ts'
        assert code_result.language == 'typescript'

    @pytest.mark.asyncio
    async def test_claude_skill_citation_metadata(
        self,
        mock_vector_store,
        mock_bm25_manager,
        mock_embedding_generator,
    ):
        """Test that results include complete metadata for Claude skill citations."""
        service = QueryService(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_generator,
            bm25_manager=mock_bm25_manager,
        )

        mock_vector_store.is_initialized = True
        mock_bm25_manager.is_initialized = True

        # Mock result with complete citation metadata
        mock_vector_store.similarity_search.return_value = [
            type('SearchResult', (), {
                'text': "def authenticate_user(username: str, password: str) -> bool:",
                'metadata': {
                    'source': 'src/auth/service.py',
                    'source_type': 'code',
                    'language': 'python',
                    'symbol_name': 'authenticate_user',
                    'start_line': 45,
                    'end_line': 52,
                    'docstring': 'Authenticate a user with credentials'
                },
                'score': 0.9,
                'chunk_id': 'code_chunk_1'
            })()
        ]

        mock_bm25_manager.search_with_filters = AsyncMock(return_value=[])
        mock_vector_store.get_count.return_value = 50

        request = QueryRequest(query="user authentication")
        response = await service.execute_query(request)

        # Verify complete citation metadata
        result = response.results[0]
        assert result.source == 'src/auth/service.py'
        assert result.source_type == 'code'
        assert result.language == 'python'
        assert 'symbol_name' in result.metadata
        assert 'start_line' in result.metadata
        assert 'docstring' in result.metadata

    @pytest.mark.asyncio
    async def test_tutorial_writing_workflow(
        self,
        mock_vector_store,
        mock_bm25_manager,
        mock_embedding_generator,
    ):
        """Test queries that would support tutorial writing workflow."""
        service = QueryService(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_generator,
            bm25_manager=mock_bm25_manager,
        )

        mock_vector_store.is_initialized = True
        mock_bm25_manager.is_initialized = True

        # Mock tutorial-relevant content
        mock_vector_store.similarity_search.return_value = [
            type('SearchResult', (), {
                'text': (
                    "# Getting Started with Authentication\n\n"
                    "First, import the auth module and create a service instance."
                ),
                'metadata': {
                    'source': 'docs/tutorials/auth-getting-started.md',
                    'source_type': 'doc',
                    'language': 'markdown',
                    'content_type': 'tutorial'
                },
                'score': 0.88,
                'chunk_id': 'tutorial_doc'
            })(),
            type('SearchResult', (), {
                'text': (
                    "from auth_sdk import AuthenticationService\n"
                    "service = AuthenticationService()"
                ),
                'metadata': {
                    'source': 'examples/python/auth_quickstart.py',
                    'source_type': 'code',
                    'language': 'python',
                    'symbol_name': 'example_usage'
                },
                'score': 0.82,
                'chunk_id': 'tutorial_code'
            })()
        ]

        mock_bm25_manager.search_with_filters = AsyncMock(return_value=[])
        mock_vector_store.get_count.return_value = 75

        request = QueryRequest(
            query="getting started with authentication tutorial",
            mode=QueryMode.HYBRID
        )

        response = await service.execute_query(request)

        # Should return both tutorial docs and example code
        assert response.total_results == 2

        doc_result = next(r for r in response.results if r.source_type == 'doc')
        code_result = next(r for r in response.results if r.source_type == 'code')

        assert 'tutorial' in doc_result.metadata.get('content_type', '')
        assert code_result.language == 'python'

