---
phase: 23-migrate-global-config-from-agent-brain-to-config-agent-brain-uninstall-cleanup
plan: "02"
subsystem: agent-brain-cli, agent-brain-server
tags: [xdg, migration, config, registry, deprecation]
dependency_graph:
  requires: [23-01]
  provides: [xdg_callers_updated]
  affects: [agent-brain-cli, agent-brain-server]
tech_stack:
  added: []
  patterns: [XDG-first config search, deprecation warnings via sys.stderr/logger.warning]
key_files:
  created: []
  modified:
    - agent-brain-cli/agent_brain_cli/config.py
    - agent-brain-cli/agent_brain_cli/commands/config.py
    - agent-brain-cli/agent_brain_cli/commands/start.py
    - agent-brain-cli/agent_brain_cli/commands/stop.py
    - agent-brain-cli/agent_brain_cli/commands/list_cmd.py
    - agent-brain-cli/agent_brain_cli/commands/init.py
    - agent-brain-server/agent_brain_server/config/provider_config.py
    - agent-brain-server/agent_brain_server/storage_paths.py
    - agent-brain-cli/tests/test_config.py
    - agent-brain-cli/tests/test_multi_instance_commands.py
decisions:
  - "Server provider_config.py inlines XDG logic (cannot import from CLI package)"
  - "Deprecation warning in CLI uses sys.stderr.write() for minimal import overhead"
  - "Deprecation warning in server uses logger.warning() (consistent with server logging)"
  - "Legacy fallback paths intentionally remain in config search (steps 5/6) to preserve backward compat"
  - "storage_paths.resolve_shared_project_dir now respects AGENT_BRAIN_SHARED_DIR then XDG_DATA_HOME"
metrics:
  duration: "~20 min"
  completed: "2026-03-12"
  tasks_completed: 2
  files_modified: 10
---

# Phase 23 Plan 02: XDG Caller Migration and Deprecation Warnings Summary

**One-liner:** All CLI commands and server config flipped to XDG-first search order with legacy `~/.agent-brain` fallback + deprecation warning, migration triggered on `start` and `init`.

## What Was Built

### Task 1: Config search priority flip + deprecation warnings

Updated three `_find_config_file()` functions to check XDG paths before legacy:

| File | Before | After |
|------|--------|-------|
| `agent_brain_cli/config.py` | legacy (step 4), XDG (step 5) | XDG (step 4), legacy (step 5) + warning |
| `commands/config.py` | legacy (step 5), XDG (step 6) | XDG (step 5), legacy (step 6) + warning |
| `server/config/provider_config.py` | legacy (step 5), XDG (step 6) | XDG (step 5), legacy (step 6) + warning |

### Task 2: Registry paths + migration triggers + server storage_paths

| File | Change |
|------|--------|
| `commands/start.py` | `migrate_legacy_paths()` + `get_xdg_state_dir()` for registry |
| `commands/init.py` | `migrate_legacy_paths()` call added |
| `commands/stop.py` | `get_registry_path()` for registry |
| `commands/list_cmd.py` | `get_registry_path()` + `get_xdg_state_dir()` |
| `server/storage_paths.py` | XDG_DATA_HOME / AGENT_BRAIN_SHARED_DIR support |

## Commits

| Tasks | Commit | Files |
|-------|--------|-------|
| 1+2 — config priority + registry XDG | 9ff2275 | 10 files |

## Test Results

- 42 CLI tests all pass (21 config + 21 multi-instance)
- mypy: clean on all 8 modified source files
- ruff: clean on all 8 modified source files

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check

- [x] Commit 9ff2275 exists
- [x] No hardcoded `~/.agent-brain` registry writes remain outside xdg_paths.py
- [x] Legacy fallback with deprecation warning in all three `_find_config_file()` implementations
- [x] `migrate_legacy_paths()` called in both `start_command` and `init_command`

## Self-Check: PASSED
