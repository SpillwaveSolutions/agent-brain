# Plan 02: HTTP listener implementation + loopback enforcement + /healthz

**Phase:** 53 — Streamable HTTP transport
**Requirements covered:** HTTP-01 (full — actual listener), HTTP-02 (full — loopback-only bind with no-auth banner)
**Depends on:** Plan 01 (consumes the dispatch stub and the new `--host` / `--port` Click options)
**Parallel-safe with:** none (extends `server.py` and may add `http.py` module; both also touched by Plan 01)
**Status:** Not started

## Goal

Replace Plan 01's `NotImplementedError` stub with a working `run_http()` that mounts an MCP Streamable HTTP listener via the MCP SDK's `StreamableHTTPSessionManager` and serves it via in-process uvicorn. Enforce loopback-only bind by whitelisting `--host` to `{127.0.0.1, localhost, ::1}` at startup. Add a `/healthz` Starlette route returning `{"status": "ok", "transport": "http"}` so operators can curl-check the listener without driving the full MCP handshake. Emit a startup banner that explicitly states the loopback-only / no-auth posture so operators see the warning in their logs. After this plan lands, `agent-brain-mcp --transport http` is a fully working, testable HTTP MCP listener. Plan 03 layers the SDK-driven round-trip smoke on top.

## Acceptance Criteria

- [ ] `agent-brain-mcp --transport http` starts a Streamable HTTP MCP listener on `127.0.0.1:8765`, logs a startup banner naming the bind address, mount path (`/mcp`), and the no-auth warning, then runs until SIGINT.
- [ ] The startup banner string contains, literally: `MCP server listening on http://127.0.0.1:<port>/mcp (loopback only, no auth — do NOT expose this port)`.
- [ ] `curl http://127.0.0.1:<port>/healthz` returns HTTP 200 with body `{"status": "ok", "transport": "http"}` (Content-Type `application/json`).
- [ ] `agent-brain-mcp --transport http --host 0.0.0.0` exits non-zero before binding, with the exact error message: `--host must be one of {127.0.0.1, localhost, ::1} (auth is deferred to v4; binding to public interfaces is unsafe in v2)`.
- [ ] `agent-brain-mcp --transport http --host 10.0.0.5` (or any other non-loopback host) also rejects with the same message.
- [ ] `agent-brain-mcp --transport http --host localhost` and `--host ::1` are accepted (alongside the default `127.0.0.1`).
- [ ] Port-in-use (`OSError` with errno 48 on macOS / 98 on Linux) caught at the uvicorn `serve()` call site and re-raised as `click.ClickException("Port {port} already in use. Pass --port <free-port> or stop the conflicting process.")` with exit code 2. NO fallback to a random port. NO fallback to stdio.
- [ ] Stdio failure paths do NOT fall back to HTTP (D-13 — unchanged from Plan 01; reasserted by a regression test in this plan).
- [ ] Backend unreachable does NOT prevent HTTP listener startup (D-14). If the backend is down, the HTTP listener still binds; per-request `BackendUnavailable` errors surface via the existing `errors.raise_backend_unavailable` mapping. (Existing behavior on stdio is preserved on HTTP.)
- [ ] The same `build_server(httpx_client, backend_transport=..., listen_transport="http")` factory drives both transports — no duplicate server construction logic between `run_stdio` and `run_http`.
- [ ] DNS-rebinding protection is verifiably enabled when bound to a loopback host: the MCP SDK auto-enables `TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"], allowed_origins=["http://127.0.0.1:*", ...])` per the SDK ref at `mcp/server/fastmcp/server.py:177-183`. Plan 02 does NOT override this — verified by test.
- [ ] `python -c "import uvicorn"` works in the MCP package's venv (transitive via SDK). If it does NOT, add `uvicorn = "^0.32"` to `pyproject.toml` as a direct dep and re-run `task install`.
- [ ] `cd agent-brain-mcp && poetry run black . && poetry run ruff check . && poetry run mypy agent_brain_mcp && poetry run pytest` exits 0.
- [ ] After SIGINT (Ctrl-C in interactive terminal, or `os.kill(pid, SIGINT)` in tests), the HTTP server drains, the httpx client closes, and the process exits cleanly with code 0. No leaked sockets.

## Files to Touch

| File                                                       | Action  | Notes |
|------------------------------------------------------------|---------|-------|
| `agent-brain-mcp/agent_brain_mcp/http.py`                  | create  | New module: `validate_loopback_host(host) -> None`, `build_asgi_app(server) -> ASGIApp`, `async def run_http(server, *, host, port) -> None`. Keep `server.py` lean. |
| `agent-brain-mcp/agent_brain_mcp/server.py`                | modify  | Replace the `NotImplementedError` stub from Plan 01 with `from .http import run_http`. Keep `run_stdio` co-located with `build_server`. |
| `agent-brain-mcp/agent_brain_mcp/cli.py`                   | modify  | Wrap the `asyncio.run(main_async(...))` call in a `try/except click.ClickException` so port-in-use surfaces cleanly with exit code 2 (Click handles the exit if we re-raise within Click's own dispatch — verify by reading `main()`'s structure and using `raise` from within `main_async`). |
| `agent-brain-mcp/pyproject.toml`                           | modify  | **Conditionally:** if `python -c "import uvicorn"` fails in the venv after `poetry install`, add `uvicorn = "^0.32"` to `[tool.poetry.dependencies]`. Re-run `poetry lock --no-update` and `poetry install`. |
| `agent-brain-mcp/tests/test_loopback_enforcement.py`       | create  | Unit tests for `validate_loopback_host()` — accept `127.0.0.1` / `localhost` / `::1`; reject `0.0.0.0`, `10.0.0.5`, `example.com`, empty string, `127.0.0.2`. Error message matches the exact contract. |
| `agent-brain-mcp/tests/test_http_listener.py`              | create  | Integration tests using `httpx.AsyncClient`: start `run_http()` in a task on an ephemeral port via `--port 0` is NOT supported (D-12 forbids dynamic ports) — use `socket.socket().bind(("127.0.0.1", 0))` then close to find a free port; pass that to `run_http`. Assert (a) `/healthz` returns 200 + correct body; (b) `/mcp` accepts a POST and gives a session-id; (c) listener actually bound to `127.0.0.1` via `sock.getsockname()`; (d) port-in-use raises `click.ClickException` with the contract message. |
| `agent-brain-mcp/tests/test_dns_rebinding.py`              | create  | Single test: build the `StreamableHTTPSessionManager` with the same args `run_http` uses; introspect the resulting transport security to assert DNS rebinding protection is on and allowed_hosts is the SDK default loopback list. Defensive pin against silent SDK regression (Risk #3). |
| `agent-brain-mcp/tests/conftest.py`                        | modify  | Add a `free_loopback_port()` helper fixture that opens `socket.AF_INET` on `127.0.0.1:0`, reads `getsockname()[1]`, closes, returns the port. Used by `test_http_listener.py`. |

## Implementation Steps

1. **Confirm uvicorn availability.** `cd agent-brain-mcp && poetry run python -c "import uvicorn; print(uvicorn.__version__)"`. If ImportError, add `uvicorn = "^0.32"` to `pyproject.toml` and re-install. Document in plan output (so Phase 50's RFC tracking captures whether this was a direct or transitive add).
2. **Create `agent_brain_mcp/http.py`** with module structure:
   ```python
   """Streamable HTTP listener for the MCP server (Phase 53)."""
   from __future__ import annotations

   import logging
   from typing import Final

   import click
   import uvicorn
   from mcp.server.lowlevel import Server
   from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
   from starlette.applications import Starlette
   from starlette.responses import JSONResponse
   from starlette.routing import Mount, Route

   logger = logging.getLogger(__name__)

   ALLOWED_LOOPBACK_HOSTS: Final[frozenset[str]] = frozenset({"127.0.0.1", "localhost", "::1"})
   MCP_MOUNT_PATH: Final[str] = "/mcp"
   HEALTHZ_PATH: Final[str] = "/healthz"


   def validate_loopback_host(host: str) -> None:
       """Reject any --host outside the loopback whitelist (HTTP-02)."""
       if host not in ALLOWED_LOOPBACK_HOSTS:
           raise click.ClickException(
               "--host must be one of {127.0.0.1, localhost, ::1} "
               "(auth is deferred to v4; binding to public interfaces is unsafe in v2)"
           )


   def build_asgi_app(server: Server) -> Starlette:
       """Compose the Starlette app: /mcp (MCP SDK) + /healthz."""
       session_manager = StreamableHTTPSessionManager(
           app=server,
           event_store=None,
           json_response=False,
           stateless=False,
       )

       async def healthz(_request):  # type: ignore[no-untyped-def]
           return JSONResponse({"status": "ok", "transport": "http"})

       async def lifespan(_app):  # type: ignore[no-untyped-def]
           async with session_manager.run():
               yield

       return Starlette(
           routes=[
               Route(HEALTHZ_PATH, healthz, methods=["GET"]),
               Mount(MCP_MOUNT_PATH, app=session_manager.handle_request),
           ],
           lifespan=lifespan,
       )


   async def run_http(server: Server, *, host: str, port: int) -> None:
       """Serve the MCP server over Streamable HTTP on host:port (loopback only)."""
       validate_loopback_host(host)
       app = build_asgi_app(server)
       config = uvicorn.Config(
           app,
           host=host,
           port=port,
           log_level="info",
           lifespan="on",
       )
       uvi_server = uvicorn.Server(config)
       logger.info(
           "MCP server listening on http://%s:%d%s (loopback only, no auth "
           "— do NOT expose this port)",
           host,
           port,
           MCP_MOUNT_PATH,
       )
       try:
           await uvi_server.serve()
       except OSError as e:
           # EADDRINUSE — macOS errno 48, Linux errno 98.
           if e.errno in (48, 98):
               raise click.ClickException(
                   f"Port {port} already in use. Pass --port <free-port> "
                   "or stop the conflicting process."
               ) from e
           raise
   ```
   Note the exact ASGI mounting shape — `Mount("/mcp", app=session_manager.handle_request)`. Verify against the SDK source at `mcp/server/fastmcp/server.py:950 streamable_http_app` (the SDK's own pattern) before finalizing. If the SDK exposes a different attribute (e.g. `streamable_http_app` or `handle_streamable_http`), match exactly.
3. **Wire `run_http` into `server.py`.** Replace Plan 01's stub:
   ```python
   from .http import run_http  # re-export so callers can import either path
   ```
   Leave the public name `run_http` reachable from `agent_brain_mcp.server` for Plan 01's tests that already import it from there.
4. **Verify Click exit code 2 path.** In `cli.py`, ensure `click.ClickException` raised inside `main_async` propagates up through `asyncio.run` and is caught by Click's outer dispatch. Click's default behavior on `ClickException` is to print the message and exit with the exception's `exit_code` (default 1). To force exit code 2 (per D-12), in `http.py`'s `run_http`, instead of `raise click.ClickException(...)`, raise a custom subclass with `exit_code = 2`:
   ```python
   class PortInUseError(click.ClickException):
       exit_code = 2
   ```
   Define `PortInUseError` at module top and use it in the `EADDRINUSE` branch. Verify by running `agent-brain-mcp --transport http --port <occupied>` and checking `$?` is `2`.
5. **Pass `listen_transport="http"` from `main_async`.** In `server.py:main_async`, the existing Plan 01 change passes `listen_transport=transport` to `build_server`. Verify this still holds; no change in Plan 02.
6. **Write `tests/test_loopback_enforcement.py`** (sync, pure unit, no async):
   - Parameterize accept cases: `127.0.0.1`, `localhost`, `::1` → no raise.
   - Parameterize reject cases: `0.0.0.0`, `10.0.0.5`, `example.com`, ``, `127.0.0.2` → `click.ClickException` raised with the exact contract message (regex match against the literal string).
7. **Write `tests/test_http_listener.py`** (async, uses `httpx.AsyncClient`):
   - Fixture: `free_loopback_port()` from conftest.
   - Test 1 — `/healthz` round-trip: start `run_http` in a task with a stubbed `Server` (use the real `build_server` with a mock httpx client; no backend calls in this test). Wait until the port is reachable (`httpx.AsyncClient.get("/healthz")` with short retries — 100ms × 20). Assert 200 + JSON body. Cancel the task; assert clean shutdown.
   - Test 2 — `/mcp` initialize: send a POST to `/mcp` with a minimal MCP `initialize` JSON-RPC envelope (use `mcp.types.InitializeRequest` to build it). Assert a 200 response with a `Mcp-Session-Id` header. NB: this is a thin "does the route mount" check — the full SDK-driven handshake is in Plan 03's e2e.
   - Test 3 — bound to loopback: after `run_http` starts, walk `uvi_server.servers[0].sockets[0].getsockname()` and assert `[0] == "127.0.0.1"`. (The fixture stashes the `uvicorn.Server` instance via test plumbing — see test code.)
   - Test 4 — port in use: bind a sibling socket on a port. Call `run_http(..., port=occupied_port)`. Assert `PortInUseError` raised with `exit_code == 2` and the contract message.
   - Test 5 — invalid host: call `run_http(..., host="0.0.0.0")` directly. Assert `click.ClickException` with the contract message; never reaches `uvicorn.Server.serve()`.
   - Test 6 — clean shutdown: start `run_http`, send SIGINT to the event loop's task (use `task.cancel()`), assert the httpx client is closed and no `ResourceWarning` is emitted (`pytest.warns` does NOT warn on `ResourceWarning`).
8. **Write `tests/test_dns_rebinding.py`** — defensive pin:
   ```python
   def test_session_manager_loopback_security_is_default():
       from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
       # Instantiate exactly as run_http does.
       mgr = StreamableHTTPSessionManager(app=..., event_store=None, json_response=False, stateless=False)
       # Read the SDK's auto-enabled transport security defaults.
       # (Introspection path: check StreamableHTTPSessionManager._transport_security or
       # the equivalent attr — verify against SDK source before finalizing.)
       # Assert: dns_rebinding_protection enabled, allowed_hosts is the loopback set.
   ```
   The exact introspection path depends on SDK internals. If the SDK does NOT expose this from the manager (only from `FastMCP`), simplify Test 8 to a smoke that asserts `StreamableHTTPSessionManager` can be constructed with the v2 args without raising — Risk #3 is then mitigated by Phase 55's SDK contract sweep instead. Document the simplification in the test docstring.
9. **Add `free_loopback_port()` to `conftest.py`:**
   ```python
   import socket
   import pytest

   @pytest.fixture
   def free_loopback_port() -> int:
       """Return a free TCP port on 127.0.0.1, then close the probe socket."""
       s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
       s.bind(("127.0.0.1", 0))
       port = s.getsockname()[1]
       s.close()
       return port
   ```
10. **Run the quality gate locally** (same as Plan 01 step 9). Fix any failures. Specifically watch for:
    - mypy strict mode complaints on Starlette's `_request` type — annotate `_request: Request | None` or add to the existing `[[tool.mypy.overrides]]` block for `agent_brain_mcp.http`.
    - ruff B008 (mutable default arg) — not applicable here but check the `lifespan` async generator pattern; if ruff complains, mark `# noqa: B008` with a reason.
    - Tests using `asyncio.create_task` should always `await task` or `task.cancel()` — use `pytest-asyncio`'s loop fixture for proper teardown.

## Verification

- **Listener boots:** `cd agent-brain-mcp && poetry run agent-brain-mcp --transport http --port 8765 &` (background). Then:
  - `curl -i http://127.0.0.1:8765/healthz` → 200, JSON `{"status":"ok","transport":"http"}`.
  - `pkill -f "agent-brain-mcp --transport http"` cleanly stops.
- **Invalid host rejected:** `poetry run agent-brain-mcp --transport http --host 0.0.0.0 2>&1 | grep -q "loopback only"` (exit non-zero).
- **Port-in-use:** in one terminal, `python -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',9999)); input()"`. In another, `poetry run agent-brain-mcp --transport http --port 9999; echo $?` → exits with `2` and prints "Port 9999 already in use".
- **Banner present:** `poetry run agent-brain-mcp --transport http 2>&1 | grep "loopback only, no auth"`.
- **Stdio unchanged:** `poetry run pytest tests/test_smoke.py tests/test_e2e_stdio.py -v` passes.
- **New tests pass:** `poetry run pytest tests/test_loopback_enforcement.py tests/test_http_listener.py tests/test_dns_rebinding.py -v` passes.
- **Per-package gate:** `cd agent-brain-mcp && poetry run black --check . && poetry run ruff check . && poetry run mypy agent_brain_mcp && poetry run pytest` exits 0.

## Risk Notes

- **`StreamableHTTPSessionManager.handle_request` may not be the exact attribute name** — the SDK could expose this via a different interface (e.g. `Mount("/mcp", app=session_manager)` if the manager is itself ASGI-callable). Step 2's note to verify against SDK source is mandatory. If the wiring shape differs, adjust `build_asgi_app` accordingly — the public Plan 02 contract is "POST /mcp speaks Streamable HTTP MCP", not a specific Python signature.
- **Lifespan handling:** Starlette's lifespan generator pattern with `session_manager.run()` is the SDK's documented pattern (per `mcp/server/fastmcp/server.py:streamable_http_app`). If the SDK pattern shifts to `async with manager`, mirror it. Lifespan errors (e.g. session manager fails to start) currently propagate as uvicorn startup failures — they exit non-zero with the underlying traceback. That's fine for Plan 02; richer error mapping is Phase 55.
- **Test 8 (`test_dns_rebinding`) may be fragile:** SDK internals can change. The test is defensive — if it starts breaking after an SDK bump, demote to a smoke (per step 8's documented fallback) rather than block on it. The actual loopback enforcement is in `validate_loopback_host` (tested in `test_loopback_enforcement.py`), which is the production guarantee.
- **In-process uvicorn vs subprocess:** D-06 commits to in-process. If a future risk emerges (e.g. uvicorn signal handling conflicts with the existing asyncio loop), the fallback is `subprocess.Popen([sys.executable, "-m", "uvicorn", ...])` — but not in Phase 53. Document if encountered as a Phase 55 follow-up.
- **Coverage on `http.py`:** the per-package pytest gate's 80% coverage threshold (per `Taskfile.yml:144`) applies. The tests in this plan should cover `validate_loopback_host` fully, `build_asgi_app` via the listener tests, and `run_http`'s happy + port-in-use paths. The lifespan teardown and uvicorn's internal `serve()` error paths are not directly testable — mark as `# pragma: no cover` if coverage falls below threshold.

---
*Plan 02 of Phase 53*
