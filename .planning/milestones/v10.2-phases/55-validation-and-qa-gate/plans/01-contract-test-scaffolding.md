# Plan 01: Contract test scaffolding (Layer 2 SDK fixture chain)

**Phase:** 55 — Validation, contract tests & QA gate integration
**Requirements covered:** VAL-01 (scaffolding portion)
**Depends on:** none — first plan
**Parallel-safe with:** none (Plans 02–04 all consume this scaffolding)
**Status:** Not started

## Goal

Stand up the new `agent-brain-mcp/tests/contract/` directory with the SDK-driven
fixture chain (subprocess spawn → `mcp.ClientSession` → teardown contract) plus
a `contract` pytest marker, so Plans 02/03/04 each get a ready-to-import
fixture surface. Also extend `fake_httpx_client` in the existing
`tests/conftest.py` with the new v2 endpoints (`/query/chunk/{id}`,
`/graph/entity/{type}/{id}`, plus any defaults needed by the 9 new tools)
without breaking the Layer 1 tests. No assertions about specific tools, URIs,
subscriptions, or transports here — those belong to Plans 02–04.

## Acceptance Criteria

- [ ] `agent-brain-mcp/tests/contract/__init__.py` exists.
- [ ] `agent-brain-mcp/tests/contract/conftest.py` defines:
  - `contract` pytest marker registered in `pyproject.toml` `[tool.pytest.ini_options].markers`.
  - `mcp_stdio_session` async fixture that yields a connected `mcp.ClientSession` against `agent-brain-mcp` over stdio, using `StdioServerParameters(command=sys.executable, args=["-m", "agent_brain_mcp", "--backend", "http"])` with `AGENT_BRAIN_MCP_BACKEND_URL` pointed at the in-process FastAPI app served by the `fake_httpx_client` fixture (or a localhost stub).
  - Subprocess teardown finalizer matching `tests/e2e/conftest.py::indexed_server`: SIGTERM → 5s wait → SIGKILL → assert UDS socket path unlinked (when applicable) → `pgrep` orphan scan that fails the test if any `agent-brain-*` process survives.
- [ ] `tests/conftest.py::fake_httpx_client` `_DEFAULT_RESPONSES` dict gains entries for every new v2 path that contract tests will exercise (at minimum: `GET /query/chunk/{id}`, `GET /graph/entity/{type}/{id}`, `GET /index/folders/`, `DELETE /index/folders/`, `GET /cache/status`, `DELETE /cache/`, `GET /index/file-types/`, `POST /index/inject/`, plus any path the 9 new tools call). Each response uses the Phase 50–54 Pydantic models for shape correctness.
- [ ] A trivial smoke test `tests/contract/test_contract_smoke.py::test_initialize_over_stdio` calls `mcp_stdio_session.initialize()` and asserts `serverInfo.name == "agent-brain"` — proves the fixture chain works.
- [ ] `task mcp:contract` invokes `poetry run pytest tests/contract -v -m contract` (replacing the existing echo placeholder in `agent-brain-mcp/Taskfile.yml`).
- [ ] `poetry run pytest tests -v` (existing Layer 1 suite) stays green — no regression from the conftest changes.
- [ ] `task mcp:contract` exits 0 on the smoke test.

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-mcp/tests/contract/__init__.py` | create | Empty marker file for pytest discovery |
| `agent-brain-mcp/tests/contract/conftest.py` | create | `contract` marker registration, `mcp_stdio_session` async fixture, subprocess teardown finalizer |
| `agent-brain-mcp/tests/contract/test_contract_smoke.py` | create | One async test asserting `initialize()` succeeds + serverInfo shape — proves the chain |
| `agent-brain-mcp/tests/conftest.py` | modify | Extend `_DEFAULT_RESPONSES` with v2 endpoint stubs; do not alter existing entries |
| `agent-brain-mcp/pyproject.toml` | modify | Register `contract` marker under `[tool.pytest.ini_options].markers`; ensure `pytest-asyncio` config (`asyncio_mode = "auto"`) is set if not already |
| `agent-brain-mcp/Taskfile.yml` | modify | Replace `contract:` placeholder echo with `poetry run pytest {{.TEST_DIR}}/contract -v -m contract` |

## Implementation Steps

1. Read `agent-brain-mcp/tests/conftest.py` and `tests/e2e/conftest.py` to copy the existing `fake_httpx_client` and `indexed_server` teardown contracts verbatim — Phase 55 inherits both.
2. Create `tests/contract/__init__.py` (empty).
3. In `tests/contract/conftest.py`:
   - Import `pytest`, `pytest_asyncio`, `mcp.ClientSession`, `mcp.client.stdio.{StdioServerParameters, stdio_client}`.
   - Register `contract` marker (use `pytest_configure(config)` hook to add the marker dynamically; mirror existing `e2e` marker registration if present).
   - Define `mcp_stdio_session` as an async fixture that:
     - Spawns `agent-brain-mcp` via `StdioServerParameters` with `env={"AGENT_BRAIN_MCP_BACKEND_URL": "<stub-url>", "PYTHONPATH": "<from sys.path>"}`.
     - Wraps in `stdio_client(...)` + `ClientSession(...)`.
     - Yields the session for the test.
     - On teardown: SIGTERM, 5s wait, SIGKILL, scan `pgrep -f agent-brain-mcp` for orphans, fail the test if any survive.
   - Optional: define `mcp_http_session` analog for Plan 04, scaffolded but unused here.
4. Extend `tests/conftest.py::fake_httpx_client._DEFAULT_RESPONSES`:
   - `(GET, /query/chunk/{id})` → returns a `ChunkRecord`-shaped JSON per Phase 50 decisions.
   - `(GET, /graph/entity/{type}/{id})` → returns a `GraphEntity`-shaped JSON per Phase 50 decisions.
   - `(GET, /index/folders/)`, `(DELETE, /index/folders/)`, `(GET, /cache/status)`, `(DELETE, /cache/)`, `(GET, /index/file-types/)`, `(POST, /index/inject/)`, `(POST, /index/?force=&allow_external=)` for `add_documents`, etc.
   - Shape matches Phase 54 tool result schemas exactly.
5. Add `contract` marker to `pyproject.toml`:
   ```toml
   [tool.pytest.ini_options]
   markers = [
     "contract: SDK-driven contract tests (stdio + HTTP transports)",
     # ...existing markers
   ]
   ```
6. Write `tests/contract/test_contract_smoke.py`:
   ```python
   import pytest
   @pytest.mark.contract
   @pytest.mark.asyncio
   async def test_initialize_over_stdio(mcp_stdio_session):
       result = await mcp_stdio_session.initialize()
       assert result.serverInfo.name == "agent-brain"
   ```
7. Update `agent-brain-mcp/Taskfile.yml::contract` to:
   ```yaml
   contract:
     desc: SDK-driven contract tests (stdio + HTTP, Phase 55)
     deps: [install]
     cmds:
       - poetry run pytest {{.TEST_DIR}}/contract -v -m contract
   ```
8. Run `task mcp:test` and `task mcp:contract` to confirm both pass.

## Verification

- `cd agent-brain-mcp && poetry run pytest tests -v` → all existing tests green (no regression from `_DEFAULT_RESPONSES` additions).
- `cd agent-brain-mcp && task contract` → smoke test passes; subprocess teardown completes cleanly (no orphan `agent-brain-mcp` processes survive).
- `ps -ef | grep agent-brain-mcp | grep -v grep` immediately after teardown returns empty.
- `task before-push` from repo root continues to pass (Plan 04 adds MCP/UDS to it; this plan must not break the current root gate).

## Risk Notes

- **macOS sockaddr_un limit (104 bytes)**: subprocess `cwd=` and any UDS path the contract fixture writes must inherit the `short_state_dir` pattern from `tests/e2e/conftest.py`. If `mcp_stdio_session` uses a tmpdir, mkdtemp under `/tmp/abmcp-contract-*`.
- **pytest-asyncio mode**: if the package isn't already configured for `asyncio_mode = "auto"`, fixtures using `async def` will silently no-op. Verify the existing async tests (`test_e2e_stdio.py`) pattern before assuming.
- **`fake_httpx_client` regression**: extending `_DEFAULT_RESPONSES` is additive but mistyped paths or wrong JSON shapes will silently break Plan 02 tests downstream. Cross-check every new entry against the Phase 54 tool's expected response shape.
- **No `agent_brain_mcp` `__main__` entrypoint?**: if `python -m agent_brain_mcp` doesn't exist yet, use `StdioServerParameters(command="agent-brain-mcp", ...)` and rely on the installed console script. Verify before locking on `-m`.
- **No `tests/contract/` precedent**: this plan literally creates the directory. If pytest collection picks up something unexpected, narrow the `Taskfile.yml::contract` cmd to `tests/contract/test_*.py` explicitly.

---
*Plan 01 of Phase 55*
