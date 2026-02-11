"""JSONL-based persistent job queue store with atomic writes and file locking."""

import asyncio
import logging
import os
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import IO, Any, Literal

from agent_brain_server.models.job import JobRecord, JobStatus, QueueStats

logger = logging.getLogger(__name__)


# Platform-safe file locking functions
# These are defined based on platform to provide consistent API
def _lock_file_noop(fd: int) -> None:
    """No-op file lock for platforms without native support."""
    pass


def _unlock_file_noop(fd: int) -> None:
    """No-op file unlock for platforms without native support."""
    pass


# Initialize lock/unlock functions based on platform
_lock_file: Callable[[int], None] = _lock_file_noop
_unlock_file: Callable[[int], None] = _unlock_file_noop
_lock_warning_shown = False

if sys.platform != "win32":
    try:
        import fcntl

        def _lock_file_fcntl(fd: int) -> None:
            """Lock file using fcntl (POSIX)."""
            fcntl.flock(fd, fcntl.LOCK_EX)

        def _unlock_file_fcntl(fd: int) -> None:
            """Unlock file using fcntl (POSIX)."""
            fcntl.flock(fd, fcntl.LOCK_UN)

        _lock_file = _lock_file_fcntl
        _unlock_file = _unlock_file_fcntl
    except ImportError:
        pass
else:
    try:
        import msvcrt

        def _lock_file_msvcrt(fd: int) -> None:
            """Lock file using msvcrt (Windows)."""
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)

        def _unlock_file_msvcrt(fd: int) -> None:
            """Unlock file using msvcrt (Windows)."""
            try:
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                # Ignore errors on unlock
                pass

        _lock_file = _lock_file_msvcrt
        _unlock_file = _unlock_file_msvcrt
    except ImportError:
        pass


class JobQueueStore:
    """JSONL-based persistent job queue with atomic writes and crash recovery.

    Features:
    - Append-only JSONL file for durability
    - Periodic snapshot compaction
    - File locking for multi-process safety
    - Restart recovery with stale job handling

    File structure:
    - index_queue.jsonl: Append-only job state changes
    - index_queue.snapshot: Full state snapshot for fast loading
    - .queue.lock: Lock file for file operations
    """

    QUEUE_FILE = "index_queue.jsonl"
    SNAPSHOT_FILE = "index_queue.snapshot"
    LOCK_FILE = ".queue.lock"

    MAX_RETRIES = 3
    COMPACT_THRESHOLD = 100  # Compact after N updates

    def __init__(self, state_dir: Path):
        """Initialize the job queue store.

        Args:
            state_dir: Directory for storing queue files.
        """
        self._state_dir = state_dir
        self._jobs_dir = state_dir / "jobs"
        self._jobs_dir.mkdir(parents=True, exist_ok=True)

        self._queue_path = self._jobs_dir / self.QUEUE_FILE
        self._snapshot_path = self._jobs_dir / self.SNAPSHOT_FILE
        self._lock_path = self._jobs_dir / self.LOCK_FILE

        # In-memory state
        self._jobs: dict[str, JobRecord] = {}
        self._update_count = 0

        # Async lock for in-process synchronization
        self._asyncio_lock = asyncio.Lock()

        logger.info(f"JobQueueStore initialized at {self._jobs_dir}")

    async def initialize(self) -> None:
        """Load jobs from persistent storage and handle stale RUNNING jobs.

        On startup:
        1. Load from snapshot if available
        2. Replay JSONL updates
        3. Reset stale RUNNING jobs to PENDING with retry tracking
        """
        async with self._asyncio_lock:
            await self._load_jobs()
            await self._handle_stale_jobs()

    async def _load_jobs(self) -> None:
        """Load jobs from snapshot and JSONL file."""
        self._jobs.clear()

        # Load from snapshot first (if exists)
        if self._snapshot_path.exists():
            try:
                with self._with_file_lock():
                    with open(self._snapshot_path) as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                job = JobRecord.model_validate_json(line)
                                self._jobs[job.id] = job
                logger.info(f"Loaded {len(self._jobs)} jobs from snapshot")
            except Exception as e:
                logger.error(f"Failed to load snapshot: {e}")
                self._jobs.clear()

        # Replay JSONL updates
        if self._queue_path.exists():
            try:
                with self._with_file_lock():
                    with open(self._queue_path) as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                job = JobRecord.model_validate_json(line)
                                self._jobs[job.id] = job
                logger.info(f"Replayed JSONL updates, total jobs: {len(self._jobs)}")
            except Exception as e:
                logger.error(f"Failed to replay JSONL: {e}")

    async def _handle_stale_jobs(self) -> None:
        """Handle jobs that were RUNNING when server stopped.

        - Reset to PENDING if retry_count < MAX_RETRIES
        - Mark as FAILED if retry_count >= MAX_RETRIES
        """
        stale_jobs = [
            job for job in self._jobs.values() if job.status == JobStatus.RUNNING
        ]

        for job in stale_jobs:
            job.retry_count += 1

            if job.retry_count > self.MAX_RETRIES:
                job.status = JobStatus.FAILED
                job.error = f"Max retries ({self.MAX_RETRIES}) exceeded after restart"
                job.finished_at = datetime.now(timezone.utc)
                logger.warning(
                    f"Job {job.id} permanently failed after {job.retry_count} retries"
                )
            else:
                job.status = JobStatus.PENDING
                job.started_at = None
                job.progress = None
                logger.info(f"Job {job.id} reset to PENDING (retry {job.retry_count})")

            await self._persist_job(job)

    def _with_file_lock(self) -> "_FileLock":
        """Context manager for file locking."""
        return _FileLock(self._lock_path)

    async def _persist_job(self, job: JobRecord) -> None:
        """Persist a job to JSONL with atomic write.

        Args:
            job: Job record to persist.
        """
        with self._with_file_lock():
            with open(self._queue_path, "a") as f:
                f.write(job.model_dump_json() + "\n")
                f.flush()
                os.fsync(f.fileno())

        self._update_count += 1

        # Compact if threshold exceeded
        if self._update_count >= self.COMPACT_THRESHOLD:
            await self._compact()

    async def _compact(self) -> None:
        """Compact queue by writing snapshot and truncating JSONL."""
        logger.info("Compacting job queue...")

        with self._with_file_lock():
            # Write snapshot to temp file
            tmp_path = self._snapshot_path.with_suffix(".tmp")
            with open(tmp_path, "w") as f:
                for job in self._jobs.values():
                    f.write(job.model_dump_json() + "\n")
                f.flush()
                os.fsync(f.fileno())

            # Atomic rename
            tmp_path.rename(self._snapshot_path)

            # Truncate JSONL
            with open(self._queue_path, "w") as f:
                f.truncate(0)
                f.flush()
                os.fsync(f.fileno())

        self._update_count = 0
        logger.info(f"Compaction complete: {len(self._jobs)} jobs in snapshot")

    async def append_job(self, job: JobRecord) -> int:
        """Append a new job to the queue.

        Args:
            job: Job record to append.

        Returns:
            Queue position (0-indexed).
        """
        async with self._asyncio_lock:
            self._jobs[job.id] = job
            await self._persist_job(job)

            # Calculate queue position
            pending_jobs = [
                j
                for j in self._jobs.values()
                if j.status == JobStatus.PENDING and j.id != job.id
            ]
            position = len(pending_jobs)

            logger.info(f"Job {job.id} appended at position {position}")
            return position

    async def update_job(self, job: JobRecord) -> None:
        """Update an existing job.

        Args:
            job: Job record with updated fields.
        """
        async with self._asyncio_lock:
            if job.id not in self._jobs:
                raise KeyError(f"Job {job.id} not found")

            self._jobs[job.id] = job
            await self._persist_job(job)

    async def get_job(self, job_id: str) -> JobRecord | None:
        """Get a job by ID.

        Args:
            job_id: Job identifier.

        Returns:
            Job record or None if not found.
        """
        return self._jobs.get(job_id)

    async def find_by_dedupe_key(self, dedupe_key: str) -> JobRecord | None:
        """Find an active job by deduplication key.

        Args:
            dedupe_key: SHA256 dedupe key.

        Returns:
            Matching job in PENDING or RUNNING status, or None.
        """
        for job in self._jobs.values():
            if job.dedupe_key == dedupe_key and job.status in (
                JobStatus.PENDING,
                JobStatus.RUNNING,
            ):
                return job
        return None

    async def get_pending_jobs(self) -> list[JobRecord]:
        """Get all pending jobs in FIFO order.

        Returns:
            List of pending jobs ordered by enqueue time.
        """
        pending = [j for j in self._jobs.values() if j.status == JobStatus.PENDING]
        return sorted(pending, key=lambda j: j.enqueued_at)

    async def get_running_job(self) -> JobRecord | None:
        """Get the currently running job, if any.

        Returns:
            Running job or None.
        """
        for job in self._jobs.values():
            if job.status == JobStatus.RUNNING:
                return job
        return None

    async def get_all_jobs(self, limit: int = 50, offset: int = 0) -> list[JobRecord]:
        """Get all jobs with pagination.

        Args:
            limit: Maximum jobs to return.
            offset: Number of jobs to skip.

        Returns:
            List of jobs sorted by enqueue time (newest first).
        """
        all_jobs = sorted(
            self._jobs.values(), key=lambda j: j.enqueued_at, reverse=True
        )
        return all_jobs[offset : offset + limit]

    async def get_queue_stats(self) -> QueueStats:
        """Get statistics about the queue.

        Returns:
            QueueStats with counts and current job info.
        """
        pending = 0
        running = 0
        completed = 0
        failed = 0
        cancelled = 0
        current_job_id = None
        current_job_running_time_ms = None

        for job in self._jobs.values():
            if job.status == JobStatus.PENDING:
                pending += 1
            elif job.status == JobStatus.RUNNING:
                running += 1
                current_job_id = job.id
                if job.started_at:
                    delta = datetime.now(timezone.utc) - job.started_at
                    current_job_running_time_ms = int(delta.total_seconds() * 1000)
            elif job.status == JobStatus.DONE:
                completed += 1
            elif job.status == JobStatus.FAILED:
                failed += 1
            elif job.status == JobStatus.CANCELLED:
                cancelled += 1

        return QueueStats(
            pending=pending,
            running=running,
            completed=completed,
            failed=failed,
            cancelled=cancelled,
            total=len(self._jobs),
            current_job_id=current_job_id,
            current_job_running_time_ms=current_job_running_time_ms,
        )

    async def get_queue_length(self) -> int:
        """Get number of pending + running jobs.

        Returns:
            Count of jobs not yet completed.
        """
        return sum(
            1
            for j in self._jobs.values()
            if j.status in (JobStatus.PENDING, JobStatus.RUNNING)
        )


class _FileLock:
    """Platform-safe file locking context manager.

    Uses fcntl on POSIX (Linux, macOS) and msvcrt on Windows.
    Falls back to no-op locking if neither is available.
    """

    def __init__(self, lock_path: Path) -> None:
        self._lock_path = lock_path
        self._lock_file: IO[Any] | None = None

    def __enter__(self) -> "_FileLock":
        global _lock_warning_shown

        self._lock_file = open(self._lock_path, "w")

        # Check if we're using the no-op lock
        if _lock_file is _lock_file_noop and not _lock_warning_shown:
            logger.warning(
                "File locking not available on this platform. "
                "Concurrent access may cause issues."
            )
            _lock_warning_shown = True

        _lock_file(self._lock_file.fileno())
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        if self._lock_file:
            _unlock_file(self._lock_file.fileno())
            self._lock_file.close()
        return False
