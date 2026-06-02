# Plan 03: SDK round-trip smoke + Taskfile + USER_GUIDE update

**Phase:** 53 — Streamable HTTP transport
**Requirements covered:** HTTP-01 (full proof via official MCP SDK HTTP client), HTTP-02 (negative-path bind tests), HTTP-03 (no-silent-fallback negative tests)
**Depends on:** Plan 02 (drives Plan 02's listener via the SDK)
**Parallel-safe with:** none (extends Taskfile and tests; nothing else parallel-safe within Phase 53)
**Status:** Not started

## Goal

Prove HTTP-01/02/03 end-to-end against the official MCP Python SDK's Streamable HTTP client. Drive `tools/list`, `resources/list`, `prompts/list`, and one `tools/call` over HTTP and assert the v1-equivalent surface (7 tools / 5 resources / 6 prompts) is identical to stdio. Add the `task mcp:smoke:http` Taskfile target so quick-start scripts and Phase 55's `task before-push` integration can drive an HTTP round-trip locally. Document the new flag in `agent-brain-mcp/README.md` and the two-axis (`backend transport` vs `listen transport`) model in `docs/USER_GUIDE.md` so operators don't conflate the MCP HTTP listener with the backend `--backend http` setting or with #179's Bearer-token middleware.

## Acceptance Criteria

- [ ] A new test file `tests/test_transport_selection.py` runs `agent-brain-mcp --transport http` as a subprocess (uvicorn on `127.0.0.1:<free-port>`), drives an `initialize` → `tools/list` → `resources/list` → `prompts/list` → `tools/call server_health` round-trip via `mcp.client.streamable_http.streamablehttp_client`, and asserts the v1 surface counts (7 tools, 5 resources, 6 prompts).
- [ ] A new test file `tests/test_http_loopback.py` (e2e-marked) runs the subprocess listener and asserts the bound socket address is `127.0.0.1:<port>` (not `0.0.0.0`, not any non-loopback). Uses `psutil.Process(pid).net_connections()` or `lsof -p <pid> -i` to inspect the actual bound interface. Skips on platforms where the inspection isn't available; runs in CI on macOS + linux.
- [ ] A new test file `tests/test_http_negative_paths.py` runs subprocesses and asserts:
  - `--transport bogus` exits non-zero with Click's standard message.
  - `--transport http --host 0.0.0.0` exits non-zero before binding with the contract message.
  - `--transport http --port <occupied>` exits with code `2` and the port-in-use message.
  - Stdio default (no `--transport`) still passes the existing stdio smoke (regression check).
- [ ] The `serverInfo._meta` block returned by `initialize` over HTTP carries both `agentBrainBackendTransport` (existing) and `agentBrainListenTransport: "http"`. (This validates Plan 01's `build_server` parameter additions over the wire — the public contract.)
- [ ] The `tools/list` set over HTTP exactly matches the `tools/list` set over stdio (parameterized test asserts symmetric difference is empty). Same for `resources/list` and `prompts/list`. No subscription-related entries appear (HTTP-03 / D-18 — Phase 53 must not assume Phase 52 has landed).
- [ ] `task mcp:smoke:http` in `agent-brain-mcp/Taskfile.yml` runs the new HTTP smoke test (`pytest tests/test_transport_selection.py -v -m e2e_http`). Sibling to the existing stdio smoke task.
- [ ] `agent-brain-mcp/README.md` has a new section "Transport selection" documenting `--transport`, `--host`, `--port`, the loopback-only posture, and the explicit no-auth warning (mirrors Plan 02's startup banner). Includes a copy-pasteable example: `agent-brain-mcp --transport http --port 8765`.
- [ ] `docs/USER_GUIDE.md` has a new subsection "MCP transport axes" with the two-axis diagram: `[MCP client] —listen transport— [agent-brain-mcp] —backend transport— [agent-brain-serve]`. Names #179 explicitly as backend-axis only; states MCP HTTP listener auth is v4 / OAUTH-01.
- [ ] `cd agent-brain-mcp && poetry run pytest -v -m "not e2e and not e2e_http"` (default fast path) still excludes the new e2e_http suite — the `addopts = "-m 'not e2e'"` line in `pyproject.toml` is extended to `addopts = "-m 'not e2e and not e2e_http'"`. The new `e2e_http` marker is registered in `[tool.pytest.ini_options].markers`.
- [ ] `cd agent-brain-mcp && task mcp:smoke:http` exits 0 on a clean working tree.
- [ ] `cd agent-brain-mcp && poetry run black . && poetry run ruff check . && poetry run mypy agent_brain_mcp && poetry run pytest` exits 0 (default fast path — e2e_http excluded).

## Files to Touch

| File                                                          | Action  | Notes |
|---------------------------------------------------------------|---------|-------|
| `agent-brain-mcp/tests/test_transport_selection.py`           | create  | The HTTP-01 round-trip proof using `mcp.client.streamable_http.streamablehttp_client`. Asserts v1 surface symmetry vs stdio. Marked `@pytest.mark.e2e_http`. |
| `agent-brain-mcp/tests/test_http_loopback.py`                 | create  | Subprocess-based loopback bind assertion. Marked `@pytest.mark.e2e_http`. |
| `agent-brain-mcp/tests/test_http_negative_paths.py`           | create  | Subprocess-based negative tests for bogus transport, non-loopback host, port-in-use. Marked `@pytest.mark.e2e_http` for the subprocess ones. Some negative tests (like `--transport bogus` which doesn't actually start a server) can run in fast lane without the marker. |
| `agent-brain-mcp/tests/conftest.py`                           | modify  | Add `mcp_http_subprocess(port, *, transport="http", host="127.0.0.1")` fixture that yields a running subprocess and tears it down (SIGINT → wait → SIGKILL fallback). Reuses Plan 02's `free_loopback_port` fixture. |
| `agent-brain-mcp/pyproject.toml`                              | modify  | Add `e2e_http` marker to `[tool.pytest.ini_options].markers`. Update `addopts` to `"-m 'not e2e and not e2e_http'"`. |
| `agent-brain-mcp/Taskfile.yml`                                | modify  | Add `mcp:smoke:http` task that runs `poetry run pytest tests/test_transport_selection.py -v -m e2e_http`. Add `mcp:smoke:all` umbrella task that runs both stdio and http smoke. |
| `agent-brain-mcp/README.md`                                   | modify  | Add "Transport selection" section. Reference the design doc filed in Phase 50. Include copy-pasteable example. |
| `docs/USER_GUIDE.md`                                          | modify  | Add "MCP transport axes" subsection under the existing MCP section. Two-axis diagram in mermaid or ASCII. State auth is v4. |
| `agent-brain-mcp/tests/test_smoke.py`                         | modify  | (Optional) add one assertion that `serverInfo._meta.agentBrainListenTransport == "stdio"` on the stdio path, mirroring the HTTP assertion. Keeps the contract symmetric. |

## Implementation Steps

1. **Verify the SDK HTTP client import.** `cd agent-brain-mcp && poetry run python -c "from mcp.client.streamable_http import streamablehttp_client; print('ok')"`. If absent at the resolved SDK version, file a one-line note and STOP — escalate (Risk #1 in 53-PLAN.md applies to the client side too).
2. **Add `e2e_http` marker to `pyproject.toml`:**
   ```toml
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   asyncio_mode = "auto"
   markers = [
       "e2e: end-to-end test requiring a real agent-brain-serve subprocess and the official MCP Python SDK as client (slow; opt-in via `task mcp:e2e`)",
       "e2e_http: end-to-end test requiring an agent-brain-mcp subprocess in HTTP transport mode (slow; opt-in via `task mcp:smoke:http`)",
   ]
   addopts = "-m 'not e2e and not e2e_http'"
   ```
3. **Add `mcp_http_subprocess` fixture to `conftest.py`:**
   ```python
   import os
   import signal
   import subprocess
   import sys
   import time
   from contextlib import contextmanager

   import httpx
   import pytest


   @contextmanager
   def _mcp_subprocess(port: int, *, host: str = "127.0.0.1", transport: str = "http", extra_env: dict[str, str] | None = None):
       env = {**os.environ, **(extra_env or {})}
       proc = subprocess.Popen(
           [sys.executable, "-m", "agent_brain_mcp.cli",
            "--transport", transport, "--host", host, "--port", str(port)],
           env=env,
           stdout=subprocess.PIPE,
           stderr=subprocess.PIPE,
       )
       try:
           # Wait for /healthz to answer (max 5s).
           deadline = time.time() + 5.0
           url = f"http://{host}:{port}/healthz"
           while time.time() < deadline:
               try:
                   r = httpx.get(url, timeout=0.5)
                   if r.status_code == 200:
                       break
               except httpx.HTTPError:
                   pass
               time.sleep(0.1)
           else:
               proc.terminate()
               raise RuntimeError(
                   f"MCP HTTP listener did not become ready at {url}: "
                   f"stderr={proc.stderr.read().decode(errors='replace')}"
               )
           yield proc
       finally:
           if proc.poll() is None:
               proc.send_signal(signal.SIGINT)
               try:
                   proc.wait(timeout=3.0)
               except subprocess.TimeoutExpired:
                   proc.kill()
                   proc.wait()


   @pytest.fixture
   def mcp_http_subprocess(free_loopback_port):
       def _factory(*, host: str = "127.0.0.1", transport: str = "http", extra_env=None):
           return _mcp_subprocess(free_loopback_port, host=host, transport=transport, extra_env=extra_env)
       return _factory
   ```
4. **Write `tests/test_transport_selection.py`** (the HTTP-01 round-trip):
   ```python
   @pytest.mark.e2e_http
   async def test_http_round_trip_lists_v1_surface(mcp_http_subprocess, free_loopback_port):
       with mcp_http_subprocess() as proc:
           url = f"http://127.0.0.1:{free_loopback_port}/mcp"
           async with streamablehttp_client(url) as (read, write, _):
               async with ClientSession(read, write) as session:
                   init_result = await session.initialize()
                   tools = (await session.list_tools()).tools
                   resources = (await session.list_resources()).resources
                   prompts = (await session.list_prompts()).prompts
                   health = await session.call_tool("server_health", {})

           # v1 surface symmetry — no Phase 52 / 54 surface yet.
           tool_names = {t.name for t in tools}
           assert tool_names == {
               "search_documents", "query_count", "index_folder",
               "get_job", "list_jobs", "cancel_job", "server_health",
           }
           assert len(resources) == 5
           assert len(prompts) == 6
           # Both transport labels surface in _meta.
           meta = init_result.serverInfo.meta or {}
           assert meta.get("agentBrainListenTransport") == "http"
           assert "agentBrainBackendTransport" in meta
           # Tool call worked.
           assert health.structuredContent is not None
   ```
   The assertion of the v1 surface counts is load-bearing for HTTP-03 / D-18 — proves Phase 53 doesn't accidentally pull in unfinished Phase 52 / 54 surface.
5. **Write `tests/test_http_loopback.py`** (HTTP-02 proof):
   ```python
   @pytest.mark.e2e_http
   def test_http_listener_bound_to_loopback_only(mcp_http_subprocess, free_loopback_port):
       import psutil  # add to pyproject [tool.poetry.group.dev.dependencies] if not present
       with mcp_http_subprocess() as proc:
           p = psutil.Process(proc.pid)
           bound = [c for c in p.net_connections(kind="tcp") if c.status == "LISTEN"]
           assert bound, "MCP HTTP listener did not bind any TCP socket"
           for conn in bound:
               assert conn.laddr.ip in ("127.0.0.1", "::1"), (
                   f"Listener bound to non-loopback interface: {conn.laddr}"
               )
   ```
   Add `psutil = "^6.0"` to `[tool.poetry.group.dev.dependencies]` in `pyproject.toml` if not already present.
6. **Write `tests/test_http_negative_paths.py`** (HTTP-03 proof):
   ```python
   def test_bogus_transport_rejected_by_click():
       result = subprocess.run(
           [sys.executable, "-m", "agent_brain_mcp.cli", "--transport", "bogus"],
           capture_output=True, text=True,
       )
       assert result.returncode != 0
       assert "not one of" in result.stderr.lower() or "not one of" in result.stdout.lower()

   def test_non_loopback_host_rejected_before_bind():
       result = subprocess.run(
           [sys.executable, "-m", "agent_brain_mcp.cli",
            "--transport", "http", "--host", "0.0.0.0"],
           capture_output=True, text=True,
           timeout=10.0,
       )
       assert result.returncode != 0
       assert "loopback only" in (result.stderr + result.stdout).lower() or "must be one of" in (result.stderr + result.stdout).lower()

   @pytest.mark.e2e_http
   def test_port_in_use_exits_code_2(free_loopback_port):
       # Hold the port open in this process.
       s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
       s.bind(("127.0.0.1", free_loopback_port))
       s.listen(1)
       try:
           result = subprocess.run(
               [sys.executable, "-m", "agent_brain_mcp.cli",
                "--transport", "http", "--port", str(free_loopback_port)],
               capture_output=True, text=True, timeout=10.0,
           )
           assert result.returncode == 2, f"Expected exit 2, got {result.returncode}: {result.stderr}"
           assert "already in use" in (result.stderr + result.stdout).lower()
       finally:
           s.close()
   ```
   Note: the negative test for non-loopback host MAY run without the e2e_http marker because it never actually binds — it errors before reaching uvicorn. The port-in-use test needs the marker because the listener does briefly attempt to bind.
7. **Add `mcp:smoke:http` to `Taskfile.yml`** alongside the existing stdio smoke (search the existing Taskfile for `mcp:e2e` and `mcp:test` for the pattern):
   ```yaml
   mcp:smoke:http:
     desc: Run the HTTP transport round-trip smoke (drives the official MCP SDK HTTP client)
     deps: [install]
     cmds:
       - poetry run pytest {{.TEST_DIR}}/test_transport_selection.py {{.TEST_DIR}}/test_http_loopback.py {{.TEST_DIR}}/test_http_negative_paths.py -v -m e2e_http
   ```
   Add an umbrella `mcp:smoke:all` that runs both stdio and http smokes. The existing root `Taskfile.yml` does NOT need to change in Phase 53 — VAL-04 / Phase 55 folds the new tasks into root `task before-push`.
8. **Update `agent-brain-mcp/README.md`.** Locate the existing Quick Start section. Add a new "Transport selection" section AFTER quick start, BEFORE the "Configuration" section:
   ```markdown
   ## Transport selection

   `agent-brain-mcp` supports two listen transports for talking to MCP clients:

   - **stdio** (default) — Claude Desktop, Claude Code, and most MCP CLI clients use this. No config needed.
   - **http** (Streamable HTTP, v10.2+) — for IDE clients and framework adapters that prefer HTTP/SSE.

   ### stdio (default)
   ```bash
   agent-brain-mcp
   ```

   ### Streamable HTTP
   ```bash
   agent-brain-mcp --transport http --host 127.0.0.1 --port 8765
   ```

   Connect with the MCP SDK HTTP client at `http://127.0.0.1:8765/mcp`.

   **Loopback only:** `--host` accepts only `127.0.0.1`, `localhost`, or `::1`. v10.2 (MCP v2) ships no authentication on the HTTP transport — authentication is reserved for MCP v4 (OAuth 2.1). Do not expose the port to non-loopback interfaces.

   **No silent fallback:** Invalid `--transport` values, non-loopback hosts, and port-in-use errors fail loudly with no fallback to stdio or to a different port.

   Health probe: `curl http://127.0.0.1:8765/healthz`.

   See `docs/plans/2026-06-XX-mcp-v2-subscriptions.md` (filed in Phase 50) for the full design.
   ```
9. **Update `docs/USER_GUIDE.md`.** Locate the existing MCP section. Add a new "## MCP transport axes" subsection:
   ```markdown
   ## MCP transport axes

   Agent Brain's MCP integration has TWO orthogonal transport axes:

   ```
   ┌─────────────┐  listen transport   ┌──────────────────┐  backend transport  ┌──────────────────┐
   │ MCP client  │ ──────────────────▶ │ agent-brain-mcp  │ ──────────────────▶ │ agent-brain-serve │
   │ (Claude,    │   --transport       │ (MCP server)     │   --backend         │ (FastAPI / UDS)  │
   │  SDK, IDE)  │   {stdio, http}     │                  │   {auto, http, uds} │                  │
   └─────────────┘                     └──────────────────┘                     └──────────────────┘
   ```

   The two axes are independent:

   - `--transport` controls how MCP clients reach `agent-brain-mcp` (stdio pipe vs Streamable HTTP).
   - `--backend` controls how `agent-brain-mcp` reaches `agent-brain-serve` (HTTP localhost vs UDS socket).

   **Authentication:** Neither axis has authentication in v10.2 (MCP v2). The MCP HTTP listen transport binds loopback only and is unauthenticated; auth is reserved for MCP v4 (OAuth 2.1, tracked as [OAUTH-01](https://github.com/SpillwaveSolutions/agent-brain/issues/188)). The optional Bearer-token middleware on `agent-brain-serve` (issue #179) is a separate, **backend-axis** concern; when it lands, `agent-brain-mcp`'s backend httpx client passes the token through, but the MCP listen transport itself remains unauthenticated until v4.

   **Local trust model:** Any process running as the same user can reach `127.0.0.1:8765` and drive MCP tools. Do not run `agent-brain-mcp --transport http` on a shared / multi-user host without external sandboxing.
   ```
10. **Run all checks.** `cd agent-brain-mcp && poetry run black . && poetry run ruff check . && poetry run mypy agent_brain_mcp && poetry run pytest` exits 0 (fast path). Then `task mcp:smoke:http` exits 0 (slow path; opt-in).

## Verification

- **HTTP round-trip via SDK:** `cd agent-brain-mcp && task mcp:smoke:http` exits 0; verbose output lists the 7 v1 tools, 5 resources, 6 prompts under the HTTP transport.
- **Loopback bind verified:** the `test_http_listener_bound_to_loopback_only` test passes — actual socket inspection confirms `127.0.0.1`.
- **Negative paths:** `pytest tests/test_http_negative_paths.py -v` (with `-m e2e_http` for the port-in-use case) all pass; exit codes match the contract (Click's default for `bogus`, custom `2` for port-in-use).
- **No silent fallback regression:** the stdio default suite (`pytest tests/test_smoke.py tests/test_e2e_stdio.py`) still passes — HTTP additions did not perturb stdio.
- **Fast path stays fast:** `cd agent-brain-mcp && poetry run pytest` (default `addopts`) excludes both `e2e` and `e2e_http` markers; runs under 30 seconds.
- **Docs accurate:** manual review of `README.md` Transport selection section and `USER_GUIDE.md` "MCP transport axes" subsection — copy-pasteable commands work, the two-axis diagram is unambiguous.
- **Curl health probe:** with the server running, `curl -s http://127.0.0.1:8765/healthz` returns `{"status":"ok","transport":"http"}`.

## Risk Notes

- **`streamablehttp_client` API shape** — the MCP SDK's HTTP client wrapper is at `mcp.client.streamable_http.streamablehttp_client`. Its yield tuple may evolve between SDK versions (the third element is currently a session-id callback / opaque object; v1.12.0's exact shape is `(read_stream, write_stream, session_id_factory)`). Step 4's example uses `(read, write, _)` — if the SDK adds a fourth element, adjust the unpacking. Defensive: use `* _trailing` to absorb extras (`async with streamablehttp_client(url) as (read, write, *_):`).
- **psutil as a dev dep** — small footprint, MIT-licensed; widely available across CI platforms. If a constraint emerges (e.g. cross-platform CI matrix can't install it), fall back to `lsof -p <pid>` parsing on macOS / linux only and skip on other platforms — but psutil is preferable.
- **Subprocess test flakiness** — the 5-second deadline for `/healthz` readiness should be plenty (uvicorn cold start is < 1s in practice), but on overloaded CI runners it may sporadically time out. Mitigation: bump to 10s if first run flakes; capture stderr in the timeout error so failures are diagnosable.
- **`mcp:smoke:http` is NOT yet in root `task before-push`** — that's VAL-04 / Phase 55. Phase 53 ships the per-package task only; Phase 55 wires it into the root QA gate. Plan 03's verification step does NOT require `task before-push` to pass — it requires `task mcp:smoke:http` (per-package) to pass.
- **`docs/USER_GUIDE.md` may have a different file layout than assumed** — verify the existing MCP section's location before editing. If `USER_GUIDE.md` doesn't have an MCP section yet (per the v10.1.2 standalone MCP user guide referenced in commit `cf7a364`), add the transport-axes content to the standalone MCP user guide at `docs/MCP_USER_GUIDE.md` (or wherever the standalone guide lives — verify path via `find docs -iname '*mcp*guide*'` before editing).
- **`build_server()` deprecation warning surfaces in tests** — Plan 01's `DeprecationWarning` on the legacy `transport=` kwarg may appear in pytest output for any test still using the old call shape. If pytest is configured with `-W error::DeprecationWarning`, those tests will fail. Plan 03's optional `test_smoke.py` update (`serverInfo._meta.agentBrainListenTransport == "stdio"`) is the right place to silence the warning by migrating `test_smoke.py`'s `build_server(...)` call to the new kwargs. The full sweep across tests is a Phase 55 cleanup, but the most prominent call site can be migrated in Plan 03.

---
*Plan 03 of Phase 53*
