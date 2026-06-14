---
phase: 64-graphrag-stability-subscriptions-debug-endpoint
verified: 2026-06-14T00:00:00Z
status: passed
score: 4/4 must-haves verified
---

# Phase 64: GraphRAG Stability + Subscriptions Debug Endpoint — Verification Report

**Phase Goal:** The GraphRAG/kuzu path never hard-crashes the server or silently under-reports; operators have tools to diagnose and restore; the subscriptions debug endpoint closes the v10.2 deferred item.
**Verified:** 2026-06-14
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Sustained GraphRAG kuzu failure surfaces a clear job error; server process continues running (no SIGSEGV process death); `simple` remains the documented fallback | VERIFIED | `build_from_documents_isolated` in `graph_index.py:209` uses `multiprocessing.get_context("spawn")`; non-zero child exit raises `GraphBuildFailedError`; `except GraphBuildFailedError` in `indexing_service.py:739` swallows graph failure and leaves job COMPLETED; 0 writes to `GRAPH_STORE_TYPE` |
| 2 | `agent-brain graph restore-from-snapshot [--snapshot PATH] [--dry-run]` replays latest kuzu snapshot; `agent-brain doctor` surfaces stale-graph condition as WARN not OK | VERIFIED | `commands/graph.py` has `@graph_group.command("restore-from-snapshot")` with `--snapshot`, `--dry-run`, `--yes` options; `cli.add_command(graph_group, name="graph")` registered; `diagnostics.py:499` has `_check_graph_staleness`; `apply_safe_fixes` calls `restore_from_snapshot` at line 786 |
| 3 | `GET /health/status` graph `entity_count` / `relationship_count` match live kuzu `SELECT COUNT(*)` — the 0/100 vs 5677/4366 discrepancy class is gone | VERIFIED | `graph_store.py:656` has `def live_counts() -> tuple[int, int, bool]` with `LIVE_COUNT_TTL_SECONDS = 5.0`; `COUNT(n)` and `COUNT(r)` kuzu queries; `graph_index.py:972` calls `self.graph_store.live_counts()`; `GraphIndexStatus.counts_stale` field in models; surfaced in `indexing_service.py:896` |
| 4 | `GET /mcp/subscriptions` returns 200 with transport, server_uptime_s, active_count, subscriptions[] (truncated session ids) without requiring a token | VERIFIED | `http.py:77` has `SUBSCRIPTIONS_PATH = "/mcp/subscriptions"`; `subscriptions_debug` handler is no-auth, loopback-only; `Route(SUBSCRIPTIONS_PATH, ...)` registered before `Mount(MCP_MOUNT_PATH, ...)` at lines 273-274; `manager.py:444` has `def snapshot()` returning `_meta` values with truncated session_id |

**Score:** 4/4 truths verified

---

## Required Artifacts

### Plan 64-01 (GSTAB-01)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agent-brain-server/agent_brain_server/storage/graph_errors.py` | `class GraphBuildFailedError(RuntimeError)` | VERIFIED | Line 16: `class GraphBuildFailedError(RuntimeError):`, 35-line file, substantive |
| `agent-brain-server/agent_brain_server/indexing/graph_index.py` | `def build_from_documents_isolated` with spawn context | VERIFIED | Line 209: function exists; line 149 and 257: `get_context("spawn")`; operator message contains `store_type=simple` at lines 84, 92, 201 |
| `agent-brain-server/agent_brain_server/services/indexing_service.py` | Catches `GraphBuildFailedError` narrowly; job stays COMPLETED | VERIFIED | Line 32: imports `build_from_documents_isolated`; line 42: imports `GraphBuildFailedError`; line 739: `except GraphBuildFailedError`; line 745: `self._state.graph_degraded = True`; line 897: `"degraded_last_run"` surfaced in status |

### Plan 64-02 (GSTAB-03)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agent-brain-server/agent_brain_server/storage/graph_store.py` | `def live_counts() -> tuple[int, int, bool]` with TTL cache, COUNT(*), degraded fallback | VERIFIED | Line 39: `LIVE_COUNT_TTL_SECONDS = 5.0`; line 656: `def live_counts`; lines 699/705: kuzu COUNT queries; line 717: `except (IndexError, RuntimeError, OSError)` degraded fallback |
| `agent-brain-server/agent_brain_server/indexing/graph_index.py` | `get_status()` calls `live_counts()` | VERIFIED | Line 972: `entities, relationships, counts_stale = self.graph_store.live_counts()` |
| `agent-brain-server/agent_brain_server/models/graph.py` | `counts_stale: bool = False` field in `GraphIndexStatus` | VERIFIED | Line 328: `counts_stale: bool = Field(...)` |

### Plan 64-03 (GSTAB-02)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agent-brain-server/agent_brain_server/storage/graph_store.py` | `def restore_from_snapshot` + `def plan_restore` public primitives | VERIFIED | Line 469: `def plan_restore`; line 501: `def restore_from_snapshot(self, snapshot_path: Path | None = None) -> int:` — no `_recovered_from_corruption` guard |
| `agent-brain-cli/agent_brain_cli/commands/graph.py` | `graph_group` with `restore-from-snapshot` subcommand; `--snapshot`, `--dry-run`, `--yes`; server guard | VERIFIED | Line 43: `def graph_group()`; line 52: `@graph_group.command("restore-from-snapshot")`; lines 54/64/69: options; line 107: `if _server_is_running(state_dir)`; 154-line file |
| `agent-brain-cli/agent_brain_cli/cli.py` | `graph_group` imported and registered | VERIFIED | Line 15: `graph_group` in import; line 169: `cli.add_command(graph_group, name="graph")` |
| `agent-brain-cli/agent_brain_cli/diagnostics.py` | `_check_graph_staleness` WARN check + `apply_safe_fixes` graph_staleness branch | VERIFIED | Line 499: `def _check_graph_staleness`; line 675: called in `run_doctor`; line 768: `check.name == "graph_staleness"` branch in `apply_safe_fixes`; line 786: `mgr.restore_from_snapshot(None)` |

### Plan 64-04 (HOUSE-01)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agent-brain-mcp/agent_brain_mcp/subscriptions/manager.py` | `def snapshot()` read-only; `_meta` records cadence_s, started_at, last_notified_at; truncated session_id; `_meta` scrubbed on all teardown paths | VERIFIED | Line 444: `def snapshot()`; line 103: `self._meta` dict init; line 190: session_id via `_truncate_session_id`; lines 337/367/397: 3 `_meta.pop` calls; line 425: `_meta.clear()` for `cleanup_all`; `start_polling` signature at line 110-118 unchanged |
| `agent-brain-mcp/agent_brain_mcp/http.py` | `SUBSCRIPTIONS_PATH = "/mcp/subscriptions"` constant; `subscriptions_debug` no-auth handler; route before Mount; `build_asgi_app` takes `subscription_manager`; `run_http` passes manager; SUBSCRIPTIONS_PATH in `__all__`; stdio documented | VERIFIED | Line 77: constant; lines 164/166: `build_asgi_app(server, subscription_manager=None)`; line 233: `subscription_manager.snapshot()`; line 273: Route before Mount at 274; line 420: `build_asgi_app(server, subscription_manager)` in `run_http`; line 477: in `__all__`; lines 88-91: stdio-has-no-endpoint documented |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `indexing_service.py` | `graph_index.build_from_documents_isolated` | import + asyncio.to_thread call | WIRED | Lines 32, 731: imported and called in `_build_graph` closure |
| `graph_index.py` | subprocess non-zero exit → `GraphBuildFailedError` | `multiprocessing.get_context("spawn")` child exit code check | WIRED | Lines 149, 257: spawn context; error message includes `store_type=simple` |
| `graph_index.py` | `graph_store.live_counts` | `get_status` reads live counts | WIRED | Line 972: direct call replacing bookkeeping reads |
| `graph_store.py` | kuzu COUNT(*) | `kuzu.Connection().execute("MATCH (n) RETURN COUNT(n)")` | WIRED | Lines 699/705: live COUNT queries inside `live_counts()` |
| `commands/graph.py` | `graph_store.restore_from_snapshot` | lazy import inside command body | WIRED | Line 153: `mgr.restore_from_snapshot(snapshot_path)` |
| `cli.py` | `graph_group` | `cli.add_command(graph_group, name="graph")` | WIRED | Line 169 |
| `diagnostics.py` | `apply_safe_fixes` graph restore branch | `check.name == "graph_staleness"` | WIRED | Line 768 branch; line 786 calls `restore_from_snapshot` |
| `http.py` | `SubscriptionManager.snapshot` | route reads `manager.snapshot()` not `_tasks` | WIRED | Line 233: `subscription_manager.snapshot()`; no `_tasks` references in http.py |
| `http.py` | `build_asgi_app` routes list | `Route(SUBSCRIPTIONS_PATH, ...)` before `Mount(MCP_MOUNT_PATH, ...)` | WIRED | Lines 273-274: correct Starlette ordering |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| GSTAB-01 | 64-01-PLAN.md | kuzu SIGSEGV no longer kills server; graceful job degradation; simple stays documented fallback | SATISFIED | `build_from_documents_isolated` (spawn), `GraphBuildFailedError` catch, `graph_degraded` state, 0 config mutations |
| GSTAB-02 | 64-03-PLAN.md | `agent-brain graph restore-from-snapshot`; doctor stale-graph WARN; `doctor --fix` restores | SATISFIED | `commands/graph.py` with all 3 flags; `_check_graph_staleness` in diagnostics; `apply_safe_fixes` graph_staleness branch |
| GSTAB-03 | 64-02-PLAN.md | `/health/status` entity/relationship counts from live kuzu COUNT(*); 0/100 vs 5677/4366 class gone | SATISFIED | `live_counts()` with TTL cache; wired into `get_status`; `counts_stale` surfaced to health router |
| HOUSE-01 | 64-04-PLAN.md | `GET /mcp/subscriptions` 200 + JSON with truncated session ids, no token, stdio undocumented | SATISFIED | `SUBSCRIPTIONS_PATH` route; `snapshot()` method; no-auth handler; stdio documented not shimmed |

No orphaned requirements — all 4 Phase 64 requirement IDs appear in PLANs and REQUIREMENTS.md marks all 4 `[x]` complete.

---

## Test Coverage

| Test File (actual location) | Tests | Requirement |
|-----------------------------|-------|-------------|
| `tests/indexing/test_graph_isolation.py` | 12 | GSTAB-01 |
| `tests/services/test_indexing_graph_degradation.py` | 8 | GSTAB-01 |
| `tests/unit/storage/test_graph_live_count.py` | 12 | GSTAB-03 |
| `tests/unit/api/test_health_graph_counts.py` | 8 | GSTAB-03 |
| `tests/unit/storage/test_graph_restore_primitive.py` | 11 | GSTAB-02 |
| `agent-brain-cli/tests/commands/test_graph_restore.py` | 8 | GSTAB-02 |
| `agent-brain-cli/tests/test_diagnostics_stale_graph.py` | 12 | GSTAB-02 |
| `agent-brain-mcp/tests/subscriptions/test_manager_snapshot.py` | 6 | HOUSE-01 |
| `agent-brain-mcp/tests/test_http_subscriptions_endpoint.py` | 6 | HOUSE-01 |

Note: Several test files landed under `tests/unit/storage/` and `tests/unit/api/` rather than the `tests/storage/` and `tests/api/` paths declared in the PLAN frontmatter. This is a path placement difference only — the tests exist, are substantive, and (per the `task before-push` gate already confirmed green) pass.

---

## Anti-Patterns Found

None. No TODO/FIXME/PLACEHOLDER patterns, no stub implementations, no empty return values found across the key modified files.

---

## Human Verification Required

### 1. Real kuzu SIGSEGV survival under load

**Test:** Run a sustained GraphRAG indexing job against a large codebase with `graphrag.store_type: kuzu`, then simulate kuzu triggering a native fault (requires a real kuzu binary that can be coaxed into a SIGSEGV under memory pressure).
**Expected:** The server process stays up; the indexing job completes with `graph_degraded: true` in status; vector + BM25 results are queryable.
**Why human:** Requires a real kuzu installation, a large dataset, and real native-crash conditions — the automated tests simulate this with `os._exit(139)` in a controlled subprocess, but real kuzu SIGSEGV under load needs field verification.

### 2. Live `curl /health/status` count accuracy

**Test:** Index a real corpus with `store_type: kuzu`, then `curl http://localhost:8000/health/status` and compare `graph_index.entity_count` / `relationship_count` against a direct kuzu Cypher `MATCH (n) RETURN COUNT(n)` query.
**Expected:** Values match within the ~5s TTL window; second poll within TTL returns the same value without issuing a new kuzu query.
**Why human:** The regression guard (bookkeeping 0/100 vs live 5677/4366) is covered by automated tests, but validating the live production flow against a real kuzu DB with real data requires a running server.

### 3. `agent-brain graph restore-from-snapshot` interactive confirmation

**Test:** With a stale kuzu graph and a valid snapshot on disk, run `agent-brain graph restore-from-snapshot` (no flags) and observe the confirmation prompt; answer `n`; confirm nothing changed; then run again and answer `y`; confirm triplets are restored.
**Expected:** Abort path leaves kuzu unchanged; confirm path logs "Restored N triplets" and kuzu reflects the snapshot contents.
**Why human:** Click CliRunner tests cover the prompt logic, but interactive terminal confirmation flow warrants a real-terminal smoke test.

---

## Summary

Phase 64 goal is achieved. All four success criteria map directly to implemented, substantive, wired code:

- **GSTAB-01**: The server is SIGSEGV-proof for kuzu failures. The `build_from_documents_isolated` function isolates kuzu writes in a `spawn` subprocess — a native crash becomes a catchable non-zero child exit. `GraphBuildFailedError` is caught narrowly in the job pipeline so vector + BM25 results commit even when graph fails. No config mutation occurs.

- **GSTAB-02**: Operators have a full restore workflow. `graph_store.py` exposes `restore_from_snapshot` and `plan_restore` public primitives. The `agent-brain graph restore-from-snapshot` CLI command (confirm-by-default, `--yes`, `--dry-run`, `--snapshot`, server guard) is registered in `cli.py`. `diagnostics.py` WARNs on the stale-graph condition and `apply_safe_fixes` calls `restore_from_snapshot` when the server is stopped.

- **GSTAB-03**: `/health/status` graph counts are now live. `live_counts()` issues real kuzu `COUNT(n)` / `COUNT(r)` queries with a 5-second TTL cache, falls back to last-known counts with `counts_stale=True` on failure (never returns 0/0 when prior counts are known). The fix is wired end-to-end from `graph_store.py` through `graph_index.get_status()` to `indexing_service.get_status()` and the health router.

- **HOUSE-01**: `GET /mcp/subscriptions` is live on the Starlette HTTP app, mounted before the `/mcp` Mount so routing is unambiguous. The route calls `SubscriptionManager.snapshot()` (not `_tasks` directly), returning `transport`, `server_uptime_s`, `active_count`, and `subscriptions[]` with truncated 8-char session IDs. No auth required. Stdio-has-no-endpoint is documented in the constant's docstring, not shimmed.

---

_Verified: 2026-06-14_
_Verifier: Claude (gsd-verifier)_
