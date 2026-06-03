---
phase: 52-resource-subscriptions
plan: 02
subsystem: mcp
tags: [mcp, subscriptions, capabilities, asyncio, agent_brain_mcp, mcp-sdk]

# Dependency graph
requires:
  - phase: 52-resource-subscriptions
    provides: Plan 01's SubscriptionManager + SubscribableUriRejected + canonical_hash + DEFAULT_DROP_KEYS public surface (locked)
  - phase: 51-uri-schemes-and-templates
    provides: PARAMETERIZED_SCHEMES + parameterized URI handlers (server.py read_resource() trailing-slash normalization pattern)
provides:
  - SubscriptionPolicy Protocol + empty SUBSCRIPTION_POLICIES registry + resolve_policy() exact-then-scheme lookup helper
  - @server.subscribe_resource() and @server.unsubscribe_resource() handlers in build_server()
  - resources.subscribe capability flipped to True via get_capabilities wrapper (MCP SDK 1.12.x hardcodes False; no upstream knob)
  - server._subscription_manager private-attr workaround for cleanup hook (Plan 04 will refactor to tuple return)
  - SubscribableUriRejected reasons extended: unknown_uri | not_subscribable | duplicate_subscribe
affects: [52-03-per-uri-policies, 52-04-disconnect-cleanup, 54-04-wait-for-job, 55-04-streamable-http-e2e]

# Tech tracking
tech-stack:
  added: []  # no new dependencies — uses Plan 01's surface + existing MCP SDK + stdlib
  patterns:
    - "URI normalization helper (_normalize_uri) shared between read_resource and subscribe paths"
    - "Subscribable-URI gate via two-step lookup: known-URI registry then per-URI policy"
    - "get_capabilities wrapper to flip SDK-hardcoded subscribe=False to True"
    - "Per-handler duplicate-subscribe pre-check to surface RuntimeError as McpError"
    - "Stub-policy via monkeypatch.setitem(SUBSCRIPTION_POLICIES, ...) for additive test fixtures"
    - "In-memory test harness via mcp.shared.memory.create_connected_server_and_client_session — inlined per test to avoid anyio task-group cross-task lifecycle issue"

key-files:
  created:
    - agent-brain-mcp/agent_brain_mcp/subscriptions/policies.py
    - agent-brain-mcp/tests/test_subscribe_handler.py
  modified:
    - agent-brain-mcp/agent_brain_mcp/server.py
    - agent-brain-mcp/agent_brain_mcp/subscriptions/__init__.py
    - agent-brain-mcp/tests/test_initialize.py
    - agent-brain-mcp/tests/e2e/test_e2e_resources.py

key-decisions:
  - "MCP SDK 1.12.x hardcodes resources.subscribe=False at mcp/server/lowlevel/server.py:211 with no opt-in knob on NotificationOptions and no derivation from _subscribe_resource_handler presence. Plan 02 flips it via a server.get_capabilities wrapper installed inside build_server(). The wrapper is the surgical fix until upstream exposes a capability flag; documented inline in build_server with line-number reference to the SDK source. NotificationOptions.resources_changed is independent and stays False — opting into listChanged is a separate future scope."
  - "Subscribable allowlist is implemented as a TWO-step check: (1) _is_known_uri rejects URIs outside RESOURCE_REGISTRY + PARAMETERIZED_SCHEMES with SubscribableUriRejected(reason='unknown_uri'); (2) resolve_policy returns None for known-but-non-subscribable URIs (e.g., corpus://config, chunk://, graph-entity://, file://) which produces SubscribableUriRejected(reason='not_subscribable'). Order matters — clients distinguish 'we don't know that scheme' from 'we know it but you can't subscribe'."
  - "Duplicate subscribe is pre-checked at the wire handler via manager.is_subscribed() rather than letting manager.start_polling raise RuntimeError. This produces SubscribableUriRejected(reason='duplicate_subscribe') with the proper -32602 error code and structured data; the bare RuntimeError from Plan 01 never reaches the MCP wire. Phase 52 CONTEXT decision A picks strict rejection so the polling-task lifecycle stays deterministic."
  - "Manager ownership: server._subscription_manager is the Plan 02 short-term shape (private attribute on the Server instance). Plan 04 will refactor build_server() to return (server, manager) so run_stdio's finally block can call manager.cleanup_all() without poking the private attr. Picked the private-attr path per the plan's recommendation — keeps the Plan 02 diff small and lets Plan 04 introduce the refactor cleanly."
  - "policies.py registry key shape: exact URI string (corpus://status) OR scheme prefix ending in '://' (job://). resolve_policy tries exact first, then scheme-prefix. This keeps Plan 03 lookup deterministic — an exact-URI entry always wins over a scheme entry — without forcing every job id to be pre-registered. Pinned by test_exact_uri_policy_wins_over_scheme."
  - "SubscriptionPolicy is a runtime_checkable Protocol (not an ABC). Plan 03's concrete policies will be plain dataclasses that happen to satisfy the Protocol; structural typing keeps the test stub class (_StubPolicy) lightweight (no inheritance required for monkeypatch.setitem fixtures)."
  - "Test pattern: integration tests INLINE the async with create_connected_server_and_client_session block rather than pulling it into a pytest_asyncio.fixture. Wrapping the harness in a fixture trips anyio's cancel-scope guard ('Attempted to exit cancel scope in a different task than it was entered in') because fixture enter/exit cross task boundaries. Documented as a comment in TestSubscribeHandlerDispatch — future contributors will hit the same trap if they refactor."
  - "Tests that leave subscriptions active MUST call manager.cleanup_all() before the in-memory harness exits. The polling task spawned by start_polling lives until cancelled; without explicit cleanup, the task lingers past the event-loop teardown and emits 'Task was destroyed but it is pending' warnings + 'no running event loop' RuntimeErrors in the manager's finally block. Plan 04 wires this into run_stdio's finally; Plan 02 tests call it explicitly."

patterns-established:
  - "Capability-flip wrapper: assign server.get_capabilities = _patched closure after build_server() registers all handlers. Future capability deltas (e.g., experimental flags) can use the same pattern — wrap, call original, mutate result."
  - "Two-step URI validation in wire handlers: (1) known-URI check vs RESOURCE_REGISTRY/PARAMETERIZED_SCHEMES, (2) policy/handler lookup. Both branches produce distinct error reasons so clients can route on them without re-parsing message text."
  - "Stub policy via monkeypatch.setitem(SUBSCRIPTION_POLICIES, 'corpus://status', stub). ADDITIVE — Plan 03's real CorpusStatusPolicy can land later and existing tests keep working because the monkeypatch replaces the entry only for the test scope."
  - "Fake-server subprocess script pattern (extends tests/test_e2e_stdio.py): inline the SUBSCRIPTION_POLICIES setup at the top of the script so the subprocess has a stub policy registered before run_stdio starts."

requirements-completed: [SUB-01, SUB-02]
# SUB-01: resources/subscribe handler wired + capability flipped to True
# SUB-02: subscribable URI allowlist enforced (unknown_uri + not_subscribable rejections)
# SUB-03 (notifications dispatch through ServerSession.send_resource_updated) is INFRASTRUCTURALLY landed —
# the on_change closure inside handle_subscribe calls session.send_resource_updated when a polled payload
# diffs. The closure is exercised by the polling-task lifecycle but no real cadence fires until Plan 03's
# policies land (Plan 02's tests use interval_s=3600 stub policies so the wire-shape is what's covered).
# SUB-04, SUB-05 closed by Plan 01.

# Metrics
duration: 14min
completed: 2026-06-03
---

# Phase 52 Plan 02: MCP wire integration & capability flip Summary

**`@server.subscribe_resource()` + `@server.unsubscribe_resource()` handlers registered with a `get_capabilities` wrapper that flips the MCP-SDK-hardcoded `subscribe=False` to `True`; subscribable-URI allowlist enforced via known-URI + policy-lookup two-step gate; 26 new tests covering wire shape, dispatch logic, and e2e subprocess round-trip.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-06-03T14:45:11Z
- **Completed:** 2026-06-03T14:59:00Z
- **Tasks:** 2 atomic commits (source + tests)
- **Files modified:** 6 (2 created: policies.py + test_subscribe_handler.py; 4 modified: server.py, subscriptions/__init__.py, test_initialize.py, test_e2e_resources.py)

## Accomplishments

- **Capability flip shipped:** `caps.resources.subscribe` is `True` over the full MCP wire (verified by both in-process `get_capabilities` assertion AND a stdio-subprocess e2e roundtrip in `test_e2e_initialize_advertises_subscribe_capability`). The SDK's hardcoded `False` at `mcp/server/lowlevel/server.py:211` is bypassed by a `_patched_get_capabilities` wrapper installed inside `build_server()`.
- **Subscribe/unsubscribe handlers wired:** `@server.subscribe_resource()` and `@server.unsubscribe_resource()` handlers validate URIs against the two-step gate (known-URI + policy), capture the owning `ServerSession` via `server.request_context.session`, and dispatch to Plan 01's `SubscriptionManager.start_polling()` / `unsubscribe()`. The on-change closure calls `session.send_resource_updated(AnyUrl(uri))` per CONTEXT decision A (owning-session only).
- **`policies.py` stub landed:** `SubscriptionPolicy` Protocol + empty `SUBSCRIPTION_POLICIES: dict[str, SubscriptionPolicy] = {}` + `resolve_policy()` exact-then-scheme lookup helper. Plan 03 will populate the registry without touching the Protocol shape or the dispatcher.
- **Three rejection reasons surfaced:** `unknown_uri` (scheme outside the resource registries), `not_subscribable` (known URI but no policy), `duplicate_subscribe` (same session, same URI, already polling). Each rejection carries `data.reason` so MCP clients can route without parsing message text.
- **211 MCP tests passing** (up from 180) — 26 new tests across 3 files cover URI normalization, `_is_known_uri`, capability flip, in-memory subscribe round-trip, scheme-prefix policy resolution, and the e2e subprocess wire shape.
- **`task before-push` exit 0** — 416 tests across the monorepo, Black + Ruff + mypy strict clean, 3 layering contracts kept.

## Task Commits

Each task was committed atomically:

1. **Task 1: Source code for wire integration** - `bde8d47` (feat) — adds `policies.py`, modifies `server.py` (subscribe/unsubscribe handlers + capability wrapper + URI normalization helpers + private-attr manager), modifies `subscriptions/__init__.py` (re-exports).
2. **Task 2: Tests** - `4716f7a` (test) — adds 26 new tests across `test_subscribe_handler.py` (NEW), `test_initialize.py` (capability assertions inverted + manager pin), `test_e2e_resources.py` (5 e2e tests via the same fake-server-subprocess pattern as `test_e2e_stdio.py`).

**Plan metadata commit:** (this SUMMARY + STATE + ROADMAP update — separate commit below)

## Files Created/Modified

- `agent-brain-mcp/agent_brain_mcp/subscriptions/policies.py` — `SubscriptionPolicy` Protocol + empty `SUBSCRIPTION_POLICIES` registry + `resolve_policy()` exact-then-scheme lookup. Plan 03 populates.
- `agent-brain-mcp/agent_brain_mcp/server.py` — `_normalize_uri` + `_is_known_uri` helpers; `@server.subscribe_resource()` handler with two-step gate + duplicate pre-check + session capture; `@server.unsubscribe_resource()` handler (idempotent ack); `_patched_get_capabilities` wrapper flipping `subscribe=False` → `True`; `server._subscription_manager` private-attr workaround; `run_stdio` instructions string bumped to v2.
- `agent-brain-mcp/agent_brain_mcp/subscriptions/__init__.py` — re-exports the new symbols (`SUBSCRIPTION_POLICIES`, `SubscriptionPolicy`, `resolve_policy`, `PolicyFetcherFactory`) alongside Plan 01's locked surface.
- `agent-brain-mcp/tests/test_initialize.py` — deletes `test_capabilities_have_no_subscriptions`; adds `test_capabilities_advertise_subscriptions` + `test_capabilities_subscribe_independent_of_resources_changed_flag` + `test_build_server_attaches_subscription_manager` (private-attr pin).
- `agent-brain-mcp/tests/test_subscribe_handler.py` — 22 tests across 4 classes: `TestUriNormalization` (4), `TestIsKnownUri` (4), `TestSubscribeHandlerDispatch` (8 integration tests via in-memory transport), `TestSubscribePolicyScheme` (2), `TestSubscribeWithMockedSession` (1 direct-handler test with `request_ctx` injection).
- `agent-brain-mcp/tests/e2e/test_e2e_resources.py` — deletes `test_resources_subscribe_returns_method_not_found` stub; preserves 5 Phase 4 skip-marked read-resource stubs; adds 5 e2e tests via the same fake-server-subprocess pattern as `test_e2e_stdio.py` (init advertises subscribe, positive ack, unknown_uri, not_subscribable, duplicate_subscribe).

## Decisions Made

(See `key-decisions` in frontmatter above — 8 decisions documented.)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] MCP SDK capability advertisement is hardcoded, not flag-driven**
- **Found during:** Task 1 (server.py wire-up). The plan asked us to verify whether `NotificationOptions.resources_subscribed` exists (Option A) or whether the capability is derived from handler presence (Option B). Reading `mcp/server/lowlevel/server.py:211` revealed neither — the SDK hardcodes `subscribe=False` regardless of handler-presence or NotificationOptions flags.
- **Issue:** Without an SDK fix or a wrapper, registering `@server.subscribe_resource()` would NOT make the SDK advertise the capability — clients would see `subscribe: false` in `initialize` and never attempt to subscribe.
- **Fix:** Installed a `_patched_get_capabilities` wrapper inside `build_server()` that calls the original method and flips `caps.resources.subscribe = True` post-hoc. The wrapper is documented inline with a line-number reference to the SDK source and a note that it's the surgical fix until upstream exposes a capability knob.
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/server.py`
- **Verification:** `test_capabilities_advertise_subscriptions` asserts `caps.resources.subscribe is True`; `test_e2e_initialize_advertises_subscribe_capability` proves the flip survives the full stdio wire round-trip via the MCP SDK client.
- **Committed in:** `bde8d47`

**2. [Rule 1 — Bug] Polling tasks leaked past in-memory harness teardown**
- **Found during:** Task 2 (running the new integration tests). Tests that subscribed left a polling task pinned to the event loop; when the loop tore down at test boundary, the manager's `_poll_loop.finally` block called `asyncio.current_task()` with no running loop → `RuntimeError: no running event loop`.
- **Issue:** Plan 01's `_poll_loop.finally` defense-in-depth block doesn't handle the case where the task is being torn down by the event-loop shutdown (vs being cancelled by `unsubscribe`). The block calls `asyncio.current_task()` unconditionally — that raises if no loop is running.
- **Fix:** Added explicit `manager.cleanup_all()` calls to integration tests that leave subscriptions active. Documented in the test docstrings that Plan 04 will wire this into `run_stdio`'s `finally` block — until then, tests manage their own polling-task lifecycle. The manager.py fix is OUT OF SCOPE for Plan 02 (Plan 01's public surface is locked); the right long-term fix is either Plan 04's `run_stdio` cleanup hook OR a defensive `try/except RuntimeError` in Plan 01's finally block (deferred to a future micro-plan).
- **Files modified:** `agent-brain-mcp/tests/test_subscribe_handler.py`
- **Verification:** `poetry run pytest tests/test_subscribe_handler.py -v` runs warning-free; `poetry run pytest -W error` also passes.
- **Committed in:** `4716f7a` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both auto-fixes were necessary for correctness. Deviation 1 is the most consequential — without the wrapper, the capability flip would silently no-op and the entire plan would fail acceptance. The fix lives entirely inside `build_server()` (no SDK monkey-patching) and is documented with the SDK source line reference so future contributors can verify it's still needed when the SDK is upgraded. Deviation 2 is purely a test-lifecycle hygiene issue surfaced by the new tests; Plan 04's `run_stdio` cleanup hook will retire the explicit `cleanup_all()` calls.

## Issues Encountered

- **anyio task-group cancel-scope guard:** Initial test design used `@pytest_asyncio.fixture` wrapping `create_connected_server_and_client_session` so tests could just take a `mcp_session` parameter. That tripped anyio's `RuntimeError: Attempted to exit cancel scope in a different task than it was entered in` because the fixture's enter/exit ran on different anyio tasks than the test body. Resolved by inlining the `async with` block per test. Documented inline in `TestSubscribeHandlerDispatch` so future contributors don't fall into the same trap.
- **MagicMock vs AsyncMock for `send_resource_updated`:** The mocked-session direct-handler test originally used a plain `MagicMock` for the session — the polling task fires `await session.send_resource_updated(...)` on its first iteration and `MagicMock(...)` returns a non-awaitable `MagicMock` instance → `TypeError: object MagicMock can't be used in 'await' expression`. Resolved by using `AsyncMock(return_value=None)` for the `send_resource_updated` attribute specifically. Added `manager.cleanup_all()` at end of the test to drop the polling task before the event loop tears down.

## User Setup Required

None — this is library-internal MCP wire-up code with no external services.

## Next Phase Readiness

**Plan 03 (per-URI policies) is unblocked.** Plan 03 will populate `SUBSCRIPTION_POLICIES` with three concrete policies:

- `"job://"` (scheme key) — 1s polling against `GET /index/jobs/{id}`, auto-cancel on terminal state.
- `"corpus://status"` (exact key) — 30s polling against `GET /health/status`, diff-suppressed.
- `"corpus://folders"` (exact key) — 5s active / 60s safety polling against `GET /index/folders/`.

The handler dispatch logic, capability flip, and rejection reasons are LOCKED at this point. Plan 03 adds the policy entries; it does NOT need to touch `server.py` or `subscriptions/__init__.py` or any of the new tests. The stub-policy monkeypatch pattern used in `tests/test_subscribe_handler.py` is additive — Plan 03's real policies will coexist with the test stubs without breakage.

**Plan 04 (disconnect cleanup hook) is also unblocked.** Plan 04 will refactor `build_server()` to return `(server, manager)` and add a `try/finally` in `run_stdio` that calls `manager.cleanup_all()`. The `server._subscription_manager` private-attr workaround stays as documented; Plan 04 retires it in the same diff. Once Plan 04 ships, the explicit `manager.cleanup_all()` calls in Plan 02's tests can be deleted (or moved into a session-scoped pytest fixture).

**Phase 54 TOOL-04 cross-phase contract held:** `SubscriptionManager.start_polling()` signature is still locked (no changes in Plan 02). Phase 54 Plan 04 (`wait_for_job`) can import these symbols verbatim without re-coordinating with Phase 52.

**Subscribable URI allowlist enforcement is partial in Plan 02 alone:** With an empty `SUBSCRIPTION_POLICIES` registry, every subscribe attempt currently returns `not_subscribable`. Plan 03 lights up the three policies; until then, the wire-shape is complete but no actual polling fires.

## Resolution of the Open Plan-Time Question

The plan flagged: *"Where does `resources.subscribe: true` actually get set?"* with two hypothesized SDK shapes (A: `NotificationOptions` flag, B: handler-presence derivation).

**Answer: neither.** Reading `mcp/server/lowlevel/server.py:208-213` shows `subscribe=False` is hardcoded:

```python
if types.ListResourcesRequest in self.request_handlers:
    resources_capability = types.ResourcesCapability(
        subscribe=False, listChanged=notification_options.resources_changed
    )
```

There is no `resources_subscribed` field on `NotificationOptions` and no derivation from `_subscribe_resource_handler is not None`. The SDK simply doesn't expose the capability — Plan 02 patches it via the `get_capabilities` wrapper. The patch is the surgical fix until upstream lands an opt-in knob; this is documented in `build_server()` with a line-number reference so future SDK upgrades can drop the wrapper if/when the capability becomes flag-driven.

## Self-Check: PASSED

- [x] `agent-brain-mcp/agent_brain_mcp/subscriptions/policies.py` exists (created)
- [x] `agent-brain-mcp/tests/test_subscribe_handler.py` exists (created)
- [x] `agent-brain-mcp/agent_brain_mcp/server.py` modified with subscribe/unsubscribe handlers + capability wrapper + manager private attr
- [x] `agent-brain-mcp/agent_brain_mcp/subscriptions/__init__.py` re-exports `SUBSCRIPTION_POLICIES`, `SubscriptionPolicy`, `resolve_policy`
- [x] `agent-brain-mcp/tests/test_initialize.py` capability assertion inverted (`subscribe is True`)
- [x] `agent-brain-mcp/tests/e2e/test_e2e_resources.py` MethodNotFound stub deleted; 5 new e2e tests added
- [x] Commit `bde8d47` exists in `git log` (feat: source code)
- [x] Commit `4716f7a` exists in `git log` (test: 26 new tests)
- [x] `poetry run pytest` (MCP non-e2e suite) — 201 passed, 38 deselected
- [x] `poetry run pytest -m e2e` — 10 passed, 28 skipped (5 NEW e2e tests pass)
- [x] `poetry run pytest -m ''` (full MCP suite) — 211 passed, 28 skipped
- [x] `poetry run black --check` — clean (29 source files)
- [x] `poetry run ruff check` — clean
- [x] `poetry run mypy agent_brain_mcp` — clean (29 source files, no issues)
- [x] `task check:layering` — 3 contracts kept, 0 broken
- [x] `task before-push` — exit 0 (416 tests across the monorepo, 80% coverage)
- [x] No edits to Plan 01's locked surface (`manager.py`, `payloads.py`, `errors.py`)
- [x] No new dependencies added

---
*Phase: 52-resource-subscriptions*
*Completed: 2026-06-03*
