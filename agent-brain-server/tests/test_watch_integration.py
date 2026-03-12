"""Tests for watch_mode integration between JobWorker and FileWatcherService."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_brain_server.job_queue.job_worker import JobWorker
from agent_brain_server.models.job import JobRecord


@pytest.fixture()
def mock_job_store() -> AsyncMock:
    """Create a mock job store."""
    store = AsyncMock()
    store.get_pending_jobs = AsyncMock(return_value=[])
    store.update_job = AsyncMock()
    store.get_job = AsyncMock(return_value=None)
    return store


@pytest.fixture()
def mock_indexing_service() -> MagicMock:
    """Create a mock indexing service."""
    service = MagicMock()
    service._lock = asyncio.Lock()
    service.storage_backend = MagicMock()
    service.storage_backend.is_initialized = True
    service.storage_backend.get_count = AsyncMock(return_value=10)
    service._run_indexing_pipeline = AsyncMock(return_value=None)
    service.get_status = AsyncMock(
        return_value={"total_chunks": 10, "total_documents": 3}
    )
    return service


@pytest.fixture()
def mock_file_watcher() -> MagicMock:
    """Create a mock FileWatcherService."""
    watcher = MagicMock()
    watcher.add_folder_watch = MagicMock()
    watcher.remove_folder_watch = MagicMock()
    return watcher


@pytest.fixture()
def mock_folder_manager() -> AsyncMock:
    """Create a mock FolderManager."""
    manager = AsyncMock()
    return manager


def _make_job(
    watch_mode: str | None = None,
    watch_debounce_seconds: int | None = None,
    source: str = "manual",
) -> JobRecord:
    """Create a test JobRecord with watch fields."""
    return JobRecord(
        id="job_test123456",
        dedupe_key="abc123",
        folder_path="/tmp/test_folder",
        include_code=True,
        watch_mode=watch_mode,
        watch_debounce_seconds=watch_debounce_seconds,
        source=source,
    )


class TestJobRecordWatchFields:
    """Test that JobRecord has watch_mode and watch_debounce_seconds fields."""

    def test_default_watch_mode_is_none(self) -> None:
        """JobRecord watch_mode defaults to None."""
        job = _make_job()
        assert job.watch_mode is None

    def test_watch_mode_auto(self) -> None:
        """JobRecord can have watch_mode='auto'."""
        job = _make_job(watch_mode="auto", watch_debounce_seconds=10)
        assert job.watch_mode == "auto"
        assert job.watch_debounce_seconds == 10

    def test_watch_mode_off(self) -> None:
        """JobRecord can have watch_mode='off'."""
        job = _make_job(watch_mode="off")
        assert job.watch_mode == "off"

    def test_source_field_default(self) -> None:
        """JobRecord source defaults to 'manual'."""
        job = _make_job()
        assert job.source == "manual"

    def test_source_field_auto(self) -> None:
        """JobRecord source can be 'auto'."""
        job = _make_job(source="auto")
        assert job.source == "auto"


class TestJobWorkerWatchIntegration:
    """Test that JobWorker notifies FileWatcherService after job completion."""

    @pytest.mark.asyncio()
    async def test_apply_watch_config_auto_calls_add_folder_watch(
        self,
        mock_job_store: AsyncMock,
        mock_indexing_service: MagicMock,
        mock_file_watcher: MagicMock,
        mock_folder_manager: AsyncMock,
    ) -> None:
        """When job has watch_mode=auto, add_folder_watch is called."""
        worker = JobWorker(mock_job_store, mock_indexing_service)
        worker.set_file_watcher_service(mock_file_watcher)
        worker.set_folder_manager(mock_folder_manager)

        # Mock folder_manager.get_folder to return a record
        mock_record = MagicMock()
        mock_record.folder_path = "/tmp/test_folder"
        mock_record.chunk_count = 10
        mock_record.chunk_ids = ["c1", "c2"]
        mock_record.include_code = True
        mock_folder_manager.get_folder = AsyncMock(return_value=mock_record)
        mock_folder_manager.add_folder = AsyncMock(return_value=mock_record)

        job = _make_job(watch_mode="auto", watch_debounce_seconds=15)

        await worker._apply_watch_config(job)

        # Verify FolderManager was updated with watch config
        mock_folder_manager.add_folder.assert_called_once_with(
            folder_path="/tmp/test_folder",
            chunk_count=10,
            chunk_ids=["c1", "c2"],
            watch_mode="auto",
            watch_debounce_seconds=15,
            include_code=True,
        )

        # Verify FileWatcherService.add_folder_watch was called
        mock_file_watcher.add_folder_watch.assert_called_once_with(
            folder_path="/tmp/test_folder",
            debounce_seconds=15,
        )

    @pytest.mark.asyncio()
    async def test_apply_watch_config_off_calls_remove_folder_watch(
        self,
        mock_job_store: AsyncMock,
        mock_indexing_service: MagicMock,
        mock_file_watcher: MagicMock,
        mock_folder_manager: AsyncMock,
    ) -> None:
        """When job has watch_mode=off, remove_folder_watch is called."""
        worker = JobWorker(mock_job_store, mock_indexing_service)
        worker.set_file_watcher_service(mock_file_watcher)
        worker.set_folder_manager(mock_folder_manager)

        mock_record = MagicMock()
        mock_record.folder_path = "/tmp/test_folder"
        mock_record.chunk_count = 10
        mock_record.chunk_ids = ["c1"]
        mock_record.include_code = False
        mock_folder_manager.get_folder = AsyncMock(return_value=mock_record)
        mock_folder_manager.add_folder = AsyncMock(return_value=mock_record)

        job = _make_job(watch_mode="off")

        await worker._apply_watch_config(job)

        mock_file_watcher.remove_folder_watch.assert_called_once_with(
            "/tmp/test_folder"
        )

    @pytest.mark.asyncio()
    async def test_apply_watch_config_none_does_nothing(
        self,
        mock_job_store: AsyncMock,
        mock_indexing_service: MagicMock,
        mock_file_watcher: MagicMock,
        mock_folder_manager: AsyncMock,
    ) -> None:
        """When job has watch_mode=None, nothing happens."""
        worker = JobWorker(mock_job_store, mock_indexing_service)
        worker.set_file_watcher_service(mock_file_watcher)
        worker.set_folder_manager(mock_folder_manager)

        job = _make_job(watch_mode=None)

        await worker._apply_watch_config(job)

        mock_file_watcher.add_folder_watch.assert_not_called()
        mock_file_watcher.remove_folder_watch.assert_not_called()
        mock_folder_manager.get_folder.assert_not_called()

    @pytest.mark.asyncio()
    async def test_apply_watch_config_no_watcher_service(
        self,
        mock_job_store: AsyncMock,
        mock_indexing_service: MagicMock,
        mock_folder_manager: AsyncMock,
    ) -> None:
        """When no file_watcher_service is set, folder_manager still updated."""
        worker = JobWorker(mock_job_store, mock_indexing_service)
        worker.set_folder_manager(mock_folder_manager)

        mock_record = MagicMock()
        mock_record.folder_path = "/tmp/test_folder"
        mock_record.chunk_count = 5
        mock_record.chunk_ids = ["c1"]
        mock_record.include_code = True
        mock_folder_manager.get_folder = AsyncMock(return_value=mock_record)
        mock_folder_manager.add_folder = AsyncMock(return_value=mock_record)

        job = _make_job(watch_mode="auto", watch_debounce_seconds=20)

        await worker._apply_watch_config(job)

        # FolderManager should still be updated
        mock_folder_manager.add_folder.assert_called_once()

    @pytest.mark.asyncio()
    async def test_apply_watch_config_handles_error_gracefully(
        self,
        mock_job_store: AsyncMock,
        mock_indexing_service: MagicMock,
        mock_file_watcher: MagicMock,
        mock_folder_manager: AsyncMock,
    ) -> None:
        """Errors in _apply_watch_config are logged but don't raise."""
        worker = JobWorker(mock_job_store, mock_indexing_service)
        worker.set_file_watcher_service(mock_file_watcher)
        worker.set_folder_manager(mock_folder_manager)

        mock_folder_manager.get_folder = AsyncMock(side_effect=RuntimeError("DB error"))

        job = _make_job(watch_mode="auto")

        # Should not raise
        await worker._apply_watch_config(job)
