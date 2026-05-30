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

## Full guide

For per-host configuration (Claude Desktop, Cursor / Windsurf, Claude Agent SDK, LangChain DeepAgents), the full tool/resource/prompt reference with schemas, worked end-to-end examples, error mapping, and troubleshooting, see **[`docs/MCP_USER_GUIDE.md`](../docs/MCP_USER_GUIDE.md)**.

For internal design (UDS bind strategy, package layering, deferred work), see [`docs/plans/2026-05-28-mcp-uds-transport-design.md`](../docs/plans/2026-05-28-mcp-uds-transport-design.md).

## License

MIT
