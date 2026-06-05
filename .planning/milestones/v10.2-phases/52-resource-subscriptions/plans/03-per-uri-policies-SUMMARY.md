---
phase: 52-resource-subscriptions
plan: 03
subsystem: mcp
tags: [mcp, subscriptions, polling, asyncio, sha256, pydantic, agent_brain_mcp]

# Dependency graph
requires:
  - phase: 52-resource-subscriptions
    provides: Plan 01's SubscriptionManager + canonical_hash + DEFAULT_DROP_KEYS (race-safe synchronous cleanup) — extended here with a SubscriptionTerminated catch in _poll_loop
  - phase: 52-resource-subscriptions
    provides: Plan 02's SubscriptionPolicy Protocol + empty SUBSCRIPTION_POLICIES registry + resolve_policy() — registry is populated here
provides:
  - JobPolicy (job:// scheme, 1.0s cadence, auto-terminates on completed/failed/cancelled)
  - CorpusStatusPolicy (corpus://status exact, 30.0s cadence, drops request_id+timestamps)
  - CorpusFoldersPolicy (corpus://folders exact, settings-driven cadence default 5.0s, drops last_polled but preserves last_indexed)
  - SubscriptionTerminated control-flow sentinel + _poll_loop catch branch (emits final on_change then exits cleanly)
  - MCPSubscriptionSettings (folders_active_interval_s + folders_safety_interval_s with Pydantic gt=0 validation)
  - mcp_subscription_settings module-level singleton + env-var ingestion at import time
  - SubscriptionPolicy Protocol refactored to read-only @property attributes (admits frozen-style dataclass implementations)
affects: [52-04-disconnect-cleanup, 54-04-wait-for-job, 55-04-streamable-http-e2e]

# Tech tracking
tech-stack:
  added: []  # no new deps — Pydantic + asyncio + dataclasses already in MCP package
  patterns:
    - "Module-level fetcher factories assigned to dataclass `field(default=...)` so Protocol attribute typing admits the dataclass (staticmethods fail mypy structural checks)"
    - "Protocol attributes as @property declarations to express read-only intent and accept frozen/effectively-immutable dataclass instances"
    - "SubscriptionTerminated as a control-flow sentinel (named with `# noqa: N818` — not an error, NOT an ...Error class)"
    - "Settings ingestion via env-var → float coercion → Pydantic BaseModel with gt=0 validation; RuntimeError reraise carries the offending env var name for operator debuggability"
    - "Drop-keys composed via `DEFAULT_DROP_KEYS | {extra}` per-policy — base allowlist stays canonical, per-URI extras are local to the policy class"

key-files:
  created:
    - agent-brain-mcp/tests/subscriptions/test_policies.py
    - agent-brain-mcp/tests/subscriptions/test_policy_integration.py
  modified:
    - agent-brain-mcp/agent_brain_mcp/subscriptions/policies.py
    - agent-brain-mcp/agent_brain_mcp/subscriptions/errors.py
    - agent-brain-mcp/agent_brain_mcp/subscriptions/manager.py
    - agent-brain-mcp/agent_brain_mcp/subscriptions/__init__.py
    - agent-brain-mcp/agent_brain_mcp/config.py

key-decisions:
  - "JobPolicy.fetcher raises SubscriptionTerminated(payload) when ApiClient.get_job reports status in {completed, failed, cancelled}. _poll_loop catches it, emits one final on_change with the terminal payload, then returns. The finally block + Plan 01's synchronous-cleanup paths both scrub the registry — no race against Plan 01's contract."
  - "JobPolicy with empty id (URI literally job://) raises SubscriptionTerminated immediately with {status: invalid, uri, reason: missing_job_id}. ApiClient.get_job is never called for a missing-id URI. Pinned by test_job_policy_empty_id_terminates_immediately."
  - "CorpusStatusPolicy.drop_keys = DEFAULT_DROP_KEYS | {request_id}. Uvicorn's GET /health/status embeds a per-request UUID — without dropping it the SHA-256 churns every 30s regardless of actual content. Real changes (total_chunks, indexing_in_progress) still produce hash diffs. Pinned by test_corpus_status_drop_keys_*."
  - "CorpusFoldersPolicy.drop_keys = DEFAULT_DROP_KEYS | {last_polled}. The risk note in the plan called this out specifically: last_indexed MUST NOT be in drop_keys because it is a real change signal (file watcher / index job completion updates it). Pinned by test_corpus_folders_last_indexed_change_is_not_suppressed AND test_corpus_folders_last_polled_change_is_suppressed."
  - "CorpusFoldersPolicy.__init__ accepts interval_s so the module-level registry can read mcp_subscription_settings.folders_active_interval_s at import time. The same constructor lets tests inject fast values (0.05s) for integration speed. Pinned by test_corpus_folders_policy_respects_custom_interval."
  - "MCPSubscriptionSettings uses Pydantic BaseModel with `Field(default=..., gt=0)` validation. Non-positive intervals would either starve the polling loop or invert asyncio.sleep's contract. Non-numeric env vars raise RuntimeError immediately at config-module import (clear failure mode at startup, not at runtime)."
  - "folders_safety_interval_s is exposed as a settings field with a default of 60.0s but Plan 03 does NOT wire it through the polling loop. The active 5s cadence runs the entire time a subscriber is active, and v2's design (CONTEXT decision E + specifics §3) has no separate no-subscriber branch. Documented inline as reserved for a future v3 micro-plan."
  - "SubscriptionPolicy Protocol attributes refactored from settable class-level vars (uri_pattern: str, ...) to read-only @property declarations. Mypy under strict mode refuses dataclass instances with read-only attributes as matches for a Protocol with settable attributes. Properties express the read-only intent at the type level and let mypy admit the @dataclass implementations. Runtime isinstance(p, SubscriptionPolicy) still works because Protocol is @runtime_checkable."
  - "build_fetcher refactored from @staticmethod inside the dataclass to module-level _build_*_fetcher functions assigned to `field(default=...)`. Mypy treats @staticmethod as a method descriptor, not a plain Callable, and refuses to admit the dataclass as a SubscriptionPolicy. Module-level functions produce a plain Callable instance attribute that satisfies the Protocol verbatim."
  - "SubscriptionTerminated is named with `# noqa: N818` despite ruff wanting an Error suffix. The class is a control-flow sentinel, not an error — naming it `...Error` would mislead Plan 03 readers into thinking the fetcher hit a fault. The same rationale carries over from Plan 01's SubscribableUriRejected noqa."
  - "Final-emission failures during terminal handling are caught and logged but do NOT block the loop from exiting. The loop is ending either way — a broken on_change closure must not pin the polling task open. Pinned by inline `try/except` inside the SubscriptionTerminated branch."

patterns-established:
  - "Per-policy drop_keys composition: `default_factory=lambda: DEFAULT_DROP_KEYS | {extra}` keeps the base allowlist immutable while letting each policy extend with URI-specific volatile keys."
  - "Settings env-var ingestion: float coercion errors → RuntimeError with the env var name; Pydantic ValidationError → RuntimeError with both env var names + the validator message. Operators see exactly which env var was wrong at startup."
  - "Test pattern for SubscriptionManager + policy end-to-end: real SubscriptionManager + fake ApiClient + _OnChangeRecorder mirror of test_manager.py + cleanup_all() in test teardown to drop polling tasks before the event loop tears down. Same discipline established in test_manager.py — every test that subscribes must cleanup_all."
  - "Module-level fetcher factories as named functions (_build_job_fetcher, etc.) instead of @staticmethod inside the dataclass. Keeps mypy happy with Protocol structural matching, makes the factory easily testable in isolation, and avoids the descriptor-protocol confusion."

requirements-completed: [SUB-01, SUB-02, SUB-03]
# SUB-01: job://<id> 1s polling, auto-terminate on terminal status — JobPolicy lands.
# SUB-02: corpus://status 30s polling, diff-suppressed — CorpusStatusPolicy lands.
# SUB-03: corpus://folders 5s/60s polling — CorpusFoldersPolicy lands the 5s active
# cadence; the 60s "safety poll" is documented as a settings field but reserved for
# a future v3 micro-plan per CONTEXT decision E (v2 has no no-subscriber branch).
# SUB-04 + SUB-05 closed by Plan 01.

# Metrics
duration: 17min
completed: 2026-06-03
---

# Phase 52 Plan 03: Per-URI polling policies & SubscriptionTerminated Summary

**Three concrete polling policies (`JobPolicy` 1s auto-terminating, `CorpusStatusPolicy` 30s diff-suppressed, `CorpusFoldersPolicy` settings-driven 5s) populate the `SUBSCRIPTION_POLICIES` registry that Plan 02 stubbed empty; `SubscriptionTerminated` control-flow sentinel extends Plan 01's `_poll_loop` with a clean-exit branch that emits one final `on_change` then releases the registry slot via the existing race-safe synchronous-cleanup paths.**

## Performance

- **Duration:** ~17 min
- **Started:** 2026-06-03T15:07:26Z
- **Completed:** 2026-06-03T15:24:39Z
- **Tasks:** 2 atomic commits (source + tests)
- **Files modified:** 7 (2 created in tests/, 5 modified in agent_brain_mcp/)

## Accomplishments

- **All three v2 subscribable URIs lit up:** `SUBSCRIPTION_POLICIES` now contains real policies for `job://` (scheme-prefix key, 1.0s cadence), `corpus://status` (exact key, 30.0s cadence), `corpus://folders` (exact key, settings-driven cadence with 5.0s default). Plan 02's subscribe handler now dispatches to real polling cadences instead of returning `not_subscribable` for everything.
- **`SubscriptionTerminated` control-flow sentinel landed:** Plan 01's `_poll_loop` catches the sentinel in the per-iteration try/except, emits one final `on_change(uri, final_payload)` with the terminal payload (if provided), and exits cleanly. Plan 01's synchronous-cleanup contract is preserved verbatim — the finally block + the existing `unsubscribe`/`cleanup_*` synchronous paths both scrub the `(session, uri)` slot.
- **MCP subscription settings:** `MCPSubscriptionSettings` Pydantic model with two `gt=0`-validated float fields (`folders_active_interval_s`, `folders_safety_interval_s`), env-var ingestion at config-module import time, and clear-failure-mode `RuntimeError` reraise with the offending env var name. Module-level singleton `mcp_subscription_settings` is read by `CorpusFoldersPolicy` instantiation at import.
- **40 new tests** (`test_policies.py` 28 + `test_policy_integration.py` 12) — MCP test count went from **201 → 241**. The full monorepo test count stays at **416** (the new MCP-only tests are deselected from the non-MCP packages). All Plan 01 + Plan 02 tests still pass — no regression in the locked surfaces.
- **All quality gates exit 0:** `black --check`, `ruff check`, `mypy` strict, `pytest`, `task check:layering` (3 contracts kept, 0 broken), `task before-push` from repo root.

## Task Commits

Each task was committed atomically:

1. **Task 1: Source code (policies + errors + manager wire + settings)** — `e0c4010` (feat) — modifies `subscriptions/policies.py` (+3 dataclasses + registry + 3 module-level fetcher factories + Protocol → @property), `subscriptions/errors.py` (+SubscriptionTerminated), `subscriptions/manager.py` (+SubscriptionTerminated catch in `_poll_loop`), `subscriptions/__init__.py` (+re-exports), `config.py` (+MCPSubscriptionSettings + env-var ingestion).
2. **Task 2: Per-policy + integration tests** — `8a2017d` (test) — adds `tests/subscriptions/test_policies.py` (28 unit tests with a hand-rolled _FakeApiClient) and `tests/subscriptions/test_policy_integration.py` (12 integration tests through SubscriptionManager + fake ApiClient + fast cadences).

**Plan metadata commit:** (this SUMMARY + STATE + ROADMAP update — separate commit below)

## Files Created/Modified

- `agent-brain-mcp/agent_brain_mcp/subscriptions/policies.py` — `JobPolicy`, `CorpusStatusPolicy`, `CorpusFoldersPolicy` dataclasses + three module-level fetcher factories + `SUBSCRIPTION_POLICIES` populated at module load + `TERMINAL_JOB_STATUSES` frozenset + `SubscriptionPolicy` Protocol refactored to @property attributes.
- `agent-brain-mcp/agent_brain_mcp/subscriptions/errors.py` — `SubscriptionTerminated(Exception)` with optional `final_payload` arg; `# noqa: N818` mirrors Plan 01's `SubscribableUriRejected` rationale.
- `agent-brain-mcp/agent_brain_mcp/subscriptions/manager.py` — `_poll_loop` catches `SubscriptionTerminated` before the generic `except Exception`, emits final `on_change` (with inner try/except so a broken closure doesn't pin the task), logs the terminate event, returns. The finally block and Plan 01's synchronous cleanup paths are untouched.
- `agent-brain-mcp/agent_brain_mcp/subscriptions/__init__.py` — re-exports `SubscriptionTerminated`, `JobPolicy`, `CorpusStatusPolicy`, `CorpusFoldersPolicy` alongside the existing Plan 01/02 public surface.
- `agent-brain-mcp/agent_brain_mcp/config.py` — `MCPSubscriptionSettings` Pydantic BaseModel + `_load_subscription_settings()` env-var ingestion + module-level `mcp_subscription_settings` singleton. Two new env vars: `AGENT_BRAIN_MCP_SUBSCRIPTION_FOLDERS_ACTIVE_INTERVAL_S` and `AGENT_BRAIN_MCP_SUBSCRIPTION_FOLDERS_SAFETY_INTERVAL_S`.
- `agent-brain-mcp/tests/subscriptions/test_policies.py` — 28 unit tests with `_FakeApiClient` covering each policy's attributes, Protocol structural match, fetcher dispatch, terminal-status parametrization, drop_keys composition correctness, registry contents, `resolve_policy` dispatch order (exact-then-scheme + not-subscribable + chunk:// non-subscription).
- `agent-brain-mcp/tests/subscriptions/test_policy_integration.py` — 12 end-to-end tests through real `SubscriptionManager.start_polling` with fast `interval_s` overrides; covers manager-level `SubscriptionTerminated` handling (3 tests), job lifecycle (running → completed), invalid-job-URI fast-terminate, status diff-suppression + real change re-emission, folders diff-suppression + last_indexed signal + custom interval_s cadence verification, parametrized resolve_policy + manager wiring across the two singleton URIs.

## Decisions Made

(See `key-decisions` in frontmatter above — 10 decisions documented.)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] `SubscriptionPolicy` Protocol attributes refactored from settable variables to `@property` declarations**
- **Found during:** Task 1 (running `poetry run mypy agent_brain_mcp` after adding the three concrete dataclasses).
- **Issue:** Mypy strict refused the dataclass instances as `SubscriptionPolicy` matches with "Protocol member ... expected settable variable, got read-only attribute" — even with `@dataclass` (non-frozen). The root cause is that fields with `field(default=callable)` produce instance attributes that mypy treats as read-only at the Protocol-conformance check. The Protocol attributes declared as `uri_pattern: str` etc. mean "settable instance variable"; the dataclass's actual instance attribute is structurally read-only-ish from mypy's perspective.
- **Fix:** Refactored `SubscriptionPolicy` to declare its attributes as `@property` methods (each with `...` body) so mypy understands they are read-only by intent. Runtime `isinstance(policy, SubscriptionPolicy)` still works because `@runtime_checkable` Protocol matches on attribute presence, not on declaration shape.
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/subscriptions/policies.py`
- **Verification:** `poetry run mypy agent_brain_mcp` clean (was 3 errors, now 0); all 28 new unit tests plus the 12 integration tests still pass; the existing 19 `tests/test_subscribe_handler.py` tests that use the `_StubPolicy` class still pass (the stub satisfies the new Protocol structurally — both `uri_pattern` etc. as attributes and as properties match the same `@property` shape under `@runtime_checkable`).
- **Committed in:** `e0c4010` (Task 1 commit)

**2. [Rule 1 — Bug] `build_fetcher` extracted from `@staticmethod` inside the dataclass to module-level functions**
- **Found during:** Task 1 (mypy continued to flag the dataclasses as not-matching the Protocol even after the @property refactor).
- **Issue:** Mypy treats `@staticmethod` as a method descriptor, not as a plain `Callable`. The Protocol declares `build_fetcher: PolicyFetcherFactory` (i.e., a `Callable[[Any, str], Callable[[], Awaitable[dict[str, Any]]]]`); the dataclass with `@staticmethod` exposes a descriptor that mypy doesn't unwrap to the plain Callable shape. So `isinstance(JobPolicy(), SubscriptionPolicy)` was True at runtime but mypy refused the dict-literal assignment.
- **Fix:** Extracted the three fetcher factories to module-level named functions (`_build_job_fetcher`, `_build_corpus_status_fetcher`, `_build_corpus_folders_fetcher`) and assigned them as `field(default=_build_*_fetcher)` on the dataclass. This produces an instance attribute whose runtime type IS a plain function (verified via `type(p.build_fetcher).__name__` == `"function"`), and mypy admits it as `PolicyFetcherFactory` verbatim.
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/subscriptions/policies.py`
- **Verification:** `poetry run mypy agent_brain_mcp` clean; `JobPolicy().build_fetcher(api, "job://abc")` works identically to the original `@staticmethod` form; the inline `del uri` no-op in the two singleton-URI factories silences ruff's unused-arg warning while keeping the Protocol signature consistent (factories always take `(api_client, uri)`).
- **Committed in:** `e0c4010` (Task 1 commit)

**3. [Rule 1 — Bug] Drop `frozen=True` on the dataclasses**
- **Found during:** Task 1 (early iteration of the policy implementation).
- **Issue:** `@dataclass(frozen=True)` produces read-only attributes via slot descriptors. Combined with the un-refactored Protocol's settable-variable attribute declarations, mypy refused the match. After refactoring the Protocol to `@property`, the dataclasses could revert to non-frozen since they are never mutated post-construction (effectively immutable by convention, not by enforcement).
- **Fix:** Removed `frozen=True` from all three dataclass decorators. The policies are still effectively immutable — instantiated once at module load and never mutated — but this is now a convention, not a runtime guarantee.
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/subscriptions/policies.py`
- **Verification:** No new mutation paths introduced; the dataclasses' `__hash__` no longer auto-generated (frozen=True implied hash) but that's fine because `SUBSCRIPTION_POLICIES` is a dict keyed by `str`, not by policy instances.
- **Committed in:** `e0c4010` (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 — Bugs surfaced by mypy strict during initial type-check).
**Impact on plan:** All three fixes preserve the plan's intended semantics. The Protocol/dataclass interplay was a known-tricky corner of mypy's structural-typing rules; the resolution (read-only Protocol attributes + module-level fetcher factories) is more idiomatic Python than the original spec and easier to read. The fix is documented inline in `policies.py` with a comment explaining why module-level factories are the right shape.

## Issues Encountered

- **`# noqa: N818` placement under black:** Initial `class SubscriptionTerminated(Exception):  # noqa: N818` worked, but black-wrapped the class signature across two lines (because the class body was long), which detached the noqa from the offending token. Ruff then flagged N818 with no acknowledgment. Resolved by shortening the line so it fits under 88 chars on a single line (`class SubscriptionTerminated(Exception):  # noqa: N818  # see note above`) with the rationale moved to a preceding block comment. Mirrors the resolution Plan 01 documented for `SubscribableUriRejected`.

## User Setup Required

None — this is library-internal code. The two new env vars (`AGENT_BRAIN_MCP_SUBSCRIPTION_FOLDERS_ACTIVE_INTERVAL_S` / `AGENT_BRAIN_MCP_SUBSCRIPTION_FOLDERS_SAFETY_INTERVAL_S`) are optional — defaults match CONTEXT decision B. Operators who want to tune the `corpus://folders` cadence can set them; otherwise no action required.

## Next Phase Readiness

**Plan 04 (disconnect cleanup hook + `build_server()` tuple refactor + e2e SDK tests) is unblocked.** Plan 04 will:

1. Refactor `build_server()` to return `(server, manager)` so `run_stdio`'s `finally` block can call `manager.cleanup_all()` without poking the `server._subscription_manager` private attribute.
2. Wire a `try/finally` into `run_stdio` (and the Phase 53 HTTP analog) that calls `manager.cleanup_all()` on transport disconnect.
3. Add a process-level e2e test that subscribes to `job://<live-id>` via the real MCP SDK client, terminates the client, and asserts the polling task exits within 2s.

Plan 04 does NOT need to touch the policies — the dispatch is wired and the polling lifecycle for terminal jobs already self-cleans via `SubscriptionTerminated`. The only thing left for Plan 04 is the disconnect path (sessions that close without their subscriptions terminating naturally).

**Phase 54 TOOL-04 (`wait_for_job`) cross-phase contract held.** Plan 03 did NOT touch `SubscriptionManager.start_polling`'s signature. Phase 54 still imports `start_polling` + `SubscriptionTerminated` verbatim; `wait_for_job` can use the same sentinel pattern (raise `SubscriptionTerminated(final_progress_payload)` from its one-shot polling fetcher when the job reaches a terminal status).

**Plan 02's stub-policy monkeypatch pattern continues to work.** `tests/test_subscribe_handler.py` uses `monkeypatch.setitem(SUBSCRIPTION_POLICIES, "corpus://status", stub)` which replaces the Plan 03 real policy with the stub for that one test scope; the real policy is restored on test teardown. The 19 tests there still pass without modification.

## Self-Check: PASSED

- [x] `agent-brain-mcp/agent_brain_mcp/subscriptions/policies.py` modified — registry populated with 3 entries
- [x] `agent-brain-mcp/agent_brain_mcp/subscriptions/errors.py` modified — `SubscriptionTerminated` added
- [x] `agent-brain-mcp/agent_brain_mcp/subscriptions/manager.py` modified — `_poll_loop` catches sentinel
- [x] `agent-brain-mcp/agent_brain_mcp/subscriptions/__init__.py` modified — re-exports
- [x] `agent-brain-mcp/agent_brain_mcp/config.py` modified — `MCPSubscriptionSettings` + env-var ingestion
- [x] `agent-brain-mcp/tests/subscriptions/test_policies.py` created — 28 unit tests
- [x] `agent-brain-mcp/tests/subscriptions/test_policy_integration.py` created — 12 integration tests
- [x] Commit `e0c4010` exists in `git log` (feat: source code)
- [x] Commit `8a2017d` exists in `git log` (test: per-policy + integration tests)
- [x] `poetry run pytest tests/subscriptions/ -v` — 79 passed (was 39; +40 new)
- [x] `poetry run pytest -m ''` (full MCP suite) — 241 passed (was 201; +40 new), 38 skipped
- [x] `poetry run black --check agent_brain_mcp tests` — clean (62 files)
- [x] `poetry run ruff check agent_brain_mcp tests` — clean
- [x] `poetry run mypy agent_brain_mcp` — clean (29 source files, no issues)
- [x] `task check:layering` — 3 contracts kept, 0 broken
- [x] `task before-push` — exit 0 (416 tests across the monorepo, 80% coverage)
- [x] No edits to `agent-brain-server/`
- [x] No edits to Plan 01's locked public surface (`SubscriptionManager.start_polling` signature unchanged)
- [x] No edits to Plan 02's `server.py` (`build_server()` + handler wiring unchanged)
- [x] Plan 01's race tests still pass (`test_subscribe_then_immediate_unsubscribe_cancels_before_first_poll` + 38 sibling manager tests)
- [x] Plan 02's wire tests still pass (`test_subscribe_handler.py` 19 tests + `test_e2e_resources.py` 5 e2e tests)
- [x] No new dependencies added — Pydantic + asyncio + dataclasses already present

---
*Phase: 52-resource-subscriptions*
*Completed: 2026-06-03*
