---
title: Agent Brain — MCP v3 (CLI-via-MCP — CLI backend abstraction, runtime discovery scope)
date: 2026-06-05
status: Plan for review
supersedes: none (additive to v2; v2 master at `docs/plans/2026-06-02-mcp-v2-subscriptions.md`)
summary: Surgical v3 design — locks the BackendClient Protocol surface, McpStdioBackend / McpHttpBackend boundaries, runtime discovery model, and sync-facade-with-async-internals decision before any CLI-via-MCP code lands.
---

> Per-phase planners write the implementation plans. This doc commits the contracts those plans must follow. Decisions + rationale + diagrams + risk register + DR only — no reference implementation. NO `BackendClient` Protocol file is written in this doc; that lands in Plan 56-02. NO McpStdioBackend / McpHttpBackend skeletons land in this doc; those land in Plan 56-03.

---

## 1. Context

### 1.1 What v2 shipped (10.2.0/10.2.1, 2026-06-03)

Per `docs/plans/2026-06-02-mcp-v2-subscriptions.md` v2 delivered:

- **16-tool MCP surface:** v1's 7 tools plus the 9 v2 additions (`explain_result`, `add_documents`, `inject_documents`, `wait_for_job`, `list_folders`, `remove_folder`, `cache_status`, `clear_cache`, `list_file_types`).
- **Streamable HTTP transport** (loopback only, no auth) alongside stdio. Loopback enforced via `psutil` kernel-bind verification (Phase 53 HTTP-02), no silent fallback (Phase 53 HTTP-03).
- **Resource subscriptions** on three time-varying URIs: `job://<id>` (1s polled), `corpus://status` (30s polled), `corpus://folders` (5s active / 60s safety poll).
- **Four parameterized URI schemes** addressable via `resources/read`: `chunk://`, `graph-entity://`, `job://`, `file://` — all advertised via `resources/templates/list` with byte-identical RFC 6570 strings (Phase 51 Plan 04 decision B).
- **`MIN_BACKEND_VERSION = "10.2.0"`** runtime check (refuses startup against older `agent-brain-server`) plus install-time `agent-brain-rag = "^10.2.0"` pin in `agent-brain-mcp/pyproject.toml`.
- **DR-5 closed:** MCP + UDS packages folded into root `task before-push` / `task pr-qa-gate`. +60-90s local pre-push cost documented in CHANGELOG.
- **API key auth on REST routers** (Issue #179 mid-flight): bearer-token middleware now lives on the FastAPI app; the MCP server passes the configured key through `httpx` when calling `agent-brain-server`.

### 1.2 What v3 adds

Per scope contract `docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md` and umbrella issue [#187](https://github.com/SpillwaveSolutions/agent-brain/issues/187), v3 ships **CLI-via-MCP scope ONLY** in this design doc:

- **`BackendClient` Protocol** in `agent-brain-cli/agent_brain_cli/client/protocol.py` — runtime-checkable structural type covering the 12 public methods + 3 context-manager dunders + `close()` that `DocServeClient` exposes today. Existing `DocServeClient` satisfies it without inheritance change.
- **`McpStdioBackend` + `McpHttpBackend`** in `agent-brain-mcp/agent_brain_mcp/client.py` alongside the existing `ApiClient`. Both classes satisfy the `BackendClient` Protocol structurally; both wrap async MCP SDK calls behind a sync facade (see §3.2).
- **CLI gains `--transport mcp` + `--mcp-transport stdio|http`** (Phase 57). The existing `open_client(ctx)` factory in `agent-brain-cli/agent_brain_cli/client/transport.py` is replaced by a transport-dispatching factory that returns the appropriate `BackendClient` implementation.
- **Runtime discovery via `<state_dir>/mcp.runtime.json`** (Phase 58 prereq — schema locked in §2.4 here). `agent-brain mcp start` helper writes this file after psutil socket-bind verification (reuses v10.2 HTTP-02 kernel-bind pattern).
- **`agent-brain prompt <name>` + `agent-brain resources list|read <uri>`** CLI commands (Phase 59) — surface MCP prompts and resources to humans, not just MCP clients.
- **Subprocess hygiene contract** (Phase 60) — pinned cwd, sanitized env (allowlist), SIGTERM→SIGKILL escalation, verified by a 1000-invocation orphan test using `pgrep`.
- **Framework adapter matrix** (Phases 61-62) — smoke tests against OpenAI Agents SDK, LangChain, LlamaIndex, Pydantic AI, Mastra, Vercel AI SDK, Autogen/AG2.
- **`task mcp:framework-matrix` + `docs/INTEGRATIONS.md`** (Phase 63) — nightly advisory CI + one-page-per-framework copy-paste recipes.

### 1.3 What v3 explicitly does NOT ship

Deferred per Phase 56 CONTEXT.md and the v3 scope contract:

- **OAuth 2.1 / DCR / DPoP for remote MCP** — v10.4 ([#188](https://github.com/SpillwaveSolutions/agent-brain/issues/188)). Strictly depends on v10.3's `McpHttpBackend`.
- **MCP sampling / completion / elicitation** — not on any roadmap.
- **Multi-instance / remote MCP federation** — tracked separately as #157.
- **Async-first `AsyncBackendClient` Protocol variant** — deferred. v3 ships sync-only. Re-evaluated when v4 OAuth work justifies exposing async to Click commands.
- **CLI-via-MCP for `agent-brain-mcp`'s own CLI** (i.e., `agent-brain-mcp` talks to its own MCP server) — explicit non-goal in v3. v3 is about `agent-brain-cli`'s transports, not MCP CLI introspection.
- **`AGENT_BRAIN_OPENAI_API_KEY` / `AGENT_BRAIN_ANTHROPIC_API_KEY` propagation through stdio subprocess by default** — Phase 60 subprocess hygiene contract owns the allowlist; secrets do NOT cross the subprocess boundary unless explicitly opted-in.

Framework matrix scope (Phases 61-62) is deferred to a separate, lighter scoping doc filed when Phase 61 starts — per Phase 56 CONTEXT.md design-doc-scope lock. This keeps the REQUIREMENTS.md framework-matrix entries audit-trail-clean against the CONTEXT.md scope boundary.

### 1.4 Spec target

MCP spec revision **2026-03-26** (matches the SDK at `mcp = "^1.12.0"` pinned in `agent-brain-mcp/pyproject.toml`). Same as v2 — no SDK bump in v3. Any future SDK bump (1.13+, 2.x) is a separate ADR.

### 1.5 Documents this doc references

- v2 master design: `docs/plans/2026-06-02-mcp-v2-subscriptions.md`
- v1 master design: `docs/plans/2026-05-28-mcp-uds-transport-design.md` §11 (v3 row) and §15.2 (master scope)
- v3 scope contract: `docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md`
- Phase 56 CONTEXT.md (locked decisions — backend location, Protocol style, sync-facade)
- Umbrella issue: [#187](https://github.com/SpillwaveSolutions/agent-brain/issues/187) (v3); future-work issue [#188](https://github.com/SpillwaveSolutions/agent-brain/issues/188) (v4 OAuth)

---

## 2. Architecture deltas vs v2

### 2.1 Three transport axes (NEW v3 axis: `cli_backend_transport`)

```
                       ┌─────────────────────────────────────────────┐
                       │              agent-brain-cli                │
                       │  (Click commands; transport-agnostic body)  │
                       └────────────────────┬────────────────────────┘
                                            │
              cli_backend_transport (NEW v3 axis)
                                            │
                        ┌───────────────────┼───────────────────┐
                        │                   │                   │
              DocServeClient        McpStdioBackend       McpHttpBackend
              (HTTP / UDS              (stdio MCP)       (Streamable HTTP MCP)
              direct to server)              │                   │
                        │                   │                   │
                        │             listen_transport (v2 axis)
                        │                   │                   │
                        │             ┌─────▼─────┐       ┌─────▼─────┐
                        │             │  stdio    │       │  HTTP     │
                        │             │ subprocess│       │  loopback │
                        │             └─────┬─────┘       └─────┬─────┘
                        │                   │                   │
                        │                   └─────────┬─────────┘
                        │                             │
                        │                  agent-brain-mcp (build_server)
                        │                             │
                        │             backend_transport (v1 axis)
                        │                             │
                        │                  ┌──────────▼──────────┐
                        │                  │   httpx (HTTP/UDS)  │
                        │                  └──────────┬──────────┘
                        └────────────────────────────► │
                                                       │
                                              agent-brain-server
                                              (FastAPI REST)
```

**These three axes are orthogonal. Reviewers commonly conflate the new v3 axis (`cli_backend_transport`) with `listen_transport` because both deal with how the CLI talks to MCP — but they are distinct.** `cli_backend_transport` is the choice the CLI user makes (`--transport http|uds|mcp`). `listen_transport` is the wire the MCP server is listening on (`stdio` or `http`). `backend_transport` is the wire the MCP server uses to reach `agent-brain-server` (`http` or `uds`).

Naming the axis explicitly here prevents v4 OAuth work from misrouting auth between the wrong pair: OAuth on `listen_transport` (HTTP MCP) is about who can drive the MCP server; OAuth on `backend_transport` is about who can drive `agent-brain-server`; the CLI's `cli_backend_transport` choice has no auth implications by itself (it only determines which class instantiates the request).

### 2.2 BackendClient Protocol — locked surface

```python
from typing import Protocol, runtime_checkable
from types import TracebackType

@runtime_checkable
class BackendClient(Protocol):
    """The shape every CLI backend implements. Structurally satisfied by
    DocServeClient (HTTP/UDS) and by McpStdioBackend / McpHttpBackend (v3).

    All methods are SYNCHRONOUS. v3 backends wrap async MCP SDK calls
    via asyncio.run(...) or a long-lived event loop attribute (see §3.2).
    """

    def __enter__(self) -> "BackendClient": ...
    def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...
    def close(self) -> None: ...

    def health(self) -> "HealthStatus": ...
    def status(self) -> "IndexingStatus": ...
    def query(self, query_text: str, top_k: int = 5,
              similarity_threshold: float = 0.7,
              mode: str = "hybrid", alpha: float = 0.5,
              source_types: list[str] | None = None,
              languages: list[str] | None = None,
              file_paths: list[str] | None = None,
              explain: bool = False) -> "QueryResponse": ...
    def index(self, folder_path: str, /,  # full signature copied verbatim from DocServeClient.index
              # chunk_size, chunk_overlap, recursive, include_code, supported_languages,
              # code_chunk_strategy, include_patterns, exclude_patterns, include_types,
              # generate_summaries, force, injector_script, folder_metadata_file,
              # dry_run, watch_mode, watch_debounce_seconds — see api_client.py for full body
              ...) -> "IndexResponse": ...
    def list_folders(self) -> list["FolderInfo"]: ...
    def delete_folder(self, folder_path: str) -> dict: ...
    def reset(self) -> "IndexResponse": ...
    def list_jobs(self, limit: int = 20) -> list[dict]: ...
    def get_job(self, job_id: str) -> dict: ...
    def cancel_job(self, job_id: str) -> dict: ...
    def cache_status(self) -> dict: ...
    def clear_cache(self) -> dict: ...
```

All dataclass return types (`HealthStatus`, `IndexingStatus`, `QueryResponse`, `FolderInfo`, `IndexResponse`) live in `agent_brain_cli/client/api_client.py` and stay there. The Protocol references them by forward-string to avoid a cycle (the cli package imports from the mcp package's backends in Phase 57, not the other way around). Plan 56-02 owns the actual `BackendClient` file; Plan 56-03 owns the McpStdioBackend / McpHttpBackend skeletons that satisfy it structurally.

### 2.3 Method ↔ MCP tool / endpoint mapping table

| BackendClient method | McpStdioBackend / McpHttpBackend wire call |
|---|---|
| `query(...)` | MCP tool `search_documents` |
| `health()` | MCP tool `server_health` |
| `status()` | MCP resource read `corpus://status` |
| `index(...)` | MCP tool `index_folder` (or `inject_documents` if `injector_script` set) |
| `list_folders()` | MCP resource read `corpus://folders` |
| `delete_folder(...)` | MCP tool `remove_folder` |
| `reset()` | (no direct MCP equivalent — see §4 risks; Plan 56-03 raises `NotImplementedError` for v3 skeleton; Phase 57+ decides whether to add a `reset_index` tool or hold for v4) |
| `list_jobs(...)` | MCP tool `list_jobs` |
| `get_job(...)` | MCP resource read `job://<id>` |
| `cancel_job(...)` | MCP tool `cancel_job` |
| `cache_status()` | MCP tool `cache_status` |
| `clear_cache()` | MCP tool `clear_cache` (requires `confirm: True`) |

Note on `query(...)`: `DocServeClient.query(query_text=...)` maps verbatim to MCP `search_documents` tool call. The MCP tool name `search_documents` is load-bearing — pinned in `agent-brain-mcp/agent_brain_mcp/tools/__init__.py` and asserted by v2 contract tests. Method ↔ tool drift would break the v3 byte-identical-equivalence DoD anchor.

### 2.4 Runtime discovery model (Phase 58 prereq — locked here)

`<state_dir>/mcp.runtime.json` schema (single-file, single-instance per `state_dir` for v3):

| Field | Type | Meaning |
|---|---|---|
| `host` | string | Loopback address (`127.0.0.1`). Phase 58 enforces loopback-only via psutil socket-bind verification BEFORE the file is written. |
| `port` | int | TCP port the MCP server is listening on. |
| `pid` | int | OS process id of the `agent-brain-mcp --transport http` process. Used by `agent-brain mcp stop` for orderly shutdown and by stale-runtime detection. |
| `started_at` | string | ISO 8601 timestamp at which the helper command completed kernel-bind verification. |
| `transport` | string | `"http"` for v3. Future-proof for additional transports without schema break. |

The Phase 58 helper command `agent-brain mcp start` is responsible for writing this file AFTER psutil socket-bind verification (reuses the v10.2 HTTP-02 pattern: bind the socket inside `psutil`, confirm the OS kernel agrees the port is bound to `127.0.0.1`, then write the discovery file). If the bind verification fails the helper exits non-zero and the file is NOT written. `agent-brain mcp stop` reads the file, sends SIGTERM to `pid`, waits, escalates to SIGKILL, deletes the file. `McpHttpBackend.__init__` reads the file to learn `host`+`port` when `--mcp-url` is not explicitly passed.

---

## 3. Python surface decisions

### 3.1 Backend class location

**Locked: both `McpStdioBackend` and `McpHttpBackend` live in `agent-brain-mcp/agent_brain_mcp/client.py` alongside the existing `ApiClient`.**

Rationale: keeps the MCP SDK dep contained to the `agent-brain-mcp` package. `agent-brain-cli` takes a SOFT (optional) dep on the mcp package — `from agent_brain_mcp.client import McpStdioBackend` succeeds only if `agent-brain-mcp` is installed in the same environment, otherwise Phase 57's transport-dispatching factory raises a clear `RuntimeError("install agent-brain-mcp to use --transport mcp")` error.

Alternative considered + rejected: a new `agent-brain-cli/client/mcp_backend.py` location would force `agent-brain-cli` to take a HARD dep on the MCP SDK, bloating the CLI's `pip install` surface for users who never touch `--transport mcp`. CONTEXT decision is unambiguous on this; the design doc locks it.

### 3.2 Sync facade with async-internal implementation

**Locked decision per CONTEXT §decisions.** Each public method on `McpStdioBackend` / `McpHttpBackend` is **synchronous** (mirroring `DocServeClient.query(...)`). Internally each method runs the MCP SDK's async call via one of two patterns:

- **Pattern A:** `asyncio.run(self._async_xxx(...))` per call. Simple. Creates and tears down a new event loop per call. For short CLI invocations (one query, one index) this is fine. For long-running ones (`agent-brain jobs --watch`, looping every 3s) the per-call loop bootstrap compounds overhead.
- **Pattern B:** keep a long-lived `_loop = asyncio.new_event_loop()` attribute on the backend instance and call `self._loop.run_until_complete(self._async_xxx(...))`. Single bootstrap cost, freed on `close()`. Trickier lifecycle — the loop must be closed cleanly on `__exit__` and SIGTERM.

**Plans 56-02 / 56-03 will measure the perf delta and pick.** CONTEXT defers the choice to plan execution. The design doc records this is an implementation detail, not a public-contract change — clients see the same sync API regardless of which pattern the backend picks.

`agent-brain-mcp/agent_brain_mcp/http.py:run_http()` is the canonical async-internal-sync-facade example in this repo (uvicorn lifespan + `asyncio.run` wiring) and Plan 56-03 must read it before committing.

### 3.3 BackendClient Protocol — `@runtime_checkable`

**Locked: `@runtime_checkable` on the Protocol so tests can assert `isinstance(backend, BackendClient)` AND mypy strict verifies the surface structurally.** Existing `DocServeClient` satisfies the Protocol WITHOUT inheritance change (no `class DocServeClient(BackendClient):` retrofit). Plan 56-03 adds a pinning test that asserts `isinstance(DocServeClient(...), BackendClient)` is True and asserts the same for both new backends, so future drift on any of the three classes is caught at unit-test time.

Note: `@runtime_checkable` on Protocols with many methods has measurable cost (PEP 544 implementation does isinstance checks across all method names). For backends we accept the cost — instantiation is once-per-CLI-invocation, not per request. If profiling later shows this dominating CLI startup, we'll switch to a custom `is_backend_client(obj)` helper that checks the methods we actually exercise; that's a Plan 57+ optimization, not a v3 contract change.

### 3.4 `MIN_BACKEND_VERSION` for v3

**DECISION: Bump to `"10.3.0"` at v3 milestone close (Phase 63).** Rationale:

- v2's MCP-layer protocol additions (subscriptions, parameterized URIs, four URI templates) are mature and pin `agent-brain-server >= 10.2.0`.
- v3 adds CLI-surface changes (`McpStdioBackend`, `McpHttpBackend`, transport selector) but NO server-side protocol break. Strictly speaking v3 could ship against `agent-brain-server 10.2.0`.
- We bump anyway, at milestone close, to keep the long-standing contract: "agent-brain-mcp X.Y.Z requires agent-brain-server >= X.Y.0". The contract is operationally load-bearing — operators rely on it for upgrade ordering.

**Plans 56-02 / 56-03 keep `MIN_BACKEND_VERSION = "10.2.0"` in the skeleton.** Phase 63 (release time) bumps to `"10.3.0"` in lockstep with the `agent-brain-rag = "^10.3.0"` pyproject pin. The bump is a one-line edit at release time; calling it out here makes the audit trail clean.

### 3.5 No silent fallback — v10.2 HTTP-03 carry-forward

Every v3 transport selection is explicit. Carry-forward from Phase 53 HTTP-03 (CONTEXT decision):

- `--transport mcp` without an installed `agent-brain-mcp` package fails loudly with the clear "install agent-brain-mcp" message from §3.1.
- `--mcp-transport http` without `mcp.runtime.json` (and no explicit `--mcp-url`) fails loudly with a "discovery file not found at `<state_dir>/mcp.runtime.json`; run `agent-brain mcp start` or pass `--mcp-url`" message.
- `--mcp-transport stdio` without `agent-brain-mcp` reachable on `PATH` fails loudly with a "agent-brain-mcp not found on PATH" message.

NO silent fallback to UDS or HTTP transport when MCP is unavailable. The CLI must surface the failure so the operator knows their transport flag was honored.

---

## 4. Per-phase decisions

### 4.1 Phase 56 (this phase) — design doc + backend skeletons

- Plan 56-01 (this) files the doc.
- Plan 56-02 lands the `BackendClient` Protocol in `agent-brain-cli/agent_brain_cli/client/protocol.py` with `@runtime_checkable` + a pinning test asserting `DocServeClient` structurally satisfies it.
- Plan 56-03 lands `McpStdioBackend` + `McpHttpBackend` skeletons in `agent-brain-mcp/agent_brain_mcp/client.py` with the sync facade + async-internal pattern (Pattern A or B per §3.2 measurement). Skeleton method bodies may `raise NotImplementedError("Wired in Phase 57+")` but signatures must match the Protocol and `isinstance(backend, BackendClient)` must succeed for BOTH new classes AND the existing `DocServeClient`.

### 4.2 Phase 57 — CLI transport selector + byte-identical equivalence

Wire `--transport mcp` + `--mcp-transport stdio|http`. Replace `open_client(ctx)` in `agent-brain-cli/agent_brain_cli/client/transport.py` with a transport-dispatching factory. Add the byte-identical-equivalence DoD-anchor test: `agent-brain --transport uds query "X"` and `agent-brain --transport mcp query "X"` return the same chunks in the same order, modulo timing.

### 4.3 Phase 58 — Runtime discovery + helper commands

File the `mcp.runtime.json` schema (already described in §2.4). Land `agent-brain mcp start` + `agent-brain mcp stop` helper commands. Discovery: `McpHttpBackend.__init__` reads `mcp.runtime.json` when `--mcp-url` is not passed.

### 4.4 Phase 59 — CLI prompts + resources commands

- `agent-brain prompt <name>` → `prompts/get` MCP call, expansion printed to stdout.
- `agent-brain resources list` → `resources/list` + `resources/templates/list` merged, printed as table.
- `agent-brain resources read <uri>` → `resources/read`, content printed as JSON or raw bytes per content type.

### 4.5 Phase 60 — Subprocess hygiene + 1000-invocation orphan test

Pinned cwd (no inherit-from-shell surprises), env allowlist (NOT pass-through), SIGTERM→SIGKILL escalation with timeout, 1000-invocation `pgrep` test confirming no orphan `agent-brain-mcp` processes after `__exit__`.

### 4.6 Phase 61-62 — Framework adapter matrix

Python smoke tests (Phase 61) + TypeScript smoke tests (Phase 62) against the matrix listed in §1.2. Framework matrix gets its own lighter scoping doc when Phase 61 starts. NOT pre-decided here.

### 4.7 Phase 63 — Tooling + docs + integration page

`task mcp:framework-matrix` (slow, opt-in, nightly CI). `docs/INTEGRATIONS.md` — one page per framework with copy-pasteable config. `MIN_BACKEND_VERSION = "10.3.0"` bump per §3.4.

---

## 5. Risk register

Top risks identified during planning for v3:

- **Async event-loop lifecycle in long-running CLI invocations** — `asyncio.run(...)` (Pattern A in §3.2) creates and tears down a new event loop per call. For short CLI invocations this is fine, but `agent-brain jobs --watch` (loops every 3s) compounds the per-call overhead. **Mitigation:** Plans 56-02/56-03 measure both patterns; if material, switch to persistent `_loop` (Pattern B) per backend instance.

- **MCP SDK API drift** (v10.2 carry-forward) — `streamablehttp_client` API surface for `McpHttpBackend` and subprocess management API for `McpStdioBackend` both ride the MCP SDK 1.12.x line. Past SDK minor bumps have shifted handler-registration shapes (cf. Phase 52 `resources.subscribe` capability workaround). **Mitigation:** pin SDK version in `agent-brain-mcp/pyproject.toml`; design doc commits to the 1.12.x line; any SDK upgrade is a separate ADR.

- **Backend version skew at startup** — `McpStdioBackend` / `McpHttpBackend` must perform the same `MIN_BACKEND_VERSION` check as the existing MCP server at startup; otherwise a v10.3 CLI talking to v10.1 server would silently issue calls that fail downstream. **Mitigation:** §3.4 decision — skeleton inherits `"10.2.0"` from v2; bump to `"10.3.0"` at v3 close. Plan 56-03 skeleton imports `MIN_BACKEND_VERSION` from `agent_brain_mcp.server` and surfaces a clear error at first connect.

- **`reset()` has no MCP tool equivalent** — v2 did not ship `reset_index` as an MCP tool (destructive op + cache invalidation makes it dangerous via MCP). The `BackendClient` Protocol declares `reset()`, but neither McpStdioBackend nor McpHttpBackend can satisfy it for real. **Mitigation:** skeleton `raise NotImplementedError("`reset_index` MCP tool not exposed in v2; tracked for v3 Phase 57+ decision")`. Phase 57+ decides whether to add the `reset_index` tool or hold for v4.

- **CLI gains a SOFT dep on `agent-brain-mcp`** — `--transport mcp` requires `agent-brain-mcp` installed in the same Python environment. The CLI's `pyproject.toml` does NOT pin it (would bloat install for users who never touch `--transport mcp`). **Mitigation:** clear error message when the import fails (§3.1); documented in user guide; `pipx install agent-brain-cli[mcp]` extra published at Phase 63 as a convenience.

---

## 6. Deferred / Related work

- **Async-first `AsyncBackendClient` Protocol** — deferred to v10.4+. v3 ships sync-only. CONTEXT decision; rationale: zero Click-command churn AND no parallel surface area to maintain alongside the sync API.

- **v9.6.0 Runtime Parity unpark (Phases 47-49)** — OPEN. The unpark decision is routed to `/gsd:discuss-phase 61` (the framework matrix discussion overlaps with external-CLI exercising; the parity work covers similar ground). NOT pre-decided here. See CONTEXT specifics #2.

- **OAuth 2.1 for remote MCP** — v10.4 / [#188](https://github.com/SpillwaveSolutions/agent-brain/issues/188). Strictly depends on v10.3's `McpHttpBackend` shipping first; OAuth wraps the same `streamablehttp_client` call site.

- **Persistent `_loop` per backend vs per-call `asyncio.run`** — performance optimization decision deferred to Plan 56-03 execution. Either pattern satisfies the sync facade contract; design doc only locks the facade, not the implementation pattern.

- **CLI-via-MCP for the `agent-brain-mcp` CLI itself** — explicit non-goal in v3 per CONTEXT deferred ideas. v3 is about `agent-brain-cli`'s transport choices, not MCP CLI introspection.

- **Framework adapter matrix scoping doc** — lighter scoping doc filed at Phase 61 start; not in this design doc per CONTEXT decision design-doc-scope.

---

## 7. Canonical references

- v2 design doc: `docs/plans/2026-06-02-mcp-v2-subscriptions.md`
- v1 master design: `docs/plans/2026-05-28-mcp-uds-transport-design.md` (§11 v3 row, §15.2 master scope)
- v3 scope doc: `docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md`
- Existing CLI surface (the shape v3 backends must match): `agent-brain-cli/agent_brain_cli/client/api_client.py`
- Existing transport factory (Phase 57 replaces): `agent-brain-cli/agent_brain_cli/client/transport.py`
- Backend class location (Plan 56-03 lands here): `agent-brain-mcp/agent_brain_mcp/client.py`
- Async-internal-sync-facade precedent: `agent-brain-mcp/agent_brain_mcp/http.py`
- Phase 56 CONTEXT.md (decisions): `.planning/phases/56-design-doc-cli-backend-skeleton/56-CONTEXT.md`
- Umbrella issues: [#187](https://github.com/SpillwaveSolutions/agent-brain/issues/187) (v3 umbrella), [#188](https://github.com/SpillwaveSolutions/agent-brain/issues/188) (v4 OAuth)

---

*Design doc filed: 2026-06-05 — Plan 56-01. Reviewers focus on §2 (architecture deltas), §3 (Python surface), §4 (risks), §5 (DR / deferred items). Reviews close before Plan 56-02 lands code.*
