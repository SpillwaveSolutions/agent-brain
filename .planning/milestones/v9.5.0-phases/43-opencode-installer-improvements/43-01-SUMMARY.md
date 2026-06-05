---
phase: 43-opencode-installer-improvements
plan: 01
subsystem: agent-brain-cli/runtime
tags: [opencode, converter, installer, plugin, tool-mapping]
dependency_graph:
  requires: []
  provides: [opencode-installer-parity]
  affects: [agent-brain-cli/agent_brain_cli/runtime/opencode_converter.py]
tech_stack:
  added: []
  patterns: [dataclass-field-extension, path-scope-stripping, yaml-frontmatter-conversion]
key_files:
  created: []
  modified:
    - agent-brain-cli/agent_brain_cli/runtime/types.py
    - agent-brain-cli/agent_brain_cli/runtime/parser.py
    - agent-brain-cli/agent_brain_cli/runtime/tool_maps.py
    - agent-brain-cli/agent_brain_cli/runtime/opencode_converter.py
    - agent-brain-cli/tests/test_runtime_converters.py
decisions:
  - "Keep dict-based frontmatter approach (not line-by-line regex like reference) — cleaner, type-safe"
  - "Add .agent-brain/* permission entries alongside plugin path in opencode.json for state dir access"
  - "Update idempotency test to use plugins/agent-brain key filter instead of any agent-brain key"
metrics:
  duration: "3 minutes"
  completed: "2026-03-25"
  tasks_completed: 2
  files_modified: 5
---

# Phase 43 Plan 01: OpenCode Installer Improvements Summary

**One-liner:** Closed all 8 OpenCode converter gaps — PluginAgent extended with allowed_tools/color/subagent_type, tool_maps updated with AskUserQuestion/SkillTool/TodoWrite and path-scope stripping, converter fixed for agent frontmatter conversion, expanded path rewriting, idempotent install, and permission pre-auth with .agent-brain/* entries.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend types, parser, and tool_maps | 0556459 | types.py, parser.py, tool_maps.py |
| 2 | Fix OpenCode converter | 3404484 | opencode_converter.py, test_runtime_converters.py |

## What Was Built

### Task 1: types.py, parser.py, tool_maps.py

**types.py** — Added three optional fields to `PluginAgent` dataclass:
- `allowed_tools: list[str]` — agent's allowed tool list (maps to `tools` bool object in OpenCode)
- `color: str` — named color (converted to hex for OpenCode)
- `subagent_type: str` — agent type (`general-purpose` mapped to `general` for OpenCode)

**parser.py** — Updated `parse_agent()` to extract the three new fields from YAML frontmatter, supporting both `allowed_tools` and `allowed-tools` key variants.

**tool_maps.py** — Three additions:
1. Added `AskUserQuestion -> question`, `SkillTool -> skill`, `TodoWrite -> todowrite` to `OPENCODE_TOOLS`
2. Rewrote `map_tool_name()` to strip path scope annotations (`Write(.agent-brain/**)` → `Write`) before lookup
3. `mcp__` prefixed tool names pass through unchanged; unknown tools are lowercased

### Task 2: opencode_converter.py

Six gap closures:
1. **Idempotency**: Added `shutil.rmtree(target_dir)` before installing — reinstall produces identical results
2. **Agent frontmatter — name removal**: `name` field omitted from output (OpenCode derives from filename)
3. **Agent frontmatter — subagent_type mapping**: `general-purpose` → `general`
4. **Agent frontmatter — tools**: `allowed_tools` converted to `tools` boolean object via `_tools_to_bool_object()`
5. **Agent frontmatter — color**: Named colors converted to hex via `_color_to_hex()`
6. **Path rewriting expansion**: Added `~/.claude/plugins/` → `~/.config/opencode/` and `~/.claude` → `~/.config/opencode` rewrites

Also added `.agent-brain/*` permission entries to `_register_in_opencode_json` alongside the plugin directory permissions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated idempotency test to match new behavior**
- **Found during:** Task 2 verification
- **Issue:** `test_install_idempotent_opencode_json` used `"agent-brain" in k` to count keys, which matched both `./.opencode/plugins/agent-brain/*` and the new `.agent-brain/*` entry — causing false failure
- **Fix:** Changed filter to `"plugins/agent-brain" in k` to specifically count only the plugin path key
- **Files modified:** `agent-brain-cli/tests/test_runtime_converters.py`
- **Commit:** 3404484

**2. Plan verify script used target.parent for opencode.json (not target.parent.parent)**
- The plan's verify script used `Path(tmp) / 'plugins' / 'agent-brain'` expecting `opencode.json` at `parent` level, but the existing implementation correctly writes to `parent.parent` (`.opencode/opencode.json`)
- Kept existing `parent.parent` behavior to preserve passing tests — the plan verify script was testing a simplified directory structure
- No code change needed; existing tests already validate correct behavior

## Verification Results

```
23 passed in 0.15s
mypy: Success: no issues found in 4 source files
ruff: All checks passed!
```

## Self-Check: PASSED

Files exist:
- agent-brain-cli/agent_brain_cli/runtime/types.py — FOUND
- agent-brain-cli/agent_brain_cli/runtime/parser.py — FOUND
- agent-brain-cli/agent_brain_cli/runtime/tool_maps.py — FOUND
- agent-brain-cli/agent_brain_cli/runtime/opencode_converter.py — FOUND

Commits exist:
- 0556459 — FOUND
- 3404484 — FOUND
