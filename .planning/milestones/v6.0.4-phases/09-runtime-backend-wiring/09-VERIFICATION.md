---
phase: 09-runtime-backend-wiring
verified: 2026-02-13T04:30:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase 9: Runtime Backend Wiring Verification Report

**Phase Goal:** Wire factory-selected storage backend into QueryService and IndexingService so backend selection controls runtime behavior

**Verified:** 2026-02-13T04:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | main.py lifespan passes storage_backend (from factory) to QueryService and IndexingService | ✓ VERIFIED | Lines 290-291, 297-298 in main.py pass `storage_backend=storage_backend` |
| 2 | When AGENT_BRAIN_STORAGE_BACKEND=postgres, QueryService uses PostgresBackend (not ChromaBackend) | ✓ VERIFIED | Test `test_postgres_factory_returns_postgres_backend` passes, factory returns PostgresBackend when backend_type="postgres" |
| 3 | Legacy vector_store + bm25_manager creation skipped when using non-chroma backend | ✓ VERIFIED | Lines 228-270 in main.py: ChromaDB init only in `if backend_type == "chroma":` block, else sets to None |
| 4 | Integration test verifies factory-selected backend is the instance used by services | ✓ VERIFIED | 5 wiring tests in `test_backend_wiring.py` verify factory-service integration |
| 5 | All existing tests pass (task before-push clean) | ✓ VERIFIED | task before-push passed: 675 server tests + 86 CLI tests, exit code 0 |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agent-brain-server/agent_brain_server/api/main.py` | Conditional ChromaDB initialization and storage_backend-driven service creation | ✓ VERIFIED | Lines 228-270: conditional init block, lines 290-300: storage_backend param to services |
| `agent-brain-server/agent_brain_server/services/query_service.py` | Graph query validation for postgres backend | ✓ VERIFIED | Lines 457-466: backend check raises ValueError with "require ChromaDB backend" message |
| `agent-brain-server/agent_brain_server/api/routers/health.py` | Graph store unavailable status on postgres backend | ✓ VERIFIED | Lines 170-183: override graph_index status with "unavailable" and reason when backend != "chroma" |
| `agent-brain-server/tests/integration/test_backend_wiring.py` | Backend wiring smoke tests | ✓ VERIFIED | 185 lines, 5 tests, all pass |
| `agent-brain-plugin/commands/agent-brain-graph.md` | Backend requirements documentation | ✓ VERIFIED | Lines 75-85: Backend Requirements section documents ChromaDB requirement |
| `agent-brain-plugin/commands/agent-brain-multi.md` | Postgres degradation behavior | ✓ VERIFIED | Lines 183, 256: Documents postgres backend auto-excludes graph |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `main.py` | `get_storage_backend()` | Factory call in lifespan | ✓ WIRED | Line 222: `storage_backend = get_storage_backend()` |
| `main.py` | IndexingService constructor | `storage_backend` parameter | ✓ WIRED | Line 290-291: `IndexingService(storage_backend=storage_backend, ...)` |
| `main.py` | QueryService constructor | `storage_backend` parameter | ✓ WIRED | Line 297-298: `QueryService(storage_backend=storage_backend)` |
| `query_service.py` | `get_effective_backend_type()` | Backend check in _execute_graph_query | ✓ WIRED | Line 458: import, line 460: call, line 461: backend check |
| `query_service.py` | Graph query validation | ValueError raise on postgres | ✓ WIRED | Lines 461-466: raises ValueError with message |
| `health.py` | `storage_backend` | Fallback for get_count when vector_store is None | ✓ WIRED | Lines 134-136: uses storage_backend.get_count() when vector_store is None |

### Requirements Coverage

| Requirement | Status | Supporting Truths |
|-------------|--------|-------------------|
| STOR-04: Services depend only on Protocol interface | ✓ SATISFIED | Truth 1, 2 — services receive StorageBackendProtocol via storage_backend param |
| CONF-03: Environment variable override for backend selection | ✓ SATISFIED | Truth 2, 3 — factory uses get_effective_backend_type() which checks AGENT_BRAIN_STORAGE_BACKEND |

### Anti-Patterns Found

No anti-patterns detected. Scanned modified sections of:
- `main.py` (lines 228-300)
- `query_service.py` (lines 457-583)
- `health.py` (lines 126-183)

No TODO/FIXME/PLACEHOLDER comments, no empty implementations, no stub patterns found.

### Human Verification Required

None — all verification automated via tests and code inspection.

Phase 9 is a wiring phase with testable integration points. All must-haves verified programmatically.

## Detailed Verification

### Truth 1: main.py lifespan passes storage_backend to services

**Verification method:** Code inspection + grep

**Evidence:**
```python
# Line 290-291
indexing_service = IndexingService(
    storage_backend=storage_backend,
    document_loader=document_loader,
)

# Line 297-298
query_service = QueryService(
    storage_backend=storage_backend,
)
```

**Grep verification:**
```bash
$ grep "storage_backend=storage_backend" main.py
            storage_backend=storage_backend,
            storage_backend=storage_backend,
```

**Legacy parameter check:**
```bash
$ grep "vector_store=vector_store" main.py
# No matches (confirmed legacy params removed from service construction)
```

**Status:** ✓ VERIFIED — Services receive storage_backend parameter from factory, not legacy vector_store/bm25_manager.

### Truth 2: QueryService uses PostgresBackend when AGENT_BRAIN_STORAGE_BACKEND=postgres

**Verification method:** Mock-based test

**Evidence:**
Test: `test_postgres_factory_returns_postgres_backend` in `test_backend_wiring.py`

```python
def test_postgres_factory_returns_postgres_backend(self) -> None:
    """Verify factory creates PostgresBackend when backend_type is postgres."""
    # Patches get_effective_backend_type to return "postgres"
    # Mocks PostgresBackend import
    # Calls get_storage_backend()
    # Asserts returned backend is PostgresBackend instance
    # Passes to QueryService, verifies service.storage_backend is same instance
```

**Test result:** PASSED (part of 5/5 wiring tests)

**Status:** ✓ VERIFIED — Factory returns PostgresBackend when environment variable set, services use that instance.

### Truth 3: Legacy vector_store + bm25_manager creation skipped on postgres

**Verification method:** Code inspection

**Evidence:**
```python
# Lines 228-270 in main.py
if backend_type == "chroma":
    # Determine persistence directories
    chroma_dir = ...
    bm25_dir = ...
    
    # Initialize ChromaDB components
    vector_store = VectorStoreManager(persist_dir=chroma_dir)
    await vector_store.initialize()
    app.state.vector_store = vector_store
    
    bm25_manager = BM25IndexManager(persist_dir=bm25_dir)
    bm25_manager.initialize()
    app.state.bm25_manager = bm25_manager
else:
    # PostgreSQL or other backend - no ChromaDB components needed
    app.state.vector_store = None
    app.state.bm25_manager = None
    logger.info(f"Skipping ChromaDB initialization (backend: {backend_type})")
```

**Conditional initialization check:**
- Line 229: `if backend_type == "chroma":`
- Lines 230-264: ChromaDB-specific initialization
- Lines 265-270: Else branch sets to None, logs skip message

**Status:** ✓ VERIFIED — ChromaDB directories and BM25 indexes only created when backend_type == "chroma".

### Truth 4: Integration test verifies factory-service wiring

**Verification method:** Test execution

**Evidence:**
Test file: `tests/integration/test_backend_wiring.py` (185 lines)

**5 tests implemented:**
1. `test_storage_backend_parameter_takes_precedence` — Verifies storage_backend param used directly
2. `test_legacy_params_still_wrap_in_chroma_backend` — Backward compat for old tests
3. `test_chroma_factory_returns_chroma_backend` — Factory returns ChromaBackend when backend=chroma
4. `test_postgres_factory_returns_postgres_backend` — Factory returns PostgresBackend when backend=postgres (mocked)
5. `test_graph_query_rejected_on_postgres_backend` — Graph queries raise ValueError on postgres

**Test results:**
```bash
$ poetry run pytest tests/integration/test_backend_wiring.py -v
======================== 5 passed, 2 warnings in 3.58s =========================
```

**Status:** ✓ VERIFIED — All wiring tests pass, confirming factory-selected backend drives service behavior.

### Truth 5: All existing tests pass (task before-push clean)

**Verification method:** CI-equivalent command execution

**Evidence:**
```bash
$ task before-push
--- Formatting code with black ---
All done! ✨ 🍰 ✨
33 files left unchanged.

--- Linting with ruff ---
All checks passed!

--- Type checking with mypy ---
Success: no issues found

--- Running tests with coverage ---
======================== 675 passed, 19 skipped in 42.53s =========================
Coverage: 73% server, 54% CLI

--- All checks passed - Ready to push ---
```

**Test breakdown:**
- 675 server tests (670 existing + 5 new wiring tests)
- 86 CLI tests
- 19 skipped (PostgreSQL-specific tests without database)
- Exit code: 0

**Status:** ✓ VERIFIED — Zero regressions, all quality gates passed.

## Additional Verifications

### Graph Query Validation

**Truth:** Graph queries raise ValueError on postgres backend with actionable message

**Evidence:**
```python
# Lines 457-466 in query_service.py
backend_type = get_effective_backend_type()
if backend_type != "chroma":
    raise ValueError(
        f"Graph queries (mode='graph') require ChromaDB backend. "
        f"Current backend: '{backend_type}'. "
        f"To use graph queries, set AGENT_BRAIN_STORAGE_BACKEND=chroma."
    )
```

**Test coverage:**
Test: `test_graph_query_rejected_on_postgres_backend` validates this behavior

**Status:** ✓ VERIFIED

### Multi-Mode Graceful Degradation

**Truth:** Multi-mode skips graph on postgres (no error, graceful degradation)

**Evidence:**
```python
# Lines 568-583 in query_service.py
backend_type = get_effective_backend_type()
if settings.ENABLE_GRAPH_INDEX and backend_type == "chroma":
    try:
        graph_results = await self._execute_graph_query(request)
    except ValueError:
        pass  # Graph not enabled or not available, skip
elif backend_type != "chroma":
    logger.info(
        "Graph component skipped in multi-mode: "
        "graph queries require ChromaDB backend "
        f"(current: {backend_type})"
    )
```

**Behavior:**
- Graph-only mode: raises ValueError (explicit error)
- Multi-mode: skips graph, logs info (graceful degradation)

**Status:** ✓ VERIFIED

### Health Endpoint Backend Awareness

**Truth:** Health endpoints show graph as unavailable on postgres backend

**Evidence:**
```python
# Lines 170-183 in health.py
backend_type = get_effective_backend_type()
graph_index_info = service_status.get("graph_index")
if backend_type != "chroma" and graph_index_info is not None:
    reason_msg = f"Graph queries require ChromaDB backend (current: {backend_type})"
    graph_index_info = {
        "enabled": False,
        "initialized": False,
        "entity_count": 0,
        "relationship_count": 0,
        "store_type": "unavailable",
        "reason": reason_msg,
    }
    service_status["graph_index"] = graph_index_info
```

**Status:** ✓ VERIFIED

### Plugin Documentation Updates

**Truth:** Plugin docs updated with ChromaDB requirement for graph queries

**Evidence:**

**agent-brain-graph.md** (lines 75-85):
```markdown
## Backend Requirements

Graph search is only available when using the **ChromaDB** storage backend (default). If you are using the PostgreSQL backend (`AGENT_BRAIN_STORAGE_BACKEND=postgres`), graph queries will return an error:

```
Error: Graph queries (mode='graph') require ChromaDB backend.
Current backend: 'postgres'.
To use graph queries, set AGENT_BRAIN_STORAGE_BACKEND=chroma.
```

To use graph search, switch to ChromaDB backend or use `/agent-brain-hybrid` for hybrid BM25 + vector search on any backend.
```

**agent-brain-multi.md** (lines 183, 256):
```markdown
**Note:** When using PostgreSQL backend, graph is automatically excluded from multi-mode results. No action needed.

**Note:** When using the PostgreSQL backend (`AGENT_BRAIN_STORAGE_BACKEND=postgres`), multi-mode automatically uses BM25 + Vector only (graph component is skipped). No error is raised -- multi-mode gracefully adapts.
```

**Status:** ✓ VERIFIED

### Commits Verification

All commits from summaries exist in repository:

| Commit | Message | Plan |
|--------|---------|------|
| e12f591 | feat(09-01): rewire main.py lifespan with conditional ChromaDB initialization | 09-01 |
| f8f3fb4 | feat(09-01): add graph query validation and health status for postgres backend | 09-01 |
| 493a611 | docs(09-01): update plugin docs for graph query ChromaDB requirement | 09-01 |
| 4004459 | style(09-01): format health.py with black | 09-01 |
| fef7882 | test(09-02): add backend wiring smoke tests | 09-02 |

**Status:** ✓ VERIFIED — All claimed commits exist

## Summary

Phase 9 successfully closed the v6.0 audit gap where factory selected the backend but services always received ChromaDB via legacy parameters.

**Key achievements:**
1. Services now receive `storage_backend` from factory (not legacy vector_store/bm25_manager)
2. ChromaDB components conditionally initialized only when backend_type == "chroma"
3. Graph queries validate backend compatibility (error on postgres)
4. Multi-mode gracefully degrades on postgres (skips graph, no error)
5. Health endpoints backend-aware (show graph unavailable on postgres)
6. Plugin documentation updated with backend requirements
7. 5 comprehensive wiring tests added
8. Zero test regressions (675 server + 86 CLI tests pass)

**All must-haves verified. Phase goal achieved.**

---

*Verified: 2026-02-13T04:30:00Z*
*Verifier: Claude (gsd-verifier)*
