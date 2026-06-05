---
phase: 09-runtime-backend-wiring
plan: 02
subsystem: testing
tags:
  - backend-wiring-tests
  - smoke-tests
  - mock-based-testing
  - quality-gate
dependency_graph:
  requires:
    - 09-01 (runtime backend wiring)
    - 05-01 (StorageBackendProtocol)
    - 05-02 (ChromaBackend adapter)
    - 06-03 (PostgreSQL integration)
  provides:
    - Automated backend wiring verification
    - Regression detection for factory-service integration
  affects:
    - tests/integration/test_backend_wiring.py (new)
tech_stack:
  added: []
  patterns:
    - Mock-based integration testing
    - Factory singleton cache management in tests
    - Lazy import mocking with patch.dict
key_files:
  created:
    - agent-brain-server/tests/integration/test_backend_wiring.py
  modified: []
decisions:
  - summary: "All wiring tests mock-based (no PostgreSQL required)"
    rationale: "Tests must run in task before-push without database dependency. Mock PostgresBackend to avoid requiring asyncpg/sqlalchemy."
    alternatives: ["Real PostgreSQL tests (rejected - CI complexity)"]
  - summary: "Patch get_effective_backend_type at agent_brain_server.storage"
    rationale: "Function is imported locally in _execute_graph_query, must patch at the module where it's imported from (not factory)"
    alternatives: []
  - summary: "Use patch.dict for lazy PostgresBackend import"
    rationale: "PostgresBackend is lazily imported in factory.py postgres branch. patch.dict allows mocking sys.modules to intercept the import."
    alternatives: []
metrics:
  duration_minutes: 5
  tasks_completed: 2
  files_created: 1
  commits: 1
  tests_added: 5
  tests_passed: 675
  completed_date: 2026-02-13
---

# Phase 09 Plan 02: Backend Wiring Tests Summary

**One-liner:** Created 5 mock-based wiring tests verifying factory-selected backend drives service behavior, all passing in task before-push without PostgreSQL.

## What Was Built

Added comprehensive smoke tests for Phase 9 backend wiring changes:

1. **test_storage_backend_parameter_takes_precedence**: Verifies `storage_backend` parameter to services is used directly (not wrapped)
2. **test_legacy_params_still_wrap_in_chroma_backend**: Ensures backward compatibility - legacy `vector_store`/`bm25_manager` params wrap in ChromaBackend
3. **test_chroma_factory_returns_chroma_backend**: Confirms factory returns ChromaBackend when `backend_type == "chroma"`
4. **test_postgres_factory_returns_postgres_backend**: Mocked test verifying factory creates PostgresBackend when `backend_type == "postgres"`
5. **test_graph_query_rejected_on_postgres_backend**: Validates graph queries raise ValueError with actionable message on postgres backend

All tests are mock-based and run without PostgreSQL database, ensuring they always execute in `task before-push`.

## Implementation Details

### Task 1: Create mock-based backend wiring smoke tests

**File created:** `agent-brain-server/tests/integration/test_backend_wiring.py`

**Test structure:**
- `@pytest.fixture(autouse=True)` to reset backend cache between tests
- Class-based test organization (`TestBackendWiring`)
- Type-annotated test methods (mypy strict compliance)
- Mock-heavy approach using `unittest.mock.MagicMock` and `patch`

**Key testing techniques:**

1. **Backend parameter precedence** (Test 1):
   - Pass `storage_backend` directly to QueryService/IndexingService
   - Assert `service.storage_backend is mock_backend` (identity check)

2. **Legacy backward compatibility** (Test 2):
   - Pass `vector_store` and `bm25_manager` separately
   - Assert service wraps them in ChromaBackend automatically
   - Verify wrapped stores match original mocks

3. **Factory singleton behavior** (Test 3, 4):
   - Call `reset_storage_backend_cache()` to force fresh instance
   - Patch `get_effective_backend_type()` to control backend selection
   - For postgres: use `patch.dict("sys.modules", ...)` to mock lazy import

4. **Graph query backend validation** (Test 5):
   - Patch `agent_brain_server.storage.get_effective_backend_type` (where it's imported)
   - Mock request object with graph query parameters
   - Assert ValueError with "chroma" and "backend" in error message

**Commit:** `fef7882` - test(09-02): add backend wiring smoke tests

### Task 2: Run task before-push to verify zero regressions

**Results:**
- ✅ Formatting: All files formatted (Black)
- ✅ Linting: No errors (Ruff)
- ✅ Type checking: No errors (mypy strict)
- ✅ Tests: 675 server tests + 86 CLI tests = 761 total (all passed)
- ✅ Coverage: 73% server, 54% CLI (both > 50% requirement)
- ✅ Exit code: 0

**Test breakdown:**
- 19 skipped (PostgreSQL-specific tests without DB)
- 675 passed (670 existing + 5 new wiring tests)
- No regressions from Phase 9 changes

## Deviations from Plan

None - plan executed exactly as written.

## Verification

All verification steps passed:

1. ✅ `pytest tests/integration/test_backend_wiring.py -v` - 5 tests pass
2. ✅ `ruff check tests/integration/test_backend_wiring.py` - No lint errors
3. ✅ `mypy tests/integration/test_backend_wiring.py --ignore-missing-imports` - No type errors
4. ✅ `task before-push` - Exit code 0
5. ✅ Total test count: 675 (670 existing + 5 new)
6. ✅ No `pytest.mark.postgres` on new tests (all mock-based)

## Testing

**New tests:** 5 mock-based wiring tests

| Test | Purpose | Technique |
|------|---------|-----------|
| test_storage_backend_parameter_takes_precedence | Verify new constructor param works | Direct mock injection |
| test_legacy_params_still_wrap_in_chroma_backend | Verify backward compatibility | Legacy param wrapping check |
| test_chroma_factory_returns_chroma_backend | Verify factory for chroma | Mock get_effective_backend_type |
| test_postgres_factory_returns_postgres_backend | Verify factory for postgres | Mock lazy import with patch.dict |
| test_graph_query_rejected_on_postgres_backend | Verify graph validation | Mock backend check in _execute_graph_query |

**Existing tests:** All 670 server tests + 86 CLI tests pass (zero regressions)

## Impact Assessment

### Files Created

| File | Lines | Purpose |
|------|-------|---------|
| test_backend_wiring.py | 181 | Mock-based wiring smoke tests |

### Coverage

**Before:** 670 tests, no backend wiring coverage
**After:** 675 tests, backend wiring fully covered

Backend wiring logic now has automated regression detection:
- Factory backend selection
- Service constructor parameter precedence
- Legacy backward compatibility
- Graph query backend validation

## Success Criteria

- [x] 5 mock-based wiring tests exist in tests/integration/test_backend_wiring.py
- [x] Tests verify: storage_backend precedence, legacy backward compat, chroma factory, postgres factory, graph query rejection
- [x] All tests are mock-based (no PostgreSQL required)
- [x] task before-push passes with exit code 0
- [x] Zero test regressions from Phase 9 changes (all 670 existing tests still pass)

## Self-Check

Verifying claims before proceeding:

**Created files:**
```bash
[ -f "agent-brain-server/tests/integration/test_backend_wiring.py" ] && echo "FOUND" || echo "MISSING"
```
✅ FOUND: agent-brain-server/tests/integration/test_backend_wiring.py

**Commits exist:**
```bash
git log --oneline --all | grep -q "fef7882" && echo "FOUND: fef7882" || echo "MISSING"
```
✅ FOUND: fef7882 - test(09-02): add backend wiring smoke tests

**Tests pass:**
```bash
cd agent-brain-server && poetry run pytest tests/integration/test_backend_wiring.py -v 2>&1 | grep -q "5 passed" && echo "PASS" || echo "FAIL"
```
✅ PASS: 5 tests pass

**task before-push passes:**
```bash
task before-push 2>&1 | tail -1 | grep -q "All checks passed" && echo "PASS" || echo "FAIL"
```
✅ PASS: All checks passed - Ready to push

## Self-Check: PASSED

All claimed files, commits, and test results exist. Plan executed successfully.
