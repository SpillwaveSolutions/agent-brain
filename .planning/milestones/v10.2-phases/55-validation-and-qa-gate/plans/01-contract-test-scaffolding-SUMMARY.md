---
phase: 55-validation-and-qa-gate
plan: 01
subsystem: testing
tags: [mcp, contract-tests, pytest, mcp-sdk, stdio, fixture-chain, fake-backend, anyio]

requires:
  - phase: 50-server-endpoint-prep-v2-design-doc
    provides: ChunkRecord + GraphEntityRecord wire shapes (the _DEFAULT_RESPONSES stubs mirror them 1:1)
  - phase: 51-deferred-uri-schemes
    provides: parameterized URI dispatcher + 4 handlers; contract tests will exercise chunk/graph-entity/job/file resources
  - phase: 52-resource-subscriptions
    provides: SubscriptionManager + build_server tuple shape; Plan 03 will subscribe via mcp_stdio_session
  - phase: 53-streamable-http-transport
    provides: run_http listener + serverInfo._meta wire wiring; Plan 04 will reuse mcp_http_subprocess for HTTP contract tests
  - phase: 54-remaining-mcp-tools
    provides: 16 ToolSpec entries (7 v1 + 9 v2); Plan 02 will parametrize the contract matrix over all 16 names

provides:
  - SDK-driven contract fixture chain (mcp_stdio_session factory + autouse D-17 orphan scan)
  - tests/contract/ directory + __init__.py for pytest discovery
  - bundled fake-server script template (_DEFAULT_CONTRACT_SERVER_SCRIPT) Plans 02/03/04 inherit
  - extended _DEFAULT_RESPONSES with 8 new v2 endpoint stubs (additive — no existing entries modified)
  - 'contract' pytest marker registered in pyproject.toml + excluded from default fast path
  - task contract wired to real pytest invocation (replaces Phase 4 placeholder)
  - smoke test asserting initialize() succeeds + serverInfo.name == 'agent-brain'

affects: [55-02-tool-matrix, 55-03-subscription-lifecycle, 55-04-http-transport-contract, 55-05-root-qa-gate]

tech-stack:
  added: []  # No new runtime deps; all uses existing mcp 1.12.x SDK + httpx MockTransport + pytest-asyncio
  patterns:
    - "Callable-returning-async-context-manager fixture shape (mcp_stdio_session) to dodge anyio's exit-cancel-scope-in-different-task trap that bites async-generator fixtures wrapping stdio_client"
    - "Bundled fake-server script template + JSON-serialized _DEFAULT_RESPONSES table passed via env var, so Plans 02/03/04 inject per-test response overrides without rewriting the script"
    - "D-17 orphan-scan autouse fixture: pgrep -f script_name AFTER every test, FAIL the test if any survived, SIGKILL them so subsequent tests don't inherit"
    - "Script-name-scoped pgrep pattern (fake_contract_server.py) — does NOT match the pytest parent process or unrelated subprocesses"

key-files:
  created:
    - agent-brain-mcp/tests/contract/__init__.py
    - agent-brain-mcp/tests/contract/conftest.py
    - agent-brain-mcp/tests/contract/test_contract_smoke.py
    - .planning/phases/55-validation-and-qa-gate/plans/01-contract-test-scaffolding-SUMMARY.md
  modified:
    - agent-brain-mcp/tests/conftest.py
    - agent-brain-mcp/pyproject.toml
    - agent-brain-mcp/Taskfile.yml

key-decisions:
  - "Entry point: sys.executable + path to bundled fake-server script (NOT `python -m agent_brain_mcp.cli` against a real backend) — the contract suite needs a fast in-memory backend per CONTEXT D-04, not a live agent-brain-serve. The fake-server script mirrors the proven test_e2e_stdio.py + _FAKE_HTTP_SERVER_SCRIPT pattern."
  - "mcp_stdio_session is a CALLABLE returning an async context manager — NOT an async-generator fixture yielding a session. Load-bearing because async-generator fixtures wrapping stdio_client trip anyio's 'exit cancel scope in a different task' guard (pytest-asyncio runs setup and teardown in different tasks). Documented Phase 52 Plan 02 Decision precedent."
  - "Backend responses passed to the fake-server subprocess via the AGENT_BRAIN_MCP_CONTRACT_RESPONSES_JSON env var as a JSON-serialized 'METHOD path' -> body dict. Lets Plans 02/03/04 inject per-test overrides without rewriting the script."
  - "D-17 orphan scan is implemented as an autouse fixture, NOT as part of the mcp_stdio_session fixture. Every contract test gets the safety net regardless of whether it consumed the session — guards against future fixtures or direct subprocess spawns leaking processes."
  - "pgrep pattern is script-name-scoped (fake_contract_server.py) NOT module-name-scoped (agent_brain_mcp) — module name would false-positive against the pytest parent process which imports agent_brain_mcp for the per-test fixtures."

patterns-established:
  - "Phase 55 contract subprocess pattern: bundled fake-server script + httpx.MockTransport backend + JSON env-var responses table (Plans 02/03/04 use the same pattern)"
  - "Callable factory fixture shape for SDK stdio sessions (replaces async-generator fixture pattern broken by anyio task ownership)"
  - "Defensive autouse orphan-scan teardown for any test spawning subprocesses (D-17 contract from Phase 4 / Phase 52 carried into Phase 55)"

requirements-completed: []  # VAL-01 scaffolding only — full VAL-01 closes in Plan 02 (16-tool matrix). Plan 01 frontmatter declares no requirements field; the plan covers "VAL-01 (scaffolding portion)" per the PLAN.md goal.

duration: 11min
completed: 2026-06-03
---

# Phase 55 Plan 01: Contract Test Scaffolding Summary

**SDK-driven contract fixture chain landed — `mcp_stdio_session` factory + autouse D-17 orphan scan + 8 new v2 endpoint stubs in `_DEFAULT_RESPONSES`, ready for Plans 02-04 to consume verbatim.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-06-03T19:53:51Z
- **Completed:** 2026-06-03T20:04:37Z
- **Tasks:** 3 atomic commits + 1 docs commit
- **Files modified:** 4 (3 created, 4 modified)

## Accomplishments

- `agent-brain-mcp/tests/contract/` directory + `mcp_stdio_session` fixture (Plans 02/03/04 lock into this verbatim).
- Smoke test proves the chain end-to-end: spawns the fake-backed subprocess, completes the SDK handshake, asserts `serverInfo.name == 'agent-brain'`, tears down cleanly with zero orphan processes.
- `_DEFAULT_RESPONSES` extended with 8 new entries (DELETE /index/folders/, GET/DELETE /index/cache/, POST /index/add, 3 terminal JobRecord variants for wait_for_job) — strictly additive, no existing v1 entries modified.
- `contract` pytest marker registered + excluded from default fast path; `task contract` invokes real pytest (replaces Phase 4 placeholder echo).
- D-17 orphan-scan autouse fixture catches teardown regressions before they leak into the next test.

## Task Commits

Each task was committed atomically on `main`:

1. **Task 1: extend `_DEFAULT_RESPONSES`** — `f0b5966` (test)
2. **Task 2: contract scaffolding + smoke + marker** — `fb24ab9` (test)
3. **Task 3: wire `task contract`** — `2e92dcc` (chore)

**Plan metadata:** (this commit, after SUMMARY.md + STATE.md + ROADMAP.md updates)

## Files Created/Modified

- `agent-brain-mcp/tests/contract/__init__.py` — empty marker for pytest discovery
- `agent-brain-mcp/tests/contract/conftest.py` — `mcp_stdio_session` factory fixture, autouse D-17 orphan scan, bundled fake-server script template (`_DEFAULT_CONTRACT_SERVER_SCRIPT`), helpers `_build_responses_env` / `_scan_for_orphans` / `_kill_orphans`
- `agent-brain-mcp/tests/contract/test_contract_smoke.py` — ONE test asserting initialize() over stdio returns `serverInfo.name == 'agent-brain'`
- `agent-brain-mcp/tests/conftest.py` — 8 new entries added to `_DEFAULT_RESPONSES` (additive only)
- `agent-brain-mcp/pyproject.toml` — `contract` marker registered under `[tool.pytest.ini_options].markers` + `addopts` extended to exclude `contract` from default fast path
- `agent-brain-mcp/Taskfile.yml` — `contract:` task replaces the Phase 4 placeholder echo with `poetry run pytest tests/contract -v -m contract`

## Decisions Made

- **Subprocess entry point: bundled fake-server script via `sys.executable + script-path`**, NOT `python -m agent_brain_mcp.cli` against a real backend. The contract suite uses an in-memory `httpx.MockTransport` backend (CONTEXT D-04); spawning the real CLI would require a live `agent-brain-serve` on port 8000 and would 10x the suite duration. The bundled script mirrors the proven `test_e2e_stdio.py` and `_FAKE_HTTP_SERVER_SCRIPT` patterns — same wire protocol, no backend dependence.
- **`mcp_stdio_session` is a CALLABLE returning an async context manager**, not an async-generator fixture. Load-bearing because async-generator fixtures wrapping `stdio_client` trip anyio's `RuntimeError: Attempted to exit cancel scope in a different task than it was entered in` (pytest-asyncio runs setup and teardown in different tasks; anyio's task-group ownership demands same-task entry/exit). Documented Phase 52 Plan 02 Decision precedent — `create_connected_server_and_client_session` was inlined for the same reason. Tests use `async with mcp_stdio_session() as session:` instead of plain consumption.
- **Backend responses passed via `AGENT_BRAIN_MCP_CONTRACT_RESPONSES_JSON` env var** (JSON-serialized `"METHOD path" -> body` table) — Plans 02/03/04 inject per-test overrides without rewriting the bundled script. Tuple keys flattened to strings for JSON compatibility; subprocess rehydrates to tuples at startup.
- **D-17 orphan scan is autouse** (runs after EVERY contract test) — not coupled to `mcp_stdio_session` consumption. Future tests that spawn subprocesses directly (e.g., Plan 04's HTTP subprocess) inherit the same safety net.
- **pgrep pattern is script-name-scoped (`fake_contract_server.py`)** rather than module-name-scoped (`agent_brain_mcp`). Module-name scoping would false-positive against the parent `pytest` process that imports `agent_brain_mcp` for its per-test fixtures.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `mcp_stdio_session` fixture signature changed from direct yield to factory + async context manager**

- **Found during:** Task 2 (running the initial smoke test)
- **Issue:** The plan's literal signature `async def mcp_stdio_session() yield session` (consumed as `await mcp_stdio_session.initialize()`) triggered `RuntimeError: Attempted to exit cancel scope in a different task than it was entered in` from anyio's `_asyncio.py:455`. Root cause: pytest-asyncio runs the fixture's `__aenter__` in the fixture task but resumes the generator's teardown in a DIFFERENT task; anyio's `CancelScope.__exit__` rejects cross-task exit because cancel scopes are tied to the entering task. The smoke test PASSED on the assertion but the teardown threw, polluting the test result.
- **Fix:** Restructured `mcp_stdio_session` as a callable returning an async context manager (`async with mcp_stdio_session() as session:`). Setup and teardown now happen in the SAME task (the test's own task) — anyio is happy. Smoke test updated to use the new shape. The fixture's PUBLIC SURFACE is still the same locked shape Plans 02/03/04 need (a fixture named `mcp_stdio_session`, yielding a `ClientSession`); only the consumption idiom changed from `await mcp_stdio_session.foo()` to `async with mcp_stdio_session() as session: await session.foo()`. The factory accepts optional `response_overrides`, `custom_script`, `extra_env` kwargs that Plans 02/03/04 will use heavily.
- **Files modified:** `agent-brain-mcp/tests/contract/conftest.py`, `agent-brain-mcp/tests/contract/test_contract_smoke.py`
- **Verification:** Smoke test now passes cleanly (0.46s, no anyio traceback). `task contract` exit 0.
- **Committed in:** `fb24ab9` (the fix was made before the commit landed, so the commit contains the correct shape).

**2. [Rule 2 - Missing Critical] Added autouse `_contract_orphan_scan_after_each_test` fixture as defense-in-depth**

- **Found during:** Task 2 (designing the fixture's teardown surface)
- **Issue:** The plan's success criteria specifies "Teardown finalizer scans for orphan `agent-brain-mcp` processes and fails the test if any survive" — but coupling this scan to `mcp_stdio_session` means tests that DON'T consume the fixture (e.g., a future Plan 04 test that spawns its own HTTP subprocess) wouldn't get the safety net. Future direct-subprocess tests would leak orphans into the next test, masking real regressions.
- **Fix:** Implemented the orphan scan as an autouse fixture that runs after EVERY test in `tests/contract/`. The session fixture STILL benefits from the SDK's stdio_client SIGTERM contract (inside the `async with`), and the autouse fixture catches anything that slipped through. Two-layered teardown matches the Phase 4 / Phase 52 pattern.
- **Files modified:** `agent-brain-mcp/tests/contract/conftest.py`
- **Verification:** Smoke test passes; pgrep returns empty after teardown.
- **Committed in:** `fb24ab9`

---

**Total deviations:** 2 auto-fixed (1 bug — anyio task ownership; 1 missing critical — D-17 coverage for non-session tests).
**Impact on plan:** Both deviations preserve the plan's PUBLIC SURFACE (`mcp_stdio_session` fixture name + D-17 teardown contract + JSON-backend env var). The factory consumption pattern is the ONLY shape that works with anyio task groups; Plans 02/03/04 inherit it without churn because the calling pattern (`async with mcp_stdio_session(...) as session:`) is the natural one for SDK-driven contract tests. No scope creep — neither deviation adds production code or new dependencies.

## Issues Encountered

- anyio's cross-task cancel-scope error on the initial async-generator fixture (resolved by the factory restructure above).
- Ruff complained about `UP037` (quoted forward references) and `I001` (import order around the inline comment block) — both auto-fixed before commit.

## Self-Check

Verified after writing SUMMARY.md:

- `agent-brain-mcp/tests/contract/__init__.py` → exists
- `agent-brain-mcp/tests/contract/conftest.py` → exists
- `agent-brain-mcp/tests/contract/test_contract_smoke.py` → exists
- `f0b5966` (Task 1 commit) → in git log
- `fb24ab9` (Task 2 commit) → in git log
- `2e92dcc` (Task 3 commit) → in git log
- `task contract` → exit 0 (1 passed)
- `task before-push` → exit 0 (416 monorepo CLI tests + format/lint/typecheck all clean)
- `task check:layering` → exit 0 (3/3 contracts kept, 164 files, 414 deps)
- mcp default fast-path `pytest tests -v` → 451 passed, 48 deselected, 0 failures

## Self-Check: PASSED

## User Setup Required

None — no external service configuration required. Contract suite uses in-memory MockTransport backend.

## Next Phase Readiness

- `mcp_stdio_session` fixture LOCKED on `fb24ab9`. Plans 02 (16-tool matrix VAL-01), 03 (subscription lifecycle VAL-02), 04 (HTTP transport VAL-03) can import it verbatim.
- `_DEFAULT_RESPONSES` extended with 8 v2 endpoint stubs — Plans 02/03/04 can either rely on the defaults or pass `response_overrides=` for per-test backends.
- `contract` pytest marker + Taskfile wiring in place — Plans 02/03/04 just add `@pytest.mark.contract` to their tests and they automatically run under `task contract`.
- ROADMAP Phase 55 row stays at 1/5 plans complete; Plan 02 (parameterized 16-tool contract matrix) is the next workable plan.

---
*Phase: 55-validation-and-qa-gate*
*Plan: 01 — contract test scaffolding*
*Completed: 2026-06-03*
