"""Integration tests for ``GET /query/chunk/{chunk_id}``.

Covers the 200 / 404 paths plus the explicit "no embedding in payload"
assertion locked by the v2 design doc §2.3.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_brain_server.models import ChunkRecord


@pytest.fixture
def sample_chunk_record() -> ChunkRecord:
    """Build a representative ChunkRecord used across the 200-path tests."""
    return ChunkRecord(
        chunk_id="chunk_known_abc",
        parent_doc_id="/repo/docs/auth.md",
        source="/repo/docs/auth.md",
        content="Authentication is configured via JWT...",
        summary="Top-level overview of the auth flow.",
        folder_id="/repo/docs",
        token_count=128,
        language=None,
    )


class TestChunkByIdEndpoint:
    """Route-level tests for the new chunk lookup endpoint."""

    def test_returns_200_with_full_chunk_record(
        self,
        app_with_mocks,
        client,
        sample_chunk_record: ChunkRecord,
    ) -> None:
        """200 path: payload matches ChunkRecord and excludes embedding."""
        storage_mock = MagicMock(spec=["get_chunk_by_id"])
        storage_mock.get_chunk_by_id = AsyncMock(return_value=sample_chunk_record)
        app_with_mocks.state.storage_backend = storage_mock

        response = client.get(f"/query/chunk/{sample_chunk_record.chunk_id}")

        assert response.status_code == 200
        body = response.json()
        # Locked field set per v2 design doc §2.3.
        assert set(body.keys()) == {
            "chunk_id",
            "parent_doc_id",
            "source",
            "content",
            "summary",
            "folder_id",
            "token_count",
            "language",
        }
        # Critical: never leak embeddings on this endpoint.
        assert "embedding" not in body

        assert body["chunk_id"] == sample_chunk_record.chunk_id
        assert body["content"] == sample_chunk_record.content
        assert body["parent_doc_id"] == sample_chunk_record.parent_doc_id
        assert body["folder_id"] == sample_chunk_record.folder_id

        storage_mock.get_chunk_by_id.assert_awaited_once_with(
            sample_chunk_record.chunk_id
        )

    def test_returns_404_with_structured_error(self, app_with_mocks, client) -> None:
        """404 path: body carries error code + chunk_id (not 200-found-false)."""
        storage_mock = MagicMock(spec=["get_chunk_by_id"])
        storage_mock.get_chunk_by_id = AsyncMock(return_value=None)
        app_with_mocks.state.storage_backend = storage_mock

        response = client.get("/query/chunk/nonexistent-id")

        assert response.status_code == 404
        body = response.json()
        assert body == {
            "detail": {
                "error": "chunk_not_found",
                "chunk_id": "nonexistent-id",
            }
        }

    def test_storage_error_surfaces_as_500(self, app_with_mocks, client) -> None:
        """StorageError from the backend is wrapped as HTTP 500."""
        from agent_brain_server.storage.protocol import StorageError

        storage_mock = MagicMock(spec=["get_chunk_by_id"])
        storage_mock.get_chunk_by_id = AsyncMock(
            side_effect=StorageError("boom", backend="chroma")
        )
        app_with_mocks.state.storage_backend = storage_mock

        response = client.get("/query/chunk/some-id")

        assert response.status_code == 500
        assert "Chunk lookup failed" in response.json()["detail"]

    def test_chunk_id_with_special_characters(
        self,
        app_with_mocks,
        client,
        sample_chunk_record: ChunkRecord,
    ) -> None:
        """Chunk IDs with URL-safe special characters round-trip cleanly."""
        weird_id = "doc-abc_123.42"
        record = sample_chunk_record.model_copy(update={"chunk_id": weird_id})

        storage_mock = MagicMock(spec=["get_chunk_by_id"])
        storage_mock.get_chunk_by_id = AsyncMock(return_value=record)
        app_with_mocks.state.storage_backend = storage_mock

        response = client.get(f"/query/chunk/{weird_id}")

        assert response.status_code == 200
        assert response.json()["chunk_id"] == weird_id
        storage_mock.get_chunk_by_id.assert_awaited_once_with(weird_id)
