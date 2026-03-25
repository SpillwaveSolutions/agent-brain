---
phase: 43-opencode-installer-improvements
plan: 02
subsystem: agent-brain-cli/tests
tags: [opencode, tests, ocdi, coverage, quality-gate]
dependency_graph:
  requires: [43-01]
  provides: [ocdi-test-coverage]
  affects: [agent-brain-cli/tests/test_runtime_converters.py]
tech_stack:
  added: []
  patterns: [pytest-fixtures-with-new-fields, ocdi-requirement-tracing]
key_files:
  created: []
  modified:
    - agent-brain-cli/tests/test_runtime_converters.py
    - agent-brain-cli/tests/test_runtime_parser.py
    - agent-brain-cli/tests/test_install_agent.py
    - agent-brain-cli/agent_brain_cli/runtime/opencode_converter.py
decisions:
  - "Updated test_install_writes_opencode_json and test_install_merges_opencode_json to use .opencode/plugins/agent-brain structure matching implementation's target_dir.parent.parent behavior"
  - "Fixed test_install_agent.py opencode test to expect singular command/ dir — existing test was broken by 43-01"
  - "Updated test_runtime_parser.py to reflect map_tool_name lowercase-fallback and OPENCODE_TOOLS superset behavior from 43-01"
metrics:
  duration: "8 minutes"
  completed: "2026-03-25"
  tasks_completed: 2
  files_modified: 4
---

# Phase 43 Plan 02: OCDI Requirement Tests Summary

**One-liner:** Added 11 new tests covering all 6 OCDI requirements, fixed 3 pre-existing test failures from 43-01, and achieved `task before-push` pass with 307 CLI tests and 1001 server tests green.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add tests for all OCDI requirements | 87d8c30 | test_runtime_converters.py |
| 2 | Run full quality gate | f236920 | test_runtime_converters.py, test_runtime_parser.py, test_install_agent.py, opencode_converter.py |

## What Was Built

### Task 1: New OCDI requirement tests in TestOpenCodeConverter

Updated `sample_agent` fixture to include `allowed_tools`, `color`, `subagent_type` fields.

Added 11 new test methods:

| Test | OCDI Requirement |
|------|-----------------|
| `test_install_creates_singular_dirs` | OCDI-02 |
| `test_convert_agent_removes_name` | OCDI-03 |
| `test_convert_agent_maps_subagent_type` | OCDI-03 |
| `test_convert_agent_color_to_hex` | OCDI-03 |
| `test_convert_agent_tools_object` | OCDI-03 + OCDI-05 |
| `test_convert_agent_rewrites_claude_paths` | OCDI-04 |
| `test_install_writes_opencode_json` | OCDI-01 |
| `test_install_merges_opencode_json` | OCDI-01 |
| `test_install_idempotent` | OCDI-06 |
| `test_tool_map_strips_path_scope` | OCDI-05 support |

All 33 converter tests pass.

### Task 2: Quality gate — pre-existing test failures fixed

Three test failures found when running `task before-push` that were caused by 43-01 implementation changes but not caught then:

1. **test_install_agent.py** — `test_opencode_project_install` asserted `commands/` (plural) but OpenCode now uses `command/` (singular). Fixed to `command/`.

2. **test_runtime_parser.py::test_unknown_tool_passthrough** — asserted `map_tool_name("CustomTool", "claude") == "CustomTool"` but 43-01 changed the fallback to lowercase. Fixed expectation to `"customtool"`.

3. **test_runtime_parser.py::test_all_maps_have_same_keys** — asserted `CLAUDE_TOOLS.keys() == OPENCODE_TOOLS.keys()` but 43-01 added `AskUserQuestion`, `SkillTool`, `TodoWrite` to OPENCODE_TOOLS only. Fixed to `issubset` check.

Also fixed Ruff E501 (line too long >88) in docstrings of new tests.

Final result: `task before-push` exits 0 — 307 CLI tests pass, 1001 server tests pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan test structure for opencode.json didn't match implementation**
- **Found during:** Task 1 verification
- **Issue:** Plan specified `target = tmp_path / "plugins" / "agent-brain"` expecting `opencode.json` at `tmp_path / "plugins"` (parent), but the implementation places it at `target_dir.parent.parent` — so `tmp_path / "opencode.json"`
- **Fix:** Updated `test_install_writes_opencode_json` and `test_install_merges_opencode_json` to use `.opencode/plugins/agent-brain` structure matching implementation
- **Files modified:** `agent-brain-cli/tests/test_runtime_converters.py`
- **Commit:** 87d8c30

**2. [Rule 1 - Bug] Three pre-existing test failures from 43-01 caught by quality gate**
- **Found during:** Task 2 (`task before-push`)
- **Issue:** `test_install_agent.py`, `test_runtime_parser.py` tests were stale after 43-01 changes
- **Fix:** Updated expectations to match new behavior (singular dirs, lowercase fallback, superset keys)
- **Files modified:** `agent-brain-cli/tests/test_install_agent.py`, `agent-brain-cli/tests/test_runtime_parser.py`, `agent-brain-cli/agent_brain_cli/runtime/opencode_converter.py` (Black format only)
- **Commit:** f236920

## Verification Results

```
task before-push: All checks passed — Ready to push
mypy: Success: no issues found in 34 source files
ruff: All checks passed!
307 passed in 4.78s (CLI)
1001 passed, 23 skipped (server)
```

## Self-Check: PASSED

Files exist:
- agent-brain-cli/tests/test_runtime_converters.py — FOUND
- agent-brain-cli/tests/test_runtime_parser.py — FOUND
- agent-brain-cli/tests/test_install_agent.py — FOUND

Commits exist:
- 87d8c30 — FOUND
- f236920 — FOUND
