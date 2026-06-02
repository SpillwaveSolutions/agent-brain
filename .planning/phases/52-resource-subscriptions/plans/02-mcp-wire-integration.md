# Plan 02: MCP wire integration & capability flip

**Phase:** 52 — Resource subscriptions
**Requirements covered:** SUB-04 (notifications/resources/updated wired to ServerSession.send_resource_updated)
**Depends on:** 01 (imports `SubscriptionManager`, `SubscribableUriRejected`)
**Parallel-safe with:** 03 (different files; 03's policies are imported into 02's handler at register time but the policy module itself is standalone)
**Status:** Not started

## Goal

Wire the MCP wire protocol to Plan 01's `SubscriptionManager`. This plan:

1. Flips the `resources.subscribe` capability from `False` to `True` in `initialize` (capability negotiation).
2. Registers `@server.subscribe_resource()` and `@server.unsubscribe_resource()` handlers that validate URIs against the allowlist and dispatch to a registry of per-URI policy callables (which Plan 03 fills in).
3. Owns the `SubscriptionManager` instance lifecycle as a module-level singleton inside `agent_brain_mcp.server` (created at `build_server()` time, accessible to `run_stdio` for the cleanup hook Plan 04 wires up).
4. Updates the v1 capability test to assert subscriptions are **advertised** rather than absent — inverts the existing assertion at `test_initialize.py:32-51`.
5. Replaces the v1 "subscribe returns MethodNotFound" test (`test_e2e_resources.py:40-…`) with a positive-path test that exercises subscribe → ack → unsubscribe → ack against a stub policy.

This plan ships **no per-URI cadence implementations** — those are Plan 03. Plan 02's handler dispatches by URI scheme to a "policy registry" that starts out empty (or with a stub). Plan 03 fills the registry.

## Acceptance Criteria

- [ ] `agent-brain-mcp/agent_brain_mcp/server.py` `build_server()`:
  - Creates a module-level `SubscriptionManager` instance via a factory (so tests can swap it)
  - Registers `@server.subscribe_resource()` handler with signature `async def handle_subscribe(uri: AnyUrl) -> None`
  - Registers `@server.unsubscribe_resource()` handler with signature `async def handle_unsubscribe(uri: AnyUrl) -> None`
- [ ] `NotificationOptions(...)` at `server.py:258` is updated so the MCP SDK advertises `resources.subscribe: true` in the initialize capabilities (verify by inspecting `mcp/server/lowlevel/server.py` for which `NotificationOptions` field drives the `resources.subscribe` capability — likely a `resources_subscribed=True` or similar; if the SDK derives capability from handler presence alone, this becomes a no-op and the test assertion proves it)
- [ ] Subscribe handler logic:
  1. Normalize the URI (apply same trailing-slash strip as `server.py:149`)
  2. Look up the URI scheme in `SUBSCRIPTION_POLICIES` registry (new dict in `agent_brain_mcp/subscriptions/policies.py` — defined in Plan 03; for Plan 02 land an empty `SUBSCRIPTION_POLICIES: dict[str, SubscriptionPolicy] = {}` and a stub `SubscriptionPolicy` Protocol)
  3. If URI not in `RESOURCE_REGISTRY`: raise `SubscribableUriRejected(reason="unknown_uri")`
  4. If URI scheme has no policy in `SUBSCRIPTION_POLICIES`: raise `SubscribableUriRejected(reason="not_subscribable")`
  5. Get session via `server.request_context.session`
  6. If already subscribed: raise `SubscribableUriRejected(reason="duplicate_subscribe")` (MCP spec is ambiguous — choose strict rejection for v2; document in design doc)
  7. Resolve the policy's `fetcher` and `interval_s` and `drop_keys`
  8. Define `async def on_change(uri_str: str, payload: dict) -> None:` that calls `await session.send_resource_updated(AnyUrl(uri_str))` — wraps with a debug log at INFO with session_id[:8]
  9. Call `subscription_manager.start_polling(session, uri_str, interval_s, fetcher, on_change, drop_keys)`
- [ ] Unsubscribe handler logic:
  1. Same URI normalization
  2. Session via `request_context.session`
  3. `subscription_manager.unsubscribe(session, uri_str)` — return value ignored (MCP `EmptyResult` regardless; missing subscription is a no-op per spec)
- [ ] `agent_brain_mcp/subscriptions/policies.py` exists with:
  - `class SubscriptionPolicy(Protocol):` defining `uri_pattern: str`, `interval_s: float`, `drop_keys: frozenset[str]`, `async def fetcher(api_client, uri: str) -> dict[str, Any]: ...`
  - `SUBSCRIPTION_POLICIES: dict[str, SubscriptionPolicy] = {}` — Plan 03 populates
- [ ] `agent_brain_mcp/resources/corpus.py` `RESOURCE_REGISTRY` is consulted for the "URI is known" check (no edits to registry contents in this plan — Plan 51 already added `job://`)
- [ ] Existing test `test_initialize.py::test_capabilities_have_no_subscriptions` is **deleted** and replaced with `test_capabilities_advertise_subscriptions`:
  - Asserts `caps.resources.subscribe is True` (or, if SDK derives differently, asserts the handler is registered via `Server._subscribe_resource_handler is not None`)
- [ ] Existing test `tests/e2e/test_e2e_resources.py::test_resources_subscribe_returns_method_not_found` is **deleted** and replaced with `test_resources_subscribe_acks_known_uri`:
  - Registers a stub policy for `corpus://status` (via a `monkeypatch` on `SUBSCRIPTION_POLICIES`)
  - Subscribes via the official MCP SDK client
  - Asserts `EmptyResult` ack received
  - Unsubscribes and asserts `EmptyResult` ack received
- [ ] New negative-path tests:
  - `test_subscribe_unknown_uri_rejected` — subscribe to `bogus://x`, assert `McpError` with code `-32602` and `data.reason == "unknown_uri"`
  - `test_subscribe_not_subscribable_uri_rejected` — subscribe to `corpus://config` (in registry but not in `SUBSCRIPTION_POLICIES`), assert `data.reason == "not_subscribable"`
  - `test_subscribe_twice_same_uri_same_session_rejected` — duplicate subscribe, assert `data.reason == "duplicate_subscribe"`
- [ ] `task mcp:pr-qa-gate` and `task before-push` exit 0

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-mcp/agent_brain_mcp/server.py` | modify | Add subscribe/unsubscribe handlers in `build_server()`, instantiate manager, update `NotificationOptions` |
| `agent-brain-mcp/agent_brain_mcp/subscriptions/policies.py` | create | `SubscriptionPolicy` Protocol + empty `SUBSCRIPTION_POLICIES` dict (Plan 03 fills) |
| `agent-brain-mcp/agent_brain_mcp/subscriptions/__init__.py` | modify | Re-export `SubscriptionPolicy`, `SUBSCRIPTION_POLICIES` |
| `agent-brain-mcp/tests/test_initialize.py` | modify | Delete `test_capabilities_have_no_subscriptions`, add `test_capabilities_advertise_subscriptions` |
| `agent-brain-mcp/tests/e2e/test_e2e_resources.py` | modify | Delete `test_resources_subscribe_returns_method_not_found`, add positive-path + 3 negative-path tests |
| `agent-brain-mcp/tests/test_subscribe_handler.py` | create | Unit tests for handler dispatch (URI norm, registry lookup, policy lookup, duplicate, session capture) |

## Implementation Steps

1. Read `agent-brain-mcp/.venv/lib/python3.12/site-packages/mcp/server/lowlevel/server.py:408-432` to confirm `subscribe_resource` / `unsubscribe_resource` decorator signatures and what they expect handlers to return (likely `None` → SDK wraps in `EmptyResult`).
2. Read same file to find how `NotificationOptions` flags map to `resources.subscribe` capability — check `_create_initialization_options` or similar. If capability is derived from handler-registered-ness alone, the `NotificationOptions` update is a no-op; if there's a flag, flip it.
3. Create `agent_brain_mcp/subscriptions/policies.py`:
   - `from typing import Protocol, Any, Awaitable, Callable`
   - `class SubscriptionPolicy(Protocol): uri_pattern: str; interval_s: float; drop_keys: frozenset[str]; async def fetcher(self, api_client: Any, uri: str) -> dict[str, Any]: ...`
   - `SUBSCRIPTION_POLICIES: dict[str, SubscriptionPolicy] = {}`
   - Helper `def resolve_policy(uri: str) -> SubscriptionPolicy | None:` — matches by scheme + optional path prefix (`job://` matches all `job://<id>`, `corpus://status` matches exact)
4. Edit `agent_brain_mcp/server.py`:
   - Add `from .subscriptions import SubscriptionManager` and `from .subscriptions.policies import SUBSCRIPTION_POLICIES, resolve_policy`
   - At top of `build_server()`: `subscription_manager = SubscriptionManager()` (later returned alongside server so `run_stdio` can call `cleanup_all` — see Plan 04)
   - For Plan 02: return a tuple `(server, subscription_manager)` from `build_server()` OR attach to `server._subscription_manager` as a private attr (recommend the latter — less API churn, since main() already does `server = build_server(...)`)
   - Register handlers via `@server.subscribe_resource()` / `@server.unsubscribe_resource()` decorators per SDK signatures; handler bodies follow logic in Acceptance Criteria
   - Update `NotificationOptions(...)` if necessary
5. Update `tests/test_initialize.py`:
   - Delete the line 32-51 negative-path test
   - Add `test_capabilities_advertise_subscriptions` using the same fixture machinery — asserts `caps.resources.subscribe is True`
6. Update `tests/e2e/test_e2e_resources.py`:
   - Delete the `MethodNotFound` test at line 40
   - Add positive-path test using `monkeypatch.setitem(SUBSCRIPTION_POLICIES, "corpus://status", <stub>)` — stub policy has `interval_s=10.0` (long, so no poll fires during ack-only test) and a trivial fetcher
   - Add 3 negative-path tests
7. Create `tests/test_subscribe_handler.py`:
   - Unit tests that don't spawn the SDK e2e — directly invoke the handler closure captured at `build_server()` time
   - Tests for URI normalization, registry rejection, policy rejection, duplicate rejection, session capture (mock `request_context.session`)
8. Run `task mcp:pr-qa-gate`. Run `task before-push` from repo root.

## Verification

```bash
cd agent-brain-mcp
# Unit-level: handler dispatch logic
poetry run pytest tests/test_subscribe_handler.py -v

# Capability flip
poetry run pytest tests/test_initialize.py::TestInitialize::test_capabilities_advertise_subscriptions -v

# E2E SDK roundtrip — subscribe/unsubscribe acks
poetry run pytest tests/e2e/test_e2e_resources.py -v

# Full per-package gate
task mcp:pr-qa-gate

# Repo-root gate
cd ..
task before-push    # MUST exit 0
```

Manual SDK smoke (optional, illustrative):

```python
# scripts/mcp-subscribe-smoke.py
import asyncio
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from mcp.shared.exceptions import McpError

async def main():
    params = StdioServerParameters(command="agent-brain-mcp", args=["--backend", "uds"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # Plan 02: just ack, no notifications received (no policy registered)
            try:
                await session.subscribe_resource("bogus://x")
            except McpError as e:
                print(f"unknown URI rejected as expected: {e.error.data}")

asyncio.run(main())
```

## Risk Notes

- **Where does `resources.subscribe: true` actually get set?** Two possibilities in the SDK:
  1. `NotificationOptions` flag on `create_initialization_options(...)` — Plan 02 flips it.
  2. Auto-derived from `Server._subscribe_resource_handler is not None` — registering the handler is sufficient, the `NotificationOptions` edit is dead code.
  Read the SDK in step 1 above to determine which. Either way, the test assertion proves the wire shape.
- **`server._subscription_manager` as a private attr feels hacky.** The cleaner alternative is to refactor `build_server()` to return `(server, manager)` and update `run_stdio` / `main` signatures. The hacky private-attr path keeps the diff smaller and lets Plan 04 introduce the refactor cleanly. Recommend the refactor in Plan 04 (so this plan stays small), but flag if the test machinery gets ugly — may need to refactor here.
- **Duplicate-subscribe semantics**: MCP spec doesn't define this clearly. v2 chooses "reject" to make the polling task lifecycle deterministic. Document the choice in the design doc; if Phase 53 or framework adapters complain, revisit.
- **Test isolation**: positive-path e2e test monkeypatches `SUBSCRIPTION_POLICIES`, but if Plan 03 has already populated it, the monkeypatch must use `monkeypatch.setitem` (additive) not `monkeypatch.setattr` (wipe). Document so tests don't break when run in either plan-order.

---
*Plan 02 of Phase 52*
