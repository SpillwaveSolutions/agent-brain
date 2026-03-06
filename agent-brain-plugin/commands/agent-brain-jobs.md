---
name: agent-brain-jobs
description: Monitor and manage async indexing jobs in the queue
parameters:
  - name: job_id
    description: Specific job ID to inspect or cancel
    required: false
  - name: watch
    description: Poll the queue with live updates every 3 seconds
    required: false
    default: false
  - name: cancel
    description: Cancel the specified job (requires job_id)
    required: false
    default: false
skills:
  - using-agent-brain
---

# Job Queue Management

## Purpose

Monitor and manage async indexing jobs. Indexing runs in the background via a job queue — use this command to list jobs, watch progress, inspect details (including eviction summaries for incremental indexing), and cancel stuck or unwanted jobs.

## Usage

```
/agent-brain-jobs
/agent-brain-jobs --watch
/agent-brain-jobs <job_id>
/agent-brain-jobs <job_id> --cancel
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| job_id | No | - | Specific job ID to inspect |
| --watch / -w | No | false | Poll queue every 3 seconds with live updates |
| --cancel / -c | No | false | Cancel the specified job (requires job_id) |
| --limit / -l | No | 20 | Maximum number of jobs to show |
| --json | No | false | Output as JSON |

### Examples

```
# List all jobs
/agent-brain-jobs

# Watch queue with live updates
/agent-brain-jobs --watch

# Inspect a specific job
/agent-brain-jobs abc123

# Cancel a running job
/agent-brain-jobs abc123 --cancel
```

## Execution

Based on the parameters:

### List All Jobs

```bash
agent-brain jobs
```

### Watch Queue (Live Updates)

```bash
agent-brain jobs --watch
```

Press Ctrl+C to stop watching.

### Inspect Job Details

```bash
agent-brain jobs <job_id>
```

### Cancel a Job

```bash
agent-brain jobs <job_id> --cancel
```

### Expected Output

**List:**
```
Job ID    Status     Folder                  Created
abc123    completed  /home/user/docs         2026-03-05T12:00:00
def456    running    /home/user/src          2026-03-05T12:05:00
ghi789    queued     /home/user/tests        2026-03-05T12:06:00
```

**Job Detail (with eviction summary):**
```
Job Details: abc123

Status:    completed
Folder:    /home/user/docs
Created:   2026-03-05T12:00:00
Completed: 2026-03-05T12:00:45

Eviction Summary:
  Files added:     3
  Files changed:   2
  Files deleted:   1
  Files unchanged: 42
  Chunks evicted:  15
  Chunks created:  25
```

**Watch mode:**
```
Job Queue (polling every 3s, Ctrl+C to stop)

Job ID    Status     Folder                  Progress
def456    running    /home/user/src          Processing...
ghi789    queued     /home/user/tests        Waiting...
```

## Job Status Values

| Status | Meaning |
|--------|---------|
| `queued` | Job is waiting in the queue |
| `pending` | Job is about to start |
| `running` | Job is actively indexing |
| `completed` | Job finished successfully |
| `failed` | Job encountered an error |
| `cancelled` | Job was cancelled by user |

## Eviction Summary (Incremental Indexing)

When a folder is re-indexed, Agent Brain uses manifest tracking to detect changes. The eviction summary shows:

| Field | Meaning |
|-------|---------|
| Files added | New files not previously indexed |
| Files changed | Files with different content (old chunks evicted, new ones created) |
| Files deleted | Files removed from disk (their chunks are evicted) |
| Files unchanged | Files with same content (skipped for efficiency) |
| Chunks evicted | Old chunk embeddings removed from the index |
| Chunks created | New chunk embeddings added to the index |

This enables efficient incremental updates — only changed files are re-processed.

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| Server not running | Agent Brain server is stopped | Run `agent-brain start` |
| Job not found | Invalid job ID | Check `agent-brain jobs` for valid IDs |
| Queue full (429) | Too many concurrent jobs | Wait for current jobs to complete |
| Connection error | Server unreachable | Verify with `agent-brain status` |

### Recovery Commands

```bash
# Check server status
agent-brain status

# List all jobs to find valid IDs
agent-brain jobs

# Cancel a stuck job
agent-brain jobs <job_id> --cancel

# Force re-index if job failed
agent-brain index <path> --force
```

## Notes

- Jobs run asynchronously in the background
- Only one job runs at a time; others queue in FIFO order
- Watch mode polls every 3 seconds and shows live status changes
- Eviction summary only appears for incremental re-indexing (not first-time indexing)
- Use `--force` on the index/inject command to bypass manifest and force full re-indexing
- Job history persists across server restarts (JSONL storage)
