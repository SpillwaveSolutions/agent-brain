---
phase: 13-content-injection-pipeline
plan: 01
subsystem: indexing
tags: [content-injection, importlib, metadata-enrichment, chromadb, fastapi, pydantic, dry-run]

# Dependency graph
requires:
  - phase: 12-folder-management
    provides: FolderManager, JobRecord model, IndexRequest model, pipeline architecture
provides:
  - ContentInjector service with script loading, folder metadata merging, scalar validation
  - IndexRequest.injector_script, IndexRequest.folder_metadata_file, IndexRequest.dry_run fields
  - JobRecord.injector_script, JobRecord.folder_metadata_file fields
  - _run_indexing_pipeline content_injector parameter (Step 2.5)
  - JobWorker wiring: builds ContentInjector from JobRecord, passes to pipeline
  - JobService.enqueue_job passes injection fields through to JobRecord
  - API path validation for injector_script and folder_metadata_file
  - dry_run mode: validate injector against sample chunks without enqueueing
  - 28 unit + integration tests for injection pipeline
affects:
  - 13-content-injection-pipeline (plans 02+)
  - pipeline tests referencing _run_indexing_pipeline signature

# Tech tracking
tech-stack:
  added: []
  patterns:
    - ContentInjector factory pattern (build() returns None when no injection needed)
    - Per-chunk exception handling (catch + warn, never crash pipeline)
    - TYPE_CHECKING guard for ContentInjector import in indexing_service.py
    - apply_to_chunks only writes to chunk.metadata.extra for non-schema keys
    - Lazy import of ContentInjector in JobWorker to avoid circular imports

key-files:
  created:
    - agent-brain-server/agent_brain_server/services/content_injector.py
    - agent-brain-server/tests/test_content_injector.py
    - agent-brain-server/tests/test_injection_pipeline.py
  modified:
    - agent-brain-server/agent_brain_server/models/index.py
    - agent-brain-server/agent_brain_server/models/job.py
    - agent-brain-server/agent_brain_server/services/indexing_service.py
    - agent-brain-server/agent_brain_server/job_queue/job_worker.py
    - agent-brain-server/agent_brain_server/job_queue/job_service.py
    - agent-brain-server/agent_brain_server/api/routers/index.py

key-decisions:
  - "ContentInjector.build() returns None when both paths are None — no-op when injection not configured"
  - "apply_to_chunks writes only to chunk.metadata.extra for keys NOT in known_keys set — prevents injectors overwriting schema fields"
  - "Per-chunk exceptions caught and logged with warning, pipeline continues (INJECT-05 resilience)"
  - "Non-scalar metadata values (list, dict) stripped with warning for ChromaDB compatibility (INJECT-06)"
  - "Lazy import ContentInjector in JobWorker via local import inside conditional block — avoids circular import"
  - "TYPE_CHECKING guard for ContentInjector in indexing_service.py — clean dependency direction"
  - "dry_run returns HTTP 202 (same as endpoint declared status) with job_id='dry_run'"
  - "JobService.enqueue_job must explicitly pass injector_script and folder_metadata_file to JobRecord constructor — Pydantic does not auto-propagate"

patterns-established:
  - "Injection step is Step 2.5 in pipeline: after chunking, before embedding — enriched fields present when stored in ChromaDB"
  - "ContentInjector is parameter, not singleton mutation — clean dependency injection, testable, backward compatible"
  - "All injection metadata stored in chunk.metadata.extra dict, surfaced via to_dict() which calls data.update(self.extra)"

# Metrics
duration: 9min
completed: 2026-03-05
---

# Phase 13 Plan 01: Content Injection Pipeline Summary

**ContentInjector service with importlib-based script loading, JSON folder metadata merging, scalar validation, pipeline integration (Step 2.5), job worker wiring, API path validation, and dry-run endpoint**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-05T21:05:59Z
- **Completed:** 2026-03-05T21:15:00Z
- **Tasks:** 2/2
- **Files modified:** 9 (4 created, 5 modified)

## Accomplishments

- ContentInjector service: loads Python scripts via importlib, merges static JSON folder metadata, handles per-chunk exceptions (INJECT-05), validates and strips non-scalar values for ChromaDB compatibility (INJECT-06)
- Extended IndexRequest (injector_script, folder_metadata_file, dry_run) and JobRecord (injector_script, folder_metadata_file) — full round-trip from API to pipeline
- Integrated injection as Step 2.5 in _run_indexing_pipeline (after chunking, before embedding) so enriched metadata is stored in ChromaDB
- JobWorker builds ContentInjector from JobRecord fields; JobService passes injection fields through to JobRecord constructor
- API validates injector_script (must exist, must be .py) and folder_metadata_file (must exist) before enqueueing
- dry_run mode: samples up to 3 files/10 chunks, applies injector, returns enrichment report without creating a job
- 28 injection tests (19 unit + 9 integration); 793 total tests pass with zero regressions; task before-push clean

## Task Commits

Each task was committed atomically:

1. **Task 1: ContentInjector service and extend models** - `9842acf` (feat)
2. **Task 2: Integrate into pipeline, job worker, and API router** - `4bd9ae3` (feat)

## Files Created/Modified

- `agent-brain-server/agent_brain_server/services/content_injector.py` - ContentInjector class (script loading, metadata merging, apply, apply_to_chunks, build factory)
- `agent-brain-server/tests/test_content_injector.py` - 19 unit tests for ContentInjector
- `agent-brain-server/tests/test_injection_pipeline.py` - 9 integration tests for pipeline, job worker, API router
- `agent-brain-server/agent_brain_server/models/index.py` - Added injector_script, folder_metadata_file, dry_run fields to IndexRequest
- `agent-brain-server/agent_brain_server/models/job.py` - Added injector_script, folder_metadata_file fields to JobRecord
- `agent-brain-server/agent_brain_server/services/indexing_service.py` - Added content_injector parameter to _run_indexing_pipeline (Step 2.5)
- `agent-brain-server/agent_brain_server/job_queue/job_worker.py` - Build ContentInjector from JobRecord, pass to pipeline; include injection fields in IndexRequest
- `agent-brain-server/agent_brain_server/job_queue/job_service.py` - Pass injector_script and folder_metadata_file to JobRecord constructor
- `agent-brain-server/agent_brain_server/api/routers/index.py` - Path validation for injection fields, dry_run handler, _handle_dry_run helper function

## Decisions Made

- ContentInjector.build() returns None when both paths are None — no ContentInjector overhead when injection not configured
- apply_to_chunks writes only to chunk.metadata.extra for keys NOT in known_keys set — prevents injectors from accidentally overwriting core schema fields (chunk_id, source, etc.)
- Per-chunk exceptions caught and logged with warning; pipeline continues without crashing (INJECT-05)
- Non-scalar metadata values (list, dict) stripped with warning for ChromaDB compatibility (INJECT-06)
- Lazy import ContentInjector in JobWorker via local import inside conditional block — avoids circular import
- JobService.enqueue_job must explicitly pass injector_script and folder_metadata_file to JobRecord constructor — Pydantic does not auto-propagate fields
- dry_run returns HTTP 202 (same status code as normal enqueue) with job_id="dry_run", status="completed"

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- `mypy` flagged unused `# type: ignore[union-attr]` comment after Python 3.10 type narrowing correctly inferred spec.loader — removed comment.
- `ruff` flagged: `getattr(module, "process_chunk")` replaced with `module.process_chunk`; quoted return types in classmethods upgraded to bare types (from __future__ import annotations active); line too long in description string fixed.
- Dry-run tests initially asserted HTTP 200, but the endpoint's declared `status_code=HTTP_202_ACCEPTED` produces 202 — updated assertions to match actual behavior.

## Self-Check: PASSED

All files found on disk. All commits exist in git history.

## User Setup Required

None — no external service configuration required. Injection feature is opt-in via IndexRequest fields.

## Next Phase Readiness

- ContentInjector service is complete and integrated into the full pipeline (API → JobRecord → JobWorker → IndexingService)
- Ready for Phase 13 Plan 02 (CLI injection flags: --injector-script, --folder-metadata-file, --dry-run)
- ChunkMetadata.extra dict confirmed to surface through to_dict() → ChromaDB storage (verified in tests)
