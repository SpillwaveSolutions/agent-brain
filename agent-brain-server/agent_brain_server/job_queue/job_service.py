"""API-facing service for job queue management.

Provides job enqueueing with deduplication, path validation, job listing,
detail retrieval, and cancellation.
"""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agent_brain_server.job_queue.job_store import JobQueueStore
from agent_brain_server.models import IndexRequest
from agent_brain_server.models.job import (
    JobDetailResponse,
    JobEnqueueResponse,
    JobListResponse,
    JobRecord,
    JobStatus,
    JobSummary,
    QueueStats,
)

logger = logging.getLogger(__name__)


class JobQueueService:
    """API-facing service for job queue operations.

    Provides:
    - Job enqueueing with deduplication
    - Path validation (project root checking)
    - Job listing, detail retrieval, and cancellation
    - Queue statistics

    Backpressure is handled at the router level, not here.
    """

    def __init__(self, store: JobQueueStore, project_root: Path | None = None) -> None:
        """Initialize the job queue service.

        Args:
            store: The underlying job queue store for persistence.
            project_root: Root directory for path validation. If None, all paths
                are allowed and path validation is skipped.
        """
        self._store = store
        self._project_root = project_root.resolve() if project_root else None
        logger.info(
            f"JobQueueService initialized with project_root={self._project_root}"
        )

    @property
    def store(self) -> JobQueueStore:
        """Get the underlying job queue store."""
        return self._store

    @property
    def project_root(self) -> Path | None:
        """Get the project root directory."""
        return self._project_root

    def _validate_path(self, path: str, allow_external: bool) -> Path:
        """Validate and resolve a path.

        Args:
            path: The path to validate.
            allow_external: Whether to allow paths outside project root.

        Returns:
            Resolved Path object.

        Raises:
            ValueError: If path is outside project root and allow_external is False.
        """
        resolved = Path(path).resolve()

        # If no project root configured, skip path validation
        if self._project_root is None:
            return resolved

        if not allow_external:
            try:
                resolved.relative_to(self._project_root)
            except ValueError as err:
                raise ValueError(
                    f"Path '{resolved}' is outside project root "
                    f"'{self._project_root}'. "
                    "Use allow_external=True to index paths outside the project."
                ) from err

        return resolved

    def _generate_job_id(self) -> str:
        """Generate a unique job ID.

        Returns:
            Job ID in format job_<uuid12>.
        """
        return f"job_{uuid.uuid4().hex[:12]}"

    async def enqueue_job(
        self,
        request: IndexRequest,
        operation: str = "index",
        force: bool = False,
        allow_external: bool = False,
    ) -> JobEnqueueResponse:
        """Enqueue an indexing job with deduplication.

        Args:
            request: The indexing request containing folder path and options.
            operation: Operation type - 'index' (replace) or 'add' (append).
            force: If True, skip deduplication check and always create new job.
            allow_external: If True, allow paths outside project root.

        Returns:
            JobEnqueueResponse with job details and queue position.

        Raises:
            ValueError: If path is outside project root and allow_external is False.
        """
        # Validate and resolve path
        resolved_path = self._validate_path(request.folder_path, allow_external)
        folder_path_str = str(resolved_path)

        # Compute deduplication key
        dedupe_key = JobRecord.compute_dedupe_key(
            folder_path=folder_path_str,
            include_code=request.include_code,
            operation=operation,
            include_patterns=request.include_patterns,
            exclude_patterns=request.exclude_patterns,
        )

        # Check for existing job (unless force=True)
        if not force:
            existing_job = await self._store.find_by_dedupe_key(dedupe_key)
            if existing_job is not None:
                # Return existing job info with dedupe_hit=True
                queue_length = await self._store.get_queue_length()
                pending_jobs = await self._store.get_pending_jobs()

                # Calculate position of existing job in queue
                position = 0
                for i, job in enumerate(pending_jobs):
                    if job.id == existing_job.id:
                        position = i
                        break

                logger.info(
                    f"Dedupe hit: returning existing job {existing_job.id} "
                    f"for path {folder_path_str}"
                )

                return JobEnqueueResponse(
                    job_id=existing_job.id,
                    status=existing_job.status.value,
                    queue_position=position,
                    queue_length=queue_length,
                    message=f"Existing job found for {folder_path_str}",
                    dedupe_hit=True,
                )

        # Create new job record
        job_id = self._generate_job_id()
        job = JobRecord(
            id=job_id,
            dedupe_key=dedupe_key,
            folder_path=folder_path_str,
            include_code=request.include_code,
            operation=operation,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
            recursive=request.recursive,
            generate_summaries=request.generate_summaries,
            supported_languages=request.supported_languages,
            include_patterns=request.include_patterns,
            exclude_patterns=request.exclude_patterns,
            status=JobStatus.PENDING,
            enqueued_at=datetime.now(timezone.utc),
        )

        # Append to queue and get position
        position = await self._store.append_job(job)
        queue_length = await self._store.get_queue_length()

        logger.info(
            f"Job {job_id} enqueued at position {position} for path {folder_path_str}"
        )

        return JobEnqueueResponse(
            job_id=job_id,
            status=JobStatus.PENDING.value,
            queue_position=position,
            queue_length=queue_length,
            message=f"Job queued for {folder_path_str}",
            dedupe_hit=False,
        )

    async def get_job(self, job_id: str) -> JobDetailResponse | None:
        """Get detailed information about a specific job.

        Args:
            job_id: The job identifier.

        Returns:
            JobDetailResponse with full job details, or None if not found.
        """
        job = await self._store.get_job(job_id)
        if job is None:
            return None

        return JobDetailResponse.from_record(job)

    async def list_jobs(self, limit: int = 50, offset: int = 0) -> JobListResponse:
        """List jobs with pagination.

        Args:
            limit: Maximum number of jobs to return.
            offset: Number of jobs to skip.

        Returns:
            JobListResponse with job summaries and counts.
        """
        jobs = await self._store.get_all_jobs(limit=limit, offset=offset)
        stats = await self._store.get_queue_stats()

        summaries = [JobSummary.from_record(job) for job in jobs]

        return JobListResponse(
            jobs=summaries,
            total=stats.total,
            pending=stats.pending,
            running=stats.running,
            completed=stats.completed,
            failed=stats.failed,
        )

    async def cancel_job(self, job_id: str) -> dict[str, str]:
        """Request cancellation of a job.

        Only PENDING or RUNNING jobs can be cancelled.
        For RUNNING jobs, sets cancel_requested flag for graceful cancellation.

        Args:
            job_id: The job identifier.

        Returns:
            Dict with status and message.

        Raises:
            KeyError: If job not found.
            ValueError: If job cannot be cancelled (already completed/failed/cancelled).
        """
        job = await self._store.get_job(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")

        if job.status == JobStatus.CANCELLED:
            return {
                "status": "already_cancelled",
                "message": f"Job {job_id} was already cancelled",
            }

        if job.status in (JobStatus.DONE, JobStatus.FAILED):
            raise ValueError(
                f"Cannot cancel job {job_id}: job has already {job.status.value}"
            )

        if job.status == JobStatus.RUNNING:
            # Request graceful cancellation
            # Create new job record with cancel_requested=True
            # (JobRecord is a Pydantic model, so we use model_copy)
            updated_job = job.model_copy(update={"cancel_requested": True})
            await self._store.update_job(updated_job)

            logger.info(f"Cancellation requested for running job {job_id}")
            return {
                "status": "cancellation_requested",
                "message": f"Cancellation requested for running job {job_id}. "
                "Job will stop at next checkpoint.",
            }

        if job.status == JobStatus.PENDING:
            # Cancel immediately
            updated_job = job.model_copy(
                update={
                    "status": JobStatus.CANCELLED,
                    "cancel_requested": True,
                    "finished_at": datetime.now(timezone.utc),
                }
            )
            await self._store.update_job(updated_job)

            logger.info(f"Pending job {job_id} cancelled")
            return {
                "status": "cancelled",
                "message": f"Job {job_id} cancelled",
            }

        # Should not reach here, but handle gracefully
        return {
            "status": "unknown",
            "message": f"Job {job_id} is in unexpected status: {job.status.value}",
        }

    async def get_queue_stats(self) -> QueueStats:
        """Get statistics about the job queue.

        Returns:
            QueueStats with counts and current job info.
        """
        return await self._store.get_queue_stats()
