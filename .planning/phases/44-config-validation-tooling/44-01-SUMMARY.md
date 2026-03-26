---
phase: 44-config-validation-tooling
plan: "01"
subsystem: agent-brain-cli
tags: [config, validation, cli, tdd, schema]
dependency_graph:
  requires: []
  provides: [config-validation-engine, config-validate-command]
  affects: [agent-brain-cli/agent_brain_cli/commands/config.py]
tech_stack:
  added: []
  patterns: [dataclass-validation, tdd-red-green, yaml-line-tracking]
key_files:
  created:
    - agent-brain-cli/agent_brain_cli/config_schema.py
    - agent-brain-cli/tests/test_config_validate.py
  modified:
    - agent-brain-cli/agent_brain_cli/commands/config.py
decisions:
  - "Used dataclass for ConfigValidationError instead of Pydantic to keep validation engine zero-dependency from server package"
  - "Renamed dataclasses.field import to dc_field to avoid shadowing the 'field' attribute name on ConfigValidationError dataclass"
  - "validate_config_dict accepts dict (no line numbers); validate_config_file reads raw text, calls dict validator, then enriches with line numbers via _find_line_number"
  - "JSON mode for 'config validate' outputs valid=None (not false) when no config found, distinguishing 'file absent' from 'file invalid'"
metrics:
  duration_seconds: 208
  completed_date: "2026-03-26"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 1
---

# Phase 44 Plan 01: Config Validation Engine and CLI Command Summary

**One-liner:** Offline YAML config validation with per-field line numbers, provider enum checks, deprecated key detection, and `agent-brain config validate` CLI command.

## What Was Built

A config schema validation engine (`config_schema.py`) and `agent-brain config validate` CLI subcommand that checks `config.yaml` against the known Agent Brain schema before the server is started, reporting errors with field dot-paths, approximate line numbers, and actionable fix suggestions.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Config schema validation engine (TDD) | c5024f3 | config_schema.py, test_config_validate.py |
| 2 | `config validate` CLI subcommand | ad84cf2 | commands/config.py |

## Artifacts

### agent-brain-cli/agent_brain_cli/config_schema.py (NEW)

Exports:
- `ConfigValidationError` — dataclass with `field`, `message`, `line_number`, `suggestion`
- `validate_config_dict(config: dict) -> list[ConfigValidationError]`
- `validate_config_file(path: Path) -> list[ConfigValidationError]`
- `format_validation_errors(errors: list[ConfigValidationError]) -> str`
- `_find_line_number(yaml_text: str, key_path: str) -> int | None`
- `VALID_EMBEDDING_PROVIDERS`, `VALID_SUMMARIZATION_PROVIDERS`, `VALID_RERANKER_PROVIDERS`
- `VALID_STORAGE_BACKENDS`, `VALID_GRAPHRAG_STORE_TYPES`, `VALID_DOC_EXTRACTORS`
- `DEPRECATED_KEYS` — migration hints for renamed config keys

Schema validation covers:
- Unknown top-level keys (compared against `VALID_TOP_LEVEL_KEYS`)
- Invalid enum values for provider/backend/store_type/doc_extractor fields
- Unknown sub-keys within each section (typo detection)
- Deprecated keys (e.g. `graphrag.use_llm_extraction` -> `doc_extractor`)
- Type mismatches (e.g. `api.port` must be int, `graphrag.enabled` must be bool)

### agent-brain-cli/agent_brain_cli/commands/config.py (MODIFIED)

Added `@config_group.command("validate")` with:
- `--file PATH` option for explicit config path (auto-detects via `_find_config_file` if omitted)
- `--json` flag for machine-readable output
- Exit 0 + "Config is valid" on success
- Exit 1 + formatted errors (field, line, suggestion) on failure
- Exit 0 + "No config file found" when no config exists

### agent-brain-cli/tests/test_config_validate.py (NEW — 18 tests)

- `TestValidateConfigDict` (8 tests) — engine unit tests covering all 9 plan behaviors
- `TestValidateConfigFile` (3 tests) — file-based validation with line-number enrichment
- `TestFormatValidationErrors` (2 tests) — output formatting
- `TestValidateCliCommand` (5 tests) — CLI integration via CliRunner

## Verification Results

```
poetry run pytest tests/test_config_validate.py tests/test_config_commands.py -x -v
# 30 passed in 0.14s

poetry run mypy agent_brain_cli/config_schema.py agent_brain_cli/commands/config.py
# Success: no issues found in 2 source files

poetry run ruff check agent_brain_cli/config_schema.py agent_brain_cli/commands/config.py
# All checks passed!
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] dataclasses.field name collision with ConfigValidationError.field attribute**
- **Found during:** Task 1, mypy check
- **Issue:** `from dataclasses import field` shadowed the `field: str` attribute name inside the `ConfigValidationError` dataclass, causing `mypy` error: `"str" not callable`
- **Fix:** Renamed the import to `from dataclasses import field as dc_field` and used `dc_field(default="")` for the default value
- **Files modified:** agent-brain-cli/agent_brain_cli/config_schema.py
- **Commit:** c5024f3 (incorporated in same commit)

**2. [Rule 1 - Style] Line length violations in config_schema.py and commands/config.py**
- **Found during:** Task 1 and Task 2, ruff check
- **Issue:** Three lines >88 chars in config_schema.py, one in config.py
- **Fix:** Wrapped long f-string messages into multi-line string concatenation / dict literals
- **Files modified:** both files
- **Commit:** incorporated into respective commits

No other deviations — plan executed as written.

## Self-Check: PASSED
