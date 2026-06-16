---
phase: 64
plan: "02"
subsystem: graphrag-health-counts
tags: [graphrag, health, kuzu, counts, ttl-cache, gstab-03]
dependency_graph:
  requires: [64-01, 64-03]
  provides: [live-counts-api, health-graph-counts-accurate]
  affects: [agent-brain-server/storage/graph_store.py, agent-brain-server/indexing/graph_index.py, agent-brain-server/models/graph.py, agent-brain-server/services/indexing_service.py]
tech_stack:
  added: [LIVE_COUNT_TTL_SECONDS, live_counts(), counts_stale field]
  patterns: [kuzu-COUNT-star, ttl-cache, degraded-fallback]
key_files:
  created:
    - agent-brain-server/tests/unit/storage/test_graph_live_count.py
    - agent-brain-server/tests/unit/api/test_health_graph_counts.py
  modified:
    - agent-brain-server/agent_brain_server/storage/graph_store.py
    - agent-brain-server/agent_brain_server/indexing/graph_index.py
    - agent-brain-server/agent_brain_server/models/graph.py
    - agent-brain-server/agent_brain_server/services/indexing_service.py
    - agent-brain-server/tests/unit/test_graph_index.py
decisions:
  - "Use sys.modules patching instead of patch() for kuzu import in tests — the live_counts() method uses `import kuzu as _kuzu_module` at call time, so the module must be replaced in sys.modules rather than patching a module attribute"
  - "Follow existing get_entity_by_id pattern for kuzu Connection: use getattr(self, '_kuzu_db', None) + type: ignore[arg-type] for the Connection(...) call — same approach as line 1229 in the same file"
  - "Test placement: plan specified tests/storage/ and tests/api/ but actual project structure is tests/unit/storage/ and tests/unit/api/ — placed in correct structure"
metrics:
  duration: "746s (~12 min)"
  completed: "2026-06-14"
  tasks_completed: 3
  files_changed: 7
requirements: [GSTAB-03]
---

# Phase 64 Plan 02: Live Graph Counts (GSTAB-03) Summary

**One-liner:** Live kuzu COUNT(*) with 5s TTL cache replaces drifting bookkeeping; `counts_stale` field surfaces degraded state in `/health/status`, eliminating the 0/100 vs 5677/4366 discrepancy class from issue #184.

## Objective

Make `/health/status` graph counts true. The prior implementation read `self._entity_count` / `self._relationship_count` from in-memory bookkeeping that drifts after a job-timeout rollback — producing the #184 `0 / 100` vs real `5677 / 4366` discrepancy. This plan replaces that source with a LIVE kuzu `COUNT(*)` at query time, wrapped in a ~5s TTL cache.

## Tasks Executed

### Task 1: Add live_counts() to GraphStoreManager (TDD)

**Files:** `graph_store.py`, `tests/unit/storage/test_graph_live_count.py`

Added to `graph_store.py`:
- `LIVE_COUNT_TTL_SECONDS: float = 5.0` module constant
- `_live_count_cache: tuple[int, int] | None` and `_live_count_cached_at: float` instance fields
- `live_counts() -> tuple[int, int, bool]` method:
  - kuzu path: `MATCH (n) RETURN COUNT(n)` + `MATCH ()-[r]->() RETURN COUNT(r)`, cached for 5s
  - TTL guard: if cache is fresh, return cached values directly (no DB round-trip)
  - Degraded fallback: on `IndexError/RuntimeError/OSError` returns last-known cache or bookkeeping with `stale=True`, NEVER 0/0
  - non-kuzu path: returns bookkeeping `(self._entity_count, self._relationship_count, False)` immediately
  - graphrag-disabled path: returns `(0, 0, False)` immediately

14 tests covering all 5 required behaviors including the #184 regression guard.

**Commit:** `8b7fd18`

### Task 2: Wire live_counts into get_status, surface counts_stale (TDD)

**Files:** `graph_index.py`, `models/graph.py`, `indexing_service.py`, `tests/unit/api/test_health_graph_counts.py`

Changes:
- `GraphIndexStatus` pydantic model: added `counts_stale: bool = False` field
- `graph_index.GraphIndexManager.get_status()`: replaced `self.graph_store.entity_count` / `.relationship_count` with `entities, relationships, counts_stale = self.graph_store.live_counts()`
- `indexing_service.get_status()`: added `"counts_stale": graph_status.counts_stale` to the `graph_index` dict
- `health.py` non-chroma 0/0 override (lines ~174-187): **untouched** — that path genuinely has no graph

8 tests covering all 4 behaviors: live counts reach the API, stale=True surfaces, non-chroma override intact, simple store unaffected.

**Commit:** `8d94787`

### Task 3: Validation gate (task before-push from repo root)

Fixed issues found by the quality gate:
- `graph_store.py`: removed unused `type: ignore[import-not-found]` (kuzu IS installed); used `getattr` + `type: ignore[arg-type]` pattern matching existing `get_entity_by_id` code
- `test_graph_live_count.py`: Ruff auto-fixed import sort order (I001) — Black reformatted to parenthesized `with` blocks too
- `test_health_graph_counts.py`: removed unused `pytest` import (F401), fixed import sort (I001), added `# noqa: E501` for 89-char docstring
- `test_graph_index.py` (Rule 1 auto-fix): existing `test_get_status_enabled` broke because `get_status()` now calls `live_counts()` instead of reading bookkeeping properties — added `mock_graph_store.live_counts.return_value = (50, 100, False)` and updated the fixture default

`task before-push` exits 0: **1387 passed, 28 skipped, 80%+ coverage**.

**Commit:** `6ef3fd3`

## Commits

| Hash | Type | Description |
|------|------|-------------|
| `8b7fd18` | feat | Add live_counts() with kuzu COUNT(*), TTL cache, degraded fallback |
| `8d94787` | feat | Wire live_counts into get_status, surface counts_stale to /health/status |
| `6ef3fd3` | chore | Fix mypy/ruff issues; update test_graph_index for live_counts |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_graph_index.py existing test broke on live_counts() change**

- **Found during:** Task 3 (before-push gate)
- **Issue:** `TestGraphIndexManagerStatus::test_get_status_enabled` was asserting `status.entity_count == 50` but after the change to use `live_counts()`, the MagicMock returned a MagicMock tuple (not real ints) from the auto-created `live_counts` mock method
- **Fix:** Added `mock_graph_store.live_counts.return_value = (10, 20, False)` to the shared fixture and `(50, 100, False)` to the specific test
- **Files modified:** `tests/unit/test_graph_index.py`
- **Commit:** `6ef3fd3`

**2. [Rule 2 - Missing] mypy type safety for kuzu Connection call**

- **Found during:** Task 3 (before-push gate)
- **Issue:** `_kuzu_module.Connection(self._kuzu_db)` triggered mypy `arg-type` because `self._kuzu_db` is typed `Any | None` but kuzu expects `Database`
- **Fix:** Used `kuzu_db = getattr(self, "_kuzu_db", None)` (matching line 1229 pattern) + `type: ignore[arg-type]` on the Connection call; removed the now-unneeded `type: ignore[import-not-found]`
- **Files modified:** `agent_brain_server/storage/graph_store.py`
- **Commit:** `6ef3fd3`

**3. [Deviation] Test file paths adjusted to match project structure**

The plan specified `tests/storage/` and `tests/api/` but the project uses `tests/unit/storage/` and `tests/unit/api/`. Tests placed in the correct project directories.

**4. [Deviation] sys.modules patching instead of module attribute patching for kuzu**

The plan's action note says "import kuzu as _kuzu_module inside the method." Since kuzu is imported inside `live_counts()` at call time, patching `agent_brain_server.storage.graph_store.kuzu` does not work when kuzu is installed. Used `patch.dict(sys.modules, {"kuzu": fake_kuzu_module})` to intercept the runtime import — the established pattern for testing code that imports inside functions.

## Verification

- `grep "def live_counts" agent-brain-server/agent_brain_server/storage/graph_store.py` matches
- `grep "LIVE_COUNT_TTL_SECONDS" agent-brain-server/agent_brain_server/storage/graph_store.py` matches
- `grep "COUNT(n)" agent-brain-server/agent_brain_server/storage/graph_store.py` matches
- `grep "COUNT(r)" agent-brain-server/agent_brain_server/storage/graph_store.py` matches
- `grep "except (IndexError, RuntimeError, OSError)" agent-brain-server/agent_brain_server/storage/graph_store.py` matches (live_counts degraded fallback)
- `grep "live_counts" agent-brain-server/agent_brain_server/indexing/graph_index.py` matches
- `grep "counts_stale" agent-brain-server/agent_brain_server/models/graph.py` matches
- `grep "counts_stale" agent-brain-server/agent_brain_server/services/indexing_service.py` matches
- health.py non-chroma override (`"entity_count": 0`) line ~182 still present and untouched
- `task before-push` exits 0: 1387 passed, 28 skipped, 80%+ server coverage

## Self-Check: PASSED

All created/modified files exist. All 3 commits verified in git log.
