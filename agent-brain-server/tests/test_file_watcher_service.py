"""Tests for FileWatcherService.

Covers:
- AgentBrainWatchFilter includes extra ignore dirs
- start() with no auto folders creates no tasks
- start() with auto folders creates correct number of tasks
- stop() sets stop_event and clears tasks
- add_folder_watch adds a new task
- remove_folder_watch cancels and removes task
- _enqueue_for_folder calls enqueue_job with source='auto' and force=False
- _enqueue_for_folder handles dedupe_hit gracefully
- _enqueue_for_folder handles missing folder record gracefully
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_brain_server.models.job import JobEnqueueResponse, JobStatus
from agent_brain_server.services.file_watcher_service import (
    AgentBrainWatchFilter,
    FileWatcherService,
)

# ---------------------------------------------------------------------------
# AgentBrainWatchFilter tests
# ---------------------------------------------------------------------------


def test_watch_filter_includes_extra_ignore_dirs() -> None:
    """AgentBrainWatchFilter includes dist and build in ignored dirs."""
    ignore_dirs = set(AgentBrainWatchFilter.ignore_dirs)
    assert "dist" in ignore_dirs
    assert "build" in ignore_dirs
    assert ".next" in ignore_dirs
    assert ".nuxt" in ignore_dirs
    assert "coverage" in ignore_dirs
    assert "htmlcov" in ignore_dirs


def test_watch_filter_inherits_default_ignores() -> None:
    """AgentBrainWatchFilter still inherits DefaultFilter ignored dirs."""
    from watchfiles import DefaultFilter

    ignore_dirs = set(AgentBrainWatchFilter.ignore_dirs)
    for default_dir in DefaultFilter.ignore_dirs:
        assert (
            default_dir in ignore_dirs
        ), f"Expected '{default_dir}' to be in AgentBrainWatchFilter.ignore_dirs"


# ---------------------------------------------------------------------------
# Helpers for mocking folder records
# ---------------------------------------------------------------------------


def make_folder_record(
    folder_path: str,
    watch_mode: str = "auto",
    watch_debounce_seconds: int | None = None,
    include_code: bool = False,
) -> MagicMock:
    record = MagicMock()
    record.folder_path = folder_path
    record.watch_mode = watch_mode
    record.watch_debounce_seconds = watch_debounce_seconds
    record.include_code = include_code
    return record


def make_enqueue_response(dedupe_hit: bool = False) -> JobEnqueueResponse:
    return JobEnqueueResponse(
        job_id="job_abc123",
        status=JobStatus.PENDING.value,
        queue_position=0,
        queue_length=1,
        message="test",
        dedupe_hit=dedupe_hit,
    )


# ---------------------------------------------------------------------------
# start() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_with_no_auto_folders_creates_no_tasks() -> None:
    """start() with no folders in auto mode creates no watcher tasks."""
    mock_folder_manager = MagicMock()
    mock_folder_manager.list_folders = AsyncMock(return_value=[])

    mock_job_service = MagicMock()

    service = FileWatcherService(
        folder_manager=mock_folder_manager,
        job_service=mock_job_service,
        default_debounce_seconds=5,
    )

    with patch("watchfiles.awatch") as _mock_awatch:
        await service.start()

    assert service.watched_folder_count == 0
    assert service.is_running is True

    await service.stop()


@pytest.mark.asyncio
async def test_start_with_off_folders_creates_no_tasks() -> None:
    """start() with folders in 'off' watch mode creates no watcher tasks."""
    off_folder = make_folder_record("/tmp/docs", watch_mode="off")

    mock_folder_manager = MagicMock()
    mock_folder_manager.list_folders = AsyncMock(return_value=[off_folder])

    mock_job_service = MagicMock()

    service = FileWatcherService(
        folder_manager=mock_folder_manager,
        job_service=mock_job_service,
        default_debounce_seconds=5,
    )

    with patch("watchfiles.awatch") as _mock_awatch:
        await service.start()

    assert service.watched_folder_count == 0

    await service.stop()


@pytest.mark.asyncio
async def test_start_with_auto_folders_creates_tasks() -> None:
    """start() with 2 auto folders creates 2 watcher tasks."""
    folder1 = make_folder_record("/tmp/folder1", watch_mode="auto")
    folder2 = make_folder_record("/tmp/folder2", watch_mode="auto")
    off_folder = make_folder_record("/tmp/folder3", watch_mode="off")

    mock_folder_manager = MagicMock()
    mock_folder_manager.list_folders = AsyncMock(
        return_value=[folder1, folder2, off_folder]
    )

    mock_job_service = MagicMock()

    # Mock awatch as an async generator that yields nothing and stops immediately
    async def mock_awatch_gen(
        *args: object, **kwargs: object
    ) -> AsyncGenerator[set, None]:
        # Return immediately (stop_event is already set or no changes)
        return
        yield  # Make this a generator

    with patch(
        "agent_brain_server.services.file_watcher_service.watchfiles.awatch",
        side_effect=mock_awatch_gen,
    ):
        service = FileWatcherService(
            folder_manager=mock_folder_manager,
            job_service=mock_job_service,
            default_debounce_seconds=5,
        )
        await service.start()

        assert service.watched_folder_count == 2
        assert service.is_running is True

        await service.stop()

    assert service.watched_folder_count == 0
    assert service.is_running is False


# ---------------------------------------------------------------------------
# stop() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_clears_tasks_and_sets_stop_event() -> None:
    """stop() sets stop_event and clears all tasks."""
    mock_folder_manager = MagicMock()
    mock_folder_manager.list_folders = AsyncMock(return_value=[])

    service = FileWatcherService(
        folder_manager=mock_folder_manager,
        job_service=MagicMock(),
        default_debounce_seconds=5,
    )

    await service.start()
    assert service.is_running is True

    await service.stop()

    assert service.is_running is False
    assert service.watched_folder_count == 0


@pytest.mark.asyncio
async def test_stop_cancels_watcher_tasks() -> None:
    """stop() cancels all running watcher tasks."""
    folder = make_folder_record("/tmp/watched", watch_mode="auto")

    mock_folder_manager = MagicMock()
    mock_folder_manager.list_folders = AsyncMock(return_value=[folder])

    # A watcher that never stops (blocks forever)
    stop_was_set = asyncio.Event()

    async def blocking_awatch(
        *args: object, **kwargs: object
    ) -> AsyncGenerator[set, None]:
        # Wait until cancelled
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            stop_was_set.set()
            raise
        yield  # Never reached

    with patch(
        "agent_brain_server.services.file_watcher_service.watchfiles.awatch",
        side_effect=blocking_awatch,
    ):
        service = FileWatcherService(
            folder_manager=mock_folder_manager,
            job_service=MagicMock(),
            default_debounce_seconds=5,
        )
        await service.start()

        # Give the task time to start
        await asyncio.sleep(0.01)

        assert service.watched_folder_count == 1

        await service.stop()

    assert service.watched_folder_count == 0


# ---------------------------------------------------------------------------
# add_folder_watch / remove_folder_watch tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_folder_watch_adds_new_task() -> None:
    """add_folder_watch starts a task for a new folder."""
    mock_folder_manager = MagicMock()
    mock_folder_manager.list_folders = AsyncMock(return_value=[])

    async def mock_awatch(*args: object, **kwargs: object) -> AsyncGenerator[set, None]:
        await asyncio.sleep(3600)
        yield  # Never reached

    with patch(
        "agent_brain_server.services.file_watcher_service.watchfiles.awatch",
        side_effect=mock_awatch,
    ):
        service = FileWatcherService(
            folder_manager=mock_folder_manager,
            job_service=MagicMock(),
            default_debounce_seconds=5,
        )
        await service.start()
        assert service.watched_folder_count == 0

        service.add_folder_watch("/tmp/new_folder", debounce_seconds=10)
        await asyncio.sleep(0.01)

        assert service.watched_folder_count == 1

        await service.stop()

    assert service.watched_folder_count == 0


@pytest.mark.asyncio
async def test_add_folder_watch_no_op_if_not_running() -> None:
    """add_folder_watch is a no-op if service has not been started."""
    service = FileWatcherService(
        folder_manager=MagicMock(),
        job_service=MagicMock(),
        default_debounce_seconds=5,
    )
    # Service never started
    service.add_folder_watch("/tmp/folder")
    assert service.watched_folder_count == 0


@pytest.mark.asyncio
async def test_add_folder_watch_no_op_if_already_watching() -> None:
    """add_folder_watch is a no-op if already watching the folder."""
    folder = make_folder_record("/tmp/dup", watch_mode="auto")

    mock_folder_manager = MagicMock()
    mock_folder_manager.list_folders = AsyncMock(return_value=[folder])

    async def mock_awatch(*args: object, **kwargs: object) -> AsyncGenerator[set, None]:
        await asyncio.sleep(3600)
        yield

    with patch(
        "agent_brain_server.services.file_watcher_service.watchfiles.awatch",
        side_effect=mock_awatch,
    ):
        service = FileWatcherService(
            folder_manager=mock_folder_manager,
            job_service=MagicMock(),
            default_debounce_seconds=5,
        )
        await service.start()
        assert service.watched_folder_count == 1

        # Try to add again (duplicate)
        service.add_folder_watch("/tmp/dup")
        assert service.watched_folder_count == 1  # Still 1

        await service.stop()


@pytest.mark.asyncio
async def test_remove_folder_watch_cancels_task() -> None:
    """remove_folder_watch cancels and removes the task."""
    folder = make_folder_record("/tmp/to_remove", watch_mode="auto")

    mock_folder_manager = MagicMock()
    mock_folder_manager.list_folders = AsyncMock(return_value=[folder])

    async def mock_awatch(*args: object, **kwargs: object) -> AsyncGenerator[set, None]:
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise
        yield

    with patch(
        "agent_brain_server.services.file_watcher_service.watchfiles.awatch",
        side_effect=mock_awatch,
    ):
        service = FileWatcherService(
            folder_manager=mock_folder_manager,
            job_service=MagicMock(),
            default_debounce_seconds=5,
        )
        await service.start()
        assert service.watched_folder_count == 1

        service.remove_folder_watch("/tmp/to_remove")
        await asyncio.sleep(0.01)

        assert service.watched_folder_count == 0

        await service.stop()


@pytest.mark.asyncio
async def test_remove_folder_watch_no_op_for_unknown_folder() -> None:
    """remove_folder_watch is a no-op for folders not being watched."""
    mock_folder_manager = MagicMock()
    mock_folder_manager.list_folders = AsyncMock(return_value=[])

    service = FileWatcherService(
        folder_manager=mock_folder_manager,
        job_service=MagicMock(),
        default_debounce_seconds=5,
    )
    await service.start()

    # Should not raise
    service.remove_folder_watch("/tmp/not_watched")

    await service.stop()


# ---------------------------------------------------------------------------
# _enqueue_for_folder tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_for_folder_calls_enqueue_job_with_source_auto() -> None:
    """_enqueue_for_folder calls enqueue_job with source='auto' and force=False."""
    folder_record = make_folder_record("/tmp/code", include_code=True)

    mock_folder_manager = MagicMock()
    mock_folder_manager.get_folder = AsyncMock(return_value=folder_record)
    mock_folder_manager.list_folders = AsyncMock(return_value=[])

    mock_job_service = MagicMock()
    mock_job_service.enqueue_job = AsyncMock(
        return_value=make_enqueue_response(dedupe_hit=False)
    )

    service = FileWatcherService(
        folder_manager=mock_folder_manager,
        job_service=mock_job_service,
        default_debounce_seconds=30,
    )
    await service.start()

    await service._enqueue_for_folder("/tmp/code")

    mock_job_service.enqueue_job.assert_called_once()
    call_kwargs = mock_job_service.enqueue_job.call_args
    assert call_kwargs.kwargs.get("source") == "auto" or (
        len(call_kwargs.args) > 0 and False  # always use kwargs check
    )
    assert call_kwargs.kwargs["source"] == "auto"
    assert call_kwargs.kwargs["force"] is False
    assert call_kwargs.kwargs["operation"] == "index"
    assert call_kwargs.kwargs["allow_external"] is True

    request = call_kwargs.kwargs["request"]
    assert request.include_code is True
    assert request.force is False

    await service.stop()


@pytest.mark.asyncio
async def test_enqueue_for_folder_handles_dedupe_hit() -> None:
    """_enqueue_for_folder handles dedupe_hit=True gracefully (no exception)."""
    folder_record = make_folder_record("/tmp/docs")

    mock_folder_manager = MagicMock()
    mock_folder_manager.get_folder = AsyncMock(return_value=folder_record)
    mock_folder_manager.list_folders = AsyncMock(return_value=[])

    mock_job_service = MagicMock()
    mock_job_service.enqueue_job = AsyncMock(
        return_value=make_enqueue_response(dedupe_hit=True)
    )

    service = FileWatcherService(
        folder_manager=mock_folder_manager,
        job_service=mock_job_service,
        default_debounce_seconds=30,
    )
    await service.start()

    # Should not raise even on dedupe hit
    await service._enqueue_for_folder("/tmp/docs")

    mock_job_service.enqueue_job.assert_called_once()

    await service.stop()


@pytest.mark.asyncio
async def test_enqueue_for_folder_handles_missing_folder_record() -> None:
    """_enqueue_for_folder handles None folder record gracefully (logs warning)."""
    mock_folder_manager = MagicMock()
    mock_folder_manager.get_folder = AsyncMock(return_value=None)
    mock_folder_manager.list_folders = AsyncMock(return_value=[])

    mock_job_service = MagicMock()
    mock_job_service.enqueue_job = AsyncMock()

    service = FileWatcherService(
        folder_manager=mock_folder_manager,
        job_service=mock_job_service,
        default_debounce_seconds=30,
    )
    await service.start()

    # Should not raise even when folder record is missing
    await service._enqueue_for_folder("/tmp/gone")

    # enqueue_job should NOT have been called
    mock_job_service.enqueue_job.assert_not_called()

    await service.stop()


@pytest.mark.asyncio
async def test_enqueue_for_folder_handles_job_service_exception() -> None:
    """_enqueue_for_folder handles enqueue_job exceptions gracefully."""
    folder_record = make_folder_record("/tmp/err")

    mock_folder_manager = MagicMock()
    mock_folder_manager.get_folder = AsyncMock(return_value=folder_record)
    mock_folder_manager.list_folders = AsyncMock(return_value=[])

    mock_job_service = MagicMock()
    mock_job_service.enqueue_job = AsyncMock(side_effect=RuntimeError("Queue full"))

    service = FileWatcherService(
        folder_manager=mock_folder_manager,
        job_service=mock_job_service,
        default_debounce_seconds=30,
    )
    await service.start()

    # Should not raise even when job service throws
    await service._enqueue_for_folder("/tmp/err")

    await service.stop()


# ---------------------------------------------------------------------------
# is_running property tests
# ---------------------------------------------------------------------------


def test_is_running_false_before_start() -> None:
    """is_running is False before start() is called."""
    service = FileWatcherService(
        folder_manager=MagicMock(),
        job_service=MagicMock(),
    )
    assert service.is_running is False


@pytest.mark.asyncio
async def test_is_running_true_after_start() -> None:
    """is_running is True after start() and False after stop()."""
    mock_folder_manager = MagicMock()
    mock_folder_manager.list_folders = AsyncMock(return_value=[])

    service = FileWatcherService(
        folder_manager=mock_folder_manager,
        job_service=MagicMock(),
    )

    await service.start()
    assert service.is_running is True

    await service.stop()
    assert service.is_running is False
