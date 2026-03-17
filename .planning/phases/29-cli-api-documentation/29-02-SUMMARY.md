---
phase: 29-cli-api-documentation
plan: 02
subsystem: docs
tags: [api-reference, openapi, fastapi, pydantic, rest-api]

# Dependency graph
requires:
  - phase: none
    provides: none
provides:
  - Accurate API_REFERENCE.md matching all 16 server endpoints
affects: [31-user-guides, 33-cross-references]

# Tech tracking
tech-stack:
  added: []
  patterns: [endpoint-by-endpoint source-to-docs verification]

key-files:
  created: []
  modified:
    - docs/API_REFERENCE.md

key-decisions:
  - "Documented all 16 endpoints including 6 previously undocumented (providers, postgres, folders, cache)"
  - "Fixed similarity_threshold default from 0.7 to 0.3 to match Pydantic model"
  - "Added TypeScript interfaces for all new models (ProvidersStatus, FolderListResponse, etc.)"

patterns-established:
  - "API docs must match router source + Pydantic models exactly"

requirements-completed: [CLIDOC-03]

# Metrics
duration: 6min
completed: 2026-03-17
---

# Phase 29 Plan 02: API Endpoint Documentation Audit Summary

**Audited and fixed API_REFERENCE.md: added 6 missing endpoints (providers, postgres, folders, cache), corrected 14+ field/parameter discrepancies, and aligned all TypeScript interfaces with Pydantic models**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-17T02:04:16Z
- **Completed:** 2026-03-17T02:10:02Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Added 6 previously undocumented endpoints: GET /health/providers, GET /health/postgres, GET /index/folders, DELETE /index/folders, GET /index/cache, DELETE /index/cache
- Fixed similarity_threshold default from 0.7 to 0.3 matching actual Pydantic model
- Added missing query parameters on POST /index (force, allow_external, rebuild_graph) and POST /index/add (force, allow_external)
- Added 11 missing IndexRequest body fields (include_types, force, injector_script, folder_metadata_file, dry_run, watch_mode, watch_debounce_seconds, etc.)
- Added missing QueryRequest fields (entity_types, relationship_types) and QueryResult fields (rerank_score, original_rank)
- Added IndexingStatus fields for queue, file watcher, embedding cache, and query cache status
- Fixed job list query params (limit 1-100, no status filter)
- Added error codes: 409 embedding mismatch, 429 queue full, 503 cache not initialized
- Added TypeScript interfaces for ProvidersStatus, FolderListResponse, FolderDeleteResponse, JobSummary, JobDetailResponse
- Fixed runtime.json path from .claude/agent-brain/ to .agent-brain/

## Task Commits

Each task was committed atomically:

1. **Task 1-2: Extract OpenAPI spec, compare, and fix API_REFERENCE.md** - `775d259` (docs)

## Files Created/Modified
- `docs/API_REFERENCE.md` - Complete API reference with all 16 endpoints documented accurately

## Decisions Made
- Documented all 16 endpoints including 6 previously undocumented ones (providers, postgres health, folder management, cache management)
- Fixed similarity_threshold default from 0.7 to 0.3 to match Pydantic model definition
- Added TypeScript interfaces for all new response models to maintain consistency with existing doc style

## Deviations from Plan

None - plan executed exactly as written. Tasks 1 and 2 were combined into a single commit since Task 1 was analysis-only with no file changes.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- API_REFERENCE.md is now accurate against source code
- Ready for Phase 30 (Configuration Documentation) and Phase 33 (Cross-References)
- All 16 endpoints documented with correct schemas

---
*Phase: 29-cli-api-documentation*
*Completed: 2026-03-17*
