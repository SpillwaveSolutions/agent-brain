---
phase: 54
plan: "04"
subsystem: agent-brain-mcp
tags:
  - mcp
  - tools
  - progress-notifications
  - async-handler
  - phase-finalization
dependency_graph:
  requires:
    - 54-01 (WaitForJobInput / WaitForJobOutput schemas locked: poll_interval
      ge=0.5 le=2.0, timeout_seconds ge=1)
    - 54-02 (TOOL_REGISTRY at 11 — read-only block precedes mutating block)
    - 54-03 (TOOL_REGISTRY at 15 — mutating block precedes wait_for_job)
    - 52-01 (SubscriptionManager.start_polling primitive locked; module-docstring
      Phase 54 reuse contract honored even though Plan 04 chose an inline
      poll loop rather than reusing start_polling — both are valid per the
      objective)
  provides:
    - wait_for_job MCP tool (TOOL-04) — the only progress-emitting tool
    - ToolSpec.emits_progress field + branched server.call_tool dispatch
    - _build_progress_notifier closure factory in server.py
    - First async tool handler in the agent-brain-mcp codebase
    - TOOL_REGISTRY at FINAL v2 count of 16
  affects:
    - Phase 55 (VAL-01 contract test will parameterize against 16 tools;
      VAL-01's MCP-spec progress-notification conformance check will
      target wait_for_job specifically)
tech_stack:
  added: []
  patterns:
    - "Async tool handler signature: ``async def handle_<name>(client, args, *, notify) -> output`` — first instance in agent-brain-mcp"
    - "ToolSpec.emits_progress discriminator: sync handlers stay on asyncio.to_thread (v1 contract preserved); async progress-emitting handlers get the notify closure injected"
    - "_build_progress_notifier closure factory: captures request_context once (progressToken + related_request_id + session) and returns an async (progress, total, message) callable; no-ops cleanly when client did not attach progressToken (MCP-spec opt-in semantic)"
    - "time.monotonic for both timeout decision AND elapsed_seconds output — NTP-immune"
    - "Defensive output projection via _project_job_output: ONLY records the keys WaitForJobOutput declares + explicit kwargs (final, elapsed_seconds, status_override) — defends against ``WaitForJobOutput(**record, final=...)`` collision risk noted in Plan 04 §Risk Notes"
    - "Cancellation propagation: asyncio.CancelledError caught, finally clause makes best-effort client.cancel_job(...) call, re-raises original CancelledError — cancel_job failure is silenced (logger.exception) so the wire cancellation flow is never masked"
    - "Terminal-states frozenset is a SUPERSET of plan's enumerated set (succeeded/failed/cancelled/dry_run) AND server's actual JobStatus values (completed/done/failed/cancelled) — absorbs server-version drift, documented in module docstring"
    - "Progress clamped to [0.0, 1.0] defensively even though the server should already guarantee this — protects the wire shape against a stale/fuzzed response"
key_files:
  created:
    - agent-brain-mcp/agent_brain_mcp/tools/wait.py
    - agent-brain-mcp/tests/test_wait_for_job_tool.py
    - agent-brain-mcp/tests/test_e2e_wait_for_job.py
  modified:
    - agent-brain-mcp/agent_brain_mcp/tools/__init__.py
    - agent-brain-mcp/agent_brain_mcp/server.py
    - agent-brain-mcp/tests/test_tools_list.py
    - agent-brain-mcp/tests/test_e2e_stdio.py
decisions:
  - "Inline poll loop in handle_wait_for_job (NOT reuse SubscriptionManager.start_polling). Reasoning: start_polling returns void and registers tasks in a session-scoped registry — wrong model for a tool that must RETURN a result; tight cancel/timeout flow is cleaner inline; the plan's sketch explicitly used inline. Phase 52's start_polling stays the locked primitive for the resources/subscribe path; Phase 54 TOOL-04 chose the alternative valid implementation per the objective's 'both are valid' clause."
  - "Terminal-states set is a 6-element superset frozenset({succeeded, failed, cancelled, dry_run, completed, done}). Reasoning: server's JobStatus enum is {PENDING, RUNNING, DONE, FAILED, CANCELLED} (wire value 'done') but the actual JobRunner has been observed to emit 'completed' as an alias in some paths; the plan + CONTEXT call out succeeded/dry_run as MCP-facing names. Honoring all six absorbs drift across server versions. Pinned by test_completed_status_treated_as_terminal AND test_done_status_treated_as_terminal."
  - "_build_progress_notifier lives in server.py (NOT in tools/wait.py). Reasoning: the closure needs `server.request_context` which is the MCP SDK's per-request ContextVar; encapsulating it in the server module keeps the SDK coupling out of the tool layer (tools/wait.py only knows the ProgressNotifier Callable type alias). Tools stay testable without an MCP request context — the unit tests pass a captured-notify mock; production gets the real wired closure."
  - "ProgressNotifier signature: ``Callable[[float, float, str | None], Awaitable[None]]`` — positional (progress, total, message). NOT kwargs. Reasoning: matches MCP spec's ProgressNotificationParams field order; lets the closure pass straight through to ``session.send_progress_notification(progress_token, progress, total, message, related_request_id)`` without re-naming. progressToken + related_request_id are baked into the closure at construction (captured from request_context) — handlers don't see them."
  - "Notification cadence: 1.0s default poll_interval_seconds, le=2.0s (Plan 01 lock). Reasoning: MCP spec requires ≤2s; we target 1s for headroom + consistency with Phase 52's job:// subscription cadence. Tests override to 0.5s for fast turn-around."
  - "Soft timeout returns ``status='timeout'`` + ``final=False`` + last-known progress/message. NEVER raises. Reasoning: CONTEXT decision E + the plan's risk register both stress that MCP cancellation (notifications/cancelled) is the client's hard escape — timeout_seconds is just a polite soft cap. Pinned by test_timeout_returns_timeout_status_without_raising."
  - "Cancellation cleanup wraps client.cancel_job in try/except Exception. Reasoning: backend may be unreachable mid-cancellation; the secondary failure MUST NOT mask the primary CancelledError. Pinned by test_cancelled_error_propagates_even_if_cancel_job_fails."
  - "test_tools_list.py upgraded to exact-count == 16 (was Plan 03's forward-compat >= 15). Reasoning: Plan 04 is the final Phase 54 plan — no more registry additions in v2 — so the assertion can lock the exact count. Phase 55's VAL-01 contract test mirrors it independently for spec conformance."
  - "v1 e2e test (tests/test_e2e_stdio.py) bumped from `assert len(tools.tools) == 7` to `== 16`. Rule-1 auto-fix — the v1 e2e was forward-incompatible by design; Phase 54 added 9 tools across Plans 02/03/04; only Plan 04 surfaces the regression because earlier plans either ran before e2e or were caught at registry-pin time."
metrics:
  duration_minutes: 45
  completed_date: 2026-06-03
  tests_added: 18
  tests_before: 433
  tests_after: 451
  commits: 4
  files_changed: 7
  lines_added_approx: 720
---

# Phase 54 Plan 04: wait_for_job (TOOL-04) Summary

**One-liner:** Shipped `wait_for_job` — the only progress-emitting MCP tool in v2 and the first async tool handler in the codebase — with terminal-status detection, soft-timeout, and best-effort cancellation propagation; bumped TOOL_REGISTRY from 15 to its final v2 count of 16.

## Scope Recap

Plan 04 is the Wave-4 (final) plan in Phase 54. It introduces:

1. **A new dispatch path** for async progress-emitting tool handlers — `ToolSpec.emits_progress: bool = False` field + `server.call_tool` branch on it (existing `asyncio.to_thread` path preserved for all v1 + Plan 02/03 tools).
2. **`tools/wait.py`** — async polling-loop handler with `time.monotonic` timeout, terminal-status detection (6-element superset frozenset), MCP `notifications/progress` emission, and cancellation cleanup.
3. **`_build_progress_notifier`** in `server.py` — closure factory that captures `request_context.meta.progressToken` + `request_context.request_id` + `request_context.session` and returns a `Callable[[float, float, str | None], Awaitable[None]]` that emits one `notifications/progress` per call. No-ops cleanly when client did not opt in (no progressToken).
4. **The final `wait_for_job` TOOL_REGISTRY entry** with `emits_progress=True` and `readOnlyHint=True`.
5. **`_summarize()` extension** with the `wait_for_job` branch at the alphabetical tail of the Phase 54 block: `wait_for_job → <job_id>: <status> (<pct>%) after <elapsed>s`.
6. **17 unit tests** + **1 e2e SDK test** + a regression bump to the v1 e2e (assert 16 tools instead of 7).

## Phase 52 Primitive Reuse Decision

The objective gave Plan 04 a choice: reuse `SubscriptionManager.start_polling` (Phase 52's locked primitive) OR implement an inline poll loop. **We chose the inline poll loop**.

Reasoning:

| Constraint                              | start_polling                                   | Inline loop                  |
| --------------------------------------- | ----------------------------------------------- | ---------------------------- |
| Return shape                            | void; registers a session-bound task            | Returns `WaitForJobOutput`   |
| Cancellation cleanup                    | `unsubscribe` triggers task.cancel              | `finally` block runs cleanup |
| Timeout semantics                       | None — designed for long-lived subscriptions    | `time.monotonic` budget       |
| Notification cadence                    | Driven by `policy.interval_s`                   | Driven by `poll_interval_seconds` arg |
| Result extraction                       | Through `on_change` callback (side-effecting)   | Direct return value          |

`start_polling` is the right primitive for **subscriptions** (long-lived, callback-driven, no return shape). `wait_for_job` is a **request-response tool** that happens to emit progress along the way — the inline approach matches the natural control flow. Phase 52's `start_polling` stays the locked primitive for `resources/subscribe`; Plan 04's inline approach is one of two valid implementations the objective explicitly sanctioned.

## Notify Primitive Signature

```python
ProgressNotifier = Callable[[float, float, str | None], Awaitable[None]]
# Called as: await notify(progress, total, message)
# Where:
#   progress: float in [0.0, 1.0] — progress_percent / 100, clamped defensively
#   total:    always 1.0 (MCP spec — handler standardizes)
#   message:  str | None — passed through from the server job record
```

The closure factory captures the per-request state once and bakes it in:

- `progressToken` from `request_context.meta.progressToken` (None → closure is a no-op)
- `related_request_id` from `request_context.request_id` (coerced str | None for the SDK signature)
- `session` from `request_context.session` (the `ServerSession` instance)

Internally invokes `session.send_progress_notification(progress_token, progress, total, message, related_request_id)`.

## Server↔MCP Surface Mirror

| MCP tool       | Schema (Plan 01)                  | ApiClient method (v1)            | HTTP route                |
| -------------- | --------------------------------- | -------------------------------- | ------------------------- |
| `wait_for_job` | `WaitForJobInput / Output`        | `ApiClient.get_job(job_id)` (v1) + `ApiClient.cancel_job(job_id)` (v1, cleanup only) | `GET /index/jobs/{id}` polling loop |

No new schemas, no new ApiClient methods, no new HTTP routes. The polling loop reuses v1's `get_job` and `cancel_job` — Plan 04's contribution is purely the async control flow + progress emission.

## Deviations from Plan

### Auto-fixed Issues (Rule 1 — bug-class)

**1. [Rule 1 — Bug] v1 e2e `assert len(tools.tools) == 7` updated to `== 16`**

- **Found during:** Quality gate after Task 6 (e2e suite run)
- **Issue:** `tests/test_e2e_stdio.py::test_initialize_lists_tools_resources_prompts` hardcoded `assert len(tools.tools) == 7` from v1. Phase 54 added 9 tools across Plans 02/03/04, but only Plan 04 surfaces this because e2e tests are marked `e2e` and excluded from the default `task mcp:test` run — earlier plans never executed this assertion. The bug is in the test, not the code: Plan 04's registry registration is correct.
- **Fix:** Bumped to `== 16` with an inline comment citing `test_tools_list.py::test_registry_has_exactly_sixteen_tools` as the authoritative tool-count contract. The e2e mirrors that contract over the SDK wire.
- **Files modified:** `agent-brain-mcp/tests/test_e2e_stdio.py`
- **Commit:** `4a2c1e0` (folded into the e2e-test commit)

### Auto-fixed Issues (Rule 3 — blocking, lint/type)

**2. [Rule 3 — Blocking] Black reformat + Ruff UP037 + mypy related_request_id coercion**

- **Found during:** Quality gate after Task 5 (post-test addition)
- **Issue:** (a) Black wanted to collapse a multi-line set-union comprehension in `test_tools_list.py::EXPECTED_TOOLS` onto fewer lines. (b) Ruff flagged `UP037` on the quoted forward-reference annotation `"ProgressNotifier"` in `_build_progress_notifier`'s return type — with `from __future__ import annotations` the quotes are redundant. (c) mypy strict flagged `Argument "related_request_id" to "send_progress_notification" of "ServerSession" has incompatible type "int | str"; expected "str | None"` — the SDK's `RequestId` type is `int | str` (mcp/types.py:40) but the `send_progress_notification` parameter is typed narrowly as `str | None` (runtime accepts either).
- **Fix:** (a) `poetry run black agent_brain_mcp tests` reformatted the set comprehension. (b) `poetry run ruff check --fix` unquoted the annotation. (c) Defensive coercion `str | None = str(raw_rid) if raw_rid is not None else None` before passing to the SDK — wire-level still gets the original repr because `str(int)` round-trips through JSON-RPC unchanged. Three lints addressed in one chore commit.
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/server.py`, `agent-brain-mcp/tests/test_tools_list.py`
- **Commit:** `7a691e7`

### None other.

The plan's `_TERMINAL_STATES` set was specified as `{"succeeded", "failed", "cancelled", "dry_run"}`. We deliberately shipped the 6-element superset `{succeeded, failed, cancelled, dry_run, completed, done}` — this is NOT a deviation but a documented design decision (see `decisions[]` frontmatter + the `tools/wait.py` module docstring). The plan's risk register §"Async/sync handler discrimination" specifically asked us to consider what the server actually emits; the superset is the answer.

## Authentication Gates

None. `wait_for_job` polls the existing `agent-brain-serve` via the v1 `ApiClient.get_job` method which has no authentication layer (loopback-only deployment per CLAUDE.md and v1 design).

## Quality Gate Results

| Gate                                                       | Result                                                            |
| ---------------------------------------------------------- | ----------------------------------------------------------------- |
| `poetry run black --check agent_brain_mcp tests`           | exit 0 (92 files clean)                                           |
| `poetry run ruff check agent_brain_mcp tests`              | exit 0 ("All checks passed")                                      |
| `poetry run mypy agent_brain_mcp`                          | exit 0 ("Success: no issues found in 36 source files")            |
| `poetry run pytest -q --no-cov` (MCP fast-lane)            | **451 passed**, 47 deselected, 2 warnings, 9.82s (was 433 → +18) |
| `poetry run pytest -m e2e --no-cov` (MCP e2e)              | **16 passed**, 28 skipped, 454 deselected (was 15 → +1)           |
| `task check:layering`                                      | exit 0 (3/3 contracts kept — 164 files, 414 deps)                 |
| `task mcp:contract`                                        | exit 0 (Phase 55 placeholder — "MCP contract validation lands in Phase 4.") |
| `task before-push` (repo root)                             | exit 0 (416 monorepo CLI tests; 80% coverage gate honored; "All checks passed - Ready to push") |

Smoke-test of registry contents:

```
$ poetry run python -c "from agent_brain_mcp.tools import TOOL_REGISTRY; ..."
Total tools: 16
wait_for_job present: True
emits_progress: True
annotations: {'readOnlyHint': True}
Tools with emits_progress=True: 1
```

The exact-count v2 contract (`== 16`) is now pinned in `tests/test_tools_list.py::test_registry_has_exactly_sixteen_tools`. The single-`emits_progress` invariant is pinned in `test_only_wait_for_job_emits_progress`.

## Commit Trail

| Commit    | Type    | Description                                                                       |
| --------- | ------- | --------------------------------------------------------------------------------- |
| `f95e0ce` | feat    | Add wait_for_job async tool with progress notifications (TOOL-04) — handler + ToolSpec.emits_progress + server.call_tool dispatch branch + _build_progress_notifier closure + _summarize branch |
| `e7d8fec` | test    | Cover wait_for_job handler with 17 unit tests + pin `== 16` exact-count + emits_progress invariant in test_tools_list.py |
| `4a2c1e0` | test    | Add e2e SDK test for wait_for_job + bump v1 e2e tool count (Rule 1 — `== 7` → `== 16`) |
| `7a691e7` | chore   | Black + Ruff + mypy fixes for wait_for_job dispatch (3 mechanical lint fixes) |

## Final TOOL_REGISTRY Inventory (16 tools)

| #  | Tool             | Plan  | Annotations                                       | emits_progress |
| -- | ---------------- | ----- | ------------------------------------------------- | -------------- |
| 1  | search_documents | v1    | `{readOnlyHint: True, openWorldHint: True}`       | False          |
| 2  | query_count      | v1    | `{readOnlyHint: True}`                            | False          |
| 3  | index_folder     | v1    | `{destructiveHint: False, openWorldHint: True}`   | False          |
| 4  | get_job          | v1    | `{readOnlyHint: True}`                            | False          |
| 5  | list_jobs        | v1    | `{readOnlyHint: True}`                            | False          |
| 6  | cancel_job       | v1    | `{destructiveHint: True}`                         | False          |
| 7  | server_health    | v1    | `{readOnlyHint: True}`                            | False          |
| 8  | explain_result   | 54-02 | `{readOnlyHint: True, openWorldHint: True}`       | False          |
| 9  | list_folders     | 54-02 | `{readOnlyHint: True}`                            | False          |
| 10 | cache_status     | 54-02 | `{readOnlyHint: True}`                            | False          |
| 11 | list_file_types  | 54-02 | `{readOnlyHint: True}`                            | False          |
| 12 | add_documents    | 54-03 | `{openWorldHint: True, destructiveHint: False}`   | False          |
| 13 | inject_documents | 54-03 | `{openWorldHint: True, destructiveHint: False}`   | False          |
| 14 | remove_folder    | 54-03 | `{destructiveHint: True}`                         | False          |
| 15 | clear_cache      | 54-03 | `{destructiveHint: True}`                         | False          |
| 16 | wait_for_job     | 54-04 | `{readOnlyHint: True}`                            | **True**       |

15 sync handlers (legacy `asyncio.to_thread` dispatch); 1 async progress-emitting handler (Phase 54 Plan 04 new dispatch branch).

## Locked Public Surface (for Phase 55)

```python
from agent_brain_mcp.tools import TOOL_REGISTRY, ToolSpec
# len(TOOL_REGISTRY) == 16 — final v2 count
# ToolSpec.emits_progress field is part of the public ToolSpec contract

from agent_brain_mcp.tools.wait import (
    ProgressNotifier,   # Callable[[float, float, str | None], Awaitable[None]]
    handle_wait_for_job,
    _TERMINAL_STATES,   # frozenset of 6 terminal job statuses
)

# server.py adds:
#   - _build_progress_notifier(server) -> ProgressNotifier
#   - call_tool now branches on spec.emits_progress
#   - _summarize() now handles wait_for_job
```

Phase 55 VAL-01 contract test will verify:
- Exact tool count == 16
- `wait_for_job` is the only emits_progress tool
- `notifications/progress` payload conforms to MCP spec 2024-11-05+ ProgressNotificationParams
- Cancellation propagation (MCP `notifications/cancelled` → `client.cancel_job` server-side cancellation)

## Self-Check: PASSED

All 7 declared files exist on disk (3 created, 4 modified — verified via tool-state tracking during execution). All 4 declared commits resolve via `git log`. Quality gates all green at commit time (2026-06-03):

- `agent-brain-mcp/agent_brain_mcp/tools/wait.py` FOUND
- `agent-brain-mcp/tests/test_wait_for_job_tool.py` FOUND
- `agent-brain-mcp/tests/test_e2e_wait_for_job.py` FOUND
- `agent-brain-mcp/agent_brain_mcp/tools/__init__.py` MODIFIED (ToolSpec.emits_progress + registry entry + imports)
- `agent-brain-mcp/agent_brain_mcp/server.py` MODIFIED (call_tool branch + _build_progress_notifier + _summarize branch + TYPE_CHECKING import)
- `agent-brain-mcp/tests/test_tools_list.py` MODIFIED (exact-count + emits_progress pin)
- `agent-brain-mcp/tests/test_e2e_stdio.py` MODIFIED (Rule 1 — v1 e2e count fix)

Commits: `f95e0ce` (feat), `e7d8fec` (test units), `4a2c1e0` (test e2e + v1 fix), `7a691e7` (chore lint).

---
*Plan 04 of Phase 54 — duration 45 minutes, 4 commits, +18 tests, ~720 LOC*
