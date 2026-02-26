---
phase: 12-folder-management-file-type-presets
plan: 02
subsystem: api
tags: [fastapi, folder-management, file-type-presets, storage-protocol, chromadb, postgres]

# Dependency graph
requires:
  - phase: 12-01
    provides: FolderManager, FolderRecord, FolderInfo/FolderListResponse/FolderDeleteRequest/FolderDeleteResponse models, delete_by_metadata on StorageBackendProtocol

provides:
  - GET /index/folders — list indexed folders with chunk_count and last_indexed
  - DELETE /index/folders — remove folder chunks from vector store, 409 on active job
  - FolderManager wired into server lifespan (app.state.folder_manager)
  - IndexingService registers folders with FolderManager after successful indexing
  - IndexRequest.include_types field — file type preset resolution to glob patterns
  - delete_by_ids on StorageBackendProtocol (ChromaDB + PostgreSQL + VectorStoreManager)

affects: [12-03, index-router, job-queue, storage-backends]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Folders router accesses app.state.folder_manager, app.state.job_service, app.state.storage_backend via request.app.state"
    - "FOLD-07 active-job guard: check stats.running > 0, then get_running_job() for targeted path comparison"
    - "delete_by_ids protocol method with empty-ID guard (empty list returns 0 immediately)"
    - "include_types resolved to glob patterns in IndexingService._run_indexing_pipeline before load_files"
    - "FolderManager initialized in lifespan with state_dir or temp dir fallback"

key-files:
  created:
    - agent-brain-server/agent_brain_server/api/routers/folders.py
    - agent-brain-server/tests/test_folders_api.py
    - agent-brain-server/tests/test_include_types.py
  modified:
    - agent-brain-server/agent_brain_server/api/routers/__init__.py
    - agent-brain-server/agent_brain_server/api/main.py
    - agent-brain-server/agent_brain_server/models/index.py
    - agent-brain-server/agent_brain_server/services/indexing_service.py
    - agent-brain-server/agent_brain_server/storage/protocol.py
    - agent-brain-server/agent_brain_server/storage/chroma/backend.py
    - agent-brain-server/agent_brain_server/storage/postgres/backend.py
    - agent-brain-server/agent_brain_server/storage/vector_store.py
    - agent-brain-server/tests/unit/storage/test_protocol.py

key-decisions:
  - "Added delete_by_ids to StorageBackendProtocol (Rule 2 — missing critical functionality): chunk_ids are canonical; without targeted ID-based deletion, folder removal could only fall back to metadata filtering which requires folder_path in chunk metadata (not stored)"
  - "FOLD-07 check uses job_service.store.get_running_job() not list_jobs(status=running) for efficient single-job lookup"
  - "FolderManager uses temp dir fallback when no state_dir configured (backward compat with single-instance mode)"
  - "include_types resolution happens in IndexingService._run_indexing_pipeline not at router level — keeps router thin"
  - "get_status() uses FolderManager.list_folders() when available for persistence across restarts"

patterns-established:
  - "Protocol extensions: add method to protocol.py → implement in both chroma/backend.py and postgres/backend.py → add to MockCompleteBackend in test_protocol.py"
  - "Folder removal pattern: check active jobs → get folder record → delete chunks by IDs → remove folder record"

# Metrics
duration: 55min
completed: 2026-02-24
---

# Phase 12 Plan 02: Folders API and include_types Summary

**REST folder management API (GET/DELETE /index/folders) with FolderManager wired into server lifespan and IndexingService, plus include_types preset resolution on IndexRequest**

## Performance

- **Duration:** ~55 min
- **Started:** 2026-02-24T02:00:00Z
- **Completed:** 2026-02-24T02:55:00Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments

- Created `GET /index/folders` and `DELETE /index/folders` REST endpoints in new `api/routers/folders.py`
- Wired FolderManager into server lifespan (`app.state.folder_manager`) with project state dir and temp dir fallback
- IndexingService now calls `folder_manager.add_folder()` after every successful indexing, enabling persistent cross-restart folder tracking
- Added `include_types: list[str] | None` to IndexRequest with preset resolution in IndexingService pipeline
- Added `delete_by_ids` to `StorageBackendProtocol` with ChromaDB (`VectorStoreManager.delete_by_ids`) and PostgreSQL implementations
- 31 new tests passing, all 756 tests green, mypy strict clean, ruff clean, black clean

## Task Commits

Each task was committed atomically:

1. **Tasks 1 + 2: Folders API router + IndexingService integration** - `0289adc` (feat)

## Files Created/Modified

- `agent-brain-server/agent_brain_server/api/routers/folders.py` — New router: GET / list, DELETE / remove with FOLD-07 active job check
- `agent-brain-server/agent_brain_server/api/routers/__init__.py` — Added folders_router export
- `agent-brain-server/agent_brain_server/api/main.py` — FolderManager init in lifespan, folders_router registered at /index/folders
- `agent-brain-server/agent_brain_server/models/index.py` — Added include_types field to IndexRequest
- `agent-brain-server/agent_brain_server/services/indexing_service.py` — folder_manager param, add_folder after indexing, clear() in reset, list_folders() in get_status, include_types resolution
- `agent-brain-server/agent_brain_server/storage/protocol.py` — Added delete_by_ids to StorageBackendProtocol
- `agent-brain-server/agent_brain_server/storage/chroma/backend.py` — Implemented delete_by_ids delegating to VectorStoreManager
- `agent-brain-server/agent_brain_server/storage/postgres/backend.py` — Implemented delete_by_ids with ANY(CAST(:ids AS text[]))
- `agent-brain-server/agent_brain_server/storage/vector_store.py` — Added VectorStoreManager.delete_by_ids with empty-ID guard
- `agent-brain-server/tests/test_folders_api.py` — 16 tests for GET/DELETE /index/folders endpoints
- `agent-brain-server/tests/test_include_types.py` — 15 tests for include_types model, resolution, and combination logic
- `agent-brain-server/tests/unit/storage/test_protocol.py` — Added delete_by_ids to MockCompleteBackend

## Decisions Made

1. **Added `delete_by_ids` to StorageBackendProtocol** (Rule 2 — missing critical functionality): The plan called for "delete by chunk IDs" as the preferred path, but the protocol only had `delete_by_metadata`. Since chunk metadata stores individual file paths (not folder paths), metadata filtering alone cannot target all chunks for a folder accurately. Targeted ID-based deletion is required for correctness.

2. **FOLD-07 check uses `job_service.store.get_running_job()`** (not `list_jobs`): More efficient — single O(N) scan of in-memory job dict vs fetching and mapping all jobs. Also avoids importing `JobStatus` in the router.

3. **FolderManager uses temp dir fallback**: When `state_dir` is None (single-instance mode without `--state-dir`), FolderManager initializes in a temp directory. This maintains backward compatibility while allowing the API endpoints to function.

4. **include_types resolution in IndexingService, not router**: Keeps the router thin; IndexingService owns the indexing pipeline logic.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added delete_by_ids to StorageBackendProtocol**
- **Found during:** Task 1 (Create folders API router)
- **Issue:** Plan specified "delete by chunk IDs" for precise folder chunk removal, but `StorageBackendProtocol` only had `delete_by_metadata`. Chunk metadata stores file-level paths, not folder paths, so metadata filtering alone is unreliable for folder-scoped deletion.
- **Fix:** Added `delete_by_ids(ids: list[str]) -> int` to protocol with empty-ID guard. Implemented in ChromaDB backend (via `VectorStoreManager.delete_by_ids`), PostgreSQL backend (parameterized DELETE with ANY clause), and MockCompleteBackend in tests.
- **Files modified:** `storage/protocol.py`, `storage/chroma/backend.py`, `storage/postgres/backend.py`, `storage/vector_store.py`, `tests/unit/storage/test_protocol.py`
- **Verification:** All 756 tests pass, protocol compliance test passes
- **Committed in:** 0289adc

---

**Total deviations:** 1 auto-fixed (Rule 2 — missing critical functionality)
**Impact on plan:** Necessary for correct operation. Targeted chunk deletion requires IDs, not metadata filtering. No scope creep.

## Issues Encountered

- **Test helper bug**: `_make_record(chunk_ids=[])` evaluated `[] or ["chunk1", "chunk2"]` as `["chunk1", "chunk2"]` due to Python falsy semantics. Fixed by using `chunk_ids if chunk_ids is not None else [...]` pattern.

## Self-Check

### Files Created/Exist

- `agent-brain-server/agent_brain_server/api/routers/folders.py` — FOUND
- `agent-brain-server/tests/test_folders_api.py` — FOUND
- `agent-brain-server/tests/test_include_types.py` — FOUND

### Commits Exist

- `0289adc` — feat(12-02): wire FolderManager and folders API into server — FOUND

### Test Results

- 756 tests pass, 23 skipped
- mypy strict: no issues in 71 source files
- ruff: all checks passed
- black: all files formatted

## Self-Check: PASSED

## Next Phase Readiness

- REST API layer complete for folder management (Plan 02 done)
- Plan 03 can now add CLI commands (`agent-brain folders`, `agent-brain folders remove`) and plugin hooks that call GET/DELETE /index/folders
- `include_types` is wired into IndexRequest — Plan 03 CLI can expose `--include-types` flag

---
*Phase: 12-folder-management-file-type-presets*
*Completed: 2026-02-24*
