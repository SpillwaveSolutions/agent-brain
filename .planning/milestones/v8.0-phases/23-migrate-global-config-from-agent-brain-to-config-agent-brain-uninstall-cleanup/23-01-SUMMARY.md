---
phase: 23-migrate-global-config-from-agent-brain-to-config-agent-brain-uninstall-cleanup
plan: "01"
subsystem: agent-brain-cli
tags: [xdg, migration, paths, config]
dependency_graph:
  requires: []
  provides: [xdg_paths_module]
  affects: [agent-brain-cli]
tech_stack:
  added: []
  patterns: [XDG Base Directory specification, Path.home() dynamic resolution for testability]
key_files:
  created:
    - agent-brain-cli/agent_brain_cli/xdg_paths.py
    - agent-brain-cli/tests/test_xdg_paths.py
  modified: []
decisions:
  - "LEGACY_DIR constant uses Path.home() at module load, but migration functions call Path.home() dynamically to support test mocking"
  - "get_registry_path() uses dynamic Path.home() in legacy fallback for testability"
  - "migrate_legacy_paths() checks if XDG config OR state dir exists (not both) to skip double-migrate"
metrics:
  duration: "~15 min"
  completed: "2026-03-12"
  tasks_completed: 1
  files_created: 2
---

# Phase 23 Plan 01: XDG Path Helpers and Migration Module Summary

**One-liner:** XDG path resolution module with `get_xdg_config_dir`, `get_xdg_state_dir`, `get_registry_path`, `migrate_legacy_paths`, and `LEGACY_DIR` — 15 tests all green.

## What Was Built

Created `agent-brain-cli/agent_brain_cli/xdg_paths.py` — the single source of truth for XDG directory resolution in the Agent Brain CLI. This module is imported by all subsequent plans (23-02, 23-03).

### Public API

| Export | Purpose |
|--------|---------|
| `LEGACY_DIR` | `Path.home() / ".agent-brain"` constant |
| `get_xdg_config_dir()` | Returns `$XDG_CONFIG_HOME/agent-brain` or `~/.config/agent-brain` |
| `get_xdg_state_dir()` | Returns `$XDG_STATE_HOME/agent-brain` or `~/.local/state/agent-brain` |
| `get_registry_path()` | XDG-first registry.json path with legacy fallback |
| `migrate_legacy_paths()` | One-time migration: copy files + delete `~/.agent-brain` |

## Commits

| Task | Commit | Files |
|------|--------|-------|
| 1 — xdg_paths.py + tests | 50e0f0f | agent_brain_cli/xdg_paths.py, tests/test_xdg_paths.py |

## Test Results

- 15 tests all pass
- mypy: clean
- ruff: clean
- black: formatted

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] LEGACY_DIR constant not patchable in tests**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Module-level `LEGACY_DIR = Path.home() / ".agent-brain"` computed at import time — `patch("pathlib.Path.home")` in tests had no effect on already-computed value
- **Fix:** Made `migrate_legacy_paths()` and `get_registry_path()` call `Path.home()` dynamically instead of using the constant, preserving `LEGACY_DIR` as a stable reference for callers
- **Files modified:** `agent_brain_cli/xdg_paths.py`
- **Commit:** 50e0f0f

**2. [Rule 1 - Bug] CliRunner `mix_stderr` not supported**
- **Found during:** Task 1 test refinement
- **Issue:** Click version in this environment doesn't support `CliRunner(mix_stderr=False)`
- **Fix:** Simplified stderr capture using direct `click.echo` mock instead
- **Files modified:** `tests/test_xdg_paths.py`
- **Commit:** 50e0f0f

## Self-Check

- [x] `agent-brain-cli/agent_brain_cli/xdg_paths.py` exists
- [x] `agent-brain-cli/tests/test_xdg_paths.py` exists
- [x] Commit 50e0f0f exists in git log

## Self-Check: PASSED
