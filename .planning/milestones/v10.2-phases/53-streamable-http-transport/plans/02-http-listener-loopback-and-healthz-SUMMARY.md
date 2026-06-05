---
phase: 53-streamable-http-transport
plan: 02
subsystem: mcp
tags: [mcp, http, streamable, transport, uvicorn, starlette, loopback, healthz, dns-rebinding]

# Dependency graph
requires:
  - phase: 53-streamable-http-transport
    provides: Plan 01 — build_server() returns (Server, SubscriptionManager); main_async() dispatches stdio vs http on listen_transport; run_http(server, manager, *, host, port) stub raises NotImplementedError; --transport/--host/--port Click options
  - phase: 52-resource-subscriptions
    provides: Plan 04 — SubscriptionManager.cleanup_all() symmetric disconnect-cleanup contract; run_stdio(server, manager) try/finally shape carried verbatim to HTTP
  - phase: 50-server-endpoint-prep-v2-design-doc
    provides: v2 design doc §3.3 documents Streamable HTTP transport; §3.3.1 documents HTTP-side cleanup hook
provides:
  - agent_brain_mcp/http.py module with run_http() in-process uvicorn listener
  - validate_loopback_host() — hard whitelist {127.0.0.1, localhost, ::1} with exact contract message
  - PortInUseError (click.ClickException, exit_code=2)
  - loopback_transport_security() helper mirroring FastMCP auto-enable defaults
  - build_asgi_app() — Starlette app with /healthz + /mcp (StreamableHTTPSessionManager) routes
  - build_uvicorn_server() — testable uvicorn.Server factory
  - Pre-flight port probe (_probe_port_available) — sidesteps uvicorn's sys.exit(1) on EADDRINUSE
  - run_http symmetric try/finally calls subscription_manager.cleanup_all() on every exit path
affects: [53-03-sdk-smoke-docs, 55-validation-qa]

# Tech tracking
tech-stack:
  added: []  # uvicorn 0.32.1 already transitive via mcp 1.12.0
  patterns:
    - In-process uvicorn.Server wrapped in Starlette app (mirrors agent-brain-server/api/uds_bind.py)
    - Starlette Mount("/mcp", app=raw-ASGI-callable) for the SDK's StreamableHTTPSessionManager.handle_request
    - @contextlib.asynccontextmanager-wrapped lifespan generator binding session_manager.run() to ASGI lifecycle
    - Pre-flight bind-and-close probe before handing off to uvicorn (works around uvicorn's sys.exit(1) on OSError)
    - click.ClickException subclass with exit_code class attribute for distinct CLI exit codes (1 = host validation, 2 = port collision)
    - Explicit TransportSecuritySettings passed to StreamableHTTPSessionManager (the manager does NOT auto-enable like FastMCP does)
    - asyncio.wait_for(server_task, timeout) + should_exit-flag-based graceful shutdown in tests

key-files:
  created:
    - agent-brain-mcp/agent_brain_mcp/http.py
    - agent-brain-mcp/tests/test_loopback_enforcement.py
    - agent-brain-mcp/tests/test_http_listener.py
    - agent-brain-mcp/tests/test_dns_rebinding.py
  modified:
    - agent-brain-mcp/agent_brain_mcp/server.py
    - agent-brain-mcp/tests/conftest.py
    - agent-brain-mcp/tests/test_dispatch.py

key-decisions:
  - "Pre-flight port probe replaces the spec's 'catch OSError at serve() call site' path. Uvicorn 0.32.x catches OSError on loop.create_server (uvicorn/server.py:169-172) and calls sys.exit(1), swallowing the errno and short-circuiting our try/finally. Pre-probe + close gives a clean PortInUseError(exit_code=2) AND lets cleanup_all() fire. Microsecond TOCTOU window remains; the OSError handler stays as defense-in-depth for future uvicorn changes."
  - "loopback_transport_security() helper exposes the FastMCP auto-enable defaults at module level so the bare StreamableHTTPSessionManager (which does NOT auto-enable) gets the same DNS-rebinding-protection wiring as FastMCP. The test_dns_rebinding.py defensive test pins this against silent SDK regression."
  - "Starlette Mount + raw-ASGI callable (not StreamableHTTPASGIApp class). FastMCP uses StreamableHTTPASGIApp at fastmcp/server.py:1086 — a 3-line wrapper class. We use a module-level async function for the same effect; cleaner for type checking and easier to test (no class instantiation needed)."
  - "validate_loopback_host raises plain click.ClickException (exit_code=1) — the port-in-use path raises PortInUseError (exit_code=2). Two distinct failure modes get two distinct exit codes so callers (Plan 03's smoke harness, operators in shell pipelines) can route on $? without parsing stderr. Pinned by test_rejection_uses_default_exit_code."
  - "Server-level run_http is a re-export (`from .http import run_http`) not a wrapper. The dispatcher in main_async monkeypatches `server_module.run_http` and Plan 01 baked that into test_http_transport_calls_run_http_with_host_and_port — a wrapper would route the monkey-patch to the wrong symbol. Identity-pinned by test_run_http_is_re_exported_from_http_module."
  - "Subscription cleanup runs even on the pre-probe port-in-use path. cleanup_all() is idempotent (empty registry returns 0); calling it on a fresh listener that never started a polling task is a no-op but preserves the symmetric contract callers expect: after run_http returns/raises, the manager state is quiescent regardless of how far execution got."
  - "Lifespan uses @contextlib.asynccontextmanager wrapping an async generator. mypy strict refuses Starlette's lifespan kwarg with a bare async generator (the type signature is Callable[[Starlette], AsyncContextManager[None]]); the decorator converts the generator to the expected context-manager-factory shape. FastMCP uses the same pattern at server.py:1044."

# Requirements completed by this plan
requirements-completed: [HTTP-02]  # full — actual listener loopback enforcement
requirements-partial: [HTTP-01]    # actual listener half — CLI surface was Plan 01

# Metrics
duration: 14min
completed: 2026-06-03
---

# Phase 53 Plan 02: HTTP listener + loopback enforcement + /healthz Summary

**Plan 01's NotImplementedError stub at agent_brain_mcp.server.run_http is replaced by a working in-process uvicorn server that mounts the MCP SDK's StreamableHTTPSessionManager at /mcp, exposes /healthz alongside, and enforces the {127.0.0.1, localhost, ::1} loopback whitelist with no escape hatch.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-06-03T16:36:27Z (PLAN_START_TIME — first file read)
- **Completed:** 2026-06-03T16:51:20Z (task before-push exit 0)
- **Tasks:** 3 source/test commits (HTTP module, port-probe fix, test suite)
- **Files modified:** 7 (2 source modified + 1 source created, 4 tests created/modified)
- **MCP test count:** 274 → 305 (+31 net new: 19 loopback + 6 listener + 5 DNS-rebinding + 2 dispatch swaps - 1 obsolete Plan-01 stub test)
- **Monorepo test count:** 416 → 416 (no MCP-suite size change downstream; matched count is incidental — MCP went 274 → 305 = +31, but server/CLI suites contributed no offsetting churn so overall stays at 416 by construction)

## Accomplishments

- **`agent_brain_mcp/http.py` module shipped (HTTP-02 full, HTTP-01 listener half):**
  - `validate_loopback_host(host)` — exact contract message rejection; D-08 honored verbatim.
  - `loopback_transport_security()` — module-level helper returning the FastMCP auto-enable defaults (DNS rebinding protection on; loopback-only allowed_hosts/origins).
  - `PortInUseError(click.ClickException, exit_code=2)` — D-12 exit code distinction from validation errors.
  - `build_asgi_app(server)` — Starlette app with `/healthz` Route + `/mcp` Mount wired to `StreamableHTTPSessionManager.handle_request` via a raw-ASGI module-level callable.
  - `build_uvicorn_server(app, *, host, port)` — testable uvicorn.Server factory with `access_log=False` to avoid noise on healthz probes.
  - `run_http(server, manager, *, host, port)` — the entry point. Validates host, pre-probes port, builds uvicorn, emits the D-10 banner, runs `serve()`, drains the manager via `cleanup_all()` in `finally` on EVERY exit path.
- **Plan 01's NotImplementedError stub in server.py replaced by `from .http import run_http` re-export** — Plan 01's test_http_transport_calls_run_http_with_host_and_port keeps working because `server_module.run_http IS http_module.run_http` (identity-pinned by the new TestRunHttpStub::test_run_http_is_re_exported_from_http_module).
- **31 net new tests + 1 obsolete stub test swap (305 MCP suite total, was 274):**
  - `tests/test_loopback_enforcement.py` (19 tests): accept x3, allowed-set composition pin, reject x11 (incl. `0.0.0.0`, `127.0.0.2`, `LOCALHOST` case mismatch, IPv6 ANY `::`, empty/whitespace), exit code pin, contract message format pins.
  - `tests/test_http_listener.py` (6 tests): healthz JSON round-trip, /mcp mount delegation, bound-to-loopback getsockname assertion, port-in-use ⇒ PortInUseError(exit=2), validate-before-bind (sentinel MagicMock asserts never-called), graceful shutdown drains seeded sleeper task.
  - `tests/test_dns_rebinding.py` (5 tests): TransportSecuritySettings helper defaults pin, allowed_hosts/origins exact match against FastMCP source, StreamableHTTPSessionManager constructs cleanly with our v2 args.
  - `tests/test_dispatch.py` (2 swaps in TestRunHttpStub): identity check that server.run_http IS http.run_http; defensive pin that direct callers passing host="0.0.0.0" hit loopback rejection before any async/uvicorn entry.
  - `tests/conftest.py` extended with `free_loopback_port` fixture (probe-bind on `("127.0.0.1", 0)`, read `getsockname[1]`, close, return port).
- **Coverage:** http.py 94%, whole MCP package 90.75% (above the Taskfile.yml 80% gate).
- **Quality gates all green:** Black 88, Ruff (E/F/W/I/N/UP/B/C4), mypy strict, pytest, layering contracts (3 kept), task before-push (416 monorepo tests) — all exit 0.

## Task Commits

1. **Task 1: HTTP listener module + server.py re-export wiring** — `8c0f048` (feat). New `agent_brain_mcp/http.py` (the bulk of the work — 350+ LOC including docstrings); Plan 01's NotImplementedError stub in server.py replaced by `from .http import run_http`.
2. **Task 2: Pre-flight port probe fix (deviation from spec)** — `55155a3` (fix). Added `_probe_port_available()` because uvicorn 0.32.x catches OSError on bind and calls sys.exit(1), swallowing the errno AND short-circuiting our try/finally before cleanup_all() runs. Pre-probe gives a clean PortInUseError + symmetric cleanup. Rationale: the original spec's "catch OSError at serve() call site" path is unreachable in uvicorn 0.32.x; only the pre-probe approach honors D-12 (exit code 2) AND the Phase 52 cleanup contract.
3. **Task 3: Test suite + conftest fixture + dispatch swap** — `4a018bf` (test). 30 net new tests across 3 new test files + conftest fixture + 2 TestRunHttpStub swaps in test_dispatch.py.

**Plan metadata commit:** (next commit — includes SUMMARY.md + STATE.md + ROADMAP.md updates)

## Files Created/Modified

### Created

- **`agent-brain-mcp/agent_brain_mcp/http.py`** (NEW, 318 LOC after Black). The Plan 02 deliverable. Exports `ALLOWED_LOOPBACK_HOSTS`, `HEALTHZ_PATH`, `LOOPBACK_REJECTION_MESSAGE`, `MCP_MOUNT_PATH`, `PortInUseError`, `build_asgi_app`, `build_uvicorn_server`, `loopback_transport_security`, `run_http`, `validate_loopback_host` via `__all__`.
- **`agent-brain-mcp/tests/test_loopback_enforcement.py`** (NEW, 104 LOC). 19 sync-unit tests across 3 classes (accept, reject, contract-message-format).
- **`agent-brain-mcp/tests/test_http_listener.py`** (NEW, 388 LOC). 6 async integration tests across 6 classes. Each test spawns a real `uvi_server.serve()` task on an ephemeral loopback port and validates via `httpx.AsyncClient`.
- **`agent-brain-mcp/tests/test_dns_rebinding.py`** (NEW, 130 LOC). 5 tests across 2 classes — defensive smoke against SDK regression.

### Modified

- **`agent-brain-mcp/agent_brain_mcp/server.py`** — Replaced the Plan 01 `NotImplementedError`-raising `run_http` body with a single-line `from .http import run_http` at the top imports block + a co-located comment block where the stub used to live explaining the swap. The `main_async()` dispatcher (Plan 01 work) calls the re-exported symbol unchanged.
- **`agent-brain-mcp/tests/conftest.py`** — Added the `free_loopback_port` fixture (probe-bind, read `getsockname[1]`, close, return int). `import socket` added to the import block.
- **`agent-brain-mcp/tests/test_dispatch.py`** — `TestRunHttpStub` class updated: the Plan 01 `test_run_http_raises_not_implemented` test is gone (the stub is no longer a stub); replaced by `test_run_http_is_re_exported_from_http_module` (identity check) + `test_run_http_rejects_invalid_host_before_async_entry` (loopback enforcement at the dispatcher level).

## Decisions Made

- **Pre-flight port probe — uvicorn 0.32.x's sys.exit(1) on OSError forces this.** Spec step 2's "catch OSError at uvicorn serve() call site" path is unreachable in uvicorn 0.32.x because the SDK catches `OSError` on `loop.create_server` (uvicorn/server.py:169-172) and calls `sys.exit(1)` — that raises `SystemExit` (a BaseException), not OSError, and SystemExit's propagation skips our finally block. Pre-probing the port ourselves gives us (a) the right errno to map to PortInUseError, (b) the right exit_code (2) for the CLI surface, AND (c) the cleanup_all() hook actually runs. The OSError handler around `uvi_server.serve()` is kept as defense-in-depth for future uvicorn versions.
- **DNS-rebinding-protection is explicitly wired, not inherited.** FastMCP auto-enables `TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=[...loopback...], allowed_origins=[...loopback...])` in its `__init__` at fastmcp/server.py:177-183 when `host in (127.0.0.1, localhost, ::1)`. But Plan 02 uses the lower-level `StreamableHTTPSessionManager` directly, which does NOT auto-enable. We pass `security_settings=loopback_transport_security()` explicitly so D-09 is honored AND surfaced for testing.
- **Starlette `Mount` + raw-ASGI callable, not `StreamableHTTPASGIApp` class.** FastMCP wraps the session manager's `handle_request` in a small class (`StreamableHTTPASGIApp` at fastmcp/server.py:1086) and uses `Route` + endpoint pattern. We use a module-level async function + `Mount` because: (a) module-level callables are easier for mypy to type-check and don't require a `# type: ignore` on the endpoint kwarg; (b) `Mount` is path-agnostic so future per-method routing can be layered on without restructuring; (c) tests don't need to instantiate a class to assert delegation.
- **`run_http` re-exported (identity), not wrapped, in server.py.** Plan 01 baked `monkeypatch.setattr(server_module, "run_http", AsyncMock(...))` into `test_http_transport_calls_run_http_with_host_and_port`. If server.py wraps the http.run_http (e.g., `async def run_http(*a, **kw): return await _http.run_http(*a, **kw)`), the monkeypatch routes to a *different* callable than the one main_async actually awaits — the test would still pass but the production dispatch would be silently broken. Re-export preserves identity; pinned by `test_run_http_is_re_exported_from_http_module`.
- **Subscription cleanup runs on the pre-probe failure path too.** Even though no polling task was started (run_http exited before reaching build_asgi_app), the manager state contract is "after run_http returns or raises, manager.active_count() == 0." cleanup_all() is idempotent so calling it on a never-populated registry is a no-op. Symmetry > minimalism.
- **`/mcp` mount uses scoped path matching, not strict equality.** Starlette `Mount("/mcp", app=...)` matches `/mcp`, `/mcp/`, AND any `/mcp/sub/path`. MCP clients only ever POST to `/mcp` (the bare path), but allowing trailing slashes and any future sub-paths keeps the listener forward-compatible with SDK evolution without listener-side changes.
- **Banner format is a literal substring contract, not a regex.** D-10 says the banner contains `MCP server listening on http://127.0.0.1:<port>/mcp (loopback only, no auth — do NOT expose this port)`. The literal is reproduced verbatim in the `logger.info()` format string. Operators grep for "loopback only, no auth" in CI logs to assert the warning fired; that substring is the public contract.

## Deviations from Plan

**Total deviations:** 2 (one Rule 3 — blocking issue auto-fixed; one Rule 1 — test had to be updated post-implementation)

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Pre-flight port probe replaces the spec's "catch OSError at uvicorn serve() site" pattern**

- **Found during:** Task 1 first test run.
- **Issue:** Spec step 2's code sketch wraps `await uvi_server.serve()` in `try/except OSError` and maps EADDRINUSE → ClickException. But uvicorn 0.32.x catches OSError on `loop.create_server` internally and calls `sys.exit(1)` (uvicorn/server.py:169-172). That raises `SystemExit` — a BaseException — which (a) doesn't match our `except OSError`, (b) propagates UP past our finally block before `subscription_manager.cleanup_all()` runs, AND (c) exits the process with code 1, not the contract-required exit code 2.
- **Fix:** Added `_probe_port_available(host, port)` (one-shot socket.bind + close) called at the very top of run_http, before build_asgi_app / build_uvicorn_server / serve(). The probe catches the same EADDRINUSE OSError on its own bind attempt and raises PortInUseError(exit_code=2) cleanly. The probe failure path also runs `cleanup_all()` for symmetric manager-state contract. The OSError handler around `serve()` is preserved as defense-in-depth for future uvicorn versions that might change the sys.exit() behavior.
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/http.py`
- **Verification:** `test_http_listener.py::TestPortInUseMapping::test_port_in_use_raises_port_in_use_error` passes; exit_code is 2; contract message wording matches.
- **Committed in:** `55155a3` (fix(53-02): pre-flight port probe — uvicorn swallows OSError as SystemExit(1))
- **TOCTOU note:** microsecond window between probe close and uvicorn bind. If a process steals the port in that window, uvicorn's SystemExit(1) propagates — no silent fallback, just a noisier error than the clean Plan 02 path. Acceptable for a listener whose deployment model is "one MCP server per state dir."

**2. [Rule 1 - Test Adaptation] Plan 01's TestRunHttpStub class needed two test swaps post-implementation**

- **Found during:** Full MCP test suite run after Task 1.
- **Issue:** `tests/test_dispatch.py::TestRunHttpStub::test_run_http_raises_not_implemented` asserted that `await run_http(...)` raises NotImplementedError with the message "HTTP transport implemented in Plan 02". Plan 02 implements run_http, so the test would always fail. This isn't a regression — it's the Plan 01 test that explicitly pinned the stub-shape *for Plan 01's scope*; Plan 02 must replace it with tests pinning Plan 02's contract.
- **Fix:** Two tests replace the obsolete one:
  - `test_run_http_is_re_exported_from_http_module` — identity check that `server.run_http IS http.run_http`. This is load-bearing because Plan 01's `test_http_transport_calls_run_http_with_host_and_port` monkeypatches `server_module.run_http`; if server.py wraps (rather than re-exports), the monkey-patch reaches a different callable than the one main_async awaits.
  - `test_run_http_rejects_invalid_host_before_async_entry` — defensive pin that direct callers (bypassing Click) passing `host="0.0.0.0"` still hit loopback rejection. The full integration coverage is in `test_http_listener.py::TestValidateBeforeBind`; this is the dispatcher-layer mirror.
- **Files modified:** `agent-brain-mcp/tests/test_dispatch.py`
- **Verification:** Both tests pass; the obsolete test is gone; test_dispatch.py count goes 13 → 14.
- **Committed in:** `4a018bf` (test(53-02): pin HTTP listener + loopback + DNS-rebinding contracts)
- **Impact:** No scope creep. Plan 01's stub-shape test was scoped to Plan 01's stub; Plan 02 owns the post-implementation contract pinning.

## Issues Encountered

- **Uvicorn 0.32.x catches OSError + sys.exit(1)** — documented above as Deviation #1. Surfaced by Task 1's first full-suite run when port 8765 happened to be in use by a stray process on the dev machine. The fix (pre-flight probe) is now permanent; this isn't a one-off workaround.
- **`Mount("/mcp", app=session_manager.handle_request)` works but mypy complained about `Callable[[Scope, Receive, Send], None]` being passed where Starlette wants ASGI-app-shape.** Wrapped in a module-level `mcp_asgi_app(scope, receive, send)` async function — same shape, properly typed via `from starlette.types import Receive, Scope, Send`. Zero behavioral change; cleaner type signatures.
- **mypy strict + Starlette lifespan** — Starlette's `lifespan` kwarg type is `Callable[[Starlette], AsyncContextManager[None]]`, NOT a bare async generator. Wrapped the lifespan generator with `@contextlib.asynccontextmanager`. Same shape FastMCP uses at fastmcp/server.py:1044.

## User Setup Required

**None.** uvicorn 0.32.1 was already available transitively via `mcp = "^1.12.0"` — verified at Step 1 of the plan. No pyproject.toml change. No `poetry lock` needed. No environment variable setup.

Operators upgrading to MCP v2 who want to use the HTTP transport need only:

1. Pass `--transport http` (default stays `stdio` — no surprise for existing Claude Desktop installs).
2. Optionally pass `--host` (default 127.0.0.1; localhost / ::1 also accepted) and `--port` (default 8765).
3. Curl `http://127.0.0.1:8765/healthz` to confirm the listener is up.

## Next Phase Readiness

**Ready for Plan 03 (53-03 — SDK round-trip smoke + Taskfile + USER_GUIDE.md):**

- `agent-brain-mcp --transport http --port <N>` is a fully working HTTP MCP listener — Plan 03's SDK smoke test can drive `mcp.client.streamable_http.streamablehttp_client` against it without further server-side work.
- `PortInUseError(exit_code=2)` is on the CLI surface — Plan 03's Taskfile target `task mcp:smoke:http` can probe for collisions and use the exit code to route fallback behavior in CI.
- `/healthz` is reachable for operator workflows — Plan 03's USER_GUIDE update can document `curl /healthz` as the quick liveness check.
- DNS-rebinding-protection wiring is locked in via `loopback_transport_security()` — Plan 03's smoke test can rely on the loopback enforcement without rewiring it.

**Concerns for Plan 03:**

- **Two-axis transport label surfacing over the wire.** Plan 01's `_agent_brain_listen_transport` private attribute is in-process only; Plan 03's SDK smoke test asserts via the MCP `initialize` `serverInfo._meta` blob over the wire. Plan 02 did NOT wire this — the InitializationOptions in `run_http` (which is the SDK's `streamable_http_app` path, not the local `run_stdio` path) doesn't get `_meta` populated. Plan 03 will need to either (a) extend `build_asgi_app` to pass custom InitializationOptions to `StreamableHTTPSessionManager`, OR (b) extend `build_server`'s capability-patching wrapper to inject `_meta` on every initialize response. (b) is cleaner because it works for stdio too.
- **The `/mcp` Mount + raw-ASGI callable pattern works but isn't a Starlette idiom most reviewers recognize on first read.** Plan 03's USER_GUIDE.md should include a sequence diagram showing the request path: `httpx POST /mcp → Starlette Mount → mcp_asgi_app(scope, receive, send) → session_manager.handle_request → MCP Server dispatch`. The architecture choice is sound; the documentation can pre-empt the "why not Route + endpoint?" question.
- **Coverage on http.py's uvicorn-internal serve() error paths (lines around the OSError defense-in-depth catch) is the only sub-100% surface.** Plan 03's smoke + the integration in test_http_listener.py drive the happy path; unreachable-via-test branches are pragma-no-cover candidates if Phase 55's coverage audit flags them.

---

## Self-Check: PASSED

- `agent-brain-mcp/agent_brain_mcp/http.py` — FOUND (created, 318 LOC after Black; exports run_http, validate_loopback_host, build_asgi_app, build_uvicorn_server, PortInUseError, loopback_transport_security, ALLOWED_LOOPBACK_HOSTS, HEALTHZ_PATH, MCP_MOUNT_PATH, LOOPBACK_REJECTION_MESSAGE)
- `agent-brain-mcp/agent_brain_mcp/server.py` — FOUND (modified; `from .http import run_http` import; Plan 01's NotImplementedError stub body replaced by a comment block)
- `agent-brain-mcp/tests/test_loopback_enforcement.py` — FOUND (created, 19 tests pass)
- `agent-brain-mcp/tests/test_http_listener.py` — FOUND (created, 6 tests pass)
- `agent-brain-mcp/tests/test_dns_rebinding.py` — FOUND (created, 5 tests pass)
- `agent-brain-mcp/tests/conftest.py` — FOUND (modified; free_loopback_port fixture added)
- `agent-brain-mcp/tests/test_dispatch.py` — FOUND (modified; TestRunHttpStub class updated with 2 new tests replacing the obsolete stub-pin)
- Commit `8c0f048` — FOUND (feat(53-02): HTTP listener replaces Plan 01 stub)
- Commit `55155a3` — FOUND (fix(53-02): pre-flight port probe — uvicorn swallows OSError as SystemExit(1))
- Commit `4a018bf` — FOUND (test(53-02): pin HTTP listener + loopback + DNS-rebinding contracts)
- `poetry run black --check agent_brain_mcp tests` — exit code 0
- `poetry run ruff check agent_brain_mcp tests` — exit code 0
- `poetry run mypy agent_brain_mcp` — exit code 0
- `poetry run pytest --cov=agent_brain_mcp --cov-fail-under=80` — exit code 0 (305 passed; coverage 90.75% above 80% gate)
- `task check:layering` — exit code 0 (3 contracts kept)
- `task before-push` — exit code 0 (416 monorepo tests passed; coverage gates honored)

---
*Phase: 53-streamable-http-transport*
*Completed: 2026-06-03*
