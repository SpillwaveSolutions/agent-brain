# MCP Server for Agent Brain — Design Scoping Document

> **⚠️ Superseded by [`2026-05-28-mcp-uds-transport-design.md`](./2026-05-28-mcp-uds-transport-design.md)** (2026-05-28).
> The v1 plan there carries forward this doc's discipline — opt-in QA gate, no resources/prompts deferred to later phases — but bundles UDS + MCP into one release and expands the v1 surface to 7 tools + 5 read-only resources + 6 prompts. Read the new plan for current scope; this file remains for historical context.

**Status:** Design-only scoping artifact. **No code shipped.** (Superseded.)
**Tracking issue:** [#153 — feat(integration): native MCP server (sub-20ms direct protocol)](https://github.com/SpillwaveSolutions/agent-brain/issues/153)
**Strategic context:** [`docs/plans/2026-strategic-recommendations-integration.md`](./2026-strategic-recommendations-integration.md), section "Transport Layer Strategy" (R5 / MCP listed third behind HTTP and UDS)
**Date:** 2026-05-26

---

## 1. What this document is — and is not

This is a **scoping artifact** that names the MCP surface and captures the design decisions
already worked through in review. It is **not** an implementation plan, a roadmap commitment,
or a marketing announcement.

Issue #153 was filed deliberately small:

> Scope the MCP surface, name the tools (`search`, `index`, `status`, `jobs`), and sketch
> the entry point binary. Defer the actual implementation until UDS lands and the user
> reassesses.

The strategic doc explicitly de-prioritizes MCP relative to a planned Unix Domain Socket
transport — MCP is positioned as "optional ecosystem integration," not the fast path. So
this document exists so that if and when MCP work resumes, the surface design is captured
rather than re-derived under time pressure.

Nothing in this document obligates anyone to build the package described. If the
MCP-vs-UDS question resolves in favor of UDS, this doc can be archived without code impact.

---

## 2. Tools (4)

Tool I/O contracts are **derived from the existing Pydantic models** in `agent-brain-rag`
(the published name of the `agent-brain-server` package). MCP tool schemas should be
emitted via `Model.model_json_schema()` so they cannot drift from the REST API contract.

| Tool name | Input model | Output model | Backs onto |
|---|---|---|---|
| `search` | `QueryRequest` (`agent-brain-server/agent_brain_server/models/query.py`) | `QueryResponse` (same file) | `POST /query/` → `QueryService.execute_query` (`agent-brain-server/agent_brain_server/services/query_service.py:169`) |
| `index` | `McpIndexRequest` (defined in §6; restricted subset of `IndexRequest`) | `IndexResponse` (`agent-brain-server/agent_brain_server/models/index.py`) | `POST /index/` |
| `status` | _(none)_ | `HealthStatus` (`agent-brain-server/agent_brain_server/models/health.py`) | `GET /health/status` |
| `jobs` | `McpJobsRequest` (`action: list \| get \| cancel`, `job_id`, `limit`) | `JobListResponse` \| `JobDetailResponse` \| cancel-ack | `GET /index/jobs/`, `GET /index/jobs/{id}`, `DELETE /index/jobs/{id}` (`agent-brain-server/agent_brain_server/api/routers/jobs.py`) |

Notes:

- `QueryMode` enum (`agent-brain-server/agent_brain_server/models/query.py:9`) defines the
  accepted `mode` values: `vector`, `bm25`, `hybrid`, `graph`, `multi`. Defaults flow from
  the server model — do not redeclare.
- The `jobs` tool uses a single tool with an `action` arg (matches issue spec
  `jobs(action, job_id)`) rather than three separate tools, to keep the agent's tool list
  short. The tool description must explicitly note that `cancel` returns 409 when the
  target job is already in a terminal state.

---

## 3. Resources (4)

Resources are MCP's URI-addressable read-only data. Use for state an agent might want to
attach to context without burning a tool call.

| URI | Returns | Backs onto |
|---|---|---|
| `agent-brain://status` | `HealthStatus` (same shape as `status` tool) | `GET /health/status` |
| `agent-brain://folders` | `FolderListResponse` | `GET /index/folders/` |
| `agent-brain://config` | **Sanitized** config snapshot — see §7 | `agent_brain_server.config.settings` |
| `agent-brain://jobs/{job_id}` | `JobDetailResponse` (parameterized resource template) | `GET /index/jobs/{job_id}` |

Search results are deliberately **not** a resource — they are query-specific and dynamic;
they belong in the `search` tool.

---

## 4. Prompts — explicitly deferred

Issue #153 names tools, not prompts. The strategic doc treats prompts as a later concern.
This scoping doc **does not** specify a prompt surface.

When prompt design happens (a separate ticket, after the surface is otherwise settled),
candidates worth considering — but not committing to here — include search-and-synthesize,
mode comparison, and index-then-explore. Documented here only so a future implementer
doesn't reflexively reintroduce them by default.

---

## 5. Dual-backend design

The MCP process supports two backends. Backend is chosen at startup; both share the same
`Backend` Protocol so tool implementations are backend-agnostic.

### 5.1 HTTP backend (default; lightweight)

- Thin httpx wrapper around the existing `agent-brain-serve` REST API.
- Default for the typical Claude Code workflow, where the per-project server is already
  running.
- Adds a localhost HTTP hop but starts in tens of ms (no LlamaIndex/ChromaDB import).
- **Route paths verified against the existing CLI client**
  (`agent-brain-cli/agent_brain_cli/client/api_client.py:263,432`): `/query/`, `/index/`,
  `/index/folders/`, `/index/jobs/`.
- Implementation note: prefer reusing or refactoring `DocServeClient`
  (`agent-brain-cli/agent_brain_cli/client/api_client.py:98`) over parallel-implementing.
  Server 422 validation errors must surface to the MCP client as structured Pydantic
  errors, not be swallowed.

### 5.2 Embedded backend (optional Poetry extra)

- Imports `agent_brain_server.services.*` and calls `QueryService.execute_query`,
  `IndexingService.*`, `JobQueueService.*`, `FolderManager.*` directly in-process.
- Targets issue #153's sub-20ms latency goal.
- Pulls the full LlamaIndex / ChromaDB / tree-sitter tree at install time, so it is
  gated behind a Poetry optional extra: `agent-brain-mcp[embedded]`.
- Default `pip install agent-brain-mcp` installs only the mcp SDK, httpx, pydantic, and
  the `agent-brain-rag` models — no heavy server runtime.
- Acquires the project's `state-dir` file lock at startup. **Fails loudly** if another
  process (a running `agent-brain-serve`, or another embedded MCP instance) already holds
  it. No silent fallback to HTTP — that would mask a configuration conflict the user
  needs to resolve.

### 5.3 Selector

CLI flag `--backend auto|http|embedded` (env var `AGENT_BRAIN_MCP_BACKEND`).

1. `auto` (default): prefer HTTP if a running server is discoverable via
   `state-dir/runtime.json`; else try embedded if the `[embedded]` extra is installed;
   else exit non-zero with a clear "no backend available" message.
2. `http`: fail non-zero if no server is reachable. Do not silently fall back.
3. `embedded`: fail non-zero if the `[embedded]` extra isn't installed or the state-dir
   lock can't be acquired. Do not silently fall back.

The principle: surface conflicts and missing pieces explicitly. Silent fallbacks make
this kind of multi-process tooling impossible to debug.

---

## 6. `McpIndexRequest` — deliberately narrower than `IndexRequest`

The full `IndexRequest` (exposed by the REST API and accepted by `DocServeClient.index` at
`agent-brain-cli/agent_brain_cli/client/api_client.py:284`) supports flags that are
inappropriate for an MCP-driven agent to set autonomously. The MCP variant exposes a
restricted subset.

### Included

| Field | Default (matches `IndexRequest`) | Notes |
|---|---|---|
| `path` | _(required)_ | Filesystem path to index |
| `include_code` | `false` | AST-based code chunking on top of plain document chunking |
| `recursive` | `true` | Recurse into subdirectories |
| `chunk_size` | `512` | Target chunk size in tokens |
| `include_patterns` | `null` | Optional include globs |
| `exclude_patterns` | `null` | Optional exclude globs |
| `file_type_preset` | `null` | Named preset (e.g. `code`, `docs`) |
| `dry_run` | `false` | Validate without enqueuing |

### Omitted on purpose

| Field | Rationale |
|---|---|
| `allow_external` | Agent could index sensitive paths outside the project; require a human to set this via the REST API or CLI. |
| `force` | Agent could trigger expensive re-index loops; humans only. |
| `injector_*` (script path + options) | Content injection requires a script path; out of scope for MCP tool I/O. |
| `watch` / `watch_*` | Long-running watcher mode; not appropriate for a single MCP tool call. |

A future implementer should treat this list as the contract — adding any of these to the
MCP surface requires a documented decision, not a casual expansion.

---

## 7. Config-resource sanitization

The `agent-brain://config` resource must use an **allowlist** of safe configuration keys,
not a blocklist. Allowlists fail safe when new env vars are added.

In addition to the allowlist, an explicit deny-pattern pass strips any key matching
`*_API_KEY`, `*_SECRET`, `*_TOKEN`. Example keys that SHOULD appear: embedding model
name, summarization model name, retrieval mode defaults, GraphRAG enabled flag, chunk
size defaults. Example keys that MUST NOT appear: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`AGENT_BRAIN_STATE_DIR` (potentially path-leak-y depending on context — review at impl
time).

---

## 8. Schema-derivation strategy

When implementation lands, MCP tool input schemas should be produced via
`Model.model_json_schema()` on the existing Pydantic models, snapshotted into a declarative
surface registry at build time. A regenerate-and-compare test fails the build if a
server-side default changes without the MCP contract being updated.

Concretely: if someone changes `QueryRequest.similarity_threshold` from `0.3` to `0.5` in
`agent-brain-server/agent_brain_server/models/query.py:34`, the MCP schema snapshot must
either auto-update (if the regen step is in CI) or the comparison test must fail. Drift
should never be silent.

---

## 9. Resolver reuse — prerequisite to implementation

`agent-brain-cli/agent_brain_cli/config.py:328,376` already implements state-dir and
base-URL resolution (including `resolve_project_root` and `runtime.json` discovery). The
MCP package should not duplicate this logic. **Before any MCP implementation PR**:

1. Extract the resolver(s) from `agent-brain-cli/agent_brain_cli/config.py` into a shared
   helper module in `agent-brain-rag` (the server package, which both the CLI and MCP
   will depend on for models anyway).
2. Update the CLI to consume the extracted helper.
3. Verify the CLI's tests still pass.

The MCP package then imports from the shared helper. One resolver, three consumers (CLI,
MCP HTTP backend, MCP embedded backend).

---

## 10. Entry-point binary sketch

The Phase-2 binary is `agent-brain-mcp`, mirroring `agent-brain-serve` and `agent-brain`:

```
agent-brain-mcp [--backend auto|http|embedded] \
                [--state-dir PATH] [--project-dir PATH] \
                [--base-url URL] \
                [--describe-surface]
```

`--describe-surface` emits the surface registry (tools + resources schemas) as JSON to
stdout and exits 0, without starting the stdio server. This is useful for client
introspection and for reviewers verifying the contract without spinning up the protocol.

Transport: stdio (the standard transport Claude Code uses to launch MCP servers as
subprocesses). HTTP/SSE transport is not needed for the initial implementation.

---

## 11. Phasing

| Phase | Deliverable | Status |
|---|---|---|
| **Phase 1** (this doc) | Scoping document. No code, no Taskfile, no plugin entries. | Shipped in this PR. |
| **Phase 2** (deferred, gated on the owner's MCP-vs-UDS decision) | New `agent-brain-mcp/` Poetry package with both backends implemented, MCP tools and resources registered, surface registry with drift-test, import-isolation test, protocol-level smoke test, opt-in Taskfile entries (`task install:mcp`, `task test:mcp`) — but **not** wired into root `task before-push` or `task pr-qa-gate` until the package is stable. Single PR, no skeleton intermediate. Tracked in [#167](https://github.com/SpillwaveSolutions/agent-brain/issues/167). | Not started. |
| **Phase 3** (further deferred) | Prompts, sampling, streaming progress notifications, plugin auto-registration, root QA-gate inclusion. | Not started. |

The Phase-1 → Phase-2 gap is intentional: shipping a skeleton that registers active MCP
tools whose bodies always raise `NotImplementedError` is a discoverable-but-broken surface
for any MCP client. Either ship the contract on paper (Phase 1) or ship working tools
(Phase 2) — never an in-between.

---

## 12. Open question

The strategic doc currently positions MCP third in transport priority behind HTTP and UDS.
**This document does not resolve that priority** — it only ensures that if MCP wins (or
both ship), the design is already worked through. The owner should explicitly decide
whether to proceed to Phase 2 after the UDS transport lands and its real-world
characteristics are visible.
