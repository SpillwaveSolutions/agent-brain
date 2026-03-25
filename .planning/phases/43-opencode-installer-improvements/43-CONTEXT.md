# Phase 43: OpenCode Installer Improvements — Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Bring `agent-brain install-agent --agent opencode` up to reference quality. The codebase-mentor project has a working OpenCode converter that handles all the transformations correctly. Agent Brain's converter has 8 known gaps that need to be fixed.

**What this phase delivers:**
- Directory singularization (commands/ → command/, agents/ → agent/, skills/ → skill/)
- `opencode.json` permission pre-authorization for plugin dir + .agent-brain/ state dir
- Full agent frontmatter conversion (name removal, tools object, color hex, subagent_type mapping)
- Complete tool name mapping (add AskUserQuestion → question, plus path scope stripping)
- Path rewriting for ~/.claude references
- Idempotent install behavior

**What this phase does NOT deliver:**
- No new CLI commands
- No server changes
- No new converter architecture (keep dict approach, fix gaps)
</domain>

<decisions>
## Implementation Decisions

### Conversion Strategy
- Keep the existing dict-based `OpenCodeConverter` class — it leverages the parser infrastructure (`PluginBundle`, `PluginAgent`, etc.)
- Fix all 8 gaps within the existing approach
- Structure changes so a future hybrid refactor is easy (pure transformation functions, separated concerns)
- Do NOT switch to line-by-line YAML parsing like the reference — the parser already extracts everything correctly

### Permission Pre-Authorization
- Write `opencode.json` with pre-authorized permissions for BOTH:
  1. Plugin install directory (e.g., `~/.config/opencode/agent-brain/*`)
  2. Project state directory (`.agent-brain/*`)
- Merge with existing `opencode.json` if present (don't overwrite)
- Use `permission.read` and `permission.external_directory` keys matching reference pattern

### Directory Names
- Output to singular directory names: `agent/`, `command/`, `skill/`
- Map from the existing plural conventions used in Claude Code plugin format

### Agent Frontmatter Conversion
- Remove `name` field (OpenCode derives from filename)
- Convert `allowed_tools` array to `tools` boolean object with mapped names
- Convert named colors to hex values (COLOR_MAP already exists, apply to agents too)
- Map `subagent_type: "general-purpose"` → `subagent_type: "general"`

### Tool Name Mapping
- Add missing mappings to `tool_maps.py` OPENCODE_TOOLS dict:
  - `AskUserQuestion` → `question`
  - `SkillTool` → `skill`
  - `TodoWrite` → `todowrite`
- Strip path scopes from tool names before mapping (e.g., `Write(.agent-brain/**)` → `Write` → `write`)
- Pass MCP tool names (`mcp__*`) through unchanged

### Path Rewriting
- Claude's discretion on exact scope — analyze what paths actually appear in plugin files and rewrite appropriately
- At minimum: `.claude/agent-brain` → `.agent-brain` (already done) plus `~/.claude` → `~/.config/opencode`

### Test Approach
- Follow existing agent-brain test patterns (pytest, PluginBundle fixtures)
- Add tests for each new behavior: singular dirs, permissions file, tool mappings, agent frontmatter fields
- Do NOT switch to monkeypatched Path.home() pattern from reference

### Claude's Discretion
- Exact `opencode.json` structure and key naming
- Whether to add a helper method for permissions writing or inline it
- Path rewriting granularity (global replace vs targeted)
- Test file organization (new file vs extend existing)
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Reference Implementation (Gold Standard)
- `/Users/richardhightower/clients/spillwave/src/codebase-mentor/ai_codebase_mentor/converters/opencode.py` — Working OpenCode converter with all transformations (380 lines). Read this to understand the target quality.
- `/Users/richardhightower/clients/spillwave/src/codebase-mentor/tests/test_opencode_installer.py` — Reference test patterns

### Current Implementation (To Be Fixed)
- `agent-brain-cli/agent_brain_cli/runtime/opencode_converter.py` — Current converter with gaps (147 lines)
- `agent-brain-cli/agent_brain_cli/runtime/tool_maps.py` — Tool name mapping tables (missing AskUserQuestion, SkillTool, TodoWrite)
- `agent-brain-cli/agent_brain_cli/runtime/types.py` — PluginBundle, PluginAgent, PluginCommand, PluginSkill types
- `agent-brain-cli/agent_brain_cli/commands/install_agent.py` — CLI command that invokes the converter

### Existing Tests
- `agent-brain-cli/tests/test_runtime_converters.py` — Existing converter tests
- `agent-brain-cli/tests/test_runtime_parser.py` — Parser tests for PluginBundle extraction
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `OpenCodeConverter` class with `convert_command()`, `convert_agent()`, `convert_skill()`, `install()` methods
- `COLOR_MAP` dict already maps named colors to hex
- `_tools_to_bool_object()` converts tool lists to boolean objects (used for skills, needs to be used for agents too)
- `_replace_paths()` handles path rewriting (needs scope expansion)
- `_rebuild_file()` creates YAML frontmatter + body markdown

### Established Patterns
- All converters follow the same interface: `convert_*()` methods + `install()` method
- Parser extracts `PluginBundle` from plugin directory, converters transform and write
- `tool_maps.py` centralizes tool name mappings per runtime
- Tests use `PluginBundle` fixtures constructed in test code

### Integration Points
- `install_agent.py` CLI command resolves target dir and calls `converter.install(bundle, target_dir, scope)`
- Target dir for OpenCode: `.opencode/plugins/agent-brain` (project) or `~/.config/opencode/plugins/agent-brain` (global)
- `opencode.json` goes in the parent of the install dir
</code_context>

<specifics>
## Specific Ideas

- The 8-gap table from conversation is the implementation checklist:
  1. Directory singularization (plural → singular)
  2. `opencode.json` permission pre-authorization (plugin dir + .agent-brain/)
  3. Agent `name` field removal
  4. Agent `subagent_type` mapping
  5. Agent `allowed_tools` → `tools` boolean object
  6. Agent color hex conversion
  7. `AskUserQuestion`/`SkillTool`/`TodoWrite` tool mappings
  8. Path rewriting scope expansion (~/.claude → ~/.config/opencode)
- Read the reference converter before implementing — it shows the exact output format OpenCode expects
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope
</deferred>

---

*Phase: 43-opencode-installer-improvements*
*Context gathered: 2026-03-24*
