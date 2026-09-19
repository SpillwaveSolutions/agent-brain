# AGENTS.md: agent-brain plugin

Agent-facing instructions for Grok Build, Codex, Cursor, and any host that loads this directory as a Claude-compatible or Agent Plugins 1.0 plugin.

## Host compatibility

| Host | How this plugin loads |
| --- | --- |
| Claude Code | Native plugin: `.claude-plugin/plugin.json`, `commands/`, `agents/`, `skills/` |
| Grok Build | Zero-config Claude plugin load. `.grok-plugin/marketplace.json` pins marketplace identity |
| Cursor | `.cursor-plugin/plugin.json` plus `.cursor/rules/agent-brain.mdc`. `agent-brain install-agent --agent cursor` writes `.cursor/plugins/agent-brain/` |
| Codex | `.codex-plugin/plugin.json`. `agent-brain install-agent --agent codex` writes `.codex/skills/agent-brain/` and an `AGENTS.md` block at the project root |
| OpenCode | `agent-brain install-agent --agent opencode` writes `.opencode/plugins/agent-brain/` |
| Agent Plugins 1.0 | Root `plugin.json`, `skills/`, and `mcp.json` |

This is one plugin with one payload. `commands/`, `agents/`, and `skills/` are shared by every host. Do not add host-specific copies of a skill. Host manifests point at the shared directories.

## Mission

Give the coding agent a local, project-scoped memory of the docs and code it works on:

- Index Markdown, PDF, and source code into one corpus per project (`.agent-brain/`).
- Search with BM25, vector, hybrid, graph, or multi mode.
- Serve the corpus over REST, Unix domain socket, and MCP (stdio or Streamable HTTP with OAuth 2.1).

## Component map

- Skills: `skills/using-agent-brain/SKILL.md` (search) and `skills/configuring-agent-brain/SKILL.md` (setup)
- Commands: `commands/agent-brain-*.md`, one slash command per CLI operation
- Agents: `agents/search-assistant.md`, `agents/research-assistant.md`, `agents/setup-assistant.md`
- MCP: `mcp.json` declares the `agent-brain-mcp` stdio server. `AGENT_BRAIN_STATE_DIR` selects the project
- Cursor rules: `.cursor/rules/agent-brain.mdc`

Plugin root variable in Claude and Grok plugin context: `${CLAUDE_PLUGIN_ROOT}`.

## Operating principles

1. Search before you read. Run `agent-brain query "<question>"` or the `search_documents` MCP tool, then open only the files the results name.
2. Pick the mode by question type: `bm25` for exact symbols, `vector` for concepts, `hybrid` by default, `graph` for callers and relationships, `multi` for a broad first pass.
3. Check `agent-brain status` before a search. Start the server with `agent-brain start` from the project root when it is down.
4. Reindex after large file moves: `agent-brain index <folder> --include-code`.
5. Never edit `.agent-brain/`. It holds server state, indexes, and the API key.
6. Do not commit `.agent-brain/`. Keep it in `.gitignore`.

## Skill routing

| User language | Skill or command |
| --- | --- |
| search, find, where is, who calls | `using-agent-brain`, `/agent-brain-search` |
| install, set up, configure provider, API key | `configuring-agent-brain`, `/agent-brain-setup` |
| index, reindex, add folder | `/agent-brain-index`, `/agent-brain-folders` |
| server down, status, jobs | `/agent-brain-status`, `/agent-brain-start`, `/agent-brain-jobs` |

## Install

- Claude Code: `claude plugins marketplace add SpillwaveSolutions/agent-brain` then `claude plugins install agent-brain@agent-brain-marketplace`
- Grok Build: zero-config Claude plugin load
- Cursor, Codex, OpenCode: `agent-brain install-agent --agent <host> --with-mcp`

See `docs/HOSTS.md` in the repository for the manifest each host reads and the MCP config target it writes.
