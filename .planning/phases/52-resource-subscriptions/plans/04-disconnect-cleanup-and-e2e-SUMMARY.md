---
phase: 52-resource-subscriptions
plan: 04
subsystem: mcp
tags: [mcp, subscriptions, disconnect, e2e, mcp-sdk, asyncio, agent_brain_mcp]

# Dependency graph
requires:
  - phase: 52-resource-subscriptions
    provides: Plan 01's SubscriptionManager + canonical_hash + DEFAULT_DROP_KEYS (public surface LOCKED)
  - phase: 52-resource-subscriptions
    provides: Plan 02's @server.subscribe_resource()/@server.unsubscribe_resource() handlers + capability flip wrapper + SubscribableUriRejected three-reason error data + server._subscription_manager private-attr workaround
  - phase: 52-resource-subscriptions
    provides: Plan 03's three concrete policies (JobPolicy + CorpusStatusPolicy + CorpusFoldersPolicy) populating SUBSCRIPTION_POLICIES + SubscriptionTerminated control-flow sentinel handled by _poll_loop
provides:
  - build_server() tuple return shape — tuple[Server, SubscriptionManager]
  - run_stdio(server, subscription_manager) signature + try/finally disconnect cleanup hook calling manager.cleanup_all() on EVERY exit path
  - _poll_loop explicit except asyncio.CancelledError clause that DEBUG-logs and re-raises (defense-in-depth on top of Plan 01's finally)
  - tests/test_notification_shape.py — 9 unit tests pinning ResourceUpdatedNotification spec conformance (SUB-04)
  - tests/e2e/test_e2e_subscriptions.py — 5 SDK-driven e2e tests covering SUB-01/02/03/05 end-to-end
  - Phase 52 ship-outcome subsection in v2 design doc (docs/plans/2026-06-02-mcp-v2-subscriptions.md §3.3.1)
affects: [53-streamable-http-transport, 54-04-wait-for-job, 55-04-streamable-http-e2e]

# Tech tracking
tech-stack:
  added: []  # no new deps — uses MCP SDK 1.12 ClientSession.message_handler + stdlib hashlib + existing pytest-asyncio
  patterns:
    - "build_server() returns (server, manager) tuple while preserving Plan 02's server._subscription_manager private attr for backwards compatibility (same instance, both surfaces)"
    - "run_stdio's body wrapped in try/finally calling cleanup_all() on every exit path; idempotent so re-entrancy is safe"
    - "Explicit except asyncio.CancelledError + DEBUG log + re-raise in _poll_loop — defense-in-depth on top of Plan 01's finally block; makes leaked-task diagnosable in CI without ratcheting logger to DEBUG"
    - "MCP SDK ClientSession message_handler kwarg receives ServerNotification | RequestResponder | Exception; filter on isinstance(msg, ServerNotification) and msg.root being ResourceUpdatedNotification"
    - "BaseExceptionGroup filter pattern for SDK stdio_client task-group BrokenResourceError — harmless subprocess-side write-after-client-close noise, surfaced as ExceptionGroup; test catches, filters, and re-raises anything unexpected"
    - "Per-test env-var parameterization of fake-server subprocess script — JOB_INTERVAL_S / STATUS_INTERVAL_S / FOLDERS_INTERVAL_S / JOB_RUNNING_POLLS / FETCHER_COUNTER_PATH all flow through StdioServerParameters.env"
    - "Counter-based primary assertion for disconnect cleanup — deterministic; no psutil thread-count dependence; the subprocess writes the fetch count to a file path passed via env var"

key-files:
  created:
    - agent-brain-mcp/tests/test_notification_shape.py
    - agent-brain-mcp/tests/e2e/test_e2e_subscriptions.py
  modified:
    - agent-brain-mcp/agent_brain_mcp/server.py
    - agent-brain-mcp/agent_brain_mcp/subscriptions/manager.py
    - agent-brain-mcp/tests/test_initialize.py
    - agent-brain-mcp/tests/test_subscribe_handler.py
    - agent-brain-mcp/tests/test_tools_list.py
    - agent-brain-mcp/tests/test_resources_read.py
    - agent-brain-mcp/tests/test_resources_read_parameterized.py
    - agent-brain-mcp/tests/test_resources_read_file.py
    - agent-brain-mcp/tests/test_resources_templates_list.py
    - agent-brain-mcp/tests/test_resources_list.py
    - agent-brain-mcp/tests/test_prompts_list.py
    - agent-brain-mcp/tests/test_prompts_get.py
    - agent-brain-mcp/tests/test_each_tool.py
    - agent-brain-mcp/tests/test_cancellation.py
    - agent-brain-mcp/tests/test_e2e_stdio.py
    - agent-brain-mcp/tests/e2e/test_e2e_resources.py
    - docs/plans/2026-06-02-mcp-v2-subscriptions.md

key-decisions:
  - "build_server() returns (server, SubscriptionManager) tuple. Plan 02's server._subscription_manager private attr is PRESERVED for backwards compatibility — the same SubscriptionManager instance is reachable both via tuple unpacking and via the private attr. Plan 02's regression pin (test_build_server_attaches_subscription_manager) was updated to assert identity-equality between the two surfaces, so future contributors see the contract explicitly: new code prefers tuple unpacking; legacy callers keep working."
  - "run_stdio(server, subscription_manager) explicitly receives the manager rather than reaching into the private attr — making the cleanup-hook dependency visible in the function signature. The body is wrapped in try/finally; the finally calls subscription_manager.cleanup_all() unconditionally. cleanup_all is idempotent (an empty registry returns 0) so the re-entrancy story is straightforward; the cleanup also logs a single info-level line if it cancelled ≥1 task so operators can audit disconnect events."
  - "Plan 01's _poll_loop already has a try/finally that scrubs the registry slot as defense-in-depth. Plan 04 ADDS an explicit `except asyncio.CancelledError` clause BEFORE the SubscriptionTerminated and generic Exception clauses. The new clause DEBUG-logs the session_id_short + uri then re-raises. Re-raising is load-bearing: Plan 01's finally block AND the manager's primary synchronous-cleanup paths (unsubscribe / cleanup_session / cleanup_all) both need the cancellation to propagate so the registry slot is purged. Plan 04's leaked-task assertion test (test_disconnect_cleans_up_polling_tasks) is the diagnostic motivation — without the explicit log, debugging a hung polling task in CI required ratcheting the root logger to DEBUG; the targeted log is cheaper."
  - "ClientSession SDK pattern (post-spike): the SDK's ClientSession accepts a message_handler kwarg that receives RequestResponder | ServerNotification | Exception. ServerNotification is a discriminated union whose .root is the concrete notification (e.g., ResourceUpdatedNotification). We filter on isinstance(msg, ServerNotification) AND isinstance(msg.root, ResourceUpdatedNotification) — Plan 04's risk register flagged this as 'unknown until spiked' but the SDK's session.py:601 confirmed it works cleanly. No need to read the underlying read stream manually."
  - "Disconnect-test primary assertion uses a counter-based file written by the subprocess on every fetch — deterministic, no OS thread-count dependence. The risk register's psutil cross-check was deemed unnecessary once the counter assertion proved stable across 3 consecutive runs. If a future regression makes the counter assertion flaky, the psutil cross-check is documented in the plan and can be added as a secondary layer."
  - "BaseExceptionGroup filter pattern for the disconnect test. The SDK's stdio_client task group surfaces an ExceptionGroup wrapping anyio.BrokenResourceError when the subprocess emits a final in-flight notification AFTER the client closes its read side. This is harmless (the subprocess's write succeeds; the parent has just stopped reading) and is EXACTLY the scenario Plan 04's cleanup hook is designed to handle: the subprocess's run_stdio.finally still fires and cancels the polling task. The test catches BaseExceptionGroup, filters out BrokenResourceError, and re-raises any other exception so real bugs aren't swallowed. Routed through builtins.BaseExceptionGroup so Python 3.10 compatibility doesn't trip mypy/ruff."
  - "Two-sessions test scoped to cross-process isolation (CONTEXT decision A risk note). For stdio, each stdio_client invocation spawns its own MCP subprocess; the 'two sessions on one process' semantic only applies to Streamable HTTP (Phase 53). The Plan 04 test verifies the trivial-but-load-bearing property that session A's process exit doesn't affect session B's notification stream. The 'real' multi-session isolation (Plan 01's test_two_sessions_for_same_uri_get_independent_tasks) covers the same-process case at the unit level."
  - "Stub status payload changes on every poll (n → n+1, n*10 → (n+1)*10) instead of just on the 2nd poll. The initial design used a fixed flip-on-poll-2 pattern but Plan 04's two-sessions test needed >2 distinct hashes across a 1.8s window (session B receives notifications BOTH during and after session A's lifetime). Changed to always-changing so the diff-suppression never causes the notification stream to stall mid-test — the Phase 52 production policies still diff-suppress correctly (Plan 03's CorpusStatusPolicy keeps the request_id-drop pattern); the e2e stub is a test fixture, not a policy."
  - "SUB-04 conformance test pins BOTH the minimal URI-only shape (the v2 default — Plan 02's on_change closure calls ServerSession.send_resource_updated(uri) which builds the minimal form) AND the optional _meta.revision envelope (CONTEXT decision C 'when known' path). Even though v2 doesn't populate revision today, the contract is locked here so any future revision-bearing path stays spec-conformant. canonical_hash is independently verified against hashlib.sha256(json.dumps(stripped, sort_keys=True, separators=(',', ':'))) — pins the digest computation."
  - "B017 ruff rule (bare Exception in pytest.raises) — the test for the method literal pin uses pydantic.ValidationError specifically rather than a generic Exception. Tighter; still proves the Literal-mismatch path raises at parse time."

requirements-completed: [SUB-01, SUB-02, SUB-03, SUB-04, SUB-05]
# Plans 01/02/03 already marked these complete in REQUIREMENTS.md; Plan 04
# closes them definitively by shipping the e2e SDK validation against the
# real MCP wire. SUB-05 specifically is Plan 04-owned (the disconnect
# cleanup hook). SUB-04 is also Plan 04-owned via test_notification_shape.py
# (Plans 01/02 wired the canonical_hash + send_resource_updated foundations;
# Plan 04 ships the conformance test that proves the wire shape parses
# against the SDK spec model).

# Metrics
duration: 18min
completed: 2026-06-03
---

# Phase 52 Plan 04: Disconnect cleanup + SDK end-to-end validation Summary

**`build_server()` refactored to return `(server, SubscriptionManager)`; `run_stdio` gains a try/finally cleanup hook that calls `manager.cleanup_all()` on every exit path; `_poll_loop` gains an explicit `except asyncio.CancelledError` clause for diagnosability; 5 SDK-driven e2e tests + 9 notification-shape conformance tests pin SUB-01/02/03/04/05 end-to-end against the real MCP wire; Phase 50's v2 design doc updated with the §3.3.1 Phase 52 ship-outcome subsection.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-06-03T15:32:45Z
- **Completed:** 2026-06-03T15:50:49Z
- **Tasks:** 4 atomic commits (build_server refactor + notification shape + e2e subscriptions + design doc)
- **Files modified:** 18 (2 created in tests/, 16 modified — 1 source + 15 test/doc)

## Accomplishments

- **`build_server()` tuple shape shipped.** Signature: `tuple[Server, SubscriptionManager]`. Plan 02's `server._subscription_manager` private-attr workaround is PRESERVED for backwards compatibility — the same `SubscriptionManager` instance is reachable both via tuple unpacking and via the private attr. The Plan 02 regression pin (`test_build_server_attaches_subscription_manager`) was extended to assert identity-equality between the two surfaces.
- **`run_stdio` disconnect cleanup hook shipped.** Signature changed from `run_stdio(server)` → `run_stdio(server, subscription_manager)`. Body wrapped in `try / finally`; the finally calls `subscription_manager.cleanup_all()` unconditionally with an info-level log line when any tasks were cancelled. `cleanup_all` is idempotent so the re-entrancy story is straightforward. The HTTP transport analog is documented in the v2 design doc §3.3.1 as Phase 53's responsibility.
- **`_poll_loop` explicit `CancelledError` clause shipped.** Plan 01's defense-in-depth `finally` block stays in place; Plan 04 adds an `except asyncio.CancelledError` clause that DEBUG-logs `session_id_short + uri` then re-raises. Re-raising is load-bearing — Plan 01's finally + the manager's primary synchronous-cleanup paths both rely on the cancellation propagating.
- **All `build_server()` callsites updated.** 15 test files unpack the tuple via `server, _ = build_server(...)` for tests that don't need the manager; `test_e2e_stdio.py` + `tests/e2e/test_e2e_resources.py` (which run subprocess scripts that wire `build_server + run_stdio`) unpack via `server, manager = build_server(...)` and pass the manager to `run_stdio`. The Plan 02 `_subscription_manager` private-attr regression test was rewritten to pin the new tuple shape AND backwards-compat identity.
- **5 SDK-driven e2e tests landed** in `tests/e2e/test_e2e_subscriptions.py` (~570 LOC). Covers:
  1. `test_subscribe_corpus_status_emits_on_change` — `corpus://status` 0.3s cadence stub; ≥1 notification within 1.5s.
  2. `test_subscribe_job_emits_until_terminal` — `job://job-fast` running→running→completed sequence; ≥2 notifications; unsubscribe after terminal is a no-op (slot already scrubbed via Plan 03's `SubscriptionTerminated`).
  3. `test_subscribe_folders_active_cadence` — `corpus://folders` 2-state flip; ≥2 distinct notifications within 1.5s.
  4. **`test_disconnect_cleans_up_polling_tasks` (SUB-05 load-bearing)** — counter-based proof: subscribe → counter increments ≥2 → exit both `ClientSession` and `stdio_client` contexts → wait 1.5s → counter delta ≤ 1. Deterministic; no psutil thread-count dependence. Catches the SDK's `BrokenResourceError` `BaseExceptionGroup` (harmless subprocess-side write-after-close noise) and re-raises anything unexpected.
  5. `test_two_sessions_independent_subscriptions` — cross-process isolation: session A's subprocess exit must not affect session B's notification stream.
- **9 notification-shape conformance tests landed** in `tests/test_notification_shape.py` (SUB-04). Three test classes:
  - `TestMinimalShape` — URI-only `ResourceUpdatedNotificationParams` parses + round-trips against the SDK Pydantic models.
  - `TestRevisionEnvelope` — 64-char hex SHA-256 revision; canonical_hash matches `hashlib.sha256(json.dumps(stripped, sort_keys=True, separators=(",", ":")))`; `_meta.revision` round-trips through `model_dump_json` / `model_validate_json`.
  - `TestMethodLiteral` — `method` is locked to `notifications/resources/updated`; arbitrary method strings raise `pydantic.ValidationError`.
- **Phase 50 v2 design doc updated** with §3.3.1 "Phase 52 ship outcome" subsection. Mirrors §3.2.1 (Phase 51 ship outcome) structure. Captures the contracts that Phase 53 + Phase 54 will inherit (especially the disconnect-cleanup pattern that Phase 53's HTTP analog must replicate).
- **Test count delta: +14** (9 SUB-04 conformance + 5 e2e SDK subscriptions). MCP suite: **265 passed** (was 241 non-e2e in Plan 03), **28 skipped** (Phase 4 stub fixtures still skip-marked). All quality gates exit 0: black, ruff, mypy strict, `task check:layering` (3 contracts kept, 0 broken), `task before-push` (416 monorepo tests, 80% coverage), `task pr-qa-gate`.

## Task Commits

Each task was committed atomically:

1. **Task 1: build_server tuple refactor + run_stdio cleanup hook + CancelledError clause** — `2d16b68` (feat)
   - `agent_brain_mcp/server.py` — `build_server() -> tuple[Server, SubscriptionManager]`; `run_stdio(server, subscription_manager)` + try/finally cleanup hook; `main_async` updated to unpack and forward
   - `agent_brain_mcp/subscriptions/manager.py` — explicit `except asyncio.CancelledError` clause in `_poll_loop` with DEBUG log + re-raise
   - 15 test files updated to unpack the tuple (callsite updates)
2. **Task 2: Notification payload shape conformance (SUB-04)** — `839b24b` (test)
   - `tests/test_notification_shape.py` NEW — 9 tests covering minimal shape, revision envelope, method literal
3. **Task 3: e2e SDK subscription tests for SUB-01/02/03/05** — `d0a3287` (test)
   - `tests/e2e/test_e2e_subscriptions.py` NEW — 5 SDK-driven e2e tests
4. **Task 4: Phase 52 ship-outcome subsection in v2 design doc** — `638ddcc` (docs)
   - `docs/plans/2026-06-02-mcp-v2-subscriptions.md` — §3.3.1 appended

**Plan metadata commit:** (this SUMMARY + STATE + ROADMAP + REQUIREMENTS update — separate commit below)

## Files Created/Modified

**Created:**
- `agent-brain-mcp/tests/test_notification_shape.py` — 9 unit tests pinning ResourceUpdatedNotification spec conformance
- `agent-brain-mcp/tests/e2e/test_e2e_subscriptions.py` — 5 SDK-driven e2e tests covering SUB-01/02/03/05

**Modified:**
- `agent-brain-mcp/agent_brain_mcp/server.py` — tuple return shape; try/finally in run_stdio
- `agent-brain-mcp/agent_brain_mcp/subscriptions/manager.py` — explicit CancelledError clause
- `agent-brain-mcp/tests/test_initialize.py` — pin tuple shape + identity-equality with private attr
- `agent-brain-mcp/tests/test_subscribe_handler.py` — tuple unpack
- `agent-brain-mcp/tests/test_tools_list.py` — tuple unpack
- `agent-brain-mcp/tests/test_resources_read.py` — tuple unpack
- `agent-brain-mcp/tests/test_resources_read_parameterized.py` — tuple unpack
- `agent-brain-mcp/tests/test_resources_read_file.py` — tuple unpack
- `agent-brain-mcp/tests/test_resources_templates_list.py` — tuple unpack
- `agent-brain-mcp/tests/test_resources_list.py` — tuple unpack
- `agent-brain-mcp/tests/test_prompts_list.py` — tuple unpack
- `agent-brain-mcp/tests/test_prompts_get.py` — tuple unpack
- `agent-brain-mcp/tests/test_each_tool.py` — tuple unpack
- `agent-brain-mcp/tests/test_cancellation.py` — tuple unpack
- `agent-brain-mcp/tests/test_e2e_stdio.py` — subprocess-embedded script unpacks both + forwards manager
- `agent-brain-mcp/tests/e2e/test_e2e_resources.py` — subprocess-embedded script unpacks both + forwards manager
- `docs/plans/2026-06-02-mcp-v2-subscriptions.md` — §3.3.1 Phase 52 ship-outcome subsection appended

## Decisions Made

(See `key-decisions` in frontmatter above — 10 decisions documented.)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] SDK `BrokenResourceError` `BaseExceptionGroup` surfacing in disconnect test**
- **Found during:** Task 3 (running `test_disconnect_cleans_up_polling_tasks` against the freshly-shipped run_stdio cleanup hook).
- **Issue:** The MCP SDK's `stdio_client` task group surfaces an `ExceptionGroup` containing `anyio.BrokenResourceError` when the subprocess emits a final in-flight notification AFTER the client closed its read side. This is structurally harmless (the subprocess's write succeeds; the parent has just stopped reading) and is EXACTLY the scenario Plan 04's cleanup hook is designed to handle gracefully — but it surfaces as a test failure because the exception escapes the test's `async with` blocks.
- **Fix:** Test catches `BaseExceptionGroup`, filters out `anyio.BrokenResourceError` instances via `isinstance`, and re-raises any other exception type via a new `BaseExceptionGroup` constructed from the residual exceptions. Routed through `builtins.BaseExceptionGroup` so the Python 3.10 minimum doesn't trip mypy/ruff (`F821 Undefined name BaseExceptionGroup`). The filter is documented inline with a multi-line comment explaining why the noise is safe.
- **Files modified:** `agent-brain-mcp/tests/e2e/test_e2e_subscriptions.py`
- **Verification:** Test passes 3/3 runs (stability check); the disconnect-cleanup contract is still verified by the counter-based primary assertion that follows.
- **Committed in:** `d0a3287`

**2. [Rule 1 — Bug] Stub status payload monotonic-counter pattern (test fixture, not production)**
- **Found during:** Task 3 (running `test_two_sessions_independent_subscriptions`).
- **Issue:** Initial design used a flip-on-poll-2 stub: empty `indexed_folders` on poll #1, populated on poll #2+. After 2 distinct canonical hashes, the diff-suppression suppressed subsequent emissions and the notification stream stalled. The two-sessions test needed >2 distinct hashes across a 1.8s window because session B keeps receiving notifications BOTH during and after session A's lifetime.
- **Fix:** Stub now uses always-changing counter fields (`total_documents=n`, `total_chunks=n*10`) so the canonical hash differs on every poll. The Phase 52 production policy (Plan 03's `CorpusStatusPolicy`) still diff-suppresses correctly via the `request_id`-drop pattern — the e2e stub is a test fixture that exercises the polling lifecycle, not a policy under test.
- **Files modified:** `agent-brain-mcp/tests/e2e/test_e2e_subscriptions.py` (test fixture only — no policy change)
- **Verification:** `test_two_sessions_independent_subscriptions` passes 3/3 runs; the other 4 e2e tests are unaffected.
- **Committed in:** `d0a3287`

**3. [Rule 1 — Bug] `B017` ruff rule — bare `Exception` in `pytest.raises`**
- **Found during:** Task 2 (ruff check after writing `test_method_cannot_be_overridden_to_arbitrary_string`).
- **Issue:** Initial test used `with pytest.raises(Exception)` to assert that a wrong `method` string raises SOMETHING at parse time. Ruff `B017` flags this as overly-broad. The actual exception is `pydantic.ValidationError`.
- **Fix:** Imported `pydantic.ValidationError` lazily inside the test (since the test is the only consumer in that module) and tightened the assertion to `pytest.raises(ValidationError)`.
- **Files modified:** `agent-brain-mcp/tests/test_notification_shape.py`
- **Verification:** `poetry run ruff check tests/test_notification_shape.py` clean; the test still passes.
- **Committed in:** `839b24b`

---

**Total deviations:** 3 auto-fixed (1 blocking + 2 bugs)

**Impact on plan:** All three deviations are surface-level test-implementation refinements — none affected the plan's intended semantics or required new code in the production paths. Deviation 1 (BrokenResourceError filter) is the most consequential because it documents a real SDK noise pattern that Phase 53's HTTP analog tests will likely also need to handle (with a different exception type for HTTP framing — added to the risk register in the v2 design doc §3.3.1). Deviations 2 and 3 are pure test hygiene.

## Issues Encountered

- **`ClientSession.message_handler` spike** — Plan 04's risk register flagged this as "unknown until spiked." The MCP SDK 1.12.x exposes a `message_handler` kwarg on `ClientSession.__init__` that receives `RequestResponder | ServerNotification | Exception` (verified at `mcp/client/session.py:121` + `:601`). `ServerNotification` is a discriminated union whose `.root` is the concrete notification type. The filter pattern `isinstance(msg, ServerNotification) and isinstance(msg.root, ResourceUpdatedNotification)` works cleanly — no need to read the underlying `read` stream manually. Documented in `_make_collector` docstring so future contributors don't repeat the spike.
- **Two-sessions cross-process semantic vs CONTEXT decision A** — Plan 04's plan flagged this as a design risk: for stdio, each `stdio_client` invocation spawns its own MCP subprocess, so "two sessions" become two processes, each with their own `SubscriptionManager`. The real same-process-multi-session test is Plan 01's `test_two_sessions_for_same_uri_get_independent_tasks` which runs inside a single asyncio loop. Plan 04's e2e test is scoped to the cross-process isolation property (closing session A's process doesn't affect session B's notification stream) — documented in the test docstring and in the v2 design doc §3.3.1 carry-forward note.
- **Subprocess-script env-var parameterization** — the test fixture parameterizes per-test cadence and behavior via `StdioServerParameters.env` rather than per-test script files. Keeps the fake-server script reusable across all 5 e2e tests and avoids fixture-script explosion. The pattern mirrors `tests/test_e2e_stdio.py`'s `E2E_SANDBOX_ROOT` env var usage.

## User Setup Required

None — this is library-internal code with no external services. The new env vars for `MCPSubscriptionSettings` were introduced in Plan 03 and are unchanged.

## Next Phase Readiness

**Phase 52 is shipped.** All five SUB requirements (SUB-01 through SUB-05) are now complete and validated end-to-end against the real MCP wire via the official Python SDK. The verifier (gsd-verifier in Wave 4 immediately following Plan 04's metadata commit) will re-confirm against the acceptance criteria.

**Phase 53 (Streamable HTTP transport) is unblocked** and inherits the disconnect-cleanup design from Phase 52:

- The `try/finally` pattern that Plan 04 added to `run_stdio` is the template for Phase 53's HTTP session-manager analog. Each HTTP session needs an equivalent hook so HTTP-disconnected sessions don't leak polling tasks.
- The `BrokenResourceError` filter pattern in `test_disconnect_cleans_up_polling_tasks` may need to extend to HTTP-transport e2e tests with a different exception type (HTTP framing layer raises differently on disconnect). The risk note is in the v2 design doc §3.3.1.
- `build_server()`'s tuple return shape is transport-agnostic — Phase 53's HTTP listener can use the same `(server, manager)` unpacking and call `manager.cleanup_all()` from its own session-lifecycle hook.

**Phase 54 (9 remaining MCP tools — TOOL-04 `wait_for_job` specifically) is also unblocked.** `SubscriptionManager.start_polling()` signature is LOCKED at this point:

```python
start_polling(
    session: Any,
    uri: str,
    interval_s: float,
    fetcher: Fetcher,
    on_change: OnChange,
    drop_keys: set[str] | frozenset[str] | None = None,
) -> None
```

`wait_for_job` will import this verbatim and raise `SubscriptionTerminated(final_progress_payload)` from its one-shot polling fetcher when the job reaches a terminal status. The polling primitive's contract is locked; any change is a cross-phase breaking change requiring deliberate coordination.

**v10.2 milestone progress:** Phase 52 closes the third of six phases; remaining work is Phase 53 (HTTP transport, independent of 52), Phase 54 (tools — depends on 52's primitive), and Phase 55 (validation + QA gate — last).

## Self-Check: PASSED

- [x] `agent-brain-mcp/agent_brain_mcp/server.py` modified — build_server returns tuple, run_stdio has try/finally hook
- [x] `agent-brain-mcp/agent_brain_mcp/subscriptions/manager.py` modified — explicit CancelledError clause
- [x] `agent-brain-mcp/tests/test_notification_shape.py` exists (created) — 9 SUB-04 conformance tests
- [x] `agent-brain-mcp/tests/e2e/test_e2e_subscriptions.py` exists (created) — 5 SDK-driven e2e tests
- [x] `agent-brain-mcp/tests/test_initialize.py` modified — pins tuple shape + identity-equality with private attr
- [x] All 15 other build_server() test callsites updated to unpack the tuple
- [x] `docs/plans/2026-06-02-mcp-v2-subscriptions.md` modified — §3.3.1 Phase 52 ship-outcome subsection appended
- [x] Commit `2d16b68` exists in `git log` (feat: build_server tuple + run_stdio cleanup + CancelledError clause)
- [x] Commit `839b24b` exists in `git log` (test: SUB-04 notification shape conformance)
- [x] Commit `d0a3287` exists in `git log` (test: SUB-01/02/03/05 e2e SDK subscriptions)
- [x] Commit `638ddcc` exists in `git log` (docs: §3.3.1 Phase 52 ship outcome)
- [x] `poetry run pytest tests/e2e/test_e2e_subscriptions.py -v -x -m e2e` — 5/5 pass, 3/3 consecutive stability runs
- [x] `poetry run pytest tests/test_notification_shape.py -v` — 9/9 pass
- [x] `poetry run pytest -m ''` (full MCP suite) — 265 passed (was 241 in Plan 03; +24 across Plans 04 + 03 e2e re-included), 28 skipped
- [x] `poetry run black --check agent_brain_mcp tests` — clean (62 files)
- [x] `poetry run ruff check agent_brain_mcp tests` — clean
- [x] `poetry run mypy agent_brain_mcp` — clean (29 source files, 0 issues)
- [x] `task check:layering` — 3 contracts kept, 0 broken
- [x] `task before-push` — exit 0 (416 tests across the monorepo, 80% coverage)
- [x] `task pr-qa-gate` — exit 0
- [x] No edits to Plan 01's locked public surface (`SubscriptionManager.start_polling` signature unchanged; cleanup_session / cleanup_all / unsubscribe / is_subscribed / active_count all unchanged)
- [x] No edits to Plan 02's handler dispatch logic (only the `build_server` return shape changed)
- [x] No edits to Plan 03's per-URI policies (`SUBSCRIPTION_POLICIES` registry, fetcher factories, `SubscriptionTerminated` sentinel all unchanged)
- [x] No new dependencies added — uses MCP SDK 1.12 `ClientSession.message_handler` + stdlib `hashlib` + existing `pytest-asyncio`

---
*Phase: 52-resource-subscriptions*
*Completed: 2026-06-03*
