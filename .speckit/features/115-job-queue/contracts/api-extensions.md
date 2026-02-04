# Feature 115: Job Queue - API Contract Extensions

## Overview

This document defines the API contract changes for the server-side job queue feature.

---

## Modified Endpoints

### POST /index

**Change:** Now returns `202 Accepted` instead of blocking until indexing completes.

**Request:** Unchanged (see existing API_REFERENCE.md)

**Response** `202 Accepted`:

```json
{
  "job_id": "job_abc123def456",
  "status": "pending",
  "queue_position": 0,
  "queue_length": 1,
  "message": "Job queued for /path/to/documents",
  "dedupe_hit": false
}
```

**Error Responses:**

| Code | Condition | Body |
|------|-----------|------|
| `400` | Invalid folder path | `{"detail": "Folder not found: /path"}` |
| `400` | Empty folder path | `{"detail": "folder_path is required"}` |
| `429` | Queue full (backpressure) | `{"detail": "Queue is full. Try again later."}` |

**Deduplication Behavior:**

If an identical job (same folder_path, include_code, operation, patterns) is already pending or running:

```json
{
  "job_id": "job_abc123def456",
  "status": "pending",
  "queue_position": 2,
  "queue_length": 5,
  "message": "Duplicate job - returning existing job",
  "dedupe_hit": true
}
```

### POST /index/add

Same changes as `POST /index` with `operation: "add"`.

---

## New Endpoints

### GET /index/jobs/

List all jobs in the queue.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | null | Filter by status (pending, running, done, failed, cancelled) |
| `limit` | int | 100 | Maximum results (1-500) |
| `offset` | int | 0 | Skip first N results |

**Response** `200 OK`:

```json
{
  "jobs": [
    {
      "id": "job_abc123def456",
      "status": "running",
      "folder_path": "/path/to/docs",
      "operation": "index",
      "include_code": true,
      "enqueued_at": "2026-02-03T10:00:00Z",
      "started_at": "2026-02-03T10:00:05Z",
      "finished_at": null,
      "progress_percent": 45.5,
      "error": null
    }
  ],
  "total": 1,
  "pending": 0,
  "running": 1,
  "completed": 0,
  "failed": 0
}
```

---

### GET /index/jobs/{job_id}

Get detailed information about a specific job.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `job_id` | string | Job identifier (e.g., `job_abc123def456`) |

**Response** `200 OK`:

```json
{
  "id": "job_abc123def456",
  "status": "running",
  "folder_path": "/path/to/docs",
  "operation": "index",
  "include_code": true,
  "enqueued_at": "2026-02-03T10:00:00Z",
  "started_at": "2026-02-03T10:00:05Z",
  "finished_at": null,
  "execution_time_ms": 15000,
  "progress": {
    "files_processed": 45,
    "files_total": 100,
    "chunks_created": 230,
    "current_file": "src/services/auth.py",
    "updated_at": "2026-02-03T10:00:20Z",
    "percent_complete": 45.0
  },
  "total_documents": 45,
  "total_chunks": 230,
  "error": null,
  "retry_count": 0,
  "cancel_requested": false
}
```

**Error Response** `404 Not Found`:

```json
{
  "detail": "Job not found: job_invalid123"
}
```

---

### DELETE /index/jobs/{job_id}

Cancel a pending or running job.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `job_id` | string | Job identifier |

**Response** `200 OK`:

```json
{
  "job_id": "job_abc123def456",
  "status": "cancelled",
  "message": "Job cancellation requested"
}
```

**Error Responses:**

| Code | Condition | Body |
|------|-----------|------|
| `404` | Job not found | `{"detail": "Job not found: job_id"}` |
| `409` | Already completed | `{"detail": "Cannot cancel completed job"}` |

**Cancellation Behavior:**

- **Pending jobs:** Immediately marked as `cancelled`
- **Running jobs:** `cancel_requested` flag set; worker checks periodically and stops gracefully
- **Done/Failed/Cancelled jobs:** Returns `409 Conflict`

---

## Health Status Extensions

### GET /health/status

**Added Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `current_job_id` | string? | ID of currently running job |
| `progress_percent` | float | Progress of current job (0.0 if none) |

**Example Response:**

```json
{
  "total_documents": 150,
  "total_chunks": 1200,
  "indexing_in_progress": true,
  "current_job_id": "job_abc123def456",
  "progress_percent": 45.5,
  "last_indexed_at": "2026-02-03T10:30:00Z",
  ...
}
```

---

## WebSocket Events (Future)

Reserved for future implementation:

```
ws://localhost:8000/ws/jobs/{job_id}
```

Events:
- `progress` - Progress update
- `completed` - Job finished successfully
- `failed` - Job failed with error
- `cancelled` - Job was cancelled

---

## CLI Integration

The CLI `jobs` command interacts with these endpoints:

```bash
# List all jobs
agent-brain jobs
# -> GET /index/jobs/

# Watch queue with live updates
agent-brain jobs --watch
# -> GET /index/jobs/ (polling)

# Get job details
agent-brain jobs job_abc123
# -> GET /index/jobs/job_abc123

# Cancel a job
agent-brain jobs job_abc123 --cancel
# -> DELETE /index/jobs/job_abc123
```

---

## Rate Limiting

The job queue implements backpressure:

- **Max queue size:** 100 jobs (configurable)
- **Max concurrent jobs:** 1 (sequential processing)
- **Deduplication window:** Jobs with identical parameters within queue

When queue is full, `POST /index` returns `429 Too Many Requests`.
