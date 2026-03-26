---
phase: 44-config-validation-tooling
plan: "02"
subsystem: agent-brain-cli
tags: [config, migration, cli, tdd, diff, wizard]
dependency_graph:
  requires: [config-validation-engine, config-validate-command]
  provides: [config-migration-engine, config-migrate-command, config-diff-command, wizard-validation]
  affects: [agent-brain-cli/agent_brain_cli/commands/config.py]
tech_stack:
  added: []
  patterns: [versioned-migration-steps, dataclass-result, unified-diff, tdd-red-green]
key_files:
  created:
    - agent-brain-cli/agent_brain_cli/config_migrate.py
    - agent-brain-cli/tests/test_config_migrate.py
  modified:
    - agent-brain-cli/agent_brain_cli/commands/config.py
decisions:
  - "Used MIGRATIONS list of callables for easy extensibility — adding new migrations is a single list append"
  - "diff_config operates on dicts (not files) and calls migrate_config internally — single source of truth for migration logic"
  - "Wizard validation added at both START (existing config check) and END (post-write check) to cover upgrade and first-run scenarios"
  - "dry-run in migrate command delegates to diff_config_file rather than duplicating logic"
metrics:
  duration_seconds: 172
  completed_date: "2026-03-26"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 1
---

# Phase 44 Plan 02: Config Migration Engine and CLI Commands Summary

**One-liner:** Versioned YAML config migration engine with `config migrate` (in-place upgrade), `config diff` (colored preview), and wizard validation integration for pre-flight config checks.

## What Was Built

A config migration module (`config_migrate.py`) with a registry of versioned migration functions, plus `agent-brain config migrate` and `agent-brain config diff` CLI commands. The setup wizard now validates existing and newly-written configs, warning the user before proceeding with invalid settings.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Config migration engine (TDD) | 669e6e6 | config_migrate.py, test_config_migrate.py (RED: 5352f20) |
| 2 | migrate/diff CLI commands + wizard integration | 5fa47c3 | commands/config.py |

## Artifacts

### agent-brain-cli/agent_brain_cli/config_migrate.py (NEW)

Exports:
- `MigrationResult` — dataclass with `original`, `migrated`, `changes`, `already_current`
- `MIGRATIONS` — list of `MigrationFn` callables applied in order
- `_migrate_use_llm_extraction` — migrates `graphrag.use_llm_extraction` bool -> `graphrag.doc_extractor` str
- `migrate_config(config: dict) -> MigrationResult` — in-memory migration
- `migrate_config_file(path: Path) -> MigrationResult` — reads YAML, migrates, writes back if changed
- `diff_config(config: dict) -> str` — unified diff string (empty if no changes)
- `diff_config_file(path: Path) -> str` — file-based wrapper for diff_config

### agent-brain-cli/agent_brain_cli/commands/config.py (MODIFIED)

Added:
- `@config_group.command("migrate")` with `--file` and `--dry-run` options
- `@config_group.command("diff")` with `--file` option (colored output: red for `-`, green for `+`, cyan for `@@`)
- Import block: `from agent_brain_cli.config_migrate import MigrationResult, diff_config_file, migrate_config_file`
- Wizard start: validates existing config and prints warnings if errors found
- Wizard end: validates post-write config, prompts user to confirm or abort on errors

### agent-brain-cli/tests/test_config_migrate.py (NEW — 18 tests)

- `TestMigrateConfigDict` (6 tests) — migrate_config unit tests
- `TestDiffConfigDict` (2 tests) — diff_config unit tests
- `TestMigrateConfigFile` (2 tests) — file-based migration and diff
- `TestMigrateCliCommand` (4 tests) — CLI migrate command including --dry-run
- `TestDiffCliCommand` (3 tests) — CLI diff command
- `TestWizardValidationIntegration` (1 test) — wizard warns on post-write validation errors

## Verification Results

```
poetry run pytest tests/test_config_migrate.py tests/test_config_validate.py tests/test_config_commands.py -v
# 48 passed in 0.18s

poetry run mypy agent_brain_cli/config_migrate.py agent_brain_cli/config_schema.py agent_brain_cli/commands/config.py
# Success: no issues found in 3 source files

poetry run ruff check agent_brain_cli/config_migrate.py agent_brain_cli/config_schema.py agent_brain_cli/commands/config.py
# All checks passed!
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Style] f-string without placeholder in wizard warning**
- **Found during:** Task 2, ruff check
- **Issue:** `f"\n[bold yellow]Warning:[/] Existing config has validation issues:"` — f-prefix unnecessary, ruff F541
- **Fix:** Removed `f` prefix
- **Files modified:** commands/config.py
- **Commit:** 5fa47c3 (incorporated)

**2. [Rule 1 - Style] Line too long in --dry-run option decorator**
- **Found during:** Task 2, ruff check (E501, 89 > 88 chars)
- **Issue:** `@click.option("--dry-run", is_flag=True, help="Show what would change without modifying")` was 89 chars
- **Fix:** Wrapped decorator across two lines using multi-line form
- **Files modified:** commands/config.py
- **Commit:** 5fa47c3 (incorporated)

**3. [Rule 1 - Style] Import block unsorted in config_migrate.py**
- **Found during:** Task 1, ruff check (I001)
- **Fix:** `ruff check --fix` applied automatically
- **Files modified:** config_migrate.py
- **Commit:** 669e6e6 (incorporated)

No architectural deviations — plan executed as written.

## Self-Check: PASSED
