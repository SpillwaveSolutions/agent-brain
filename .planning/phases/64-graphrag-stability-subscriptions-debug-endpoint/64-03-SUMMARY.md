---
phase: 64
plan: 03
subsystem: graphrag-restore-cli
tags: [graphrag, kuzu, restore, doctor, cli, diagnostics, gstab-02]
requirements: [GSTAB-02]
dependency_graph:
  requires:
    - agent-brain-server/agent_brain_server/storage/graph_store.py (GraphStoreManager)
    - agent-brain-server/agent_brain_server/storage/graph_snapshot.py (GraphSnapshotManager)
    - agent-brain-cli/agent_brain_cli/diagnostics.py (_graph_index_dir, _read_graphrag_block, _server_is_running)
    - agent-brain-cli/agent_brain_cli/cli.py (add_command registration)
  provides:
    - GraphStoreManager.plan_restore() — dry-run preview of snapshot restore
    - GraphStoreManager.restore_from_snapshot() — on-demand snapshot replay
    - agent-brain graph restore-from-snapshot CLI command
    - _check_graph_staleness() doctor check (WARN on stale)
    - apply_safe_fixes() graph_staleness branch (restore via --fix)
  affects:
    - agent-brain-cli: new 'graph' command group registered in cli.py
    - agent-brain-cli: diagnostics.py extended with stale-graph WARN check
    - agent-brain-server: GraphStoreManager gains 2 public methods
tech_stack:
  added: []
  patterns:
    - TDD red/green per task (3 sets of failing tests committed before implementation)
    - Lazy GraphStoreManager import at module level with try/except ImportError guard
    - Click confirm-by-default pattern (click.confirm with abort=False)
    - Doctor check returning None to skip non-applicable conditions
key_files:
  created:
    - agent-brain-server/tests/unit/storage/test_graph_restore_primitive.py
    - agent-brain-cli/agent_brain_cli/commands/graph.py
    - agent-brain-cli/tests/commands/test_graph_restore.py
    - agent-brain-cli/tests/test_diagnostics_stale_graph.py
  modified:
    - agent-brain-server/agent_brain_server/storage/graph_store.py
    - agent-brain-cli/agent_brain_cli/commands/__init__.py
    - agent-brain-cli/agent_brain_cli/cli.py
    - agent-brain-cli/agent_brain_cli/diagnostics.py
    - agent-brain-mcp/tests/test_http_subscriptions_endpoint.py (pre-existing fmt fix)
    - agent-brain-mcp/tests/subscriptions/test_manager_snapshot.py (pre-existing fmt fix)
decisions:
  - "plan_restore + restore_from_snapshot added as public GraphStoreManager methods;
     private _restore_from_snapshot_if_available gated on corruption flag preserved as-is"
  - "GraphStoreManager imported at module level in diagnostics.py and commands/graph.py
     (agent-brain-rag is a declared dep) to enable clean test patching"
  - "_get_live_kuzu_relationship_count() extracted as a separate helper so tests can
     patch it without needing a real kuzu database"
  - "apply_safe_fixes graph_staleness branch handles ImportError and exceptions gracefully
     (records action message, does not re-raise) matching existing --fix philosophy"
metrics:
  duration_minutes: 17
  completed_date: "2026-06-14"
  tasks_completed: 4
  tasks_total: 4
  files_created: 4
  files_modified: 8
  tests_added: 31
---

# Phase 64 Plan 03: Graph Restore CLI + Doctor Stale-Graph Check Summary

**One-liner:** On-demand kuzu snapshot restore via `agent-brain graph restore-from-snapshot` + `doctor --fix`, with stale-graph WARN check added to `agent-brain doctor`.

## What Was Built

**Task 1 — GraphStoreManager.plan_restore + restore_from_snapshot primitives**

Added two public methods to `GraphStoreManager` in `graph_store.py`:

- `plan_restore(snapshot_path=None)` — returns `(path, triplet_count)` WITHOUT mutating the store; backs `--dry-run`; returns `None` when no snapshot exists.
- `restore_from_snapshot(snapshot_path=None)` — replays snapshot triplets on demand, calls `initialize()` if needed, updates `_relationship_count` / `_last_updated`, calls `persist()`. Does NOT check `_recovered_from_corruption` — any operator can invoke it explicitly.

Both use `GraphSnapshotManager(self.persist_dir)`. `snapshot_path=None` uses `load_latest_valid()`; an explicit path uses `load()` (raising `ValueError`/`OSError` on bad files).

**Task 2 — `agent-brain graph restore-from-snapshot` CLI command**

New `commands/graph.py` with `graph_group` (Click group) and `restore-from-snapshot` subcommand:

- `--snapshot PATH` — target a specific file; defaults to latest valid on disk
- `--dry-run` — preview (calls `plan_restore`, skips `restore_from_snapshot`)
- `--yes` — skip confirmation prompt for CI/non-interactive
- Default: prints restore plan (`N triplets from <snapshot> into <kuzu_db>`) then prompts `Proceed with restore? [y/N]`
- Server guard: refuses with actionable message if `_server_is_running(state_dir)` is True
- No-snapshot: reports "No snapshot available" and exits 1

Registered in `commands/__init__.py` and `cli.py` as `cli.add_command(graph_group, name="graph")`.

**Task 3 — Doctor stale-graph WARN check + --fix restore**

Extended `diagnostics.py`:

- `_get_live_kuzu_relationship_count(graph_dir)` — opens kuzu DB read-only, runs `MATCH ()-[r]->() RETURN COUNT(r)`; returns `None` on any failure.
- `_check_graph_staleness(state_dir)` — compares snapshot triplet count vs live kuzu count. Returns `SEVERITY_WARN` when `snapshot_count > live_count` (with fix hint naming `agent-brain graph restore-from-snapshot`), `SEVERITY_OK` when consistent, `None` when not applicable.
- `run_doctor()` — appends staleness check after `graph_store_health` check.
- `apply_safe_fixes()` — new `graph_staleness` WARN branch calls `mgr.restore_from_snapshot(None)`; skips with message if server is running.

**Task 4 — Validation gate**

`task before-push` from repo root exits 0: 556 passed, 111 deselected, 7 warnings.

Pre-existing Black + Ruff issues in two MCP test files were fixed as a blocking deviation (Rule 3).

## Commits

| Hash | Type | Description |
|------|------|-------------|
| `1305219` | test | RED: failing tests for restore_from_snapshot + plan_restore primitives (11 tests) |
| `86d6300` | feat | GREEN: add public restore_from_snapshot + plan_restore to GraphStoreManager |
| `bf29dcf` | test | RED: failing tests for graph restore-from-snapshot CLI command (8 tests) |
| `97d37d0` | feat | GREEN: add 'agent-brain graph restore-from-snapshot' CLI command |
| `c80a44a` | test | RED: failing tests for doctor stale-graph WARN check + --fix (12 tests) |
| `1c15d93` | feat | GREEN: add doctor stale-graph WARN check + --fix restore action |
| `cddef68` | chore | fix pre-existing Black/Ruff issues in MCP test files (validation gate) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Pre-existing Black + Ruff failures in MCP test files**
- **Found during:** Task 4 (before-push gate)
- **Issue:** `agent-brain-mcp/tests/test_http_subscriptions_endpoint.py` and `tests/subscriptions/test_manager_snapshot.py` had Black formatting violations and 3 unused imports (Ruff F401). These were pre-existing (no changes from HEAD).
- **Fix:** `poetry run black` + `poetry run ruff check --fix` on those two files.
- **Files modified:** `agent-brain-mcp/tests/test_http_subscriptions_endpoint.py`, `agent-brain-mcp/tests/subscriptions/test_manager_snapshot.py`
- **Commit:** `cddef68`

**2. [Rule 1 - Design deviation] Module-level GraphStoreManager import**
- **Found during:** Task 2 (test patching issue)
- **Issue:** Plan said "import lazily inside the command body" but lazy import makes `patch("...GraphStoreManager")` fail in tests. Since `agent-brain-rag` IS a declared dependency, module-level import is correct.
- **Fix:** Changed to module-level `try/except ImportError` import in both `commands/graph.py` and `diagnostics.py`.
- **Impact:** Cleaner patching; no runtime behavior change.

## Test Coverage

| File | Tests | Classes |
|------|-------|---------|
| `test_graph_restore_primitive.py` | 11 | TestRestoreFromSnapshotLatest, ExplicitPath, NoSnapshot, PlanRestore, CorruptionFlag |
| `test_graph_restore.py` | 8 | TestDryRun, YesFlag, InteractivePrompt, ExplicitSnapshotPath, ServerRunningGuard, NoSnapshotAvailable, HelpOutput |
| `test_diagnostics_stale_graph.py` | 12 | TestCheckGraphStalenessWarn, Ok, Skipped, TestRunDoctorIncludesStalenessCheck, TestApplySafeFixesGraphStaleness |
| **Total** | **31** | |

## Acceptance Criteria Verification

- `graph_store.py` contains `def restore_from_snapshot(self, snapshot_path: Path | None = None) -> int:` — YES
- `graph_store.py` contains `def plan_restore(self, snapshot_path: Path | None = None)` — YES
- `restore_from_snapshot` does NOT reference `_recovered_from_corruption` as a guard — YES
- `commands/graph.py` contains `def restore_from_snapshot` AND `@graph_group.command("restore-from-snapshot")` — YES
- `commands/graph.py` contains `--dry-run`, `--yes`, `--snapshot` — YES
- `cli.py` contains `graph_group` in import AND `cli.add_command(graph_group, name="graph")` — YES
- `commands/graph.py` contains server-running guard (`_server_is_running`) — YES
- `diagnostics.py` contains `def _check_graph_staleness(state_dir: Path) -> CheckResult | None:` — YES
- `diagnostics.py` `run_doctor` contains `_check_graph_staleness(state_dir)` — YES
- `diagnostics.py` `apply_safe_fixes` contains `check.name == "graph_staleness"` — YES
- `diagnostics.py` `apply_safe_fixes` `graph_staleness` branch calls `restore_from_snapshot` — YES
- `task before-push` from repo root exits 0 — YES (556 passed)

## Self-Check: PASSED

All 5 created files confirmed on disk. All 7 commits confirmed in git log.
