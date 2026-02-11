"""Job queue models for indexing job management."""

import hashlib
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, computed_field


class JobStatus(str, Enum):
    """Status of an indexing job."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobProgress(BaseModel):
    """Progress tracking for an indexing job."""

    files_processed: int = Field(default=0, ge=0, description="Files processed so far")
    files_total: int = Field(default=0, ge=0, description="Total files to process")
    chunks_created: int = Field(default=0, ge=0, description="Chunks created so far")
    current_file: str = Field(default="", description="Currently processing file")
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last progress update timestamp",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def percent_complete(self) -> float:
        """Calculate completion percentage."""
        if self.files_total == 0:
            return 0.0
        return round((self.files_processed / self.files_total) * 100, 1)


class JobRecord(BaseModel):
    """Persistent job record for the queue."""

    id: str = Field(..., description="Unique job identifier (job_<uuid12>)")
    dedupe_key: str = Field(..., description="SHA256 hash for deduplication")

    # Request parameters (normalized)
    folder_path: str = Field(..., description="Resolved, normalized folder path")
    include_code: bool = Field(default=False, description="Whether to index code files")
    operation: str = Field(
        default="index", description="Operation type: 'index' or 'add'"
    )

    # Optional request parameters
    chunk_size: int = Field(default=512, description="Chunk size in tokens")
    chunk_overlap: int = Field(default=50, description="Chunk overlap in tokens")
    recursive: bool = Field(default=True, description="Recursive folder scan")
    generate_summaries: bool = Field(
        default=False, description="Generate LLM summaries"
    )
    supported_languages: list[str] | None = Field(
        default=None, description="Languages to index"
    )
    include_patterns: list[str] | None = Field(
        default=None, description="File patterns to include"
    )
    exclude_patterns: list[str] | None = Field(
        default=None, description="File patterns to exclude"
    )

    # Job state
    status: JobStatus = Field(
        default=JobStatus.PENDING, description="Current job status"
    )
    cancel_requested: bool = Field(
        default=False, description="Flag for graceful cancellation"
    )

    # Timestamps
    enqueued_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the job was enqueued",
    )
    started_at: datetime | None = Field(
        default=None, description="When the job started running"
    )
    finished_at: datetime | None = Field(
        default=None, description="When the job finished (done, failed, or cancelled)"
    )

    # Results and metadata
    error: str | None = Field(default=None, description="Error message if failed")
    retry_count: int = Field(default=0, ge=0, description="Number of retry attempts")
    progress: JobProgress | None = Field(default=None, description="Progress tracking")
    total_chunks: int = Field(default=0, ge=0, description="Total chunks indexed")
    total_documents: int = Field(default=0, ge=0, description="Total documents indexed")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def execution_time_ms(self) -> int | None:
        """Calculate execution time in milliseconds."""
        if self.started_at is None:
            return None
        end_time = self.finished_at or datetime.now(timezone.utc)
        delta = end_time - self.started_at
        return int(delta.total_seconds() * 1000)

    @staticmethod
    def compute_dedupe_key(
        folder_path: str,
        include_code: bool,
        operation: str,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> str:
        """Compute deduplication key from job parameters.

        Args:
            folder_path: Normalized, resolved folder path.
            include_code: Whether to include code files.
            operation: Operation type (index or add).
            include_patterns: Optional include patterns.
            exclude_patterns: Optional exclude patterns.

        Returns:
            SHA256 hash of normalized parameters.
        """
        # Normalize path (resolve and lowercase on case-insensitive systems)
        resolved = str(Path(folder_path).resolve())

        # Build dedupe string
        parts = [
            resolved,
            str(include_code),
            operation,
            ",".join(sorted(include_patterns or [])),
            ",".join(sorted(exclude_patterns or [])),
        ]
        dedupe_string = "|".join(parts)

        return hashlib.sha256(dedupe_string.encode()).hexdigest()


class JobEnqueueResponse(BaseModel):
    """Response when enqueueing a job."""

    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(default="pending", description="Job status")
    queue_position: int = Field(
        default=0, ge=0, description="Position in the queue (0 = first)"
    )
    queue_length: int = Field(default=0, ge=0, description="Total jobs in queue")
    message: str = Field(..., description="Human-readable status message")
    dedupe_hit: bool = Field(
        default=False, description="True if this was a duplicate request"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "job_id": "job_abc123def456",
                    "status": "pending",
                    "queue_position": 2,
                    "queue_length": 5,
                    "message": "Job queued for /path/to/docs",
                    "dedupe_hit": False,
                }
            ]
        }
    }


class JobListResponse(BaseModel):
    """Response for listing jobs."""

    jobs: list["JobSummary"] = Field(default_factory=list, description="List of jobs")
    total: int = Field(default=0, ge=0, description="Total number of jobs")
    pending: int = Field(default=0, ge=0, description="Number of pending jobs")
    running: int = Field(default=0, ge=0, description="Number of running jobs")
    completed: int = Field(default=0, ge=0, description="Number of completed jobs")
    failed: int = Field(default=0, ge=0, description="Number of failed jobs")


class JobSummary(BaseModel):
    """Summary view of a job for list responses."""

    id: str = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Current status")
    folder_path: str = Field(..., description="Folder being indexed")
    operation: str = Field(..., description="Operation type")
    include_code: bool = Field(..., description="Whether indexing code")
    enqueued_at: datetime = Field(..., description="When queued")
    started_at: datetime | None = Field(default=None, description="When started")
    finished_at: datetime | None = Field(default=None, description="When finished")
    progress_percent: float = Field(default=0.0, description="Completion percentage")
    error: str | None = Field(default=None, description="Error message if failed")

    @classmethod
    def from_record(cls, record: JobRecord) -> "JobSummary":
        """Create a summary from a full job record."""
        return cls(
            id=record.id,
            status=record.status,
            folder_path=record.folder_path,
            operation=record.operation,
            include_code=record.include_code,
            enqueued_at=record.enqueued_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            progress_percent=(
                record.progress.percent_complete if record.progress else 0.0
            ),
            error=record.error,
        )


class JobDetailResponse(BaseModel):
    """Detailed response for a single job."""

    id: str = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Current status")
    folder_path: str = Field(..., description="Folder being indexed")
    operation: str = Field(..., description="Operation type")
    include_code: bool = Field(..., description="Whether indexing code")

    # Timestamps
    enqueued_at: datetime = Field(..., description="When queued")
    started_at: datetime | None = Field(default=None, description="When started")
    finished_at: datetime | None = Field(default=None, description="When finished")
    execution_time_ms: int | None = Field(
        default=None, description="Execution time in ms"
    )

    # Progress
    progress: JobProgress | None = Field(default=None, description="Progress details")

    # Results
    total_documents: int = Field(default=0, description="Documents indexed")
    total_chunks: int = Field(default=0, description="Chunks created")
    error: str | None = Field(default=None, description="Error message if failed")
    retry_count: int = Field(default=0, description="Retry attempts")
    cancel_requested: bool = Field(
        default=False, description="Whether cancellation requested"
    )

    @classmethod
    def from_record(cls, record: JobRecord) -> "JobDetailResponse":
        """Create a detail response from a full job record."""
        return cls(
            id=record.id,
            status=record.status,
            folder_path=record.folder_path,
            operation=record.operation,
            include_code=record.include_code,
            enqueued_at=record.enqueued_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            execution_time_ms=record.execution_time_ms,
            progress=record.progress,
            total_documents=record.total_documents,
            total_chunks=record.total_chunks,
            error=record.error,
            retry_count=record.retry_count,
            cancel_requested=record.cancel_requested,
        )


class QueueStats(BaseModel):
    """Statistics about the job queue."""

    pending: int = Field(default=0, ge=0, description="Pending jobs count")
    running: int = Field(default=0, ge=0, description="Running jobs count")
    completed: int = Field(default=0, ge=0, description="Completed jobs count")
    failed: int = Field(default=0, ge=0, description="Failed jobs count")
    cancelled: int = Field(default=0, ge=0, description="Cancelled jobs count")
    total: int = Field(default=0, ge=0, description="Total jobs count")
    current_job_id: str | None = Field(
        default=None, description="Currently running job ID"
    )
    current_job_running_time_ms: int | None = Field(
        default=None, description="Current job running time in ms"
    )
