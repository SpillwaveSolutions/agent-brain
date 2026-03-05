"""Tests for JobWorker eviction summary and force field handling (Phase 14).

Verifies:
- JobWorker passes force=True from JobRecord to IndexRequest
- JobWorker stores eviction_summary on JobRecord after successful run
- Zero-change incremental run passes verification without marking FAILED
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_brain_server.job_queue.job_worker import JobWorker
from agent_brain_server.models.job import JobProgress, JobRecord, JobStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_job(
    folder: str = "/tmp/test_eviction",
    force: bool = False,
    status: JobStatus = JobStatus.RUNNING,
    progress_files: int = 5,
    eviction_summary: dict[str, Any] | None = None,
) -> JobRecord:
    """Create a test job record with optional eviction_summary."""
    dedupe_key = JobRecord.compute_dedupe_key(
        folder_path=folder,
        include_code=False,
        operation="index",
    )
    return JobRecord(
        id="job_eviction_test",
        dedupe_key=dedupe_key,
        folder_path=folder,
        status=status,
        force=force,
        eviction_summary=eviction_summary,
        started_at=datetime.now(timezone.utc),
        progress=JobProgress(
            files_processed=progress_files,
            files_total=progress_files,
            chunks_created=0,
            current_file="done",
            updated_at=datetime.now(timezone.utc),
        ),
    )


def _make_worker_with_mock_service(
    count_before: int = 0,
    count_after: int = 100,
    pipeline_return: dict[str, Any] | None = None,
) -> tuple[JobWorker, MagicMock]:
    """Create a JobWorker with mocked indexing service.

    Returns:
        Tuple of (worker, mock_indexing_service).
    """
    mock_storage = AsyncMock()
    mock_storage.is_initialized = True
    mock_storage.get_count = AsyncMock(return_value=count_after)

    mock_indexing_service = MagicMock()
    mock_indexing_service.storage_backend = mock_storage
    mock_indexing_service._run_indexing_pipeline = AsyncMock(
        return_value=pipeline_return
    )
    mock_indexing_service.get_status = AsyncMock(
        return_value={"total_chunks": count_after, "total_documents": 3}
    )
    mock_indexing_service._lock = __import__("asyncio").Lock()

    mock_job_store = AsyncMock()
    mock_job_store.update_job = AsyncMock()
    mock_job_store.get_job = AsyncMock(return_value=None)  # No cancel requested

    worker = JobWorker(
        job_store=mock_job_store,
        indexing_service=mock_indexing_service,
    )
    return worker, mock_indexing_service


# ---------------------------------------------------------------------------
# Test: verify_collection_delta handles zero-change incremental run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_delta_zero_change_incremental_passes() -> None:
    """Zero-change incremental run (chunks_to_create=0) should pass verification."""
    worker, _ = _make_worker_with_mock_service(count_before=50, count_after=50)

    job = _make_job(
        eviction_summary={
            "files_added": [],
            "files_changed": [],
            "files_deleted": [],
            "files_unchanged": ["file1.md"],
            "chunks_evicted": 0,
            "chunks_to_create": 0,
        }
    )

    # count_after == count_before == 50, delta == 0, but eviction says no new chunks
    result = await worker._verify_collection_delta(job, count_before=50)

    assert result is True


@pytest.mark.asyncio
async def test_verify_delta_no_eviction_summary_delta_zero_fails() -> None:
    """Without eviction summary and delta==0, verification should fail if no files
    processed and no chunks exist."""
    worker, _ = _make_worker_with_mock_service(count_before=0, count_after=0)

    job = _make_job(progress_files=0, eviction_summary=None)

    result = await worker._verify_collection_delta(job, count_before=0)

    assert result is False


@pytest.mark.asyncio
async def test_verify_delta_positive_delta_passes() -> None:
    """Positive delta (new chunks added) should pass verification."""
    worker, _ = _make_worker_with_mock_service(count_before=10, count_after=25)

    job = _make_job()

    result = await worker._verify_collection_delta(job, count_before=10)

    assert result is True


# ---------------------------------------------------------------------------
# Test: JobRecord.force is propagated to IndexRequest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_job_worker_passes_force_to_index_request(tmp_path: Any) -> None:
    """JobWorker should pass job.force to IndexRequest when creating the pipeline call.

    This test verifies the force field is threaded through by observing the
    IndexRequest passed to _run_indexing_pipeline.
    """
    captured_requests: list[Any] = []

    async def capture_pipeline(
        request: Any,
        job_id: str,
        progress_callback: Any = None,
        content_injector: Any = None,
    ) -> dict[str, Any]:
        captured_requests.append(request)
        return {
            "files_added": ["f1.md"],
            "files_changed": [],
            "files_deleted": [],
            "files_unchanged": [],
            "chunks_evicted": 0,
            "chunks_to_create": 1,
        }

    mock_storage = AsyncMock()
    mock_storage.is_initialized = True
    mock_storage.get_count = AsyncMock(side_effect=[0, 5])  # before=0, after=5

    mock_indexing_service = MagicMock()
    mock_indexing_service.storage_backend = mock_storage
    mock_indexing_service._run_indexing_pipeline = capture_pipeline
    mock_indexing_service.get_status = AsyncMock(
        return_value={"total_chunks": 5, "total_documents": 1}
    )
    mock_indexing_service._lock = __import__("asyncio").Lock()

    job = _make_job(force=True, folder="/tmp/force_test")

    mock_job_store = AsyncMock()
    mock_job_store.update_job = AsyncMock()
    mock_job_store.get_job = AsyncMock(return_value=None)

    worker = JobWorker(
        job_store=mock_job_store,
        indexing_service=mock_indexing_service,
    )

    await worker._process_job(job)

    assert len(captured_requests) == 1
    assert captured_requests[0].force is True


# ---------------------------------------------------------------------------
# Test: eviction_summary stored on job after successful run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_job_worker_stores_eviction_summary_on_success() -> None:
    """After a successful pipeline run, job.eviction_summary should be populated."""
    eviction_data = {
        "files_added": ["new.md"],
        "files_changed": [],
        "files_deleted": ["old.md"],
        "files_unchanged": ["stable.md"],
        "chunks_evicted": 3,
        "chunks_to_create": 1,
    }

    mock_storage = AsyncMock()
    mock_storage.is_initialized = True
    mock_storage.get_count = AsyncMock(side_effect=[0, 5])

    mock_indexing_service = MagicMock()
    mock_indexing_service.storage_backend = mock_storage
    mock_indexing_service._run_indexing_pipeline = AsyncMock(return_value=eviction_data)
    mock_indexing_service.get_status = AsyncMock(
        return_value={"total_chunks": 5, "total_documents": 1}
    )
    mock_indexing_service._lock = __import__("asyncio").Lock()

    job = _make_job()
    updated_jobs: list[JobRecord] = []

    mock_job_store = AsyncMock()
    mock_job_store.update_job = AsyncMock(side_effect=lambda j: updated_jobs.append(j))
    mock_job_store.get_job = AsyncMock(return_value=None)

    worker = JobWorker(
        job_store=mock_job_store,
        indexing_service=mock_indexing_service,
    )

    await worker._process_job(job)

    # Find DONE updates (may be multiple as worker updates state multiple times)
    done_jobs = [j for j in updated_jobs if j.status == JobStatus.DONE]
    assert len(done_jobs) >= 1
    # Use the last DONE update which has the eviction_summary
    done_job = done_jobs[-1]
    assert done_job.eviction_summary is not None
    assert done_job.eviction_summary["chunks_evicted"] == 3
    assert done_job.eviction_summary["chunks_to_create"] == 1
    assert "new.md" in done_job.eviction_summary["files_added"]
