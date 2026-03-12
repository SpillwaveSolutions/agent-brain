"""Tests for FolderRecord watch fields and backward compatibility.

Covers:
- FolderRecord with watch_mode, watch_debounce_seconds, include_code fields
- Backward compatibility: v7.0 JSONL records without watch fields load cleanly
- add_folder with watch_mode and watch_debounce_seconds persists to JSONL
- JobRecord with source field
- enqueue_job with source="auto" creates job with correct source field
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_brain_server.models.index import IndexRequest
from agent_brain_server.models.job import JobDetailResponse, JobRecord, JobSummary
from agent_brain_server.services.folder_manager import FolderManager, FolderRecord

# ---------------------------------------------------------------------------
# FolderRecord dataclass tests
# ---------------------------------------------------------------------------


def test_folder_record_default_watch_fields() -> None:
    """FolderRecord has correct default watch field values."""
    record = FolderRecord(
        folder_path="/tmp/docs",
        chunk_count=10,
        last_indexed="2026-01-01T00:00:00+00:00",
        chunk_ids=["a", "b"],
    )
    assert record.watch_mode == "off"
    assert record.watch_debounce_seconds is None
    assert record.include_code is False


def test_folder_record_with_watch_fields() -> None:
    """FolderRecord stores watch fields correctly."""
    record = FolderRecord(
        folder_path="/tmp/code",
        chunk_count=50,
        last_indexed="2026-01-01T00:00:00+00:00",
        chunk_ids=["c1", "c2"],
        watch_mode="auto",
        watch_debounce_seconds=15,
        include_code=True,
    )
    assert record.watch_mode == "auto"
    assert record.watch_debounce_seconds == 15
    assert record.include_code is True


def test_folder_record_asdict_includes_watch_fields() -> None:
    """asdict() serialization includes all watch fields."""
    record = FolderRecord(
        folder_path="/tmp/docs",
        chunk_count=5,
        last_indexed="2026-01-01T00:00:00+00:00",
        chunk_ids=["x"],
        watch_mode="auto",
        watch_debounce_seconds=20,
        include_code=True,
    )
    data = asdict(record)
    assert data["watch_mode"] == "auto"
    assert data["watch_debounce_seconds"] == 20
    assert data["include_code"] is True


# ---------------------------------------------------------------------------
# Backward compatibility: v7.0 JSONL files without watch fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_jsonl_v7_records_missing_watch_fields() -> None:
    """v7.0 JSONL records without watch fields load with backward-compat defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = Path(tmpdir)
        jsonl_path = state_dir / "indexed_folders.jsonl"

        # Write a v7.0-style record WITHOUT watch fields
        v7_record = {
            "folder_path": "/home/user/docs",
            "chunk_count": 42,
            "last_indexed": "2026-02-24T01:00:00+00:00",
            "chunk_ids": ["id1", "id2"],
        }
        with open(jsonl_path, "w") as f:
            f.write(json.dumps(v7_record) + "\n")

        folder_manager = FolderManager(state_dir=state_dir)
        await folder_manager.initialize()

        records = await folder_manager.list_folders()
        assert len(records) == 1

        record = records[0]
        assert record.folder_path == "/home/user/docs"
        assert record.watch_mode == "off"  # backward compat default
        assert record.watch_debounce_seconds is None  # backward compat default
        assert record.include_code is False  # backward compat default


@pytest.mark.asyncio
async def test_load_jsonl_mixed_records() -> None:
    """JSONL file with mixed v7.0 and v8.0 records loads correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = Path(tmpdir)
        jsonl_path = state_dir / "indexed_folders.jsonl"

        v7_record = {
            "folder_path": "/home/user/old-docs",
            "chunk_count": 10,
            "last_indexed": "2026-01-01T00:00:00+00:00",
            "chunk_ids": [],
        }
        v8_record = {
            "folder_path": "/home/user/new-docs",
            "chunk_count": 20,
            "last_indexed": "2026-03-01T00:00:00+00:00",
            "chunk_ids": ["a", "b"],
            "watch_mode": "auto",
            "watch_debounce_seconds": 30,
            "include_code": True,
        }
        with open(jsonl_path, "w") as f:
            f.write(json.dumps(v7_record) + "\n")
            f.write(json.dumps(v8_record) + "\n")

        folder_manager = FolderManager(state_dir=state_dir)
        await folder_manager.initialize()

        records = await folder_manager.list_folders()
        assert len(records) == 2

        # Sorted by path, old-docs comes first
        old_rec = next(r for r in records if "old-docs" in r.folder_path)
        new_rec = next(r for r in records if "new-docs" in r.folder_path)

        assert old_rec.watch_mode == "off"
        assert old_rec.watch_debounce_seconds is None

        assert new_rec.watch_mode == "auto"
        assert new_rec.watch_debounce_seconds == 30
        assert new_rec.include_code is True


# ---------------------------------------------------------------------------
# add_folder with watch fields persists to JSONL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_folder_persists_watch_fields() -> None:
    """add_folder with watch_mode and watch_debounce_seconds persists to JSONL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = Path(tmpdir)
        folder_manager = FolderManager(state_dir=state_dir)
        await folder_manager.initialize()

        record = await folder_manager.add_folder(
            folder_path=str(state_dir / "src"),
            chunk_count=100,
            chunk_ids=["c1"],
            watch_mode="auto",
            watch_debounce_seconds=10,
            include_code=True,
        )

        assert record.watch_mode == "auto"
        assert record.watch_debounce_seconds == 10
        assert record.include_code is True

        # Reload from disk to verify persistence
        folder_manager2 = FolderManager(state_dir=state_dir)
        await folder_manager2.initialize()
        records = await folder_manager2.list_folders()

        assert len(records) == 1
        loaded = records[0]
        assert loaded.watch_mode == "auto"
        assert loaded.watch_debounce_seconds == 10
        assert loaded.include_code is True


@pytest.mark.asyncio
async def test_add_folder_default_watch_fields_backward_compat() -> None:
    """add_folder with no watch kwargs uses defaults (backward compat callers)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = Path(tmpdir)
        folder_manager = FolderManager(state_dir=state_dir)
        await folder_manager.initialize()

        record = await folder_manager.add_folder(
            folder_path=str(state_dir / "docs"),
            chunk_count=5,
            chunk_ids=[],
        )

        assert record.watch_mode == "off"
        assert record.watch_debounce_seconds is None
        assert record.include_code is False


# ---------------------------------------------------------------------------
# JobRecord source field tests
# ---------------------------------------------------------------------------


def test_job_record_default_source_is_manual() -> None:
    """JobRecord has source='manual' by default."""
    job = JobRecord(
        id="job_abc123",
        dedupe_key="deadbeef",
        folder_path="/tmp/docs",
        include_code=False,
        operation="index",
    )
    assert job.source == "manual"


def test_job_record_source_auto() -> None:
    """JobRecord with source='auto' serializes and deserializes correctly."""
    job = JobRecord(
        id="job_xyz789",
        dedupe_key="cafebabe",
        folder_path="/tmp/code",
        include_code=True,
        operation="index",
        source="auto",
    )
    assert job.source == "auto"

    # Round-trip via JSON
    data = job.model_dump_json()
    loaded = JobRecord.model_validate_json(data)
    assert loaded.source == "auto"


def test_job_summary_from_record_includes_source() -> None:
    """JobSummary.from_record() includes source field from JobRecord."""
    job = JobRecord(
        id="job_sum01",
        dedupe_key="abc",
        folder_path="/tmp/docs",
        include_code=False,
        operation="index",
        source="auto",
    )
    summary = JobSummary.from_record(job)
    assert summary.source == "auto"


def test_job_detail_response_from_record_includes_source() -> None:
    """JobDetailResponse.from_record() includes source field from JobRecord."""
    job = JobRecord(
        id="job_det01",
        dedupe_key="xyz",
        folder_path="/tmp/docs",
        include_code=False,
        operation="index",
        source="auto",
    )
    detail = JobDetailResponse.from_record(job)
    assert detail.source == "auto"


# ---------------------------------------------------------------------------
# enqueue_job with source="auto"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_job_with_source_auto() -> None:
    """enqueue_job with source='auto' creates a job with source='auto'."""
    from agent_brain_server.job_queue.job_service import JobQueueService
    from agent_brain_server.models.job import JobEnqueueResponse

    # Build mocked store
    mock_store = MagicMock()
    mock_store.find_by_dedupe_key = AsyncMock(return_value=None)
    mock_store.append_job = AsyncMock(return_value=0)
    mock_store.get_queue_length = AsyncMock(return_value=1)

    # Capture the job record passed to append_job
    captured_jobs: list[JobRecord] = []

    async def capture_append(job: JobRecord) -> int:
        captured_jobs.append(job)
        return 0

    mock_store.append_job = capture_append

    service = JobQueueService(store=mock_store, project_root=None)

    request = IndexRequest(folder_path="/tmp/docs")
    response = await service.enqueue_job(
        request=request,
        operation="index",
        force=False,
        source="auto",
    )

    assert isinstance(response, JobEnqueueResponse)
    assert response.dedupe_hit is False
    assert len(captured_jobs) == 1
    assert captured_jobs[0].source == "auto"


@pytest.mark.asyncio
async def test_enqueue_job_default_source_is_manual() -> None:
    """enqueue_job without source param defaults to source='manual'."""
    from agent_brain_server.job_queue.job_service import JobQueueService

    mock_store = MagicMock()
    mock_store.find_by_dedupe_key = AsyncMock(return_value=None)
    mock_store.get_queue_length = AsyncMock(return_value=1)

    captured_jobs: list[JobRecord] = []

    async def capture_append(job: JobRecord) -> int:
        captured_jobs.append(job)
        return 0

    mock_store.append_job = capture_append

    service = JobQueueService(store=mock_store, project_root=None)

    request = IndexRequest(folder_path="/tmp/docs")
    await service.enqueue_job(request=request)

    assert len(captured_jobs) == 1
    assert captured_jobs[0].source == "manual"
