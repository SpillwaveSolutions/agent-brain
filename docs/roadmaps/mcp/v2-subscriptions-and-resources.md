---
roadmap: mcp-v2
status: planned
source_design: docs/plans/2026-05-28-mcp-uds-transport-design.md
milestone: MCP v2 (subscriptions + http transport)
---

# MCP v2 — Resource subscriptions + deferred URI schemes + Streamable HTTP + 9 remaining tools

> Issue body for `gh issue create --body-file docs/roadmaps/mcp/v2-subscriptions-and-resources.md`.
> See plan `docs/plans/2026-05-28-mcp-uds-transport-design.md` §11 (v2 row) and §15.1.

## Context

v1 (shipped in 10.1.0, see `docs/plans/2026-05-28-mcp-uds-transport-design.md`) delivered:

- UDS transport (`agent-brain-uds`)
- Minimal MCP server (`agent-brain-mcp`) with **7 tools + 5 read-only resources + 6 prompts**, stdio only
- `GET /health/config` endpoint feeding `corpus://config`
- CLI HTTP/UDS dual transport (`agent-brain --transport {auto,uds,http}`)

v2 picks up everything v1 deferred for scope: resource subscriptions, the 2 resource schemes that require new server endpoints, Streamable HTTP transport, `wait_for_job` with progress, and the 9 deferred tools.

## Scope

### Resource subscriptions (`resources/subscribe`)

- Server-side polling cadence:
  - 1s for active jobs (`job://<id>`)
  - 30s for `corpus://status`
  - watcher-driven for `corpus://folders`
- Emit `notifications/resources/updated` per the current MCP spec.

### Deferred resource schemes (require new server endpoints)

- `chunk://<chunk_id>` — needs `GET /query/chunk/{id}` (new, O(1) lookup)
- `graph-entity://<type>/<id>` — needs `GET /graph/entity/{type}/{id}` (new)
- `job://<job_id>` — uses existing `GET /index/jobs/{id}` but is only valuable once subscriptions land (otherwise it duplicates the `get_job` tool)
- `file://<abs-path>` — gated by indexed roots + MCP `roots/list` (needs a sandbox design)
- `resources/templates/list` for the above

### Streamable HTTP MCP transport

- Add alongside stdio (loopback only in v2, no auth)
- New `--transport http` flag on `agent-brain-mcp`
- Verified via the official MCP SDK HTTP client

### 9 remaining tools (from the original 16-tool set)

- `explain_result`
- `add_documents`
- `inject_documents`
- `wait_for_job` (must emit `notifications/progress` at least every 2s during indexing)
- `list_folders`
- `remove_folder`
- `cache_status`
- `clear_cache`
- `list_file_types`

## Prerequisites

- New server endpoints designed and shipped: `GET /query/chunk/{id}`, `GET /graph/entity/{type}/{id}`.
- v1 has shipped green for one release cycle (target: 10.2.0).
- New packages folded into root `task before-push` (DR-5 from v1 plan).

## Definition of done

- Own design doc filed at `docs/plans/YYYY-MM-DD-mcp-v2-subscriptions.md`.
- `resources/subscribe` + `notifications/resources/updated` tested end-to-end against the official MCP SDK.
- All deferred resource schemes addressable via `resources/read`.
- Streamable HTTP transport tested via the official MCP SDK HTTP client.
- `wait_for_job` emits `notifications/progress` at least every 2s during indexing.
- All 16 total tools (7 from v1 + 9 new) covered by parameterized contract tests.

## Explicitly NOT in scope (deferred to v3 / v4)

- CLI-via-MCP — v3 (`docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md`)
- Framework adapter matrix — v3
- OAuth — v4 (`docs/roadmaps/mcp/v4-oauth-for-remote.md`)

## Source design

`docs/plans/2026-05-28-mcp-uds-transport-design.md` §11 (v2 row), §15.1.
