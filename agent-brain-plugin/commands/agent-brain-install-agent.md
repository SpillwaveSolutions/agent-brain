---
name: agent-brain-install-agent
description: Install Agent Brain plugin for a specific runtime (Claude, OpenCode, Gemini)
parameters:
  - name: agent
    description: "Target runtime: claude, opencode, gemini, skill-runtime, or codex"
    required: true
  - name: scope
    description: "Install scope: project (default) or global"
    required: false
    default: project
  - name: plugin-dir
    description: Custom canonical plugin source directory
    required: false
  - name: dir
    description: Target skill directory (required for skill-runtime)
    required: false
  - name: dry-run
    description: List files that would be created without writing
    required: false
  - name: json
    description: Output as JSON
    required: false
  - name: path
    description: Project path for --project scope (default: cwd)
    required: false
skills:
  - configuring-agent-brain
---

# Agent Brain Install Agent

## Purpose

Installs Agent Brain plugin files for a specific AI coding runtime. Converts the canonical plugin format into the target runtime's native format and writes the files to the appropriate directory.

Supported runtimes:
- **Claude Code** — copies plugin as-is with path normalization
- **OpenCode** — converts tool lists to boolean objects, maps tool names to lowercase
- **Gemini CLI** — remaps tool names (e.g., Bash->run_shell_command), removes unsupported fields
- **Codex** — creates skill directories under `.codex/skills/agent-brain/` and generates AGENTS.md
- **skill-runtime** — generic converter producing skill directories with SKILL.md frontmatter (requires `--dir`)

## Usage

```
agent-brain install-agent --agent <runtime> [--project|--global] [--plugin-dir <path>] [--dir <path>] [--dry-run] [--json] [--path <path>]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| --agent / -a | Yes | - | Target runtime: `claude`, `opencode`, `gemini`, `skill-runtime`, or `codex` |
| --project | No | Yes | Install to project directory (default) |
| --global | No | No | Install to user-level directory |
| --plugin-dir | No | Auto-detect | Custom canonical plugin source directory |
| --dir | No* | - | Target skill directory (*required for skill-runtime) |
| --dry-run | No | No | List files without writing |
| --json | No | No | Machine-readable JSON output |
| --path / -p | No | cwd | Project path for --project scope |

### Install Directories

| Runtime | Project Scope | Global Scope |
|---------|---------------|--------------|
| Claude | `.claude/plugins/agent-brain/` | `~/.claude/plugins/agent-brain/` |
| OpenCode | `.opencode/plugins/agent-brain/` | `~/.config/opencode/plugins/agent-brain/` |
| Gemini | `.gemini/plugins/agent-brain/` | `~/.config/gemini/plugins/agent-brain/` |
| Codex | `.codex/skills/agent-brain/` | `~/.codex/skills/agent-brain/` |
| skill-runtime | Requires `--dir` | Requires `--dir` |

## Execution

### Install for Claude Code (default)

```bash
agent-brain install-agent --agent claude --project
```

### Install for OpenCode

```bash
agent-brain install-agent --agent opencode --project
```

### Install for Gemini CLI

```bash
agent-brain install-agent --agent gemini --project
```

### Install for Codex

```bash
agent-brain install-agent --agent codex --project
```

This creates skill directories under `.codex/skills/agent-brain/` and generates an `AGENTS.md` file at the project root.

### Install for Generic Skill-Runtime

```bash
agent-brain install-agent --agent skill-runtime --dir ./my-skills
```

The `--dir` flag is required for skill-runtime (it has no default directory).

### Global Installation

```bash
agent-brain install-agent --agent claude --global
```

### Preview Without Installing

```bash
agent-brain install-agent --agent claude --dry-run
```

### JSON Output

```bash
agent-brain install-agent --agent claude --json
```

### Custom Plugin Source

```bash
agent-brain install-agent --agent opencode --plugin-dir ./my-custom-plugin
```

## Output

### Normal Output

```
╭──────── Agent Brain Installed ────────╮
│ Plugin installed successfully!         │
│                                        │
│ Runtime: claude                        │
│ Scope:   project                       │
│ Target:  .claude/plugins/agent-brain/  │
│ Files:   12                            │
╰────────────────────────────────────────╯
```

### Dry Run Output

```
╭──────── Install Preview ────────╮
│ Dry run — no files written       │
│                                  │
│ Runtime: claude                  │
│ Scope:   project                 │
│ Target:  .claude/plugins/...     │
│ Files:   12                      │
╰──────────────────────────────────╯
  .claude/plugins/agent-brain/commands/agent-brain-search.md
  .claude/plugins/agent-brain/agents/search-assistant.md
  ...
```

### JSON Output

```json
{
  "status": "installed",
  "agent": "claude",
  "scope": "project",
  "target_dir": ".claude/plugins/agent-brain",
  "files_created": 12,
  "source_dir": "/path/to/canonical/plugin"
}
```

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| Could not find canonical plugin directory | Plugin source not found | Use `--plugin-dir` to specify location |
| Invalid agent choice | Unsupported runtime name | Use `claude`, `opencode`, `gemini`, `skill-runtime`, or `codex` |
| --dir is required for --agent skill-runtime | Missing target directory | Specify `--dir ./path/to/skills` |

## Notes

- All runtimes share the same `.agent-brain/` data directory for indexes and configuration
- The canonical plugin format uses YAML frontmatter + markdown body
- Runtime converters handle tool name mapping and format differences automatically
- Use `--dry-run` to preview changes before installing
