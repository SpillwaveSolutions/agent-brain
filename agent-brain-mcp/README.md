# agent-brain-mcp

Model Context Protocol server for [Agent Brain](https://github.com/SpillwaveSolutions/agent-brain).

Exposes the running Agent Brain instance as an MCP server consumable by Claude Desktop, Cursor, Windsurf, Claude Agent SDK, LangChain DeepAgents, and any other MCP-aware client.

## v1 surface

- **7 Tools**: `search_documents`, `query_count`, `index_folder`, `get_job`, `list_jobs`, `cancel_job`, `server_health`
- **5 Resources** (read-only): `corpus://config`, `corpus://status`, `corpus://health`, `corpus://providers`, `corpus://folders`
- **6 Prompts**: `find-callers`, `find-implementation`, `explain-architecture`, `compare-search-modes`, `onboard-to-codebase`, `audit-indexed-folders`
- **Transport**: stdio
- **Backend**: UDS (preferred) or HTTP, selectable via `--backend {auto,uds,http}`

Shipped in Agent Brain 10.1.0 (May 2026); see [`CHANGELOG.md`](../docs/CHANGELOG.md). v2 (subscriptions + streamable HTTP), v3 (CLI-via-MCP + framework adapters), and v4 (OAuth) are tracked under [`docs/roadmaps/mcp/`](../docs/roadmaps/mcp/).

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

### Loopback only — no auth in v10.2

`--host` accepts **only** `127.0.0.1`, `localhost`, or `::1`. Binding to a public interface is rejected at startup with the error `--host must be one of {127.0.0.1, localhost, ::1} (auth is deferred to v4; binding to public interfaces is unsafe in v2)`. There is **no `--allow-public-bind` escape hatch** — authentication is reserved for MCP v4 (OAuth 2.1; tracked as [OAUTH-01](https://github.com/SpillwaveSolutions/agent-brain/issues/188)).

The startup banner names this constraint explicitly:

```
MCP server listening on http://127.0.0.1:8765/mcp (loopback only, no auth — do NOT expose this port)
```

**Local trust model:** any process running as the same user on this host can reach the port and drive MCP tools (including `cancel_job` which is annotated `destructiveHint: true`). Do not run `--transport http` on a shared / multi-user host without external sandboxing.

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
