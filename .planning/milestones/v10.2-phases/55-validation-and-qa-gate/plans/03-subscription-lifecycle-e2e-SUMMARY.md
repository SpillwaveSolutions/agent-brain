---
phase: 55-validation-and-qa-gate
plan: 03
subsystem: testing
tags: [mcp, contract-tests, subscriptions, pytest, mcp-sdk, stdio, val-02, sub-05, message-handler, stderr-scrape, popen, disconnect-cleanup, cadence-override]

requires:
  - phase: 55-validation-and-qa-gate
    provides: mcp_stdio_session factory (callable returning async context manager — Plan 01) + contract pytest marker + autouse D-17 orphan scan + _DEFAULT_RESPONSES extended with running-job stub job_abc
  - phase: 52-resource-subscriptions
    provides: SUBSCRIPTION_POLICIES registry (3 concrete policies + resolve_policy lookup) + SubscriptionManager.cleanup_all + run_stdio try/finally cleanup hook emitting "subscription cleanup: cancelled N polling task(s) on session close" log line at server.py:984-987
  - phase: 51-deferred-uri-schemes
    provides: known-URI gate accepts job:// + corpus://status + corpus://folders for resources/subscribe dispatch

provides:
  - tests/contract/test_subscription_lifecycle.py — 4 subscription contract tests (3 parameterized happy-path + 1 disconnect-cleanup)
  - tests/contract/conftest.py extensions — message_handler kwarg on mcp_stdio_session factory + fast_cadence_subscription_module session-scoped fixture + mcp_stdio_subprocess_handle factory + widened orphan-scan pgrep alternation
  - bundled fast-cadence subscription script — _FAST_CADENCE_SUBSCRIPTION_SCRIPT monkeypatches SUBSCRIPTION_POLICIES[*].interval_s from env vars (default 0.5s) BEFORE build_server runs; logging.basicConfig(stream=sys.stderr, level=INFO) configured so the Phase 52 disconnect-cleanup log line surfaces to the parent test
  - follow-up GitHub issue #194 — proposes GET /mcp/subscriptions/__debug endpoint gated behind AGENT_BRAIN_DEBUG=1 for v10.3+ (cleaner instrumentation than stderr scrape)

affects: [55-04-http-transport-contract, 55-05-root-qa-gate]

tech-stack:
  added: []  # No new runtime deps — uses existing mcp 1.12.x SDK + httpx MockTransport + pytest-asyncio + select (stdlib)
  patterns:
    - "Cadence override via subprocess script monkeypatch — overrides SUBSCRIPTION_POLICIES[*].interval_s on the policy instances in the bundled subprocess script before build_server reads the registry (env vars AGENT_BRAIN_MCP_CADENCE_{JOB,STATUS,FOLDERS}_S, default 0.5s each). Avoids needing a Phase 52 settings hot-reload knob and avoids gating tests behind @pytest.mark.slow."
    - "Notification capture via SDK message_handler — extended mcp_stdio_session factory accepts a message_handler kwarg that forwards into ClientSession(read, write, message_handler=...); callback filters on ServerNotification.root and appends ResourceUpdatedNotification to a list the test asserts against. Public surface preserved for Plans 02/04 (default None → SDK's _default_message_handler unchanged)."
    - "Raw Popen handle for disconnect test — mcp_stdio_subprocess_handle factory yields a subprocess.Popen with PIPE'd stdin/stdout/stderr so the test can hand-frame JSON-RPC requests on stdin and force-close stdin without going through the SDK's stdio_client teardown (which sends SIGTERM rather than EOF). Required because SUB-05's spec contract is 'EOF triggers cleanup'."
    - "Stderr-log-scrape verification (CONTEXT D-06 fallback) — Phase 52 ships no observability endpoint for subscription counts; the disconnect test reads the subprocess's stderr looking for the literal Phase 52 log line 'subscription cleanup: cancelled' emitted at server.py:984-987. select+os.read non-blocking drain lets the test scrape WHILE the subprocess is still in its finally block, with a 5s deadline budget."
    - "Test-only logging.basicConfig in the bundled subprocess script — agent_brain_mcp itself does not configure logging (production MCP servers inherit it from the LLM client / plugin host), so logger.info calls would silently drop without basicConfig(level=INFO, stream=sys.stderr) at the top of the fast-cadence script. The disconnect test's stderr scrape depends on this; production servers are unaffected."

key-files:
  created:
    - agent-brain-mcp/tests/contract/test_subscription_lifecycle.py
    - .planning/phases/55-validation-and-qa-gate/plans/03-subscription-lifecycle-e2e-SUMMARY.md
  modified:
    - agent-brain-mcp/tests/contract/conftest.py

key-decisions:
  - "Cadence override strategy: bundled subprocess script monkeypatches policy instances in SUBSCRIPTION_POLICIES before build_server runs (chose over option B 'factory's response_overrides' because cadence is a per-policy attribute not a response; chose over option D 'mark @pytest.mark.slow' because that defeats the contract suite's snapshot-fast-feedback contract). Env-var-driven so each test can dial cadence independently (default 0.5s uniformly applied; Plan 03 happy-path tests use the default)."
  - "Notification capture via SDK message_handler kwarg, NOT custom session implementation. Extending the existing mcp_stdio_session factory with a message_handler kwarg preserves the locked Plan 01 fixture name and adds zero churn to Plans 02 (16-tool matrix) and Plan 04 (HTTP transport). Plans 02/04 ignore the kwarg (default None → SDK's _default_message_handler)."
  - "Disconnect test uses raw subprocess.Popen, NOT the mcp_stdio_session factory. The SDK's stdio_client wraps stdin/stdout in an anyio task group whose teardown sends SIGTERM. SUB-05's spec contract is 'EOF triggers cleanup' — a different signal path than SIGTERM (though Phase 52's finally handles both). The raw-Popen path lets us isolate the EOF code path, which is what an LLM client closing its stdio pipe would actually do."
  - "Stderr log scrape, NOT observability endpoint (CONTEXT D-06 fallback). Phase 52 did not ship /mcp/subscriptions/__debug; rather than add it in Phase 55 (which would violate CONTEXT D-19 'do not patch Phase 50-54 deliverables in Phase 55'), Plan 03 scrapes the Phase 52 log line literal 'subscription cleanup: cancelled' (emitted at server.py:984-987 via logger.info). Follow-up issue #194 filed to expose a debug endpoint in v10.3+."
  - "Logging.basicConfig added to the bundled subprocess script ONLY (test-only setup). agent_brain_mcp itself stays unchanged — production MCP servers inherit logging configuration from the LLM client / plugin host runtime. Without this, the disconnect test's stderr scrape would always fail because the default root logger has no handler attached and logger.info calls silently drop."
  - "Disconnect test subscribes to job://job_abc (the v1 _DEFAULT_RESPONSES stub returning status='running', progress=50%). The stub never flips to a terminal status, so the JobPolicy fetcher never raises SubscriptionTerminated and the polling task stays alive until the disconnect — exactly the SUB-05 scenario. Using job_done (terminal) would cause Phase 52's _poll_loop to auto-exit before the disconnect could test the cleanup hook."
  - "Cadence assertion window = cadence × 1.5 (per CONTEXT D-07). With the 0.5s override, the window is 0.75s — long enough for one poll cycle plus ~250ms CI jitter budget. Phase 52's _poll_loop emits the first observation immediately on subscribe (CONTEXT specifics: 'first poll always fires'), so even a single iteration produces ≥1 notification."
  - "Orphan-scan pgrep widened to alternation 'fake_(contract|subscription)_server.py' so subscription-lifecycle orphans surface in the SAME autouse D-17 safety net that catches Plan 01/02 contract-test orphans. No new fixture; just a regex update."

patterns-established:
  - "Subscription contract test layout: parametrized (uri, cadence_s, mode) matrix + 1 disconnect-cleanup test using raw Popen. Plan 04 may inherit the matrix pattern for HTTP-transport SSE framing tests if their cadence assertions follow a similar shape."
  - "Test-script logging.basicConfig at script-top (BEFORE importing agent_brain_mcp.server) — required pattern for any contract test that asserts on logger.info output, since the MCP package does not configure logging itself."
  - "Cadence-override-via-script-monkeypatch pattern: subprocess scripts that need to compress Phase 52's production cadences for CI speed should monkeypatch SUBSCRIPTION_POLICIES[*].interval_s before build_server runs. Env-var-driven so tests can dial cadence individually."

requirements-completed: [VAL-02]

duration: 10min
completed: 2026-06-03
---

# Phase 55 Plan 03: Subscription Lifecycle E2E Test Summary

**4 new SDK-driven contract tests close VAL-02 / Phase 52 SUB-05 end-to-end: 3 parameterized happy-path lifecycle assertions over the three Phase 52 subscribable URIs (`job://`, `corpus://status`, `corpus://folders`) plus 1 disconnect-cleanup test verifying `run_stdio`'s `finally` hook fires via Phase 52's `"subscription cleanup: cancelled N polling task(s)"` log line — stderr-scrape fallback per CONTEXT D-06 because Phase 52 ships no observability endpoint (follow-up issue #194 filed).**

## Performance

- **Duration:** 10 min 20 sec
- **Started:** 2026-06-03T20:35:30Z
- **Completed:** 2026-06-03T20:45:50Z
- **Tasks:** 2 atomic commits on `main`
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- **VAL-02 closed end-to-end.** All three Phase 52 subscribable URIs now have an MCP-SDK-driven contract test pinning the subscribe → wait → assert ≥1 `notifications/resources/updated` → unsubscribe round-trip. The matrix dimension `(uri, cadence_s, mode)` mirrors CONTEXT D-05's recommended shape.
- **SUB-05 disconnect cleanup pinned at the wire boundary.** The disconnect test drives raw JSON-RPC framing on a `subprocess.Popen.stdin`, force-closes the pipe, and scrapes stderr for the Phase 52 log line literal — proves `run_stdio`'s `finally` block actually runs and `cleanup_all()` cancels the polling task. If Phase 52's cleanup hook regresses in any v10.3+ change, this test fails loudly with the captured stderr in the assertion message.
- **Cadence override mechanism in place.** The bundled fast-cadence subscription script (`fake_subscription_server.py`) monkeypatches all three `SubscriptionPolicy.interval_s` attributes BEFORE `build_server` runs, compressing Phase 52's 30s `corpus://status` cadence into the contract suite's sub-second budget. Env vars `AGENT_BRAIN_MCP_CADENCE_{JOB,STATUS,FOLDERS}_S` let future tests dial cadence per-test.
- **Contract suite stays under budget.** Plan 03 adds 4.32s to the contract suite (16.65s → 20.97s) — well under the +20s acceptance threshold. All 4 new tests run stdio-only per CONTEXT D-08 (Plan 04 will cover HTTP transport's SSE framing).
- **Public fixture surface preserved.** The `mcp_stdio_session` factory gained an additive `message_handler` kwarg; Plans 02 and 04 are unaffected (default `None` → SDK's `_default_message_handler`). The new `mcp_stdio_subprocess_handle` factory is an independent fixture that Plan 04 may reuse if the HTTP-transport disconnect test needs analogous raw-process access.
- **Follow-up filed for clean observability.** GitHub issue #194 proposes `GET /mcp/subscriptions/__debug` gated behind `AGENT_BRAIN_DEBUG=1` for v10.3+; v10.2 ships the stderr-scrape fallback as planned.
- **All quality gates pass:** `task before-push` exit 0 (416 monorepo CLI tests + 460 MCP fast-path), `task contract` exit 0 (43 tests in 20.97s — was 39 in 16.65s), `task check:layering` 3/3 contracts kept (164 files, 414 deps), MCP `task pr-qa-gate` exit 0 with coverage above 80% floor (unchanged — Plan 03 adds tests only).

## Task Commits

Each task was committed atomically on `main`:

1. **Task 1: extend `tests/contract/conftest.py`** — `0c156fd` (test)
   - Added `_FAST_CADENCE_SUBSCRIPTION_SCRIPT` + `fast_cadence_subscription_module` fixture (script monkeypatches SUBSCRIPTION_POLICIES cadences)
   - Extended `mcp_stdio_session` factory with `message_handler` kwarg (additive, default None preserves Plans 02/04 behavior)
   - Added `mcp_stdio_subprocess_handle` factory (raw Popen for disconnect test)
   - Widened orphan-scan pgrep to `fake_(contract|subscription)_server.py` alternation
2. **Task 2: subscription lifecycle test file + logging config** — `0c3c9ec` (test)
   - Created `tests/contract/test_subscription_lifecycle.py` with 3 parameterized happy-path tests + 1 disconnect-cleanup test
   - Added `logging.basicConfig(stream=sys.stderr, level=INFO)` to the fast-cadence script so the Phase 52 log line surfaces (test-only — production MCP servers inherit logging from the LLM client runtime)

**Plan metadata:** (this commit, after SUMMARY.md + STATE.md + ROADMAP.md + REQUIREMENTS.md updates)

## Files Created/Modified

- `agent-brain-mcp/tests/contract/test_subscription_lifecycle.py` — 4 subscription contract tests: 3 parameterized happy-path tests (job://, corpus://status, corpus://folders) + 1 disconnect-cleanup test. Notification capture via SDK message_handler callback; cadence assertions use cadence × 1.5 window; disconnect verification via stderr log scrape.
- `agent-brain-mcp/tests/contract/conftest.py` — extended with `_FAST_CADENCE_SUBSCRIPTION_SCRIPT` + `fast_cadence_subscription_module` session-scoped fixture + `mcp_stdio_subprocess_handle` factory + `message_handler` kwarg on `mcp_stdio_session`. Orphan-scan pgrep alternation widened. Test-only `logging.basicConfig` added to the bundled subscription script.

## Decisions Made

- **Cadence override via subprocess-script monkeypatch (chose over factory `response_overrides`, env-var-on-policy, or `@pytest.mark.slow`).** The cadence is a `SubscriptionPolicy.interval_s` attribute on a *dataclass instance* in the SUBSCRIPTION_POLICIES dict — mutating it directly in the subprocess script before `build_server` runs is the simplest mechanism. `response_overrides` is for HTTP responses, not policy attributes. Phase 52 exposes the folders cadence via env var but not job/status; uniform env-var override on all three is cleaner. Marking the test `@pytest.mark.slow` defeats the contract suite's sub-30s contract.
- **Notification capture via `message_handler` kwarg on the existing factory (chose over a parallel custom-fixture implementation).** Extending `mcp_stdio_session` with a `message_handler` kwarg is purely additive — Plans 02/04 inherit the same fixture and ignore the kwarg. A parallel fixture would have duplicated the `stdio_client` + `ClientSession` setup logic and risked drift.
- **Raw `Popen` handle for the disconnect test (chose over `mcp_stdio_session`).** The SDK's `stdio_client` wraps stdin/stdout in an anyio task group whose teardown sends SIGTERM, not EOF. SUB-05's spec contract is "client disconnect (stdio EOF) triggers cleanup." Testing via `stdio_client` would conflate SIGTERM and EOF cleanup paths; the raw `Popen` approach lets us isolate EOF, which is what an LLM client closing its stdio pipe actually does. Phase 52's `finally` handles both signal paths but verifying them independently matters for regression isolation.
- **Stderr log-scrape verification (CONTEXT D-06 fallback path).** Phase 52 did not ship a subscription-count observability endpoint. Adding one in Phase 55 would violate CONTEXT D-19 ("do not patch Phase 50-54 deliverables here"). The Phase 52 cleanup log line is a stable observable: `logger.info("subscription cleanup: cancelled %d polling task(s) on session close", cleaned)` at `server.py:984-987`. The literal substring `"subscription cleanup: cancelled"` is a robust anchor that survives the `%d` format placeholder. Follow-up #194 filed to add `GET /mcp/subscriptions/__debug` in v10.3+ for cleaner instrumentation.
- **Test-only `logging.basicConfig` in the fast-cadence subprocess script.** `agent_brain_mcp` itself does not configure logging — production MCP servers inherit logging from the LLM client / plugin host (e.g., Claude Code's plugin-runtime stderr capture, Codex's logging setup). Without `basicConfig(level=INFO, stream=sys.stderr)` at the top of the bundled script, the default root logger has no handler and `logger.info` calls silently drop, making the disconnect test's stderr scrape always fail. The configuration is scoped to the test-only script so production behavior is unaffected.
- **Disconnect test subscribes to `job://job_abc`, not `job://job_done`.** `job_abc` is the v1 `_DEFAULT_RESPONSES` stub returning `status="running", progress=50%` — the polling task stays alive because the JobPolicy fetcher never sees a terminal status. `job_done` (added in Plan 01) is terminal; subscribing to it would auto-exit via `SubscriptionTerminated` before the disconnect could test the cleanup hook. The wait_for_job tests in Plan 02 use `job_done` for the opposite reason (force fast termination); the SUB-05 disconnect test needs the opposite scenario.
- **Cadence assertion window = cadence × 1.5 (CONTEXT D-07).** With the 0.5s override, the window is 0.75s. Phase 52's `_poll_loop` emits the first observation immediately on subscribe (no initial sleep — CONTEXT specifics: "first poll always fires"), so even one polling cycle is enough to produce ≥1 notification. The 1.5× multiplier covers CI runner jitter without inflating the suite duration.
- **Orphan-scan pgrep widened, not duplicated.** The Plan 01 autouse fixture caught only `fake_contract_server.py`. Plan 03 widens to `fake_(contract|subscription)_server.py` alternation so subscription-lifecycle orphans surface in the same pass. A separate autouse fixture would have been redundant and risked race conditions between the two scans.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added `logging.basicConfig` to the fast-cadence subprocess script**

- **Found during:** Task 2 (running the initial disconnect test)
- **Issue:** First disconnect-test run failed with empty stderr — the assertion's captured-stderr message showed `assert 'subscription cleanup: cancelled' in ''`. Root cause: `agent_brain_mcp` does NOT configure logging anywhere (verified via `grep -rn "basicConfig\|StreamHandler\|setup_logging" agent_brain_mcp/` returning no results). The `logger = logging.getLogger(__name__)` at `server.py:75` creates a logger with no handler; Python's default behavior for handlerless loggers is to silently drop `logger.info` calls. Without log output on stderr, the test had no observable evidence that `cleanup_all()` ran.
- **Fix:** Added `logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(name)s %(levelname)s %(message)s")` at the top of `_FAST_CADENCE_SUBSCRIPTION_SCRIPT` BEFORE the `agent_brain_mcp.server` import. This attaches a StreamHandler to stderr so `logger.info` calls in the subprocess surface to the parent test's stderr drain. Scoped to the test-only script so production MCP servers (which inherit logging from the LLM client runtime) are unaffected.
- **Files modified:** `agent-brain-mcp/tests/contract/conftest.py` (the inline subscript)
- **Verification:** Disconnect test now passes in 1.18s, captured stderr contains `agent_brain_mcp.server INFO subscription cleanup: cancelled 1 polling task(s) on session close`.
- **Committed in:** `0c3c9ec` (Task 2 — the fix was folded into the same commit as the test file because they're coupled)

### Acknowledged Gaps (NOT auto-fixed — out of Phase 55 scope)

**2. [Rule 4 — would be architectural] No `/mcp/subscriptions/__debug` endpoint added.**

- **Found during:** Task 2 implementation planning
- **Issue:** Phase 52 did not ship a per-session subscription-count observability surface. The disconnect-cleanup test could read this endpoint directly to verify count==0 after disconnect; without it, the test falls back to stderr log scraping.
- **Why not auto-fixed:** Adding an endpoint to `agent_brain_mcp.server` would violate CONTEXT D-19 ("Phase 55 does NOT patch Phase 50-54 deliverables") and CONTEXT specifics ("recommended fallback for D-06: file as a Phase 52 follow-up issue rather than a Phase 55 task"). The plan explicitly anticipated this gap.
- **Mitigation:** Follow-up GitHub issue #194 filed via `gh issue create` proposing the endpoint for v10.3+. The stderr-scrape verification mechanism works today; the follow-up replaces it with cleaner instrumentation later. Both the issue body and this SUMMARY document the chain so the v10.3 planner has full context.
- **Recorded for v10.3+ planning:** Follow-up issue #194 — https://github.com/SpillwaveSolutions/agent-brain/issues/194

---

**Total auto-fix deviations:** 1 (missing critical — logging configuration). One acknowledged gap explicitly carried as a v10.3+ follow-up per the plan's design.

## Issues Encountered

- **Empty stderr on first disconnect-test run** — root cause was missing logging configuration in the subprocess script (see Deviation #1 above). Fixed by adding `logging.basicConfig` to the fast-cadence script.
- **Phase 52 didn't ship an observability endpoint** — anticipated by CONTEXT D-06; resolved via the stderr-scrape fallback + GitHub follow-up #194.
- **`gh issue create --label "follow-up"` failed** — the `follow-up` label doesn't exist in the SpillwaveSolutions/agent-brain repo. Retried without `--label` and the issue created successfully (#194). Not a Plan 03 concern; the follow-up record is complete.

## Self-Check

Verified after writing SUMMARY.md:

- `agent-brain-mcp/tests/contract/test_subscription_lifecycle.py` → exists
- `agent-brain-mcp/tests/contract/conftest.py` → modified (new fixtures + extended factory + widened orphan scan)
- `0c156fd` (Task 1 commit) → in git log
- `0c3c9ec` (Task 2 commit) → in git log
- `task contract` → exit 0 (43 passed in 20.97s — was 39 in 16.65s)
- `task before-push` → exit 0 (416 monorepo CLI tests + 460 MCP fast-path + format/lint/typecheck/coverage all clean)
- `task check:layering` → exit 0 (3/3 contracts kept, 164 files, 414 deps)
- mcp default fast-path `pytest tests -v` → 460 passed, 90 deselected (no regression from Plans 01/02 baseline)
- GitHub follow-up issue #194 filed and visible at https://github.com/SpillwaveSolutions/agent-brain/issues/194

## Self-Check: PASSED

## User Setup Required

None — no external service configuration required. Contract suite uses in-memory MockTransport backend (CONTEXT D-04).

## Next Phase Readiness

- **VAL-02 done.** The subscription lifecycle + disconnect cleanup is locked against the official MCP 1.12.x SDK over stdio. Plan 04 (HTTP transport VAL-03) inherits the `mcp_stdio_session` factory + the message_handler kwarg + the orphan-scan widening verbatim.
- **`mcp_stdio_subprocess_handle` factory available for Plan 04** if the HTTP transport's disconnect test needs analogous raw-process control (the HTTP transport closes via TCP RST rather than stdin EOF, so Plan 04 may need its own subprocess factory — the pattern is established here).
- **Follow-up #194 tracked for v10.3+** — the observability endpoint proposal documents the entire fallback chain for the v10.3 planner. Stderr-scrape verification remains in place until the endpoint lands.
- 22/24 plans complete across v10.2 milestone. Phase 55 plan 3/5 done. Plan 04 (HTTP transport contract VAL-03) is the next workable plan within Phase 55.

---
*Phase: 55-validation-and-qa-gate*
*Plan: 03 — subscription lifecycle E2E*
*Completed: 2026-06-03*
