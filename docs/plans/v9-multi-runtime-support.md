# v9.0 Multi-Runtime Support Plan

## Context

Agent Brain is currently Claude-only: its plugin, state storage (`.claude/agent-brain/`), and CLI all assume Claude Code as the runtime. The goal is to make Agent Brain **runtime-agnostic** so it works with Claude, OpenCode, and Gemini CLI from a single canonical plugin source.

**Core insight:** Runtimes are thin adapters over a shared data layer. The real system is Agent Brain itself -- indexes, config, jobs, logs -- not any one runtime. Claude, OpenCode, and Gemini are **interfaces to the same Agent Brain**.

**What prompted this:** A comprehensive multi-runtime architecture design where `agent-brain install-agent --agent claude|opencode|gemini` converts the canonical plugin format into each runtime's native format, and all runtimes share a `.agent-brain/` data directory.

**Intended outcome:** A new milestone (v9.0) with GSD phases that incrementally deliver:
1. Runtime-neutral storage (`.agent-brain/` instead of `.claude/agent-brain/`)
2. Plugin parser and converter infrastructure
3. `install-agent` CLI command
4. Runtime-specific converters (Claude, OpenCode, Gemini)
5. Updated plugin files and documentation

---

## Architecture Overview

```
Runtime Layer (thin adapters)
   +-  Claude plugin    (.claude/plugins/agent-brain/)
   +-  OpenCode commands (.opencode/commands/)
   +-  Gemini agents    (.gemini/)

Shared Data Layer (runtime-neutral)
   +-- .agent-brain/
        +-- config/
        +-- data/
        |   +-- chroma_db/
        |   +-- bm25_index/
        |   +-- llamaindex/
        |   +-- graph_index/
        +-- embedding_cache/
        +-- manifests/
        +-- logs/
        +-- jobs/

Global Config
   +-- ~/.config/agent-brain/
   +-- ~/.local/state/agent-brain/registry.json
```

**Install flow:**
```
pip install agent-brain
agent-brain install-agent --project --agent claude
agent-brain install-agent --project --agent opencode
agent-brain install-agent --project --agent gemini
```

The installer reads the canonical plugin source (agent-brain-plugin/) and converts each file's frontmatter and body to the target runtime's native format.

---

## Current State Analysis

### Plugin Format (agent-brain-plugin/)
- **31 command .md files** with YAML frontmatter: `name`, `description`, `parameters[]`, `skills[]`
- **3 agent .md files** with frontmatter: `name`, `description`, `triggers[]`, `skills[]`
- **2 skills** in `skills/<name>/SKILL.md` with frontmatter: `name`, `description`, `allowed-tools[]`, `metadata{}`
- Templates, scripts, references, plugin.json manifest

### Hardcoded `.claude/agent-brain` References
| File | Location | Change Needed |
|------|----------|---------------|
| `agent-brain-server/agent_brain_server/storage_paths.py` | `STATE_DIR_NAME = ".claude/agent-brain"` | Change to `".agent-brain"` |
| `agent-brain-server/agent_brain_server/api/main.py` | `state_dir.parent.parent.parent` (depth 3) | Change to `state_dir.parent` (depth 1) |
| `agent-brain-server/agent_brain_server/config/provider_config.py` | Walk-up search for `.claude/agent-brain/config.yaml` | Add `.agent-brain` primary, keep fallback |
| `agent-brain-cli/agent_brain_cli/config.py` | `STATE_DIR_NAME`, `_find_config_file` walk-up | Update paths |
| `agent-brain-cli/agent_brain_cli/commands/init.py` | Target directory creation | `.agent-brain/` |
| `agent-brain-cli/agent_brain_cli/commands/start.py` | State dir resolution | `.agent-brain/` |

### Runtime Conversion Differences

**Claude (native -- minimal changes):**
- Plugin stays as-is, just update path references

**OpenCode:**
- `allowed-tools` list -> `tools` boolean object
- Tool names: PascalCase -> lowercase (`Read` -> `read`, `Write` -> `write`, `Bash` -> `bash`)
- Color values: named -> hex (`cyan` -> `"#00FFFF"`)

**Gemini:**
- Tool name mapping: `Read` -> `read_file`, `Write` -> `write_file`, `Edit` -> `replace`, `Bash` -> `run_shell_command`, `WebSearch` -> `google_web_search`
- Remove unsupported fields (`color`)
- Commands become thin wrappers around CLI

---

## GSD Milestone: v9.0 Multi-Runtime Support

**Milestone Goal:** Agent Brain works with Claude Code, OpenCode, and Gemini CLI from a single canonical plugin source, with runtime-neutral storage at `.agent-brain/`.

---

### Phase 26: Runtime-Neutral State Directory

**Goal:** All Agent Brain state lives under `.agent-brain/` instead of `.claude/agent-brain/`, with backward-compatible auto-migration for existing users.

**Depends on:** Phase 25 (setup wizard must be complete)

**Requirements:** RT-STORE-01, RT-STORE-02, RT-STORE-03, RT-STORE-04

**Success Criteria** (what must be TRUE):
1. `agent-brain init` creates `.agent-brain/` (not `.claude/agent-brain/`) in the project root
2. `agent-brain start` finds and uses `.agent-brain/` as the state directory
3. Existing projects with `.claude/agent-brain/` auto-migrate to `.agent-brain/` on first `init` or `start`
4. Project root detection works via `.agent-brain/` marker (in addition to `.claude/`, `pyproject.toml`, git root)
5. `AGENT_BRAIN_STATE_DIR` env var still overrides all detection
6. All existing tests updated and passing with new paths

**Critical files to modify:**
- `agent-brain-server/agent_brain_server/storage_paths.py` -- change `STATE_DIR_NAME = ".claude/agent-brain"` to `".agent-brain"`
- `agent-brain-server/agent_brain_server/api/main.py` -- fix `.parent.parent.parent` (depth 3) to `.parent` (depth 1) with backward compat
- `agent-brain-server/agent_brain_server/config/provider_config.py` -- update walk-up search for config.yaml
- `agent-brain-cli/agent_brain_cli/config.py` -- update STATE_DIR_NAME and `_find_config_file` walk-up
- `agent-brain-cli/agent_brain_cli/commands/init.py` -- change target directory
- `agent-brain-cli/agent_brain_cli/commands/start.py` -- change state dir resolution

**New files:**
- `agent-brain-cli/agent_brain_cli/migration.py` -- auto-migration from `.claude/agent-brain` to `.agent-brain`

**Plans:** 2 plans
- 26-01: Server-side state dir migration (storage_paths.py, main.py depth fix, provider_config.py, migration helper)
- 26-02: CLI-side state dir migration (config.py, init.py, start.py, test updates)

---

### Phase 27: Plugin Parser and Converter Infrastructure

**Goal:** A reusable parser reads the canonical plugin format (YAML frontmatter + markdown body) and a converter protocol enables per-runtime output generation.

**Depends on:** Phase 26 (state dir must be settled before converters reference it)

**Requirements:** RT-PARSE-01, RT-PARSE-02, RT-CONV-01, RT-CONV-02

**Success Criteria** (what must be TRUE):
1. `parse_plugin_dir(path)` returns a `PluginBundle` with all 31 commands, 3 agents, and 2 skills parsed from the canonical plugin directory
2. Each `PluginCommand` contains: name, description, parameters list, skills list, body markdown
3. Each `PluginAgent` contains: name, description, triggers list, skills list, body markdown
4. Each `PluginSkill` contains: name, description, allowed_tools list, metadata dict, body markdown, references paths
5. `RuntimeConverter` protocol defines `convert_command`, `convert_agent`, `convert_skill`, `install` methods
6. Tool name mapping tables exist for Claude (identity), OpenCode, and Gemini
7. >90% test coverage on parser and tool mapping

**New files (all in `agent-brain-cli/agent_brain_cli/runtime/`):**
- `__init__.py` -- package exports
- `types.py` -- `RuntimeType`, `Scope`, `PluginCommand`, `PluginAgent`, `PluginSkill`, `PluginBundle` dataclasses
- `parser.py` -- `parse_frontmatter()`, `parse_command()`, `parse_agent()`, `parse_skill()`, `parse_plugin_dir()`
- `converter_base.py` -- `RuntimeConverter` protocol
- `tool_maps.py` -- `CLAUDE_TOOLS`, `OPENCODE_TOOLS`, `GEMINI_TOOLS` dicts

**Plans:** 2 plans
- 27-01: Data models and YAML frontmatter parser with tests
- 27-02: RuntimeConverter protocol, tool mapping tables, PluginBundle integration tests against real plugin dir

---

### Phase 28: Runtime Converters (Claude, OpenCode, Gemini)

**Goal:** Three concrete converters transform the canonical plugin format into each runtime's native format, producing installable output directories.

**Depends on:** Phase 27 (parser and protocol must exist)

**Requirements:** RT-CLAUDE-01, RT-OPENCODE-01, RT-OPENCODE-02, RT-GEMINI-01, RT-GEMINI-02

**Success Criteria** (what must be TRUE):
1. Claude converter copies commands/agents/skills as-is, updates `.claude/agent-brain` references to `.agent-brain` in body text, copies `plugin.json`
2. OpenCode converter transforms `allowed-tools` list to `tools` boolean object, maps PascalCase tool names to lowercase, converts named colors to hex
3. Gemini converter maps tool names (`Read`->`read_file`, `Write`->`write_file`, `Edit`->`replace`, `Bash`->`run_shell_command`), removes unsupported fields (`color`), generates thin CLI wrappers
4. Each converter produces a valid output directory that can be installed directly
5. Round-trip test: parse canonical -> convert to runtime -> verify output structure matches expected format

**New files (all in `agent-brain-cli/agent_brain_cli/runtime/`):**
- `claude_converter.py` -- Claude native converter
- `opencode_converter.py` -- OpenCode converter with tool/color mapping
- `gemini_converter.py` -- Gemini converter with tool mapping and wrapper generation

**Plans:** 3 plans (parallelizable)
- 28-01: Claude converter + tests
- 28-02: OpenCode converter + tests
- 28-03: Gemini converter + tests

---

### Phase 29: `install-agent` CLI Command

**Goal:** Users can run `agent-brain install-agent --agent claude|opencode|gemini --project|--global` to install Agent Brain integration for their chosen runtime.

**Depends on:** Phase 28 (all converters must exist)

**Requirements:** RT-INSTALL-01, RT-INSTALL-02, RT-INSTALL-03, RT-INSTALL-04

**Success Criteria** (what must be TRUE):
1. `agent-brain install-agent --agent claude --project` installs plugin to `.claude/plugins/agent-brain/`
2. `agent-brain install-agent --agent opencode --project` installs converted commands/agents to OpenCode's directory
3. `agent-brain install-agent --agent gemini --project` installs converted commands/agents to `.gemini/`
4. `--global` flag installs to user-level directories (`~/.claude/plugins/`, `~/.config/opencode/`, `~/.config/gemini/`)
5. `--dry-run` lists files that would be created without writing anything
6. `--plugin-dir` accepts custom canonical plugin source path
7. `--json` produces machine-readable output

**Files to modify:**
- `agent-brain-cli/agent_brain_cli/cli.py` -- register `install-agent` command
- `agent-brain-cli/agent_brain_cli/commands/__init__.py` -- add export

**New files:**
- `agent-brain-cli/agent_brain_cli/commands/install_agent.py` -- Click command implementation

**Plugin-dir resolution order:**
1. `--plugin-dir` CLI flag (if provided)
2. `{repo_root}/agent-brain-plugin/` (development)
3. `~/.local/share/agent-brain/plugin/` (installed)
4. Error with instructions

**Plans:** 2 plans
- 29-01: Core `install-agent` command with Claude and plugin-dir resolution
- 29-02: OpenCode + Gemini install paths, --global scope, --dry-run, --json, E2E tests

---

### Phase 30: Plugin File Updates and Documentation

**Goal:** All plugin markdown files reference `.agent-brain/` instead of `.claude/agent-brain/`, and the new `install-agent` command is documented.

**Depends on:** Phase 29 (command must exist before documenting it)

**Requirements:** RT-DOCS-01, RT-DOCS-02, RT-DOCS-03

**Success Criteria** (what must be TRUE):
1. Zero references to `.claude/agent-brain` remain in any plugin command, agent, or skill file (replaced with `.agent-brain`)
2. New `agent-brain-install-agent.md` command file exists in plugin
3. Skills reference docs updated with multi-runtime information
4. `agent-brain-help.md` includes `install-agent` in the command list
5. `task before-push` passes with all changes

**Files to modify:**
- ~15 plugin command files that reference `.claude/agent-brain`
- `agent-brain-plugin/skills/configuring-agent-brain/SKILL.md`
- `agent-brain-plugin/skills/using-agent-brain/SKILL.md`
- `agent-brain-plugin/commands/agent-brain-help.md`

**New files:**
- `agent-brain-plugin/commands/agent-brain-install-agent.md`

**Plans:** 2 plans
- 30-01: Bulk path replacement in plugin files + new install-agent command doc
- 30-02: Skill and reference doc updates for multi-runtime awareness

---

## Requirements Reference

### RT-STORE: Runtime-Neutral Storage
- **RT-STORE-01**: State directory at `.agent-brain/` instead of `.claude/agent-brain/`
- **RT-STORE-02**: Auto-migration from `.claude/agent-brain/` to `.agent-brain/`
- **RT-STORE-03**: Backward-compatible detection (check both paths)
- **RT-STORE-04**: `AGENT_BRAIN_STATE_DIR` env var override preserved

### RT-PARSE: Plugin Parser
- **RT-PARSE-01**: Parse YAML frontmatter from command/agent/skill .md files
- **RT-PARSE-02**: `PluginBundle` contains all parsed commands, agents, skills

### RT-CONV: Converter Infrastructure
- **RT-CONV-01**: `RuntimeConverter` protocol with convert + install methods
- **RT-CONV-02**: Centralized tool name mapping tables per runtime

### RT-CLAUDE: Claude Converter
- **RT-CLAUDE-01**: Native format preservation with path updates

### RT-OPENCODE: OpenCode Converter
- **RT-OPENCODE-01**: Tool format conversion (`allowed-tools` -> `tools` boolean)
- **RT-OPENCODE-02**: PascalCase -> lowercase tool names, named -> hex colors

### RT-GEMINI: Gemini Converter
- **RT-GEMINI-01**: Tool name mapping to Gemini equivalents
- **RT-GEMINI-02**: Unsupported field removal, thin CLI wrapper generation

### RT-INSTALL: Install Command
- **RT-INSTALL-01**: `install-agent` CLI command with `--agent` flag
- **RT-INSTALL-02**: `--project` and `--global` scope support
- **RT-INSTALL-03**: `--dry-run` mode
- **RT-INSTALL-04**: `--plugin-dir` for custom source path

### RT-DOCS: Documentation
- **RT-DOCS-01**: All plugin files updated to `.agent-brain/` paths
- **RT-DOCS-02**: `install-agent` command documented in plugin
- **RT-DOCS-03**: Skills updated with multi-runtime awareness

---

## Verification

After all phases complete:
1. `task before-push` exits 0
2. `task pr-qa-gate` exits 0
3. `agent-brain init` creates `.agent-brain/` in a fresh project
4. `agent-brain install-agent --agent claude --project --dry-run` lists expected files
5. `agent-brain install-agent --agent opencode --project --dry-run` shows converted output
6. `agent-brain install-agent --agent gemini --project --dry-run` shows converted output
7. Existing project with `.claude/agent-brain/` auto-migrates on `agent-brain start`

## Execution Order

Phases 26 -> 27 -> 28 -> 29 -> 30 (sequential, each depends on previous)

Phase 28 plans are parallelizable (28-01, 28-02, 28-03 can run concurrently).

---

## GSD Setup Instructions

To set up this milestone with GSD:

```bash
# 1. Create the milestone
/gsd:new-milestone   # v9.0 Multi-Runtime Support

# 2. Add phases (in order)
/gsd:add-phase       # Phase 26: Runtime-Neutral State Directory
/gsd:add-phase       # Phase 27: Plugin Parser and Converter Infrastructure
/gsd:add-phase       # Phase 28: Runtime Converters (Claude, OpenCode, Gemini)
/gsd:add-phase       # Phase 29: install-agent CLI Command
/gsd:add-phase       # Phase 30: Plugin File Updates and Documentation

# 3. Plan each phase
/gsd:plan-phase      # Start with Phase 26

# 4. Execute
/gsd:execute-phase   # Execute each phase in order
```

Reference this plan at: `docs/plans/v9-multi-runtime-support.md`

---
*Created: 2026-03-16*
