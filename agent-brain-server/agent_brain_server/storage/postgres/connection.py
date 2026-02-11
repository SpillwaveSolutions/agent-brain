"""PostgreSQL async connection pool manager.

This module provides the PostgresConnectionManager class for managing
an async SQLAlchemy engine with connection pooling, retry logic with
exponential backoff, and pool health metrics.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import QueuePool

from agent_brain_server.storage.postgres.config import PostgresConfig
from agent_brain_server.storage.protocol import StorageError

logger = logging.getLogger(__name__)


class PostgresConnectionManager:
    """Async connection pool manager for PostgreSQL.

    Manages the lifecycle of a SQLAlchemy async engine with configurable
    connection pooling, retry-on-connect with exponential backoff, and
    pool health metrics.

    Usage::

        config = PostgresConfig()
        manager = PostgresConnectionManager(config)
        await manager.initialize_with_retry()
        # ... use manager.engine ...
        await manager.close()

    Attributes:
        config: PostgreSQL configuration.
    """

    def __init__(self, config: PostgresConfig) -> None:
        """Initialize connection manager.

        Args:
            config: PostgreSQL configuration with connection and pool params.
        """
        self.config = config
        self._engine: AsyncEngine | None = None

    async def initialize(self) -> None:
        """Create the async SQLAlchemy engine with connection pooling.

        Configures the engine with pool sizing, pre-ping validation,
        and connection recycling per the config.

        Raises:
            StorageError: If engine creation fails.
        """
        try:
            self._engine = create_async_engine(
                self.config.get_connection_url(),
                echo=self.config.debug,
                pool_size=self.config.pool_size,
                max_overflow=self.config.pool_max_overflow,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
            logger.info(
                "PostgreSQL connection pool created: "
                "pool_size=%d, max_overflow=%d, total_max=%d",
                self.config.pool_size,
                self.config.pool_max_overflow,
                self.config.pool_size + self.config.pool_max_overflow,
            )
        except Exception as e:
            raise StorageError(
                f"Failed to create PostgreSQL engine: {e}",
                backend="postgres",
            ) from e

    async def initialize_with_retry(
        self,
        max_attempts: int = 5,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
    ) -> None:
        """Initialize with retry and exponential backoff.

        Retries connection on failure, useful when PostgreSQL containers
        are still starting up.

        Args:
            max_attempts: Maximum number of connection attempts.
            initial_delay: Initial delay in seconds before first retry.
            backoff_factor: Multiplier for delay between retries.

        Raises:
            StorageError: If all connection attempts fail.
        """
        delay = initial_delay

        for attempt in range(1, max_attempts + 1):
            try:
                await self.initialize()
                # Verify connectivity by testing pool
                async with self._engine.connect() as conn:  # type: ignore[union-attr]
                    await conn.execute(text("SELECT 1"))
                logger.info(
                    "PostgreSQL connection established on attempt %d/%d",
                    attempt,
                    max_attempts,
                )
                return
            except Exception as e:
                # Clean up failed engine
                if self._engine is not None:
                    try:
                        await self._engine.dispose()
                    except Exception:
                        pass
                    self._engine = None

                if attempt < max_attempts:
                    logger.warning(
                        "PostgreSQL connection attempt %d/%d failed: %s. "
                        "Retrying in %.1fs...",
                        attempt,
                        max_attempts,
                        str(e),
                        delay,
                    )
                    await asyncio.sleep(delay)
                    delay *= backoff_factor

        raise StorageError(
            f"PostgreSQL connection failed after {max_attempts} attempts. "
            f"Ensure PostgreSQL is running and accessible at "
            f"{self.config.host}:{self.config.port}",
            backend="postgres",
        )

    async def close(self) -> None:
        """Dispose the engine and release all connections.

        Idempotent -- safe to call multiple times or before initialization.
        """
        if self._engine is not None:
            await self._engine.dispose()
            logger.info("PostgreSQL connection pool closed")
            self._engine = None

    @property
    def engine(self) -> AsyncEngine:
        """Get the async engine instance.

        Returns:
            The initialized AsyncEngine.

        Raises:
            RuntimeError: If the connection manager has not been initialized.
        """
        if self._engine is None:
            raise RuntimeError(
                "Connection manager not initialized. Call initialize() first."
            )
        return self._engine

    async def get_pool_status(self) -> dict[str, Any]:
        """Get connection pool health metrics.

        Returns a dictionary with pool status suitable for health
        endpoints and monitoring.

        Returns:
            Dictionary with pool metrics:
            - pool_size: Configured pool size
            - checked_in: Number of idle connections
            - checked_out: Number of active connections
            - overflow: Number of overflow connections
            - total: Total pool capacity (size + overflow)
        """
        if self._engine is None:
            return {"status": "not_initialized"}

        pool = self._engine.pool
        if not isinstance(pool, QueuePool):
            return {"status": "active", "pool_type": type(pool).__name__}

        return {
            "status": "active",
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total": pool.size() + pool.overflow(),
        }
