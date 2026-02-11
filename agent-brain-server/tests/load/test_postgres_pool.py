"""PostgreSQL connection pool load tests."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import pytest

from agent_brain_server.storage.postgres.backend import PostgresBackend
from agent_brain_server.storage.postgres.config import PostgresConfig

try:
    import asyncpg  # noqa: F401

    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.slow,
    pytest.mark.skipif(not HAS_ASYNCPG, reason="asyncpg not installed"),
    pytest.mark.skipif(
        "DATABASE_URL" not in os.environ,
        reason="DATABASE_URL required for PostgreSQL load tests",
    ),
]


def _build_embeddings(count: int, dimensions: int) -> list[list[float]]:
    """Build deterministic embeddings for load tests."""
    embeddings: list[list[float]] = []
    for i in range(count):
        value = float(i % 8) / 8.0 + 0.1
        embeddings.append([value] * dimensions)
    return embeddings


@pytest.mark.asyncio
async def test_connection_pool_under_load() -> None:
    """Validate pool handles 50 concurrent queries + background indexing."""
    config = PostgresConfig.from_database_url(os.environ["DATABASE_URL"])
    backend = PostgresBackend(config=config)
    await backend.initialize()

    try:
        if backend.schema_manager is None:
            raise AssertionError("Postgres schema manager not initialized")

        dimensions = backend.schema_manager.embedding_dimensions
        ids = [f"load_doc_{i}" for i in range(100)]
        embeddings = _build_embeddings(len(ids), dimensions)
        documents = [
            f"Load test document number {i} about topic {i % 10}" for i in range(100)
        ]
        metadatas = [{"idx": i, "topic": f"topic_{i % 10}"} for i in range(100)]

        await backend.upsert_documents(ids, embeddings, documents, metadatas)

        async def query_task(task_id: int) -> int:
            query_embedding = [0.5] * dimensions
            results = await backend.vector_search(
                query_embedding=query_embedding,
                top_k=5,
                similarity_threshold=0.0,
            )
            assert len(results) > 0, f"Query {task_id} returned no results"
            return task_id

        async def background_indexing_task() -> None:
            for i in range(10):
                await backend.upsert_documents(
                    ids=[f"bg_{i}"],
                    embeddings=_build_embeddings(1, dimensions),
                    documents=[f"Background document {i}"],
                    metadatas=[{"idx": i, "source": "background"}],
                )
                await asyncio.sleep(0.05)

        query_tasks = [query_task(i) for i in range(50)]
        bg_task = background_indexing_task()

        results = await asyncio.gather(*query_tasks, bg_task, return_exceptions=True)
        errors = [result for result in results if isinstance(result, Exception)]
        assert not errors, f"Concurrent operations raised errors: {errors}"

        metrics = await backend.connection_manager.get_pool_status()
        assert isinstance(metrics, dict)
        assert metrics.get("status") == "active"
        if "pool_size" in metrics:
            assert metrics["pool_size"] >= 0
            assert metrics["checked_in"] >= 0
            assert metrics["checked_out"] >= 0
            assert metrics["overflow"] >= 0
            assert metrics["total"] == metrics["pool_size"] + metrics["overflow"]

    finally:
        await backend.reset()
        await backend.close()


@pytest.mark.asyncio
async def test_connection_pool_metrics_valid() -> None:
    """Validate pool metrics are present and within expected bounds."""
    config = PostgresConfig.from_database_url(os.environ["DATABASE_URL"])
    backend = PostgresBackend(config=config)
    await backend.initialize()

    try:
        metrics: dict[str, Any] = await backend.connection_manager.get_pool_status()
        assert isinstance(metrics, dict)
        assert metrics.get("status") == "active"

        if "pool_size" in metrics:
            assert metrics["pool_size"] >= 0
            assert metrics["overflow"] >= 0
            assert metrics["total"] >= metrics["pool_size"]
            assert metrics["total"] == metrics["pool_size"] + metrics["overflow"]
        else:
            assert "pool_type" in metrics

    finally:
        await backend.close()
