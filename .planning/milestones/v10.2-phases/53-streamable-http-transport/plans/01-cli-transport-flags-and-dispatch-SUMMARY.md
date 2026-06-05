---
phase: 53-streamable-http-transport
plan: 01
subsystem: mcp
tags: [mcp, click, cli, transport, http, stdio, dispatcher]

# Dependency graph
requires:
  - phase: 52-resource-subscriptions
    provides: build_server() returns (Server, SubscriptionManager) tuple — Plan 52-04 contract preserved verbatim
  - phase: 50-server-endpoint-prep-v2-design-doc
    provides: v2 design doc §3.3 documents the Streamable HTTP transport approach Phase 53 implements
provides:
  - --transport [stdio|http] / --host / --port Click options on agent-brain-mcp
  - build_server() with split backend_transport= / listen_transport= axis labels (Phase 53 D-01)
  - Backwards-compatible build_server(transport=) deprecation alias emitting DeprecationWarning
  - main_async() dispatcher choosing run_stdio vs run_http on the listen-side transport
  - run_http(server, manager, *, host, port) NotImplementedError stub awaiting Plan 02
  - No-silent-fallback invariant pinned in tests (HTTP-03)
affects: [53-02-http-listener, 53-03-sdk-smoke-docs, 54-mcp-tool-completion, 55-validation-qa]

# Tech tracking
tech-stack:
  added: []  # no new deps — leverages existing Click + MCP SDK 1.12.x
  patterns:
    - Two-axis transport labeling (backend vs listen) via private Server._agent_brain_* attributes
    - Deprecation alias kwarg routed via warnings.warn(stacklevel=2)
    - Click case-insensitive Choice + IntRange validators for CLI input sanitization
    - asyncio.run + main_async kwargs as the dispatch surface (no module-level globals)

key-files:
  created:
    - agent-brain-mcp/tests/test_cli_transport_flags.py
    - agent-brain-mcp/tests/test_dispatch.py
  modified:
    - agent-brain-mcp/agent_brain_mcp/cli.py
    - agent-brain-mcp/agent_brain_mcp/server.py
    - agent-brain-mcp/tests/test_smoke.py

key-decisions:
  - "Backwards-compat alias: build_server(transport=) routes to backend_transport with DeprecationWarning. Keeps Phase 52 tuple-return contract + alias path working without coordinated rename across the test suite."
  - "Legacy _agent_brain_transport attribute kept as one-way shim mirroring backend_transport (Phase 55 will remove). _agent_brain_backend_transport and _agent_brain_listen_transport are the new private contract."
  - "run_http stub takes (server, subscription_manager, *, host, port) so Plan 02 inherits the disconnect-cleanup contract symmetrically with run_stdio."
  - "main_async raises ValueError on unknown transport — Click's Choice already rejects at the CLI layer; this is the defensive guard for direct callers (tests, embeddings)."
  - "No env-var read for transport selection: AGENT_BRAIN_MCP_TRANSPORT is documented as reserved-but-not-honored per Phase 53 D-02."
  - "When BOTH transport= and backend_transport= are passed, the legacy transport= wins. Keeps the migration path single-knob: callers replacing transport=X with backend_transport=X don't accidentally drop their value mid-edit."

patterns-established:
  - "Two-axis transport labels (backend vs listen) on Server instance: pattern reusable for Phase 53 Plan 02 (HTTP serverInfo._meta surfacing) and Phase 55 SDK contract validation."
  - "monkeypatch.setattr(server_module, 'run_stdio', AsyncMock(...)) + AsyncMock(server_module, 'run_http', ...) is the canonical isolation pattern for main_async() dispatch tests — keeps the version-compat check and build_server in the path while neutralizing the I/O entry points."

requirements-completed: [HTTP-01, HTTP-03]
# HTTP-01: CLI flag surface shipped (full --transport/--host/--port). Plan 02 closes the HTTP listener half.
# HTTP-03: Explicit selection / no silent fallback shipped end-to-end at the dispatcher level. Plan 02 layers on port-in-use ClickException.

# Metrics
duration: 31min
completed: 2026-06-03
---

# Phase 53 Plan 01: CLI transport flags + dispatcher refactor Summary

**Three new Click options (--transport [stdio|http], --host, --port) wired into agent-brain-mcp; main_async() now dispatches stdio vs http via a tuple-preserving build_server() refactor that splits Phase 52's single transport= kwarg into orthogonal backend_transport= / listen_transport= labels.**

## Performance

- **Duration:** 31 min
- **Started:** 2026-06-03T15:55:00Z (approx — first source edit)
- **Completed:** 2026-06-03T16:25:05Z (task before-push exit 0)
- **Tasks:** 4 (cli flags, server.py refactor, CLI test file, dispatcher test file + smoke touch)
- **Files modified:** 5 (2 source, 3 test)

## Accomplishments

- **CLI surface (HTTP-01 partial):** `--transport [stdio|http]` (case-insensitive Choice, default stdio), `--host TEXT` (default 127.0.0.1), `--port INTEGER` (default 8765, click.IntRange(1, 65535)) all advertised in `--help`, all parse correctly, all reject invalid values with Click's standard usage errors.
- **build_server() two-axis refactor:** Phase 52's single `transport=` kwarg split into orthogonal `backend_transport=` (how MCP talks to agent-brain-serve) and `listen_transport=` (how MCP client reaches MCP server). Both axis labels surfaced on the Server instance as private attributes for in-process testing; Plan 03 will wire these into the MCP `initialize` `serverInfo._meta` blob over the wire.
- **Backwards compatibility preserved:** `build_server(transport=X)` legacy path still works, emits `DeprecationWarning("build_server(transport=) is deprecated; use backend_transport=", stacklevel=2)`, and routes the value to `backend_transport`. Phase 52 tuple-return contract (`tuple[Server, SubscriptionManager]`) untouched. 250 existing tests still pass without modification.
- **main_async() dispatcher (HTTP-03 full):** Accepts `transport: str = "stdio"`, `host: str = "127.0.0.1"`, `port: int = 8765`. Dispatches:
  - `transport="stdio"` → `await run_stdio(server, manager)` (Phase 52 path unchanged byte-for-byte)
  - `transport="http"` → `await run_http(server, manager, host=host, port=port)` (Plan 02 stub raises NotImplementedError)
  - Anything else → `raise ValueError(f"Unknown transport: {transport!r}")` (defensive guard for direct callers bypassing Click)
  - No silent fallback on HTTP runtime errors — pinned by `test_no_silent_fallback_on_http_runtime_error`.
- **run_http stub:** `async def run_http(server, manager, *, host, port)` raises `NotImplementedError("HTTP transport implemented in Plan 02")`. Manager parameter mirrors `run_stdio`'s signature so Plan 02 inherits the Phase 52 disconnect-cleanup contract symmetrically across both transports.
- **24 net new tests, 274 total:** 10 CLI flag tests (test_cli_transport_flags.py), 13 dispatcher tests (test_dispatch.py), +1 smoke assertion (test_smoke.py). Black, Ruff, mypy strict all green; 3 layering contracts kept; full monorepo `task before-push` exits 0 with 416 passed.

## Task Commits

1. **Task 1+2: CLI flags + server.py refactor (build_server signature, run_http stub, main_async dispatch)** — `3e76220` (feat)
2. **Task 3+4: tests/test_cli_transport_flags.py NEW + tests/test_dispatch.py NEW + tests/test_smoke.py legacy-alias assertion** — `52ddfdf` (test)

**Plan metadata commit:** (this commit — final, includes SUMMARY.md + STATE.md + ROADMAP.md updates)

## Files Created/Modified

- `agent-brain-mcp/agent_brain_mcp/cli.py` — Added three Click options (`--transport`, `--host`, `--port`) and threaded them through `main_async(...)`. Existing `--backend / --backend-url / --state-dir` untouched (orthogonal axis per Phase 53 D-01).
- `agent-brain-mcp/agent_brain_mcp/server.py` — `build_server()` signature now `(httpx_client, *, backend_transport="http", listen_transport="stdio", transport=None)`. Legacy `transport=` kwarg routes through `warnings.warn(..., DeprecationWarning, stacklevel=2)` to `backend_transport`. Both new axis labels and the legacy shim set as private Server attributes. New `async def run_http(server, manager, *, host, port)` stub. `main_async()` accepts new kwargs and dispatches on `transport`. `import warnings` added.
- `agent-brain-mcp/tests/test_cli_transport_flags.py` NEW — 10 tests across 4 classes (help surface, transport rejection, port range, dispatch passthrough). CliRunner-driven with asyncio.run + main_async monkey-patched.
- `agent-brain-mcp/tests/test_dispatch.py` NEW — 13 tests across 4 classes covering build_server two-axis contract, deprecation alias, main_async dispatch (stdio/http/invalid), listen_transport propagation, no-silent-fallback, and run_http stub.
- `agent-brain-mcp/tests/test_smoke.py` — Added `test_build_server_legacy_transport_kwarg_still_constructs` assertion pinning the deprecation-alias smoke path.

## Decisions Made

- **Legacy `transport=` kwarg wins over explicit `backend_transport=`.** Documented in `build_server()` body and pinned by `test_legacy_transport_kwarg_does_not_override_explicit_backend`. Rationale: single-knob migration — callers replacing `transport=X` with `backend_transport=X` don't accidentally drop their value during the edit.
- **`_agent_brain_transport` legacy shim kept as one-way mirror of `backend_transport`.** No production tests read it (verified by grep), but the shim costs nothing and protects any downstream observability/debug code that may sample the private attribute. Phase 55 removal noted in the inline comment.
- **run_http takes `subscription_manager` parameter even though Plan 01's stub never uses it.** Plan 02 will need the manager for the HTTP-side `try/finally` cleanup hook (Phase 52 CONTEXT decision D, layer 1). Plumbing it through now avoids a backward-incompatible signature change in Plan 02.
- **No env-var support for `--transport`.** Honors Phase 53 D-02. Help text explicitly mentions `AGENT_BRAIN_MCP_TRANSPORT is reserved but NOT honored in v2 (Phase 53 D-02)` so operators don't quietly assume it works.

## Deviations from Plan

**Total deviations:** 1 (Rule 2 — missing critical functionality, scoped to the test surface)

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] No-silent-fallback test added to test_dispatch.py**

- **Found during:** Task 4 (writing test_dispatch.py)
- **Issue:** The plan's Verification section lists "no silent fallback if `transport="http"` and `run_http` raises any error other than `NotImplementedError`" as an acceptance criterion (line 24), but the plan's Implementation Step 8 (test_dispatch.py spec) did not enumerate a corresponding test case. Without it, HTTP-03's "explicit selection / no silent fallback" requirement would be unpinned at the dispatcher level.
- **Fix:** Added `test_no_silent_fallback_on_http_runtime_error` to `TestMainAsyncDispatch` — patches `run_http` to raise `OSError("Address already in use")` and asserts (a) the error propagates and (b) `run_stdio` is never awaited as a fallback.
- **Files modified:** `agent-brain-mcp/tests/test_dispatch.py`
- **Verification:** Test passes (`tests/test_dispatch.py::TestMainAsyncDispatch::test_no_silent_fallback_on_http_runtime_error PASSED`)
- **Committed in:** `52ddfdf` (Task 3+4 commit)

**Impact on plan:** No scope creep — this directly tightens an acceptance criterion the plan already listed. Plan 02's port-in-use ClickException wrapping rides on top of this invariant; pinning the invariant here means a regression in Plan 02 can't silently downgrade HTTP failures to stdio.

## Issues Encountered

- **None.** SDK availability gate (`from mcp.server.streamable_http_manager import StreamableHTTPSessionManager`) passed cleanly on the first invocation — risk #1 in 53-PLAN.md cleared. The version-compat probe was straightforward to stub via `monkeypatch.setattr("agent_brain_mcp.client.ApiClient.server_health", ...)`. Click's `case_sensitive=False` Choice normalized values cleanly without test-side coercion. The `run_stdio` / `run_http` `AsyncMock` patches worked first try (`monkeypatch.setattr(server_module, ...)` on the module-level functions, not the imported names).

## User Setup Required

None — no external service configuration introduced. Plan 02 will add operator-visible behavior (HTTP listener startup banner with loopback-only warning per D-10), but Plan 01 is purely internal plumbing + CLI flag surface.

## Next Phase Readiness

**Ready for Plan 02 (53-02 — HTTP listener implementation):**

- `run_http(server, manager, *, host, port)` stub is in place with the exact signature Plan 02 needs. Swap the `raise NotImplementedError` body for the StreamableHTTPSessionManager + uvicorn wiring.
- `main_async()` dispatcher already routes HTTP traffic to `run_http`; Plan 02 won't touch the dispatcher.
- `build_server()` already surfaces `listen_transport` on the Server instance; Plan 03 will wire this into the MCP `initialize` `serverInfo._meta` blob over the wire.
- Backwards-compat alias means Plan 02 can keep using the `(server, manager) = build_server(httpx_client, backend_transport=X, listen_transport=Y)` shape without further refactor pressure.

**Concerns for Plan 02:**

- The `subscription_manager` parameter on `run_http` is currently unused (Plan 01 stub). Plan 02 must wire it into the HTTP-side disconnect-cleanup hook (mirror of Phase 52 Plan 04's stdio `finally: manager.cleanup_all()` pattern). If Plan 02 misses this, the symmetric-cleanup contract documented in the v2 design doc §3.3.1 carry-forward breaks.
- The current `_agent_brain_listen_transport` private attribute is in-process only. Plan 03's SDK smoke test will assert the label via the over-the-wire `_meta` blob; if Plan 02's HTTP path doesn't expose the attribute via the `InitializationOptions`, Plan 03 will need a server-side wiring change (likely surface here rather than in Plan 03).

---

## Self-Check: PASSED

- `agent-brain-mcp/agent_brain_mcp/cli.py` — FOUND (modified, contains --transport/--host/--port)
- `agent-brain-mcp/agent_brain_mcp/server.py` — FOUND (modified, contains build_server backend_transport/listen_transport split + run_http stub + main_async dispatcher)
- `agent-brain-mcp/tests/test_cli_transport_flags.py` — FOUND (created, 10 tests pass)
- `agent-brain-mcp/tests/test_dispatch.py` — FOUND (created, 13 tests pass)
- `agent-brain-mcp/tests/test_smoke.py` — FOUND (modified, 2 tests pass including the new legacy-alias smoke)
- Commit `3e76220` — FOUND (feat(53-01): CLI flags + dispatcher refactor)
- Commit `52ddfdf` — FOUND (test(53-01): pin CLI transport flags + dispatcher contract)
- `task before-push` — exit code 0 (416 monorepo tests passed)
- `task check:layering` — exit code 0 (3 contracts kept)

---
*Phase: 53-streamable-http-transport*
*Completed: 2026-06-03*
