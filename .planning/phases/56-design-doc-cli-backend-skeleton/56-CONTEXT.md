# Phase 56: Design doc + CLI backend skeleton - Context

**Gathered:** 2026-06-05 (auto mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers TWO things:

1. **v3 design doc** filed at `docs/plans/2026-06-<dd>-mcp-v3-cli-via-mcp.md` covering CLI backend abstraction, runtime discovery model, and explicit scope boundaries — landing BEFORE any MCP-layer code so reviewers can challenge the shape (v2 Phase 50 design-first precedent).
2. **Backend client skeletons** — `McpStdioBackend` and `McpHttpBackend` Python classes that satisfy the same shape `DocServeClient` exposes today, so CLI commands can swap transports without code changes.

Out of phase scope (deferred to later phases in this milestone):
- CLI `--transport mcp` selector wiring → Phase 57
- `mcp.runtime.json` discovery + helper commands → Phase 58
- `agent-brain prompt` / `resources` CLI commands → Phase 59
- Subprocess hygiene + orphan test → Phase 60
- Framework adapter matrix → Phases 61-62
- `task mcp:framework-matrix` + INTEGRATIONS.md → Phase 63

</domain>

<decisions>
## Implementation Decisions

### Backend class location
- `McpStdioBackend` and `McpHttpBackend` live in **`agent-brain-mcp/agent_brain_mcp/client.py`** alongside the existing `ApiClient` class.
- Rationale: keeps the MCP SDK dependency contained to the `agent-brain-mcp` package; agent-brain-cli does NOT take a hard dep on the MCP SDK (it picks up the backends via the protocol at runtime, optionally).
- Mirrors v10.2 boundary: backend transport (`agent-brain-serve` ↔ MCP) and listen transport (MCP client ↔ MCP server) both kept in the MCP package.
- Alternative considered + rejected: a new `agent-brain-cli/client/mcp_backend.py` location would force CLI to import the MCP SDK as a hard dep, bloating the CLI's `pip install` surface.

### Interface contract style
- Define a new `BackendClient` `typing.Protocol` (NOT an ABC) in **`agent-brain-cli/agent_brain_cli/client/protocol.py`**.
- The existing `DocServeClient` already satisfies the protocol by structural typing — no inheritance change required.
- `McpStdioBackend` + `McpHttpBackend` declare `Protocol` conformance explicitly via runtime-checkable `@runtime_checkable` so mypy strict verifies the surface AND tests can assert `isinstance(backend, BackendClient)`.
- Protocol must declare every public method DocServeClient exposes today: `health()`, `status()`, `query()`, `index()`, `list_folders()`, `delete_folder()`, `reset()`, `list_jobs()`, `get_job()`, `cancel_job()`, `cache_status()`, `clear_cache()`, plus context-manager dunders `__enter__`, `__exit__`, `close()`.

### Sync facade with async-internal implementation
- Backend public methods are **synchronous** (mirroring `DocServeClient.query(...)` etc.).
- Internally, each method runs the MCP SDK's async call via `asyncio.run(...)` or a long-lived `_loop` attribute kept open across calls (the latter avoids repeated event-loop bootstrap overhead — measure once during planning).
- Rationale: preserves zero changes to Click commands in `agent-brain-cli/agent_brain_cli/commands/*.py`. v10.2 `run_http()` already uses async-internal-sync-facade for the uvicorn boot; the same pattern applies to client calls.
- The v3 design doc must explicitly call out this is a v3 design choice — v4 OAuth work may revisit this if remote calls justify exposing async to the CLI.

### Design doc scope
- Design doc covers **CLI-via-MCP scope ONLY** (DESIGN-V3-01, CLI-MCP-01, CLI-MCP-02).
- Framework matrix (Phases 61-62) gets its own lighter scoping doc when that phase starts.
- v9.6.0 Runtime Parity unpark decision stays **open** — referenced in design doc only as "to be decided at Phase 61 discuss-phase". Do NOT pre-decide.
- Design doc structure should mirror v2 design doc (`docs/plans/2026-06-02-mcp-v2-subscriptions.md`): goals → non-goals → wire shape → Python surface → risks → DR (deferred items).

### Claude's Discretion
- Exact protocol attribute set vs method-only (some attributes like `_url` or `state_dir` may need to be on the protocol if any CLI command reads them directly — verify during planning by `rg "client\." agent-brain-cli/`).
- Whether to keep a single shared `_loop` per backend instance or use `asyncio.run` per call (perf vs simplicity tradeoff — measure during planning).
- File naming for the design doc: pick the actual date (yyyy-mm-dd format) at plan/write time.
- Whether the `BackendClient` Protocol should expose async methods directly for future-proofing, OR stay sync-only and force v4 to add a parallel `AsyncBackendClient` (recommend sync-only for now; defer the split).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v3 scope source-of-truth
- `docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md` — Issue-body version of v3 scope (CLI-via-MCP + framework matrix + tooling). DoD anchors: byte-identical `--transport mcp` results vs `--transport uds`, 1000-invocation no-orphan test, INTEGRATIONS.md.
- `docs/plans/2026-05-28-mcp-uds-transport-design.md` §11 (v3 row) and §15.2 — Master MCP roadmap document; v3 row scopes McpStdioBackend + McpHttpBackend.

### v2 design-first precedent (structural template)
- `docs/plans/2026-06-02-mcp-v2-subscriptions.md` — v2 design doc; v3 design doc should mirror its structure (goals/non-goals/wire shape/Python surface/risks/DR sections).
- `.planning/milestones/v10.2-phases/50-server-endpoint-prep-v2-design-doc/50-PLAN.md` — Phase 50 plan; shows how v2 wove design doc landing into Plan 01 (file design → review → then implement endpoints in later plans).

### Existing client interface (the shape v3 backends must match)
- `agent-brain-cli/agent_brain_cli/client/api_client.py` — `DocServeClient` is the existing shape: 12 public methods + 3 context-manager methods + `from_httpx` factory. ALL must be on the `BackendClient` Protocol.
- `agent-brain-cli/agent_brain_cli/client/transport.py` — `open_client(ctx, *, timeout)` factory; v3 will need a parallel `open_mcp_backend(ctx, *, transport, ...)` factory at Phase 57.
- `agent-brain-mcp/agent_brain_mcp/client.py` — Existing `ApiClient` lives here; new MCP backends live alongside. Existing class shows the pattern for HTTP-over-MCP-transport.

### Async-internal-sync-facade precedent
- `agent-brain-mcp/agent_brain_mcp/http.py` — `run_http()` is the canonical example of async-internal-sync-facade in this repo. Read before deciding `asyncio.run` vs persistent `_loop`.

### Prereq features (already shipped)
- v10.2 `MIN_BACKEND_VERSION = 10.2.0` (now 10.2.1 with API key auth) — backends must respect the same min-version check at instantiation time.
- v10.2 16-tool MCP surface — `McpStdioBackend.query()` maps to `search_documents` tool call; full method ↔ tool mapping lives in the design doc.

### Open question (NOT pre-decided)
- `docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md` "Open Questions" — v9.6.0 Runtime Parity unpark decision belongs in Phase 61 discuss-phase, not here.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`DocServeClient` (12 public methods)** in `agent-brain-cli/agent_brain_cli/client/api_client.py` — the exact interface shape new backends must satisfy. Use as the source-of-truth for the `BackendClient` Protocol definition.
- **`open_client(ctx)` factory** in `agent-brain-cli/agent_brain_cli/client/transport.py` — the existing factory function; Phase 57 will wrap this with a transport-dispatching variant. Phase 56 should make sure the BackendClient Protocol covers everything `open_client` returns.
- **`ApiClient`** in `agent-brain-mcp/agent_brain_mcp/client.py` — existing MCP-side client showing the HTTP-over-MCP-transport pattern. New backends sit in the same module.
- **`run_http()`** in `agent-brain-mcp/agent_brain_mcp/http.py` — canonical async-internal-sync-facade example. Reuse the lifespan pattern + `asyncio.run` wiring.

### Established Patterns
- **Two-axis transport labels (v10.2 Plan 53-01 decision):** `backend_transport` (server ↔ MCP) and `listen_transport` (MCP server ↔ MCP client) are orthogonal. New CLI backends introduce a THIRD axis: `cli_backend_transport` (CLI ↔ backend). Design doc must name this axis explicitly so v4 OAuth work doesn't conflate them.
- **MIN_BACKEND_VERSION (v10.2 Plan 51-04 decision):** Runtime version check at startup; new backends must inherit this check before issuing the first request.
- **No silent fallback (v10.2 HTTP-03 decision):** Explicit transport selection at every layer. v3 CLI's `--transport mcp` must NOT fall back to UDS on MCP unavailability.

### Integration Points
- Phase 57 will swap `open_client(ctx)` (returns DocServeClient) for a transport-dispatching factory that can return McpStdioBackend or McpHttpBackend. Phase 56 makes sure the Protocol is the contract that lets that swap work without touching individual commands.
- `agent_brain_mcp/security/__init__.py` is a re-export shim per v10.2 Plan 51-03 ("share, don't fork"). If v3 backends need any sandbox helpers (likely for `resources read file://` at Phase 59), reuse via the shim; do NOT fork.
- v10.2 lock-drift guard (`scripts/before_push_lock_guard.sh`) wraps `task before-push`; new MCP-package dependencies must NOT trigger drift. Pin SDK versions in pyproject before lock-drift fires.

</code_context>

<specifics>
## Specific Ideas

- **Design-first**: v2 Phase 50 landed the design doc as Plan 01 before any URI scheme code (Plans 02-04). v3 Phase 56 mirrors this: design doc is the first Plan, the two backend skeletons are Plans 2-3.
- **Don't pre-decide v9.6.0 Runtime Parity** unpark — that's a Phase 61 discuss-phase decision. Mention in design doc as "open question routed to Phase 61".
- **Loopback-only stays** through all of v10.3. OAuth 2.1 is v10.4 (#188).

</specifics>

<deferred>
## Deferred Ideas

- **Async-first Protocol variant** (`AsyncBackendClient`): Could unlock parallel queries from the CLI someday, but adds parallel surface area now. Deferred to v10.4 or beyond — sync-only Protocol for v10.3.
- **Persistent `_loop` per backend vs per-call `asyncio.run`**: Performance optimization decision deferred to planning step (measure during Phase 56 Plan 02/03 execution).
- **CLI-via-MCP for the `agent-brain-mcp` CLI itself** (i.e., agent-brain-mcp talks to its own MCP server): explicit non-goal in v3 — v3 is about agent-brain CLI's transports, not MCP CLI introspection.

</deferred>

---

*Phase: 56-design-doc-cli-backend-skeleton*
*Context gathered: 2026-06-05*
