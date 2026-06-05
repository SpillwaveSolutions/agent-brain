---
phase: 55-validation-and-qa-gate
plan: 04
subsystem: testing
tags: [mcp, contract-tests, pytest, mcp-sdk, http, streamable-http, transport, sdk-driven, fixture-cascade]

requires:
  - phase: 53-streamable-http-transport
    provides: Plan 02 — agent_brain_mcp.http.run_http + validate_loopback_host + healthz endpoint + MCP_MOUNT_PATH constant
  - phase: 53-streamable-http-transport
    provides: Plan 03 — mcp_http_subprocess + fake_http_server_module fixtures in tests/conftest.py (reused verbatim via pytest parent-conftest cascade — no duplicate fixture, no new fake-server script)
  - phase: 55-validation-and-qa-gate
    provides: Plan 01 — contract pytest marker + autouse D-17 orphan-scan + tests/contract/ directory + tests/contract/conftest.py
  - phase: 55-validation-and-qa-gate
    provides: Plan 02 — 16-tool TOOL_REGISTRY contract pinned over stdio (Plan 04 asserts same 16 surface over HTTP)
  - phase: 55-validation-and-qa-gate
    provides: Plan 03 — autouse orphan-scan regex precedent (alternation pattern; Plan 04 widens it to include fake_mcp_http_server.py)

provides:
  - tests/contract/test_http_transport_contract.py (5 wire-protocol contract tests + 1 mount-path sanity pin = 6 contract tests)
  - tests/contract/conftest.py::mcp_http_session factory fixture (async context manager around streamablehttp_client + ClientSession; parallel to mcp_stdio_session shape from Plan 01)
  - Defensive *_ unpack on streamablehttp_client yield tuple (forward-compat absorbing future SDK additive elements per Phase 53 Plan 03 risk #1)
  - Autouse orphan-scan regex widened from `fake_(contract|subscription)_server.py` to also match `fake_mcp_http_server.py`
  - Fixture-cascade pattern proof: tests/conftest.py fixtures (mcp_http_subprocess + free_loopback_port + fake_http_server_module) reused verbatim from tests/contract/ tests via pytest's parent-conftest discovery

affects: [55-05-root-qa-gate]

tech-stack:
  added: []  # No new runtime or dev deps. Reuses mcp 1.12.x streamablehttp_client + Phase 53 Plan 03's psutil + Plan 01's contract marker.
  patterns:
    - "Callable-returning-async-context-manager fixture shape for SDK HTTP sessions (parallel to mcp_stdio_session — same anyio task-ownership trap dodge)"
    - "Fixture-cascade reuse: Plan 04 inherits Phase 53 Plan 03's mcp_http_subprocess + fake_http_server_module from tests/conftest.py without duplication, by virtue of pytest's parent-conftest discovery"
    - "Defensive trailing-tuple unpack on streamablehttp_client yield (`as (read, write, *_)`) — absorbs additive SDK signature evolution"
    - "Mount-path sanity pin: hard-coded fixture constant tested against the production MCP_MOUNT_PATH so silent drift surfaces at collection time, not as vague 404s mid-test"
    - "Transport-equivalence proof: Plan 04 asserts the SAME 16-tool surface + SAME 5 v1 corpus URIs surface over HTTP as over stdio (Plan 02), catching one-transport-but-not-the-other regressions"

key-files:
  created:
    - agent-brain-mcp/tests/contract/test_http_transport_contract.py
    - .planning/phases/55-validation-and-qa-gate/plans/04-http-transport-contract-test-SUMMARY.md
  modified:
    - agent-brain-mcp/tests/contract/conftest.py
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "mcp_http_session is a CALLABLE returning an async context manager — same shape as Plan 01's mcp_stdio_session. The callable + `async with` pattern keeps setup and teardown in the same asyncio task, dodging anyio's `Attempted to exit cancel scope in a different task` trap that bites async-generator fixtures wrapping ``streamablehttp_client`` for the same reason it bites ``stdio_client`` (Phase 52 Plan 02 Decision precedent, re-affirmed in Plan 01 Decision)."
  - "Plan 04 REUSES Phase 53 Plan 03's mcp_http_subprocess + fake_http_server_module fixtures via pytest's parent-conftest cascade — does NOT create a duplicate HTTP harness in tests/contract/. The parent fixtures already encapsulate the free-port allocation, the SIGINT→3s→SIGKILL teardown, the /healthz readiness probe, and the fake-backend wiring. Duplicating any of that would create silent drift between the e2e_http and contract HTTP tests."
  - "Hard-coded `_HTTP_MOUNT_PATH = '/mcp'` in tests/contract/conftest.py (rather than importing agent_brain_mcp.http.MCP_MOUNT_PATH) keeps the contract conftest import-cheap for the stdio-only contract tests — the production HTTP module pulls in uvicorn + starlette which would otherwise be loaded at collection time for every Plan 02/03 stdio test. Drift is guarded by the dedicated `test_http_mount_path_matches_production_constant` test (catches at collection-time, not mid-test as a vague 404)."
  - "Defensive `*_` unpack on streamablehttp_client's yield tuple. The SDK's 1.12.x yield shape is `(read, write, session_id_factory)`; trailing additions are forward-compat. `async with streamablehttp_client(url) as (read, write, *_):` absorbs any new ones without test churn (Phase 53 Plan 03 risk #1, re-applied)."
  - "Orphan-scan regex widened from `fake_(contract|subscription)_server.py` to `fake_(contract|subscription)_server.py|fake_mcp_http_server.py` so HTTP-transport subprocess leaks surface in the same D-17 safety net. Both the Plan 03 stdio variants AND the Phase 53 HTTP variant now share one autouse scan."
  - "Plan 04 ADDS a mount-path sanity-pin test beyond the plan's literal 5 acceptance-criteria tests (6 total). The pin protects the fixture's URL construction against future drift in the production constant — catches the silent-404 failure mode at collection time, before the SDK handshake fails with a misleading 'protocol error' instead of 'mount path moved'. Strict tightening, no scope creep — the constant duplication was inevitable because importing the production module from conftest is import-cost-prohibitive."
  - "Plan 04 does NOT touch loopback-rejection (--host 0.0.0.0) or --transport-rejection negative paths — those tests live in Phase 53 (CONTEXT D-10). Plan 04's scope is only the happy-path SDK round-trip + transport-equivalence proof."

patterns-established:
  - "Plan 04 transport-equivalence proof pattern: SAME assertions on SAME wire surface (16 tools, 5 v1 corpus URIs, JSON read round-trip) over HTTP that Plan 02 makes over stdio — catches one-transport-only regressions in the v2 surface"
  - "Fixture-cascade reuse from tests/conftest.py into tests/contract/ (pytest parent-conftest discovery) — Plan 04 demonstrates the pattern is load-bearing for future MCP transport variants (e.g., a UDS contract test could reuse the same idiom)"

requirements-completed: [VAL-03]

duration: 8min
completed: 2026-06-03
---

# Phase 55 Plan 04: Streamable HTTP transport contract test (VAL-03) Summary

**HTTP transport SDK round-trip wire-verified — `mcp_http_session` fixture in `tests/contract/conftest.py` wraps Phase 53 Plan 03's `mcp_http_subprocess` + the official MCP SDK's `streamablehttp_client` into a `contract`-marked async-context-manager parallel to Plan 01's `mcp_stdio_session`; 6 new tests (5 acceptance + 1 mount-path sanity pin) prove initialize / tools/list==16 / tools/call(server_health) / resources/list⊇{5 v1 corpus URIs} / resources/read(corpus://config) all round-trip cleanly over HTTP. VAL-03 closed.**

## Performance

- **Duration:** 8 min 29 sec
- **Started:** 2026-06-03T20:53:14Z
- **Completed:** 2026-06-03T21:01:43Z
- **Tasks:** 1 atomic test commit (per-task granularity collapses naturally here — conftest fixture and test file are interdependent and ship as one unit) + 1 docs metadata commit
- **Files modified:** 2 (1 created, 1 modified) in code; +3 planning files (SUMMARY, STATE, ROADMAP, REQUIREMENTS)
- **MCP contract suite:** 43 → 49 tests (+6 — 5 acceptance tests + 1 mount-path sanity pin)
- **MCP contract suite duration:** 20.97s → 24.73s (+3.76s; well under the +20s budget noted in plan_specific_guidance and the <90s acceptance ceiling)
- **HTTP test file alone:** 3.84s for 6 tests (under the 15s test-file budget)
- **MCP fast path:** 460 tests / 96 deselected — UNCHANGED (contract tests stay opt-in per Plan 01's marker exclusion in `addopts`)
- **Monorepo `task before-push`:** exit 0 — 416 CLI tests + format/lint/typecheck/test/coverage clean

## Accomplishments

- **`mcp_http_session` factory fixture** (`tests/contract/conftest.py`): async context manager around `streamablehttp_client(url)` + `ClientSession(read, write)`, parallel to Plan 01's `mcp_stdio_session` callable shape. The callable + `async with` pattern keeps SDK setup and teardown in the test's own asyncio task — same anyio task-ownership trap that bites async-generator fixtures wrapping `stdio_client` also bites those wrapping `streamablehttp_client` (Plan 01 Decision precedent, re-applied here). Mount URL constructed as `http://{host}:{port}{_HTTP_MOUNT_PATH}` with `_HTTP_MOUNT_PATH = "/mcp"` mirroring `agent_brain_mcp.http.MCP_MOUNT_PATH`.
- **Defensive `*_` unpack on `streamablehttp_client` yield tuple** (`async with streamablehttp_client(url) as (read, write, *_):`). The SDK's 1.12.x yield shape is `(read, write, session_id_factory)`; trailing additions are forward-compat per Phase 53 Plan 03 risk #1. The unpack pattern absorbs additive SDK signature evolution without test churn.
- **Fixture-cascade reuse from `tests/conftest.py` into `tests/contract/`:** Plan 04 consumes Phase 53 Plan 03's `mcp_http_subprocess` + `fake_http_server_module` + `free_loopback_port` fixtures directly — pytest's parent-conftest discovery makes them visible without re-exposure or duplication. The parent fixtures encapsulate free-port allocation (`socket.bind(("127.0.0.1", 0))` + release), the SIGINT→3s→SIGKILL teardown, the `/healthz` readiness probe (10s timeout, 0.1s interval), and the `httpx.MockTransport` fake-backend wiring. Duplicating any of that in `tests/contract/` would have created silent drift between the `e2e_http` and `contract` HTTP suites.
- **Autouse orphan-scan widened (`tests/contract/conftest.py::_scan_for_orphans`):** the `pgrep -f` regex went from `fake_(contract|subscription)_server.py` to `fake_(contract|subscription)_server.py|fake_mcp_http_server.py` so the Phase 53 HTTP fake-server's orphans (if SDK `streamablehttp_client` teardown ever fails to drain) surface in the same D-17 safety net that catches stdio orphans. The error message and docstring are updated to reflect the wider scope.
- **5 acceptance tests + 1 sanity pin** (all marked `contract` + `asyncio` except the sanity pin which is sync):
  - `test_http_initialize` — SDK handshake completes; `serverInfo.name == "agent-brain"`; capabilities advertise `tools`, `resources`, `prompts`.
  - `test_http_tools_list_returns_16` — `tools/list` returns exactly 16 tools (the full v2 surface from Plan 02), proving transport equivalence with stdio.
  - `test_http_tool_call_smoke` — `call_tool("server_health", {})` returns non-empty `content` with `content[0].type == "text"` AND a `structuredContent` dict (the dual-shape contract from v2 design doc §3.2).
  - `test_http_resources_list_includes_v1_static` — `resources/list` advertises all 5 v1 `corpus://` URIs (config, status, health, providers, folders).
  - `test_http_resources_read_corpus_config` — `resources/read corpus://config` returns `contents[0].mimeType == "application/json"` with a parseable JSON body containing `storage_backend`.
  - `test_http_mount_path_matches_production_constant` — pins fixture-local `_HTTP_MOUNT_PATH` against `agent_brain_mcp.http.MCP_MOUNT_PATH` so silent drift in the production constant surfaces at collection time instead of as a vague 404 mid-test.
- **Scope discipline maintained per CONTEXT D-10:** Plan 04 does NOT add loopback-rejection (`--host 0.0.0.0`) or `--transport`-rejection negative path tests — Phase 53 owns those. Plan 04 asserts only the happy-path SDK round-trip + transport-equivalence proof.
- **NO root Taskfile changes** — Plan 05 (VAL-04, DR-5 closure) owns folding the contract suite into root `task before-push`.

## Task Commits

Single atomic test commit on `main`:

1. **Task 1: HTTP transport contract tests + conftest fixture** — `9b8eda6` (test)

**Plan metadata commit:** (next commit — includes SUMMARY.md + STATE.md + ROADMAP.md + REQUIREMENTS.md updates)

## Files Created/Modified

### Created

- **`agent-brain-mcp/tests/contract/test_http_transport_contract.py`** (213 lines) — 5 SDK-driven Streamable HTTP contract tests + 1 mount-path sanity pin. Each test marked `@pytest.mark.contract` + `@pytest.mark.asyncio` (sanity pin is sync). Module docstring cites Phase 55 CONTEXT D-04 (in-memory fake backend), D-09 (subprocess + readiness), D-10 (Phase 53 owns rejection tests), and D-11 (free-port allocation).
- **`.planning/phases/55-validation-and-qa-gate/plans/04-http-transport-contract-test-SUMMARY.md`** — this file.

### Modified

- **`agent-brain-mcp/tests/contract/conftest.py`** — three additions:
  1. New import: `from mcp.client.streamable_http import streamablehttp_client`.
  2. Orphan-scan regex widened from `fake_(contract|subscription)_server.py` to `fake_(contract|subscription)_server.py|fake_mcp_http_server.py`; error message + docstring updated to reflect the wider scope.
  3. New `mcp_http_session` factory fixture (~80 lines including docstring) — async context manager that opens `streamablehttp_client` against the URL `http://127.0.0.1:{free_loopback_port}/mcp` and wraps the streams in a `ClientSession`. Consumes `mcp_http_subprocess` + `free_loopback_port` via the parent-conftest cascade. Hard-coded `_HTTP_MOUNT_PATH = "/mcp"` constant beneath the fixture (sanity-pinned against production by `test_http_mount_path_matches_production_constant`).
- **`.planning/STATE.md`** — plan counter advanced 3/5 → 4/5; `stopped_at` updated with this plan's outcomes (commits, test counts, verification gates).
- **`.planning/ROADMAP.md`** — Phase 55 row plans-complete 3/5 → 4/5; Plan 04 row checkbox `[ ]` → `[x]` with completion narrative.
- **`.planning/REQUIREMENTS.md`** — VAL-03 line `[ ]` → `[x]` with closure narrative; traceability table row "Pending" → "Complete (2026-06-03, Plan 55-04)".

## Decisions Made

- **`mcp_http_session` is a CALLABLE returning an async context manager** — same shape as Plan 01's `mcp_stdio_session`. The callable + `async with` pattern keeps setup and teardown in the same asyncio task, dodging anyio's `Attempted to exit cancel scope in a different task` trap that bites async-generator fixtures wrapping `streamablehttp_client` for the SAME reason it bites those wrapping `stdio_client` (Phase 52 Plan 02 Decision precedent, re-affirmed in Plan 01 Decision). The fixture's public surface is `(*, host="127.0.0.1", extra_env=None) -> AsyncContextManager[ClientSession]` — kwargs are passthroughs to the inner `mcp_http_subprocess` factory; tests consume as `async with mcp_http_session() as session:`.
- **Reuse Phase 53 Plan 03's `mcp_http_subprocess` + `fake_http_server_module` fixtures verbatim** via pytest's parent-conftest cascade. The parent fixtures already encapsulate free-port allocation, SIGINT→3s→SIGKILL teardown, `/healthz` readiness probe, and `httpx.MockTransport` fake-backend wiring. Duplicating any of that in `tests/contract/` would create silent drift between the `e2e_http` and `contract` HTTP suites. The cascade pattern is now load-bearing for future MCP transport variants (e.g., a hypothetical UDS contract test could reuse the same idiom).
- **Hard-coded `_HTTP_MOUNT_PATH = "/mcp"`** in `tests/contract/conftest.py` rather than importing `agent_brain_mcp.http.MCP_MOUNT_PATH`. The production HTTP module pulls in uvicorn + starlette at import time — re-importing it at the contract conftest's module level would add several hundred ms of cold-load cost to EVERY contract test (including the Plan 02/03 stdio-only ones). Drift is guarded by `test_http_mount_path_matches_production_constant` which imports the production constant inside the test body and pins it against the conftest's constant — collection-time drift detection, no module-level import cost.
- **Defensive `*_` unpack on `streamablehttp_client` yield tuple** (`async with streamablehttp_client(url) as (read, write, *_):`). The SDK's 1.12.x yield shape is `(read, write, session_id_factory)`; trailing additions are forward-compat per the SDK design (Phase 53 Plan 03 risk #1, re-applied). The unpack pattern absorbs any new elements without test churn on SDK upgrades.
- **Orphan-scan regex widened from `fake_(contract|subscription)_server.py` to `fake_(contract|subscription)_server.py|fake_mcp_http_server.py`.** Phase 53's HTTP fake-server script name (`fake_mcp_http_server.py`) is distinct from the Plan 01 / Plan 03 stdio script names; the autouse scan needs to catch all three. The error message in `_contract_orphan_scan_after_each_test` now names all three scripts so future investigators see the full surface immediately.
- **Plan 04 ADDS a 6th test (`test_http_mount_path_matches_production_constant`) beyond the plan's literal 5 acceptance-criteria tests.** The sanity pin protects the fixture's URL construction against future drift in the production constant — catches the silent-404 failure mode at collection time, before the SDK handshake fails with a misleading "protocol error" instead of "mount path moved". This is strict tightening (not scope creep) because the constant duplication was inevitable given the import-cost trade-off above.
- **Plan 04 does NOT touch loopback-rejection (`--host 0.0.0.0`) or `--transport`-rejection negative paths** — those tests live in Phase 53 (CONTEXT D-10). Plan 04's scope is only the happy-path SDK round-trip + transport-equivalence proof.

## Deviations from Plan

**Total deviations:** 1 (Rule 2 — missing critical functionality, auto-applied) + 0 (Rule 4 architectural)

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Mount-path sanity-pin test added beyond the plan's literal 5 tests**

- **Found during:** Writing the test file (designing the fixture's URL construction).
- **Issue:** The fixture's URL is constructed as `f"http://{host}:{free_loopback_port}{_HTTP_MOUNT_PATH}"` with `_HTTP_MOUNT_PATH` hard-coded to `"/mcp"`. If the production `agent_brain_mcp.http.MCP_MOUNT_PATH` ever drifts (e.g., a v3 plan changes the mount to `/v2/mcp`), the fixture would silently construct an URL pointing at a non-existent route. The SDK handshake would fail with a vague "protocol error" or "connection closed" rather than a clear "mount path moved" — masking the real regression for the next engineer to investigate.
- **Fix:** Added `test_http_mount_path_matches_production_constant` to the test file. Imports `MCP_MOUNT_PATH` from the production module + `_HTTP_MOUNT_PATH` from the conftest, asserts equality. Test is sync (no async chain needed), marked `@pytest.mark.contract` so it runs under `task contract`. Drift now surfaces at collection time with a clear error message naming both constants and the file to update.
- **Files modified:** `agent-brain-mcp/tests/contract/test_http_transport_contract.py` (the test was added to the same file as the 5 acceptance tests).
- **Verification:** All 6 tests pass (3.84s total); the sanity pin alone takes <0.01s.
- **Committed in:** `9b8eda6` (Task 1 — combined with the 5 acceptance tests and the conftest fixture).
- **Impact on plan:** Strict tightening — the plan's acceptance criteria specifies 5 tests; this adds a 6th sanity pin that protects the fixture itself from silent drift. The plan's 5 acceptance-criteria tests are all present; the sanity pin is additive coverage. No scope creep, no new dependencies, no production code touched.

---

**Total deviations:** 1 (Rule 2 — additive sanity pin).
**Impact on plan:** Strict tightening of the test surface. No deviations on the plan's literal acceptance criteria; all 5 specified tests are present + 1 sanity pin protecting the fixture.

## Issues Encountered

- **Initial Black + Ruff warnings on the first commit attempt** — Black wanted reformatting (one line under the 88-char limit when wrapped); Ruff flagged import order (the production `MCP_MOUNT_PATH` import inside the sanity-pin test body should appear after `from tests.contract.conftest`). Both auto-fixed by `poetry run black tests/contract/test_http_transport_contract.py && poetry run ruff check --fix tests/contract/test_http_transport_contract.py`. No semantic changes; commit happened post-format.
- **`streamable_http_client` deprecation warning** — `mcp 1.12.x` emits `DeprecationWarning: Use streamable_http_client instead.` when the test uses `streamablehttp_client`. The deprecation refers to the underscored alias `streamable_http_client` that older SDKs exposed; `streamablehttp_client` IS the current canonical name in our pinned SDK (verified by `inspect.signature(streamablehttp_client)`). The warning is internal to the SDK's compat shim and will resolve when the SDK pin moves; no action needed for Plan 04. Documented here so future readers don't try to "fix" a working name.

## User Setup Required

**None.** All dependencies (mcp 1.12.x, psutil dev dep, httpx) were already installed by Phase 53 Plan 03's groundwork. The `mcp.client.streamable_http.streamablehttp_client` symbol is already importable in the venv:

```bash
$ cd agent-brain-mcp && poetry run python -c "from mcp.client.streamable_http import streamablehttp_client; print('ok')"
ok
```

SDK signature (verified at execution time, mcp 1.12.x):

```python
streamablehttp_client(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float | datetime.timedelta = 30,
    sse_read_timeout: float | datetime.timedelta = 300,
    terminate_on_close: bool = True,
    httpx_client_factory: McpHttpClientFactory = ...,
    auth: httpx.Auth | None = None,
) -> AsyncGenerator[tuple[MemoryObjectReceiveStream, MemoryObjectSendStream, Callable[[], str | None]], None]
```

Yield tuple shape: `(read, write, session_id_factory)` — absorbed by the defensive `*_` unpack pattern.

## Next Phase Readiness

- **Phase 55 plan 4/5 complete.** Only Plan 05 (root QA gate integration + VALIDATION.md) remains to close milestone v10.2.
- **`mcp_http_session` fixture LOCKED on `9b8eda6`.** Future MCP transport contract tests (hypothetical: UDS transport contract, Phase 4+ v3 work) can reuse the same callable-async-context-manager shape — the fixture interface is forward-stable.
- **Plan 05 (root QA gate integration) scope confirmed:** Plan 04 did NOT modify root `Taskfile.yml` — that edit is Plan 05's deliverable per CONTEXT D-12. Plan 05 will fold `task: mcp:before-push` (which runs `task contract` transitively) into root `task before-push`; once that lands, the HTTP contract suite Plan 04 ships will be CI-enforced automatically.
- **ROADMAP Phase 55 row advances to 4/5 plans complete.** v10.2 milestone advances to 23/24 plans complete (~96%). One plan to ship.

## SDK Version + Yield Tuple Shape Report

- **MCP SDK pin:** `mcp = "^1.12.0"` (unchanged from Phase 53 — no bump).
- **Effective SDK version at execution:** `mcp 1.12.x` (the venv has no `__version__` attribute exposed; `inspect.signature(streamablehttp_client)` confirms the yield-tuple shape).
- **`streamablehttp_client` yield tuple shape:** `(read, write, session_id_factory)` — three elements. `read` is a `MemoryObjectReceiveStream[SessionMessage | Exception]`, `write` is a `MemoryObjectSendStream[SessionMessage]`, `session_id_factory` is a `Callable[[], str | None]`. Plan 04's `async with streamablehttp_client(url) as (read, write, *_):` absorbs the trailing element AND any future additions.

## Fake-server Fixture Reuse Verification

The plan asked: "whether `fake_http_server_module` worked or you had to add a contract-marker variant".

**It worked.** Phase 53 Plan 03's session-scoped `fake_http_server_module` fixture in `tests/conftest.py` (writes `fake_mcp_http_server.py` to a tmp path) was reused verbatim. The `mcp_http_subprocess` factory in `tests/conftest.py` already binds both `free_loopback_port` and `fake_http_server_module` and exposes a `(host, extra_env)` parameter surface — Plan 04's `mcp_http_session` fixture consumes the factory directly without adding a contract-marker variant. Pytest's parent-conftest cascade made the fixtures visible to `tests/contract/` tests automatically. No fixture-marker conflict; the `e2e_http`-marked test file (`test_transport_selection.py`) and the `contract`-marked test file (`test_http_transport_contract.py`) share the same underlying subprocess fixture cleanly because the marker lives on the TEST, not on the fixture.

## Self-Check

Verified after writing SUMMARY.md:

- `agent-brain-mcp/tests/contract/test_http_transport_contract.py` → exists (6 contract tests)
- `agent-brain-mcp/tests/contract/conftest.py` → modified (import added, orphan-scan regex widened, `mcp_http_session` fixture appended, `_HTTP_MOUNT_PATH` constant added)
- `9b8eda6` (Task 1 commit) → in git log
- `poetry run black --check agent_brain_mcp tests` → exit code 0
- `poetry run ruff check agent_brain_mcp tests` → exit code 0
- `poetry run mypy agent_brain_mcp` → exit code 0 (36 source files, no issues)
- `poetry run pytest tests/contract/test_http_transport_contract.py -v -m contract` → 6 passed in 3.84s
- `task contract` → 49 passed in 24.73s
- `task check:layering` → 3 contracts kept (164 files, 414 deps)
- `task before-push` → exit code 0 (416 monorepo CLI tests; coverage gate honored; format/lint/typecheck clean)
- MCP fast path (`poetry run pytest`) → 460 passed, 96 deselected (no regression from Plan 03 baseline)

## Self-Check: PASSED

---

*Phase: 55-validation-and-qa-gate*
*Plan: 04 — Streamable HTTP transport contract test*
*Completed: 2026-06-03*
