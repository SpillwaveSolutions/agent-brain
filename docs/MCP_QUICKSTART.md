# MCP Quickstart — use Agent Brain over MCP in ~5 minutes

A copy-paste walkthrough to get the Agent Brain **MCP server** running and registered with
**Claude Code**, so the model can search your indexed corpus as a native tool. For the full
reference (all 16 tools, resources, prompts, OAuth, per-host config) see the
[MCP User Guide](./MCP_USER_GUIDE.md).

> **MCP server vs. plugin:** the *plugin* gives you `/agent-brain-*` slash commands you drive by
> hand. The *MCP server* lets the model itself call Agent Brain as tools during a session. You can
> run both against the same backend. This guide sets up the MCP server.

---

## Prerequisites

- Python 3.10+
- A provider key for embeddings (e.g. `OPENAI_API_KEY`), or Ollama for a fully-local setup
- Claude Code (this works in any MCP host; the one-command registration targets Claude Code)

---

## Step 1 — Install the packages

```bash
pip install agent-brain-rag agent-brain-cli agent-brain-ag-mcp
# verify
agent-brain --version
agent-brain-mcp --help
```

> PyPI ships the MCP server as `agent-brain-ag-mcp`; the console script is `agent-brain-mcp`.

## Step 2 — Start the backend and index something

The MCP server is a thin proxy — it indexes nothing itself. You need a running backend with
content in it.

```bash
cd /path/to/your/project
export OPENAI_API_KEY="sk-..."        # or configure Ollama — see the Configuring guide

agent-brain init                      # creates .agent-brain/
agent-brain start                     # starts the FastAPI backend
agent-brain index ./docs ./src        # index some docs/code
agent-brain status                    # expect: healthy, document count > 0
```

## Step 3 — Register the MCP server with Claude Code

One command writes the `.mcp.json` entry for you (idempotent; preview with `--dry-run` first):

```bash
agent-brain install-agent --agent claude --with-mcp --dry-run   # preview
agent-brain install-agent --agent claude --with-mcp             # do it
```

This merges an `agent-brain` server into the project's `.mcp.json` (preserving any other servers),
pinning an absolute `AGENT_BRAIN_STATE_DIR`. Confirm:

```bash
cat .mcp.json
```

```json
{
  "mcpServers": {
    "agent-brain": {
      "command": "agent-brain-mcp",
      "args": ["--backend", "auto"],
      "env": { "AGENT_BRAIN_STATE_DIR": "/abs/path/to/your/project/.agent-brain" }
    }
  }
}
```

> **Other hosts / runtimes:** auto-registration currently targets Claude Code. For Claude Desktop,
> Cursor, Windsurf, OpenCode, Gemini, or Codex, paste the same `mcpServers` block into that host's
> config (see [MCP User Guide → Configuration](./MCP_USER_GUIDE.md#configuration)).

## Step 4 — Reload Claude Code and approve the server

Restart Claude Code (or reload the window) in that project. Claude Code reads `.mcp.json` on
startup and will prompt you to approve the new `agent-brain` server. After approval, the 16 tools
become available to the model.

Verify from a terminal that the server itself is healthy:

```bash
# Drive the server through the CLI's MCP transport
agent-brain --transport mcp resources list
agent-brain --transport mcp resources read corpus://status
```

You should see the `corpus://` resources and a status payload with your document count.

## Step 5 — Use it

In a Claude Code session in that project, just ask in natural language — the model will pick the
`search_documents` tool itself:

> "Search the indexed corpus for how authentication is handled."
> "Use agent-brain to find the callers of `register_claude_mcp`."
> "What does `corpus://status` report for the index?"

You don't invoke tools by name; the model selects them. The MCP tools cover search
(`search_documents` across semantic / bm25 / hybrid / graph / multi modes), indexing
(`index_folder`, `add_documents`, `inject_documents`), jobs (`list_jobs`, `wait_for_job`,
`cancel_job`), folders, cache, and health. See the
[tool reference](./MCP_USER_GUIDE.md#tool-reference-16-tools).

---

## Optional — remote server with OAuth (v10.4)

For local use you need **no auth** — skip this. To run Agent Brain on a remote/shared host, enable
OAuth 2.1 on the HTTP listen transport (off by default):

```bash
# Server side
export AGENT_BRAIN_AUTH=oauth
export AGENT_BRAIN_OAUTH_RESOURCE="https://agent-brain.example.com/mcp"
agent-brain-mcp --transport http --host 127.0.0.1 --port 8765    # behind a gateway

# Client side — register with the client OAuth dance enabled
agent-brain install-agent --agent claude --with-mcp --mcp-auth oauth
```

The client opens a browser once, caches tokens at `<state_dir>/mcp-oauth-tokens.json`, and refreshes
silently. Per-tool scopes (`agent-brain:read|index|admin|subscribe`) apply, with default-deny on the
mutating tools. Full setup: [MCP User Guide → Authentication](./MCP_USER_GUIDE.md#authentication).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Server doesn't appear in Claude Code | Reload the window; confirm `.mcp.json` exists at the project root and you approved the server |
| `agent-brain-mcp: command not found` in the host | Use the absolute path from `which agent-brain-mcp` as `command` in `.mcp.json` |
| Tools return "backend unavailable" | The backend isn't running — `agent-brain start`, then `agent-brain status` |
| Empty / no results | Index something first (`agent-brain index ./docs`) and check `agent-brain status` shows a document count |
| Wrong corpus | `AGENT_BRAIN_STATE_DIR` points at the wrong `.agent-brain`; re-run `install-agent --with-mcp` from the right project root |
| `install-agent --with-mcp` won't merge | Your `.mcp.json` is invalid JSON — the command fails closed; fix/remove it and re-run |
| 401 / 403 from a remote server | 401 → set `AGENT_BRAIN_MCP_AUTH=oauth` on the client; 403 `insufficient_scope` → the token lacks the tool's scope |

---

## Related docs

- [MCP User Guide](./MCP_USER_GUIDE.md) — full tool/resource/prompt reference, OAuth, per-host config
- [Configuring Agent Brain](../agent-brain-plugin/skills/configuring-agent-brain/references/mcp-setup-guide.md) — MCP setup reference in the plugin skill
- [User Guide](./USER_GUIDE.md) — backend setup, indexing, retrieval modes
- [Plugin Guide](./PLUGIN_GUIDE.md) — the slash-command companion
