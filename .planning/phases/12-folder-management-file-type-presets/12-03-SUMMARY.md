---
phase: 12-folder-management-file-type-presets
plan: "03"
subsystem: cli-plugin
tags: [cli, folders, file-type-presets, plugin, phase-12]
dependency_graph:
  requires: ["12-02"]
  provides: ["cli-folders-commands", "cli-types-commands", "plugin-slash-commands"]
  affects: ["agent-brain-cli", "agent-brain-plugin"]
tech_stack:
  added:
    - "Click command groups (folders, types)"
    - "Rich tables for folder/preset display"
  patterns:
    - "CLI command group pattern (Click @group + @command)"
    - "Hardcoded presets in CLI to avoid cross-package dependency"
    - "Isolated filesystem tests for folder add command"
key_files:
  created:
    - agent-brain-cli/agent_brain_cli/commands/folders.py
    - agent-brain-cli/agent_brain_cli/commands/types.py
    - agent-brain-cli/tests/test_folders_cli.py
    - agent-brain-cli/tests/test_types_cli.py
    - agent-brain-plugin/commands/agent-brain-folders.md
    - agent-brain-plugin/commands/agent-brain-types.md
  modified:
    - agent-brain-cli/agent_brain_cli/client/api_client.py
    - agent-brain-cli/agent_brain_cli/client/__init__.py
    - agent-brain-cli/agent_brain_cli/commands/__init__.py
    - agent-brain-cli/agent_brain_cli/commands/index.py
    - agent-brain-cli/agent_brain_cli/cli.py
    - agent-brain-server/tests/test_folders_api.py
    - agent-brain-server/tests/test_folder_manager.py
    - agent-brain-server/tests/test_include_types.py
decisions:
  - "Hardcode FILE_TYPE_PRESETS in CLI to avoid agent-brain-server cross-package dependency"
  - "folders add is alias for index (idempotent re-indexing per FOLD-09)"
  - "folder_path for remove uses type=str not click.Path to allow non-existent disk paths"
metrics:
  duration: "~10 minutes"
  completed: "2026-02-25"
  tasks_completed: 3
  files_created: 6
  files_modified: 8
  tests_added: 35
---

# Phase 12 Plan 03: CLI Folders, Types Commands, and Plugin Slash Commands Summary

**One-liner:** CLI `folders` and `types` command groups with Rich table output, `--include-type` flag for index, and plugin slash commands for folder management.

## What Was Built

Complete user-facing CLI interface for Phase 12 folder management and file type presets:

### 1. DocServeClient Extensions (`api_client.py`)

- Added `FolderInfo` dataclass with `folder_path`, `chunk_count`, `last_indexed` fields
- Added `list_folders() -> list[FolderInfo]` — calls `GET /index/folders/`
- Added `delete_folder(folder_path) -> dict` — calls `DELETE /index/folders/`
- Updated `index()` to accept `include_types: list[str] | None` — passes to server JSON body
- Exported `FolderInfo` from `client/__init__.py`

### 2. `commands/folders.py` — Folders Command Group

Three subcommands under `agent-brain folders`:

| Subcommand | Description |
|------------|-------------|
| `list` | Rich table: Folder Path, Chunks, Last Indexed |
| `add` | Alias for indexing — queues job, shows job ID |
| `remove` | Prompts for confirmation (skippable with `--yes`), shows chunks deleted |

Error handling covers: 404 (folder not indexed), 409 (active job conflict), ConnectionError, ServerError.

### 3. `commands/types.py` — Types Command Group

Single subcommand `agent-brain types list`:
- Local command — no server connection required
- Hardcoded `FILE_TYPE_PRESETS` dict (matches `agent_brain_server/services/file_type_presets.py`)
- Rich table: Preset, Extensions
- JSON output with `--json`

### 4. Index Command `--include-type` Flag

Added to `commands/index.py`:
```
--include-type TEXT  Comma-separated file type presets to include
                     (e.g., python,docs,typescript).
                     Use 'agent-brain types list' to see all available presets.
```
Parses comma-separated preset names, passes `include_types=list` to `client.index()`.
Shows preset names in Rich output when specified.

### 5. CLI Registration (`cli.py`, `commands/__init__.py`)

Registered `folders_group` and `types_group` with main `cli` group. Updated help text to document all new commands.

### 6. Plugin Slash Commands

- `agent-brain-plugin/commands/agent-brain-folders.md` — `/agent-brain-folders list|add|remove`
- `agent-brain-plugin/commands/agent-brain-types.md` — `/agent-brain-types`

Both follow the existing plugin command format with frontmatter, purpose, usage, execution steps, and error handling tables.

## Tests

35 new tests across 2 test files:

| File | Tests | Coverage |
|------|-------|----------|
| `test_folders_cli.py` | 21 | 89% of `folders.py` |
| `test_types_cli.py` | 14 | 100% of `types.py` |

All tests pass. Total CLI test suite: 121 tests.

## Quality Gate

- `task before-push` exits 0
- Server: 756 tests pass, 74% coverage
- CLI: 121 tests pass, 58% total coverage (above 50% threshold)
- mypy strict: 0 errors in 18 CLI source files
- ruff: 0 errors (5 pre-existing errors auto-fixed in server tests)
- black: all files formatted

## Help Output Verification

All XCUT-03 requirements verified:
- `agent-brain folders --help` — shows list, add, remove with examples
- `agent-brain folders list --help` — shows --json option
- `agent-brain folders add --help` — shows FOLDER_PATH, --include-code
- `agent-brain folders remove --help` — shows FOLDER_PATH, --yes
- `agent-brain types --help` — shows list subcommand
- `agent-brain types list --help` — shows --json and --include-type examples
- `agent-brain index --help` — shows --include-type option

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing ruff lint errors in server test files**
- **Found during:** Task 3 (task before-push run)
- **Issue:** 6 ruff errors in `test_folders_api.py`, `test_folder_manager.py`, `test_include_types.py` from Plans 01/02 execution — unused imports, unused variable, unnecessary open mode parameter
- **Fix:** 5 auto-fixed with `ruff check --fix`, 1 removed manually (`data = response.json()` unused assignment)
- **Files modified:** `tests/test_folders_api.py`, `tests/test_folder_manager.py`, `tests/test_include_types.py`
- **Commit:** 47cb99a

**2. [Rule 2 - Format] Black formatting for `folders.py`**
- **Found during:** Task 2 ruff/black check
- **Issue:** `black --check` found one formatting inconsistency in `folders.py`
- **Fix:** `poetry run black agent_brain_cli/commands/folders.py`
- **Files modified:** `agent_brain_cli/commands/folders.py`
- **Commit:** included in feat(12-03)

## Commits

| Hash | Message |
|------|---------|
| c37b562 | feat(12-03): add folders/types CLI commands and extend DocServeClient |
| bf7e0fd | feat(12-03): add --include-type to index command and plugin slash commands |
| 47cb99a | fix(12-03): resolve pre-existing ruff lint errors in server tests |

## Self-Check: PASSED

All created files confirmed to exist on disk. All commits confirmed in git history.

| Check | Status |
|-------|--------|
| `folders.py` created | PASSED |
| `types.py` created | PASSED |
| `test_folders_cli.py` created | PASSED |
| `test_types_cli.py` created | PASSED |
| `agent-brain-folders.md` created | PASSED |
| `agent-brain-types.md` created | PASSED |
| commit c37b562 exists | PASSED |
| commit bf7e0fd exists | PASSED |
| commit 47cb99a exists | PASSED |
