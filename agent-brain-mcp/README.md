# agent-brain-mcp

Model Context Protocol server for [Agent Brain](https://github.com/SpillwaveSolutions/agent-brain).

Exposes the running Agent Brain instance as an MCP server consumable by Claude Desktop, Cursor, Windsurf, Claude Agent SDK, LangChain DeepAgents, and any other MCP-aware client.

## Surface (v10.4)

- **16 Tools**: `search_documents`, `query_count`, `explain_result`, `index_folder`, `add_documents`, `inject_documents`, `get_job`, `list_jobs`, `wait_for_job`, `cancel_job`, `list_folders`, `remove_folder`, `cache_status`, `clear_cache`, `list_file_types`, `server_health`
- **5 Resources** (read-only): `corpus://config`, `corpus://status`, `corpus://health`, `corpus://providers`, `corpus://folders`
- **6 Prompts**: `find-callers`, `find-implementation`, `explain-architecture`, `compare-search-modes`, `onboard-to-codebase`, `audit-indexed-folders`
- **Listen transport**: stdio (default) or Streamable HTTP (`--transport http`)
- **Backend**: UDS (preferred) or HTTP, selectable via `--backend {auto,uds,http}`
- **Auth**: OAuth 2.1 on the HTTP listen transport (`AGENT_BRAIN_AUTH=oauth`), **off by default**

The full v1–v4 MCP roadmap shipped by Agent Brain 10.4.0; see [`CHANGELOG.md`](../docs/CHANGELOG.md)
and the [MCP User Guide](../docs/MCP_USER_GUIDE.md). Register for Claude Code with
`agent-brain install-agent --agent claude --with-mcp`.

## Install

```bash
pip install agent-brain-ag-mcp
```

The PyPI distribution is `agent-brain-ag-mcp`; the installed console script is `agent-brain-mcp`.

## Quick config

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

## Transport selection (v10.2+)

`agent-brain-mcp` supports two **listen transports** for talking to MCP clients:

- **stdio** (default) — Claude Desktop, Claude Code, and most MCP CLI clients use this. No flags needed.
- **http** (Streamable HTTP, new in v10.2) — for IDE clients and framework adapters that prefer HTTP/SSE. Wraps the official MCP SDK's `StreamableHTTPSessionManager` over an in-process uvicorn server.

### stdio (default)

```bash
agent-brain-mcp
```

No `--transport` flag needed. Existing Claude Desktop / Code installs keep working unchanged.

### Streamable HTTP

```bash
agent-brain-mcp --transport http --host 127.0.0.1 --port 8765
```

Then connect from an MCP client using the official Python SDK:

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
```

Liveness probe (no MCP handshake required):

```bash
curl http://127.0.0.1:8765/healthz
# → {"status":"ok","transport":"http"}
```

### Loopback bind + authentication

`--host` accepts **only** `127.0.0.1`, `localhost`, or `::1` (no `--allow-public-bind` escape
hatch). For remote access, run the loopback HTTP listener **behind a gateway / reverse proxy** and
enable authentication rather than binding a public interface directly.

**Authentication (v10.4):** OAuth 2.1 on the HTTP listen transport is **off by default**
(`AGENT_BRAIN_AUTH=none`). Set `AGENT_BRAIN_AUTH=oauth` (+ `AGENT_BRAIN_OAUTH_RESOURCE`) to require
audience-bound Bearer tokens with per-tool scopes (`agent-brain:read|index|admin|subscribe`,
default-deny on writes). Co-located and split AS/RS topologies are supported. See the
[MCP User Guide → Authentication](../docs/MCP_USER_GUIDE.md#authentication).

**Local trust model (no-auth mode):** with `AGENT_BRAIN_AUTH=none`, any process running as the same
user on this host can reach the port and drive MCP tools (including destructive ones like
`cancel_job`). Do not run `--transport http` unauthenticated on a shared / multi-user host without
external sandboxing.

### No silent fallback

Invalid `--transport` values, non-loopback `--host` values, and port-in-use errors fail loudly. There is no fallback from `http` to `stdio` (or vice versa). Exit codes are distinct:

| Failure mode                          | Exit code |
| ------------------------------------- | --------- |
| Click usage error (bogus value, etc.) | 1         |
| Non-loopback host rejected            | 1         |
| Port already in use (Plan 02 D-12)    | 2         |

`AGENT_BRAIN_MCP_TRANSPORT` is reserved as an environment variable but **not honored** in v10.2 — explicit `--transport` is required to opt into HTTP (Phase 53 D-02).

### Backend axis is independent

`--backend {auto,uds,http}` controls how `agent-brain-mcp` reaches `agent-brain-serve` (the indexing backend). It is **orthogonal** to `--transport`. See `docs/MCP_USER_GUIDE.md` for the two-axis transport model.

## Full guide

For per-host configuration (Claude Desktop, Cursor / Windsurf, Claude Agent SDK, LangChain DeepAgents), the full tool/resource/prompt reference with schemas, worked end-to-end examples, error mapping, and troubleshooting, see **[`docs/MCP_USER_GUIDE.md`](../docs/MCP_USER_GUIDE.md)**.

For internal design (UDS bind strategy, package layering, deferred work), see [`docs/plans/2026-05-28-mcp-uds-transport-design.md`](../docs/plans/2026-05-28-mcp-uds-transport-design.md).

## License

MIT
