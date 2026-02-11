---
phase: 07-testing-ci
plan: 01
subsystem: testing
tags: [pytest, contract-tests, chromadb, postgres, poetry]

# Dependency graph
requires:
  - phase: 06-postgresql-backend
    provides: PostgreSQL storage backend implementation
provides:
  - Storage backend contract test suite
  - Hybrid search similarity validation
affects: [ci, testing, postgres-backend]

# Tech tracking
tech-stack:
  added: [None]
  patterns:
    - Backend contract fixture parametrization
    - BM25 seeding for Chroma contract tests
    - RRF Jaccard similarity checks

key-files:
  created:
    - agent-brain-server/tests/contract/conftest.py
    - agent-brain-server/tests/contract/test_backend_contract.py
    - agent-brain-server/tests/contract/test_hybrid_search_contract.py
  modified:
    - agent-brain-server/agent_brain_server/storage/vector_store.py
    - agent-brain-server/poetry.lock
    - agent-brain-cli/poetry.lock

key-decisions:
  - "Avoid updating Chroma hnsw:space metadata during embedding metadata writes."

patterns-established:
  - "Contract tests run against both backends with skip logic when PostgreSQL is unavailable."
  - "Hybrid search similarity validated via >=0.6 Jaccard overlap."

# Metrics
completed: 2026-02-11
---

# Phase 7 Plan 1: Testing & CI Summary

**Contract tests now cover all StorageBackendProtocol methods and hybrid search similarity across ChromaDB and PostgreSQL backends.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-02-11T17:58:50Z
- **Completed:** 2026-02-11T18:14:25Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- Added parametrized contract fixtures for ChromaDB/PostgreSQL backends with graceful skips.
- Implemented 14 protocol contract tests covering counts, searches, metadata, and validation.
- Added hybrid search contract coverage with cross-backend similarity checks and Jaccard thresholding.

## Task Commits

Each task was committed atomically:

1. **Task 1: Contract test fixtures with backend parametrization** - `4866f54` (test)
2. **Task 2: Protocol contract tests for all 11 StorageBackendProtocol methods** - `cbbc918` (fix)
3. **Task 3: Hybrid search result similarity contract test** - `45af3fd` (test)

Additional commits:
- `0e96da2` (chore) format contract tests after quality gate
- `34db267` (chore) refresh server and CLI poetry.lock files

## Files Created/Modified
- `agent-brain-server/tests/contract/conftest.py` - backend fixtures for contract suite
- `agent-brain-server/tests/contract/test_backend_contract.py` - protocol-level contract tests
- `agent-brain-server/tests/contract/test_hybrid_search_contract.py` - hybrid search validation and similarity checks
- `agent-brain-server/agent_brain_server/storage/vector_store.py` - avoid invalid metadata updates for ChromaDB
- `agent-brain-server/poetry.lock` - refreshed dependency lock
- `agent-brain-cli/poetry.lock` - refreshed dependency lock

## Decisions Made
- Avoid updating Chroma's `hnsw:space` metadata during embedding metadata writes to prevent invalid collection modify errors.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Chroma metadata update raised invalid distance function errors**
- **Found during:** Task 2 (Protocol contract tests)
- **Issue:** `set_embedding_metadata` attempted to modify `hnsw:space`, which Chroma forbids
- **Fix:** Skip updating `hnsw:space` during metadata updates
- **Files modified:** `agent-brain-server/agent_brain_server/storage/vector_store.py`
- **Verification:** `poetry run pytest tests/contract/test_backend_contract.py -v -k "chroma" --no-header`
- **Committed in:** `cbbc918`

**2. [Rule 3 - Blocking] Poetry lock mismatch blocked `task before-push`**
- **Found during:** Plan verification
- **Issue:** `poetry install` failed due to outdated lock files
- **Fix:** Regenerated server and CLI `poetry.lock` files
- **Files modified:** `agent-brain-server/poetry.lock`, `agent-brain-cli/poetry.lock`
- **Verification:** `task before-push`
- **Committed in:** `34db267`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both fixes were required for correctness and verification; no scope expansion.

## Issues Encountered
- `task before-push` required rebuilding CLI env; resolved by switching CLI venv to Python 3.10 and installing dependencies.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Contract test suite is ready for CI integration.
- PostgreSQL contract tests remain skip-safe when DATABASE_URL is unset.

---
*Phase: 07-testing-ci*
*Completed: 2026-02-11*

## Self-Check: PASSED
