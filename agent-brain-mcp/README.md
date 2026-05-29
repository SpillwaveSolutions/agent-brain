# agent-brain-mcp

Model Context Protocol server for [Agent Brain](https://github.com/SpillwaveSolutions/agent-brain).

Exposes the running Agent Brain instance as an MCP server consumable by Claude Desktop, Claude Code, OpenCode, Gemini CLI, and any other MCP-aware client.

## v1 surface (Phase 4)

- **7 Tools**: `search_documents`, `query_count`, `index_folder`, `get_job`, `list_jobs`, `cancel_job`, `server_health`
- **5 Resources** (read-only): `corpus://config`, `corpus://status`, `corpus://health`, `corpus://providers`, `corpus://folders`
- **6 Prompts**: `find-callers`, `find-implementation`, `explain-architecture`, `compare-search-modes`, `onboard-to-codebase`, `audit-indexed-folders`
- **Transport**: stdio
- **Backend**: UDS (preferred) or HTTP, selectable via `--backend {auto,uds,http}`

## Status

Phase 0 scaffold (10.0.7) — public surface lands in Phase 4.
See [`docs/plans/2026-05-28-mcp-uds-transport-design.md`](../docs/plans/2026-05-28-mcp-uds-transport-design.md).

## Claude Desktop / Code config (when Phase 4 ships)

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

## License

MIT
