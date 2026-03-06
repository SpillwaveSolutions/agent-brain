# Phase 15: File Watcher & Background Incremental Updates - Context

**Gathered:** 2026-03-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Folders configured with `watch_mode: auto` automatically stay indexed after every file change, without any manual reindex command. Per-folder debounce collapses rapid edits and git operations into single reindex jobs. The watcher integrates with the existing job queue — no changes to the indexing pipeline itself.

</domain>

<decisions>
## Implementation Decisions

### Watcher Config Model
- Extend FolderRecord dataclass with `watch_mode: str = "off"` and `watch_debounce_seconds: int | None = None` fields
- Persisted in existing `indexed_folders.jsonl` — single source of truth for all folder config
- Global default debounce (30 seconds) in config.yaml, with per-folder override via `watch_debounce_seconds`
- Default watch_mode for new folders is `off` (explicit opt-in) — no surprise behavior

### CLI Surface
- `--watch` and `--debounce` flags added to the existing `agent-brain folders add` command
- Usage: `agent-brain folders add ./src --watch auto --debounce 10`
- Consistent with existing `--include-type` pattern on folders add
- No separate `agent-brain folders watch` command — all config via flags on `folders add`

### Job Source Tracking
- New `source: str` field on JobRecord Pydantic model with values `"manual"` or `"auto"`
- Default `"manual"` preserves backward compatibility with existing jobs
- Source column added to `agent-brain jobs` table output
- Debounce + existing dedupe_key deduplication is sufficient — no additional rate limiting
- Auto and manual jobs cancel identically — no special bulk cancel for auto jobs

### Claude's Discretion
- Exclusion patterns for watcher (.git/, __pycache__/, dist/, build/, node_modules/) — hardcoded sensible defaults
- Watcher lifecycle: start watching on server boot for all auto folders, stop when folder removed
- watchfiles `awatch()` usage pattern including stop_event for graceful shutdown
- Error handling for watcher failures (log and continue, don't crash server)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `FolderManager` (`services/folder_manager.py`): dataclass-based FolderRecord, async JSONL persistence with atomic writes, asyncio.Lock for thread safety
- `JobQueueService.enqueue_job()` (`job_queue/job_service.py`): dedupe_key prevents duplicate PENDING/RUNNING jobs for same folder — watcher events naturally deduplicated
- `watchfiles` already installed as transitive dep via uvicorn[standard] — zero new dependencies needed

### Established Patterns
- Module-level `_job_worker` ref in `api/main.py` with `start()`/`stop()` in lifespan — FileWatcherService follows identical pattern
- `asyncio.create_task()` for background work in lifespan (JobWorker does this)
- Atomic JSONL writes via temp + Path.replace() for FolderManager persistence

### Integration Points
- `api/main.py` lifespan: Add `_file_watcher` construction and start/stop alongside `_job_worker`
- `app.state.folder_manager`: FileWatcherService reads this to know which folders to watch
- `app.state.job_service`: FileWatcherService calls `enqueue_job()` with `force=False` and `source="auto"`
- `folders add` CLI command: Add `--watch` and `--debounce` flags
- `folders list` CLI command: Show watch_mode and watcher status columns
- `/health/status` endpoint: Include watcher status (running/stopped, folder count)

</code_context>

<specifics>
## Specific Ideas

- Per-folder debounce default is 30 seconds — user specified this explicitly
- Some directories are read-only and won't change (watch_mode: off), others need auto-reindex (watch_mode: auto)
- Watcher-triggered jobs use `force=False` to leverage ManifestTracker incremental diff — only changed files processed
- The `source` field on JobRecord enables CLI filtering and display of auto vs manual jobs

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 15-file-watcher-and-background-incremental-updates*
*Context gathered: 2026-03-06*
