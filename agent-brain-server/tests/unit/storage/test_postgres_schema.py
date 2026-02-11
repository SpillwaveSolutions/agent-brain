"""Unit tests for PostgresSchemaManager."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_brain_server.storage.postgres.config import PostgresConfig
from agent_brain_server.storage.postgres.connection import (
    PostgresConnectionManager,
)
from agent_brain_server.storage.postgres.schema import PostgresSchemaManager
from agent_brain_server.storage.protocol import StorageError


def _make_mock_engine() -> MagicMock:
    """Create a mock async engine with begin()/connect() context managers."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    mock_engine = MagicMock()
    mock_engine.begin = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        )
    )
    mock_engine.connect = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        )
    )
    return mock_engine


@pytest.fixture
def config() -> PostgresConfig:
    """Create a test PostgresConfig."""
    return PostgresConfig(hnsw_m=16, hnsw_ef_construction=64)


@pytest.fixture
def connection_manager(config: PostgresConfig) -> PostgresConnectionManager:
    """Create a mocked connection manager."""
    manager = PostgresConnectionManager(config)
    manager._engine = _make_mock_engine()
    return manager


@pytest.fixture
def schema_manager(
    connection_manager: PostgresConnectionManager,
    config: PostgresConfig,
) -> PostgresSchemaManager:
    """Create a schema manager with mocked connection."""
    return PostgresSchemaManager(
        connection_manager=connection_manager,
        embedding_dimensions=3072,
        config=config,
    )


def _get_executed_sql(mock_engine: Any) -> list[str]:
    """Extract SQL text from all execute() calls on the mock engine."""
    # Get the mock conn from begin() context manager
    begin_cm = mock_engine.begin.return_value
    mock_conn = begin_cm.__aenter__.return_value
    sqls: list[str] = []
    for c in mock_conn.execute.call_args_list:
        text_obj = c[0][0]
        sqls.append(str(text_obj.text if hasattr(text_obj, "text") else text_obj))
    return sqls


class TestCreateSchema:
    """Tests for create_schema() method."""

    async def test_creates_vector_extension(
        self,
        schema_manager: PostgresSchemaManager,
        connection_manager: PostgresConnectionManager,
    ) -> None:
        """create_schema() executes CREATE EXTENSION vector."""
        await schema_manager.create_schema()

        sqls = _get_executed_sql(connection_manager._engine)
        assert any("CREATE EXTENSION IF NOT EXISTS vector" in s for s in sqls)

    async def test_vector_dimension_in_sql(
        self,
        schema_manager: PostgresSchemaManager,
        connection_manager: PostgresConnectionManager,
    ) -> None:
        """create_schema() uses correct vector dimension."""
        await schema_manager.create_schema()

        sqls = _get_executed_sql(connection_manager._engine)
        assert any("vector(3072)" in s for s in sqls)

    async def test_hnsw_index_params(
        self,
        schema_manager: PostgresSchemaManager,
        connection_manager: PostgresConnectionManager,
    ) -> None:
        """create_schema() uses HNSW parameters from config."""
        await schema_manager.create_schema()

        sqls = _get_executed_sql(connection_manager._engine)
        assert any("m = 16" in s for s in sqls)
        assert any("ef_construction = 64" in s for s in sqls)

    async def test_gin_tsvector_index(
        self,
        schema_manager: PostgresSchemaManager,
        connection_manager: PostgresConnectionManager,
    ) -> None:
        """create_schema() creates GIN index for tsvector."""
        await schema_manager.create_schema()

        sqls = _get_executed_sql(connection_manager._engine)
        assert any("gin(tsv)" in s for s in sqls)

    async def test_embedding_metadata_table(
        self,
        schema_manager: PostgresSchemaManager,
        connection_manager: PostgresConnectionManager,
    ) -> None:
        """create_schema() creates embedding_metadata table."""
        await schema_manager.create_schema()

        sqls = _get_executed_sql(connection_manager._engine)
        assert any("embedding_metadata" in s for s in sqls)


class TestValidateDimensions:
    """Tests for validate_dimensions() method."""

    async def test_passes_when_dimensions_match(
        self,
        schema_manager: PostgresSchemaManager,
    ) -> None:
        """validate_dimensions() passes when dimensions match."""
        # Mock get_embedding_metadata to return matching dims
        schema_manager.get_embedding_metadata = AsyncMock(  # type: ignore[method-assign]
            return_value={"dimensions": 3072}
        )

        # Should not raise
        await schema_manager.validate_dimensions()

    async def test_raises_on_dimension_mismatch(
        self,
        schema_manager: PostgresSchemaManager,
    ) -> None:
        """validate_dimensions() raises StorageError on mismatch."""
        schema_manager.get_embedding_metadata = AsyncMock(  # type: ignore[method-assign]
            return_value={"dimensions": 1536}
        )

        with pytest.raises(StorageError, match="dimension mismatch"):
            await schema_manager.validate_dimensions()

    async def test_passes_when_no_metadata(
        self,
        schema_manager: PostgresSchemaManager,
    ) -> None:
        """validate_dimensions() passes on first run (no metadata)."""
        schema_manager.get_embedding_metadata = AsyncMock(  # type: ignore[method-assign]
            return_value=None
        )

        # Should not raise
        await schema_manager.validate_dimensions()


class TestStoreEmbeddingMetadata:
    """Tests for store_embedding_metadata() method."""

    async def test_executes_upsert_sql(
        self,
        schema_manager: PostgresSchemaManager,
        connection_manager: PostgresConnectionManager,
    ) -> None:
        """store_embedding_metadata() executes INSERT/ON CONFLICT SQL."""
        await schema_manager.store_embedding_metadata(
            provider="openai",
            model="text-embedding-3-large",
            dimensions=3072,
        )

        sqls = _get_executed_sql(connection_manager._engine)
        assert any("INSERT INTO embedding_metadata" in s for s in sqls)
        assert any("ON CONFLICT" in s for s in sqls)


class TestGetEmbeddingMetadata:
    """Tests for get_embedding_metadata() method."""

    async def test_returns_dict_when_metadata_exists(
        self,
        schema_manager: PostgresSchemaManager,
        connection_manager: PostgresConnectionManager,
    ) -> None:
        """get_embedding_metadata() returns dict when metadata exists."""
        # Set up mock to return a row
        mock_result = MagicMock()
        mock_row = ("openai", "text-embedding-3-large", 3072)
        mock_result.fetchone.return_value = mock_row

        # Get the mock conn from connect() context manager
        connect_cm = connection_manager._engine.connect.return_value  # type: ignore[union-attr]
        mock_conn = connect_cm.__aenter__.return_value
        mock_conn.execute = AsyncMock(return_value=mock_result)

        result = await schema_manager.get_embedding_metadata()

        assert result is not None
        assert result["provider"] == "openai"
        assert result["model"] == "text-embedding-3-large"
        assert result["dimensions"] == 3072

    async def test_returns_none_when_no_metadata(
        self,
        schema_manager: PostgresSchemaManager,
        connection_manager: PostgresConnectionManager,
    ) -> None:
        """get_embedding_metadata() returns None when no metadata."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None

        connect_cm = connection_manager._engine.connect.return_value  # type: ignore[union-attr]
        mock_conn = connect_cm.__aenter__.return_value
        mock_conn.execute = AsyncMock(return_value=mock_result)

        result = await schema_manager.get_embedding_metadata()

        assert result is None

    async def test_returns_none_when_table_not_exists(
        self,
        schema_manager: PostgresSchemaManager,
        connection_manager: PostgresConnectionManager,
    ) -> None:
        """get_embedding_metadata() returns None when table does not exist."""
        connect_cm = connection_manager._engine.connect.return_value  # type: ignore[union-attr]
        mock_conn = connect_cm.__aenter__.return_value
        mock_conn.execute = AsyncMock(
            side_effect=Exception(
                'relation "embedding_metadata" does not exist'
            )
        )

        result = await schema_manager.get_embedding_metadata()

        assert result is None
