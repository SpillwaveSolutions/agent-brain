# Plan 04: Streamable HTTP transport contract test (VAL-03)

**Phase:** 55 — Validation, contract tests & QA gate integration
**Requirements covered:** VAL-03
**Depends on:** Plan 01 (consumes contract pytest marker + teardown contract); the `_tool_matrix.py` from Plan 02 if available, otherwise duplicates a 1-tool smoke
**Parallel-safe with:** Plans 02 and 03 (different transport, different test file)
**Status:** Not started

## Goal

Drive the Streamable HTTP MCP transport end-to-end via the official SDK's
`streamablehttp_client` to confirm that `agent-brain-mcp --transport http`
serves the full initialize → tools/list → tools/call → resources/list →
resources/read flow correctly. This is the first usage of
`mcp.client.streamable_http.streamablehttp_client` in the repo — Phase 55
introduces it. Loopback-only and `--transport` rejection behavior is verified
by Phase 53's own tests; Phase 55 only asserts the happy path works via SDK.

## Acceptance Criteria

- [ ] `agent-brain-mcp/tests/contract/test_http_transport_contract.py` exists with a fixture chain that:
  - Allocates a free localhost port via `socket.bind(("127.0.0.1", 0))` then releases it (per D-11).
  - Spawns `agent-brain-mcp --transport http --port <free_port>` as a subprocess with `cwd` and `env` set so it picks up `AGENT_BRAIN_MCP_BACKEND_URL=<fake_backend>`.
  - Polls `http://127.0.0.1:<port>/health` (or the MCP HTTP `initialize` endpoint) with 0.1s interval, 10s timeout, until ready.
  - On teardown: SIGTERM → 5s → SIGKILL → orphan `pgrep` scan (same contract as Plan 01).
- [ ] Test cases (one async test each, all `@pytest.mark.contract`):
  - `test_http_initialize` — opens `streamablehttp_client(url)` → `ClientSession` → `initialize()`, asserts `serverInfo.name == "agent-brain"` and capabilities advertise `tools`, `resources`, `prompts`.
  - `test_http_tools_list_returns_16` — `await session.list_tools()` returns 16 entries.
  - `test_http_tool_call_smoke` — calls one read-only tool (recommend `server_health`) and asserts `content[0]` is `TextContent` plus `structuredContent` is a dict.
  - `test_http_resources_list_includes_v1_static` — asserts `corpus://{config,status,health,providers,folders}` present.
  - `test_http_resources_read_corpus_config` — `resources/read` on `corpus://config` returns a `contents[0]` with `mimeType == "application/json"` and a parseable JSON `text`.
- [ ] `task mcp:contract` continues to run all contract tests green in <90s wall time (HTTP startup adds ~5s, port-allocation adds ~0.1s).
- [ ] Loopback-only assertion (`--host 0.0.0.0` rejection) is **NOT** in this plan (D-10) — it belongs to Phase 53 and is verified there.

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-mcp/tests/contract/test_http_transport_contract.py` | create | 5 SDK-driven tests over Streamable HTTP, with subprocess + port-allocation fixture |
| `agent-brain-mcp/tests/contract/conftest.py` | modify | Add `mcp_http_subprocess` fixture (yields `(proc, base_url)`) and `mcp_http_session` async fixture (yields connected `ClientSession`) |

## Implementation Steps

1. Re-read `.planning/phases/53-streamable-http-transport/53-CONTEXT.md` (if available) to confirm:
   - Exact `--transport http` flag name and `--port`/`--host` flag names.
   - The HTTP server's `/health` endpoint path (or whether MCP HTTP exposes its own readiness probe).
   - Whether the v2 server uses SSE for `notifications/resources/updated` over HTTP (informs Plan 03's stdio-only scoping rationale).
2. Add to `tests/contract/conftest.py`:
   ```python
   import socket, subprocess, sys, time, pytest, pytest_asyncio
   from contextlib import closing
   from mcp.client.streamable_http import streamablehttp_client
   from mcp import ClientSession

   def _free_port() -> int:
       with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
           s.bind(("127.0.0.1", 0))
           return s.getsockname()[1]

   @pytest.fixture
   def mcp_http_subprocess(short_state_dir, fake_backend_url):
       port = _free_port()
       proc = subprocess.Popen(
           [sys.executable, "-m", "agent_brain_mcp",
            "--transport", "http", "--port", str(port), "--host", "127.0.0.1"],
           env={..., "AGENT_BRAIN_MCP_BACKEND_URL": fake_backend_url, ...},
       )
       base_url = f"http://127.0.0.1:{port}"
       _wait_ready(base_url, timeout=10.0)
       try:
           yield (proc, base_url)
       finally:
           proc.terminate()
           try: proc.wait(timeout=5)
           except subprocess.TimeoutExpired:
               proc.kill(); proc.wait()
           _assert_no_orphans()

   @pytest_asyncio.fixture
   async def mcp_http_session(mcp_http_subprocess):
       _, base_url = mcp_http_subprocess
       async with streamablehttp_client(base_url) as (read, write, _):
           async with ClientSession(read, write) as session:
               yield session
   ```
3. Write `tests/contract/test_http_transport_contract.py`:
   ```python
   import pytest

   @pytest.mark.contract
   @pytest.mark.asyncio
   async def test_http_initialize(mcp_http_session):
       result = await mcp_http_session.initialize()
       assert result.serverInfo.name == "agent-brain"
       assert result.capabilities.tools is not None
       assert result.capabilities.resources is not None

   @pytest.mark.contract
   @pytest.mark.asyncio
   async def test_http_tools_list_returns_16(mcp_http_session):
       await mcp_http_session.initialize()
       tools = await mcp_http_session.list_tools()
       assert len(tools.tools) == 16

   @pytest.mark.contract
   @pytest.mark.asyncio
   async def test_http_tool_call_smoke(mcp_http_session):
       await mcp_http_session.initialize()
       result = await mcp_http_session.call_tool("server_health", {})
       assert result.content
       assert result.content[0].type == "text"
       assert isinstance(result.structuredContent, dict)

   @pytest.mark.contract
   @pytest.mark.asyncio
   async def test_http_resources_list_includes_v1_static(mcp_http_session):
       await mcp_http_session.initialize()
       resources = await mcp_http_session.list_resources()
       uris = {r.uri for r in resources.resources}
       assert {"corpus://config", "corpus://status", "corpus://health",
               "corpus://providers", "corpus://folders"} <= uris

   @pytest.mark.contract
   @pytest.mark.asyncio
   async def test_http_resources_read_corpus_config(mcp_http_session):
       import json
       await mcp_http_session.initialize()
       result = await mcp_http_session.read_resource("corpus://config")
       assert result.contents
       assert result.contents[0].mimeType == "application/json"
       json.loads(result.contents[0].text)  # parses cleanly
   ```
4. Run `task mcp:contract` and confirm all 5 HTTP tests pass alongside Plans 02/03 contract tests.
5. Confirm port allocation is non-racy by running the suite twice back-to-back; if collisions surface, switch to ephemeral-port retries with up to 3 attempts.

## Verification

- `cd agent-brain-mcp && poetry run pytest tests/contract/test_http_transport_contract.py -v` → 5 tests pass; suite duration <15s.
- `cd agent-brain-mcp && task contract` → full contract suite (Plans 02 + 03 + 04) passes in <90s.
- Manual: `agent-brain-mcp --transport http --port 18000 --host 127.0.0.1 &` then `curl -sS http://127.0.0.1:18000/health` returns 200; SDK `streamablehttp_client("http://127.0.0.1:18000")` can `initialize()` from a `python -c` snippet.
- `ps -ef | grep agent-brain-mcp | grep -v grep` empty after `task contract` exits — fixture teardown must clean up the HTTP subprocess.
- Coverage delta: HTTP transport tests should pull in `agent_brain_mcp.server` HTTP branches not covered by stdio tests; expect a small (<2pp) coverage improvement, no regression below 80%.

## Risk Notes

- **HTTP server startup race**: `_wait_ready` must use a real socket-level probe (e.g., `httpx.get(base_url + "/health")` with retries). Don't rely on `subprocess.poll() is None` alone — the process may be up but Uvicorn not yet bound. The 10s timeout per D-09 is the budget.
- **`/health` endpoint may not exist on the MCP HTTP server**: if `agent-brain-mcp --transport http` doesn't expose `/health` (it's a Phase 53 deliverable, not a v1 endpoint), use the MCP HTTP transport's own readiness signal — try `streamablehttp_client(...)` with short retries until it succeeds. Worst case: `time.sleep(2.0)` and proceed (documented compromise).
- **Streamable HTTP SDK shape**: the `streamablehttp_client` context manager yields `(read, write, ...)` — confirm against `mcp` 1.12.x source. The third yielded value may be a metadata channel; ignore it if unused.
- **Free-port allocation TOCTOU**: between releasing the port and the subprocess binding it, another process could grab it. Mitigation: retry the whole `_free_port → spawn → _wait_ready` loop up to 3 times.
- **Subprocess env propagation**: tests must explicitly pass `PYTHONPATH` and `AGENT_BRAIN_MCP_BACKEND_URL` to the subprocess, otherwise `agent-brain-mcp` may either fail to import or call out to a real backend at localhost:8000. Inherit the parent env minus secrets, then override the backend URL.
- **Greenfield risk**: per CONTEXT.md `<code_context>`, `streamablehttp_client` has zero existing usages in the repo. This plan is the first integration; if the SDK shape differs from documentation, the Plan 01 smoke test will surface it first (consider adding an HTTP smoke variant to Plan 01 if iteration here is painful).

---
*Plan 04 of Phase 55*
