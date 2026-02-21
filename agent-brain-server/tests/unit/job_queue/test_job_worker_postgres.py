"""Tests for job worker with PostgreSQL storage backend.

Verifies that job verification uses storage_backend.get_count()
instead of vector_store.get_count(), which would return 0 when
using a non-ChromaDB backend.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_brain_server.job_queue.job_worker import JobWorker
from agent_brain_server.models.job import JobProgress, JobRecord, JobStatus


def _make_job(
    folder: str = "/tmp/test",
    status: JobStatus = JobStatus.RUNNING,
) -> JobRecord:
    """Create a test job record."""
    dedupe_key = JobRecord.compute_dedupe_key(
        folder_path=folder,
        include_code=False,
        operation="index",
    )
    return JobRecord(
        id="job_test123",
        dedupe_key=dedupe_key,
        folder_path=folder,
        status=status,
        started_at=datetime.now(timezone.utc),
        progress=JobProgress(
            files_processed=5,
            files_total=5,
            chunks_created=0,
            current_file="done",
            updated_at=datetime.now(timezone.utc),
        ),
    )


def _make_worker(
    count_before: int = 0,
    count_after: int = 100,
) -> tuple[JobWorker, AsyncMock]:
    """Create a JobWorker with mocked storage_backend.

    Returns:
        Tuple of (worker, mock_storage_backend).
    """
    mock_storage = AsyncMock()
    mock_storage.is_initialized = True
    # _verify_collection_delta only calls get_count once (for count_after)
    # count_before is passed as a parameter
    mock_storage.get_count = AsyncMock(return_value=count_after)

    mock_indexing_service = MagicMock()
    mock_indexing_service.storage_backend = mock_storage

    mock_job_store = AsyncMock()

    worker = JobWorker(
        job_store=mock_job_store,
        indexing_service=mock_indexing_service,
    )
    return worker, mock_storage


@pytest.mark.asyncio
async def test_verify_collection_delta_uses_storage_backend() -> None:
    """Verify _verify_collection_delta reads from storage_backend."""
    worker, mock_storage = _make_worker(count_before=0, count_after=100)
    job = _make_job()

    result = await worker._verify_collection_delta(job, count_before=0)

    assert result is True
    mock_storage.get_count.assert_called_once()


@pytest.mark.asyncio
async def test_verify_collection_delta_detects_new_chunks() -> None:
    """Delta > 0 means verification passes."""
    worker, _ = _make_worker(count_before=50, count_after=150)
    job = _make_job()

    result = await worker._verify_collection_delta(job, count_before=50)

    assert result is True


@pytest.mark.asyncio
async def test_verify_collection_delta_no_new_chunks_fails() -> None:
    """No new chunks and no files processed means failure."""
    worker, _ = _make_worker(count_before=0, count_after=0)
    job = _make_job()
    job.progress = JobProgress(
        files_processed=0,
        files_total=0,
        chunks_created=0,
        current_file="",
        updated_at=datetime.now(timezone.utc),
    )

    result = await worker._verify_collection_delta(job, count_before=0)

    assert result is False


@pytest.mark.asyncio
async def test_verify_collection_delta_reindexed_files_pass() -> None:
    """Files processed but no new chunks (already indexed) is OK."""
    worker, _ = _make_worker(count_before=100, count_after=100)
    job = _make_job()

    result = await worker._verify_collection_delta(job, count_before=100)

    # Should pass because files_processed > 0
    assert result is True


@pytest.mark.asyncio
async def test_verify_collection_delta_error_returns_false() -> None:
    """Storage error during verification returns False."""
    mock_storage = AsyncMock()
    mock_storage.is_initialized = True
    mock_storage.get_count = AsyncMock(side_effect=Exception("Connection lost"))

    mock_indexing_service = MagicMock()
    mock_indexing_service.storage_backend = mock_storage

    worker = JobWorker(
        job_store=AsyncMock(),
        indexing_service=mock_indexing_service,
    )
    job = _make_job()

    result = await worker._verify_collection_delta(job, count_before=0)

    assert result is False
