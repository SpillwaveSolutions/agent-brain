---
phase: 09-runtime-backend-wiring
plan: 01
subsystem: server-lifecycle
tags:
  - backend-wiring
  - conditional-init
  - graph-validation
  - health-status
dependency_graph:
  requires:
    - 05-01 (StorageBackendProtocol)
    - 05-02 (ChromaBackend adapter)
    - 06-01 (PostgreSQL foundation)
    - 06-02 (PostgreSQL operations)
    - 06-03 (PostgreSQL integration)
  provides:
    - Factory-driven service initialization
    - Backend-conditional ChromaDB init
    - Graph query backend validation
  affects:
    - main.py (lifespan function)
    - query_service.py (graph query validation)
    - health.py (backend-aware status)
tech_stack:
  added: []
  patterns:
    - Conditional initialization based on backend_type
    - Backend compatibility validation in query methods
    - Graceful degradation in multi-mode queries
key_files:
  created: []
  modified:
    - agent-brain-server/agent_brain_server/api/main.py
    - agent-brain-server/agent_brain_server/services/query_service.py
    - agent-brain-server/agent_brain_server/api/routers/health.py
    - agent-brain-plugin/commands/agent-brain-graph.md
    - agent-brain-plugin/commands/agent-brain-multi.md
decisions:
  - summary: "Conditional ChromaDB initialization wrapped in backend_type check"
    rationale: "Avoid creating ChromaDB directories and BM25 indexes when using postgres backend"
    alternatives: []
  - summary: "Graph queries raise ValueError on postgres, multi-mode gracefully skips"
    rationale: "Graph is ChromaDB-only (stores in SimplePropertyGraphStore). Explicit error for graph-only mode, graceful degradation for multi-mode"
    alternatives: []
  - summary: "Health endpoints use getattr() for vector_store to handle None safely"
    rationale: "vector_store is None when backend is postgres, must handle both cases"
    alternatives: []
metrics:
  duration_minutes: 4
  tasks_completed: 3
  files_modified: 5
  commits: 4
  tests_passed: 670
  completed_date: 2026-02-13
---

# Phase 09 Plan 01: Runtime Backend Wiring Summary

**One-liner:** Rewired main.py lifespan to pass factory-selected storage backend to services, conditionally skip ChromaDB/BM25 initialization on postgres, added graph query validation, and updated plugin docs.

## What Was Built

Closed the v6.0 audit gap where factory selected the backend but services always received ChromaDB via legacy parameters. Now:

1. **main.py lifespan** conditionally initializes ChromaDB components only when `backend_type == "chroma"`
2. **Services receive storage_backend** from factory (not legacy vector_store/bm25_manager parameters)
3. **Graph queries validate backend** before execution (raise ValueError on postgres)
4. **Multi-mode gracefully degrades** (skips graph on postgres, logs info message)
5. **Health endpoints** show graph as unavailable on postgres backend
6. **Plugin documentation** updated with backend requirements and postgres-specific guidance

## Implementation Details

### Task 1: Rewire main.py lifespan with conditional ChromaDB initialization

**Changes:**
- Move `get_effective_backend_type()` check early in lifespan (before ChromaDB init)
- Wrap VectorStoreManager and BM25IndexManager creation in `if backend_type == "chroma":` block
- When backend is postgres: set `app.state.vector_store = None`, `app.state.bm25_manager = None`
- Pass `storage_backend=storage_backend` to IndexingService and QueryService (not legacy params)
- Set `app.state.backend_type = backend_type` for use by health/query routers

**Result:**
- No ChromaDB directories created when `AGENT_BRAIN_STORAGE_BACKEND=postgres`
- Services receive storage backend from factory
- Backward compatibility preserved (services support both old and new constructor patterns)

**Commit:** `e12f591` - feat(09-01): rewire main.py lifespan with conditional ChromaDB initialization

### Task 2: Add graph query validation and health endpoint graph status for postgres backend

**query_service.py changes:**
- `_execute_graph_query()`: Add backend compatibility check before ENABLE_GRAPH_INDEX check
  - Raise ValueError with actionable message when backend != "chroma"
- `_execute_multi_query()`: Check backend before attempting graph query
  - If backend != "chroma": skip graph, log info message (graceful degradation)

**health.py changes:**
- `health_check()`: Use `getattr()` for vector_store (handle None for postgres)
  - Add branch: when vector_store is None, check storage_backend.is_initialized
- `indexing_status()`: Use `getattr()` for vector_store, fallback to storage_backend.get_count()
  - Override graph_index status when backend != "chroma" (set unavailable with reason)

**Result:**
- Graph-only mode raises clear error on postgres: "Graph queries require ChromaDB backend"
- Multi-mode gracefully skips graph on postgres (no error, just info log)
- Health endpoints show graph_store as unavailable with reason on postgres
- Health endpoints handle None vector_store safely

**Commits:**
- `f8f3fb4` - feat(09-01): add graph query validation and health status for postgres backend
- `4004459` - style(09-01): format health.py with black

### Task 3: Update plugin documentation for graph query ChromaDB requirement

**agent-brain-graph.md:**
- Added "Backend Requirements" section after "Prerequisites"
  - Documents ChromaDB requirement for graph queries
  - Shows postgres backend error message
  - Provides resolution options (switch to chroma or use hybrid)
- Added "PostgreSQL Backend" error handling section
  - Documents error and resolution options

**agent-brain-multi.md:**
- Updated "Graceful Degradation" section
  - Added note: postgres backend auto-uses BM25 + Vector only (no error)
- Updated "Graph Index Not Available" section
  - Added note: postgres backend auto-excludes graph (no action needed)

**Result:**
- Plugin users understand graph queries require ChromaDB
- Clear guidance for postgres users (switch backend or use hybrid/multi)
- Multi-mode degradation behavior documented

**Commit:** `493a611` - docs(09-01): update plugin docs for graph query ChromaDB requirement

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Black formatting issue in health.py**
- **Found during:** Task 2 verification
- **Issue:** Black reformatted health.py after manual edits (line wrapping for f-string)
- **Fix:** Ran `poetry run black agent_brain_server/api/routers/health.py`
- **Files modified:** health.py
- **Commit:** `4004459`

## Verification

All verification steps passed:

1. ✅ `ruff check agent_brain_server/` - No lint errors
2. ✅ `mypy agent_brain_server/ --ignore-missing-imports` - No type errors
3. ✅ `black --check agent_brain_server/` - Formatting correct
4. ✅ `pytest tests/ -x -q` - All 670 tests pass (19 skipped)
5. ✅ `grep "storage_backend=storage_backend" main.py` - Returns hits for both services
6. ✅ `grep "vector_store=vector_store" main.py` - No hits in service construction

## Testing

**Existing tests:** 670 passed, 19 skipped (no regressions)

The backward-compatible constructors in IndexingService and QueryService ensured all existing tests continued to work without modification. Tests that pass `vector_store` and `bm25_manager` still work via the legacy constructor path.

## Impact Assessment

### Files Modified

| File | Lines Changed | Purpose |
|------|---------------|---------|
| main.py | ~47 lines | Conditional ChromaDB init, pass storage_backend to services |
| query_service.py | ~20 lines | Graph query backend validation, multi-mode graceful degradation |
| health.py | ~30 lines | Handle None vector_store, override graph status on postgres |
| agent-brain-graph.md | +20 lines | Backend requirements, postgres error handling |
| agent-brain-multi.md | +7 lines | Postgres degradation behavior |

### Behavioral Changes

**When backend is chroma (default):**
- No change - services work exactly as before

**When backend is postgres:**
- ChromaDB directories not created (chroma_db/, bm25_index/)
- Graph queries return explicit error with actionable message
- Multi-mode uses BM25 + Vector only (logs info, no error)
- Health endpoint shows graph as unavailable with reason

## Success Criteria

- [x] main.py passes storage_backend to IndexingService and QueryService (not vector_store/bm25_manager)
- [x] ChromaDB components only initialized when backend_type == "chroma"
- [x] Graph queries raise ValueError on postgres backend with actionable message
- [x] Multi-mode skips graph on postgres (no error, graceful degradation)
- [x] Health endpoint shows graph as unavailable on postgres
- [x] Health endpoints handle None vector_store for postgres backend
- [x] Plugin docs updated with ChromaDB requirement for graph queries
- [x] All existing tests still pass (backward-compatible constructors preserve test patterns)

## Self-Check

Verifying claims before proceeding:

**Created files:**
```bash
[ -f ".planning/phases/09-runtime-backend-wiring/09-01-SUMMARY.md" ] && echo "FOUND: SUMMARY.md" || echo "MISSING: SUMMARY.md"
```
✅ FOUND: SUMMARY.md

**Commits exist:**
```bash
git log --oneline --all | grep -E "(e12f591|f8f3fb4|493a611|4004459)" && echo "FOUND: all commits" || echo "MISSING: commits"
```
✅ FOUND: all commits
- e12f591: feat(09-01): rewire main.py lifespan with conditional ChromaDB initialization
- f8f3fb4: feat(09-01): add graph query validation and health status for postgres backend
- 493a611: docs(09-01): update plugin docs for graph query ChromaDB requirement
- 4004459: style(09-01): format health.py with black

## Self-Check: PASSED

All claimed files and commits exist. Plan executed successfully.
