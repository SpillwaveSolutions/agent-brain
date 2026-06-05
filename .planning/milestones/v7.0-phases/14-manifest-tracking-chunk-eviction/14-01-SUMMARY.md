---
phase: 14-manifest-tracking-chunk-eviction
plan: 01
subsystem: indexing
tags: [manifest, eviction, incremental-indexing, sha256, async, chromadb, postgres]

requires:
  - phase: 12-folder-management
    provides: FolderManager atomic write pattern, delete_by_ids on StorageBackendProtocol
  - phase: 13-content-injection-pipeline
    provides: ContentInjector dependency injection patterns

provides:
  - ManifestTracker with async load/save/delete and atomic writes
  - FileRecord, FolderManifest, EvictionSummary dataclasses
  - compute_file_checksum (SHA-256 streaming, 64KB chunks)
  - ChunkEvictionService with compute_diff_and_evict (force/no-manifest/normal modes)
  - manifests subdirectory in storage_paths (EVICT-06)
  - JobRecord.force field for force-mode plumbing (EVICT-08)
  - JobRecord.eviction_summary and JobDetailResponse.eviction_summary (EVICT-09)
  - 26 unit tests covering all diff/eviction/checksum scenarios

affects:
  - 14-02 (indexing pipeline wiring — will consume ManifestTracker, ChunkEvictionService)

tech-stack:
  added: []
  patterns:
    - ManifestTracker mirrors FolderManager async/lock/atomic-write pattern from Phase 12
    - TYPE_CHECKING import for StorageBackendProtocol avoids circular imports (same as ContentInjector)
    - mtime fast-path + SHA-256 checksum for changed-file detection (O(delta) not O(N))
    - Bulk eviction — collect all stale chunk IDs, single delete_by_ids call

key-files:
  created:
    - agent-brain-server/agent_brain_server/services/manifest_tracker.py
    - agent-brain-server/agent_brain_server/services/chunk_eviction_service.py
    - agent-brain-server/tests/test_manifest_tracker.py
    - agent-brain-server/tests/test_chunk_eviction_service.py
  modified:
    - agent-brain-server/agent_brain_server/services/__init__.py
    - agent-brain-server/agent_brain_server/storage_paths.py
    - agent-brain-server/agent_brain_server/models/job.py
    - agent-brain-server/tests/unit/test_storage_paths.py

key-decisions:
  - "ManifestTracker stores one JSON file per folder at state_dir/manifests/<sha256(folder_path)>.json — mirrors FolderManager pattern, flat directory, no path-separator issues"
  - "mtime equality as fast-path: if mtime unchanged, skip SHA-256 (O(1)); only compute checksum when mtime changes — handles ~95% of unchanged files cheaply"
  - "ChunkEvictionService uses _compute_incremental_diff as private helper — force and no-manifest paths are factored out for clarity"
  - "TYPE_CHECKING import for StorageBackendProtocol in chunk_eviction_service.py — avoids circular import, same pattern as ContentInjector in Phase 13"
  - "eviction_summary stored as dict[str, Any] on JobRecord (not dataclass) — Pydantic serialization friendly, CLI can display it without server package dep"

patterns-established:
  - "ManifestTracker: async save/load/delete with asyncio.Lock and asyncio.to_thread for all file IO — consistent with FolderManager"
  - "Bulk eviction: collect all IDs from deleted+changed files first, then single delete_by_ids call — avoids N storage calls"
  - "Force mode: load manifest, collect all prior chunk IDs, delete, delete manifest, return all files — complete reset"

duration: 5min
completed: 2026-03-05
---

# Phase 14 Plan 01: Manifest Tracking & Chunk Eviction Foundation Summary

**ManifestTracker (per-folder JSON manifests with atomic writes) and ChunkEvictionService (mtime+SHA-256 diff, bulk chunk eviction) providing the change-detection infrastructure for incremental indexing**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-05T22:07:49Z
- **Completed:** 2026-03-05T22:12:58Z
- **Tasks:** 2/2
- **Files modified:** 8 (4 created, 4 modified)

## Accomplishments

- ManifestTracker: async per-folder JSON manifests with atomic temp+replace writes, SHA-256-keyed paths, asyncio.Lock concurrency safety
- ChunkEvictionService: three-mode diff (force / no-manifest / normal), mtime fast-path + SHA-256 verification, bulk eviction via single `delete_by_ids` call
- storage_paths extended with `manifests` subdirectory (EVICT-06); JobRecord extended with `force` (EVICT-08) and `eviction_summary` (EVICT-09)
- 26 unit tests all passing; full test suite 819 passed, zero regressions

## Task Commits

1. **Task 1: Create ManifestTracker and ChunkEvictionService** — `447fc1c` (feat)
2. **Task 2: Extend storage_paths, JobRecord, unit tests** — `1caf26b` (feat)

## Files Created/Modified

- `agent-brain-server/agent_brain_server/services/manifest_tracker.py` — ManifestTracker, FileRecord, FolderManifest, EvictionSummary, compute_file_checksum (220 lines)
- `agent-brain-server/agent_brain_server/services/chunk_eviction_service.py` — ChunkEvictionService with force/no-manifest/normal diff modes (220 lines)
- `agent-brain-server/agent_brain_server/services/__init__.py` — updated exports for all new symbols
- `agent-brain-server/agent_brain_server/storage_paths.py` — added `manifests` to SUBDIRECTORIES and resolve_storage_paths()
- `agent-brain-server/agent_brain_server/models/job.py` — added `force` and `eviction_summary` to JobRecord; added `eviction_summary` to JobDetailResponse.from_record()
- `agent-brain-server/tests/test_manifest_tracker.py` — 16 unit tests (round-trip, delete, SHA-256 path, checksum, atomic write, multi-manifest)
- `agent-brain-server/tests/test_chunk_eviction_service.py` — 10 unit tests (no-manifest, no-changes, deleted, changed, force, mtime+same-checksum, mixed, empty, no-eviction)
- `agent-brain-server/tests/unit/test_storage_paths.py` — updated expected_keys set to include `manifests`

## Decisions Made

- ManifestTracker uses SHA-256 of folder path string as manifest filename — flat directory, no path-separator issues across OS
- mtime equality as O(1) fast-path before computing SHA-256 — handles ~95% of unchanged files without disk read
- TYPE_CHECKING import for StorageBackendProtocol — avoids circular import, consistent with ContentInjector pattern from Phase 13
- `eviction_summary` stored as `dict[str, Any]` not dataclass on JobRecord — Pydantic serialization friendly for API response

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff UP037 quoted type annotations in chunk_eviction_service.py**
- **Found during:** Task 2 verification (ruff check)
- **Issue:** Two string-quoted type annotations (`"StorageBackendProtocol"`, `"object"`) flagged by ruff UP037. With `from __future__ import annotations`, quotes are redundant.
- **Fix:** Removed quotes from both annotations; ran `black` to reformat both affected files
- **Files modified:** agent-brain-server/agent_brain_server/services/chunk_eviction_service.py, agent-brain-server/agent_brain_server/models/job.py
- **Verification:** `poetry run ruff check` passes; `poetry run black --check` passes
- **Committed in:** 1caf26b (Task 2 commit)

**2. [Rule 1 - Bug] Updated test_storage_paths.py expected keys set**
- **Found during:** Task 2 full test suite run
- **Issue:** `tests/unit/test_storage_paths.py::test_returns_expected_keys` failed because it hardcoded the old set of keys, missing `manifests`
- **Fix:** Added `"manifests"` to the `expected_keys` set in the test
- **Files modified:** agent-brain-server/tests/unit/test_storage_paths.py
- **Verification:** `poetry run pytest tests/unit/test_storage_paths.py` — 9 passed
- **Committed in:** 1caf26b (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — correctness fixes)
**Impact on plan:** Both auto-fixes necessary for code quality and test correctness. No scope creep.

## Issues Encountered

None — implementation followed the research patterns exactly.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- ManifestTracker and ChunkEvictionService are importable from `agent_brain_server.services`
- All mypy strict, ruff, and black checks pass
- Plan 02 can wire these services into `IndexingService._run_indexing_pipeline()` — integration point clearly defined in RESEARCH.md Pattern 5
- JobRecord.force field ready for JobWorker to consume (Pattern 7 in RESEARCH.md)

---
*Phase: 14-manifest-tracking-chunk-eviction*
*Completed: 2026-03-05*

## Self-Check: PASSED

All files present and all commits verified:

| Item | Status |
|------|--------|
| agent-brain-server/agent_brain_server/services/manifest_tracker.py | FOUND |
| agent-brain-server/agent_brain_server/services/chunk_eviction_service.py | FOUND |
| agent-brain-server/tests/test_manifest_tracker.py | FOUND |
| agent-brain-server/tests/test_chunk_eviction_service.py | FOUND |
| .planning/phases/14-manifest-tracking-chunk-eviction/14-01-SUMMARY.md | FOUND |
| Commit 447fc1c (Task 1) | FOUND |
| Commit 1caf26b (Task 2) | FOUND |
