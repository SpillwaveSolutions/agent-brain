---
phase: 15-file-watcher-and-background-incremental-updates
plan: "01"
subsystem: services
tags: [watchfiles, anyio, asyncio, file-watcher, job-queue, incremental-indexing, background-tasks]

# Dependency graph
requires:
  - phase: 14-manifest-and-eviction
    provides: ManifestTracker for incremental indexing, JobRecord model
  - phase: 12-folder-management-and-presets
    provides: FolderManager, FolderRecord, job queue system
provides:
  - FileWatcherService with per-folder asyncio tasks using watchfiles.awatch()
  - FolderRecord extended with watch_mode, watch_debounce_seconds, include_code fields
  - JobRecord extended with source field (manual/auto)
  - enqueue_job() accepts source parameter
  - IndexRequest extended with watch_mode, watch_debounce_seconds
  - FolderInfo API response includes watch_mode, watch_debounce_seconds
  - Settings.AGENT_BRAIN_WATCH_DEBOUNCE_SECONDS = 30
  - /health/status includes file_watcher section (running, watched_folders)
  - Backward compatibility: v7.0 JSONL records load cleanly without watch fields
affects:
  - 15-02-plan (CLI/plugin commands for --watch auto flag)
  - 16-embedding-cache (watcher generates repeated auto-reindex events to cache)
  - 17-query-cache (file watcher triggers index_generation invalidation)

# Tech tracking
tech-stack:
  added:
    - watchfiles 1.1.1 (already transitive dep via uvicorn — no new install needed)
    - anyio.Event (for clean shutdown signaling to watchfiles.awatch stop_event)
  patterns:
    - One asyncio.Task per watched folder (independent lifecycle, named tasks)
    - anyio.Event created inside async context (required by anyio docs)
    - source="auto" field distinguishes watcher-triggered vs user-triggered jobs
    - Deduplication via existing dedupe_key mechanism (BGINC-02 satisfied)
    - TYPE_CHECKING guard for FolderManager/JobQueueService to avoid circular imports

key-files:
  created:
    - agent-brain-server/agent_brain_server/services/file_watcher_service.py
    - agent-brain-server/tests/test_file_watcher_service.py
    - agent-brain-server/tests/test_folder_manager_watch.py
  modified:
    - agent-brain-server/agent_brain_server/services/folder_manager.py
    - agent-brain-server/agent_brain_server/services/__init__.py
    - agent-brain-server/agent_brain_server/models/job.py
    - agent-brain-server/agent_brain_server/models/index.py
    - agent-brain-server/agent_brain_server/models/folders.py
    - agent-brain-server/agent_brain_server/config/settings.py
    - agent-brain-server/agent_brain_server/job_queue/job_service.py
    - agent-brain-server/agent_brain_server/api/main.py
    - agent-brain-server/agent_brain_server/api/routers/health.py
    - agent-brain-server/agent_brain_server/models/health.py
    - agent-brain-server/agent_brain_server/api/routers/folders.py

key-decisions:
  - "watchfiles is already a transitive dep via uvicorn — no new dependency needed"
  - "anyio.Event (not asyncio.Event) used because watchfiles.awatch expects anyio-compatible stop_event"
  - "One asyncio.Task per folder (not one event loop for all) allows independent folder lifecycles"
  - "source field default='manual' maintains full backward compatibility with existing job records"
  - "force=False for watcher-triggered jobs — rely on ManifestTracker for incremental efficiency (BGINC-03)"
  - "allow_external=True for watcher-enqueued jobs — folders may be outside project root"
  - "TYPE_CHECKING guard imports prevent circular dependency: services -> job_queue -> models"
  - "AgentBrainWatchFilter.ignore_dirs uses tuple concatenation not + operator (mypy Sequence[str] type)"

patterns-established:
  - "Watcher pattern: start() discovers auto-mode folders, creates tasks; stop() sets anyio.Event then cancels"
  - "Backward compat: JSONL loader uses data.get('field', default) for new optional fields"
  - "Service lifecycle: file watcher starts AFTER job worker, stops BEFORE job worker (dependency order)"
  - "Health endpoint pattern: getattr(request.app.state, 'service', None) for optional services"

requirements-completed:
  - WATCH-01
  - WATCH-02
  - WATCH-03
  - WATCH-04
  - WATCH-05
  - WATCH-06
  - BGINC-01
  - BGINC-02
  - BGINC-03
  - BGINC-04

# Metrics
duration: 7min
completed: 2026-03-07
---

# Phase 15 Plan 01: File Watcher & Background Incremental Updates — Server-Side Summary

**FileWatcherService with per-folder asyncio tasks using watchfiles.awatch(), wired into FastAPI lifespan with source="auto" job enqueueing and backward-compatible FolderRecord/JobRecord model extensions**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-07T03:38:00Z
- **Completed:** 2026-03-07T03:45:00Z
- **Tasks:** 2
- **Files modified:** 13

## Accomplishments

- Created `FileWatcherService` with per-folder asyncio tasks, `AgentBrainWatchFilter` extending `DefaultFilter` with dist/build/.next/coverage dirs, and clean shutdown via `anyio.Event`
- Extended `FolderRecord`, `JobRecord`, `IndexRequest`, `FolderInfo`, and `Settings` with all fields needed for Phase 15-02 CLI integration — no further server model changes required
- Wired `FileWatcherService` into FastAPI lifespan (starts after `JobWorker`, stops before `JobWorker`), with `/health/status` reporting watcher running status and watched folder count
- 31 new unit tests (13 model + 18 watcher) all passing, `task before-push` exits 0 (860 passed, 77% coverage)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend data models** - `c5b4d47` (feat)
2. **Task 2: Create FileWatcherService, wire into lifespan, add health status** - `0ebed71` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `agent_brain_server/services/file_watcher_service.py` — NEW: FileWatcherService, AgentBrainWatchFilter, _watch_folder_loop
- `tests/test_file_watcher_service.py` — NEW: 18 unit tests for FileWatcherService
- `tests/test_folder_manager_watch.py` — NEW: 13 tests for model backward compat and watch fields
- `agent_brain_server/services/folder_manager.py` — FolderRecord: watch_mode, watch_debounce_seconds, include_code; add_folder() kwargs; backward-compat _load_jsonl
- `agent_brain_server/services/__init__.py` — FileWatcherService export added
- `agent_brain_server/models/job.py` — JobRecord/JobSummary/JobDetailResponse: source field (default='manual')
- `agent_brain_server/models/index.py` — IndexRequest: watch_mode, watch_debounce_seconds fields
- `agent_brain_server/models/folders.py` — FolderInfo: watch_mode, watch_debounce_seconds fields
- `agent_brain_server/models/health.py` — IndexingStatus: file_watcher field
- `agent_brain_server/config/settings.py` — AGENT_BRAIN_WATCH_DEBOUNCE_SECONDS=30
- `agent_brain_server/job_queue/job_service.py` — enqueue_job(): source parameter added
- `agent_brain_server/api/main.py` — FileWatcherService wired into lifespan start/stop, both branches
- `agent_brain_server/api/routers/health.py` — /health/status includes file_watcher section
- `agent_brain_server/api/routers/folders.py` — FolderInfo construction includes watch_mode, watch_debounce_seconds

## Decisions Made

- watchfiles 1.1.1 is already a transitive dependency via uvicorn — no new dependency install needed
- `anyio.Event` used (not `asyncio.Event`) because `watchfiles.awatch()` stop_event parameter requires anyio-compatible event; must be created inside async context
- `force=False` for watcher-triggered jobs — ManifestTracker performs incremental diffing, avoiding unnecessary re-embedding (BGINC-03)
- `allow_external=True` for watcher-enqueued jobs — auto-mode folders registered before project-root was set would fail validation otherwise
- `TYPE_CHECKING` guard prevents circular imports: `services/file_watcher_service.py` imports from `job_queue/job_service.py` which imports from `services/` at runtime
- `tuple(DefaultFilter.ignore_dirs) + tuple(_EXTRA_IGNORE_DIRS)` pattern required (not `+` on Sequence) to satisfy mypy strict operator typing

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added `file_watcher` field to IndexingStatus model**
- **Found during:** Task 2 (health router update)
- **Issue:** Plan specified adding file_watcher info to /health/status response dict, but the IndexingStatus Pydantic model didn't have a `file_watcher` field — the response would fail Pydantic validation
- **Fix:** Added `file_watcher: dict[str, Any] | None = Field(default=None, ...)` to `IndexingStatus` in `models/health.py`
- **Files modified:** agent-brain-server/agent_brain_server/models/health.py
- **Verification:** mypy passes, all tests pass
- **Committed in:** 0ebed71 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (missing critical field for correctness)
**Impact on plan:** Required for correctness — without it the health endpoint would fail at runtime. No scope creep.

## Issues Encountered

- mypy `type: ignore[assignment]` on `ignore_dirs` class attribute caused an "unused ignore comment" error — resolved by using explicit `tuple[str, ...]` type annotation instead
- Ruff `UP037` flag on quoted type annotations in `__init__` — resolved with `ruff --fix` (quotes not needed with `from __future__ import annotations`)
- `from __future__ import annotations` already present made the `TYPE_CHECKING` guard pattern work cleanly

## User Setup Required

None - no external service configuration required. watchfiles is already installed via uvicorn.

## Next Phase Readiness

- Plan 15-02 can implement CLI `--watch auto` flag using `FolderRecord.watch_mode` and `FileWatcherService.add_folder_watch()`
- All server-side model fields are in place — CLI only needs to read/write `watch_mode` and `watch_debounce_seconds` fields
- `FileWatcherService` is accessible via `app.state.file_watcher_service` for CLI commands that need to trigger watcher updates
- No blockers for Phase 15-02

---
*Phase: 15-file-watcher-and-background-incremental-updates*
*Completed: 2026-03-07*
