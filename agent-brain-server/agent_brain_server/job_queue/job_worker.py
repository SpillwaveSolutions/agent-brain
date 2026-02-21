"""Background job worker that processes indexing jobs from the queue."""

import asyncio
import logging
from datetime import datetime, timezone

from agent_brain_server.job_queue.job_store import JobQueueStore
from agent_brain_server.models import IndexingState, IndexingStatusEnum, IndexRequest
from agent_brain_server.models.job import JobProgress, JobRecord, JobStatus
from agent_brain_server.services.indexing_service import IndexingService

logger = logging.getLogger(__name__)


class CancellationRequestedError(Exception):
    """Raised when a job cancellation is requested."""

    pass


class JobWorker:
    """Background asyncio task that polls for and processes indexing jobs.

    Features:
    - Polls for pending jobs from JobQueueStore
    - Processes one job at a time (concurrency=1)
    - Timeout support with configurable MAX_RUNTIME_SECONDS
    - Cancellation via cancel_requested flag on JobRecord
    - Progress updates at configurable intervals
    - Verifies storage backend has chunks after indexing before marking DONE

    Example:
        worker = JobWorker(job_store, indexing_service)
        await worker.start()
        # ... later ...
        await worker.stop()
    """

    # Default configuration
    MAX_RUNTIME_SECONDS: int = 7200  # 2 hours
    PROGRESS_CHECKPOINT_INTERVAL: int = 50  # Update progress every N files
    POLL_INTERVAL_SECONDS: float = 1.0  # Poll for new jobs every N seconds

    def __init__(
        self,
        job_store: JobQueueStore,
        indexing_service: IndexingService,
        max_runtime_seconds: int | None = None,
        progress_checkpoint_interval: int | None = None,
        poll_interval_seconds: float | None = None,
    ):
        """Initialize the job worker.

        Args:
            job_store: Job queue store for persistence.
            indexing_service: Indexing service for processing jobs.
            max_runtime_seconds: Maximum job runtime before timeout.
            progress_checkpoint_interval: Update progress every N files.
            poll_interval_seconds: Poll interval for checking new jobs.
        """
        self._job_store = job_store
        self._indexing_service = indexing_service

        # Configuration (use instance values or defaults)
        self._max_runtime_seconds = max_runtime_seconds or self.MAX_RUNTIME_SECONDS
        self._progress_interval = (
            progress_checkpoint_interval or self.PROGRESS_CHECKPOINT_INTERVAL
        )
        self._poll_interval = poll_interval_seconds or self.POLL_INTERVAL_SECONDS

        # Internal state
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._current_job: JobRecord | None = None
        self._stop_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        """Check if the worker is currently running."""
        return self._running and self._task is not None and not self._task.done()

    @property
    def current_job(self) -> JobRecord | None:
        """Get the currently processing job, if any."""
        return self._current_job

    async def start(self) -> None:
        """Start the background worker task.

        Creates an asyncio task that polls for pending jobs and processes them.
        Safe to call multiple times (subsequent calls are no-ops if already running).
        """
        if self._running:
            logger.warning("JobWorker already running")
            return

        self._running = True
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("JobWorker started")

    async def stop(self, timeout: float = 30.0) -> None:
        """Gracefully stop the worker.

        Signals the worker to stop and waits for the current job to complete
        or for the timeout to expire.

        Args:
            timeout: Maximum seconds to wait for graceful shutdown.
        """
        if not self._running:
            return

        logger.info("JobWorker stopping...")
        self._running = False
        self._stop_event.set()

        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    f"JobWorker did not stop within {timeout}s, cancelling task"
                )
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

        self._task = None
        self._current_job = None
        logger.info("JobWorker stopped")

    async def _run_loop(self) -> None:
        """Main worker loop that polls for and processes jobs.

        Continuously polls for pending jobs and processes them one at a time.
        Exits when stop() is called.
        """
        logger.info("JobWorker run loop started")

        while self._running:
            try:
                # Check for pending jobs
                pending_jobs = await self._job_store.get_pending_jobs()

                if pending_jobs:
                    # Process the first pending job (FIFO)
                    job = pending_jobs[0]
                    await self._process_job(job)
                else:
                    # No jobs, wait before polling again
                    try:
                        await asyncio.wait_for(
                            self._stop_event.wait(),
                            timeout=self._poll_interval,
                        )
                        # If we get here, stop was requested
                        break
                    except asyncio.TimeoutError:
                        # Normal timeout, continue polling
                        pass

            except Exception as e:
                logger.error(f"Error in job worker loop: {e}", exc_info=True)
                # Brief pause before retrying to avoid tight error loop
                await asyncio.sleep(1.0)

        logger.info("JobWorker run loop exited")

    async def _process_job(self, job: JobRecord) -> None:
        """Process a single indexing job.

        Marks the job as RUNNING, executes the indexing pipeline with timeout,
        and marks the job as DONE, FAILED, or CANCELLED based on outcome.

        Args:
            job: The job record to process.
        """
        logger.info(f"Processing job {job.id} for {job.folder_path}")
        self._current_job = job

        try:
            # Mark job as RUNNING
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            job.progress = JobProgress(
                files_processed=0,
                files_total=0,
                chunks_created=0,
                current_file="",
                updated_at=datetime.now(timezone.utc),
            )
            await self._job_store.update_job(job)

            # Set IndexingService state to indicate indexing is in progress
            # This ensures status endpoints reflect the correct state
            async with self._indexing_service._lock:
                self._indexing_service._state = IndexingState(
                    current_job_id=job.id,
                    status=IndexingStatusEnum.INDEXING,
                    is_indexing=True,
                    folder_path=job.folder_path,
                    started_at=job.started_at,
                    completed_at=None,
                    error=None,
                )

            # Create IndexRequest from JobRecord
            index_request = IndexRequest(
                folder_path=job.folder_path,
                include_code=job.include_code,
                chunk_size=job.chunk_size,
                chunk_overlap=job.chunk_overlap,
                recursive=job.recursive,
                generate_summaries=job.generate_summaries,
                supported_languages=job.supported_languages,
                include_patterns=job.include_patterns,
                exclude_patterns=job.exclude_patterns,
            )

            # Create progress callback that checks for cancellation
            async def progress_callback(current: int, total: int, message: str) -> None:
                """Progress callback that updates job and checks for cancellation."""
                # Re-fetch job to check for cancellation request
                refreshed_job = await self._job_store.get_job(job.id)
                if refreshed_job and refreshed_job.cancel_requested:
                    logger.info(f"Cancellation requested for job {job.id}")
                    raise CancellationRequestedError(
                        f"Job {job.id} cancellation requested"
                    )

                # Update progress at intervals
                if (
                    job.progress is None
                    or current - job.progress.files_processed >= self._progress_interval
                    or current == total
                ):
                    job.progress = JobProgress(
                        files_processed=current,
                        files_total=total,
                        chunks_created=0,  # Will be updated at end
                        current_file=message,
                        updated_at=datetime.now(timezone.utc),
                    )
                    await self._job_store.update_job(job)

            # Get chunk count before indexing for delta verification
            count_before = 0
            try:
                storage = self._indexing_service.storage_backend
                if storage.is_initialized:
                    count_before = await storage.get_count()
            except Exception as e:
                logger.warning(f"Could not get count before indexing: {e}")

            # Execute indexing with timeout
            try:
                await asyncio.wait_for(
                    self._indexing_service._run_indexing_pipeline(
                        index_request, job.id, progress_callback
                    ),
                    timeout=self._max_runtime_seconds,
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"Job {job.id} timed out after {self._max_runtime_seconds}s"
                )
                job.status = JobStatus.FAILED
                job.error = f"Job timed out after {self._max_runtime_seconds} seconds"
                job.finished_at = datetime.now(timezone.utc)
                await self._job_store.update_job(job)

                # Clear IndexingService state on timeout
                async with self._indexing_service._lock:
                    self._indexing_service._state = IndexingState(
                        current_job_id=job.id,
                        status=IndexingStatusEnum.FAILED,
                        is_indexing=False,
                        folder_path=job.folder_path,
                        started_at=job.started_at,
                        completed_at=job.finished_at,
                        error=job.error,
                    )
                return

            # Verify collection has new chunks (delta verification)
            verification_passed = await self._verify_collection_delta(job, count_before)

            if verification_passed:
                # Get final chunk count from indexing service status
                status = await self._indexing_service.get_status()
                job.total_chunks = status.get("total_chunks", 0)
                job.total_documents = status.get("total_documents", 0)

                # Update final progress
                if job.progress:
                    job.progress = JobProgress(
                        files_processed=job.progress.files_total,
                        files_total=job.progress.files_total,
                        chunks_created=job.total_chunks,
                        current_file="Complete",
                        updated_at=datetime.now(timezone.utc),
                    )

                job.status = JobStatus.DONE
                job.finished_at = datetime.now(timezone.utc)
                logger.info(
                    f"Job {job.id} completed: {job.total_documents} docs, "
                    f"{job.total_chunks} chunks"
                )

                # Clear IndexingService state on success
                async with self._indexing_service._lock:
                    self._indexing_service._state = IndexingState(
                        current_job_id=job.id,
                        status=IndexingStatusEnum.COMPLETED,
                        is_indexing=False,
                        folder_path=job.folder_path,
                        started_at=job.started_at,
                        completed_at=job.finished_at,
                        error=None,
                    )
            else:
                job.status = JobStatus.FAILED
                job.error = "Verification failed: No chunks found in vector store"
                job.finished_at = datetime.now(timezone.utc)
                logger.error(f"Job {job.id} verification failed: no chunks in store")

                # Clear IndexingService state on verification failure
                async with self._indexing_service._lock:
                    self._indexing_service._state = IndexingState(
                        current_job_id=job.id,
                        status=IndexingStatusEnum.FAILED,
                        is_indexing=False,
                        folder_path=job.folder_path,
                        started_at=job.started_at,
                        completed_at=job.finished_at,
                        error=job.error,
                    )

            await self._job_store.update_job(job)

        except CancellationRequestedError:
            job.status = JobStatus.CANCELLED
            job.error = "Job was cancelled by user request"
            job.finished_at = datetime.now(timezone.utc)
            await self._job_store.update_job(job)

            # Clear IndexingService state on cancellation
            async with self._indexing_service._lock:
                self._indexing_service._state = IndexingState(
                    current_job_id=job.id,
                    status=IndexingStatusEnum.IDLE,
                    is_indexing=False,
                    folder_path=job.folder_path,
                    started_at=job.started_at,
                    completed_at=job.finished_at,
                    error=job.error,
                )
            logger.info(f"Job {job.id} cancelled")

        except Exception as e:
            logger.error(f"Job {job.id} failed with error: {e}", exc_info=True)
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.finished_at = datetime.now(timezone.utc)
            await self._job_store.update_job(job)

            # Clear IndexingService state on error
            async with self._indexing_service._lock:
                self._indexing_service._state = IndexingState(
                    current_job_id=job.id,
                    status=IndexingStatusEnum.FAILED,
                    is_indexing=False,
                    folder_path=job.folder_path,
                    started_at=job.started_at,
                    completed_at=job.finished_at,
                    error=job.error,
                )

        finally:
            self._current_job = None

    async def _verify_collection_delta(self, job: JobRecord, count_before: int) -> bool:
        """Verify that the vector store has new chunks after indexing.

        Uses delta verification (count_after - count_before) to avoid false
        positives when prior chunks exist but the job added nothing.

        Args:
            job: The job record to verify.
            count_before: Chunk count before indexing started.

        Returns:
            True if verification passed (new chunks added), False otherwise.
        """
        try:
            storage = self._indexing_service.storage_backend
            count_after = await storage.get_count()
            delta = count_after - count_before

            if delta > 0:
                logger.info(
                    f"Verification passed for job {job.id}: "
                    f"{delta} new chunks (before={count_before}, after={count_after})"
                )
                return True
            elif count_after > 0 and delta == 0:
                # Special case: job might have processed files that were already indexed
                # Check if any documents were processed
                if job.progress and job.progress.files_processed > 0:
                    logger.warning(
                        f"Job {job.id} processed {job.progress.files_processed} files "
                        f"but added no new chunks (may have been already indexed)"
                    )
                    # Consider this a success if files were processed
                    return True
                logger.warning(
                    f"Verification failed for job {job.id}: no new chunks added "
                    f"(before={count_before}, after={count_after})"
                )
                return False
            else:
                logger.warning(
                    f"Verification failed for job {job.id}: no chunks in vector store"
                )
                return False

        except Exception as e:
            logger.error(f"Verification error for job {job.id}: {e}")
            return False
