---
phase: 52-resource-subscriptions
plan: 01
subsystem: mcp
tags: [mcp, subscriptions, asyncio, sha256, polling, agent_brain_mcp]

# Dependency graph
requires:
  - phase: 51-uri-schemes-and-templates
    provides: parameterized URI schemes (job://, chunk://, graph-entity://, file://); subscribable allowlist gates only job:// and corpus://*
provides:
  - SubscriptionManager class with start_polling / unsubscribe / cleanup_session / cleanup_all / is_subscribed / active_count
  - canonical_hash() helper that drops volatile keys at every nesting depth before SHA-256
  - DEFAULT_DROP_KEYS frozenset {timestamp, updated_at, elapsed_ms, polled_at, now}
  - SubscribableUriRejected(McpError) with reason in {unknown_uri, not_subscribable}
  - Fetcher / OnChange callable type aliases for Phase 54 reuse
affects: [52-02-subscribe-handlers, 52-03-per-uri-policies, 52-04-disconnect-cleanup, 54-04-wait-for-job]

# Tech tracking
tech-stack:
  added: []  # no new dependencies — uses stdlib asyncio + hashlib + json + existing mcp SDK
  patterns:
    - "Per-session subscription registry keyed by (id(session), uri)"
    - "Synchronous registry write before asyncio.create_task — guarantees safe immediate-unsubscribe"
    - "try/finally defense-in-depth with identity-check guard against re-subscribe race"
    - "Canonical-hash diff-suppression with recursive volatile-key strip"

key-files:
  created:
    - agent-brain-mcp/agent_brain_mcp/subscriptions/__init__.py
    - agent-brain-mcp/agent_brain_mcp/subscriptions/manager.py
    - agent-brain-mcp/agent_brain_mcp/subscriptions/payloads.py
    - agent-brain-mcp/agent_brain_mcp/subscriptions/errors.py
    - agent-brain-mcp/tests/subscriptions/__init__.py
    - agent-brain-mcp/tests/subscriptions/test_manager.py
    - agent-brain-mcp/tests/subscriptions/test_payloads.py
  modified: []

key-decisions:
  - "Public API surface (start_polling signature + canonical_hash + DEFAULT_DROP_KEYS + SubscribableUriRejected) is LOCKED — Plans 02/03/04 and Phase 54 TOOL-04 (wait_for_job) all import these symbols verbatim. Documented in every module-level docstring."
  - "Synchronous registry pop in unsubscribe / cleanup_session / cleanup_all: when a task is cancelled BEFORE its coroutine starts running, asyncio skips the body entirely and try/finally never runs. The primary cleanup path is now synchronous; the finally block remains as defense-in-depth for the case where the loop crashes mid-iteration (uses identity check to avoid evicting a re-subscribe)."
  - "Fetcher exception inside the polling loop is logged and the loop continues to the next interval. A transient HTTP 5xx from agent-brain-server must not tear down a long-running subscription."
  - "Non-serializable payload falls through with an empty-string hash sentinel — forces a diff vs any real prior digest so the subscriber is poked anyway. Better to over-emit than swallow a real change."
  - "Tuples are flattened to lists inside canonical_hash because JSON has no tuple type and we want byte-stable output regardless of how the upstream HTTP client serializes its result."

patterns-established:
  - "Subscription registry: dict[tuple[int, str], asyncio.Task[None]] keyed by (id(session), uri). Plan 02 will look up by this key when ServerSession.send_resource_updated needs to fire."
  - "Polling task name format: 'agent-brain-mcp-poll:{uri}:{session_id}' for diagnostic visibility in task introspection."
  - "Module-level type aliases (Fetcher, OnChange) — Phase 54 TOOL-04 imports these so wait_for_job's progress-notification machinery matches Plan 01's polling contract by construction."

requirements-completed: [SUB-04, SUB-05]  # payload shape foundations + per-session registry. SUB-01/02/03 wait for Plan 02.

# Metrics
duration: 14min
completed: 2026-06-03
---

# Phase 52 Plan 01: Subscription manager core Summary

**Greenfield `agent_brain_mcp.subscriptions` subpackage with `SubscriptionManager` polling primitive + `canonical_hash` diff-suppression helper + `SubscribableUriRejected` error type. No MCP wire integration yet (Plans 02-04 do that) — just the data structures and the public API contract that Phase 54 `wait_for_job` will also consume.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-06-03T14:24:25Z
- **Completed:** 2026-06-03T14:38:10Z
- **Tasks:** 2 atomic commits (implementation + tests with a manager fix surfaced during test execution)
- **Files modified:** 7 created (4 source + 3 test), 0 modified outside the new subpackage

## Accomplishments

- `SubscriptionManager` class with 6 public methods (start_polling, unsubscribe, cleanup_session, cleanup_all, is_subscribed, active_count). Public API contract is locked and documented as Phase 54 TOOL-04 (`wait_for_job`) reuse target.
- `canonical_hash(payload, drop=None)` recursively strips drop-keys at every nesting depth, JSON-normalizes (sorted keys, byte-stable separators), SHA-256 hex digest. Backs `_meta.revision` in MCP notification payloads.
- `DEFAULT_DROP_KEYS` frozenset covers the 5 CONTEXT-mandated volatile keys (`timestamp`, `updated_at`, `elapsed_ms`, `polled_at`, `now`).
- `SubscribableUriRejected(McpError)` carries `reason` in `{unknown_uri, not_subscribable}` via the standard `INVALID_PARAMS` JSON-RPC code; Plan 02 wires this into the `@server.subscribe_resource()` handler.
- 39 unit tests across 2 files, 18 of which exercise the manager's asyncio behavior with real `pytest-asyncio` loops including the load-bearing race-safety test (subscribe then immediately unsubscribe → fetcher never fires, registry self-cleans).
- 88% line coverage on the MCP package overall; 96%+ on every new subscriptions module.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement subpackage (payloads, errors, manager, __init__)** - `6e354da` (feat)
2. **Task 2: Unit tests + manager cancellation-timing fix** - `a01f0b5` (test)

**Plan metadata commit:** (this SUMMARY + STATE + ROADMAP update — separate commit below)

## Files Created/Modified

- `agent-brain-mcp/agent_brain_mcp/subscriptions/__init__.py` — re-exports the 5 public symbols + 2 type aliases for Phase 54 reuse
- `agent-brain-mcp/agent_brain_mcp/subscriptions/payloads.py` — `canonical_hash()` + `DEFAULT_DROP_KEYS`, recursive depth-strip
- `agent-brain-mcp/agent_brain_mcp/subscriptions/errors.py` — `SubscribableUriRejected` MCP error with structured `data.reason`
- `agent-brain-mcp/agent_brain_mcp/subscriptions/manager.py` — `SubscriptionManager` class, ~310 LOC including docstrings
- `agent-brain-mcp/tests/subscriptions/__init__.py` — empty package marker
- `agent-brain-mcp/tests/subscriptions/test_payloads.py` — 21 tests covering hash determinism + recursive-strip + edge cases
- `agent-brain-mcp/tests/subscriptions/test_manager.py` — 18 tests covering subscribe/unsubscribe lifecycle + race safety + multi-session isolation + diff-suppression + SubscribableUriRejected smoke tests

## Decisions Made

- **Public API surface is LOCKED:** `start_polling(session, uri, interval_s, fetcher, on_change, drop_keys=None)` signature documented in module docstring as the Phase 54 `wait_for_job` reuse contract. Plans 02/03/04 import these symbols verbatim.
- **Cancellation-timing fix:** when `unsubscribe()` is called before the polling coroutine starts, asyncio skips the body entirely — the `try/finally` does NOT run. Fixed by making the primary cleanup path synchronous (pop registry + cancel task in `unsubscribe`/`cleanup_session`/`cleanup_all`), with the finally block as defense-in-depth for the case where the loop crashes mid-iteration. The finally uses an identity check (`current is asyncio.current_task()`) to avoid evicting a re-subscribed task that took the same slot.
- **Fetcher exception is logged, loop continues:** a transient HTTP 5xx from `agent-brain-server` must not tear down a long-running subscription. Loop logs via `logger.exception` and proceeds to the next interval.
- **Non-serializable payload falls through with empty-string hash sentinel:** forces a diff vs any real prior digest so the subscriber is still poked. Better to over-emit than swallow a real change.
- **Tuple → list normalization inside `canonical_hash`:** JSON has no tuple type; we flatten to list for byte-stable output regardless of how the upstream HTTP client serializes results.
- **`SubscribableUriRejected` class name pinned by Plan 01 public API** — ruff `N818` wants an `Error` suffix, but the symbol is named in the plan's acceptance criteria and is consumed by Plan 02. Added `noqa: N818` with a comment so future readers understand why.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Synchronous registry-pop in cleanup paths**
- **Found during:** Task 2 (running the unit tests)
- **Issue:** Plan §step5 says "`try / finally` ... In `finally`: `self._tasks.pop(key, None)`" as the cleanup path. But when a task is cancelled BEFORE its coroutine ever starts running (the race-safety test scenario: subscribe + unsubscribe on the next line), asyncio skips the coroutine body entirely. The `finally` never runs and the registry leaks the entry. Four tests failed against the original implementation: `test_subscribe_then_immediate_unsubscribe_cancels_before_first_poll`, `test_cleanup_session_cancels_all_uris_for_that_session`, `test_cleanup_all_cancels_everything`, `test_is_subscribed_and_active_count`.
- **Fix:** Made the primary cleanup path synchronous — `unsubscribe`/`cleanup_session`/`cleanup_all` now pop the registry AND `_last_hash` synchronously before calling `task.cancel()`. The `_poll_loop.finally` remains as defense-in-depth for the case where the loop crashes mid-iteration AFTER it actually started running. Race against re-subscribe is handled by an identity check: the finally only pops if `self._tasks.get(key) is asyncio.current_task()`.
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/subscriptions/manager.py`
- **Verification:** All 39 unit tests pass; full MCP suite (180 tests) passes; full monorepo before-push (416 tests) passes.
- **Committed in:** `a01f0b5` (Task 2 commit, alongside the tests that surfaced the bug)

---

**Total deviations:** 1 auto-fixed (Rule 1 — Bug)
**Impact on plan:** The fix preserves the plan's intended semantics (registry self-cleans on subscribe-immediate-unsubscribe race; `active_count() == 0` after `cleanup_all()`) but corrects a latent asyncio semantics misunderstanding in the plan's prescriptive implementation. The acceptance criteria are still met; only the implementation strategy was adjusted. The finally block is preserved (defense-in-depth) as the plan mandates.

## Issues Encountered

- **Ruff N818 vs. plan-pinned class name:** `SubscribableUriRejected` doesn't end in `Error` (which ruff's `N818` rule wants), but the symbol name is locked by Plan 01's acceptance criteria and Plan 02's import. Resolved with a `noqa: N818` plus inline comment so future contributors understand the constraint.
- **Black line-wrapping of the `noqa` line:** initial attempt put the noqa comment on a long line; black wrapped the class signature across multiple lines which detached the noqa from the offending token. Resolved by shortening the noqa comment so the line stays under 88 chars.

## User Setup Required

None — this is library-internal code with no external services.

## Next Phase Readiness

**Plan 02 (subscribe handlers wiring) is unblocked.** All the symbols Plan 02 needs are importable:

```python
from agent_brain_mcp.subscriptions import (
    SubscriptionManager,
    SubscribableUriRejected,
    canonical_hash,
    DEFAULT_DROP_KEYS,
    Fetcher,
    OnChange,
)
```

Plan 02 will:
1. Construct a singleton `SubscriptionManager` inside `build_server()`.
2. Add `@server.subscribe_resource()` and `@server.unsubscribe_resource()` handlers that validate the URI against the subscribable allowlist (raising `SubscribableUriRejected` for misses) and call `mgr.start_polling(...)` / `mgr.unsubscribe(...)`.
3. Flip `NotificationOptions(resources_changed=True)` at `server.py:344` and update the relevant capability tests in `test_initialize.py`.

Plans 03 (per-URI policies) and 04 (disconnect cleanup hook) build on top of Plan 02.

**Phase 54 cross-phase contract held:** `start_polling()` signature is locked. Phase 54 Plan 04 (`wait_for_job`) imports these symbols verbatim.

## Self-Check: PASSED

- [x] `agent-brain-mcp/agent_brain_mcp/subscriptions/__init__.py` exists
- [x] `agent-brain-mcp/agent_brain_mcp/subscriptions/manager.py` exists
- [x] `agent-brain-mcp/agent_brain_mcp/subscriptions/payloads.py` exists
- [x] `agent-brain-mcp/agent_brain_mcp/subscriptions/errors.py` exists
- [x] `agent-brain-mcp/tests/subscriptions/__init__.py` exists
- [x] `agent-brain-mcp/tests/subscriptions/test_manager.py` exists
- [x] `agent-brain-mcp/tests/subscriptions/test_payloads.py` exists
- [x] Commit `6e354da` exists in `git log`
- [x] Commit `a01f0b5` exists in `git log`
- [x] `poetry run pytest tests/subscriptions/ -v` — 39 passed
- [x] Full MCP suite — 180 passed
- [x] `poetry run black --check` — clean
- [x] `poetry run ruff check` — clean
- [x] `poetry run mypy agent_brain_mcp` — clean (28 source files)
- [x] `task check:layering` — 3 contracts kept, 0 broken
- [x] `task before-push` — exit 0 (416 tests across the monorepo)
- [x] No edits to `server.py`, `client.py`, or `resources/*.py`
- [x] No new dependencies added

---
*Phase: 52-resource-subscriptions*
*Completed: 2026-06-03*
