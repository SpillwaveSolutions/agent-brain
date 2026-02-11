"""Unit tests for PostgresConnectionManager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_brain_server.storage.postgres.config import PostgresConfig
from agent_brain_server.storage.postgres.connection import (
    PostgresConnectionManager,
)
from agent_brain_server.storage.protocol import StorageError


@pytest.fixture
def config() -> PostgresConfig:
    """Create a test PostgresConfig."""
    return PostgresConfig(
        host="testhost",
        port=5432,
        database="testdb",
        user="testuser",
        password="testpass",
    )


@pytest.fixture
def manager(config: PostgresConfig) -> PostgresConnectionManager:
    """Create a test PostgresConnectionManager."""
    return PostgresConnectionManager(config)


class TestInitialize:
    """Tests for initialize() method."""

    @patch(
        "agent_brain_server.storage.postgres.connection.create_async_engine"
    )
    async def test_initialize_creates_engine(
        self,
        mock_create: MagicMock,
        manager: PostgresConnectionManager,
    ) -> None:
        """initialize() creates engine with correct parameters."""
        mock_engine = MagicMock()
        mock_create.return_value = mock_engine

        await manager.initialize()

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["pool_size"] == 10
        assert call_kwargs["max_overflow"] == 10
        assert call_kwargs["pool_pre_ping"] is True
        assert call_kwargs["pool_recycle"] == 3600

    @patch(
        "agent_brain_server.storage.postgres.connection.create_async_engine"
    )
    async def test_initialize_uses_connection_url(
        self,
        mock_create: MagicMock,
        manager: PostgresConnectionManager,
        config: PostgresConfig,
    ) -> None:
        """initialize() uses connection URL from config."""
        mock_create.return_value = MagicMock()

        await manager.initialize()

        call_args = mock_create.call_args[0]
        expected_url = config.get_connection_url()
        assert call_args[0] == expected_url


class TestClose:
    """Tests for close() method."""

    async def test_close_disposes_engine(
        self,
        manager: PostgresConnectionManager,
    ) -> None:
        """close() disposes the engine."""
        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()
        manager._engine = mock_engine

        await manager.close()

        mock_engine.dispose.assert_awaited_once()
        assert manager._engine is None

    async def test_close_idempotent(
        self,
        manager: PostgresConnectionManager,
    ) -> None:
        """close() is safe to call twice."""
        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()
        manager._engine = mock_engine

        await manager.close()
        await manager.close()  # Should not raise

        assert manager._engine is None


class TestEngineProperty:
    """Tests for engine property."""

    def test_engine_raises_when_not_initialized(
        self,
        manager: PostgresConnectionManager,
    ) -> None:
        """engine raises RuntimeError when not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = manager.engine

    def test_engine_returns_engine_after_init(
        self,
        manager: PostgresConnectionManager,
    ) -> None:
        """engine returns engine after initialization."""
        mock_engine = MagicMock()
        manager._engine = mock_engine

        assert manager.engine is mock_engine


class TestGetPoolStatus:
    """Tests for get_pool_status() method."""

    async def test_pool_status_not_initialized(
        self,
        manager: PostgresConnectionManager,
    ) -> None:
        """Returns not_initialized when engine is None."""
        status = await manager.get_pool_status()
        assert status == {"status": "not_initialized"}

    async def test_pool_status_with_queue_pool(
        self,
        manager: PostgresConnectionManager,
    ) -> None:
        """Returns pool metrics when using QueuePool."""
        from sqlalchemy.pool import QueuePool

        mock_pool = MagicMock(spec=QueuePool)
        mock_pool.size.return_value = 10
        mock_pool.checkedin.return_value = 8
        mock_pool.checkedout.return_value = 2
        mock_pool.overflow.return_value = 1

        mock_engine = MagicMock()
        mock_engine.pool = mock_pool
        manager._engine = mock_engine

        status = await manager.get_pool_status()

        assert status["status"] == "active"
        assert status["pool_size"] == 10
        assert status["checked_in"] == 8
        assert status["checked_out"] == 2
        assert status["overflow"] == 1
        assert status["total"] == 11


class TestInitializeWithRetry:
    """Tests for initialize_with_retry() method."""

    @patch(
        "agent_brain_server.storage.postgres.connection.create_async_engine"
    )
    async def test_succeeds_on_first_attempt(
        self,
        mock_create: MagicMock,
        manager: PostgresConnectionManager,
    ) -> None:
        """Succeeds on first attempt when DB is available."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect = MagicMock(return_value=mock_conn)
        mock_engine.dispose = AsyncMock()
        mock_create.return_value = mock_engine

        await manager.initialize_with_retry(max_attempts=3)

        assert manager._engine is mock_engine

    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch(
        "agent_brain_server.storage.postgres.connection.create_async_engine"
    )
    async def test_retries_on_failure_then_succeeds(
        self,
        mock_create: MagicMock,
        mock_sleep: AsyncMock,
        manager: PostgresConnectionManager,
    ) -> None:
        """Retries on failure and succeeds eventually."""
        # First call fails, second succeeds
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        mock_engine_ok = MagicMock()
        mock_engine_ok.connect = MagicMock(return_value=mock_conn)
        mock_engine_ok.dispose = AsyncMock()

        mock_engine_fail = MagicMock()
        mock_engine_fail.connect = MagicMock(
            side_effect=Exception("Connection refused")
        )
        mock_engine_fail.dispose = AsyncMock()

        mock_create.side_effect = [mock_engine_fail, mock_engine_ok]

        await manager.initialize_with_retry(
            max_attempts=3,
            initial_delay=0.01,
        )

        assert manager._engine is mock_engine_ok
        mock_sleep.assert_awaited_once()

    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch(
        "agent_brain_server.storage.postgres.connection.create_async_engine"
    )
    async def test_raises_after_max_attempts(
        self,
        mock_create: MagicMock,
        mock_sleep: AsyncMock,
        manager: PostgresConnectionManager,
    ) -> None:
        """Raises StorageError after max_attempts exhausted."""
        mock_engine = MagicMock()
        mock_engine.connect = MagicMock(
            side_effect=Exception("Connection refused")
        )
        mock_engine.dispose = AsyncMock()
        mock_create.return_value = mock_engine

        with pytest.raises(StorageError, match="failed after 2 attempts"):
            await manager.initialize_with_retry(
                max_attempts=2,
                initial_delay=0.01,
            )
