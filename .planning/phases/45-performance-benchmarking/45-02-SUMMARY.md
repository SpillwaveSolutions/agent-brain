---
phase: 45-performance-benchmarking
plan: 02
subsystem: scripts/benchmark
tags: [benchmark, testing, mode-support-matrix, unit-tests]
dependency_graph:
  requires: []
  provides: [MODE_SUPPORT_MATRIX, get_mode_support, benchmark-helper-tests]
  affects: [scripts/query_benchmark.py, agent-brain-server/tests]
tech_stack:
  added: []
  patterns: [data-structure-matrix, unit-test-class-per-function]
key_files:
  created:
    - scripts/benchmark_queries.json
    - agent-brain-server/tests/unit/test_benchmark_helpers.py
  modified:
    - scripts/query_benchmark.py
decisions:
  - "Used explicit MODE_SUPPORT_MATRIX dict (4 keys x 5 modes) rather than implicit HTTP error detection"
  - "Benchmark loop always iterates DEFAULT_MODES (not user --modes arg) to guarantee 5-row output"
  - "Skipped modes (not in --modes) get 'skipped' status distinct from 'unsupported'"
  - "Test file imports from scripts/ via sys.path.insert for zero-packaging overhead"
metrics:
  duration_minutes: 22
  completed_date: "2026-03-27"
  tasks_completed: 2
  files_changed: 3
---

# Phase 45 Plan 02: Mode Support Matrix and Benchmark Helper Tests Summary

MODE_SUPPORT_MATRIX data structure added to query_benchmark.py with 4 backend/graph configs x 5 modes, guaranteeing exactly 5 rows per benchmark run; 36 unit tests added for all helper functions.

## Tasks Completed

| # | Name | Commit | Key Files |
|---|------|--------|-----------|
| 1 | Add MODE_SUPPORT_MATRIX and guarantee exactly 5 rows | 8b41cdd | scripts/query_benchmark.py |
| 2 | Add unit tests for benchmark helper functions | fdc9415 | agent-brain-server/tests/unit/test_benchmark_helpers.py |
| - | Commit benchmark_queries.json | 4b30eba | scripts/benchmark_queries.json |

## What Was Built

### Task 1: MODE_SUPPORT_MATRIX

Added an explicit `MODE_SUPPORT_MATRIX` constant near the top of `scripts/query_benchmark.py`. The matrix is a `dict[tuple[str, bool], dict[str, tuple[bool, str]]]` mapping `(backend, graph_enabled)` to per-mode `(supported, reason)` entries.

Four backend/graph configurations:
- `("chroma", True)` — all 5 modes supported
- `("chroma", False)` — `graph` unsupported ("UNSUPPORTED: requires GraphRAG")
- `("postgres", True)` — `graph` unsupported ("UNSUPPORTED: Chroma-only"); `multi` annotated ("graph contribution absent")
- `("postgres", False)` — same as postgres+True

Added `get_mode_support(backend, graph_enabled, mode)` helper function that performs the matrix lookup with unknown-backend fallback (returns `(True, "")` for unknown backends).

Updated the `main()` benchmark loop to:
1. Always iterate all 5 `DEFAULT_MODES` (not the user's `--modes` list)
2. Mark modes not in `--modes` as `"skipped"` status
3. Short-circuit unsupported modes via matrix lookup without hitting the HTTP endpoint
4. Propagate matrix annotations (supported=True but non-empty reason) to result dicts

Updated `print_results_table()` to render `"skipped"` status with dimmed display.

### Task 2: Unit Tests

Created `agent-brain-server/tests/unit/test_benchmark_helpers.py` with 36 tests across 6 test classes:

| Class | Tests | Coverage |
|-------|-------|----------|
| TestComputeStats | 7 | empty list, single value, p50, QPS, min/max, count, keys |
| TestFormatModeStatus | 4 | ok, unsupported+reason, error, keys present |
| TestBuildRunMetadata | 5 | required fields, ISO date, backend, chunk_count, corpus_identity |
| TestGetModeSupport | 9 | all combos, None treatment, case-insensitive backend |
| TestModeSupportMatrix | 5 | entry count, mode count per entry, key presence, tuple types |
| TestBuildJsonOutput | 6 | required keys, unsupported listing, supported listing, rows count |

The test file imports from `scripts/` via `sys.path.insert(0, str(Path(...) / "scripts"))` — no packaging required.

## Decisions Made

1. **Explicit matrix over implicit HTTP detection** — MODE_SUPPORT_MATRIX is a named data structure that makes backend/mode compatibility clear and testable, rather than relying on HTTP 4xx responses.

2. **5-row guarantee via DEFAULT_MODES iteration** — The benchmark loop always iterates all 5 DEFAULT_MODES, with user-requested subset producing "skipped" rows for unrequested modes. This ensures output always has exactly 5 rows.

3. **Skipped vs Unsupported distinction** — "unsupported" = matrix says the mode doesn't work on this backend; "skipped" = user excluded the mode via --modes flag. Semantically distinct.

4. **Test import via sys.path** — Rather than packaging the benchmark script, tests use `sys.path.insert` pointing at `scripts/`. This avoids cross-package dependencies and keeps the script standalone.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

### Files exist
- [x] `scripts/query_benchmark.py` — present, contains MODE_SUPPORT_MATRIX
- [x] `scripts/benchmark_queries.json` — present, 20 queries committed
- [x] `agent-brain-server/tests/unit/test_benchmark_helpers.py` — present, 36 tests

### Commits exist
- [x] `8b41cdd` — feat(45-02): add MODE_SUPPORT_MATRIX and guarantee 5-row benchmark output
- [x] `fdc9415` — test(45-02): add unit tests for benchmark helper functions
- [x] `4b30eba` — chore(45-02): commit benchmark_queries.json fixed query set

### Tests pass
- [x] `poetry run pytest tests/unit/test_benchmark_helpers.py -v` — 36/36 passed
- [x] `python scripts/query_benchmark.py --help` — exits 0

## Self-Check: PASSED
