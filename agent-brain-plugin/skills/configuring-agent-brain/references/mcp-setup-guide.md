# MCP Setup Guide

How to install, register, and configure the Agent Brain **MCP (Model Context Protocol)
server** so MCP-aware clients (Claude Code, Claude Desktop, Cursor, Windsurf, the Claude
Agent SDK, LangChain DeepAgents) can reach your indexed corpus.

## 1. Install the MCP package

```bash
pip install agent-brain-ag-mcp          # or: uv pip install / pipx install
```

PyPI name is `agent-brain-ag-mcp`; the console script is `agent-brain-mcp` and the import
path is `agent_brain_mcp`.

## 2. Register the server

### Option A — through the plugin (Claude Code, recommended)

```bash
agent-brain install-agent --agent claude --with-mcp
```

This writes/merges an `agent-brain` entry into the project-level `.mcp.json` (or
`~/.claude.json` with `--global`), preserving any other servers and keys. It is idempotent
(re-running reports `unchanged`), supports `--dry-run`, and pins `AGENT_BRAIN_STATE_DIR` to
the project's absolute `.agent-brain` path.

| Flag | Values | Default | Purpose |
|------|--------|---------|---------|
| `--with-mcp` | — | off | Register the MCP server during install |
| `--mcp-backend` | `auto`/`uds`/`http` | `auto` | How the server reaches `agent-brain-serve` |
| `--mcp-auth` | `none`/`oauth` | `none` | Write `AGENT_BRAIN_MCP_AUTH=oauth` for remote OAuth servers |

### Option B — manual JSON (any client)

Claude Desktop, Cursor, and Windsurf use the same `mcpServers` shape:

```json
{
  "mcpServers": {
    "agent-brain": {
      "command": "agent-brain-mcp",
      "args": ["--backend", "auto"],
      "env": { "AGENT_BRAIN_STATE_DIR": "/abs/path/.agent-brain" }
    }
  }
}
```

- `--backend {auto,uds,http}` selects how the MCP server reaches `agent-brain-serve`
  (`auto` prefers the Unix domain socket, falls back to HTTP). This is **orthogonal** to
  the MCP *listen* transport.
- Always pin `AGENT_BRAIN_STATE_DIR` to an **absolute** path — MCP clients launch the
  server from an unknown working directory.

### Listen transport

`stdio` is the default (no flag). For IDE/framework clients that prefer HTTP:

```bash
agent-brain-mcp --transport http --host 127.0.0.1 --port 8765   # loopback only
```

## 3. OAuth 2.1 for remote servers (v10.4+)

Local/loopback servers need no auth. To expose Agent Brain remotely, enable OAuth 2.1 on the
Streamable HTTP transport. **Off by default.**

| Variable | Side | Values | Notes |
|----------|------|--------|-------|
| `AGENT_BRAIN_AUTH` | server | `none` (default) / `basic` / `oauth` | Server-side auth mode |
| `AGENT_BRAIN_OAUTH_RESOURCE` | server | absolute URI, no fragment | Required only in `oauth` mode (RFC 8707) |
| `AGENT_BRAIN_MCP_AUTH` | client | unset / `oauth` | Opts the client into the OAuth dance |

- Co-located AS/RS (single binary) and split AS/RS (external IdP: Keycloak/Auth0/Cognito).
- Per-tool scopes — `agent-brain:read | index | admin | subscribe` — with default-deny on the
  mutating tools (`index_folder`, `add_documents`, `inject_documents`, `remove_folder`,
  `cancel_job`, `clear_cache`).
- Client tokens are stored at `<state_dir>/mcp-oauth-tokens.json` (chmod `0o600`) and refreshed
  silently. The server validates `aud` (no token passthrough; the MCP→REST leg keeps using
  `X-API-Key`).
- Invalid auth config fails closed: an empty/scheme-less/fragmented `AGENT_BRAIN_OAUTH_RESOURCE`
  in `oauth` mode exits with code 2 at startup.

## 4. Verify

```bash
agent-brain-mcp --help                          # server starts, lists flags
agent-brain --transport mcp resources list      # drive it from the CLI
```

Current surface: **16 tools**, 5 `corpus://` resources, 6 prompts.

## 5. Other runtimes

`install-agent --with-mcp` auto-registers for **Claude Code** today. For OpenCode, Gemini, and
Codex, register manually using the Option B JSON in that runtime's MCP config location. (The
flag prints a note and skips for non-Claude runtimes rather than failing.)

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Client can't find the server | Ensure `agent-brain-mcp` is on `PATH`; use an absolute `AGENT_BRAIN_STATE_DIR` |
| Tools missing / empty | Start the backend first (`agent-brain start`) and index something |
| `.mcp.json` not valid JSON | `install-agent --with-mcp` refuses to merge into a corrupt file — fix/remove it and re-run |
| 401 from a remote server | Set `AGENT_BRAIN_MCP_AUTH=oauth` on the client; confirm the server's `AGENT_BRAIN_OAUTH_RESOURCE` |
| 403 `insufficient_scope` | The token lacks the tool's scope (e.g. calling an index tool with only `agent-brain:read`) |

See also `docs/MCP_USER_GUIDE.md` and the MCP package README for the full reference.
