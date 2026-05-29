# agent-brain-uds

Unix-domain-socket transport for [Agent Brain](https://github.com/SpillwaveSolutions/agent-brain).

**Client-side only.** This package provides:

- Socket path resolution (`resolve_socket_path`) consistent with `agent-brain-server`'s state-dir layout.
- Permission validation (`validate_socket`) — owner-UID match, no group/world bits, no-symlink check.
- `httpx`-compatible client factory (`make_client` / `make_async_client`) speaking HTTP/1.1 over UDS.

The corresponding server-side bind (`agent_brain_server.api.uds_bind`) lives in `agent-brain-server` to keep the dep direction acyclic.

## Status

Phase 0 scaffold (10.0.7) — public surface lands in Phase 1.
See [`docs/plans/2026-05-28-mcp-uds-transport-design.md`](../docs/plans/2026-05-28-mcp-uds-transport-design.md).

## License

MIT
