"""Regression tests for duplicate chunk ID deduplication in upsert paths.

Covers requirements DEDUP-01, DEDUP-02, DEDUP-03, DEDUP-04, DEDUP-05.
"""

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_collection() -> MagicMock:
    """Mock ChromaDB collection with synchronous upsert."""
    col = MagicMock()
    col.upsert = MagicMock()
    col.metadata = {}
    return col


@pytest.fixture
def initialized_store(mock_collection: MagicMock) -> Any:
    """VectorStoreManager with mocked ChromaDB client and pre-initialized state."""
    with patch("chromadb.PersistentClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_client_cls.return_value = mock_client

        from agent_brain_server.storage.vector_store import VectorStoreManager

        store = VectorStoreManager(
            persist_dir="/tmp/test_dedup", collection_name="test_dedup"
        )
        store._collection = mock_collection
        store._initialized = True
        yield store


# ---------------------------------------------------------------------------
# ChromaDB deduplication tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_deduplicates_batch(
    initialized_store: Any, mock_collection: MagicMock
) -> None:
    """DEDUP-01/04: Batch with duplicate IDs is deduplicated; last occurrence wins."""
    ids = ["chunk_aaa", "chunk_bbb", "chunk_aaa"]  # 'chunk_aaa' duplicated
    embeddings = [[0.1], [0.2], [0.9]]  # last embedding for 'chunk_aaa' is [0.9]
    documents = ["first", "second", "third"]
    metadatas = [{"v": 1}, {"v": 2}, {"v": 99}]

    count = await initialized_store.upsert_documents(
        ids, embeddings, documents, metadatas
    )

    # Should return 2 (unique count after dedup)
    assert count == 2

    # ChromaDB upsert should have been called with deduplicated lists
    assert mock_collection.upsert.call_count == 1
    call_kwargs = mock_collection.upsert.call_args.kwargs

    # Only 2 unique IDs should reach ChromaDB
    assert len(call_kwargs["ids"]) == 2
    assert "chunk_bbb" in call_kwargs["ids"]
    assert "chunk_aaa" in call_kwargs["ids"]

    # Last-occurrence values for chunk_aaa: embedding=[0.9], meta={"v": 99}
    aaa_idx = call_kwargs["ids"].index("chunk_aaa")
    assert call_kwargs["embeddings"][aaa_idx] == [0.9]
    assert call_kwargs["metadatas"][aaa_idx] == {"v": 99}


@pytest.mark.asyncio
async def test_upsert_no_duplicates_unchanged(
    initialized_store: Any, mock_collection: MagicMock
) -> None:
    """DEDUP-05: Batch without duplicates passes through unchanged — no data loss."""
    ids = ["chunk_x", "chunk_y"]
    embeddings = [[0.1, 0.2], [0.3, 0.4]]
    documents = ["doc_x", "doc_y"]
    metadatas = [{"a": 1}, {"b": 2}]

    count = await initialized_store.upsert_documents(
        ids, embeddings, documents, metadatas
    )

    assert count == 2
    assert mock_collection.upsert.call_count == 1
    call_kwargs = mock_collection.upsert.call_args.kwargs

    # Exact same lists should reach ChromaDB
    assert call_kwargs["ids"] == ["chunk_x", "chunk_y"]
    assert call_kwargs["embeddings"] == [[0.1, 0.2], [0.3, 0.4]]
    assert call_kwargs["documents"] == ["doc_x", "doc_y"]
    assert call_kwargs["metadatas"] == [{"a": 1}, {"b": 2}]


@pytest.mark.asyncio
async def test_upsert_logs_warning_on_duplicates(
    initialized_store: Any, mock_collection: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """DEDUP-02: Warning is logged when duplicates are detected, with count info."""
    ids = ["dup_id", "other_id", "dup_id"]  # 'dup_id' appears twice
    embeddings = [[0.1], [0.2], [0.3]]
    documents = ["first", "second", "third"]
    metadatas = [{"x": 1}, {"x": 2}, {"x": 3}]

    with caplog.at_level(logging.WARNING, logger="agent_brain_server.storage.vector_store"):
        await initialized_store.upsert_documents(ids, embeddings, documents, metadatas)

    # Warning should be emitted
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) >= 1

    # The warning should mention the duplicate count
    warning_text = " ".join(r.message for r in warning_records)
    assert "1" in warning_text or "duplicate" in warning_text.lower()


@pytest.mark.asyncio
async def test_upsert_empty_batch(
    initialized_store: Any, mock_collection: MagicMock
) -> None:
    """Edge case: empty batch should not crash and should return 0."""
    count = await initialized_store.upsert_documents([], [], [], [])

    assert count == 0
    # ChromaDB upsert may be called with empty lists — no error should occur
    assert mock_collection.upsert.call_count == 1


# ---------------------------------------------------------------------------
# PostgreSQL backend deduplication tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_postgres_upsert_deduplicates(caplog: pytest.LogCaptureFixture) -> None:
    """DEDUP-03: PostgreSQL backend deduplicates batch before calling keyword_ops/vector_ops."""
    from agent_brain_server.storage.postgres.backend import PostgresBackend
    from agent_brain_server.storage.postgres.config import PostgresConfig

    config = PostgresConfig(
        host="localhost",
        port=5432,
        database="test",
        username="test",
        password="test",
    )

    backend = PostgresBackend(config)

    # Mock the ops objects so no real DB calls happen
    mock_keyword_ops = MagicMock()
    mock_keyword_ops.upsert_with_tsvector = AsyncMock()
    mock_vector_ops = MagicMock()
    mock_vector_ops.upsert_embeddings = AsyncMock()

    backend.keyword_ops = mock_keyword_ops
    backend.vector_ops = mock_vector_ops
    backend._initialized = True

    ids = ["pg_chunk_a", "pg_chunk_b", "pg_chunk_a"]  # 'pg_chunk_a' duplicated
    embeddings = [[1.0], [2.0], [9.0]]
    documents = ["text_a_first", "text_b", "text_a_last"]
    metadatas = [{"n": 1}, {"n": 2}, {"n": 99}]

    count = await backend.upsert_documents(ids, embeddings, documents, metadatas)

    # Should return 2 unique documents
    assert count == 2

    # keyword_ops.upsert_with_tsvector called exactly 2 times (not 3)
    assert mock_keyword_ops.upsert_with_tsvector.call_count == 2

    # vector_ops.upsert_embeddings called exactly 2 times
    assert mock_vector_ops.upsert_embeddings.call_count == 2

    # Verify last-occurrence semantics: "pg_chunk_a" should use last values
    calls = mock_keyword_ops.upsert_with_tsvector.call_args_list
    chunk_ids_called = [c.kwargs["chunk_id"] for c in calls]
    assert "pg_chunk_a" in chunk_ids_called
    assert "pg_chunk_b" in chunk_ids_called

    # The call for pg_chunk_a should have the last-occurrence text and metadata
    pg_a_call = next(c for c in calls if c.kwargs["chunk_id"] == "pg_chunk_a")
    assert pg_a_call.kwargs["document_text"] == "text_a_last"
    assert pg_a_call.kwargs["metadata"] == {"n": 99}
