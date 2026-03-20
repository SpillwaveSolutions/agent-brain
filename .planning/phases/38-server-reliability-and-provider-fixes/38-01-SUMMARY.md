---
phase: 38-server-reliability-and-provider-fixes
plan: 01
subsystem: infra
tags: [storage-paths, chromadb, telemetry, tests]

requires:
  - phase: 37-complete-link-verification-audit-metadata
    provides: documentation baseline and verified planning context
provides:
  - State-dir-aware fallback path resolution for ChromaDB, BM25, and embedding cache
  - Lifespan telemetry suppression for ChromaDB/PostHog startup noise
  - Regression tests asserting storage paths are absolute and rooted in state_dir
affects: [server-startup, storage-initialization, logging]

tech-stack:
  added: []
  patterns:
    - state_dir-first storage path fallback in lifespan
    - startup-time telemetry suppression via env + logger levels

key-files:
  created:
    - .planning/phases/38-server-reliability-and-provider-fixes/deferred-items.md
  modified:
    - agent-brain-server/agent_brain_server/api/main.py
    - agent-brain-server/tests/unit/test_storage_paths.py

key-decisions:
  - "Keep settings defaults unchanged and fix path behavior in lifespan fallback logic only."
  - "Apply telemetry suppression in lifespan with setdefault + logger level reduction to avoid overriding explicit user settings."

patterns-established:
  - "Fallback path rule: prefer storage_paths, then state_dir/data, then absolute-resolved settings path."

requirements-completed: []

duration: 1 min
completed: 2026-03-20
---

# Phase 38 Plan 01: CWD paths and telemetry summary

**Server startup now resolves ChromaDB/BM25/cache paths under state directories instead of CWD-relative defaults, and suppresses ChromaDB telemetry log noise.**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-20T00:58:26Z
- **Completed:** 2026-03-20T00:59:33Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added fallback state-dir resolution in `lifespan()` for direct server runs without explicit `AGENT_BRAIN_STATE_DIR`.
- Replaced CWD-relative fallback behavior for Chroma/BM25 and embedding cache with state-dir-aware path resolution.
- Added startup telemetry suppression and regression tests proving storage paths are absolute and under `state_dir`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix CWD-relative chroma_db and cache fallback paths** - `476ff6d` (fix)
2. **Task 2: Suppress ChromaDB PostHog telemetry errors + add CWD path test** - `41e1bec` (fix)

## Files Created/Modified
- `agent-brain-server/agent_brain_server/api/main.py` - state-dir-aware fallback paths and telemetry suppression in lifespan startup.
- `agent-brain-server/tests/unit/test_storage_paths.py` - regression tests for absolute storage paths and chroma/cache location guarantees.
- `.planning/phases/38-server-reliability-and-provider-fixes/deferred-items.md` - out-of-scope pre-existing verification blocker log.

## Decisions Made
- Kept `CHROMA_PERSIST_DIR` and `BM25_INDEX_PATH` defaults unchanged in settings and fixed behavior in runtime resolution path only.
- Used `os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")` plus logger level controls to reduce startup noise without forcing overrides.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Task 1 verification import command failed due a pre-existing Gemini provider import issue (`google.genai` dependency state), logged to `deferred-items.md` and treated as out-of-scope for this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 38 plan 01 deliverables are complete and verified via unit tests/grep checks.
- Ready for `38-02-PLAN.md`.

---
*Phase: 38-server-reliability-and-provider-fixes*
*Completed: 2026-03-20*

## Self-Check: PASSED
