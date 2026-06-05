---
phase: 15-file-watcher-and-background-incremental-updates
plan: "02"
subsystem: cli, job-queue, plugin
tags: [watch-mode, cli-flags, job-worker, file-watcher, plugin-docs, end-to-end]

# Dependency graph
requires:
  - phase: 15-file-watcher-and-background-incremental-updates
    plan: "01"
    provides: FileWatcherService, FolderRecord watch fields, JobRecord source field, IndexRequest watch fields
provides:
  - CLI --watch auto/off and --debounce flags on folders add
  - CLI folders list Watch column
  - CLI jobs Source column (manual/auto)
  - JobRecord watch_mode and watch_debounce_seconds fields
  - JobWorker._apply_watch_config() notifies FileWatcherService after job completion
  - IndexingService passes include_code to folder_manager.add_folder()
  - Plugin docs updated with file watcher section
affects:
  - 16-embedding-cache (watcher auto-reindex events flow through job queue)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "JobWorker setter injection: set_file_watcher_service() and set_folder_manager() called after lifespan init"
    - "Watch config applied post-completion: _apply_watch_config() runs after DONE status, updates FolderRecord then notifies watcher"
    - "Graceful degradation: _apply_watch_config() catches all exceptions (watch config failure does not fail the job)"

key-files:
  created:
    - agent-brain-server/tests/test_watch_integration.py
    - agent-brain-cli/tests/test_folders_watch_flags.py
  modified:
    - agent-brain-server/agent_brain_server/models/job.py
    - agent-brain-server/agent_brain_server/job_queue/job_worker.py
    - agent-brain-server/agent_brain_server/job_queue/job_service.py
    - agent-brain-server/agent_brain_server/api/routers/index.py
    - agent-brain-server/agent_brain_server/api/main.py
    - agent-brain-server/agent_brain_server/services/indexing_service.py
    - agent-brain-cli/agent_brain_cli/client/api_client.py
    - agent-brain-cli/agent_brain_cli/commands/folders.py
    - agent-brain-cli/agent_brain_cli/commands/jobs.py
    - agent-brain-plugin/skills/using-agent-brain/references/api_reference.md
    - agent-brain-plugin/commands/agent-brain-index.md

key-decisions:
  - "watch_mode and watch_debounce_seconds added to JobRecord (not just IndexRequest) so JobWorker can apply config after completion"
  - "Setter injection for FileWatcherService/FolderManager on JobWorker (not constructor) because lifespan creates them in sequence"
  - "_apply_watch_config runs after job DONE — watch config only persisted after successful indexing, never before"
  - "CLI FolderInfo dataclass extended with watch_mode and watch_debounce_seconds (backward-compatible defaults)"

requirements-completed:
  - WATCH-06
  - WATCH-07
  - BGINC-04
  - XCUT-03

# Metrics
duration: 6min
completed: 2026-03-07
---

# Phase 15 Plan 02: CLI and Plugin Integration for Watch Mode Summary

**End-to-end watch_mode flow from CLI --watch auto flag through IndexRequest, JobRecord, JobWorker post-completion hook to FileWatcherService.add_folder_watch(), with folders list Watch column, jobs Source column, and plugin documentation**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-07T03:50:53Z
- **Completed:** 2026-03-07T03:57:21Z
- **Tasks:** 2
- **Files modified:** 13 (11 code + 2 docs)

## Accomplishments

- Added `watch_mode` and `watch_debounce_seconds` fields to `JobRecord` so watch config flows through the job queue
- `enqueue_job()` copies watch fields from `IndexRequest` to `JobRecord`; index router passes them from request body
- `JobWorker._apply_watch_config()` runs after job completes with DONE status: updates `FolderRecord` via `FolderManager.add_folder()` then calls `FileWatcherService.add_folder_watch()` (or `remove_folder_watch()` for mode=off)
- Setter injection: `set_file_watcher_service()` and `set_folder_manager()` called in lifespan after both services are created
- `IndexingService._run_indexing_pipeline()` now passes `include_code` to `folder_manager.add_folder()` (was missing)
- CLI `folders add` accepts `--watch auto/off` and `--debounce N` flags, passed through to `client.index()`
- CLI `folders list` shows `Watch` column (auto in cyan, off in dim) and JSON includes `watch_mode`/`watch_debounce_seconds`
- CLI `jobs` shows `Source` column (manual/auto) in both table and detail views
- Plugin `api_reference.md` documents folder commands, Watch/Source columns, and File Watcher section with debounce/exclusion info
- Plugin `agent-brain-index.md` documents `--watch` and `--debounce` parameters with examples
- 10 new server tests + 6 new CLI tests, all passing; `task before-push` exits 0 (870+142 tests, 78%+59% coverage)

## Task Commits

1. **Task 1: Wire index router, job worker, and CLI** - `cbeda12` (feat)
2. **Task 2: Update plugin docs** - `32fdbf7` (docs)

## Files Created/Modified

- `tests/test_watch_integration.py` -- NEW: 10 tests for JobRecord watch fields and JobWorker._apply_watch_config()
- `tests/test_folders_watch_flags.py` -- NEW: 6 tests for --watch/--debounce flags and folders list Watch column
- `agent_brain_server/models/job.py` -- watch_mode, watch_debounce_seconds fields on JobRecord
- `agent_brain_server/job_queue/job_worker.py` -- _apply_watch_config(), set_file_watcher_service(), set_folder_manager()
- `agent_brain_server/job_queue/job_service.py` -- enqueue_job copies watch fields from request
- `agent_brain_server/api/routers/index.py` -- resolved_request includes watch_mode, watch_debounce_seconds
- `agent_brain_server/api/main.py` -- wires JobWorker to FileWatcherService and FolderManager in both lifespan branches
- `agent_brain_server/services/indexing_service.py` -- passes include_code to folder_manager.add_folder()
- `agent_brain_cli/client/api_client.py` -- index() accepts watch_mode/watch_debounce_seconds, FolderInfo extended
- `agent_brain_cli/commands/folders.py` -- --watch and --debounce flags, Watch column in list
- `agent_brain_cli/commands/jobs.py` -- Source column in table and detail panel
- `api_reference.md` -- folder commands, Watch/Source columns, File Watcher section
- `agent-brain-index.md` -- --watch/--debounce params, examples, notes

## Decisions Made

- watch_mode/watch_debounce_seconds on JobRecord (not just IndexRequest): JobWorker needs these after completion to update FolderRecord and notify FileWatcherService
- Setter injection (not constructor args): JobWorker is created before FileWatcherService in lifespan; setters allow wiring after both exist
- Watch config applied post-completion only: FolderRecord watch fields updated AFTER successful indexing, never before (avoids watching folders with failed indexes)
- _apply_watch_config catches all exceptions: watch config failure should not mark an otherwise successful job as failed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] include_code not passed to folder_manager.add_folder()**
- **Found during:** Task 1 (reviewing IndexingService call)
- **Issue:** `folder_manager.add_folder()` call in `_run_indexing_pipeline()` did not pass `include_code` from the request, so FolderRecord always had `include_code=False`
- **Fix:** Added `include_code=request.include_code` to the call
- **Files modified:** agent-brain-server/agent_brain_server/services/indexing_service.py
- **Committed in:** cbeda12 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (bug)
**Impact on plan:** Required for correctness -- without it, watcher-triggered jobs would never index code files even if the original folder was indexed with `--include-code`.

## Issues Encountered

None -- plan executed cleanly after fixing the include_code bug.

## User Setup Required

None -- all changes are backward-compatible. Existing folders default to watch_mode="off".

## Next Phase Readiness

- Phase 15 is complete (Plans 01 + 02)
- Phase 16 (Embedding Cache) can proceed -- watcher auto-reindex events now flow through the job queue
- No blockers

---
*Phase: 15-file-watcher-and-background-incremental-updates*
*Completed: 2026-03-07*
