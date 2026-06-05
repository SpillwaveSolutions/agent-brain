---
phase: 23-migrate-global-config-from-agent-brain-to-config-agent-brain-uninstall-cleanup
plan: "03"
subsystem: agent-brain-cli
tags: [uninstall, cleanup, cli-command, xdg]
dependency_graph:
  requires: [23-01]
  provides: [uninstall_command]
  affects: [agent-brain-cli]
tech_stack:
  added: []
  patterns: [Click command with --yes/--json flags, SIGTERM server shutdown, Rich Confirm prompt]
key_files:
  created:
    - agent-brain-cli/agent_brain_cli/commands/uninstall.py
    - agent-brain-cli/tests/test_uninstall_command.py
  modified:
    - agent-brain-cli/agent_brain_cli/commands/__init__.py
    - agent-brain-cli/agent_brain_cli/cli.py
decisions:
  - "Use shutil.rmtree(ignore_errors=True) for idempotent removal"
  - "Brief 0.5s sleep after SIGTERM batch for graceful shutdown"
  - "JSON output skips confirmation prompt (same as --yes for scripting)"
  - "LEGACY_DIR imported from xdg_paths.py and patched in tests for isolation"
metrics:
  duration: "~15 min"
  completed: "2026-03-12"
  tasks_completed: 1
  files_created: 2
  files_modified: 2
---

# Phase 23 Plan 03: Uninstall Command Summary

**One-liner:** `agent-brain uninstall` command removes all global XDG + legacy dirs, stops servers via SIGTERM, with confirmation prompt, --yes/--json flags, and 8 passing tests.

## What Was Built

Created `agent-brain-cli/agent_brain_cli/commands/uninstall.py` — the `agent-brain uninstall` command that cleanly removes all global Agent Brain data.

### Command Behavior

1. Collects existing directories: `get_xdg_config_dir()`, `get_xdg_state_dir()`, `LEGACY_DIR`
2. If none exist: reports "Nothing to remove"
3. If `--yes` not set: shows warning listing dirs + `Confirm.ask()` prompt
4. Reads registry, sends SIGTERM to all running server PIDs
5. `shutil.rmtree()` all existing directories (ignoring errors)
6. Reports what was removed (Rich or JSON)
7. Does NOT touch project-level `.claude/agent-brain/` directories

## Commits

| Task | Commit | Files |
|------|--------|-------|
| 1 — uninstall command + registration | e573161 | 4 files |

## Test Results

- 8 tests all pass
- 185 total CLI tests — all green
- mypy: clean
- ruff: clean (fixed B007 unused loop var + E501 line length)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff B007: unused loop variable `project_root` in `_stop_servers`**
- **Found during:** ruff check after implementation
- **Fix:** Renamed to `_project_root` per Python convention
- **Files modified:** `commands/uninstall.py`
- **Commit:** e573161

**2. [Rule 1 - Bug] Ruff E501: three lines exceeded 88 char limit**
- **Found during:** ruff check after implementation
- **Fix:** Split long strings across lines
- **Files modified:** `commands/uninstall.py`
- **Commit:** e573161

## Self-Check

- [x] `agent-brain-cli/agent_brain_cli/commands/uninstall.py` exists
- [x] `agent-brain-cli/tests/test_uninstall_command.py` exists
- [x] Commit e573161 exists in git log
- [x] `agent-brain uninstall --help` shows --yes and --json flags

## Self-Check: PASSED
