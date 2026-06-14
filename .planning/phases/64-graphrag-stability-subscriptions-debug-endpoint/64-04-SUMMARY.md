---
phase: 64-graphrag-stability-subscriptions-debug-endpoint
plan: 04
subsystem: mcp
tags: [mcp, subscriptions, debug-endpoint, starlette, http, snapshot]

# Dependency graph
requires:
  - phase: 52-resource-subscriptions
    provides: SubscriptionManager with _tasks/_last_hash registries and _truncate_session_id
  - phase: 53-streamable-http-transport
    provides: Starlette ASGI app in http.py with /healthz route and build_asgi_app

provides:
  - SubscriptionManager.snapshot() read-only introspection method with per-subscription metadata
  - GET /mcp/subscriptions debug endpoint returning JSON subscription state (no token, loopback-only)
  - Per-subscription bookkeeping: cadence_s, started_at, last_notified_at, truncated session_id

affects:
  - 65-oauth2.1 (adds auth to /mcp/subscriptions in future)
  - future operator tooling relying on subscription state inspection

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Loopback-only no-auth debug endpoint mirroring /healthz trust model"
    - "TDD with blocking-fetcher pattern for testing snapshot state without firing on_change"
    - "monotonic start time captured in build_asgi_app closure for server_uptime_s"

key-files:
  created:
    - agent-brain-mcp/tests/subscriptions/test_manager_snapshot.py
    - agent-brain-mcp/tests/test_http_subscriptions_endpoint.py
  modified:
    - agent-brain-mcp/agent_brain_mcp/subscriptions/manager.py
    - agent-brain-mcp/agent_brain_mcp/http.py

key-decisions:
  - "snapshot() returns a shallow copy of _meta values (dict(meta)) to ensure read-only contract"
  - "started_monotonic captured inside build_asgi_app closure so uptime is per-app-build, not global"
  - "Route(SUBSCRIPTIONS_PATH) registered BEFORE Mount(MCP_MOUNT_PATH) to avoid Starlette Mount shadowing"
  - "build_asgi_app accepts subscription_manager=None default for backward compat with existing callers"
  - "stdio transport has no HTTP listener: SUBSCRIPTIONS_PATH constant docstring documents this — no shim"

patterns-established:
  - "Loopback debug introspection endpoints mount alongside /healthz with same no-token trust model"
  - "_meta dict mirrors _tasks/_last_hash cleanup paths (pop in unsubscribe/cleanup_session/_poll_loop finally, clear in cleanup_all)"

requirements-completed: [HOUSE-01]

# Metrics
duration: 21min
completed: 2026-06-14
---

# Phase 64 Plan 04: Subscriptions Debug Endpoint Summary

**GET /mcp/subscriptions debug endpoint backed by SubscriptionManager.snapshot(): loopback-only no-token JSON view of active subscription state (session ids, URIs, uptime, cadence, notification timestamps)**

## Performance

- **Duration:** 21 min
- **Started:** 2026-06-14T13:46:01Z
- **Completed:** 2026-06-14T14:06:40Z
- **Tasks:** 3
- **Files modified:** 4 (2 new test files, manager.py, http.py)

## Accomplishments
- Added `SubscriptionManager.snapshot()` read-only introspection method with per-subscription metadata bookkeeping (cadence_s, started_at, last_notified_at, truncated session_id) — start_polling signature unchanged
- Wired `GET /mcp/subscriptions` route into the Starlette ASGI app (http.py) using `SUBSCRIPTIONS_PATH` constant, mounted before the `/mcp` Mount to avoid shadow; loopback-only, no token, mirrors /healthz trust model
- Documented that stdio transport has no HTTP listener so the endpoint does not exist under stdio (no shim); `task before-push` exits 0 with 556 MCP tests passing

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Add failing snapshot() tests** - `c28eecc` (test)
2. **Task 1 (GREEN): Add metadata + snapshot() to SubscriptionManager** - `f031f4e` (feat)
3. **Task 2 (RED): Add failing subscriptions endpoint tests** - `808cafc` (test)
4. **Task 2 (GREEN): Add GET /mcp/subscriptions route to Starlette app** - `bdc5612` (feat)
5. **Task 3: Documentation + validation gate** - `c16316a` (chore)

## Files Created/Modified
- `agent-brain-mcp/agent_brain_mcp/subscriptions/manager.py` - Added `_meta` dict, per-subscription metadata in `start_polling`, `last_notified_at` stamping in `_poll_loop`, `_meta.pop` in all teardown paths, `snapshot()` method
- `agent-brain-mcp/agent_brain_mcp/http.py` - Added `SUBSCRIPTIONS_PATH` constant with stdio/no-token docstring, updated `build_asgi_app` signature, added `subscriptions_debug` handler, registered route before Mount, updated `run_http` to pass manager, added to `__all__`
- `agent-brain-mcp/tests/subscriptions/test_manager_snapshot.py` - 6 TDD tests for snapshot behavior
- `agent-brain-mcp/tests/test_http_subscriptions_endpoint.py` - 6 TDD tests for the HTTP endpoint

## Decisions Made
- snapshot() returns `[dict(meta) for meta in self._meta.values()]` — shallow copy guarantees read-only contract (callers can't mutate internal metadata)
- `started_monotonic = time.monotonic()` captured inside `build_asgi_app` closure (not at module level) so uptime reflects per-ASGI-app lifetime; avoids module-level global state
- `Route(SUBSCRIPTIONS_PATH)` registered BEFORE `Mount(MCP_MOUNT_PATH)` in Starlette routes list — Starlette matches Routes before Mounts in list order, so the specific `/mcp/subscriptions` Route is found first even though `/mcp` is a prefix
- `subscription_manager: SubscriptionManager | None = None` default in `build_asgi_app` keeps backward compat with all existing callers and tests

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed Ruff import-order + mypy unused-type-ignore errors blocking task before-push**
- **Found during:** Task 3 (validation gate)
- **Issue:** Pre-existing Ruff I001 import-order violations in agent-brain-server/tests/indexing/test_graph_isolation.py, agent-brain-server/tests/services/test_indexing_graph_degradation.py, agent-brain-cli/agent_brain_cli/commands/graph.py, agent-brain-cli/agent_brain_cli/diagnostics.py, and agent-brain-cli/tests/test_diagnostics_stale_graph.py; also an unused `type: ignore[assignment,misc]` mypy error in graph.py and diagnostics.py (imported from 64-03 tasks). E501 line-too-long in test_graph_isolation.py.
- **Fix:** `ruff check --fix` auto-fixed import order; manual docstring line wrap for E501; removed unused `type: ignore` comments where mypy no longer needed them (the `None` assignment in except ImportError blocks does not require ignore suppression in current mypy)
- **Files modified:** agent-brain-server/tests/indexing/test_graph_isolation.py, agent-brain-server/tests/services/test_indexing_graph_degradation.py, agent-brain-cli/agent_brain_cli/commands/graph.py, agent-brain-cli/agent_brain_cli/diagnostics.py, agent-brain-cli/tests/test_diagnostics_stale_graph.py
- **Verification:** `task before-push` exits 0; Ruff all checks passed; mypy strict no issues
- **Committed in:** `c16316a` (chore validation gate commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 blocking)
**Impact on plan:** Fix necessary for `task before-push` to exit 0. All issues pre-existed in 64-03 output files. No scope creep for 64-04.

## Issues Encountered
- `poetry.lock` drift during `task before-push` (monorepo bootstrap side effect): the lock guard script reverts this automatically; `task before-push` exits 0 after revert — this is expected behavior documented by issue #174.

## Next Phase Readiness
- HOUSE-01 fully closed: operators can `curl http://127.0.0.1:PORT/mcp/subscriptions` to inspect live subscription state without restarting the server
- Phase 64 Success Criterion 4 is met
- Phase 65 (OAuth 2.1) will add authentication to this endpoint in a future milestone

## Self-Check: PASSED

- manager.py: FOUND
- http.py: FOUND
- test_manager_snapshot.py: FOUND
- test_http_subscriptions_endpoint.py: FOUND
- Commit c28eecc: FOUND
- Commit f031f4e: FOUND
- Commit 808cafc: FOUND
- Commit bdc5612: FOUND
- Commit c16316a: FOUND

---
*Phase: 64-graphrag-stability-subscriptions-debug-endpoint*
*Completed: 2026-06-14*
