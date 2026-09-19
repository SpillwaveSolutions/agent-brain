# Hosts

Agent Brain ships one plugin payload (`agent-brain-plugin/commands/`, `agents/`, `skills/`) with a native manifest per host. This page lists what each host reads, how you install, and where `--with-mcp` registers the MCP server.

## Host table

| Host | Manifest read | Install | MCP config target |
| --- | --- | --- | --- |
| Claude Code | `agent-brain-plugin/.claude-plugin/plugin.json` via `.claude-plugin/marketplace.json` | `claude plugins marketplace add SpillwaveSolutions/agent-brain` then `claude plugins install agent-brain@agent-brain-marketplace`, or `agent-brain install-agent --agent claude` | `.mcp.json` (project) or `~/.claude.json` (global) |
| Grok Build | Claude manifest, zero config. `agent-brain-plugin/.grok-plugin/marketplace.json` pins identity | Load the Claude plugin, or `agent-brain install-agent --agent grok` | `.mcp.json`, same as Claude Code |
| Cursor | `agent-brain-plugin/.cursor-plugin/plugin.json` and `.cursor/rules/agent-brain.mdc` | `agent-brain install-agent --agent cursor` | `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global) |
| Codex | `agent-brain-plugin/.codex-plugin/plugin.json` | `agent-brain install-agent --agent codex` | `$CODEX_HOME/config.toml`, `[mcp_servers.agent-brain]`. Codex has no project-level MCP file |
| OpenCode | Converted plugin under `.opencode/plugins/agent-brain/` | `agent-brain install-agent --agent opencode` | `opencode.json` (project) or `~/.config/opencode/opencode.json` (global) |
| Agent Plugins 1.0 client | `agent-brain-plugin/plugin.json`, `skills/`, `mcp.json` | Point the client at `agent-brain-plugin/` | `mcp.json` in the plugin, `AGENT_BRAIN_STATE_DIR=${PLUGIN_DATA}` |
| Any skill runtime | `SKILL.md` directories | `agent-brain install-agent --agent skill-runtime --dir <path>` | None. Register the MCP server by hand |

## Install directories

| Host | Project scope | Global scope |
| --- | --- | --- |
| Claude Code | `.claude/plugins/agent-brain/` | `~/.claude/plugins/agent-brain/` |
| Grok Build | `.grok/plugins/agent-brain/` | `~/.grok/plugins/agent-brain/` |
| Cursor | `.cursor/plugins/agent-brain/` | `~/.cursor/plugins/agent-brain/` |
| Codex | `.codex/skills/agent-brain/` | `~/.codex/skills/agent-brain/` |
| OpenCode | `.opencode/plugins/agent-brain/` | `~/.config/opencode/plugins/agent-brain/` |

## Rules for the payload

- One payload. Do not copy a skill per host. Manifests point at the shared `skills/`, `commands/`, and `agents/` directories.
- Versions stay in lockstep. `scripts/check_plugin_manifest_versions.sh` fails `task before-push` when any manifest version differs from `agent-brain-server/pyproject.toml`.
- `agent-brain-plugin/AGENTS.md` is the host compatibility contract that cloud sessions read. Update it when a host or a manifest changes.
- `.cursor/rules/` is soft guidance. It is not a hook and it does not replace the skills.

## Not included on purpose

- Per-host hooks (`hooks/codex-hooks.json`, `hooks/cursor-hooks.json`). Agent Brain ships no hooks.
- `hosts/*/SKILL.md` host bindings. Those exist in the OKF plugins for a shared write protocol that Agent Brain does not have.

## Related

- [PLUGIN_GUIDE.md](PLUGIN_GUIDE.md) for the command reference
- [MCP_USER_GUIDE.md](MCP_USER_GUIDE.md) for MCP transports and OAuth
- [INTEGRATIONS.md](INTEGRATIONS.md) for per-editor MCP configuration
