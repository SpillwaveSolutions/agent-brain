# Plan 03: Per-URI polling policies & change-stream

**Phase:** 52 — Resource subscriptions
**Requirements covered:** SUB-01 (`job://<id>` 1s), SUB-02 (`corpus://status` 30s), SUB-03 (`corpus://folders` 5s active / 60s safety)
**Depends on:** 01 (`SubscriptionManager`, `canonical_hash`)
**Parallel-safe with:** 02 (different files; 02's handler reads from the policy registry this plan populates)
**Status:** Not started

## Goal

Implement the three concrete `SubscriptionPolicy` instances that fulfill SUB-01, SUB-02, SUB-03. Each policy declares its URI pattern, polling interval, drop-key set for diff suppression, and an async fetcher that calls into the existing `ApiClient`. The `corpus://folders` policy is the most novel — it polls at 5s while subscribed and falls back to a 60s safety cadence, configurable via settings.

Policies are registered into Plan 02's `SUBSCRIPTION_POLICIES` registry at module import time. Plan 02's subscribe handler dispatches automatically.

This plan does **not** modify the wire handler (Plan 02 owns that) and does **not** add the run_stdio cleanup hook (Plan 04 owns that).

## Acceptance Criteria

- [ ] `agent-brain-mcp/agent_brain_mcp/subscriptions/policies.py` (extended from Plan 02's stub) defines three policy classes:
  - `JobPolicy` — matches `job://<id>` pattern, `interval_s = 1.0`, fetcher calls `ApiClient.get_job(job_id)`, drop_keys includes timestamps, **auto-terminates when polled job reaches terminal state** (`status in {completed, failed, cancelled}`) — emits the final notification then signals the subscription manager to cancel its own task
  - `CorpusStatusPolicy` — matches `corpus://status` (exact), `interval_s = 30.0`, fetcher calls `ApiClient.server_status()`, drop_keys `= DEFAULT_DROP_KEYS | {"request_id"}`
  - `CorpusFoldersPolicy` — matches `corpus://folders` (exact), `interval_s` configurable (default 5.0 from settings.folders_active_interval_s), fetcher calls `ApiClient.list_folders()`, drop_keys = `DEFAULT_DROP_KEYS | {"last_polled"}` (none of `last_indexed` since that's a real change signal)
- [ ] `SUBSCRIPTION_POLICIES` registry populated at module-load with the three policies keyed by URI scheme/pattern (use a `resolve_policy(uri)` helper for pattern matching, since `job://<id>` needs prefix matching while `corpus://status` is exact)
- [ ] `agent_brain_mcp/config.py` extended with two new settings (matching `MCPSettings` pattern):
  - `mcp_subscription_folders_active_interval_s: float = 5.0` (env: `AGENT_BRAIN_MCP_SUBSCRIPTION_FOLDERS_ACTIVE_INTERVAL_S`)
  - `mcp_subscription_folders_safety_interval_s: float = 60.0` (env: `AGENT_BRAIN_MCP_SUBSCRIPTION_FOLDERS_SAFETY_INTERVAL_S`)
  - These wire into `CorpusFoldersPolicy.__init__` at module load
- [ ] **Auto-cancel for terminal job**: `JobPolicy.fetcher` raises a sentinel `SubscriptionTerminated` (defined in `subscriptions/errors.py`) when the polled job is terminal — Plan 01's `_poll_loop` catches this in the `try/except` and exits cleanly (auto-removing from registry via the `finally` block). Update Plan 01's manager to handle this sentinel — minor extension, document the contract.
- [ ] Each policy unit-tested in `tests/subscriptions/test_policies.py`:
  - `JobPolicy.fetcher` returns dict on running job; raises `SubscriptionTerminated` on terminal status (parameterize: completed, failed, cancelled)
  - `JobPolicy` URI pattern matches `job://abc`, `job://uuid-with-dashes`, doesn't match `job://` (empty id), doesn't match `jobs://abc`
  - `CorpusStatusPolicy.fetcher` returns dict from `ApiClient.server_status()`; drop_keys produce stable hash across two calls that differ only in `timestamp`
  - `CorpusFoldersPolicy.fetcher` returns folders list; `interval_s` reads from settings
- [ ] Integration-style test in `tests/subscriptions/test_policy_integration.py` proving each policy works end-to-end through `SubscriptionManager.start_polling` with a mocked `ApiClient`:
  - Job policy: start with `status=running` → poll fires `on_change` once with running payload, then mock flips to `status=completed` → second on_change with completed payload → loop auto-exits and task removed from manager registry
  - Status policy: payload constant across 2 polls → `on_change` fires exactly once (first poll); flip a non-volatile field → second `on_change` fires; flip only a timestamp → no third `on_change`
  - Folders policy: with `interval_s=0.1` (override via constructor), mock `list_folders()` to return constant → first poll fires `on_change`, subsequent polls don't
- [ ] No edits to `agent-brain-server/` (this phase is MCP-package-only — server-side data sources reuse existing endpoints)
- [ ] `task mcp:pr-qa-gate` and `task before-push` exit 0

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-mcp/agent_brain_mcp/subscriptions/policies.py` | modify | Add 3 policy classes + populate `SUBSCRIPTION_POLICIES` + `resolve_policy()` |
| `agent-brain-mcp/agent_brain_mcp/subscriptions/errors.py` | modify | Add `SubscriptionTerminated` sentinel |
| `agent-brain-mcp/agent_brain_mcp/subscriptions/manager.py` | modify | `_poll_loop` catches `SubscriptionTerminated` and exits cleanly |
| `agent-brain-mcp/agent_brain_mcp/config.py` | modify | Add two new settings fields |
| `agent-brain-mcp/tests/subscriptions/test_policies.py` | create | Per-policy unit tests (~120 LOC) |
| `agent-brain-mcp/tests/subscriptions/test_policy_integration.py` | create | Manager + policy integration tests with mocked `ApiClient` (~150 LOC) |

## Implementation Steps

1. Edit `agent_brain_mcp/subscriptions/errors.py`: add `class SubscriptionTerminated(Exception): """Signals a polling loop should exit cleanly (e.g., job reached terminal state)."""`
2. Edit `agent_brain_mcp/subscriptions/manager.py`:
   - In `_poll_loop`, wrap the `await fetcher()` in `try / except SubscriptionTerminated as exc`
   - On terminal: extract the final payload from `exc.args[0]` if provided, call `on_change(uri, final_payload)` one last time, then `return` (the `finally` block handles registry cleanup)
   - Update unit tests for manager to cover this exit path
3. Edit `agent_brain_mcp/config.py` to add the two new MCP settings fields with env binding and Pydantic validation (floats, must be > 0).
4. Edit `agent_brain_mcp/subscriptions/policies.py`:
   - Import `ApiClient` from `agent_brain_mcp.client`
   - Define `class JobPolicy:` with `uri_pattern = "job://"`, `interval_s = 1.0`, `drop_keys = DEFAULT_DROP_KEYS`, async `fetcher(api_client, uri)`:
     - Parse `job_id` from URI (strip `"job://"` prefix)
     - `payload = await asyncio.to_thread(api_client.get_job, job_id)` (per server.py:130 pattern)
     - If `payload.get("status") in {"completed", "failed", "cancelled"}`: `raise SubscriptionTerminated(payload)`
     - Else `return payload`
   - Define `class CorpusStatusPolicy:` similarly, `interval_s = 30.0`, fetcher wraps `api_client.server_status()`
   - Define `class CorpusFoldersPolicy:` with `__init__(self, interval_s)` so settings-driven cadence can be injected; fetcher wraps `api_client.list_folders()`
   - At module level: instantiate the three policies and `SUBSCRIPTION_POLICIES["job://"] = JobPolicy(); SUBSCRIPTION_POLICIES["corpus://status"] = CorpusStatusPolicy(); SUBSCRIPTION_POLICIES["corpus://folders"] = CorpusFoldersPolicy(interval_s=settings.mcp_subscription_folders_active_interval_s)`
   - Implement `def resolve_policy(uri: str) -> SubscriptionPolicy | None:` — checks exact match first, then scheme-prefix match for `job://` style
5. Write `tests/subscriptions/test_policies.py` — fake `ApiClient` with `get_job`, `server_status`, `list_folders` returning controllable payloads; test each policy in isolation; parameterize terminal-status cases.
6. Write `tests/subscriptions/test_policy_integration.py`:
   - Use `pytest-asyncio`
   - Build a real `SubscriptionManager`, fake `session = object()`, fake `ApiClient`, collector `on_change`
   - For each policy: monkeypatch `interval_s` to a fast value (e.g., 0.05s) where appropriate, simulate payload changes, assert collector receives the expected sequence
   - For `JobPolicy`: flip mock to terminal, sleep, assert manager registry is empty and final terminal-state on_change was emitted
7. **Plan 02 cross-check**: at this point, Plan 02's handler dispatching against the populated `SUBSCRIPTION_POLICIES` should "just work" — but Plan 02's e2e tests use a stub policy via monkeypatch. Run Plan 02's tests too to confirm no regression.
8. Run `task mcp:pr-qa-gate`, `task before-push`.

## Verification

```bash
cd agent-brain-mcp
poetry run pytest tests/subscriptions/test_policies.py tests/subscriptions/test_policy_integration.py -v

# Run full subscription module
poetry run pytest tests/subscriptions/ -v

# Run Plan 02's e2e to confirm no regression
poetry run pytest tests/e2e/test_e2e_resources.py -v

# Full gates
task mcp:pr-qa-gate
cd ..
task before-push    # MUST exit 0
```

Manual sanity check (requires running `agent-brain-serve`):

```bash
# Terminal 1: start the server
agent-brain start

# Terminal 2: start an indexing job (gives us a job:// to subscribe to)
JOB_ID=$(agent-brain index /tmp/some-folder --json | jq -r .job_id)

# Terminal 3: drive MCP via stdio, subscribe to that job
python - <<EOF
import asyncio
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

async def main():
    params = StdioServerParameters(command="agent-brain-mcp", args=["--backend", "uds"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            count = 0
            async def on_notif(notif):
                nonlocal count
                count += 1
                print(f"notif #{count}: {notif}")
            # Subscribe and let it run for 5 seconds
            await session.subscribe_resource("job://${JOB_ID}")
            await asyncio.sleep(5)
            print(f"received {count} notifications in 5s — expected ≥3 (1s cadence)")

asyncio.run(main())
EOF
```

## Risk Notes

- **`ApiClient.get_job` may not exist in the exact shape needed** — the v1 MCP client wraps a `get_job(job_id) -> dict`. Verify in `agent-brain-mcp/agent_brain_mcp/client.py` and adjust if needed.
- **`list_folders()` payload shape** — `GET /index/folders/` returns a list of objects with `last_indexed` timestamps. These are real change signals and **must not** be in `drop_keys`. The drop_keys for `CorpusFoldersPolicy` should be tight (just the polling-internal `last_polled` if we add it, plus base `DEFAULT_DROP_KEYS`). Conversely, the response wrapper may include an envelope-level timestamp that should be dropped — inspect the actual payload and document drop_keys in code comments.
- **`asyncio.to_thread` around sync httpx calls** — must follow server.py:130, 158 pattern. Don't `await` the sync method directly inside an async fetcher.
- **Job ID parsing**: `job://abc-def-123` → strip `"job://"`. Reject empty IDs (`job://`) with `ValueError` at fetch time, which Plan 01's `_poll_loop` will treat as a fatal exit. Plan 02's handler could pre-validate but that complicates the handler — keep validation in the fetcher and accept that an invalid `job://` subscribes successfully but fires no notifications and terminates fast. Document.
- **Settings reload timing**: the `interval_s` for `CorpusFoldersPolicy` is read at module import. If settings change after the MCP server starts, the new value isn't picked up. v2 accepts this — no hot reload (per Phase 52 context "Specifics" section). Document explicitly.
- **Safety-poll cadence (60s) not yet wired**: this plan implements the **active** 5s cadence. The 60s safety poll concept from the design doc is for periods when no subscriber is active — meaningless when subscription model is per-session and the polling task only runs while subscribed. Resolve in the design doc: the "safety poll" is actually a sanity assertion (no missed signals during an active subscription); the 60s number is a max-staleness budget. No code change needed — document the resolution in design doc + code comment.

---
*Plan 03 of Phase 52*
