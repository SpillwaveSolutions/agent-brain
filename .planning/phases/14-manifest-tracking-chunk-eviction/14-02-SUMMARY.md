---
phase: 14-manifest-tracking-chunk-eviction
plan: 02
subsystem: indexing
tags: [manifest, eviction, incremental-indexing, bm25, job-worker, cli, integration-tests]

requires:
  - phase: 14-01
    provides: ManifestTracker, ChunkEvictionService, JobRecord.force+eviction_summary

provides:
  - ManifestTracker integration in IndexingService._run_indexing_pipeline
  - Incremental indexing: diff, evict stale chunks, skip unchanged files
  - BM25 incremental rebuild with unchanged file chunks from storage
  - Manifest save after successful pipeline completion
  - Zero-change run early return (status COMPLETED, no upsert calls)
  - JobWorker: force field threaded to IndexRequest, eviction_summary stored on job
  - JobWorker: zero-change incremental run passes verification (not FAILED)
  - JobService: force=request.force propagated to JobRecord
  - api/main.py lifespan: ManifestTracker initialized and passed to IndexingService
  - CLI jobs.py: eviction summary display in job detail panel (EVICT-09)
  - 10 new tests: 5 IndexingService manifest integration, 5 JobWorker eviction

affects:
  - []

tech-stack:
  added: []
  patterns:
    - Lazy import pattern for manifest_tracker inside _run_indexing_pipeline — avoids circular imports
    - dataclasses.asdict() for EvictionSummary -> dict conversion before storing on JobRecord
    - _patch_chunkers context manager in tests — patches ContextAwareChunker to control chunk output

key-files:
  created:
    - agent-brain-server/tests/test_indexing_service_manifest.py
    - agent-brain-server/tests/test_job_worker_eviction.py
  modified:
    - agent-brain-server/agent_brain_server/services/indexing_service.py
    - agent-brain-server/agent_brain_server/job_queue/job_worker.py
    - agent-brain-server/agent_brain_server/job_queue/job_service.py
    - agent-brain-server/agent_brain_server/api/main.py
    - agent-brain-cli/agent_brain_cli/commands/jobs.py

key-decisions:
  - "Return dict[str, Any] | None from _run_indexing_pipeline (dataclasses.asdict of EvictionSummary) — JobWorker can store directly on JobRecord.eviction_summary without importing server dataclasses"
  - "Zero-change early return inside manifest branch returns eviction_summary_result (dict) not None — JobWorker zero-change check reads chunks_to_create from the dict"
  - "_patch_chunkers in tests patches ContextAwareChunker at service module level — _run_indexing_pipeline creates its own ContextAwareChunker internally, so the mock chunker kwarg is bypassed"
  - "BM25 incremental fallback: if storage_backend.bm25_manager is None, use self.bm25_manager directly — handles both ChromaBackend (has bm25_manager) and PostgresBackend (no bm25_manager) cases"
  - "storage.bm25_manager must NOT be set on mock in tests — hasattr() check in IndexingService constructor will pick up None value and override the passed bm25_manager kwarg"

duration: 9min
completed: 2026-03-05
---

# Phase 14 Plan 02: Manifest Tracking & Chunk Eviction Pipeline Wiring Summary

**Full incremental indexing end-to-end: ManifestTracker+ChunkEvictionService wired into IndexingService pipeline, JobWorker force+eviction threading, CLI eviction summary display**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-05T22:16:19Z
- **Completed:** 2026-03-05T22:25:13Z
- **Tasks:** 2/2
- **Files modified:** 7 (2 created, 5 modified)

## Accomplishments

- `IndexingService._run_indexing_pipeline`: integrated manifest diff, chunk eviction, document filtering, BM25 incremental rebuild, manifest save — returns `dict[str, Any] | None` eviction summary
- Zero-change runs: early return path saves manifest and returns COMPLETED without calling upsert
- `JobWorker._process_job`: passes `force=job.force` to `IndexRequest`, captures pipeline return, stores as `job.eviction_summary`
- `JobWorker._verify_collection_delta`: zero-change incremental run (chunks_to_create==0) passes verification
- `JobQueueService.enqueue_job`: propagates `force=request.force` to `JobRecord`
- `api/main.py` lifespan: creates `ManifestTracker` from `storage_paths["manifests"]` or fallback, passes to `IndexingService`
- CLI `jobs.py`: displays eviction summary panel with colored file counts and chunk metrics
- 10 new tests all passing; 829 total (was 819), zero regressions, 77% coverage

## Task Commits

1. **Task 1: Wire manifest tracking into pipeline** — `6f482cb` (feat)
2. **Task 2: CLI eviction summary display and integration tests** — `b32fb92` (feat)
3. **Style fix: ruff lint/import order in test files** — `bf045df` (style)

## Files Created/Modified

- `agent-brain-server/agent_brain_server/services/indexing_service.py` — manifest integration in pipeline, `manifest_tracker` param, return type change
- `agent-brain-server/agent_brain_server/job_queue/job_worker.py` — force field, eviction_summary capture, zero-change verification
- `agent-brain-server/agent_brain_server/job_queue/job_service.py` — `force=request.force` to JobRecord
- `agent-brain-server/agent_brain_server/api/main.py` — ManifestTracker init in lifespan
- `agent-brain-cli/agent_brain_cli/commands/jobs.py` — eviction summary panel in `_create_job_detail_panel`
- `agent-brain-server/tests/test_indexing_service_manifest.py` — 5 integration tests (first-time, incremental, force, deleted, zero-change)
- `agent-brain-server/tests/test_job_worker_eviction.py` — 5 unit tests (zero-change verification, force field, eviction_summary storage)

## Decisions Made

- Return `dict[str, Any] | None` from `_run_indexing_pipeline` — dataclasses.asdict() for Pydantic-friendly serialization
- Zero-change early return returns the eviction dict so JobWorker can detect chunks_to_create==0
- `_patch_chunkers` test helper patches ContextAwareChunker at pipeline level — internal chunker creation bypasses constructor kwarg
- BM25 incremental fallback handles both storage backends (chroma has bm25_manager, postgres does not)
- Mock storage backend in tests must NOT have `bm25_manager` attribute to avoid overriding passed kwarg

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] storage.bm25_manager = None causes AttributeError in tests**
- **Found during:** Task 2 test execution
- **Issue:** Setting `storage.bm25_manager = None` on the AsyncMock causes `hasattr()` to return True, making `self.bm25_manager = None` in the constructor, leading to `AttributeError: 'NoneType' object has no attribute 'build_index'` during BM25 rebuild
- **Fix:** Removed `storage.bm25_manager = None` from mock — when hasattr returns False, constructor uses the explicitly passed `bm25_manager` kwarg
- **Files modified:** tests/test_indexing_service_manifest.py
- **Committed in:** Task 2 (b32fb92) after fix

**2. [Rule 1 - Bug] ContextAwareChunker created internally bypasses mock**
- **Found during:** Task 2 test execution (chunk IDs didn't match expected values)
- **Issue:** `_run_indexing_pipeline` creates its own `ContextAwareChunker` instance internally, bypassing the mock `chunker` kwarg. Real chunks with generated IDs were produced.
- **Fix:** Added `_patch_chunkers()` context manager that patches `ContextAwareChunker` at the service module level, returning the test's mock chunks
- **Files modified:** tests/test_indexing_service_manifest.py
- **Committed in:** Task 2 (b32fb92)

**3. [Rule 1 - Bug] Ruff import sort and lint issues in test files**
- **Found during:** Final quality gate (`poetry run ruff check agent_brain_server tests`)
- **Issue:** I001 (import sort), F401 (unused import), F841 (unused variable), E501 (line too long) — some in new files, some in pre-existing Phase 14 Plan 01 files
- **Fix:** Applied `ruff --fix`, manually removed unused variable, shortened docstring line
- **Files modified:** tests/test_chunk_eviction_service.py, tests/test_manifest_tracker.py, tests/test_indexing_service_manifest.py, tests/test_job_worker_eviction.py
- **Committed in:** bf045df (style)

---

**Total deviations:** 3 auto-fixed (all Rule 1 — correctness/quality fixes)
**Impact on plan:** All fixes necessary. No scope creep.

## Issues Encountered

None blocking — all deviations resolved inline.

## User Setup Required

None — no external service configuration required.

## Phase 14 Completion

Phase 14 is now complete:

| Plan | Status | Key Deliverable |
|------|--------|-----------------|
| 14-01 | Complete | ManifestTracker, ChunkEvictionService, storage_paths, JobRecord fields |
| 14-02 | Complete | Pipeline wiring, JobWorker threading, CLI display, integration tests |

**EVICT requirements satisfied:**
- EVICT-01..05: ManifestTracker + ChunkEvictionService (Plan 01)
- EVICT-06: manifests subdirectory in storage_paths (Plan 01)
- EVICT-07: bulk eviction via delete_by_ids (Plan 01)
- EVICT-08: force bypass via force=True (Plan 01 model + Plan 02 wiring)
- EVICT-09: CLI eviction summary display (Plan 02)

**v7.0 milestone:** Phase 14 closes the Index Management milestone.

---
*Phase: 14-manifest-tracking-chunk-eviction*
*Completed: 2026-03-05*

## Self-Check: PASSED

| Item | Status |
|------|--------|
| agent-brain-server/agent_brain_server/services/indexing_service.py | FOUND |
| agent-brain-server/agent_brain_server/job_queue/job_worker.py | FOUND |
| agent-brain-server/agent_brain_server/job_queue/job_service.py | FOUND |
| agent-brain-server/agent_brain_server/api/main.py | FOUND |
| agent-brain-cli/agent_brain_cli/commands/jobs.py | FOUND |
| agent-brain-server/tests/test_indexing_service_manifest.py | FOUND |
| agent-brain-server/tests/test_job_worker_eviction.py | FOUND |
| Commit 6f482cb (Task 1) | FOUND |
| Commit b32fb92 (Task 2) | FOUND |
| Commit bf045df (style fix) | FOUND |
