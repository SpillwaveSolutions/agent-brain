# Feature 115: Job Queue - Data Model

## Overview

This document defines the Pydantic models used in the server-side job queue implementation.

---

## Job Status Enum

```python
class JobStatus(str, Enum):
    """Status of an indexing job."""
    PENDING = "pending"     # Queued, waiting to run
    RUNNING = "running"     # Currently executing
    DONE = "done"           # Completed successfully
    FAILED = "failed"       # Failed with error
    CANCELLED = "cancelled" # Cancelled by user
```

**State Transitions:**

```
PENDING -> RUNNING -> DONE
    |         |
    |         v
    |     FAILED
    v
CANCELLED
```

---

## JobProgress Model

Tracks progress of a running job.

| Field | Type | Description |
|-------|------|-------------|
| `files_processed` | int | Files processed so far (>=0) |
| `files_total` | int | Total files to process (>=0) |
| `chunks_created` | int | Chunks created so far (>=0) |
| `current_file` | str | Currently processing file path |
| `updated_at` | datetime | Last progress update timestamp (UTC) |
| `percent_complete` | float | Computed: (files_processed / files_total) * 100 |

---

## JobRecord Model

Primary persistence model for queue entries.

### Identifiers

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Unique job identifier (format: `job_<uuid12>`) |
| `dedupe_key` | str | SHA256 hash for deduplication |

### Request Parameters (Normalized)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `folder_path` | str | - | Resolved, normalized folder path |
| `include_code` | bool | false | Whether to index code files |
| `operation` | str | "index" | Operation type: 'index' or 'add' |
| `chunk_size` | int | 512 | Chunk size in tokens |
| `chunk_overlap` | int | 50 | Chunk overlap in tokens |
| `recursive` | bool | true | Recursive folder scan |
| `generate_summaries` | bool | false | Generate LLM summaries |
| `supported_languages` | list[str] | null | Languages to index |
| `include_patterns` | list[str] | null | File patterns to include |
| `exclude_patterns` | list[str] | null | File patterns to exclude |

### Job State

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | JobStatus | PENDING | Current job status |
| `cancel_requested` | bool | false | Flag for graceful cancellation |

### Timestamps

| Field | Type | Description |
|-------|------|-------------|
| `enqueued_at` | datetime | When the job was enqueued (UTC) |
| `started_at` | datetime? | When the job started running |
| `finished_at` | datetime? | When the job finished |

### Results and Metadata

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `error` | str? | null | Error message if failed |
| `retry_count` | int | 0 | Number of retry attempts |
| `progress` | JobProgress? | null | Progress tracking |
| `total_chunks` | int | 0 | Total chunks indexed |
| `total_documents` | int | 0 | Total documents indexed |
| `execution_time_ms` | int? | computed | Execution time in ms |

### Deduplication Key Computation

```python
@staticmethod
def compute_dedupe_key(
    folder_path: str,
    include_code: bool,
    operation: str,
    include_patterns: Optional[list[str]] = None,
    exclude_patterns: Optional[list[str]] = None,
) -> str:
    """Compute SHA256 hash of normalized parameters."""
    resolved = str(Path(folder_path).resolve())
    parts = [
        resolved,
        str(include_code),
        operation,
        ",".join(sorted(include_patterns or [])),
        ",".join(sorted(exclude_patterns or [])),
    ]
    dedupe_string = "|".join(parts)
    return hashlib.sha256(dedupe_string.encode()).hexdigest()
```

---

## Response Models

### JobEnqueueResponse

Returned when enqueueing a job (HTTP 202).

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | str | Unique job identifier |
| `status` | str | Job status ("pending") |
| `queue_position` | int | Position in queue (0 = first) |
| `queue_length` | int | Total jobs in queue |
| `message` | str | Human-readable status message |
| `dedupe_hit` | bool | True if duplicate request |

### JobListResponse

Returned when listing jobs.

| Field | Type | Description |
|-------|------|-------------|
| `jobs` | list[JobSummary] | List of job summaries |
| `total` | int | Total number of jobs |
| `pending` | int | Number of pending jobs |
| `running` | int | Number of running jobs |
| `completed` | int | Number of completed jobs |
| `failed` | int | Number of failed jobs |

### JobSummary

Summary view for list responses.

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Job identifier |
| `status` | JobStatus | Current status |
| `folder_path` | str | Folder being indexed |
| `operation` | str | Operation type |
| `include_code` | bool | Whether indexing code |
| `enqueued_at` | datetime | When queued |
| `started_at` | datetime? | When started |
| `finished_at` | datetime? | When finished |
| `progress_percent` | float | Completion percentage |
| `error` | str? | Error message if failed |

### JobDetailResponse

Detailed response for single job.

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Job identifier |
| `status` | JobStatus | Current status |
| `folder_path` | str | Folder being indexed |
| `operation` | str | Operation type |
| `include_code` | bool | Whether indexing code |
| `enqueued_at` | datetime | When queued |
| `started_at` | datetime? | When started |
| `finished_at` | datetime? | When finished |
| `execution_time_ms` | int? | Execution time in ms |
| `progress` | JobProgress? | Progress details |
| `total_documents` | int | Documents indexed |
| `total_chunks` | int | Chunks created |
| `error` | str? | Error message if failed |
| `retry_count` | int | Retry attempts |
| `cancel_requested` | bool | Whether cancellation requested |

### QueueStats

Statistics about the job queue.

| Field | Type | Description |
|-------|------|-------------|
| `pending` | int | Pending jobs count |
| `running` | int | Running jobs count |
| `completed` | int | Completed jobs count |
| `failed` | int | Failed jobs count |
| `cancelled` | int | Cancelled jobs count |
| `total` | int | Total jobs count |
| `current_job_id` | str? | Currently running job ID |
| `current_job_running_time_ms` | int? | Current job running time |

---

## Persistence Format

Jobs are persisted in `.claude/agent-brain/jobs/index_queue.jsonl` using JSON Lines format:

```jsonl
{"id":"job_abc123","status":"done","folder_path":"/docs",...}
{"id":"job_def456","status":"pending","folder_path":"/src",...}
```

### File Locking

The queue file uses file-based locking via `.claude/agent-brain/jobs/.queue.lock` to prevent concurrent access issues.
