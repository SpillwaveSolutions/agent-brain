"""Integration-level tests for ManifestTracker integration in IndexingService.

Tests verify that the incremental indexing pipeline correctly:
- Creates manifests on first-time index
- Skips unchanged files on subsequent runs
- Processes only changed/new files
- Evicts chunks for deleted files
- Bypasses manifest when force=True
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_brain_server.models import IndexingStatusEnum, IndexRequest
from agent_brain_server.services.indexing_service import IndexingService
from agent_brain_server.services.manifest_tracker import (
    FileRecord,
    FolderManifest,
    ManifestTracker,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_storage_backend(chunk_count: int = 0) -> AsyncMock:
    """Create a mock StorageBackendProtocol."""
    storage = AsyncMock()
    storage.is_initialized = True
    storage.initialize = AsyncMock()
    storage.get_count = AsyncMock(return_value=chunk_count)
    storage.get_embedding_metadata = AsyncMock(return_value=None)
    storage.set_embedding_metadata = AsyncMock()
    storage.upsert_documents = AsyncMock()
    storage.delete_by_ids = AsyncMock(return_value=0)
    storage.get_by_id = AsyncMock(return_value=None)
    storage.validate_embedding_compatibility = MagicMock()
    # Do NOT set bm25_manager on mock — IndexingService will use the
    # explicitly passed bm25_manager kwarg instead
    return storage


def _make_doc(source_path: str) -> MagicMock:
    """Create a mock LlamaIndex Document."""
    doc = MagicMock()
    doc.metadata = {"source": source_path, "source_type": "doc"}
    doc.text = f"Content of {source_path}"
    return doc


def _make_chunk(chunk_id: str, source_path: str) -> MagicMock:
    """Create a mock TextChunk."""
    chunk = MagicMock()
    chunk.chunk_id = chunk_id
    chunk.text = f"Chunk text from {source_path}"
    meta = MagicMock()
    meta.to_dict = MagicMock(return_value={"source": source_path, "source_type": "doc"})
    meta.language = None
    chunk.metadata = meta
    return chunk


def _make_indexing_service(
    storage: AsyncMock,
    manifest_tracker: ManifestTracker,
    doc_loader_docs: list[Any],
    chunks: list[Any],
) -> IndexingService:
    """Create an IndexingService with mocked dependencies."""
    mock_loader = AsyncMock()
    mock_loader.load_files = AsyncMock(return_value=doc_loader_docs)

    mock_chunker = AsyncMock()
    mock_chunker.chunk_documents = AsyncMock(return_value=chunks)

    mock_embedding_gen = MagicMock()
    mock_embedding_gen.get_embedding_dimensions = MagicMock(return_value=1536)
    mock_embedding_gen.embed_chunks = AsyncMock(
        return_value=[[0.1] * 1536 for _ in chunks]
    )

    mock_bm25 = MagicMock()
    mock_bm25.build_index = MagicMock()

    mock_graph = MagicMock()
    mock_graph.get_status = MagicMock(
        return_value=MagicMock(
            enabled=False,
            initialized=False,
            entity_count=0,
            relationship_count=0,
            store_type="none",
        )
    )

    service = IndexingService(
        storage_backend=storage,
        document_loader=mock_loader,
        chunker=mock_chunker,
        embedding_generator=mock_embedding_gen,
        bm25_manager=mock_bm25,
        graph_index_manager=mock_graph,
        manifest_tracker=manifest_tracker,
    )
    return service


def _patch_chunkers(chunks: list[Any]) -> Any:
    """Return a context manager that patches ContextAwareChunker to return chunks."""
    import contextlib

    @contextlib.contextmanager  # type: ignore[misc]
    def ctx() -> Any:
        mock_doc_chunker = AsyncMock()
        mock_doc_chunker.chunk_documents = AsyncMock(return_value=chunks)
        with patch(
            "agent_brain_server.services.indexing_service.ContextAwareChunker",
            return_value=mock_doc_chunker,
        ):
            yield

    return ctx()


# ---------------------------------------------------------------------------
# Test: first-time index creates manifest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_time_index_creates_manifest(tmp_path: Path) -> None:
    """First-time index should create a manifest file with file entries."""
    folder = str(tmp_path / "docs")
    Path(folder).mkdir()

    file1 = str(tmp_path / "docs" / "a.md")
    file2 = str(tmp_path / "docs" / "b.md")
    Path(file1).write_text("content a")
    Path(file2).write_text("content b")

    manifests_dir = tmp_path / "manifests"
    tracker = ManifestTracker(manifests_dir=manifests_dir)

    docs = [_make_doc(file1), _make_doc(file2)]
    chunk1 = _make_chunk("c1", file1)
    chunk2 = _make_chunk("c2", file2)
    storage = _make_storage_backend()

    service = _make_indexing_service(storage, tracker, docs, [chunk1, chunk2])

    request = IndexRequest(folder_path=folder)
    with _patch_chunkers([chunk1, chunk2]):
        await service._run_indexing_pipeline(request, "job_test")

    # Manifest should now exist
    manifest = await tracker.load(str(Path(folder).resolve()))
    assert manifest is not None
    resolved_file1 = str(Path(file1).resolve())
    resolved_file2 = str(Path(file2).resolve())
    assert resolved_file1 in manifest.files
    assert resolved_file2 in manifest.files
    assert "c1" in manifest.files[resolved_file1].chunk_ids
    assert "c2" in manifest.files[resolved_file2].chunk_ids


# ---------------------------------------------------------------------------
# Test: incremental index skips unchanged files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_incremental_index_skips_unchanged_files(tmp_path: Path) -> None:
    """Incremental run with unchanged files should not reprocess them."""
    folder = str(tmp_path / "docs")
    Path(folder).mkdir()

    file1 = str(tmp_path / "docs" / "a.md")
    Path(file1).write_text("content a")

    manifests_dir = tmp_path / "manifests"
    tracker = ManifestTracker(manifests_dir=manifests_dir)

    # Pre-populate manifest so file appears unchanged
    from agent_brain_server.services.manifest_tracker import compute_file_checksum

    checksum = await asyncio.to_thread(compute_file_checksum, file1)
    import os

    mtime = os.stat(file1).st_mtime

    abs_folder = str(Path(folder).resolve())
    abs_file1 = str(Path(file1).resolve())
    manifest = FolderManifest(folder_path=abs_folder)
    manifest.files[abs_file1] = FileRecord(
        checksum=checksum, mtime=mtime, chunk_ids=["old-chunk-1"]
    )
    await tracker.save(manifest)

    docs = [_make_doc(file1)]
    chunk1 = _make_chunk("c1", file1)
    storage = _make_storage_backend()

    service = _make_indexing_service(storage, tracker, docs, [chunk1])

    request = IndexRequest(folder_path=folder)
    result = await service._run_indexing_pipeline(request, "job_test")

    # Should get an eviction summary back with zero chunks_to_create
    assert result is not None
    assert result["chunks_to_create"] == 0
    assert len(result["files_unchanged"]) == 1
    assert service._state.status == IndexingStatusEnum.COMPLETED

    # Storage upsert should NOT have been called (no new chunks)
    storage.upsert_documents.assert_not_called()


# ---------------------------------------------------------------------------
# Test: force=True bypasses manifest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_force_bypasses_manifest(tmp_path: Path) -> None:
    """force=True should evict all prior chunks and process all files."""
    folder = str(tmp_path / "docs")
    Path(folder).mkdir()

    file1 = str(tmp_path / "docs" / "a.md")
    Path(file1).write_text("content a")

    manifests_dir = tmp_path / "manifests"
    tracker = ManifestTracker(manifests_dir=manifests_dir)

    # Pre-populate manifest with an old chunk
    abs_folder = str(Path(folder).resolve())
    abs_file1 = str(Path(file1).resolve())
    old_manifest = FolderManifest(folder_path=abs_folder)
    old_manifest.files[abs_file1] = FileRecord(
        checksum="oldchecksum", mtime=0.0, chunk_ids=["old-chunk-1"]
    )
    await tracker.save(old_manifest)

    docs = [_make_doc(file1)]
    chunk1 = _make_chunk("c1-new", file1)
    storage = _make_storage_backend()
    storage.delete_by_ids = AsyncMock(return_value=1)

    service = _make_indexing_service(storage, tracker, docs, [chunk1])

    request = IndexRequest(folder_path=folder, force=True)
    with _patch_chunkers([chunk1]):
        result = await service._run_indexing_pipeline(request, "job_test")

    # Should process all files and evict old chunks
    assert result is not None
    assert result["chunks_evicted"] == 1
    assert result["chunks_to_create"] == 1
    storage.delete_by_ids.assert_called_once_with(["old-chunk-1"])


# ---------------------------------------------------------------------------
# Test: deleted file chunks are evicted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deleted_file_chunks_evicted(tmp_path: Path) -> None:
    """Files present in manifest but not on disk should have chunks evicted."""
    folder = str(tmp_path / "docs")
    Path(folder).mkdir()

    file1 = str(tmp_path / "docs" / "a.md")
    file2 = str(tmp_path / "docs" / "b.md")
    Path(file1).write_text("content a")
    Path(file2).write_text("content b")

    manifests_dir = tmp_path / "manifests"
    tracker = ManifestTracker(manifests_dir=manifests_dir)

    # Pre-populate manifest with 3 files, one of which doesn't exist on disk
    from agent_brain_server.services.manifest_tracker import compute_file_checksum

    abs_folder = str(Path(folder).resolve())
    abs_file1 = str(Path(file1).resolve())
    abs_file2 = str(Path(file2).resolve())
    abs_deleted = str(tmp_path / "docs" / "deleted.md")

    checksum1 = await asyncio.to_thread(compute_file_checksum, file1)
    checksum2 = await asyncio.to_thread(compute_file_checksum, file2)
    import os

    manifest = FolderManifest(folder_path=abs_folder)
    manifest.files[abs_file1] = FileRecord(
        checksum=checksum1, mtime=os.stat(file1).st_mtime, chunk_ids=["c1"]
    )
    manifest.files[abs_file2] = FileRecord(
        checksum=checksum2, mtime=os.stat(file2).st_mtime, chunk_ids=["c2"]
    )
    manifest.files[abs_deleted] = FileRecord(
        checksum="old", mtime=0.0, chunk_ids=["deleted-chunk-1"]
    )
    await tracker.save(manifest)

    # Only file1 and file2 on disk
    docs = [_make_doc(file1), _make_doc(file2)]
    chunk1 = _make_chunk("c1", file1)
    chunk2 = _make_chunk("c2", file2)
    storage = _make_storage_backend()
    storage.delete_by_ids = AsyncMock(return_value=1)

    service = _make_indexing_service(storage, tracker, docs, [chunk1, chunk2])

    request = IndexRequest(folder_path=folder)
    with _patch_chunkers([chunk1, chunk2]):
        result = await service._run_indexing_pipeline(request, "job_test")

    # deleted.md's chunks should be evicted
    assert result is not None
    assert result["chunks_evicted"] == 1
    assert abs_deleted in result["files_deleted"]
    storage.delete_by_ids.assert_called_once_with(["deleted-chunk-1"])


# ---------------------------------------------------------------------------
# Test: zero-change run - no reindex needed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zero_change_run_succeeds(tmp_path: Path) -> None:
    """Zero-change incremental run should succeed without calling upsert."""
    folder = str(tmp_path / "docs")
    Path(folder).mkdir()

    file1 = str(tmp_path / "docs" / "a.md")
    Path(file1).write_text("content a")

    manifests_dir = tmp_path / "manifests"
    tracker = ManifestTracker(manifests_dir=manifests_dir)

    import os

    from agent_brain_server.services.manifest_tracker import compute_file_checksum

    checksum = await asyncio.to_thread(compute_file_checksum, file1)
    mtime = os.stat(file1).st_mtime

    abs_folder = str(Path(folder).resolve())
    abs_file1 = str(Path(file1).resolve())
    manifest = FolderManifest(folder_path=abs_folder)
    manifest.files[abs_file1] = FileRecord(
        checksum=checksum, mtime=mtime, chunk_ids=["c1"]
    )
    await tracker.save(manifest)

    docs = [_make_doc(file1)]
    storage = _make_storage_backend()

    service = _make_indexing_service(storage, tracker, docs, [])

    request = IndexRequest(folder_path=folder)
    result = await service._run_indexing_pipeline(request, "job_test")

    assert result is not None
    assert result["chunks_to_create"] == 0
    assert result["chunks_evicted"] == 0
    assert service._state.status == IndexingStatusEnum.COMPLETED
    storage.upsert_documents.assert_not_called()

    # Manifest should still exist
    saved_manifest = await tracker.load(abs_folder)
    assert saved_manifest is not None
    assert abs_file1 in saved_manifest.files
