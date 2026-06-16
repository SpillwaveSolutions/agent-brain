---
phase: 68-per-tool-scope-enforcement
plan: "02"
subsystem: auth
tags: [oauth, scopes, mcp, middleware, asgi, jwt, dispatch, http-403]

requires:
  - phase: 68-01
    provides: "TOOL_SCOPE_REQUIREMENTS (16 entries), require_scope(), InsufficientScopeError"
  - phase: 67-co-located-as-rs-middleware
    provides: "AuthenticationMiddleware sets scope['user'] (AccessToken); BearerAuthBackend; RequireAuthMiddleware"
  - phase: 66-oauth-design
    provides: "PRM/OASM well-known routes mounted outside auth middleware; _OAUTH_SCOPES in http.py"

provides:
  - "server.py: _enforce_scope() defense-in-depth at call_tool/read_resource/get_prompt/handle_subscribe"
  - "http.py: ScopeEnforcementMiddleware — pre-dispatch ASGI guard returning real HTTP 403 with RFC 9396 WWW-Authenticate"
  - "tests/test_tool_scope_enforcement.py: 61 acceptance tests proving SC1/SC2/SC3, mode-gating, Phase 66 regression"

affects:
  - phase-70-split-as-rs
  - OAUTH-06 (token endpoint — now has enforcement infrastructure)

tech-stack:
  added: []
  patterns:
    - "Pre-dispatch ASGI body buffering: ScopeEnforcementMiddleware reads and replays body before calling app so the MCP lowlevel server sees an unmodified stream"
    - "Two-layer defense: HTTP middleware emits real 403 (SC#2/SC#3); server.py _enforce_scope catches stdio/in-process callers that bypass HTTP stack"
    - "ASGI middleware composition order: AuthenticationMiddleware OUTERMOST (sets scope['user']), then RequireAuthMiddleware, then ScopeEnforcementMiddleware, then mcp_asgi_app — outer runs first"

key-files:
  created:
    - agent-brain-mcp/tests/test_tool_scope_enforcement.py
  modified:
    - agent-brain-mcp/agent_brain_mcp/server.py
    - agent-brain-mcp/agent_brain_mcp/http.py

key-decisions:
  - "Pre-dispatch ASGI guard (not handler exception): MCP lowlevel server wraps all handler exceptions as JSON-RPC errors in HTTP 200 — scope errors raised inside dispatch NEVER produce HTTP 403; guard must buffer body and short-circuit before dispatch"
  - "Middleware composition fix (Rule 1 auto-fix): plan's locked order had RequireAuthMiddleware OUTSIDE AuthenticationMiddleware — ASGI outer runs first, so scope['user'] was unset; swapped to Auth outermost"
  - "handle_unsubscribe not guarded: no-op teardown per MCP spec; subscription already required subscribe scope at subscribe time"
  - "Unknown tool name → None (pass-through): ScopeEnforcementMiddleware returns None for tools not in TOOL_SCOPE_REQUIREMENTS, letting dispatch return INVALID_PARAMS — avoids false 403 on unknown names"
  - "MutableMapping[str, Any] return type on replay_receive: Starlette's Receive Callable returns MutableMapping, not dict — mypy strict required the looser type"

patterns-established:
  - "Body buffering pattern: read full body into bytes, build replay coroutine that pops from list, forward replay to downstream app — reusable for any pre-dispatch ASGI guard"
  - "RFC 9396 WWW-Authenticate emission: Bearer error='insufficient_scope', scope='<required>', resource_metadata='<PRM URL>'"

requirements-completed: [OAUTH-06]

duration: 90min
completed: 2026-06-16
---

# Phase 68 Plan 02: Dispatch-Layer Scope Enforcement Summary

**Pre-dispatch ASGI ScopeEnforcementMiddleware in http.py emitting real HTTP 403 with RFC 9396 WWW-Authenticate, plus _enforce_scope defense-in-depth in server.py for stdio/in-process paths, validated by 61 acceptance tests**

## Performance

- **Duration:** 90 min
- **Started:** 2026-06-16T20:00:00Z
- **Completed:** 2026-06-16T21:30:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Added `_enforce_scope(server, required)` helper to `server.py` — mode-gated to oauth, reads `request.user.scopes` via `server.request_context`, calls `require_scope()`; wired at `call_tool` (per TOOL_SCOPE_REQUIREMENTS), `read_resource`, `get_prompt`, and `handle_subscribe`
- Added `ScopeEnforcementMiddleware` to `http.py` — buffers JSON-RPC body, maps method+params.name to required scope, checks `scope["user"].scopes` set by upstream `AuthenticationMiddleware`, emits HTTP 403 with RFC 9396 `WWW-Authenticate: Bearer error="insufficient_scope", scope="<required>", resource_metadata="<PRM>"` header; passes through `initialize`, `tools/list`, and unknown tool names
- Fixed critical middleware composition bug (Rule 1 auto-fix): corrected `AuthenticationMiddleware` to be outermost (ASGI outer runs first), so `scope["user"]` is populated before `RequireAuthMiddleware` and `ScopeEnforcementMiddleware` read it
- Shipped 61 acceptance tests: SC1 (read token + 9 read tools pass), SC2 (read token + 4 index tools = 403), SC3 (read token + 3 admin tools = 403), `_enforce_scope` unit tests, `_send_403` emission unit tests, resource/prompt gates, mode-gating (none/basic = no-op), Phase 66 mount-order regression (PRM/OASM/healthz still 200)
- `task before-push` exits 0: 916 passed, 0 regressions, Black/Ruff/mypy strict clean

## Task Commits

1. **Task 1: _enforce_scope defense-in-depth** - `d519030` (feat)
2. **Task 2: ScopeEnforcementMiddleware pre-dispatch guard** - `a794aef` (feat)
3. **Task 3: 61 acceptance tests** - `ed4c0c6` (test)

## Files Created/Modified

- `agent-brain-mcp/agent_brain_mcp/server.py` — _enforce_scope() helper + 4 call sites (modified)
- `agent-brain-mcp/agent_brain_mcp/http.py` — ScopeEnforcementMiddleware class + corrected middleware composition (modified)
- `agent-brain-mcp/tests/test_tool_scope_enforcement.py` — 61-test acceptance suite (new)

## Decisions Made

- **Pre-dispatch ASGI guard (not handler exception):** The MCP lowlevel server (`mcp/server/lowlevel/server.py` ~line 785) catches ALL handler exceptions and wraps them as JSON-RPC errors inside HTTP 200. Scope errors raised inside `call_tool` or any other dispatch handler never produce HTTP 403. The guard buffers the request body and short-circuits with a real HTTP 403 BEFORE handing off to the MCP ASGI app.
- **Middleware composition fix:** The plan's locked composition had `RequireAuthMiddleware` outside `AuthenticationMiddleware`. In ASGI, outer middleware runs first; `RequireAuthMiddleware` was checking `scope["user"]` before `AuthenticationMiddleware` ever set it, so every request returned 401. Fixed by making `AuthenticationMiddleware` outermost. Phase 67 tests never caught this because they only tested "no token → 401" (which returns 401 regardless of order) and exempt routes.
- **handle_unsubscribe not guarded:** MCP spec treats unsubscribe as teardown — the subscription already required `agent-brain:subscribe` scope at subscribe time. Guarding unsubscribe would prevent cleanup.
- **Unknown tool → pass-through (not 403):** `ScopeEnforcementMiddleware._required_scope()` returns `None` for tool names not in `TOOL_SCOPE_REQUIREMENTS`. The request passes through to dispatch, which returns INVALID_PARAMS (JSON-RPC error, HTTP 200). Prevents false 403 on typos or future tools before the SOT is updated.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Middleware composition order: RequireAuthMiddleware was outside AuthenticationMiddleware**

- **Found during:** Task 2 (ScopeEnforcementMiddleware integration testing)
- **Issue:** Plan's locked middleware composition had `RequireAuthMiddleware(AuthenticationMiddleware(...))` — outer-before-inner ASGI semantics meant `RequireAuthMiddleware` ran BEFORE `AuthenticationMiddleware` set `scope["user"]`, so every request returned 401 (including valid-token requests that should have gotten 403 for insufficient scope)
- **Fix:** Swapped to `AuthenticationMiddleware(RequireAuthMiddleware(ScopeEnforcementMiddleware(mcp_asgi_app)))` — Auth outermost (runs first, populates `scope["user"]`), then scope check
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/http.py`
- **Commit:** `a794aef`

**2. [Rule 2 - Type] `replay_receive` return type: dict → MutableMapping**

- **Found during:** Task 2 (mypy strict check)
- **Issue:** Starlette's `Receive` type is `Callable[[], Awaitable[MutableMapping[str, Any]]]`; the replay coroutine returned `dict[str, Any]` which fails mypy strict
- **Fix:** Changed messages list and `replay_receive` return type to `MutableMapping[str, Any]`; added `from collections.abc import AsyncIterator, MutableMapping` import
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/http.py`
- **Commit:** `a794aef`

## Issues Encountered

- Black reformatted test file after initial write; Ruff found 9 E501 violations (long docstrings) that required manual shortening — corrected before commit

## User Setup Required

None — pure code change. Set `AGENT_BRAIN_AUTH=oauth` to engage enforcement (none/basic modes unchanged).

## Next Phase Readiness

- OAuth 2.1 per-tool scope enforcement is now complete: HTTP 403 with RFC 9396 headers on insufficient scope, defense-in-depth in server.py for stdio paths
- Phase 70 (split AS/RS) can reuse `ScopeEnforcementMiddleware` as-is — it reads `scope["user"]` (set by whatever Authentication middleware is in place)
- `_enforce_scope` in server.py is mode-gated and verifier-agnostic

---
*Phase: 68-per-tool-scope-enforcement*
*Completed: 2026-06-16*
