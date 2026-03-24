---
phase: 41-bug-fixes-and-reliability
plan: 01
subsystem: server-lifespan, storage-paths, test-coverage
tags: [bugfix, reliability, storage-paths, telemetry, regression-tests]
dependency_graph:
  requires: []
  provides: [BUGFIX-01-locked, BUGFIX-02-fixed, BUGFIX-03-locked, BUGFIX-04-locked]
  affects: [agent-brain-server/api/main.py, agent-brain-server/config/settings.py]
tech_stack:
  added: []
  patterns: [guaranteed-state-dir-fallback, source-inspection-tests, cross-package-test-placement]
key_files:
  created:
    - agent-brain-server/tests/unit/test_lifespan_path_resolution.py
    - agent-brain-server/tests/unit/test_bugfix_regressions.py
    - agent-brain-cli/tests/test_bugfix01_start_timeout.py
  modified:
    - agent-brain-server/agent_brain_server/api/main.py
    - agent-brain-server/agent_brain_server/config/settings.py
decisions:
  - "Place BUGFIX-01 regression test in agent-brain-cli/tests/ to avoid cross-venv import of agent_brain_cli"
  - "Use direct file source inspection (Path.read_text) for regression tests instead of inspect.getsource to avoid torch/pydantic patching issues"
  - "Add guaranteed fallback in lifespan except block so state_dir is always non-None"
  - "Replace tier-3 CWD-relative else branch with RuntimeError (unreachable dead code)"
metrics:
  duration: 8m
  completed_date: "2026-03-24"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 2
  tests_added: 21
---

# Phase 41 Plan 01: Bug Fixes and Reliability Summary

**One-liner:** Guaranteed state_dir resolution via lifespan hardening (BUGFIX-02) plus regression tests locking down start-timeout-120, telemetry suppression, and Gemini google-genai migration.

## What Was Built

### Task 1: Fix state_dir path resolution (BUGFIX-02)

Fixed the lifespan path resolution in `agent_brain_server/api/main.py` to guarantee `state_dir` is always non-None:

1. **Guaranteed fallback in except block:** When `resolve_state_dir(Path.cwd())` raises, the except block now sets `state_dir = Path.cwd() / ".agent-brain"` and calls `resolve_storage_paths(state_dir)` — instead of silently leaving `state_dir` as `None`.

2. **Runtime assertion:** Added `assert state_dir is not None, "state_dir must be resolved by lifespan"` after the if/elif block.

3. **Unreachable tier-3 replaced with RuntimeError:** The old tier-3 else branch (`chroma_dir = str(Path(settings.CHROMA_PERSIST_DIR).resolve())`) — which used CWD-relative `./chroma_db` — is replaced with `raise RuntimeError("Storage path resolution failed: state_dir is unexpectedly None")`.

4. **Legacy comments in settings.py:** Added `# Legacy CWD-relative defaults — only used when state_dir resolution fails completely.` above `CHROMA_PERSIST_DIR`, `BM25_INDEX_PATH`, and `GRAPH_INDEX_PATH`.

### Task 2: Regression tests for BUGFIX-01, BUGFIX-03, BUGFIX-04

**BUGFIX-01 (start --timeout default=120):**
- `agent-brain-cli/tests/test_bugfix01_start_timeout.py`: 3 tests verifying `start_command` has `--timeout` parameter with `default=120` and help text mentioning "120".

**BUGFIX-03 (ChromaDB telemetry suppression):**
- `agent-brain-server/tests/unit/test_bugfix_regressions.py`: 5 tests verifying:
  - `ANONYMIZED_TELEMETRY` env var is set via `os.environ.setdefault`
  - `posthog` and `chromadb.telemetry` loggers are suppressed in main.py
  - `VectorStoreManager` passes `anonymized_telemetry=False` to `ChromaSettings`

**BUGFIX-04 (Gemini google-genai migration):**
- 3 tests verifying `gemini.py` uses `import google.genai`, not `google.generativeai`, and `pyproject.toml` lists `google-genai`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] BUGFIX-01 test placed in CLI tests, not server tests**
- **Found during:** Task 2 setup
- **Issue:** Plan noted BUGFIX-01 test imports `agent_brain_cli` but the plan said to place it in `agent-brain-server/tests/`. The server venv does not have `agent_brain_cli` installed.
- **Fix:** Placed test in `agent-brain-cli/tests/test_bugfix01_start_timeout.py` (per important_note in execution prompt).
- **Files modified:** `agent-brain-cli/tests/test_bugfix01_start_timeout.py` (new)

**2. [Rule 1 - Bug] Used `Path.read_text()` instead of `inspect.getsource()` for source inspection tests**
- **Found during:** Task 1 RED phase
- **Issue:** `inspect.getsource(settings_module)` fails because `settings_module.settings` is a Pydantic Settings instance, not a module — torch patches `getfile` and `TypeError` results.
- **Fix:** Changed all source inspection tests to read files directly: `Path(__file__).parent.../module.py).read_text()`.
- **Files modified:** `test_lifespan_path_resolution.py`, `test_bugfix_regressions.py`

**3. [Rule 2 - Missing] Line-length and unused import fixes**
- **Found during:** `task before-push`
- **Issue:** 13 ruff E501 errors and 1 unused import in test files + 1 in main.py comment.
- **Fix:** Rewrote docstrings to fit 88 chars, removed unused `from unittest.mock import patch`, fixed main.py comment length.

## Test Results

- **Server tests:** 999 passed, 23 skipped
- **CLI tests:** 294 passed
- **New regression tests added:** 21 (10 lifespan path + 8 bugfix regressions + 3 CLI timeout)
- **`task before-push`:** PASSED (format, lint, typecheck, all tests)

## Commits

| Hash | Description |
|------|-------------|
| 04b2f3d | fix(41-01): harden state_dir resolution to eliminate CWD-relative fallback (BUGFIX-02) |
| 48816cf | test(41-01): add regression tests for BUGFIX-01, BUGFIX-03, BUGFIX-04 |
| 459e13f | fix(41-01): fix lint/format issues after before-push check |

## Self-Check

- [x] `agent-brain-server/tests/unit/test_lifespan_path_resolution.py` created
- [x] `agent-brain-server/tests/unit/test_bugfix_regressions.py` created
- [x] `agent-brain-cli/tests/test_bugfix01_start_timeout.py` created
- [x] `agent-brain-server/agent_brain_server/api/main.py` modified (assert + RuntimeError)
- [x] `agent-brain-server/agent_brain_server/config/settings.py` modified (legacy comments)
- [x] All 4 acceptance criteria pass
- [x] `task before-push` exits with code 0
