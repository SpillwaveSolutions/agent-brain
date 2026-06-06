# Phase 57: CLI transport selector + byte-identical equivalence - Context

**Gathered:** 2026-06-06 (auto mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers:

1. **`--transport mcp` + `--mcp-transport stdio|http`** wired into the Click CLI as top-level group flags (alongside the existing `--transport http|uds|auto`), with explicit selection and no silent fallback (carries forward the v10.2 HTTP-03 contract).
2. **A transport-dispatching factory** replacing `open_client(ctx)` in `agent-brain-cli/agent_brain_cli/client/transport.py` — returns a `BackendClient` Protocol, dispatching to `DocServeClient` (HTTP/UDS), `McpStdioBackend`, or `McpHttpBackend` based on the resolved `cli_backend_transport` axis.
3. **Working `query()` end-to-end on both `--transport mcp` paths** — the wire calls (`search_documents` MCP tool over stdio + Streamable HTTP) replace the `NotImplementedError("Wired in Phase 57+")` sentinels for the `query` path. Other backend methods (`health`, `status`, `index`, `list_folders`, `delete_folder`, `list_jobs`, `get_job`, `cancel_job`, `cache_status`, `clear_cache`) get wired in this phase too via the same async-internal-sync-facade pattern.
4. **The v3 Definition-of-Done anchor test** — a byte-identical-equivalence contract test asserting `agent-brain --transport uds query "X"` and `agent-brain --transport mcp query "X"` return the same chunks in the same order against the same backend state, modulo timestamps and elapsed fields.

Out of phase scope (deferred to later phases in this milestone):
- `mcp.runtime.json` discovery file (read or write) → Phase 58
- `agent-brain mcp start` / `agent-brain mcp stop` helper commands → Phase 58
- `agent-brain prompt <name>` / `agent-brain resources list|read <uri>` commands → Phase 59
- Subprocess hygiene (pinned cwd, env allowlist, SIGTERM/SIGKILL escalation, 1000-invocation no-orphan test) → Phase 60
- `reset_index` MCP tool addition (or formal hold-for-v4 decision) → Phase 57+ open item, surfaces here as `NotImplementedError` on `--transport mcp` `reset()` calls only
- `MIN_BACKEND_VERSION` bump to `"10.3.0"` → Phase 63 (milestone close)
- Framework adapter matrix → Phases 61-62

</domain>

<decisions>
## Implementation Decisions

### Click flag wiring & precedence
- **`--transport` extends `click.Choice` to `["auto", "http", "uds", "mcp"]`** in the top-level `cli` group (`agent-brain-cli/agent_brain_cli/cli.py:34-44`). Case-insensitive, as today.
- **New top-level `--mcp-transport` group flag** with `click.Choice(["stdio", "http"], case_sensitive=False)`, `default=None`. Lives alongside `--transport` so it applies to every subcommand uniformly.
  - When `--transport mcp` and `--mcp-transport` is unset → resolve via `AGENT_BRAIN_MCP_TRANSPORT` env, then default to `"stdio"`.
  - When `--mcp-transport` is set but `--transport != mcp` → ignored silently (matches `--socket-path` ignored when `--transport=http`).
- **New top-level `--mcp-url` group flag** with `default=None`, used only when `--transport mcp --mcp-transport http`. Required in Phase 57 (Phase 58 makes it optional once `mcp.runtime.json` discovery lands).
  - Env precedence: `--mcp-url` arg → `AGENT_BRAIN_MCP_URL` env → error (`exit 2`) with the §3.5 design-doc-wording message.
- **`ctx.obj` carries the new keys** `mcp_transport_hint` (str | None) and `mcp_url_override` (str | None) alongside the existing `transport_hint`, `base_url_override`, `socket_path_override`, `debug_transport` keys.

### Transport dispatcher refactor shape
- **Rename `open_client(ctx)` → `open_backend(ctx)`** in `agent-brain-cli/agent_brain_cli/client/transport.py`. Return type changes from `DocServeClient` to `BackendClient` (the Protocol shipped in Plan 56-02). All 20 call sites across 8 commands get updated in a single atomic commit.
- **Dispatcher branches** (in order):
  1. `transport == "mcp"` and `mcp_transport == "stdio"` → `McpStdioBackend()` (no required args yet; Phase 60 hardens subprocess hygiene)
  2. `transport == "mcp"` and `mcp_transport == "http"` → `McpHttpBackend(url=resolved_mcp_url, timeout=timeout)`
  3. `transport == "http"` → existing `DocServeClient(base_url=..., timeout=..., api_key=...)`
  4. `transport == "uds"` → existing `from_httpx(...)` path
- **`config.resolve_transport(...)`** stays single-axis (`http`/`uds`/`auto`). A **new** `config.resolve_mcp_transport(...)` function handles the MCP axis (`stdio`/`http` + url resolution). Two single-axis resolvers compose cleaner than one dual-axis resolver; precedence logic stays per-axis testable.
- **Soft dep on `agent-brain-mcp`** — `transport.py` imports `from agent_brain_mcp.client import McpStdioBackend, McpHttpBackend` inside the `transport == "mcp"` branch (not at module load). When the import fails, raise `click.UsageError("install agent-brain-mcp to use --transport mcp")` per design doc §3.1.

### Wiring the BackendClient methods (replacing Plan 56-03 sentinels)
- **Sync facade pattern: Pattern A (`asyncio.run(...)` per call)** for both `McpStdioBackend` and `McpHttpBackend`. Rationale: simplest correct implementation; per-call overhead acceptable for short CLI invocations (one query, one index). Long-running flows (`agent-brain jobs --watch` loops every 3s) get a Phase 60 SUMMARY note recommending Pattern B revisit if profiling shows compounding overhead — NOT a Phase 57 blocker.
- **Stdio backend subprocess lifecycle: per-call spawn.** Each public method spawns `agent-brain-mcp --transport stdio`, runs the async tool call, tears down. Phase 60 owns subprocess hygiene + persistent-subprocess optimization. Phase 57 ships the simplest correct code path.
- **Method ↔ MCP wire mapping** uses the table in v3 design doc §2.3 verbatim:
  - `query(...)` → MCP tool `search_documents`
  - `health()` → MCP tool `server_health`
  - `status()` → MCP resource read `corpus://status`
  - `index(...)` → MCP tool `index_folder` (or `inject_documents` if `injector_script` set)
  - `list_folders()` → MCP resource read `corpus://folders`
  - `delete_folder(...)` → MCP tool `remove_folder`
  - `list_jobs(...)` → MCP tool `list_jobs`
  - `get_job(...)` → MCP resource read `job://<id>`
  - `cancel_job(...)` → MCP tool `cancel_job`
  - `cache_status()` → MCP tool `cache_status`
  - `clear_cache()` → MCP tool `clear_cache` (requires `confirm: True`)
  - `reset()` → **stays `NotImplementedError`** with message `"--transport mcp does not support reset; use --transport uds or http (no reset_index MCP tool in v2; v3 Phase 57+ open decision per design doc §4 risks)"`. Phase 57+ open decision deliberately NOT taken here.

### Byte-identical equivalence DoD test (CLI-MCP-04)
- **Test location:** `agent-brain-cli/tests/contract/test_transport_equivalence.py` (new subdirectory `contract/` for transport-equivalence and similar cross-transport pinning tests).
- **Test invocation:** `subprocess.run([sys.executable, "-m", "agent_brain_cli", "--transport", "uds", "query", "echo"])` vs `--transport mcp --mcp-transport stdio query "echo"` against a small fixed seeded corpus.
- **Field stripping:** the test compares JSON output after popping top-level `elapsed_seconds` and per-chunk `indexed_at` keys. Anything else differing fails the test loudly. The stripping helper lives in `tests/contract/_normalize.py` so Phase 58/59 reuse it.
- **Pytest fixture:** `transport_equivalence_corpus` fixture seeds an isolated `state_dir` with a 3-document corpus and starts the server with both UDS socket AND `agent-brain-mcp --transport stdio` reachable. Reuses the existing UDS smoke harness in `tests/integration/test_smoke_uds.py` for the UDS leg; adds a small MCP stdio harness for the new leg.
- **CI gate:** the test goes into `task before-push` AND `task pr-qa-gate` (root-level). Not opt-in — it's the v3 DoD anchor.

### No-silent-fallback contract (carries v10.2 HTTP-03)
- All `--transport mcp` failure modes surface with `exit code 2` and the §3.5-design-doc-wording messages:
  - `--transport mcp` + `agent-brain-mcp` not installed → `"install agent-brain-mcp to use --transport mcp"`
  - `--mcp-transport stdio` + `agent-brain-mcp` not on PATH → `"agent-brain-mcp not found on PATH; install agent-brain-mcp into the same Python environment"`
  - `--mcp-transport http` without `--mcp-url` (and no `AGENT_BRAIN_MCP_URL`) → `"discovery file support lands in Phase 58; pass --mcp-url explicitly in Phase 57"` (Phase 58 swaps this for the design-doc §3.5 wording about `mcp.runtime.json`)
- **NO** auto-fallback to UDS or HTTP. The operator's transport flag is honored or the CLI exits non-zero.

### `--debug-transport` honors the MCP axis
- Existing `--debug-transport` flag stays. When the resolved transport is `mcp`, the debug line reads `[debug-transport] mcp (stdio|http) -> <target> (with X-API-Key | no auth)`. `<target>` is the resolved MCP URL for http, or `"subprocess: agent-brain-mcp"` for stdio.

### Claude's Discretion
- **Exact internal helper signatures** in `transport.py` — whether `resolve_mcp_transport` returns `(transport, target)` like `resolve_transport` does, or a richer 3-tuple. Planner picks during task breakdown.
- **Pytest fixture cleanup order** for the transport-equivalence test — agent-brain-mcp subprocess teardown semantics interact with the existing UDS server fixture; planner may need a small `gc.collect()` or explicit close ordering.
- **Whether `delete_folder` and `clear_cache` get the same `confirm: True` Pydantic guard that v10.2 Plan 54-03 added** — the MCP tools already enforce it; CLI may want to surface a confirmation prompt OR pass through. Recommend pass-through for parity with `--transport uds` behavior; planner verifies no test expects a CLI-side prompt today.
- **`subprocess.run` vs `subprocess.Popen` for the stdio backend per-call spawn** — `subprocess.run` simpler; `Popen` allows finer cleanup. Recommend `run` for Phase 57, hand off to Phase 60 for hygiene-driven refinement.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v3 scope source-of-truth + design doc
- `docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md` §2.1, §2.3, §3.1, §3.2, §3.3, §3.5, §4.2, §5 — Locked surface, method↔wire mapping, sync facade, no-silent-fallback contract, Phase 57 scope, risk register. **READ ALL OF THIS FIRST.**
- `docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md` — Issue-body version of v3 scope; DoD anchor is byte-identical `--transport mcp` vs `--transport uds`.
- `docs/plans/2026-05-28-mcp-uds-transport-design.md` §11 (v3 row) and §15.2 — Master MCP roadmap document.

### Prior phase 56 artifacts (carry-forward contracts)
- `.planning/phases/56-design-doc-cli-backend-skeleton/56-CONTEXT.md` — Phase 56 decisions (backend location, Protocol style, sync facade, design doc scope) that Phase 57 inherits unchanged.
- `agent-brain-cli/agent_brain_cli/client/protocol.py` — `BackendClient` Protocol shipped in Plan 56-02. Phase 57 wires real implementations behind this surface.
- `agent-brain-mcp/agent_brain_mcp/client.py` — `McpStdioBackend` + `McpHttpBackend` skeletons shipped in Plan 56-03. Phase 57 replaces `NotImplementedError("Wired in Phase 57+")` sentinels with real wire calls. `MIN_BACKEND_VERSION = "10.2.0"` stays through Phase 57; bump deferred to Phase 63.

### Existing CLI transport surface (what Phase 57 modifies)
- `agent-brain-cli/agent_brain_cli/cli.py` — Top-level Click group; lines 34-58 hold the `--transport`/`--socket-path`/`--base-url`/`--debug-transport` flags. Phase 57 extends this with `--mcp-transport` + `--mcp-url`.
- `agent-brain-cli/agent_brain_cli/client/transport.py` — `open_client(ctx)` factory; lines 30-67. Phase 57 renames + extends to `open_backend(ctx) -> BackendClient`.
- `agent-brain-cli/agent_brain_cli/config.py` lines 469-545 — `resolve_transport(...)` function (single-axis HTTP/UDS resolver). Phase 57 adds parallel `resolve_mcp_transport(...)` for the MCP axis.
- 8 command modules using `open_client`: `agent-brain-cli/agent_brain_cli/commands/{query,index,reset,cache,jobs,inject,folders,status}.py` — 20 total call sites that swap to `open_backend`.

### v10.2 HTTP-03 contract (no-silent-fallback precedent)
- `.planning/phases/53-mcp-streamable-http-transport/` (search for HTTP-03) — v10.2 carry-forward; explicit transport selection, no silent fallback, `exit code 2` on misuse.

### Existing test patterns to reuse / extend
- `agent-brain-cli/tests/integration/test_smoke_uds.py` — UDS smoke harness. Phase 57's byte-equivalence test imports the corpus seed fixture from here.
- `agent-brain-mcp/tests/test_cli_backends_skeleton.py` — Plan 56-03's skeleton conformance tests. Phase 57's new wire-level tests sit alongside these.

### MCP SDK surface
- `mcp.client.stdio.stdio_client` — used by `McpStdioBackend` to launch subprocess + run tool calls.
- `mcp.client.streamable_http.streamablehttp_client` — used by `McpHttpBackend` for the loopback HTTP path (v10.2 Phase 53 first repo usage; reuse the pattern).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`BackendClient` Protocol** (`agent-brain-cli/agent_brain_cli/client/protocol.py`) — shipped in Plan 56-02, satisfied structurally by `DocServeClient` today and Phase 57's wired backends. Forward-string references avoid circular imports.
- **`McpStdioBackend` + `McpHttpBackend` skeletons** (`agent-brain-mcp/agent_brain_mcp/client.py`) — class shells + `__enter__`/`__exit__`/`close()` already real. Phase 57 replaces 24 `NotImplementedError("Wired in Phase 57+")` sentinels with real implementations.
- **`resolve_transport(...)` precedence pattern** (`agent-brain-cli/agent_brain_cli/config.py:469`) — clean per-axis resolver design. `resolve_mcp_transport(...)` will mirror its shape.
- **UDS smoke harness** (`agent-brain-cli/tests/integration/test_smoke_uds.py`) — pytest fixture for spinning up a server + driving CLI calls. Byte-equivalence test reuses the corpus seeding logic.
- **Plan 56-03 skeleton conformance tests** (`agent-brain-mcp/tests/test_cli_backends_skeleton.py`) — Phase 57's new tests sit alongside; the `isinstance(backend, BackendClient)` pins stay green throughout.
- **MCP SDK `streamablehttp_client`** (v10.2 Phase 53 first repo usage) — pattern for spinning up a Streamable HTTP session against a loopback listener.
- **MCP SDK `stdio_client`** (v10.2 Phase 51-54 usage) — pattern for stdio-subprocess MCP sessions.

### Established Patterns
- **Sync facade with `asyncio.run(...)` internal** — `agent-brain-mcp/agent_brain_mcp/http.py::run_http()` is the canonical reference; Phase 57 follows the same pattern per method.
- **No silent fallback** — v10.2 HTTP-03 pattern; explicit `click.UsageError` raises with `exit code 2` on misuse. Phase 57 carries forward.
- **`ctx.obj`-passed options** — top-level group flags land in `ctx.obj` keyed by option name; subcommands read via `ctx.obj.get(...)`.
- **Lazy imports for optional deps** — `transport.py` imports `agent_brain_uds` lazily inside the UDS branch (line ~62); Phase 57 lazy-imports `agent_brain_mcp.client` inside the `mcp` branch identically.
- **Method ↔ wire mapping fixed by v10.2** — all 16 MCP tools registered + asserted by `_tool_matrix.py` source-of-truth (drift-guarded at import time). Phase 57 cannot drift the wire names; tools' shapes are already locked.

### Integration Points
- **Top-level Click group** (`cli.py:30-66`) — where new `--mcp-transport` + `--mcp-url` flags + extended `--transport` choice list slot in.
- **`open_client` callsites** — 20 across 8 commands. Atomic rename to `open_backend` in a single commit; type-checker (mypy strict) verifies all callsites compile against the new `BackendClient` return type.
- **`task before-push` + `task pr-qa-gate`** — root-level QA gates already cover `agent-brain-cli` + `agent-brain-mcp`. Phase 57's byte-equivalence test gets picked up automatically when filed under `agent-brain-cli/tests/contract/`.
- **Existing `--debug-transport` flag** — extends naturally to log the MCP transport + target.
- **`resolve_api_key()` precedence** (issue #179) — stays as-is; both MCP backends pass the API key into the HTTP backend transport (server-side auth applies regardless of CLI-side transport choice).

</code_context>

<specifics>
## Specific Ideas

- **Byte-identical seed corpus:** small, deterministic, no embedding model randomness in the picture (use a recorded fixture for embeddings if needed). Three documents, 3-4 chunks each, query `"echo"` returns predictable top-5.
- **Reuse the `--transport=auto` UDS-first fallback pattern** for `--transport mcp --mcp-transport=stdio` is **explicitly NOT done** — `mcp` is always explicit, never `auto`. (`auto` stays HTTP/UDS only.)
- **Naming alignment:** `--transport mcp` (not `--transport=stdio` or `--transport=mcp-http`). The `--mcp-transport` sub-axis is what selects stdio vs http. This matches the v3 design doc §2.1 three-axes diagram exactly.
- **Plans should be sequenced:**
  - Plan 57-01: Wire `--mcp-transport` + `--mcp-url` flags, `resolve_mcp_transport` config helper, `open_backend` dispatcher rename + 20-callsite swap (no MCP method wiring yet — `query` still NotImplementedError).
  - Plan 57-02: Wire `query()` end-to-end on both MCP backends + the byte-identical-equivalence DoD test (CLI-MCP-04 anchor).
  - Plan 57-03: Wire remaining methods (`health`, `status`, `index`, `list_folders`, `delete_folder`, `list_jobs`, `get_job`, `cancel_job`, `cache_status`, `clear_cache`); `reset()` stays `NotImplementedError` with the §3.5 wording.

</specifics>

<deferred>
## Deferred Ideas

- **Pattern B (persistent `_loop`) for the sync facade** — measured-then-applied optimization deferred to Phase 60 SUMMARY recommendation if profiling shows `--watch` loops compounding overhead. Phase 57 ships Pattern A.
- **`mcp.runtime.json` discovery in the CLI** — Phase 58. Phase 57 requires explicit `--mcp-url` or `AGENT_BRAIN_MCP_URL` when `--mcp-transport http`.
- **`reset_index` MCP tool** — open decision deferred per design doc §5 risk register. Phase 57+ decides between adding the tool or holding for v4. Phase 57 ships `NotImplementedError` with a pointer.
- **Subprocess hygiene** (pinned cwd, env allowlist, SIGTERM/SIGKILL escalation, persistent subprocess) — Phase 60.
- **`MIN_BACKEND_VERSION = "10.3.0"` bump** — Phase 63 (milestone close).
- **`pipx install agent-brain-cli[mcp]` extra** — Phase 63 convenience packaging.
- **Persistent subprocess for stdio backend** — Phase 60 hygiene refinement; Phase 57 spawns per call.

</deferred>

---

*Phase: 57-cli-transport-selector-byte-identical-equivalence*
*Context gathered: 2026-06-06 (auto mode — recommended defaults selected)*
