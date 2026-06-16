---
phase: 69-mcphttpbackend-client-side-oauth-dance
plan: "02"
subsystem: agent-brain-mcp
tags: [oauth, loopback, browser, callback-server, tdd, python]
dependency_graph:
  requires:
    - 69-01-SUMMARY.md  # FileTokenStorage — used alongside these handlers in OAuthClientProvider
  provides:
    - build_redirect_handler callable (opens browser + stderr fallback)
    - LoopbackCallbackServer (OS-assigned ephemeral port, captures code+state)
    - build_callback_handler callable wrapping LoopbackCallbackServer
  affects:
    - 69-03-PLAN.md  # Wave-2 McpHttpBackend _http_session factory consumes all three exports
tech_stack:
  added:
    - stdlib http.server (HTTPServer + BaseHTTPRequestHandler) for loopback callback
  patterns:
    - asyncio.to_thread to run blocking handle_request() without blocking event loop
    - _OAuthHTTPServer subclass carries typed oauth_code/oauth_state attrs (mypy-clean)
    - Injectable opener/stream params for test isolation (no webbrowser.open in tests)
key_files:
  created:
    - agent-brain-mcp/agent_brain_mcp/oauth/oauth_handlers.py
    - agent-brain-mcp/tests/test_oauth_loopback_handlers.py
  modified:
    - agent-brain-mcp/agent_brain_mcp/oauth/__init__.py
decisions:
  - "Used stdlib http.server (no new dependency) per Decision C discretion note"
  - "_OAuthHTTPServer subclass instead of type: ignore[attr-defined] on HTTPServer for clean mypy"
  - "build_redirect_handler swallows all opener exceptions (OSError and beyond) so headless CI never crashes"
  - "Port 0 binding: OS assigns free ephemeral port; redirect_uri is fixed at __init__ time before the dance"
metrics:
  duration: "~21 minutes"
  completed: "2026-06-16T23:54:00Z"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
  tests_added: 15
  tests_total_passing: 954
---

# Phase 69 Plan 02: Redirect Handler + Loopback Callback Server Summary

**One-liner:** Ephemeral-port loopback callback server (stdlib http.server, OS-assigned port) + injectable browser redirect handler for OAuthClientProvider; 15 TDD tests, mypy strict clean, before-push exits 0.

## What Was Built

### `agent_brain_mcp/oauth/oauth_handlers.py` (net-new)

Three public symbols that satisfy the two callable shapes the MCP SDK `OAuthClientProvider` requires:

1. **`build_redirect_handler(opener, stream)`** — returns `async def _handler(url) -> None` that:
   - Prints `"Open this URL to authorize:\n{url}\n"` to `stream` (default `sys.stderr`) as headless fallback.
   - Calls `opener(url)` (default `webbrowser.open`); swallows all exceptions so missing-browser never crashes the dance.

2. **`class LoopbackCallbackServer`** — binds `_OAuthHTTPServer("127.0.0.1", 0)` so the OS assigns a free ephemeral port:
   - `port: int` and `redirect_uri: str` (`http://127.0.0.1:<port>/callback`) are readable immediately after `__init__` — BEFORE the dance starts, so DCR registers the correct URI.
   - `wait_for_callback() -> tuple[str, str | None]` runs `handle_request()` via `asyncio.to_thread` (non-blocking), then returns `(code, state)`. Raises `RuntimeError` if code is absent.
   - Context manager (`__enter__`/`__exit__`) calls `close()` / `server_close()`.
   - `_OAuthHTTPServer` subclass carries `oauth_code: str | None` and `oauth_state: str | None` as typed instance attrs — avoids `type: ignore[attr-defined]` and satisfies mypy strict.
   - Request handler silences Apache-style log noise (`log_message` no-op).
   - Response body includes "Authentication complete -- you may close this tab." (200) or an error page (400) if code is missing.

3. **`build_callback_handler(server)`** — returns `async def _handler() -> tuple[str, str | None]` that delegates to `server.wait_for_callback()`.

### `agent_brain_mcp/oauth/__init__.py` (modified — append only)

Added imports and `__all__` entries for the three new symbols. `FileTokenStorage` from Plan 01 is preserved unchanged.

## TDD Execution

**RED commit:** `edd0fbb` — 15 failing tests covering port binding, redirect_uri shape, code+state capture, no-state-returns-None, missing-code-raises, redirect handler opener/stream injection, OSError swallowing, stderr default, build_callback_handler delegation, and package exports.

**GREEN commit:** `de93f17` — implementation; all 15 tests pass.

**FIX commit:** `bc3bcee` — Ruff (I001 import sort, UP007 Optional->|, UP006 Tuple->tuple, UP035 typing->collections.abc, E501 line), mypy (_OAuthHTTPServer typed subclass replaces two `# type: ignore[attr-defined]` suppressions), Black reformat.

## Verification

### Acceptance Criteria

All criteria pass:

- `grep "def build_redirect_handler" agent-brain-mcp/agent_brain_mcp/oauth/oauth_handlers.py` -- matches
- `grep "class LoopbackCallbackServer" agent-brain-mcp/agent_brain_mcp/oauth/oauth_handlers.py` -- matches
- `grep "def build_callback_handler" agent-brain-mcp/agent_brain_mcp/oauth/oauth_handlers.py` -- matches
- `grep "/callback" agent-brain-mcp/agent_brain_mcp/oauth/oauth_handlers.py` -- matches
- `grep -E "HTTPServer\(.*0\)|server_address\[1\]" agent-brain-mcp/agent_brain_mcp/oauth/oauth_handlers.py` -- matches
- `grep "webbrowser" agent-brain-mcp/agent_brain_mcp/oauth/oauth_handlers.py` -- matches
- `poetry run pytest tests/test_oauth_loopback_handlers.py` -- 15 passed

### Quality Gate

`task before-push` (from repo root): **exits 0**
- 954 MCP tests passed, 111 deselected, 0 failures
- Black, Ruff, mypy strict all clean across server/cli/uds/mcp packages

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Typed HTTPServer subclass for mypy compliance**
- **Found during:** Task 2 (quality gate)
- **Issue:** Assigning `Optional[str]` type annotations to non-self attributes on `http.server.HTTPServer` (foreign object) caused `mypy [misc]: Type cannot be declared in assignment to non-self attribute`.
- **Fix:** Introduced `_OAuthHTTPServer(http.server.HTTPServer)` subclass with `oauth_code: str | None` and `oauth_state: str | None` as properly typed `__init__` attrs. Handler uses `isinstance(self.server, _OAuthHTTPServer)` guard before writing.
- **Files modified:** `agent_brain_mcp/oauth/oauth_handlers.py`
- **Commit:** `bc3bcee`

**2. [Rule 3 - Blocking] Ruff UP007/UP006/UP035/I001 errors from Python-3.10+ type syntax enforcement**
- **Found during:** Task 2 (quality gate)
- **Issue:** Project ruff config enforces modern union syntax (`X | Y` instead of `Optional[X]`/`Union[X,Y]`), lowercase `tuple` instead of `Tuple`, `collections.abc` instead of `typing` for `Awaitable`/`Callable`, and sorted import blocks.
- **Fix:** Rewrote all type hints in `oauth_handlers.py` to use `str | None`, `tuple[str, str | None]`, `Callable[[str], bool] | None`, imported `Awaitable`/`Callable` from `collections.abc`, fixed import block sort.
- **Files modified:** `agent_brain_mcp/oauth/oauth_handlers.py`, `agent_brain_mcp/tests/test_oauth_loopback_handlers.py`
- **Commit:** `bc3bcee`

## Commits

| Hash | Type | Description |
|------|------|-------------|
| `edd0fbb` | test | TDD RED: 15 failing tests for loopback handlers |
| `de93f17` | feat | TDD GREEN: oauth_handlers.py + __init__.py exports |
| `bc3bcee` | fix | Ruff/mypy/black quality gate fixes |

## Integration Notes for Plan 69-03

The Wave-2 factory (`McpHttpBackend._http_session()`) imports these symbols from `agent_brain_mcp.oauth`:

```python
from agent_brain_mcp.oauth import (
    LoopbackCallbackServer,
    build_callback_handler,
    build_redirect_handler,
)
```

Usage pattern:

```python
with LoopbackCallbackServer() as loopback:
    # loopback.redirect_uri is now fixed -- pass to OAuthClientMetadata.redirect_uris
    auth_provider = OAuthClientProvider(
        server_url=self.url,
        client_metadata=OAuthClientMetadata(
            redirect_uris=[AnyUrl(loopback.redirect_uri)],
            ...
        ),
        storage=FileTokenStorage(self._state_dir),
        redirect_handler=build_redirect_handler(),
        callback_handler=build_callback_handler(loopback),
    )
```
