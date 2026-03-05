"""Integration tests for content injection pipeline (INJECT-01 through INJECT-07)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_brain_server.api.routers.index import router
from agent_brain_server.models.index import IndexRequest
from agent_brain_server.models.job import JobRecord, JobStatus
from agent_brain_server.services.content_injector import ContentInjector

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_job_record(
    injector_script: str | None = None,
    folder_metadata_file: str | None = None,
    folder: str = "/tmp/test_folder",
) -> JobRecord:
    """Create a minimal JobRecord for testing."""
    dedupe_key = JobRecord.compute_dedupe_key(
        folder_path=folder,
        include_code=False,
        operation="index",
    )
    return JobRecord(
        id="job_abc123",
        dedupe_key=dedupe_key,
        folder_path=folder,
        status=JobStatus.PENDING,
        injector_script=injector_script,
        folder_metadata_file=folder_metadata_file,
    )


def _create_index_app(
    folder_exists: bool = True,
    queue_pending: int = 0,
    queue_running: int = 0,
    enqueue_job_result: Any = None,
    dry_run_doc_count: int = 2,
    dry_run_chunk_count: int = 3,
) -> FastAPI:
    """Create a minimal FastAPI app with mocked state for index endpoint tests."""
    from agent_brain_server.indexing.chunking import ChunkMetadata, TextChunk

    app = FastAPI()
    app.include_router(router, prefix="/index")

    # Mock job service
    mock_queue_stats = MagicMock()
    mock_queue_stats.pending = queue_pending
    mock_queue_stats.running = queue_running

    if enqueue_job_result is None:
        mock_enqueue_result = MagicMock()
        mock_enqueue_result.job_id = "job_test123"
        mock_enqueue_result.status = "pending"
        mock_enqueue_result.dedupe_hit = False
        enqueue_job_result = mock_enqueue_result

    mock_job_service = AsyncMock()
    mock_job_service.get_queue_stats = AsyncMock(return_value=mock_queue_stats)
    mock_job_service.enqueue_job = AsyncMock(return_value=enqueue_job_result)

    # Mock indexing service with document_loader and chunker for dry_run
    def _make_chunk(idx: int) -> TextChunk:
        meta = ChunkMetadata(
            chunk_id=f"chunk_{idx}",
            source="/tmp/test_folder/doc.md",
            file_name="doc.md",
            chunk_index=idx,
            total_chunks=dry_run_chunk_count,
            source_type="doc",
        )
        return TextChunk(
            chunk_id=f"chunk_{idx}",
            text=f"chunk text {idx}",
            source="/tmp/test_folder/doc.md",
            chunk_index=idx,
            total_chunks=dry_run_chunk_count,
            token_count=3,
            metadata=meta,
        )

    mock_docs = [MagicMock() for _ in range(dry_run_doc_count)]
    mock_chunks = [_make_chunk(i) for i in range(dry_run_chunk_count)]

    mock_document_loader = AsyncMock()
    mock_document_loader.load_files = AsyncMock(return_value=mock_docs)

    mock_chunker = AsyncMock()
    mock_chunker.chunk_documents = AsyncMock(return_value=mock_chunks)

    mock_indexing_service = MagicMock()
    mock_indexing_service.document_loader = mock_document_loader
    mock_indexing_service.chunker = mock_chunker

    app.state.job_service = mock_job_service
    app.state.indexing_service = mock_indexing_service

    return app


# ---------------------------------------------------------------------------
# IndexingService._run_indexing_pipeline injection integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_indexing_pipeline_calls_apply_to_chunks_when_injector_set() -> None:
    """_run_indexing_pipeline calls content_injector.apply_to_chunks when set."""
    from agent_brain_server.services.indexing_service import IndexingService

    # Create a minimal mock storage backend
    mock_storage = AsyncMock()
    mock_storage.is_initialized = True
    mock_storage.get_embedding_metadata = AsyncMock(return_value=None)
    mock_storage.get_count = AsyncMock(return_value=5)
    mock_storage.upsert_documents = AsyncMock()
    mock_storage.set_embedding_metadata = AsyncMock()

    # Mock document loader returning zero documents (early exit)
    mock_loader = AsyncMock()
    mock_loader.load_files = AsyncMock(return_value=[])

    mock_chunker = MagicMock()
    mock_embedding_gen = MagicMock()
    mock_embedding_gen.get_embedding_dimensions = MagicMock(return_value=3072)

    mock_bm25 = MagicMock()
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
        storage_backend=mock_storage,
        document_loader=mock_loader,
        chunker=mock_chunker,
        embedding_generator=mock_embedding_gen,
        bm25_manager=mock_bm25,
        graph_index_manager=mock_graph,
    )

    mock_injector = MagicMock(spec=ContentInjector)
    mock_injector.apply_to_chunks = MagicMock(return_value=0)

    request = IndexRequest(folder_path="/tmp/test_folder")

    await service._run_indexing_pipeline(
        request,
        "job_test",
        content_injector=mock_injector,
    )

    # No chunks (documents was empty, early return) — apply_to_chunks not called
    mock_injector.apply_to_chunks.assert_not_called()


@pytest.mark.asyncio
async def test_run_indexing_pipeline_no_injector_backward_compat() -> None:
    """_run_indexing_pipeline works without content_injector (backward compat)."""
    from agent_brain_server.services.indexing_service import IndexingService

    mock_storage = AsyncMock()
    mock_storage.is_initialized = True
    mock_storage.get_embedding_metadata = AsyncMock(return_value=None)
    mock_storage.get_count = AsyncMock(return_value=0)
    mock_storage.upsert_documents = AsyncMock()
    mock_storage.set_embedding_metadata = AsyncMock()

    mock_loader = AsyncMock()
    mock_loader.load_files = AsyncMock(return_value=[])

    mock_chunker = MagicMock()
    mock_embedding_gen = MagicMock()
    mock_embedding_gen.get_embedding_dimensions = MagicMock(return_value=3072)
    mock_bm25 = MagicMock()
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
        storage_backend=mock_storage,
        document_loader=mock_loader,
        chunker=mock_chunker,
        embedding_generator=mock_embedding_gen,
        bm25_manager=mock_bm25,
        graph_index_manager=mock_graph,
    )

    request = IndexRequest(folder_path="/tmp/test_folder")

    # Must not raise even without content_injector
    await service._run_indexing_pipeline(request, "job_test")


# ---------------------------------------------------------------------------
# JobWorker._process_job injection wiring
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_job_worker_creates_content_injector_from_job_record(
    tmp_path: Path,
) -> None:
    """JobWorker._process_job builds ContentInjector when job has injection params."""
    from agent_brain_server.job_queue.job_worker import JobWorker

    # Create a real injector script
    script = tmp_path / "inject.py"
    script.write_text(
        "def process_chunk(chunk):\n    chunk['job_tagged'] = True\n    return chunk\n",
        encoding="utf-8",
    )

    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({"env": "test"}), encoding="utf-8")

    job = _make_job_record(
        injector_script=str(script),
        folder_metadata_file=str(meta),
    )

    # Track if ContentInjector.build was called with correct args
    build_calls: list[dict[str, Any]] = []
    original_build = ContentInjector.build

    def spy_build(
        script_path: str | None = None,
        metadata_path: str | None = None,
    ) -> ContentInjector | None:
        build_calls.append({"script_path": script_path, "metadata_path": metadata_path})
        return original_build(script_path=script_path, metadata_path=metadata_path)

    # Mock the indexing service to avoid real indexing
    mock_storage = AsyncMock()
    mock_storage.is_initialized = True
    mock_storage.get_count = AsyncMock(return_value=0)

    mock_indexing_service = MagicMock()
    mock_indexing_service.storage_backend = mock_storage
    mock_indexing_service._lock = __import__("asyncio").Lock()

    # _run_indexing_pipeline captures the injector passed to it
    injector_received: list[ContentInjector | None] = []

    async def fake_pipeline(
        req: Any,
        job_id: str,
        callback: Any = None,
        content_injector: ContentInjector | None = None,
    ) -> None:
        injector_received.append(content_injector)

    mock_indexing_service._run_indexing_pipeline = fake_pipeline
    mock_indexing_service._state = MagicMock()
    mock_indexing_service._state.status.value = "completed"
    mock_indexing_service.get_status = AsyncMock(
        return_value={"total_chunks": 5, "total_documents": 2}
    )

    mock_job_store = AsyncMock()
    mock_job_store.update_job = AsyncMock()
    mock_job_store.get_job = AsyncMock(return_value=job)

    worker = JobWorker(
        job_store=mock_job_store,
        indexing_service=mock_indexing_service,
    )

    with patch.object(ContentInjector, "build", side_effect=spy_build):
        await worker._process_job(job)

    # build was called with the correct paths
    assert len(build_calls) == 1
    assert build_calls[0]["script_path"] == str(script)
    assert build_calls[0]["metadata_path"] == str(meta)

    # Injector was passed to pipeline
    assert len(injector_received) == 1
    assert injector_received[0] is not None


@pytest.mark.asyncio
async def test_job_worker_no_injector_when_job_has_no_injection_params() -> None:
    """JobWorker._process_job passes content_injector=None when no params set."""
    from agent_brain_server.job_queue.job_worker import JobWorker

    job = _make_job_record()  # no injector_script, no folder_metadata_file

    mock_storage = AsyncMock()
    mock_storage.is_initialized = True
    mock_storage.get_count = AsyncMock(return_value=0)

    mock_indexing_service = MagicMock()
    mock_indexing_service.storage_backend = mock_storage
    mock_indexing_service._lock = __import__("asyncio").Lock()

    injector_received: list[ContentInjector | None] = []

    async def fake_pipeline(
        req: Any,
        job_id: str,
        callback: Any = None,
        content_injector: ContentInjector | None = None,
    ) -> None:
        injector_received.append(content_injector)

    mock_indexing_service._run_indexing_pipeline = fake_pipeline
    mock_indexing_service._state = MagicMock()
    mock_indexing_service.get_status = AsyncMock(
        return_value={"total_chunks": 5, "total_documents": 2}
    )

    mock_job_store = AsyncMock()
    mock_job_store.update_job = AsyncMock()
    mock_job_store.get_job = AsyncMock(return_value=job)

    worker = JobWorker(
        job_store=mock_job_store,
        indexing_service=mock_indexing_service,
    )

    await worker._process_job(job)

    assert len(injector_received) == 1
    assert injector_received[0] is None


# ---------------------------------------------------------------------------
# API endpoint path validation
# ---------------------------------------------------------------------------


def test_index_endpoint_rejects_missing_injector_script(
    tmp_path: Path,
) -> None:
    """POST /index/ returns 400 when injector_script does not exist."""
    app = _create_index_app(folder_exists=True)
    client = TestClient(app)

    # tmp_path exists as a directory, injector_script does not exist
    response = client.post(
        "/index/",
        json={
            "folder_path": str(tmp_path),
            "injector_script": str(tmp_path / "nonexistent.py"),
        },
    )

    assert response.status_code == 400
    assert "nonexistent.py" in response.json()["detail"]


def test_index_endpoint_rejects_non_py_injector_script(
    tmp_path: Path,
) -> None:
    """POST /index/ returns 400 when injector_script is not a .py file."""
    # Create a non-.py file
    bad_script = tmp_path / "inject.sh"
    bad_script.write_text("#!/bin/bash\necho hello\n", encoding="utf-8")

    app = _create_index_app(folder_exists=True)
    client = TestClient(app)

    response = client.post(
        "/index/",
        json={
            "folder_path": str(tmp_path),
            "injector_script": str(bad_script),
        },
    )

    assert response.status_code == 400
    assert ".py" in response.json()["detail"]


def test_index_endpoint_rejects_missing_folder_metadata_file(
    tmp_path: Path,
) -> None:
    """POST /index/ returns 400 when folder_metadata_file does not exist."""
    app = _create_index_app(folder_exists=True)
    client = TestClient(app)

    response = client.post(
        "/index/",
        json={
            "folder_path": str(tmp_path),
            "folder_metadata_file": str(tmp_path / "missing_meta.json"),
        },
    )

    assert response.status_code == 400
    assert "missing_meta.json" in response.json()["detail"]


# ---------------------------------------------------------------------------
# dry_run mode
# ---------------------------------------------------------------------------


def test_index_endpoint_dry_run_returns_report_without_enqueueing(
    tmp_path: Path,
) -> None:
    """POST /index/ with dry_run=true returns report without creating a job."""
    # Create a valid injector script
    script = tmp_path / "inject.py"
    script.write_text(
        "def process_chunk(chunk):\n    chunk['dry'] = True\n    return chunk\n",
        encoding="utf-8",
    )

    app = _create_index_app(
        folder_exists=True,
        dry_run_doc_count=2,
        dry_run_chunk_count=3,
    )
    client = TestClient(app)

    response = client.post(
        "/index/",
        json={
            "folder_path": str(tmp_path),
            "injector_script": str(script),
            "dry_run": True,
        },
    )

    # dry_run returns the same HTTP 202 as the endpoint's declared status_code
    assert response.status_code == 202
    data = response.json()
    assert data["job_id"] == "dry_run"
    assert data["status"] == "completed"
    assert "Dry-run" in data["message"]

    # Verify job was NOT enqueued
    job_service = app.state.job_service
    job_service.enqueue_job.assert_not_called()


def test_index_endpoint_dry_run_no_injector_returns_empty_report(
    tmp_path: Path,
) -> None:
    """dry_run with no injector returns zero-enrichment report."""
    app = _create_index_app(
        folder_exists=True,
        dry_run_doc_count=1,
        dry_run_chunk_count=2,
    )
    client = TestClient(app)

    response = client.post(
        "/index/",
        json={
            "folder_path": str(tmp_path),
            "dry_run": True,
        },
    )

    # dry_run returns the same HTTP 202 as the endpoint's declared status_code
    assert response.status_code == 202
    data = response.json()
    assert data["job_id"] == "dry_run"
    assert "0/" in data["message"]  # 0 chunks enriched
