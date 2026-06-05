# Plan 03: Subscription lifecycle E2E test (VAL-02)

**Phase:** 55 — Validation, contract tests & QA gate integration
**Requirements covered:** VAL-02 (closes SUB-05 verification)
**Depends on:** Plan 01 (consumes `mcp_stdio_session` fixture)
**Parallel-safe with:** Plan 02 (different test file) and Plan 04 (different transport)
**Status:** Not started

## Goal

Verify `resources/subscribe` → `notifications/resources/updated` → `unsubscribe`
end-to-end against the official MCP SDK over stdio, for all three subscription
URIs Phase 52 ships (`job://<id>` @ 1s cadence, `corpus://status` @ 30s,
`corpus://folders` @ watcher-driven). Also verify that client disconnect
releases server-side subscriptions (SUB-05): when a second client subscribes
then drops its stdio pipe without unsubscribing, the per-client subscription
count must drop to 0 within one cadence window.

## Acceptance Criteria

- [ ] `agent-brain-mcp/tests/contract/test_subscription_lifecycle.py` parametrizes one test per subscription URI (`job://`, `corpus://status`, `corpus://folders`) with `(uri, cadence_seconds, mode)` tuples where `mode ∈ {"poll", "watcher"}`.
- [ ] Each happy-path test: opens session → `subscribe(uri)` → `asyncio.wait_for(receive_notification, timeout=cadence * 1.5)` → asserts at least one `notifications/resources/updated` arrived with the correct `uri` field → `unsubscribe(uri)` → asserts no further notifications arrive within `cadence * 1.5`.
- [ ] Each notification payload validates against the MCP spec shape: `params.uri` is the subscribed URI, `params._meta` or `params.revision` (whichever Phase 52 emits) is present and well-formed.
- [ ] `test_disconnect_cleanup` spawns a **second** `agent-brain-mcp` subprocess, subscribes to `job://<id>`, then forcibly closes the stdio pipe (no explicit `unsubscribe`), waits 2 × cadence (2s for `job://`), and asserts the per-client subscription count on the server is 0. Use the Phase 52 observability surface if exposed; otherwise scrape the MCP subprocess stderr for the spec-mandated disconnect log line.
- [ ] If Phase 52 did NOT expose a subscription-count observability surface, this plan files a follow-up GitHub issue `gh issue create --title "MCP v2 follow-up: expose /mcp/subscriptions debug endpoint" --label "mcp,v2,follow-up"` and uses log-scraping as the verification mechanism in the interim. The plan's PR description must call this out.
- [ ] Subscription tests run **stdio only** (per D-08); the HTTP transport's SSE framing is covered by Plan 04, not here.
- [ ] `task mcp:contract` continues to pass; subscription tests add <20s to suite time (the 30s `corpus://status` cadence test must use a fixture-overridden cadence — see Risks).

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-mcp/tests/contract/test_subscription_lifecycle.py` | create | Parametrized happy-path subscribe/notify/unsubscribe + disconnect-cleanup test |
| `agent-brain-mcp/tests/contract/conftest.py` | modify | Add `mcp_stdio_subprocess_handle` fixture (returns the raw `Popen` handle so disconnect-cleanup test can call `proc.stdin.close()` mid-test) |
| `agent-brain-mcp/tests/conftest.py` | modify | If `_DEFAULT_RESPONSES` lacks a poll-target endpoint for the fake backend (e.g., `GET /index/jobs/{id}` returning a `running` state), add it so the subscription has something to "notice changes" against |

## Implementation Steps

1. Re-read `.planning/phases/52-resource-subscriptions/52-CONTEXT.md` (if available) to confirm:
   - Exact cadence values shipped (`job://` 1s, `corpus://status` 30s, `corpus://folders` watcher).
   - Whether Phase 52 exposed any subscription-count observability surface (e.g., `GET /mcp/subscriptions/__debug` behind `AGENT_BRAIN_DEBUG=1`).
   - The notification payload shape Phase 52 committed to (URI + revision metadata vs URI + `_meta`).
2. If Phase 52 supports per-instance cadence override (e.g., via `AGENT_BRAIN_MCP_CADENCE_STATUS_SEC=2` env var), use it in the test fixture to compress 30s → 2s for CI speed. Otherwise, mark the `corpus://status` test `@pytest.mark.slow` and gate it behind `AGENT_BRAIN_E2E=1`.
3. Write `tests/contract/test_subscription_lifecycle.py`:
   ```python
   import asyncio, pytest
   from mcp.types import ResourceUpdatedNotification

   CASES = [
       ("job://test-job-1", 1.0, "poll"),
       ("corpus://status", 2.0, "poll"),   # cadence-overridden to 2s in fixture
       ("corpus://folders", 3.0, "watcher"),
   ]

   @pytest.mark.contract
   @pytest.mark.asyncio
   @pytest.mark.parametrize("uri,cadence,mode", CASES, ids=lambda c: str(c[0]))
   async def test_subscription_lifecycle(mcp_stdio_session, uri, cadence, mode):
       await mcp_stdio_session.initialize()
       await mcp_stdio_session.subscribe_resource(uri)
       notif = await asyncio.wait_for(
           _next_resource_update(mcp_stdio_session),
           timeout=cadence * 1.5,
       )
       assert notif.params.uri == uri
       await mcp_stdio_session.unsubscribe_resource(uri)
       with pytest.raises(asyncio.TimeoutError):
           await asyncio.wait_for(
               _next_resource_update(mcp_stdio_session),
               timeout=cadence * 1.5,
           )

   @pytest.mark.contract
   @pytest.mark.asyncio
   async def test_disconnect_cleanup(mcp_stdio_subprocess_handle, debug_subscription_count_url):
       # Spawn second session via the handle, subscribe, then kill stdin
       proc = mcp_stdio_subprocess_handle  # raw Popen
       async with _open_client_against(proc) as session:
           await session.initialize()
           await session.subscribe_resource("job://disconnect-test")
       # Closing the session above closes stdin without explicit unsubscribe.
       await asyncio.sleep(2.0)  # one cadence window
       count = await _query_subscription_count(debug_subscription_count_url)
       assert count == 0
   ```
4. Add a helper `_next_resource_update(session)` that awaits the next `notifications/resources/updated` event off the session's incoming-message queue. Use the SDK's `session.incoming_messages` channel if available; otherwise patch in a small listener.
5. In `tests/contract/conftest.py`, add `mcp_stdio_subprocess_handle` fixture that yields the raw `Popen` from `stdio_client(...)` — needed so the disconnect test can close stdin without going through `ClientSession.__aexit__()`.
6. If no debug endpoint exists, swap the `_query_subscription_count` helper with a stderr-log scraper that greps for the Phase 52 disconnect-cleanup log line (e.g., `"subscription released for client <id>"`).
7. File the follow-up issue if needed:
   ```bash
   gh issue create --title "MCP v2 follow-up: expose /mcp/subscriptions debug endpoint" \
     --label "mcp,v2,follow-up" \
     --body "Phase 55 SUB-05 verification fell back to log scraping because Phase 52 did not expose a subscription-count observability surface. Add GET /mcp/subscriptions/__debug gated behind AGENT_BRAIN_DEBUG=1."
   ```
8. Run `task mcp:contract` to confirm green.

## Verification

- `cd agent-brain-mcp && task contract` → all 3 happy-path tests + 1 disconnect test pass.
- `cd agent-brain-mcp && poetry run pytest tests/contract/test_subscription_lifecycle.py -v` → 4 tests passing; total time <20s.
- Manual: with `AGENT_BRAIN_DEBUG=1 agent-brain-mcp --transport stdio < /dev/stdin` interactively, send a `resources/subscribe` for `job://...`, observe `notifications/resources/updated` arriving at ~1s cadence. Confirms human-visible behavior matches the test.
- `ps -ef | grep agent-brain-mcp | grep -v grep` empty after `task contract` completes — disconnect-cleanup test must not leak the second subprocess.

## Risk Notes

- **30s cadence vs CI speed**: a literal 30s sleep per subscription test inflates the contract suite past the 60s target. The fixture MUST inject a cadence override (`AGENT_BRAIN_MCP_CADENCE_STATUS_SEC=2` or analog). If Phase 52 didn't expose this knob, file as a Phase 52 follow-up and skip the `corpus://status` cadence assertion in Phase 55 (only assert the URI shape + subscribe/unsubscribe RPC roundtrip).
- **No subscription-count observability**: D-06 in CONTEXT.md flags this as a likely gap. Plan must handle both paths (endpoint present → query directly; endpoint absent → log-scrape + file follow-up issue).
- **Cadence tolerance flakiness**: `cadence * 1.5` is the per-D-07 deadline. Sub-1s cadences are flaky on shared CI runners; this plan asserts no cadence below 1s. If a test flakes intermittently, raise the multiplier to 2.0 (not 3.0 — that masks real cadence-drift bugs).
- **Notification payload shape drift**: MCP spec versions may differ on whether `revision` is a top-level field or nested under `_meta`. The test must read from whichever path Phase 52 emits — pin to the MCP SDK version Phase 50 locked in the v2 design doc, do not float.
- **Disconnect test orphan risk**: forcibly closing stdin without unsubscribe is exactly the scenario that strands polling tasks if Phase 52's cleanup is buggy. The teardown finalizer from Plan 01 catches orphans, but if the second subprocess survives, `ps` scan will fail the test — that's the intended signal, not a bug in this plan.
- **SDK `subscribe_resource` API name**: confirm the actual method name in `mcp` 1.12.x — if the SDK uses `request(...)` directly, adjust the helper. The smoke fixture in Plan 01 will surface the shape.

---
*Plan 03 of Phase 55*
