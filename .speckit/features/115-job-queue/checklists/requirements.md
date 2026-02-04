# Feature 115: Job Queue - Requirements Checklist

## Core Requirements

### Job Queue Infrastructure

- [x] JobQueueStore with JSONL persistence
- [x] File-based locking for concurrent access
- [x] Job ID generation (job_<uuid12> format)
- [x] State transitions (PENDING -> RUNNING -> DONE/FAILED/CANCELLED)

### Job Worker

- [x] Background worker thread started with server
- [x] Sequential job processing (one at a time)
- [x] Timeout handling for stuck jobs
- [x] Graceful cancellation via cancel_requested flag
- [x] Progress tracking during execution

### Job Deduplication

- [x] SHA256-based dedupe key computation
- [x] Parameters included: folder_path, include_code, operation, patterns
- [x] Return existing job_id for duplicates
- [x] dedupe_hit flag in response

### Backpressure

- [x] Maximum queue size limit (100 jobs)
- [x] 429 Too Many Requests when full
- [x] Queue length in enqueue response

---

## API Endpoints

### Modified Endpoints

- [x] POST /index returns 202 Accepted
- [x] POST /index/add returns 202 Accepted
- [x] Response includes job_id, queue_position, queue_length

### New Endpoints

- [x] GET /index/jobs/ - List all jobs
- [x] GET /index/jobs/{job_id} - Get job details
- [x] DELETE /index/jobs/{job_id} - Cancel job

### Response Models

- [x] JobEnqueueResponse model
- [x] JobListResponse model
- [x] JobSummary model
- [x] JobDetailResponse model
- [x] QueueStats model

---

## CLI Integration

### Jobs Command

- [x] `agent-brain jobs` - List all jobs
- [x] `agent-brain jobs --watch` - Live updates with Rich table
- [x] `agent-brain jobs <job_id>` - Show job details
- [x] `agent-brain jobs <job_id> --cancel` - Cancel job

### Index Command Updates

- [x] Shows job_id when indexing starts
- [x] Non-blocking by default
- [x] `--wait` option for synchronous behavior (optional)

---

## Runtime Autodiscovery

### runtime.json

- [x] Written before server starts (both modes)
- [x] Location: .claude/agent-brain/runtime.json
- [x] Contains: base_url, port, bind_host, pid, started_at, foreground

### CLI Config

- [x] Config module reads runtime.json
- [x] Resolution order: AGENT_BRAIN_URL > runtime.json > config.yaml > default
- [x] Walks directory tree upward to find runtime.json

---

## Documentation

- [x] API_REFERENCE.md updated with job endpoints
- [x] USER_GUIDE.md updated with job queue section
- [x] CHANGELOG.md created for v3.0.0
- [x] data-model.md created with Pydantic models
- [x] api-extensions.md created with API contracts

---

## Testing

### Unit Tests

- [x] JobQueueStore tests
- [x] JobWorker tests
- [x] Deduplication tests
- [x] Progress tracking tests

### Integration Tests

- [x] POST /index returns 202
- [x] GET /index/jobs/ returns list
- [x] Job completion flow
- [x] Cancellation flow

### Local Integration Check

- [x] scripts/local_integration_check.sh created
- [x] Validates runtime.json creation
- [x] Validates job completion
- [x] Validates query after indexing

---

## Version Increment

- [x] agent-brain-server/pyproject.toml -> 3.0.0
- [x] agent-brain-server/__init__.py -> 3.0.0
- [x] agent-brain-cli/pyproject.toml -> 3.0.0
- [x] agent-brain-cli/__init__.py -> 3.0.0
- [x] agent-brain-plugin/plugin.json -> 3.0.0

---

## Removed Features

- [x] No --daemon flag (server backgrounds by default)
- [x] locking.py no longer deletes runtime.json

---

## Known Test Baselines

- Server tests: 341 pass (1 pre-existing similarity_threshold failure expected)
- CLI tests: 72 pass (state-dir test may be flaky)
