"""Backend wiring smoke tests.

Verify that factory-selected storage backend drives service behavior.
These tests are mock-based and always run in task before-push
(no PostgreSQL database required).
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from agent_brain_server.services.indexing_service import IndexingService
from agent_brain_server.services.query_service import QueryService
from agent_brain_server.storage.chroma.backend import ChromaBackend
from agent_brain_server.storage.factory import (
    get_storage_backend,
    reset_storage_backend_cache,
)


@pytest.fixture(autouse=True)
def cleanup_backend_cache() -> Generator[None, None, None]:
    """Reset backend cache between tests."""
    reset_storage_backend_cache()
    yield
    reset_storage_backend_cache()


class TestBackendWiring:
    """Test suite for backend wiring logic."""

    def test_storage_backend_parameter_takes_precedence(self) -> None:
        """Verify storage_backend parameter takes precedence over legacy params.

        When storage_backend is provided to QueryService and IndexingService,
        it should be used directly (not wrapped in ChromaBackend).
        """
        # Create a mock backend
        mock_backend = MagicMock()
        mock_backend.is_initialized = True

        # Pass to QueryService
        query_service = QueryService(storage_backend=mock_backend)
        assert query_service.storage_backend is mock_backend

        # Pass to IndexingService
        indexing_service = IndexingService(storage_backend=mock_backend)
        assert indexing_service.storage_backend is mock_backend

    def test_legacy_params_still_wrap_in_chroma_backend(self) -> None:
        """Verify legacy vector_store/bm25_manager params wrap in ChromaBackend.

        This ensures backward compatibility with existing tests that pass
        vector_store and bm25_manager directly.
        """
        # Create mock legacy parameters
        mock_vector_store = MagicMock()
        mock_bm25_manager = MagicMock()

        # Pass legacy params to QueryService
        query_service = QueryService(
            vector_store=mock_vector_store, bm25_manager=mock_bm25_manager
        )
        assert isinstance(query_service.storage_backend, ChromaBackend)
        assert query_service.storage_backend.vector_store is mock_vector_store
        assert query_service.storage_backend.bm25_manager is mock_bm25_manager

        # Pass legacy params to IndexingService
        indexing_service = IndexingService(
            vector_store=mock_vector_store, bm25_manager=mock_bm25_manager
        )
        assert isinstance(indexing_service.storage_backend, ChromaBackend)
        assert indexing_service.storage_backend.vector_store is mock_vector_store
        assert indexing_service.storage_backend.bm25_manager is mock_bm25_manager

    def test_chroma_factory_returns_chroma_backend(self) -> None:
        """Verify factory returns ChromaBackend when backend type is chroma."""
        # Reset cache to force fresh instance
        reset_storage_backend_cache()

        # Patch get_effective_backend_type to return "chroma"
        with patch(
            "agent_brain_server.storage.factory.get_effective_backend_type"
        ) as mock_get_type:
            mock_get_type.return_value = "chroma"

            # Get backend from factory
            backend = get_storage_backend()
            assert isinstance(backend, ChromaBackend)

            # Pass to QueryService and verify it uses the same instance
            query_service = QueryService(storage_backend=backend)
            assert query_service.storage_backend is backend

    def test_postgres_factory_returns_postgres_backend(self) -> None:
        """Verify factory returns PostgresBackend when backend type is postgres.

        This test mocks the PostgresBackend lazy import to avoid requiring
        asyncpg/sqlalchemy dependencies.
        """
        # Reset cache to force fresh instance
        reset_storage_backend_cache()

        # Create mock PostgresBackend and PostgresConfig
        mock_postgres_backend = MagicMock()
        mock_postgres_config = MagicMock()

        # Mock provider settings with postgres config
        mock_provider_settings = MagicMock()
        mock_provider_settings.storage.postgres = {
            "host": "localhost",
            "port": 5432,
            "database": "test_db",
            "user": "test_user",
            "password": "test_pass",
        }

        # Patch the lazy imports inside the factory's postgres branch
        with patch(
            "agent_brain_server.storage.factory.get_effective_backend_type"
        ) as mock_get_type, patch(
            "agent_brain_server.storage.factory.load_provider_settings"
        ) as mock_load_settings, patch.dict(
            "sys.modules",
            {
                "agent_brain_server.storage.postgres": MagicMock(
                    PostgresBackend=MagicMock(return_value=mock_postgres_backend),
                    PostgresConfig=MagicMock(return_value=mock_postgres_config),
                )
            },
        ):
            # Setup mocks
            mock_get_type.return_value = "postgres"
            mock_load_settings.return_value = mock_provider_settings

            # Get backend from factory
            backend = get_storage_backend()
            assert backend is mock_postgres_backend

            # Pass to QueryService and verify it uses the same instance
            query_service = QueryService(storage_backend=backend)
            assert query_service.storage_backend is backend

    @pytest.mark.asyncio
    async def test_graph_query_rejected_on_postgres_backend(self) -> None:
        """Verify graph queries raise ValueError on postgres backend.

        Graph queries require ChromaDB's SimplePropertyGraphStore and should
        fail explicitly on postgres backend with actionable error message.
        The backend check happens before ENABLE_GRAPH_INDEX check.
        """
        # Create a mock postgres backend
        mock_backend = MagicMock()
        mock_backend.is_initialized = True

        # Create QueryService with mock backend
        query_service = QueryService(storage_backend=mock_backend)

        # Create a mock graph query request
        mock_request = MagicMock()
        mock_request.query = "test query"
        mock_request.mode = "graph"
        mock_request.top_k = 5

        # Mock get_effective_backend_type where it's imported
        # in _execute_graph_query from agent_brain_server.storage
        with patch(
            "agent_brain_server.storage.get_effective_backend_type"
        ) as mock_get_type:
            mock_get_type.return_value = "postgres"

            # Attempt to execute graph query
            with pytest.raises(ValueError) as exc_info:
                await query_service._execute_graph_query(mock_request)

            # Verify error message mentions ChromaDB requirement
            error_msg = str(exc_info.value)
            # Should get the backend compatibility error
            assert "chroma" in error_msg.lower()
            assert "backend" in error_msg.lower()
