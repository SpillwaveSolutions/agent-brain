# Plan 01: CLI transport flags + dispatcher refactor

**Phase:** 53 — Streamable HTTP transport
**Requirements covered:** HTTP-01 (partial — flag surface), HTTP-03 (full — explicit selection / no silent fallback)
**Depends on:** none — first plan
**Parallel-safe with:** none (touches both `cli.py` and `server.py` which Plan 02 also extends)
**Status:** Not started

## Goal

Add the three new Click options (`--transport`, `--host`, `--port`) to `agent-brain-mcp` and refactor `main_async()` to dispatch on `transport`. Stdio remains the default; HTTP dispatches into a stub `run_http()` that raises `NotImplementedError` for now (Plan 02 fills it). The `build_server()` signature gains a second axis label (`listen_transport`) so the MCP `initialize` payload reports both labels in `_meta` for client debugging. This plan ships a fully testable CLI surface for HTTP-03's "explicit selection" semantics without yet starting a real HTTP listener — keeping the diff atomic.

## Acceptance Criteria

- [ ] `agent-brain-mcp --help` lists `--transport [stdio|http]`, `--host TEXT`, and `--port INTEGER` options under the existing flag block.
- [ ] `agent-brain-mcp --transport stdio` (and `agent-brain-mcp` with no transport flag) produces identical stdio behavior to today — existing `test_e2e_stdio.py` and `test_smoke.py` still pass byte-for-byte equivalent results.
- [ ] `agent-brain-mcp --transport bogus` exits non-zero with a Click usage error mentioning `'bogus' is not one of 'stdio', 'http'` (Click's standard `Choice` rejection).
- [ ] `agent-brain-mcp --transport http` reaches the dispatcher and raises `NotImplementedError("HTTP transport implemented in Plan 02")` (placeholder — Plan 02 replaces).
- [ ] `--transport` default is `stdio`. `AGENT_BRAIN_MCP_TRANSPORT` env var is **NOT** read (D-02 — reserved name, not honored in v2).
- [ ] `--host` defaults to `127.0.0.1` (only validated/enforced in Plan 02; Plan 01 just plumbs it through).
- [ ] `--port` defaults to `8765`, uses `click.IntRange(1, 65535)` for input validation.
- [ ] `build_server()` accepts a new `listen_transport: str = "stdio"` keyword argument. The existing `transport=` parameter is renamed to `backend_transport=` (backwards-compatible alias preserved: if caller passes `transport=`, log a `DeprecationWarning` and route to `backend_transport`). The `_meta` block surfaces BOTH `_meta.agentBrainBackendTransport` and `_meta.agentBrainListenTransport`.
- [ ] `main_async()` accepts new keyword args `transport: str = "stdio"`, `host: str = "127.0.0.1"`, `port: int = 8765`. Dispatch logic: stdio path calls `run_stdio(server)`; http path calls `run_http(server, host=host, port=port)` (which raises `NotImplementedError` in this plan).
- [ ] No silent fallback: if `transport == "http"` and `run_http` raises any error other than `NotImplementedError`, it propagates — no rewrite to stdio. (Plan 02's port-in-use handling is layered on top of this contract.)
- [ ] All Phase 53 tests added in this plan pass (see Verification below); pre-existing 18+ MCP unit/integration tests continue to pass.
- [ ] `cd agent-brain-mcp && poetry run black . && poetry run ruff check . && poetry run mypy agent_brain_mcp && poetry run pytest` exits 0.

## Files to Touch

| File                                                                | Action  | Notes |
|---------------------------------------------------------------------|---------|-------|
| `agent-brain-mcp/agent_brain_mcp/cli.py`                            | modify  | Add `--transport / --host / --port` Click options; pass through to `main_async`. |
| `agent-brain-mcp/agent_brain_mcp/server.py`                         | modify  | Rename `build_server(transport=)` → `build_server(backend_transport=)` with deprecation alias; add `listen_transport=` keyword. Expand `_meta` block to surface both labels. Add `async def run_http(server, *, host, port)` stub that raises `NotImplementedError("HTTP transport implemented in Plan 02")`. Refactor `main_async()` to accept `transport/host/port` and dispatch on `transport`. |
| `agent-brain-mcp/tests/test_cli_transport_flags.py`                 | create  | New test file: `--help` lists new options; `--transport bogus` exits with Click error; `--transport http` dispatches to `run_http` stub (mock the stub); default is stdio. |
| `agent-brain-mcp/tests/test_dispatch.py`                            | create  | New test file: `main_async(transport="stdio")` calls `run_stdio`; `main_async(transport="http")` calls `run_http`; no silent crossover; build_server's `_meta` block carries both axis labels. |
| `agent-brain-mcp/tests/test_smoke.py`                               | modify  | Add one assertion that the existing stdio smoke continues to pass after the `transport=` → `backend_transport=` parameter rename (deprecation alias verified). |

## Implementation Steps

1. **Verify MCP SDK version.** Before any edit, run `cd agent-brain-mcp && poetry run python -c "from mcp.server.streamable_http_manager import StreamableHTTPSessionManager; print('ok')"`. If this fails, file a one-line note in the plan's risk section and STOP — escalate to user before proceeding. (Risk #1 in 53-PLAN.md.)
2. **Add Click options in `cli.py`.** After the existing `--state-dir` option, add three new Click options:
   - `--transport`: `click.Choice(["stdio", "http"], case_sensitive=False)`, default `"stdio"`, help string mentions "Listen transport. Auth deferred to v4 — http binds loopback only."
   - `--host`: `str`, default `"127.0.0.1"`, help string mentions "Loopback host for --transport http. Only 127.0.0.1 / localhost / ::1 accepted."
   - `--port`: `click.IntRange(1, 65535)`, default `8765`, help string mentions "TCP port for --transport http."
   Pass all three through to `asyncio.run(main_async(...))`. Do NOT touch the existing `--backend / --backend-url / --state-dir` options — they're an orthogonal axis (D-01).
3. **Rename `build_server()` parameter.** In `server.py`:
   - Change `def build_server(httpx_client: httpx.Client, *, transport: str = "http") -> Server:` to `def build_server(httpx_client: httpx.Client, *, backend_transport: str = "http", listen_transport: str = "stdio", transport: str | None = None) -> Server:`.
   - At top of function body: if `transport is not None`, emit `warnings.warn("build_server(transport=) is deprecated; use backend_transport=", DeprecationWarning, stacklevel=2)` and set `backend_transport = transport`.
   - Replace the existing `server._agent_brain_transport = transport` (line 209) with two attributes: `server._agent_brain_backend_transport = backend_transport` and `server._agent_brain_listen_transport = listen_transport`. (Keep `_agent_brain_transport = backend_transport` as a backward-compat shim for any test that reads it; mark with a comment for removal in Phase 55.)
4. **Surface both labels in `initialize`.** The MCP SDK's `Server.get_capabilities()` / `InitializationOptions` doesn't directly read these private attributes; the labels appear in the `serverInfo._meta` block per the v1 plan's §6.1 lockstep pattern. Locate where `_meta` is constructed in the current stdio path (search for `_meta` in `server.py` and `run_stdio` — if not present in v1, add a comment marker `# Phase 55 will wire _meta surfacing; for now both labels live on Server.* attributes`). The Phase 53 contract is: both labels are accessible to tests via the `Server` attributes. Plan 03 will assert them via `serverInfo._meta` over the wire once the HTTP path lights up.
5. **Add `run_http` stub in `server.py`.** Below `run_stdio`:
   ```python
   async def run_http(server: Server, *, host: str, port: int) -> None:
       """Run the MCP server over Streamable HTTP. Implemented in Phase 53 Plan 02."""
       raise NotImplementedError("HTTP transport implemented in Plan 02")
   ```
6. **Refactor `main_async()` to dispatch.** Update the signature to accept `transport: str = "stdio"`, `host: str = "127.0.0.1"`, `port: int = 8765`. After the version-compat check, replace the unconditional `await run_stdio(server)` call with:
   ```python
   if transport == "stdio":
       await run_stdio(server)
   elif transport == "http":
       await run_http(server, host=host, port=port)
   else:
       # Click's Choice already rejects this; defensive guard for direct callers.
       raise ValueError(f"Unknown transport: {transport!r}")
   ```
   Pass `listen_transport=transport` to `build_server()`.
7. **Write `tests/test_cli_transport_flags.py`.** Use Click's `CliRunner`:
   - Test 1: `runner.invoke(main, ["--help"])` — assert stdout contains `--transport [stdio|http]`, `--host`, `--port`.
   - Test 2: `runner.invoke(main, ["--transport", "bogus"])` — assert exit_code != 0 and `"'bogus' is not one of 'stdio', 'http'"` in result.output (case-insensitive — Click message is `'bogus' is not one of 'stdio', 'http'`).
   - Test 3: monkey-patch `asyncio.run` to capture the awaitable's args; assert default invocation passes `transport="stdio"`.
   - Test 4: `runner.invoke(main, ["--transport", "http", "--port", "9999"])` — assert the awaitable receives `transport="http"`, `port=9999`. Use a fake `main_async` via monkeypatch that records its kwargs without actually starting a server.
   - Test 5: `runner.invoke(main, ["--port", "0"])` — assert Click rejects (IntRange 1..65535).
8. **Write `tests/test_dispatch.py`.** Use `pytest-asyncio` (already set up — `asyncio_mode = "auto"`):
   - Test 1: Patch `run_stdio` and `run_http` as `AsyncMock`s; call `main_async(transport="stdio", ...)` — assert `run_stdio` was awaited once and `run_http` was not.
   - Test 2: Same setup; call `main_async(transport="http", host="127.0.0.1", port=8765, ...)` — assert `run_http` was awaited with `host="127.0.0.1"` and `port=8765`, and `run_stdio` was not.
   - Test 3: `main_async(transport="invalid", ...)` raises `ValueError`.
   - Test 4: `build_server(httpx_client, backend_transport="uds", listen_transport="http")` produces a `Server` whose `_agent_brain_backend_transport == "uds"` and `_agent_brain_listen_transport == "http"`.
   - Test 5: `build_server(httpx_client, transport="uds")` (legacy kwarg) emits `DeprecationWarning` and sets `_agent_brain_backend_transport == "uds"`.
   Use `pytest.warns(DeprecationWarning)` for the legacy kwarg test.
9. **Run the quality gate locally.** From repo root: `cd agent-brain-mcp && poetry run black . && poetry run ruff check . --fix && poetry run mypy agent_brain_mcp && poetry run pytest -x`. Fix any failures. Do NOT run `task before-push` from root yet — that's a Phase 55 / VAL-04 task. Per-package quality gate is sufficient for Plan 01.

## Verification

- **Click help surface:** `cd agent-brain-mcp && poetry run agent-brain-mcp --help | grep -E "(transport|host|port)"` shows three lines for the new options.
- **Bogus transport rejected:** `poetry run agent-brain-mcp --transport bogus 2>&1 | grep -i "not one of"` exits non-zero.
- **HTTP stub fires:** `poetry run agent-brain-mcp --transport http 2>&1 | grep -i "not implemented"` exits non-zero (the `NotImplementedError` surfaces as a traceback). This will be GREEN in Plan 02.
- **Stdio unchanged:** `cd agent-brain-mcp && poetry run pytest tests/test_smoke.py tests/test_e2e_stdio.py -v` passes — proves backward compatibility.
- **New tests pass:** `cd agent-brain-mcp && poetry run pytest tests/test_cli_transport_flags.py tests/test_dispatch.py -v` passes.
- **Full per-package gate:** `cd agent-brain-mcp && poetry run black --check . && poetry run ruff check . && poetry run mypy agent_brain_mcp && poetry run pytest` exits 0.
- **Pre-push (only if Phase 55 already integrated `task before-push`):** root `task before-push` exits 0. If MCP is not yet in root `task before-push` (it isn't — that's VAL-04 in Phase 55), this verification step is omitted for Plan 01.

## Risk Notes

- **Deprecation alias for `transport=`:** required because `build_server()` is called from at least three places in the package (`server.py:main_async` itself, `tests/conftest.py`, and `tests/test_smoke.py` per existing structure). The alias keeps tests passing without a coordinated rename across the test suite — Plan 03 / Phase 55 can do that cleanup.
- **`Server` attribute access in tests:** the `_agent_brain_*_transport` attributes are private (underscore-prefixed). Tests that read them are tightly coupled to the implementation. This is acceptable for Phase 53 because the `_meta` over-the-wire surface (the public contract) is asserted in Plan 03's HTTP smoke; Plan 01's tests just verify the in-process plumbing.
- **No env var for `--transport`:** D-02 explicitly forbids reading `AGENT_BRAIN_MCP_TRANSPORT`. If a downstream test sets that env var, it must be ignored. No test for this in Plan 01 (negative-space test is brittle); Plan 03's USER_GUIDE.md update will note it.
- **`run_http` is a stub:** Plan 01 lands a half-feature on `main`. Mitigation: the stub raises `NotImplementedError` cleanly — no half-bound socket, no partial HTTP behavior. CI cannot accidentally exercise it because no test in this plan invokes `run_http` directly except via mock.

---
*Plan 01 of Phase 53*
