"""File watcher service for automatic incremental re-indexing.

This module provides FileWatcherService, which starts one asyncio task per
auto-mode folder using watchfiles.awatch(). When file changes are detected,
it enqueues an incremental indexing job via the job queue (deduplicated, force=False).

Key design decisions:
- One asyncio Task per folder (independent lifecycle)
- anyio.Event for clean shutdown (watchfiles supports stop_event natively)
- Deduplication via existing dedupe_key mechanism (no double-indexing)
- source="auto" distinguishes watcher-triggered jobs from manual jobs
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import anyio
import watchfiles
from watchfiles import DefaultFilter

from agent_brain_server.models.index import IndexRequest

if TYPE_CHECKING:
    from agent_brain_server.job_queue.job_service import JobQueueService
    from agent_brain_server.services.folder_manager import FolderManager

logger = logging.getLogger(__name__)


# Directories to exclude from watching (extends DefaultFilter defaults)
_EXTRA_IGNORE_DIRS = frozenset(
    {
        "dist",
        "build",
        ".next",
        ".nuxt",
        "coverage",
        "htmlcov",
    }
)


class AgentBrainWatchFilter(DefaultFilter):
    """Custom watchfiles filter that extends DefaultFilter with extra ignore dirs.

    DefaultFilter already ignores .git/, __pycache__/, node_modules/, .tox,
    .venv, etc. This subclass adds project-specific build artifact directories.
    """

    ignore_dirs: tuple[str, ...] = tuple(DefaultFilter.ignore_dirs) + tuple(
        _EXTRA_IGNORE_DIRS
    )


async def _watch_folder_loop(
    folder_path: str,
    debounce_ms: int,
    stop_event: anyio.Event,
    enqueue_callback: Callable[[str], Awaitable[None]],
) -> None:
    """Async loop that watches a folder and enqueues jobs on changes.

    Args:
        folder_path: Absolute path to the folder to watch.
        debounce_ms: Debounce interval in milliseconds.
        stop_event: anyio.Event — when set, the watcher exits cleanly.
        enqueue_callback: Async callable invoked with folder_path on each change.
    """
    logger.info(
        f"File watcher started for {folder_path} " f"(debounce={debounce_ms}ms)"
    )
    try:
        async for _changes in watchfiles.awatch(
            folder_path,
            debounce=debounce_ms,
            stop_event=stop_event,
            recursive=True,
            watch_filter=AgentBrainWatchFilter(),
        ):
            logger.debug(
                f"File changes detected in {folder_path} " f"({len(_changes)} event(s))"
            )
            await enqueue_callback(folder_path)
    except asyncio.CancelledError:
        logger.info(f"File watcher task cancelled for {folder_path}")
        raise
    except Exception as exc:
        logger.error(
            f"File watcher error for {folder_path}: {exc!r} — stopping watcher",
            exc_info=True,
        )


class FileWatcherService:
    """Manages per-folder asyncio tasks for file watching.

    On server startup, starts one asyncio Task per folder with watch_mode='auto'.
    On file change, enqueues an incremental indexing job (deduplicated, force=False).
    On shutdown, cleans up all watcher tasks gracefully via anyio.Event.

    Usage::

        service = FileWatcherService(folder_manager, job_service, debounce_seconds=30)
        await service.start()
        # ... server running ...
        await service.stop()
    """

    def __init__(
        self,
        folder_manager: FolderManager,
        job_service: JobQueueService,
        default_debounce_seconds: int = 30,
    ) -> None:
        """Initialize FileWatcherService.

        Args:
            folder_manager: FolderManager instance for listing/getting folder records.
            job_service: JobQueueService instance for enqueueing jobs.
            default_debounce_seconds: Global debounce in seconds for folders without
                a per-folder override.
        """
        self._folder_manager = folder_manager
        self._job_service = job_service
        self._default_debounce_seconds = default_debounce_seconds
        self._stop_event: anyio.Event | None = None
        self._tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def watched_folder_count(self) -> int:
        """Number of folders currently being watched."""
        return len(self._tasks)

    @property
    def is_running(self) -> bool:
        """True if the watcher service has been started and not yet stopped."""
        return self._stop_event is not None and not self._stop_event.is_set()

    async def start(self) -> None:
        """Start the file watcher service.

        Creates an anyio.Event (must be called inside an async context) and
        launches a watcher task for each folder with watch_mode='auto'.
        """
        # anyio.Event MUST be created inside an async context
        self._stop_event = anyio.Event()

        folders = await self._folder_manager.list_folders()
        auto_folders = [f for f in folders if f.watch_mode == "auto"]

        for folder_record in auto_folders:
            self._start_task(
                folder_path=folder_record.folder_path,
                debounce_seconds=folder_record.watch_debounce_seconds,
            )

        logger.info(
            f"FileWatcherService started: watching {len(auto_folders)} "
            f"folder(s) (default debounce={self._default_debounce_seconds}s)"
        )

    async def stop(self) -> None:
        """Stop the file watcher service gracefully.

        Sets the stop_event (signals watchfiles.awatch to exit), cancels all
        tasks, and waits for them to finish.
        """
        if self._stop_event is not None:
            self._stop_event.set()

        # Cancel and await all watcher tasks
        tasks_snapshot = list(self._tasks.items())
        for _folder_path, task in tasks_snapshot:
            if not task.done():
                task.cancel()

        for _folder_path, task in tasks_snapshot:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        self._tasks.clear()
        logger.info("FileWatcherService stopped")

    def add_folder_watch(
        self,
        folder_path: str,
        debounce_seconds: int | None = None,
    ) -> None:
        """Start watching a new folder.

        Called after a folder is registered with watch_mode='auto'.
        No-op if the service is not running or already watching the folder.

        Args:
            folder_path: Absolute path to the folder to watch.
            debounce_seconds: Per-folder debounce (None = use global default).
        """
        if not self.is_running:
            logger.debug(
                f"add_folder_watch called but service not running " f"for {folder_path}"
            )
            return

        if folder_path in self._tasks:
            logger.debug(f"Already watching {folder_path}")
            return

        self._start_task(folder_path=folder_path, debounce_seconds=debounce_seconds)
        logger.info(f"Added file watcher for {folder_path}")

    def remove_folder_watch(self, folder_path: str) -> None:
        """Stop watching a folder.

        Called when a folder is removed or its watch_mode is set to 'off'.

        Args:
            folder_path: Absolute path to the folder to stop watching.
        """
        task = self._tasks.pop(folder_path, None)
        if task is not None and not task.done():
            task.cancel()
            logger.info(f"Removed file watcher for {folder_path}")
        else:
            logger.debug(f"No active watcher to remove for {folder_path}")

    def _start_task(
        self,
        folder_path: str,
        debounce_seconds: int | None,
    ) -> None:
        """Create and register an asyncio task for watching a folder.

        Args:
            folder_path: Absolute path to the folder.
            debounce_seconds: Per-folder override (None = use global default).
        """
        effective_debounce = debounce_seconds or self._default_debounce_seconds
        debounce_ms = effective_debounce * 1000

        assert (
            self._stop_event is not None
        ), "_start_task called before start() — stop_event is None"

        task = asyncio.create_task(
            _watch_folder_loop(
                folder_path=folder_path,
                debounce_ms=debounce_ms,
                stop_event=self._stop_event,
                enqueue_callback=self._enqueue_for_folder,
            ),
            name=f"watcher:{folder_path}",
        )
        self._tasks[folder_path] = task

    async def _enqueue_for_folder(self, folder_path: str) -> None:
        """Enqueue an incremental indexing job for the given folder.

        Reads include_code from the folder's FolderRecord and creates an
        IndexRequest with force=False (rely on ManifestTracker for incremental).
        Deduplication by existing dedupe_key mechanism prevents double-indexing.

        Args:
            folder_path: Absolute path to the changed folder.
        """
        try:
            folder_record = await self._folder_manager.get_folder(folder_path)
            if folder_record is None:
                logger.warning(
                    f"File watcher: folder record not found for {folder_path} "
                    f"— skipping enqueue"
                )
                return

            include_code = folder_record.include_code
            request = IndexRequest(
                folder_path=folder_path,
                include_code=include_code,
                recursive=True,
                force=False,
            )
            response = await self._job_service.enqueue_job(
                request=request,
                operation="index",
                force=False,
                allow_external=True,
                source="auto",
            )

            if response.dedupe_hit:
                logger.debug(
                    f"File watcher dedupe hit for {folder_path} "
                    f"(existing job: {response.job_id})"
                )
            else:
                logger.info(
                    f"File watcher enqueued job {response.job_id} " f"for {folder_path}"
                )

        except Exception as exc:
            logger.error(
                f"File watcher failed to enqueue job for {folder_path}: {exc!r}",
                exc_info=True,
            )
