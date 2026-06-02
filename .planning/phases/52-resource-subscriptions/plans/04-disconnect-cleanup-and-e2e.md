# Plan 04: Disconnect cleanup + SDK end-to-end validation

**Phase:** 52 — Resource subscriptions
**Requirements covered:** SUB-05 (disconnect cleanup); end-to-end validation of SUB-01, SUB-02, SUB-03, SUB-04
**Depends on:** 01, 02, 03
**Parallel-safe with:** none — last plan in phase
**Status:** Not started

## Goal

Close out Phase 52 by:

1. Adding the `try/finally` cleanup hook in `run_stdio(...)` so an MCP session exit (stdio EOF, exception, etc.) calls `subscription_manager.cleanup_all()` — releasing every polling task owned by that session.
2. Adding a per-task guard inside `_poll_loop` that handles `CancelledError` cleanly and self-removes from the registry (defense-in-depth — already partially landed in Plan 01's `finally` block; this plan adds the explicit catch + the test that proves both layers work).
3. Writing the **end-to-end SDK tests** that exercise the full subscribe → receive updates → unsubscribe / disconnect → assert-no-leaked-tasks flow for each subscribable URI. These are the tests that prove SUB-01, SUB-02, SUB-03, SUB-05 against the official MCP SDK.
4. Closing the loop on the small `build_server()` refactor: have `build_server()` return `(server, subscription_manager)` cleanly (replacing the private-attr workaround Plan 02 may have used) — small enough to belong here, where the cleanup hook needs explicit access.

## Acceptance Criteria

- [ ] `build_server()` in `agent-brain-mcp/agent_brain_mcp/server.py` returns `tuple[Server, SubscriptionManager]` instead of attaching the manager as a private attr; `main()` is updated to unpack and pass the manager to `run_stdio`
- [ ] `run_stdio(server, subscription_manager)` signature updated. Body wrapped in `try / finally`:
  ```python
  async def run_stdio(server: Server, subscription_manager: SubscriptionManager) -> None:
      async with stdio_server() as (read_stream, write_stream):
          try:
              await server.run(read_stream, write_stream, init_options)
          finally:
              cleaned = subscription_manager.cleanup_all()
              if cleaned:
                  logger.info(f"subscription cleanup: cancelled {cleaned} polling tasks on session close")
  ```
- [ ] `_poll_loop` in `agent_brain_mcp/subscriptions/manager.py` already has `try/finally` from Plan 01; Plan 04 adds an explicit `except asyncio.CancelledError:` clause that re-raises (so the cancellation propagates) but logs the cancel at DEBUG with `session_id[:8]` + `uri`. This makes the leaked-task assertion test diagnosable.
- [ ] New e2e test file `agent-brain-mcp/tests/e2e/test_e2e_subscriptions.py` (this is the heart of the plan, ~160 LOC):
  - `test_subscribe_corpus_status_emits_on_change`: monkeypatch `CorpusStatusPolicy.interval_s` to 0.5s; mock `/health/status` (or `ApiClient.server_status` via a custom backend URL pointing to a stub aiohttp server); flip a non-volatile field; assert exactly 1 `notifications/resources/updated` arrives within 1.5s; payload conforms to `ResourceUpdatedNotificationParams` shape: `params.uri == "corpus://status"`, `params._meta is None or "revision" in params._meta`
  - `test_subscribe_job_emits_until_terminal`: launch a fake job via the stub server (status sequence: running → running → completed); subscribe via `subscribe_resource("job://<id>")`; collect notifications for 4s; assert ≥2 notifications received, last one terminal; assert subscription manager's `active_count()` drops to 0 within 1s of terminal
  - `test_subscribe_folders_active_cadence`: monkeypatch `CorpusFoldersPolicy.interval_s` to 0.5s; mock `ApiClient.list_folders()` to flip on the 2nd call; subscribe to `corpus://folders`; assert 2 notifications within 1.5s (first poll + folder change)
  - `test_disconnect_cleans_up_polling_tasks` (SUB-05): spawn `agent-brain-mcp` as a subprocess via stdio; subscribe to `corpus://status`; kill the **client side** of the pipe (close stdin); within 2s poll `psutil.Process(mcp_pid).threads()` (or `num_threads()`) and assert no extra polling thread is alive vs the pre-subscribe baseline. Alternative if `psutil` thread visibility is unreliable: use a probe URL — the stub `ApiClient` increments a counter on every fetch; after the kill, sleep 3s, assert the counter is stable (proves the polling loop stopped fetching)
  - `test_two_sessions_independent_subscriptions`: spawn two `ClientSession` instances (each its own `stdio_client`); both subscribe to `corpus://status`; close session A; assert session B still receives notifications; close session B; assert manager state is empty
- [ ] Test `test_notification_payload_conforms_to_mcp_spec` (SUB-04) — unit-level check against `mcp.types.ResourceUpdatedNotification` schema: stub the handler call, capture the `send_resource_updated` argument, assert its serialized form parses back to `ResourceUpdatedNotification` without validation errors and contains `params.uri` and (when revision is computed) `params._meta.revision` as a 64-char hex string
- [ ] Capability test in `tests/test_initialize.py` extended (or new test added) to assert the full `resources` capability shape: `caps.resources.subscribe is True`, `caps.resources.listChanged is False` (unchanged — listChanged is out of scope for v2)
- [ ] `agent-brain-mcp/tests/e2e/conftest.py` extended with a `stub_api_server` fixture that runs an aiohttp server on a random port and exposes hooks for tests to mutate the responses it returns (so e2e tests can drive `corpus://status` and `corpus://folders` payload changes deterministically). If a stub server is too heavy, an alternative is `monkeypatch` on `ApiClient` methods — pick the simpler path and document; recommend `monkeypatch` for v2 since the URI-level fetcher is already `await asyncio.to_thread(api_client.method)`.
- [ ] `task mcp:pr-qa-gate` exits 0
- [ ] `task before-push` exits 0 from repo root — this is the **final** quality gate for Phase 52
- [ ] Phase 52 design-doc subsection (filed in Phase 50's v2 design doc) is updated/confirmed to reflect: the subscribable URI allowlist (`job://`, `corpus://status`, `corpus://folders`), the auto-cancel semantics for terminal jobs, the per-session ownership model, the `start_polling` contract that Phase 54 TOOL-04 will reuse

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-mcp/agent_brain_mcp/server.py` | modify | `build_server()` returns tuple; `run_stdio()` takes manager param + `try/finally` cleanup hook; `main()` updated to unpack |
| `agent-brain-mcp/agent_brain_mcp/subscriptions/manager.py` | modify | Explicit `except asyncio.CancelledError` with DEBUG log + re-raise |
| `agent-brain-mcp/tests/e2e/test_e2e_subscriptions.py` | create | 5 e2e tests covering SUB-01, SUB-02, SUB-03, SUB-05 |
| `agent-brain-mcp/tests/e2e/conftest.py` | modify | Add fixtures for monkeypatching `ApiClient` methods and for spawning a second `stdio_client` session in a single test |
| `agent-brain-mcp/tests/test_initialize.py` | modify | Extend capability shape assertion (`listChanged is False`) |
| `agent-brain-mcp/tests/test_notification_shape.py` | create | Unit test asserting `ResourceUpdatedNotification` spec conformance |
| `docs/plans/2026-06-XX-mcp-v2-subscriptions.md` (filed in Phase 50) | modify | Append/confirm Phase 52 subsection (allowlist, ownership model, `start_polling` reuse contract) |

## Implementation Steps

1. Edit `server.py`:
   - Change `build_server() -> Server:` → `build_server() -> tuple[Server, SubscriptionManager]:`
   - Hold the manager as a local var inside `build_server`, capture it in the subscribe/unsubscribe handler closures, return it as the second tuple element
   - Update `run_stdio(server)` → `run_stdio(server, subscription_manager)`; wrap the `await server.run(...)` body in `try / finally`
   - Update `main()` / `cli.py` callsites to unpack `(server, mgr) = build_server(...)` and pass both into `run_stdio`
2. Edit `subscriptions/manager.py`:
   - In `_poll_loop`, add explicit `except asyncio.CancelledError:` with a DEBUG log including `session_id_short = str(key[0])[:8]` and `uri`. Re-raise so cancellation semantics are preserved.
   - Confirm the `finally` block still runs after the explicit catch (Python guarantees this).
3. Create `tests/e2e/test_e2e_subscriptions.py` — use the official MCP SDK Python client. Pattern (per `test_e2e_stdio.py` in v1):
   ```python
   async with stdio_client(server_params) as (read, write):
       async with ClientSession(read, write) as session:
           await session.initialize()
           notifications: list[ResourceUpdatedNotification] = []
           session.message_handler = lambda msg: notifications.append(msg) if isinstance(msg, ResourceUpdatedNotification) else None
           await session.subscribe_resource(AnyUrl("corpus://status"))
           await asyncio.sleep(1.5)
           assert len(notifications) >= 1
           assert notifications[0].params.uri == AnyUrl("corpus://status")
   ```
   Adapt to the actual SDK message-receive pattern — may need to read incoming messages off `read` stream directly if `ClientSession` doesn't expose a notification handler hook. Verify in SDK source before writing.
4. For `test_disconnect_cleans_up_polling_tasks`:
   - Spawn the MCP server in a subprocess via `subprocess.Popen([sys.executable, "-m", "agent_brain_mcp", "--backend", "http"])` with stdin/stdout pipes
   - Use a minimal `ClientSession` to subscribe
   - Record `psutil.Process(p.pid).num_threads()` before subscribe; after subscribe; sleep 0.5s; close stdin (simulates client disconnect)
   - Poll thread count every 100ms for up to 2s; assert it returns to the pre-subscribe baseline
   - Alternative assertion (more reliable, less flaky): use a custom monkeypatch-injected counter on the fetcher — after disconnect + 2s, the counter must not increment further
   - Recommend the counter approach for primary assertion; psutil as a secondary cross-check
5. Create `tests/test_notification_shape.py`:
   - Import `from mcp.types import ResourceUpdatedNotification, ResourceUpdatedNotificationParams`
   - Build a payload as the handler would (URI + `_meta.revision`); serialize via `model_dump_json`; round-trip parse; assert no errors
   - Assert revision is a 64-char hex SHA-256
6. Update `tests/test_initialize.py` capability assertion to cover the full resources capability shape.
7. Edit `agent-brain-mcp/tests/e2e/conftest.py`:
   - Add a `monkeypatched_api_client` fixture that lets tests substitute the `ApiClient` methods at module level
   - Add a `dual_stdio_session` fixture context manager that yields two independent client sessions sharing nothing — for the two-sessions test
8. Run the full e2e suite locally with `-x` to catch flake early. Tune `interval_s` overrides + sleeps until tests are stable.
9. Update the Phase 50 design doc's Phase 52 subsection: append the subscribable URI allowlist, ownership model, `start_polling` reuse contract for Phase 54. If the design doc already covers these from Phase 50's planning, confirm consistency.
10. `task mcp:pr-qa-gate`. `task before-push` from repo root. Both must exit 0.

## Verification

```bash
cd agent-brain-mcp

# Subscription E2E suite — the SUB-01..05 acceptance tests
poetry run pytest tests/e2e/test_e2e_subscriptions.py -v -x

# Notification payload shape (SUB-04)
poetry run pytest tests/test_notification_shape.py -v

# Confirm Plan 02 capability assertion still passes after the listChanged extension
poetry run pytest tests/test_initialize.py -v

# Whole MCP package
poetry run pytest -v

# Per-package gate
task mcp:pr-qa-gate

# Repo root gate — closes the phase
cd ..
task before-push    # MUST exit 0
task pr-qa-gate     # MUST exit 0
```

Manual end-to-end smoke (operator-level confirmation that the phase actually works):

```bash
# Terminal 1
agent-brain start --uds

# Terminal 2
JOB_ID=$(agent-brain index /tmp/test-corpus --json | jq -r .job_id)

# Terminal 3
python - <<EOF
import asyncio
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from pydantic import AnyUrl

async def main():
    params = StdioServerParameters(command="agent-brain-mcp", args=["--backend", "uds"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Subscribe to live job
            print(f"subscribing to job://${JOB_ID}")
            await session.subscribe_resource(AnyUrl(f"job://${JOB_ID}"))

            # Subscribe to status
            print("subscribing to corpus://status")
            await session.subscribe_resource(AnyUrl("corpus://status"))

            # Subscribe to folders
            print("subscribing to corpus://folders")
            await session.subscribe_resource(AnyUrl("corpus://folders"))

            # Listen for 10 seconds
            await asyncio.sleep(10)

asyncio.run(main())
EOF
# Expected: 1s-cadence stream of job:// notifications until job completes,
#           then they stop. Periodic corpus://status notifications if status flips.
#           Folder notifications if you add/remove a folder via `agent-brain folders add` in another terminal.
```

## Risk Notes

- **Disconnect test flakiness is the #1 risk for this plan.** `psutil` thread counts can lag, OS scheduling jitters, asyncio task cancellation isn't instantaneous. Mitigations:
  - Primary assertion uses an injectable fetcher counter (deterministic, no OS dependency).
  - psutil check is a secondary cross-check with generous polling (2s budget).
  - If both prove flaky, fall back to an in-process check: subscribe, capture the manager's `active_count()` before and after, simulate disconnect by closing the read stream, assert `cleanup_all` was called via a logger spy.
- **`build_server() -> tuple` refactor blast radius**: `main()` and `cli.py` callsites need updating, and any test that calls `build_server()` directly needs the tuple-unpack. The v1 test suite calls `build_server()` extensively — run the full suite after the refactor.
- **`ClientSession` notification handling**: the MCP Python SDK's `ClientSession` may or may not expose a clean hook for receiving `notifications/resources/updated` server-pushed messages. If not, e2e tests must read messages off the underlying `read` stream and dispatch manually. Spike this in the first hour of the plan — if the SDK doesn't support it gracefully, document the workaround in `conftest.py`.
- **Two-sessions test depends on stdio session isolation** — each `stdio_client` call spawns a new MCP subprocess. The "same server, two sessions" semantics only apply to Streamable HTTP transport (Phase 53). For stdio, two `ClientSession`s mean two server processes, which is still a useful isolation test, but the **assertion** changes: each process owns its manager, so closing session A's process trivially doesn't affect session B's process. **Recommendation**: scope this test to "two sessions to the same process" only when Phase 53 lands HTTP transport. For Phase 52, test multi-session inside a single process at the unit level (Plan 01 already covers this), and document the cross-process isolation as a trivial consequence of process isolation.
- **Design doc update**: Phase 50 owns the v2 design doc file. Plan 04 only appends/confirms Phase 52 subsections. If Phase 50's doc doesn't exist yet (Phase 50 not shipped), this plan's design-doc update is a no-op and the contract is captured in code + this plan file. Document this dependency explicitly in the PR description.

---
*Plan 04 of Phase 52*
