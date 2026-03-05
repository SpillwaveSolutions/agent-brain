---
phase: 13-content-injection-pipeline
plan: 02
subsystem: cli
tags: [content-injection, cli, inject-command, docserveclient, injector-protocol, dry-run]

# Dependency graph
requires:
  - phase: 13-content-injection-pipeline
    plan: 01
    provides: ContentInjector service, IndexRequest injection fields, dry_run API endpoint
provides:
  - inject CLI command with --script, --folder-metadata, --dry-run options
  - DocServeClient.index() extended with injector_script, folder_metadata_file, dry_run params
  - inject_command registered in CLI entry point
  - 15 unit tests for inject command
  - docs/INJECTOR_PROTOCOL.md — full injector protocol documentation (INJECT-08)
affects:
  - CLI users via agent-brain inject subcommand
  - INJECTOR_PROTOCOL.md documents server-side behavior from Phase 13 Plan 01

# Tech tracking
tech-stack:
  added: []
  patterns:
    - inject command as superset of index command — inherits all index options plus injection-specific ones
    - Validation-before-call pattern — check at least one injection option provided before making API call
    - Absolute path resolution for --script and --folder-metadata before sending to server

key-files:
  created:
    - agent-brain-cli/agent_brain_cli/commands/inject.py
    - agent-brain-cli/tests/test_inject_command.py
    - docs/INJECTOR_PROTOCOL.md
  modified:
    - agent-brain-cli/agent_brain_cli/client/api_client.py
    - agent-brain-cli/agent_brain_cli/commands/__init__.py
    - agent-brain-cli/agent_brain_cli/cli.py

key-decisions:
  - "inject command requires at least one of --script or --folder-metadata — validated before API call, exit code 2"
  - "Paths resolved to absolute before sending to server — server needs absolute paths to load files"
  - "inject is superset of index — all index options inherited to avoid user confusion"
  - "dry_run output differs from normal inject output — shows 'Dry-run validation complete' header"

# Metrics
duration: 4min
completed: 2026-03-05
---

# Phase 13 Plan 02: CLI inject command and Injector Protocol Documentation Summary

**inject CLI command with --script, --folder-metadata, --dry-run; DocServeClient extended with injection params; INJECTOR_PROTOCOL.md documents the full process_chunk protocol with examples**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-05T21:17:46Z
- **Completed:** 2026-03-05T21:21:43Z
- **Tasks:** 2/2
- **Files modified:** 6 (3 created, 3 modified)

## Accomplishments

- Extended `DocServeClient.index()` with three new optional parameters: `injector_script`, `folder_metadata_file`, and `dry_run` — values sent in POST body when not None
- Created `commands/inject.py` with `@click.command("inject")` — inherits all 14 options from `index_command` plus 3 injection-specific options
- Validation enforced at CLI level: at least one of `--script` or `--folder-metadata` must be provided, exits with code 2 otherwise
- `--script` and `--folder-metadata` paths resolved to absolute paths before sending to server
- Dry-run output shows "Dry-run validation complete" header and report from server; normal inject output shows job ID and injection configuration
- Registered `inject_command` in `commands/__init__.py` and `cli.py`, and updated CLI docstring with inject example
- 15 unit tests covering: script, folder-metadata, both combined, dry-run, validation, chunk-size, include-code, no-recursive, include-type, JSON output (normal + dry-run), connection error, server error, JSON error
- Created `docs/INJECTOR_PROTOCOL.md` (~200 lines) covering: overview, quick start, process_chunk protocol, input keys table, output constraints, value constraints, exception handling, two example scripts (enrich.py, classify.py), folder metadata JSON spec, dry-run mode, best practices, and limitations
- 136 CLI tests pass, 793 server tests pass, `task before-push` clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend DocServeClient and create inject CLI command** - `2916384` (feat)
2. **Task 2: Create injector protocol documentation** - `1ced5e3` (docs)

## Files Created/Modified

- `agent-brain-cli/agent_brain_cli/commands/inject.py` - inject CLI command with all options, validation, output formatting, error handling
- `agent-brain-cli/tests/test_inject_command.py` - 15 unit tests for inject command
- `docs/INJECTOR_PROTOCOL.md` - Full injector protocol documentation (INJECT-08)
- `agent-brain-cli/agent_brain_cli/client/api_client.py` - Added injector_script, folder_metadata_file, dry_run params to index() method
- `agent-brain-cli/agent_brain_cli/commands/__init__.py` - Added inject_command import and __all__ export
- `agent-brain-cli/agent_brain_cli/cli.py` - Added inject_command import, registration, and docstring update

## Decisions Made

- inject command validates at least one injection option before making API call — exits with code 2, consistent with Click's own validation exit code
- Paths resolved to absolute by CLI before sending — server-side path loading requires absolute paths
- inject is a superset of index (not a subcommand) — all index options available to avoid user confusion when combining injection with code/type presets
- Dry-run output format differs to make it visually clear no job was enqueued

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- Ruff flagged I001 (import sort order) in `commands/__init__.py` and `cli.py` after inserting `inject_command` — ruff auto-fixed to alphabetical order within the import block
- Test file had unused `os` and `tempfile` imports — ruff removed them
- One line exceeded 88 chars in test assertion — manually split to multi-line
- One unused variable in test (`mock_client = _make_mock_client(...)`) — changed to `_make_mock_client(...)` (side effect only call)
- Black reformatted test file — all clean after formatting

## Self-Check: PASSED

All files found on disk. All commits exist in git history.

Verified:
- `agent-brain-cli/agent_brain_cli/commands/inject.py` - FOUND
- `agent-brain-cli/tests/test_inject_command.py` - FOUND
- `docs/INJECTOR_PROTOCOL.md` - FOUND
- Commit `2916384` - FOUND
- Commit `1ced5e3` - FOUND

## Next Phase Readiness

- CLI inject command complete and registered — `agent-brain inject --script enrich.py /path` works end-to-end
- INJECTOR_PROTOCOL.md documents the complete injection system for developers
- Phase 13 Plan 02 fully satisfies: INJECT-01, INJECT-04, INJECT-06 (CLI surface), INJECT-08 (documentation)
