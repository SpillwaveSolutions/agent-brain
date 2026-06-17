---
phase: 69-mcphttpbackend-client-side-oauth-dance
plan: "03"
subsystem: mcp-client-oauth
tags: [oauth, mcp-http-backend, refactor, auth-injection, client-side]
dependency_graph:
  requires: ["69-01", "69-02"]
  provides: ["OAUTH-07"]
  affects: ["McpHttpBackend", "transport.py", "oauth_client.py"]
tech_stack:
  added:
    - "OAuthClientProvider (mcp.client.auth.oauth2) — httpx.Auth implementation driving PKCE dance"
    - "_http_session() async context manager — single streamablehttp_client seam with auth="
  patterns:
    - "Lazy-import inside function (deferred-import pattern preserved)"
    - "Opt-in env var default OFF (AGENT_BRAIN_MCP_AUTH=oauth activates)"
    - "Provider lazy-once per McpHttpBackend instance (_auth_provider cache)"
key_files:
  created:
    - "agent-brain-mcp/agent_brain_mcp/oauth/oauth_client.py (build_oauth_client_provider factory)"
    - "agent-brain-mcp/tests/test_mcp_http_backend_oauth.py (5 unit tests)"
  modified:
    - "agent-brain-mcp/agent_brain_mcp/oauth/__init__.py (export build_oauth_client_provider + CLIENT_SCOPES)"
    - "agent-brain-mcp/agent_brain_mcp/client.py (MCP_CLIENT_AUTH_ENV + _get_auth + _http_session + 17 refactored methods)"
    - "agent-brain-cli/agent_brain_cli/client/transport.py (thread state_dir into McpHttpBackend http branch)"
decisions:
  - "DCR path (no client_metadata_url): co-located AS supports DCR; local CLI cannot host CIMD HTTPS doc"
  - "auth=None default preserves pre-Phase-69 byte-identical path when AGENT_BRAIN_MCP_AUTH is unset"
  - "Single _http_session() CM: all 17 former per-method sites centralised; one seam for auth injection"
  - "Provider cached once per McpHttpBackend instance (_auth_provider) for Pattern A reuse within invocation"
  - "McpStdioBackend untouched: OAuth applies to HTTP transport only (stdio_client path unchanged)"
metrics:
  duration: "21 minutes"
  completed: "2026-06-17T00:20:02Z"
  tasks_completed: 3
  tasks_total: 3
  files_created: 2
  files_modified: 4
requirements: [OAUTH-07]
---

# Phase 69 Plan 03: McpHttpBackend OAuth Wiring Summary

**One-liner:** OAuth 2.1 client dance wired into McpHttpBackend via a single `_http_session()` CM with `auth=` injection, DCR + full scope union, and `FileTokenStorage`-keyed `OAuthClientProvider` behind an `AGENT_BRAIN_MCP_AUTH=oauth` opt-in.

## What Was Built

Three moving parts assembled into a complete client-side OAuth 2.1 integration:

### Task 1: Factory (`oauth_client.py`)

`build_oauth_client_provider(server_url, state_dir)` assembles:
- `LoopbackCallbackServer()` bound eagerly so the OS-assigned port is known for DCR
- `OAuthClientMetadata(redirect_uris=[server.redirect_uri], scope="agent-brain:read agent-brain:index agent-brain:admin")`
- `FileTokenStorage(state_dir)` — persists token + client_info at `state_dir/mcp-oauth-tokens.json` (0o600)
- `build_redirect_handler()` + `build_callback_handler(server)` — browser + loopback UX
- `OAuthClientProvider(server_url, metadata, storage, redirect, callback, timeout=300.0)` — DCR path, no `client_metadata_url`

All SDK imports inside the function body (deferred-import pattern preserved).

### Task 2: Centralization + opt-in + threading

**client.py additions:**
- `MCP_CLIENT_AUTH_ENV = "AGENT_BRAIN_MCP_AUTH"` (module constant, mirrors server's `AGENT_BRAIN_AUTH`)
- `__init__`: `self._state_dir`, `self._oauth_enabled = env == "oauth"`, `self._auth_provider: Any | None = None`
- `_get_auth()`: returns `None` (default OFF) or lazily-built `OAuthClientProvider` (cached per instance); raises `RuntimeError` if OAuth ON but `state_dir` is `None`
- `_http_session()`: single `@asynccontextmanager` calling `streamablehttp_client(self.url, auth=self._get_auth())`, yielding an initialized `ClientSession`
- All 17 `_async_*` methods refactored to `async with self._http_session() as session:` (removed per-method lazy imports)

**transport.py change:**
- `McpHttpBackend(url=mcp_target, timeout=timeout, state_dir=state_dir)` — `state_dir` now threaded through so `FileTokenStorage` is keyed to the project directory

**Tests (5 cases):**
1. Unset env → `_get_auth()` returns `None`
2. Non-"oauth" values → `None`
3. `AGENT_BRAIN_MCP_AUTH=oauth` + `state_dir` → `httpx.Auth` instance, same object on second call (caching)
4. OAuth ON + `state_dir=None` → `RuntimeError` matching `AGENT_BRAIN_MCP_AUTH=oauth`
5. `inspect.getsource(client).count("streamablehttp_client(") == 1` — structural guard

### Task 3: Quality gate

Fixed Black/Ruff/mypy issues introduced by the refactor:
- Ruff UP037: removed string quotes from type annotations (now using `TYPE_CHECKING` block)
- Ruff I001: sorted imports in test file
- mypy: removed unused `type: ignore` on `_get_auth`; added typed intermediate vars for `model_dump()` calls

## Acceptance Criteria Verification

| Criterion | Status |
|-----------|--------|
| `grep -c "streamablehttp_client(" client.py` == 1 | PASS |
| `grep "_http_session" client.py` ≥ 18 times | PASS (19) |
| `grep "auth=auth" client.py` matches | PASS |
| `grep "AGENT_BRAIN_MCP_AUTH" client.py` matches | PASS |
| `grep "state_dir=state_dir" transport.py` at http branch | PASS |
| `stdio_client` count unchanged in client.py | PASS (29) |
| test: `inspect.getsource(client).count("streamablehttp_client(") == 1` | PASS |
| test: `_get_auth()` returns SAME provider on 2nd call | PASS |
| All 5 new OAuth tests pass | PASS |
| `task before-push` exits 0 | PASS (959+577+1388+32 tests) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stale Phase 59 comment referenced streamablehttp_client(self.url)**
- **Found during:** Task 2 — updating comments to not inflate grep count
- **Issue:** A block comment in the Phase 59 section header included the literal string `streamablehttp_client(self.url)` which would make `grep -c "streamablehttp_client("` report more than 1
- **Fix:** Updated stale comment to reference `_http_session()` instead
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/client.py`
- **Commit:** 7c21446

**2. [Rule 1 - Bug] Two docstrings also included `streamablehttp_client(self.url)` literal**
- **Found during:** Task 2 — checking grep -c result after refactor
- **Issue:** Class and method docstrings inherited the old literal text
- **Fix:** Paraphrased to "17 former per-method transport call sites"
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/client.py`
- **Commit:** 7c21446

**3. [Rule 2 - Missing] Typed intermediate variables for model_dump() calls**
- **Found during:** Task 3 — mypy reported `no-any-return` on two `_async_*` methods
- **Issue:** `result.model_dump(mode="json", exclude_none=False)` returns `Any` in mypy strict mode; assigned typed vars needed
- **Fix:** Added `dumped: dict[str, Any] = result.model_dump(...)` before return in `_async_get_prompt` and `_async_read_resource`
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/client.py`
- **Commit:** ed4cec2

## Self-Check: PASSED

- FOUND: agent-brain-mcp/agent_brain_mcp/oauth/oauth_client.py
- FOUND: agent-brain-mcp/tests/test_mcp_http_backend_oauth.py
- FOUND commit 77381af (Task 1 factory)
- FOUND commit 7c21446 (Task 2 centralization)
- FOUND commit ed4cec2 (Task 3 quality gate)
