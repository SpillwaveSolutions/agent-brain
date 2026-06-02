# Plan 04: Progress-emitting tool — wait_for_job

**Phase:** 54 — 9 remaining MCP tools
**Requirements covered:** TOOL-04 (`wait_for_job` with `notifications/progress` at least every 2s)
**Depends on:** Plan 01 (schemas + ApiClient methods) AND Phase 52 (`ProgressNotifier` injection contract on `ToolSpec` + `server.call_tool`)
**Parallel-safe with:** Plans 02 and 03 once their constraints are met (disjoint files except `tools/__init__.py::TOOL_REGISTRY`). MUST NOT start before Phase 52 finalizes the `ProgressNotifier` shape.
**Status:** Not started

## Goal

Ship the only tool in Phase 54 that consumes Phase 52's subscription/notification infrastructure: `wait_for_job` blocks on an active indexing job and emits `notifications/progress` at least every 2s (we target 1s for margin and consistency with the `job://` subscription cadence) until the job reaches a terminal status, then returns the final `JobRecord`. This is also the first **async tool handler** in the codebase, introducing a new dispatch path in `server.call_tool` for progress-emitting tools.

## Acceptance Criteria

- [ ] `agent_brain_mcp/tools/wait.py` exists with `handle_wait_for_job` as an **async** function with signature:
  ```python
  async def handle_wait_for_job(
      client: ApiClient,
      args: WaitForJobInput,
      *,
      notify: ProgressNotifier,
  ) -> WaitForJobOutput:
  ```
  where `ProgressNotifier` is the type/protocol exported by Phase 52 (likely `Callable[[float, float, str | None], Awaitable[None]]` or a small Protocol — Plan 04 imports it from wherever Phase 52 defines it).
- [ ] `ToolSpec` gains an `emits_progress: bool = False` field (default False so v1 tools and Plans 02/03 tools are unaffected).
- [ ] `wait_for_job`'s `ToolSpec` entry sets `emits_progress=True` and `annotations={"readOnlyHint": True}` (the tool itself is a read-only poll; the server-side state changes are driven by other tools).
- [ ] `server.call_tool` (lines 105-133 in v1) branches on `spec.emits_progress`:
  - If False (all v1 + all Plan 02/03 tools): existing `asyncio.to_thread(spec.handler, api, args)` path.
  - If True (only `wait_for_job` for now): `await spec.handler(api, args, notify=notify)` where `notify` is a closure that wraps the MCP server's `send_progress_notification` (or equivalent — exact API comes from Phase 52).
- [ ] Poll cadence: 1.0 second between `GET /index/jobs/{id}` calls (CONTEXT decision E — under the ≤2s spec requirement, matches `job://` subscription cadence).
- [ ] Progress notification payload conforms to MCP spec:
  ```python
  {
      "progressToken": <token from request meta>,
      "progress": <float in [0.0, 1.0]>,  # progress_percent / 100
      "total": 1.0,
      "message": <str, server's progress message or None>,
  }
  ```
- [ ] Terminal states handled: `succeeded`, `failed`, `cancelled`, `dry_run` — all treated as terminal. Final `notifications/progress` sent with `progress=1.0` before returning.
- [ ] Timeout behavior: if `timeout_seconds` is set and exceeded, return `WaitForJobOutput(status="timeout", ...)` with last-known job state — do NOT raise. (CONTEXT decision E.)
- [ ] Cancellation propagation: if the handler receives `asyncio.CancelledError` (MCP `notifications/cancelled`), the `finally:` block calls `client.cancel_job(args.job_id)` and re-raises. (CONTEXT decision E.) Tool description warns: "Cancelling this MCP request will also cancel the underlying indexing job server-side."
- [ ] `_summarize()` in `server.py` gains the `wait_for_job` branch: `wait_for_job → <job_id>: <status> (<progress>%) after <elapsed>s` per CONTEXT `<specifics>`.
- [ ] After this plan lands, `len(TOOL_REGISTRY) == 16` (7 v1 + 9 v2). `tests/test_tools_list.py` asserts the exact count.
- [ ] Unit tests in `agent-brain-mcp/tests/test_wait_for_job_tool.py` cover:
  1. Happy path: 3-step job (0% → 50% → 100% succeeded). Assert 3+ progress notifications were emitted (1 per poll + 1 final). Use a mocked `notify` callable to capture calls.
  2. Failed terminal: server returns `status="failed"`. Final notification has `progress=1.0`. Output has `status="failed"`.
  3. Cancelled terminal: server returns `status="cancelled"`. Same handling.
  4. Dry run: server returns `status="dry_run"` immediately. Output treats as terminal.
  5. Timeout: `timeout_seconds=2`, job never completes; output has `status="timeout"`, `final=False`, last-known progress.
  6. Cancellation propagation: handler is `asyncio.cancel()`ed; assert `client.cancel_job` is called in cleanup and `CancelledError` re-raised.
  7. Poll-interval clamping: `WaitForJobInput(job_id="x", poll_interval_seconds=5.0)` raises `pydantic.ValidationError` (`le=2.0` from Plan 01).
  8. Notification payload shape: capture a notification call; assert it has `progressToken`, `progress` (float in [0,1]), `total: 1.0`, and `message`.
- [ ] Integration test against the official MCP SDK in `agent-brain-mcp/tests/test_e2e_wait_for_job.py`: start a fake indexing job (via fixture), invoke `wait_for_job` via SDK client, assert receive `>=2` progress notifications within ~3 seconds, assert final result is the job record.
- [ ] `task mcp:test`, `task mcp:pr-qa-gate`, `task check:layering`, `task before-push` all pass.
- [ ] `agent-brain-mcp` package's existing `task mcp:contract` (validates schemas against pinned MCP spec) still passes with the new tool.

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-mcp/agent_brain_mcp/tools/wait.py` | create | Async handler. ~100 LOC including imports, polling loop, cancellation cleanup, comments. |
| `agent-brain-mcp/agent_brain_mcp/tools/__init__.py` | modify | Extend `ToolSpec` dataclass with `emits_progress: bool = False`. Add `wait_for_job` entry. Final count: 16 tools. |
| `agent-brain-mcp/agent_brain_mcp/server.py` | modify | `call_tool` branches on `spec.emits_progress`. `_summarize` gains `wait_for_job` branch. |
| `agent-brain-mcp/tests/test_wait_for_job_tool.py` | create | 8 unit tests as enumerated above. Heavy use of `asyncio` and mocking. |
| `agent-brain-mcp/tests/test_e2e_wait_for_job.py` | create | 1 integration test using official MCP SDK client (extends existing `tests/test_e2e_stdio.py` pattern). |
| `agent-brain-mcp/tests/test_tools_list.py` | modify | Bump assertion to `len(TOOL_REGISTRY) == 16` (final v2 count). |

## Implementation Steps

1. **Verify Phase 52 deliverable.** Before writing code, confirm Phase 52 has shipped:
   - The `ProgressNotifier` type (or Protocol / Callable signature) in `agent_brain_mcp.subscriptions` or wherever Phase 52 placed it.
   - The wiring in `server.call_tool` that creates the `notify` closure from the MCP server's `send_progress_notification` method. If Phase 52 did NOT wire `call_tool` (only built the primitive), Plan 04 owns the wiring — adjust scope accordingly.
   - Read `.planning/phases/52-*/52-PLAN.md` and the resulting SUMMARY before starting.
2. **Confirm `progressToken` source.** Per the MCP spec, the client attaches a `progressToken` in the request meta. The MCP SDK exposes this via the request context. Verify the exact accessor (likely `request.meta.progressToken` or similar) by reading Phase 52's notification-send code.
3. Open `agent_brain_mcp/tools/__init__.py` and extend the `ToolSpec` dataclass:
   ```python
   @dataclass
   class ToolSpec:
       name: str
       description: str
       handler: Callable  # sync OR async — discriminated by emits_progress
       input_model: type[BaseModel]
       output_model: type[BaseModel]
       annotations: dict[str, Any]
       emits_progress: bool = False
   ```
4. Open `server.py::call_tool` (v1 lines 105-133) and add the branching dispatch:
   ```python
   if spec.emits_progress:
       # Async handler with progress notification injection.
       # Phase 52 provides the notify closure here (or it's built inline).
       notify = self._build_progress_notifier(request)  # from Phase 52
       result = await spec.handler(api_client, args, notify=notify)
   else:
       # Sync handler wrapped in to_thread (v1 behavior).
       result = await asyncio.to_thread(spec.handler, api_client, args)
   ```
   The exact `_build_progress_notifier` invocation depends on Phase 52's API. If Phase 52 didn't ship that builder, write it here — it's a thin closure over the MCP server's progress-send method.
5. Create `tools/wait.py`. Sketch:
   ```python
   import asyncio
   import time
   from typing import TYPE_CHECKING

   from agent_brain_mcp.client import ApiClient
   from agent_brain_mcp.schemas import WaitForJobInput, WaitForJobOutput

   if TYPE_CHECKING:
       from agent_brain_mcp.subscriptions import ProgressNotifier  # from Phase 52

   _TERMINAL_STATES = {"succeeded", "failed", "cancelled", "dry_run"}


   async def handle_wait_for_job(
       client: ApiClient,
       args: WaitForJobInput,
       *,
       notify: "ProgressNotifier",
   ) -> WaitForJobOutput:
       start = time.monotonic()
       last_record: dict | None = None
       try:
           while True:
               record = await asyncio.to_thread(client.get_job, args.job_id)
               last_record = record
               progress = (record.get("progress_percent") or 0) / 100.0
               await notify(progress=progress, total=1.0, message=record.get("message"))

               if record.get("status") in _TERMINAL_STATES:
                   # Final notification
                   await notify(progress=1.0, total=1.0, message=record.get("message"))
                   elapsed = time.monotonic() - start
                   return WaitForJobOutput(
                       **record,
                       final=True,
                       elapsed_seconds=elapsed,
                   )

               if args.timeout_seconds is not None and (time.monotonic() - start) >= args.timeout_seconds:
                   elapsed = time.monotonic() - start
                   return WaitForJobOutput(
                       **(last_record or {"job_id": args.job_id, "status": "timeout"}),
                       status="timeout",
                       final=False,
                       elapsed_seconds=elapsed,
                   )

               await asyncio.sleep(args.poll_interval_seconds)
       except asyncio.CancelledError:
           # Client cancelled via notifications/cancelled — propagate to server.
           try:
               await asyncio.to_thread(client.cancel_job, args.job_id)
           except Exception:
               pass  # best-effort cleanup
           raise
   ```
   Notes:
   - `WaitForJobOutput(**record, ...)` assumes the record dict's keys overlap with output model fields. If they don't, adapt. Confirm by reading `agent-brain-server/agent_brain_server/models/job.py::JobRecord` shape.
   - The `notify` callable signature (`progress=, total=, message=`) is illustrative — match the exact signature Phase 52 ships.
6. Open `tools/__init__.py` and add the `ToolSpec`:
   ```python
   "wait_for_job": ToolSpec(
       name="wait_for_job",
       description=(
           "Block until a job reaches a terminal status (succeeded, failed, "
           "cancelled, or dry_run). Emits notifications/progress at least every "
           "2 seconds (1s default cadence) while the job runs. Cancelling this "
           "MCP request via notifications/cancelled will also cancel the "
           "underlying indexing job server-side."
       ),
       handler=handle_wait_for_job,
       input_model=WaitForJobInput,
       output_model=WaitForJobOutput,
       annotations={"readOnlyHint": True},
       emits_progress=True,
   ),
   ```
7. Extend `server.py::_summarize()` with the `wait_for_job` branch:
   ```python
   elif name == "wait_for_job":
       progress = structured.get("progress_percent", 0)
       elapsed = structured.get("elapsed_seconds", 0)
       summary = f"wait_for_job → {structured['job_id']}: {structured['status']} ({progress}%) after {elapsed:.1f}s"
   ```
8. Write `tests/test_wait_for_job_tool.py`. Use `pytest.mark.asyncio` and a captured `notify` mock:
   ```python
   @pytest.mark.asyncio
   async def test_happy_path_emits_progress(...):
       captured = []
       async def fake_notify(*, progress, total, message):
           captured.append((progress, total, message))
       # mock client.get_job to return [25%, 75%, 100% succeeded]
       ...
       output = await handle_wait_for_job(client, args, notify=fake_notify)
       assert len(captured) >= 3
       assert captured[-1][0] == 1.0  # final notification
       assert output.status == "succeeded"
       assert output.final is True
   ```
   Repeat shape for the 8 enumerated tests.
9. Write `tests/test_e2e_wait_for_job.py`. Use the official MCP SDK client (existing v1 pattern from `tests/test_e2e_stdio.py`):
   1. Start agent-brain-mcp stdio subprocess via SDK.
   2. Mock backend to expose a fake indexing job that takes ~3s and progresses through 3 polls.
   3. Call `wait_for_job` via SDK. Collect progress notifications from the SDK's notification stream.
   4. Assert ≥2 progress notifications received, final result is the terminal job record.
10. Update `tests/test_tools_list.py` to assert `len(TOOL_REGISTRY) == 16`. Also assert `TOOL_REGISTRY["wait_for_job"].emits_progress is True` — the only one.
11. Run `task mcp:test`, then `task mcp:pr-qa-gate`, then `task check:layering`, then `task before-push`.

## Verification

```bash
# Wait-for-job unit tests
cd agent-brain-mcp && poetry run pytest tests/test_wait_for_job_tool.py -v

# E2E integration via MCP SDK
cd agent-brain-mcp && poetry run pytest tests/test_e2e_wait_for_job.py -v

# Final tool count check
cd agent-brain-mcp && poetry run python -c "
from agent_brain_mcp.tools import TOOL_REGISTRY
assert len(TOOL_REGISTRY) == 16, f'Expected 16 tools, got {len(TOOL_REGISTRY)}'
assert TOOL_REGISTRY['wait_for_job'].emits_progress is True
print(f'TOOL_REGISTRY count: {len(TOOL_REGISTRY)} OK')
print('wait_for_job emits_progress: True OK')
"

# Full package gate
cd agent-brain-mcp && task pr-qa-gate

# Contract test (existing v1 task)
cd agent-brain-mcp && task mcp:contract

# Layering
cd /Users/richardhightower/clients/spillwave/src/agent-brain && task check:layering

# Root gate (MANDATORY)
cd /Users/richardhightower/clients/spillwave/src/agent-brain && task before-push

# Manual stdio smoke — call wait_for_job and observe progress notifications
# (requires a running agent-brain-serve with an active indexing job)
cd agent-brain-mcp && cat > /tmp/wait-smoke.jsonl <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0.1"}}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"wait_for_job","arguments":{"job_id":"<paste-active-id>"},"_meta":{"progressToken":"smoke-1"}}}
EOF
poetry run agent-brain-mcp --backend http --backend-url http://127.0.0.1:8000 < /tmp/wait-smoke.jsonl
# Expect: alternating notifications/progress + tools/call result
```

## Risk Notes

- **Phase 52 cross-dependency** — this plan CANNOT ship until Phase 52's `ProgressNotifier` contract is final. If Phase 52 changes the notification primitive's signature post-Plan-04-drafting, expect rework. Mitigation: review Phase 52's PLAN.md and SUMMARY before drafting; review Phase 52's PR before merge.
- **Async/sync handler discrimination** — adding `emits_progress` to `ToolSpec` and branching in `call_tool` is a small surgery but easy to get wrong. The branch must be exhaustive: `emits_progress=True` ⇒ `await spec.handler(api, args, notify=notify)`; otherwise the v1 `to_thread` path. Test both paths with a v1 tool and the new `wait_for_job` to confirm no regression.
- **`progressToken` propagation** — the MCP spec requires `progressToken` from the request meta to appear in every progress notification. If Phase 52's `notify` closure already injects it, Plan 04's handler doesn't think about it. If not, Plan 04 must extract it. Verify by reading Phase 52's wiring.
- **Cancellation cleanup robustness** — if `client.cancel_job` itself raises (network down, server gone), the `finally:` block must swallow and re-raise the original `CancelledError`. Don't mask user cancellation with a secondary error.
- **`time.monotonic()` vs wall-clock** — use `monotonic` for elapsed/timeout; otherwise NTP adjustments can break the timeout logic.
- **Test flakiness** — async tests with sleeps are flaky. Use a tight `asyncio.sleep(0.01)` in tests with mocked `client.get_job` rather than the production 1.0s cadence. The 1.0s value is the production default; tests should override via the `poll_interval_seconds` argument set to 0.05 or use frozen-time fixtures.
- **E2E integration with MCP SDK** — the SDK's notification stream API can be tricky. Refer to `tests/test_e2e_stdio.py` from v1 for the established pattern; extend rather than invent.
- **Tool description progress claim** — the description says "every 2 seconds (1s default cadence)". The MCP spec requires ≤2s. If we ever change the default above 1.0s, the description and the `poll_interval_seconds` `le=` constraint must stay aligned.
- **`WaitForJobOutput(**record, ...)` field collision** — if the record dict has a `final` or `elapsed_seconds` key, the explicit kwargs collide. Filter or pop those keys defensively before spread. Test with an actual server job record dict.

---
*Plan 04 of Phase 54*
