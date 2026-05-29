# Agent Brain — MCP Server + UDS Transport (v1)

**Date:** 2026-05-28
**Status:** Plan for review (refined via Ultraplan against the v2 draft)
**On approval:** copy to `docs/plans/2026-05-28-mcp-uds-transport-design.md` per CLAUDE.md
**Supersedes:** `docs/plans/2026-mcp-server-design.md` (the existing design-only scoping artifact — note the actual filename is `2026-mcp-server-design.md`, not the `2026-05-26-…` referenced in earlier drafts; the supersede header in the implementation PR must use the real path)

---

## 1. Context

Agent Brain ships at 10.0.7 as a localhost-only FastAPI service. Two real clients exist today:

- `agent-brain-cli` — Click app that opens an `httpx.Client` against `runtime.json::base_url`.
- The Claude Code plugin — shells out to the CLI.

`docs/plans/2026-mcp-server-design.md` already scoped a 4-tool / 4-resource MCP surface but was deliberately deferred until UDS was decided. The strategic doc still ranks transports HTTP → UDS → MCP. This plan ships both UDS and a minimal MCP server in the same release because they share one piece of infrastructure (a UDS-aware `httpx.Client`) and one verification path (CLI parity tests under each transport).

### What v1 buys

1. UDS as a faster, project-scoped local transport (no port, just a 0600 socket under `<state_dir>/`).
2. A stdio MCP server exposing **7 tools, 5 read-only Resources, and 6 Prompts** — enough for Claude Desktop / Code to run real RAG sessions, see project state at a glance, and trigger common workflows without shelling out.
3. CLI gains `--transport {http,uds,auto}`; default behavior unchanged.
4. One tiny new HTTP endpoint, `GET /health/config`, exposing storage backend type + which stores are enabled (vector / BM25 / graph) + active reranker — so the `corpus://config` Resource has a real data source.

### What v1 does **not** ship

- MCP resource **subscriptions** (no `resources/subscribe` — clients use `resources/read` to fetch current state on demand)
- MCP **sampling / elicitation / logging / completions** capabilities
- Streamable HTTP MCP transport (stdio only)
- CLI-via-MCP (CLI never speaks MCP in v1)
- Framework-adapter matrix
- OAuth / remote MCP
- The 9 deferred tools from the original plan (`explain_result`, `add_documents`, `inject_documents`, `wait_for_job`, `list_folders`, `remove_folder`, `cache_status`, `clear_cache`, `list_file_types`)
- The 2 deferred resource schemes that would need new server endpoints (`chunk://<id>` needs `GET /query/chunk/{id}`; `graph-entity://<type>/<id>` needs `GET /graph/entity/{type}/{id}`)

Those are listed in §11 as later work, each requiring its own design doc.

---

## 2. Verified facts about the current code

Before designing, the codebase was checked against earlier drafts. Items below are corrections used in this plan:

| Claim in earlier draft | Reality on disk |
|---|---|
| `docs/plans/2026-05-26-mcp-server-design.md` | Actual filename is `docs/plans/2026-mcp-server-design.md` |
| `DELETE /index/folders/{path}` | `DELETE /index/folders/` (path lives in `FolderDeleteRequest` body) — `routers/folders.py:61` |
| New `Backend` Protocol layer | `StorageBackendProtocol` already exists in `agent_brain_server/storage/protocol.py:94`. A new `Backend` would collide in tool output and confuse readers. We extend the existing `DocServeClient` (`agent_brain_cli/client/api_client.py:158`) instead — one method per call, already 13 methods, already the seam every CLI command goes through. |
| e2e-cli adapter for UDS / MCP | `e2e-cli/adapters/` holds AI-runtime adapters (`claude.sh`), not transport adapters — wrong location. UDS/MCP coverage lives in unit + integration tests under the new packages. |
| Release lockstep updates "4 new version files" | The existing flow updates 5 files (`.claude/commands/ag-brain-release.md:46-51`). Adding two packages adds 4 lines: 2 × `pyproject.toml` + 2 × `__init__.py`. Total becomes 9 files. |
| `agent-brain-server/agent_brain_server/api/main.py:694` is where routers mount | Confirmed — `app.include_router(...)` block runs from line 694 to 699 |
| CLI URL resolution chain | Already implemented at `agent_brain_cli/config.py:376-414` (`get_server_url`: env → runtime.json → config file → default). New transport selection should plug into this same function, not create a parallel chain. |
| `agent_brain_server.models` package is dep-clean | Confirmed — only stdlib + Pydantic. Safe for the MCP package to import for JSON-Schema generation. |

---

## 3. Architecture

```
                  ┌───────────────────────────────────┐
                  │   agent-brain-server (existing)   │
                  │  ┌─────────────────────────────┐  │
                  │  │ FastAPI app (routes ↔ same) │  │
                  │  └─────────────────────────────┘  │
                  │  ┌─────────────────────────────┐  │
   New, opt-in →  │  │ api/uds_bind.py  (NEW)      │  │ ← writes runtime.json
                  │  │ two-Server orchestration    │  │   with socket_path
                  │  └─────────────────────────────┘  │
                  └───────┬─────────────────┬─────────┘
                          │ TCP             │ AF_UNIX
                          │ 127.0.0.1:port  │ <state_dir>/agent-brain.sock
                          │                 │
            ┌─────────────┼─────────────────┼──────────────┐
            │             │                 │              │
   ┌────────▼───────┐ ┌───▼─────────────────▼──┐ ┌────────▼─────────┐
   │ agent-brain-   │ │ agent-brain-uds (NEW)  │ │ agent-brain-mcp  │
   │ cli (modified) │ │ tiny client-only pkg:  │ │      (NEW)       │
   │                │ │  - socket path resolver│ │  stdio MCP server│
   │ --transport    │ │  - perm validator      │ │   7 tools        │
   │   http|uds|auto│ │  - httpx.Client factory│ │                  │
   │                │ │  (no Backend protocol) │ │ depends on:      │
   │ depends on:    │ │                        │ │  - agent-brain-  │
   │  - agent-brain-│ │ depends on:            │ │    uds           │
   │    rag (models)│ │  - httpx>=0.27         │ │  - agent-brain-  │
   │  - agent-brain-│ │  - agent-brain-rag     │ │    rag (models)  │
   │    uds (NEW)   │ │    (models only)       │ │  - mcp (SDK)     │
   └────────────────┘ └────────────────────────┘ └──────────────────┘
```

### Layering invariants (enforced by import-linter)

1. `agent_brain_server` MUST NOT import from `agent_brain_uds`, `agent_brain_mcp`, or `agent_brain_cli`.
2. `agent_brain_uds` MAY import only from `agent_brain_server.models` (+ stdlib + httpx).
3. `agent_brain_mcp` MUST NOT import from `agent_brain_server.services`, `.api`, `.indexing`, `.storage` — all backend calls go through HTTP/UDS via the shared client. MAY import from `agent_brain_server.models` and `agent_brain_uds`.
4. `agent_brain_cli` MAY import from `agent_brain_uds` and `agent_brain_server.models`.

These four rules eliminate the cycle the earlier draft would have created (its `Backend` protocol was going to live in `agent-brain-uds` while also being consumed by `agent-brain-server` for tests).

---

## 4. Package layout

### 4.1 `agent-brain-uds` (NEW — client-side only, ~200 LOC)

```
agent-brain-uds/
├── pyproject.toml          # name: agent-brain-uds; deps: httpx>=0.27, agent-brain-rag>=10.1.0
├── Taskfile.yml            # install / test / lint / typecheck / format / pr-qa-gate
├── agent_brain_uds/
│   ├── __init__.py         # re-exports: resolve_socket_path, validate_socket, make_client
│   ├── paths.py            # resolve_socket_path(state_dir=None) -> Path  (+ pointer-file fallback)
│   ├── permissions.py      # validate_socket(path) -> None | raises
│   ├── client.py           # make_client(state_dir=None, timeout=30.0) -> httpx.Client
│   │                       # make_async_client(...) -> httpx.AsyncClient
│   └── errors.py           # AgentBrainUdsError / SocketNotFoundError /
│                           # SocketPermissionError / SocketStaleError /
│                           # SocketPathTooLongError
└── tests/
    ├── conftest.py
    ├── test_paths.py            # 5 resolver branches + pointer-file roundtrip
    ├── test_permissions.py      # adversarial: symlink, world-readable, cross-uid, parent-dir mode
    └── test_client_roundtrip.py # spawn stub uvicorn UDS, roundtrip a /health/ call
```

**Deliberately not in this package**: a `Backend` Protocol. The earlier draft would have had this pkg own a 13-method protocol that both CLI and MCP must implement. That's parallel infrastructure to the already-13-method `DocServeClient` and triples the lines of code being shipped without buying anything. Instead, both CLI and MCP get an `httpx.Client` from `make_client()` and pass it to whichever client class they want.

### 4.2 `agent-brain-mcp` (NEW)

```
agent-brain-mcp/
├── pyproject.toml          # deps: mcp>=1.0, agent-brain-uds>=10.1.0, agent-brain-rag>=10.1.0
├── Taskfile.yml            # install / test / lint / typecheck / format / pr-qa-gate / mcp:contract
├── agent_brain_mcp/
│   ├── __init__.py
│   ├── server.py           # MCP stdio entry; capability negotiation; version-compat check
│   ├── config.py           # CLI flags: --backend {auto,uds,http}, --backend-url, --state-dir
│   ├── client.py           # ApiClient — thin httpx wrapper, ~80 LOC, takes an httpx.Client
│   │                       # (does NOT import DocServeClient — keeps MCP free of CLI dep)
│   ├── tools/
│   │   ├── __init__.py     # TOOL_REGISTRY = {name: (handler, input_model, output_model, annotations)}
│   │   ├── search.py       # search_documents
│   │   ├── meta.py         # query_count, server_health
│   │   ├── index.py        # index_folder
│   │   └── jobs.py         # get_job, list_jobs, cancel_job
│   ├── resources/          # 5 resources (§6.5) — read-only, no subscriptions
│   │   ├── __init__.py     # RESOURCE_REGISTRY
│   │   └── corpus.py       # corpus://config | status | health | providers | folders
│   ├── prompts/            # 6 prompt templates (§6.6)
│   │   ├── __init__.py     # PROMPT_REGISTRY
│   │   ├── find_callers.py
│   │   ├── find_implementation.py
│   │   ├── explain_architecture.py
│   │   ├── compare_search_modes.py
│   │   ├── onboard_to_codebase.py
│   │   └── audit_indexed_folders.py
│   ├── schemas.py          # JSON Schema generation via pydantic.TypeAdapter
│   └── errors.py           # HTTP → JSON-RPC mapping
└── tests/
    ├── conftest.py
    ├── test_initialize.py        # serverInfo + tools/resources/prompts capabilities
    ├── test_tools_list.py        # 7 tools advertised with correct schemas
    ├── test_each_tool.py         # parameterized: 7 tools × valid args against fake client
    ├── test_resources_list.py    # 5 resources advertised
    ├── test_resources_read.py    # each resource returns expected JSON shape
    ├── test_prompts_list.py      # 6 prompts advertised with arguments
    ├── test_prompts_get.py       # each prompt expands with sample arguments
    ├── test_error_mapping.py     # HTTP 400/404/409/422/500/502/503/504 → MCP errors
    ├── test_version_compat.py    # refuse to start if server /health version below pinned floor
    └── test_e2e_stdio.py         # official MCP Python SDK as client; full handshake + tool/resource/prompt call
```

**Why MCP has its own thin `ApiClient` instead of importing `DocServeClient` from CLI**: avoids `agent-brain-mcp → agent-brain-cli` dep direction. `agent-brain-cli` imports Click + Rich at module init; we don't want either in the MCP server process. The duplication is ~80 LOC and bounded.

### 4.3 `agent-brain-server` (modified, additive only)

- NEW: `agent_brain_server/api/uds_bind.py` — `serve_dual()` and `serve_uds_only()` helpers.
- MODIFIED: `agent_brain_server/api/main.py` — `run()` (line 726) honors `--uds` / `--uds-only` and `AGENT_BRAIN_UDS*` env, delegates to `uds_bind` when set.
- MODIFIED: `agent_brain_server/runtime.py` — `RuntimeState` gains optional `socket_path: str | None = None`. Backwards compatible (old runtime.json files without the field still parse).
- NEW: `GET /health/config` endpoint in `agent_brain_server/api/routers/health.py` — returns a small `ConfigStatus` model (~30 LOC):
  ```python
  {
    "storage_backend": "chroma" | "postgres",
    "stores": { "vector": true, "bm25": true, "graph": <bool from indexing service> },
    "reranker_enabled": bool,
    "embedding_model": str,                # active embedding model name
    "rerank_model": str | None,
    "graph_extractor": str | None,         # GRAPH_LANGEXTRACT_PROVIDER if set
    "watcher_running": bool
  }
  ```
  All values pulled from existing `settings`, `factory.get_effective_backend_type()`, and the indexing service — no new state. Mirrors the *configuration* shape, not runtime stats (which stay in `/health/status`).

### 4.4 `agent-brain-cli` (modified, additive only)

- NEW: `agent_brain_cli/client/transport.py` — single helper `open_client(ctx) -> DocServeClient`. Reads transport choice from Click context / env / runtime.json and either:
  - HTTP: existing path — `DocServeClient(base_url=resolved_url)`
  - UDS: `DocServeClient.from_httpx(make_uds_client(state_dir))`
- MODIFIED: `agent_brain_cli/client/api_client.py` — `DocServeClient` gains a `from_httpx(client: httpx.Client) -> DocServeClient` classmethod and an internal seam that uses the provided client. Existing `__init__(base_url, timeout)` stays as a thin wrapper. Tests stay green.
- MODIFIED: `agent_brain_cli/cli.py` — `@click.group()` gains `--transport [auto|http|uds]`, `--socket-path`, `--base-url`, `--debug-transport`; stores on Click context.
- MODIFIED: every command in `commands/` (`query.py`, `index.py`, `jobs.py`, `folders.py`, `cache.py`, `reset.py`, `status.py`, `inject.py`): replace `with DocServeClient(base_url=resolved_url) as client:` with `with open_client(ctx) as client:`. Mechanical refactor — no behavior change in HTTP mode.
- MODIFIED: `agent_brain_cli/commands/start.py` — `--uds` and `--uds-only` flags, passes through to the server's `agent-brain-serve` invocation.
- MODIFIED: `agent_brain_cli/config.py:376-414` — `get_server_url()` is kept HTTP-only. New sibling `resolve_transport()` returns `("http", url)` or `("uds", socket_path)` from the same precedence chain.

---

## 5. Server-side UDS bind (Phase-1 spike required)

`uvicorn.Config.bind_socket()` is mutually exclusive between `uds=` and `(host,port)=` (verified by inspecting uvicorn 0.32 source). Serving both from one process needs two `uvicorn.Server` instances on a shared asyncio loop, with the app lifespan running exactly once.

```python
# agent_brain_server/api/uds_bind.py
async def serve_dual(app, *, host, port, socket_path):
    cfg_tcp = uvicorn.Config(app=app, host=host, port=port, lifespan="on")
    cfg_uds = uvicorn.Config(app=app, uds=str(socket_path), lifespan="off")
    server_tcp = uvicorn.Server(cfg_tcp)
    server_uds = uvicorn.Server(cfg_uds)
    try:
        await asyncio.gather(server_tcp.serve(), server_uds.serve())
    finally:
        Path(socket_path).unlink(missing_ok=True)
```

**Spike gate (Phase 1 exit criterion):** `scripts/spike_dual_bind.py` must demonstrate
(a) start, (b) one HTTP request returns `/health/`, (c) one UDS request returns same, (d) `SIGTERM` cleans up both, (e) socket file is removed. If any of those fail, fall back to "UDS lives in its own uvicorn process" (separate `agent-brain-serve --uds-only` instance, discovered via `runtime.json`).

---

## 6. MCP server — v1 surface

### 6.1 Initialize

```jsonc
// capabilities advertised
{
  "tools":     { "listChanged": false },
  "resources": { "subscribe": false, "listChanged": false },   // read-only, static set in v1
  "prompts":   { "listChanged": false }
}

// serverInfo
{ "name": "agent-brain", "version": "<lockstep>",
  "instructions": "Agent Brain MCP v1 (7 tools, 5 resources, 6 prompts, stdio).",
  "_meta": { "agentBrainApiVersion": "<from /health/>",
             "agentBrainTransport": "uds|http" } }
```

No subscriptions, sampling, logging, completions, or elicitation capability in v1. Resources are read-on-demand only.

### 6.2 The 7 tools (lockstep with existing routes)

| Tool | Hint annotations | HTTP backing | Notes |
|---|---|---|---|
| `search_documents` | `readOnlyHint: true`, `openWorldHint: true` | `POST /query/` | All 5 retrieval modes via `mode` param |
| `query_count` | `readOnlyHint: true` | `GET /query/count` | |
| `index_folder` | `destructiveHint: false`, `openWorldHint: true` | `POST /index/?force=&allow_external=` | Returns `{job_id, status}` |
| `get_job` | `readOnlyHint: true` | `GET /index/jobs/{job_id}` | |
| `list_jobs` | `readOnlyHint: true` | `GET /index/jobs/?limit=&offset=` | Cursor = base64(offset) |
| `cancel_job` | `destructiveHint: true` | `DELETE /index/jobs/{job_id}` | Requires `confirm: true` in input schema, validated server-side |
| `server_health` | `readOnlyHint: true` | `GET /health/` | Used for startup version-compat check |

Tool annotations are **hints** per the current MCP spec; the `cancel_job` confirmation gate is enforced as a required input-schema field, not via annotation.

Every tool response includes `content: [{type:"text", text: <short human summary>}]` **and** `structuredContent: {…}` per the current MCP spec; `outputSchema` declared via `pydantic.TypeAdapter(Model).json_schema()`.

### 6.3 Error mapping (HTTP → MCP)

| HTTP | MCP code | Notes |
|---|---|---|
| 400 / 422 | `-32602 InvalidParams` | Pydantic detail echoed into `data.cause` |
| 404 | `-32602 InvalidParams` | "Job not found" etc. |
| 409 | `-32000 InvalidRequest` | Conflict |
| 500 | `-32603 InternalError` | Include `data.requestId` |
| 502 | `-32001 BackendUnavailable` (custom) | UDS gone / HTTP unreachable |
| 503 | `-32002 ServiceIndexing` (custom) | Indexing-in-progress signaled by `/health` |
| 504 | `-32003 BackendTimeout` (custom) | Wrap timeout |

All error responses carry `data.httpStatus` and `data.cause`.

### 6.4 Cancellation

MCP `notifications/cancelled` cancels the underlying `httpx` request. v1 has no long-running tools (no `wait_for_job` — that's v2), so cancellation is fast-path only. One test (`test_e2e_stdio.py`) covers it.

### 6.5 Resources (v1 — read-only, 5 schemes)

Every URI maps to a single existing endpoint (plus the new `/health/config`). No subscriptions, no templates, no pagination — just `resources/list` returns a fixed set of 5 entries and `resources/read` calls through to the backend. MIME type is `application/json` for all five.

| URI | MIME | Backed by | What the model sees |
|---|---|---|---|
| `corpus://config` | `application/json` | `GET /health/config` (new endpoint, see §4.3) | Storage backend type, vector/bm25/graph enable flags, embedding + rerank model names, graph extractor, watcher status |
| `corpus://status` | `application/json` | `GET /health/status` | `total_chunks`, `total_documents`, indexing in progress, current job, queue depth, graph index size, embedding/query cache hit rates, file watcher state |
| `corpus://health` | `application/json` | `GET /health/` | `status`, `message`, `version`, `mode`, `instance_id`, `project_id` |
| `corpus://providers` | `application/json` | `GET /health/providers` | Active embedding / summarization / reranker provider, model name, healthy/degraded/unavailable, validation errors |
| `corpus://folders` | `application/json` | `GET /index/folders/` | Array of `{folder_path, chunk_count, last_indexed, watch_mode, watch_debounce_seconds}` — answers "what directories are indexed and which are auto-watched" in one call |

This set deliberately answers the operator questions Agent Brain users actually ask: *what's configured, what's indexed, what's it doing right now, which providers are alive, which folders are being watched.* All five fit on one screen for a typical project.

**Deliberately deferred to v2** (need new endpoints, not "drop-in" data):
- `chunk://<chunk_id>` — would need `GET /query/chunk/{id}` for O(1) lookup
- `graph-entity://<type>/<id>` — would need `GET /graph/entity/{type}/{id}`
- `job://<job_id>` — *could* ship in v1 since `/index/jobs/{id}` exists, but resource subscriptions are what make it interesting; without `resources/subscribe`, it duplicates the `get_job` tool. Ship in v2 alongside subscriptions.
- `file://<path>` — needs a roots/sandbox story that's bigger than v1 should take on

### 6.6 Prompts (v1 — 6 templates derived from existing plugin commands)

These map 1:1 to the most-used patterns in `agent-brain-plugin/commands/` and the `agent-brain-skill/` workflows. Each one is a parameterized message sequence the MCP server returns via `prompts/get`; the client model then executes the tool plan.

| Prompt | Arguments | Mirrors | What it does |
|---|---|---|---|
| `find-callers` | `symbol` (required), `language` (optional) | `agent-brain-graph.md` | `search_documents` with `mode=graph`, `relationship_types=["calls"]`, query=`symbol` — returns ranked callers with source paths. |
| `find-implementation` | `feature` (required) | `agent-brain-bm25.md` + `agent-brain-graph.md` | Two-step: `search_documents` `mode=bm25` for exact symbol match, then `mode=graph` to walk to tests and related code. |
| `explain-architecture` | `folder` (required), `depth` (default 2) | `agent-brain-multi.md` | `search_documents` `mode=multi` restricted to `folder`, then summarize. Pulls READMEs + entrypoints + relationship graph at given depth. |
| `compare-search-modes` | `query` (required) | `agent-brain-bm25.md` / `-hybrid.md` / `-multi.md` (progressive escalation) | Runs the same `query` under `mode=bm25`, then `hybrid`, then `multi`, and presents the three result sets side-by-side. Teaches the user which mode fits their need. |
| `onboard-to-codebase` | `area` (optional) | `using-agent-brain` SKILL.md | Reads `corpus://config`, `corpus://stats`, `corpus://folders` resources, then runs `search_documents` for top-N entrypoints and key abstractions in `area` (or whole corpus if omitted). Produces a "where to start" briefing. |
| `audit-indexed-folders` | (none) | `agent-brain-folders.md` | Reads `corpus://folders` resource, identifies stale (`last_indexed` older than 7 days) and unwatched (`watch_mode == "off"`) folders, and suggests `index_folder` calls with appropriate flags. |

Each prompt definition includes `arguments` (with descriptions + JSON-Schema validation) and a `messages` array per MCP `prompts/get` shape. Bodies are stored as small Python templates in `agent_brain_mcp/prompts/*.py`.

**Why these six**: each one answers a question users already ask (per the plugin commands and skill docs), composes more than one Tool / Resource (so it's not just a renamed tool call), and runs end-to-end against the v1 backend without needing v2 features.

---

## 7. Configuration

| Env var | Default | Used by |
|---|---|---|
| `AGENT_BRAIN_UDS` | `0` | server — enables dual bind |
| `AGENT_BRAIN_UDS_ONLY` | `0` | server — UDS without TCP |
| `AGENT_BRAIN_UDS_PATH` | `<state_dir>/agent-brain.sock` | both — override resolver |
| `AGENT_BRAIN_TRANSPORT` | `auto` | CLI |
| `AGENT_BRAIN_MCP_BACKEND` | `auto` | MCP server |
| `AGENT_BRAIN_MCP_BACKEND_URL` | (from runtime.json) | MCP server |

CLI examples:
```bash
agent-brain start --uds                       # dual-bind
agent-brain start --uds-only                  # UDS only
agent-brain --transport uds query "auth"      # force UDS
agent-brain --transport auto index ./src      # prefer UDS, fall back to HTTP
agent-brain-mcp --backend auto                # MCP stdio entry
```

Claude Desktop / Code config:
```json
{
  "mcpServers": {
    "agent-brain": {
      "command": "agent-brain-mcp",
      "args": ["--backend", "auto"],
      "env": { "AGENT_BRAIN_STATE_DIR": "/Users/me/proj/.agent-brain" }
    }
  }
}
```

---

## 8. Security

| Surface | Control |
|---|---|
| UDS | parent dir `0700`; socket file `0600`; owner-UID match enforced on connect; rejects symlinks via `os.lstat`+`O_NOFOLLOW`-equivalent check; rejects world/group bits |
| HTTP | unchanged — loopback bind, no auth |
| MCP stdio | inherits Claude Desktop's process env; no network surface |
| `cancel_job` | required `confirm: true` in input schema — server-side guard, not annotation |

OAuth and remote MCP authorization → v3 (own design doc).

---

## 9. Layering enforcement (added in Phase 0)

New file `.importlinter` at repo root:

```toml
[importlinter]
root_packages = ["agent_brain_server", "agent_brain_uds", "agent_brain_mcp", "agent_brain_cli"]

[[importlinter.contracts]]
name = "server has no upward deps"
type = "forbidden"
source_modules = ["agent_brain_server"]
forbidden_modules = ["agent_brain_uds", "agent_brain_mcp", "agent_brain_cli"]

[[importlinter.contracts]]
name = "uds touches only server.models"
type = "forbidden"
source_modules = ["agent_brain_uds"]
forbidden_modules = ["agent_brain_server.services", "agent_brain_server.api",
                     "agent_brain_server.indexing", "agent_brain_server.storage"]

[[importlinter.contracts]]
name = "mcp never calls server internals"
type = "forbidden"
source_modules = ["agent_brain_mcp"]
forbidden_modules = ["agent_brain_server.services", "agent_brain_server.api",
                     "agent_brain_server.indexing", "agent_brain_server.storage",
                     "agent_brain_cli"]
```

New root task `task check:layering` runs `lint-imports`. Phase 0 commits the contracts before any code so CI proves the rules work.

---

## 10. Phases

Each phase is one PR. Exit gate is "tests + new `check:layering` task green, no regression in `task before-push`".

| # | Phase | Output | ~Duration |
|---|---|---|---|
| 0 | Scaffold + import-linter contracts | Both new packages scaffolded with empty tests; root `Taskfile.yml` `includes`; `.importlinter`; root `check:layering` task; CI green on no-op tests | ½ day |
| 1 | `agent-brain-uds` + dual-bind spike | `paths.py`, `permissions.py`, `client.py`, `errors.py` with unit tests; `scripts/spike_dual_bind.py` proves the two-`Server` pattern works (spike gate decides whether Phase 2 keeps "single process" or falls back to "separate UDS process") | 2 days |
| 2 | Server-side UDS bind + `/health/config` | `api/uds_bind.py`; `main.py` honors env + flags; `RuntimeState.socket_path`; new `GET /health/config` endpoint (~30 LOC, §4.3); `agent-brain start --uds` works end-to-end | 1 day |
| 3 | CLI transport selector | `client/transport.py`; `--transport`/`--socket-path`/`--base-url`/`--debug-transport`; every command refactored to `open_client(ctx)`; all existing CLI tests pass under both transports | 1 day |
| 4 | `agent-brain-mcp` v1 | 7 tools + 5 resources + 6 prompts (§6.3, §6.5, §6.6), stdio, structured tool output, version-compat check, official-SDK e2e test covering tool / resource / prompt calls | 2.5 days |
| 5 | Adversarial security + error mapping | Symlink / world-readable / group-readable / cross-UID rejection tests; all 8 HTTP→MCP code mappings; cancellation test | 1 day |
| 6 | Docs + ship | USER_GUIDE section; CHANGELOG with bench numbers; `2026-mcp-server-design.md` header marked superseded; lockstep release to 10.1.0 | ½ day |

Total: ~1.5 weeks. v1 is **not** added to root `task before-push` / `task pr-qa-gate` yet — new packages live behind their own `task uds:*` / `task mcp:*` per-package gates, matching the precedent in `docs/plans/2026-mcp-server-design.md` (§9 below).

---

## 11. Future (own design docs, in order)

- **v2** — Resource **subscriptions** (`resources/subscribe`) + the 2 deferred resource schemes (`chunk://<id>`, `graph-entity://<type>/<id>`) and the supporting new server endpoints + `job://<id>` (now subscription-worthy) + Streamable HTTP MCP transport + `wait_for_job` tool with progress notifications + the remaining 9 deferred tools (`explain_result`, `add_documents`, `inject_documents`, `wait_for_job`, `list_folders`, `remove_folder`, `cache_status`, `clear_cache`, `list_file_types`).
- **v3** — CLI-via-MCP (`McpStdioBackend` / `McpHttpBackend`) + framework integration matrix (OpenAI Agents SDK, LangChain, LlamaIndex, Mastra, Pydantic AI, Vercel AI SDK).
- **v4** — OAuth 2.1 for remote MCP (Protected Resource Metadata required; DCR is MAY).

---

## 12. Verification

Format follows `docs/plans/2026-05-27-query-explain-parameter.md`.

### 12.1 Quality gates

```bash
# Per-package, opt-in for v1 (NOT in root before-push yet)
task uds:test
task uds:pr-qa-gate
task mcp:test
task mcp:pr-qa-gate
task mcp:contract            # validates the 7 tools' schemas against the pinned MCP spec

# Always-on, runs across every package
task check:layering          # import-linter contracts

# Existing root gates (must continue passing)
task before-push
task pr-qa-gate
```

### 12.2 End-to-end manual commands

```bash
# 1. Dual-bind sanity
AGENT_BRAIN_UDS=1 agent-brain start
curl -sS http://127.0.0.1:$(jq -r .port .agent-brain/runtime.json)/health/ | jq .status
curl --unix-socket .agent-brain/agent-brain.sock http://localhost/health/ | jq .status
agent-brain stop
test ! -e .agent-brain/agent-brain.sock                # cleaned up

# 2. CLI parity under both transports
agent-brain start --uds
agent-brain index ./docs --wait
diff \
  <(agent-brain --transport http query "What is RAG?" --json | jq 'del(.query_time_ms)') \
  <(agent-brain --transport uds  query "What is RAG?" --json | jq 'del(.query_time_ms)')
# expect: empty diff
agent-brain stop

# 3. MCP stdio handshake + 7 tools + 5 resources + 6 prompts
agent-brain-mcp --backend uds < scripts/mcp-smoke.jsonl > /tmp/mcp-out.jsonl
jq -e 'select(.id==2).result.tools | length == 7'      /tmp/mcp-out.jsonl
jq -e 'select(.id==3).result.resources | length == 5'  /tmp/mcp-out.jsonl
jq -e 'select(.id==4).result.prompts | length == 6'    /tmp/mcp-out.jsonl

# 3a. Sanity-check a resource read and a prompt expansion
agent-brain-mcp --backend uds < scripts/mcp-read-resources.jsonl | \
  jq -e '.result.contents[0].uri == "corpus://folders"'
agent-brain-mcp --backend uds < scripts/mcp-get-prompt.jsonl | \
  jq -e '.result.messages | length > 0'

# 4. Real MCP SDK e2e
pytest agent-brain-mcp/tests/test_e2e_stdio.py -v

# 5. Claude Desktop smoke (manual, nightly)
#    With the config from §7 installed, restart Claude Desktop and ask:
#    "Use the agent-brain search_documents tool to find 'QueryService'."
#    Expect structured chunks with file paths.

# 6. Adversarial UDS + error mapping
pytest agent-brain-uds/tests/test_permissions.py -v       # all rejections enforced
pytest agent-brain-mcp/tests/test_error_mapping.py -v     # all 8 mappings

# 7. Layering
task check:layering                                       # no contract violations

# 8. Project-level smoke
./scripts/quick_start_guide.sh                            # existing end-to-end gate
```

### 12.3 Functional acceptance (each item must have a backing test in the diff)

1. `paths.py` returns the expected path for all 5 resolver branches and falls back to a pointer file when the resolved path exceeds 104 bytes.
2. `permissions.py` rejects: symlink target, world-readable socket, group-readable socket, cross-UID owner, parent dir not `0700`.
3. Dual-bind serves both HTTP and UDS in one process; `SIGTERM` removes the socket.
4. `RuntimeState.socket_path` is present when `--uds`, absent (and old `runtime.json` files still parse) otherwise.
5. `agent-brain --transport http query …` and `--transport uds query …` produce byte-identical results modulo timing fields.
6. `--transport auto` picks UDS when the socket validates, HTTP otherwise; raises a clear error when neither is reachable.
7. `agent-brain start --uds-only` plus a CLI that resolves to HTTP raises explicitly rather than hanging.
8. MCP `initialize` over the official SDK reports `tools.listChanged: false`, `resources.subscribe: false`, `prompts.listChanged: false`, and exactly 7 tools / 5 resources / 6 prompts.
9. Each of the 7 tools returns `content` + `structuredContent` with the declared `outputSchema`.
10. `cancel_job` without `confirm: true` returns `-32602 InvalidParams`.
11. Each of HTTP 400/404/409/422/500/502/503/504 maps to its row in §6.3.
12. `notifications/cancelled` cancels the in-flight `httpx` request within 1s.
13. `list_jobs` cursor pagination: page 1's `nextCursor` is a valid page-2 cursor.
14. MCP server refuses to start when `/health/` reports a `version` below the floor pinned in `agent-brain-mcp/pyproject.toml`.
15. `task check:layering` fails when a contract-violating import is introduced (verified by adding a temporary `import agent_brain_cli` to `agent_brain_server/api/main.py` in a CI dry-run).
16. `GET /health/config` returns valid `ConfigStatus` JSON with the documented fields (§4.3); reflects `AGENT_BRAIN_STORAGE_BACKEND` env override.
17. `resources/list` returns exactly the 5 URIs from §6.5; `resources/read` on each returns valid JSON with the fields documented in that table.
18. `prompts/list` returns exactly the 6 prompts from §6.6; `prompts/get` with sample arguments expands each to a non-empty `messages` array; argument-validation rejects missing required arguments with a clear error.
19. `prompt: onboard-to-codebase` end-to-end: `prompts/get` → client runs the resulting plan (using v1 tools + resources) → produces a coherent briefing on a fixture corpus. (Smoke via `pytest agent-brain-mcp/tests/test_e2e_stdio.py::test_onboard_prompt`.)

### 12.4 Benchmark (recorded, not gating)

```bash
python scripts/bench_uds_vs_http.py \
  --corpus e2e-cli/fixtures/codebase-small \
  --queries scripts/bench_queries.txt \
  --iterations 1000 --warmup 100 \
  --report p50,p95,p99,throughput \
  --record docs/CHANGELOG.md
```

Hardware noted in the CHANGELOG entry. If UDS isn't faster on the bench host, that's a finding — it does not block the release.

### 12.5 PR checklist (paste into PR body)

- [ ] `task uds:pr-qa-gate` exits 0
- [ ] `task mcp:pr-qa-gate` exits 0
- [ ] `task mcp:contract` exits 0
- [ ] `task check:layering` exits 0
- [ ] `task before-push` exits 0
- [ ] `task pr-qa-gate` exits 0
- [ ] All 8 manual E2E commands (§12.2) pass locally
- [ ] All 19 functional acceptance items (§12.3) have backing tests
- [ ] CHANGELOG `[10.1.0]` entry exists with benchmark numbers
- [ ] `docs/USER_GUIDE.md` has new "Using Agent Brain via MCP" + "Choosing a transport" sections
- [ ] `docs/plans/2026-mcp-server-design.md` header updated to "Superseded by 2026-05-28-mcp-uds-transport-design.md"
- [ ] `.claude/commands/ag-brain-release.md` and `.claude/agents/release_agent.md` list 9 lockstep files (was 5)

---

## 13. Repository changes (summary)

| Path | Change |
|---|---|
| `agent-brain-uds/**` | NEW package |
| `agent-brain-mcp/**` | NEW package |
| `agent-brain-server/agent_brain_server/api/uds_bind.py` | NEW |
| `agent-brain-server/agent_brain_server/api/main.py` | Wire `AGENT_BRAIN_UDS*` and `--uds`/`--uds-only` to `uds_bind` |
| `agent-brain-server/agent_brain_server/api/routers/health.py` | NEW route `GET /health/config` returning `ConfigStatus` (~30 LOC) |
| `agent-brain-server/agent_brain_server/models/health.py` | NEW `ConfigStatus` Pydantic model (storage backend, stores enabled, providers, watcher) |
| `agent-brain-server/agent_brain_server/runtime.py` | Add `socket_path: str | None` to `RuntimeState` |
| `agent-brain-cli/agent_brain_cli/client/api_client.py` | Add `DocServeClient.from_httpx(client)` classmethod |
| `agent-brain-cli/agent_brain_cli/client/transport.py` | NEW — `open_client(ctx)` selector |
| `agent-brain-cli/agent_brain_cli/cli.py` | Add `--transport`/`--socket-path`/`--base-url`/`--debug-transport` |
| `agent-brain-cli/agent_brain_cli/commands/*.py` | Mechanical: `DocServeClient(base_url=…)` → `open_client(ctx)` |
| `agent-brain-cli/agent_brain_cli/commands/start.py` | Add `--uds` / `--uds-only` |
| `agent-brain-cli/agent_brain_cli/config.py` | Add `resolve_transport()` next to `get_server_url()` |
| `agent-brain-cli/pyproject.toml` | Add path-dep on `agent-brain-uds` (PyPI dep at release) |
| `Taskfile.yml` | `includes: { uds, mcp }`; `task check:layering`. **Not** added to `before-push` / `pr-qa-gate` in v1. |
| `.importlinter` | NEW — contracts per §9 |
| `scripts/spike_dual_bind.py` | NEW — Phase 1 spike script |
| `scripts/bench_uds_vs_http.py` | NEW — recorded-only benchmark |
| `scripts/mcp-smoke.jsonl` | NEW — JSON-RPC tape: initialize → tools/list → resources/list → prompts/list |
| `scripts/mcp-read-resources.jsonl` | NEW — JSON-RPC tape: initialize → resources/read corpus://folders |
| `scripts/mcp-get-prompt.jsonl` | NEW — JSON-RPC tape: initialize → prompts/get onboard-to-codebase |
| `.claude/commands/ag-brain-release.md` | Update lockstep file list 5 → 9 |
| `.claude/agents/release_agent.md` | Same |
| `docs/USER_GUIDE.md` | "Using Agent Brain via MCP" + "Choosing a transport" |
| `docs/plans/2026-mcp-server-design.md` | Header: "Superseded by 2026-05-28-mcp-uds-transport-design.md" |
| `docs/plans/2026-05-28-mcp-uds-transport-design.md` | This document, copied on approval |
| `docs/CHANGELOG.md` | New `[10.1.0]` entry with benchmark + MCP v1 callout |

---

## 14. Key decisions (each captured here so reviewers can challenge in one place)

1. **No new `Backend` protocol.** Reuse `DocServeClient` (extended with `from_httpx`). The earlier draft's parallel protocol would have duplicated all 13 methods and clashed with `StorageBackendProtocol`. See §2, §4.4.
2. **MCP keeps its own thin `ApiClient`** (~80 LOC). Avoids `agent-brain-mcp → agent-brain-cli` dep, which would pull Click/Rich into the MCP process.
3. **UDS package is client-only.** Server-side UDS bind lives in `agent-brain-server`. Kills the cycle the earlier draft would have introduced.
4. **Dual-bind requires a spike** before Phase 2 commits to it (uvicorn's `Config.bind_socket()` is mutually exclusive on `uds=` vs `host/port`). Fallback is two processes.
5. **New packages don't join root `before-push` in v1.** They have their own `pr-qa-gate`. Folds into root only after 10.1.0 ships green and one release cycle elapses (target: 10.2.0). Matches `2026-mcp-server-design.md` precedent.
6. **Lockstep versions (5 → 9 files).** Same release flow, just two more `pyproject.toml` + `__init__.py` pairs.
7. **CLI does NOT speak MCP in v1.** That's v3.

---

## 15. GitHub issues to file on approval

The future MCP work in §11 (v2 / v3 / v4) is filed as tracking issues **before** Phase 0 starts so the roadmap is visible to anyone landing on the repo. Each issue links back to this plan as the source design and explicitly states it requires its own design doc before any code lands.

**Suggested labels:** `roadmap`, `mcp`, plus `v2` / `v3` / `v4` milestone tags as appropriate.
**Suggested milestone:** create three new milestones — `MCP v2 (resources + prompts)`, `MCP v3 (CLI-via-MCP + frameworks)`, `MCP v4 (OAuth for remote)`.

**Filed during Phase 6 (Docs + ship)** by the implementer; ship task is gated on these issues existing and being linked from the CHANGELOG entry. Use the existing `gh` CLI per `mastering-github-cli` conventions.

### 15.1 Issue: MCP v2 — Subscriptions, deferred resources, Streamable HTTP, remaining tools

```bash
gh issue create \
  --title "MCP v2: Resource subscriptions + deferred URI schemes + Streamable HTTP + 9 remaining tools" \
  --label "roadmap,mcp,v2" \
  --milestone "MCP v2 (subscriptions + http transport)" \
  --body "$(cat <<'EOF'
## Context

v1 (shipped in 10.1.0, see `docs/plans/2026-05-28-mcp-uds-transport-design.md`) delivered:
- UDS transport
- Minimal MCP server with **7 tools + 5 read-only resources + 6 prompts**, stdio only
- `GET /health/config` endpoint feeding `corpus://config`
- CLI HTTP/UDS dual transport

v2 picks up everything v1 deferred for scope: subscriptions, the 2 resource schemes that require new server endpoints, Streamable HTTP transport, `wait_for_job` with progress, and the 9 deferred tools.

## Scope

- **Resource subscriptions** (`resources/subscribe` capability):
  - Server-side polling (1s for active jobs, 30s for `corpus://stats`, watcher-driven for `corpus://folders`)
  - Emit `notifications/resources/updated` per spec
- **Deferred resource schemes** (need new server endpoints):
  - `chunk://<chunk_id>` — requires `GET /query/chunk/{id}` (new, O(1) lookup)
  - `graph-entity://<type>/<id>` — requires `GET /graph/entity/{type}/{id}` (new)
  - `job://<job_id>` — uses existing `GET /index/jobs/{id}` but is only valuable once subscriptions land
  - `file://<abs-path>` — gated by indexed roots + MCP `roots/list` (needs sandbox design)
  - `resources/templates/list` for the above
- **Streamable HTTP MCP transport** alongside stdio (loopback only in v2, no auth)
- **9 remaining tools** from the original 16-tool set:
  - `explain_result`, `add_documents`, `inject_documents`, `wait_for_job` (progress notifications)
  - `list_folders`, `remove_folder`, `cache_status`, `clear_cache`, `list_file_types`

## Prerequisites

- New server endpoints: `GET /query/chunk/{id}`, `GET /graph/entity/{type}/{id}` (server-side design must cover both)
- v1 has shipped green for one release cycle (target: 10.2.0)
- New packages folded into root `task before-push` per DR-5

## Definition of done

- Own design doc filed at `docs/plans/YYYY-MM-DD-mcp-v2-subscriptions.md`
- `resources/subscribe` + `notifications/resources/updated` tested end-to-end against the official MCP SDK
- All deferred resource schemes addressable via `resources/read`
- Streamable HTTP transport tested via official MCP SDK HTTP client
- `wait_for_job` emits `notifications/progress` at least every 2s during indexing
- All 16 total tools (7 from v1 + 9 new) covered by parameterized contract tests

## Explicitly NOT in scope (deferred to v3 / v4)

- CLI-via-MCP (v3)
- Framework adapter matrix (v3)
- OAuth (v4)

## Source design

This plan: `docs/plans/2026-05-28-mcp-uds-transport-design.md` §11 (v2 row)
EOF
)"
```

### 15.2 Issue: MCP v3 — CLI-via-MCP + LLM framework adapter matrix

```bash
gh issue create \
  --title "MCP v3: CLI speaks MCP + framework integration matrix" \
  --label "roadmap,mcp,v3" \
  --milestone "MCP v3 (CLI-via-MCP + frameworks)" \
  --body "$(cat <<'EOF'
## Context

v1 shipped CLI HTTP/UDS. v2 added MCP resources/prompts/HTTP. v3 makes the CLI a reference MCP client and validates the MCP server against the major LLM agent frameworks.

## Scope

- **CLI-via-MCP**:
  - New `McpStdioBackend` and `McpHttpBackend` in `agent_brain_mcp/client.py` satisfying the same shape `DocServeClient` exposes
  - CLI gains `--transport mcp` and `--mcp-transport stdio|http`
  - CLI gains `agent-brain prompt <name>` for `prompts/get` expansion
  - CLI gains `agent-brain resources list` and `agent-brain resources read <uri>`
  - CLI auto-discovers running MCP HTTP server via new `<state_dir>/mcp.runtime.json`
  - New CLI helper `agent-brain mcp start` that runs `agent-brain-mcp --transport http` and writes `mcp.runtime.json`
- **Framework integration matrix** — adapter smoke tests for each:
  - OpenAI Agents SDK (Python) — `MCPServerStdio` / `MCPServerStreamableHttp`
  - LangChain — `langchain-mcp-adapters`
  - LlamaIndex — `llama-index-tools-mcp`
  - Pydantic AI — `MCPServerStdio`
  - Mastra (TypeScript) — `@mastra/mcp`
  - Vercel AI SDK (TypeScript) — `experimental_createMCPClient`
  - Autogen / AG2 — `McpWorkbench`
  - Optional: Goose, Continue.dev, Cline, Cursor, Cody — config recipes only
- **New `task mcp:framework-matrix`** (slow, opt-in, nightly CI)
- **New `docs/INTEGRATIONS.md`** — one short page per framework with copy-pasteable config

## Prerequisites

- v2 shipped (resources + prompts are what makes CLI-via-MCP interesting)
- v2 packages folded into root QA gate

## Definition of done

- Own design doc filed
- `agent-brain --transport mcp query "X"` produces byte-identical results to `--transport uds` (modulo timing)
- All 6 Python frameworks pass `search_documents` smoke against the MCP server
- `docs/INTEGRATIONS.md` shipped
- MCP stdio subprocess hygiene: pinned cwd, sanitized env (allowlist), SIGTERM/SIGKILL escalation, no orphans verified by 1000-invocation `pgrep` test

## Source design

This plan: `docs/plans/2026-05-28-mcp-uds-transport-design.md` §11 (v3 row)
EOF
)"
```

### 15.3 Issue: MCP v4 — OAuth 2.1 for remote Agent Brain instances

```bash
gh issue create \
  --title "MCP v4: OAuth 2.1 for remote Agent Brain (own milestone)" \
  --label "roadmap,mcp,v4,security" \
  --milestone "MCP v4 (OAuth for remote)" \
  --body "$(cat <<'EOF'
## Context

v1–v3 are all localhost-trust. To run Agent Brain remotely (CI box, shared dev server, hosted SaaS) and have MCP clients consume it safely, the resource server needs real auth. Per the current MCP spec, Protected Resource Metadata is required for protected servers; Dynamic Client Registration is MAY (not MUST).

## Scope

- Adopt the standards stack:
  - OAuth 2.1 (consolidated spec) for authorization grants
  - PKCE (RFC 7636) — mandatory for all public clients (every MCP client is public)
  - **Protected Resource Metadata (RFC 9728)** — required by MCP spec, exposed at `/.well-known/oauth-protected-resource`
  - **Dynamic Client Registration (RFC 7591)** — MAY per current spec; we ship it for ergonomics
  - Authorization Server Metadata (RFC 8414) at `/.well-known/oauth-authorization-server`
  - Resource Indicators (RFC 8707) — bind tokens to a specific Agent Brain resource URI
  - Token Introspection (RFC 7662)
  - Revocation (RFC 7009)
  - DPoP (RFC 9449) — optional, for token binding
- Deployment shapes supported:
  - Co-located AS/RS (single binary, self-hosted single-user; JWT-signed tokens, no introspection)
  - Split AS/RS (enterprise — Auth0 / Keycloak / Cognito / custom; JWKS-cached verification)
- Scope design:
  - `agent-brain:read` — all `readOnlyHint: true` tools + resource reads
  - `agent-brain:index` — `index_folder`, `add_documents`, `inject_documents`, `wait_for_job`
  - `agent-brain:admin` — `cancel_job`, `remove_folder`, `clear_cache`
  - `agent-brain:subscribe` — long-lived resource subscriptions
- Token lifecycle: 15-min access tokens, rotating 30-day refresh tokens, replay detection (RFC 6749 §10.4)
- MCP client side: `McpHttpBackend` (from v3) handles the `WWW-Authenticate` challenge and the OAuth dance per spec
- Server-side middleware in `agent-brain-server` toggled by `AGENT_BRAIN_AUTH=oauth` (default `none`)
- Migration: v1.x adds `AGENT_BRAIN_AUTH=basic` (shared secret bearer) as a LAN bridge before full OAuth ships

## Threat model (must be in design doc)

- Token theft via curl/log capture → short-lived access tokens + refresh; DPoP where supported
- Replay → DPoP / TLS-binding / short TTLs
- Cross-tenant data leakage → resource-scoped tokens; `aud` claim validation
- Confused deputy → per-resource token isolation per MCP authorization spec

## Prerequisites

- v3 shipped (`McpHttpBackend` exists)
- Independent security review of the design doc before implementation
- Test coverage gate ≥ 90% on the new `oauth/` middleware

## Definition of done

- Own design doc filed
- Co-located AS/RS deployment works end-to-end
- Split AS/RS verified against at least one external IdP (Keycloak in CI)
- `WWW-Authenticate` challenge → MCP client OAuth dance → authorized tool call works against the official MCP SDK client
- Audit log for every authorized call (separate concern — may need its own milestone)

## Source design

This plan: `docs/plans/2026-05-28-mcp-uds-transport-design.md` §11 (v4 row)
EOF
)"
```

### 15.4 Optional tracking issue

```bash
gh issue create \
  --title "MCP roadmap meta-issue (v2 / v3 / v4 tracking)" \
  --label "roadmap,mcp,epic" \
  --body "$(cat <<'EOF'
## Source design

`docs/plans/2026-05-28-mcp-uds-transport-design.md`

## v1 (this release — 10.1.0)

Shipped per the plan above. UDS transport + 7-tool stdio MCP server + CLI HTTP/UDS dual transport.

## Roadmap

- [ ] #<v2-issue> — MCP v2: Resources + Prompts + Streamable HTTP
- [ ] #<v3-issue> — MCP v3: CLI-via-MCP + framework integration matrix
- [ ] #<v4-issue> — MCP v4: OAuth 2.1 for remote Agent Brain

Each phase requires its own design doc before implementation lands. Phase order is hard — v3 depends on v2's HTTP transport; v4 depends on v3's `McpHttpBackend`.
EOF
)"
```

### 15.5 Phase 6 exit gate addition

Phase 6 (Docs + ship) gains one new criterion:

- The three roadmap issues (§15.1–15.3) and the meta-issue (§15.4) are filed on `spillwave/agent-brain` and linked from the CHANGELOG `[10.1.0]` entry under a "Roadmap" subsection.

This guarantees the future work is visible to maintainers and external contributors the moment v1 ships, rather than living only in the design doc.
