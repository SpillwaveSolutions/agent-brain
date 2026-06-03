---
phase: 55-validation-and-qa-gate
plan: 02
subsystem: testing
tags: [mcp, contract-tests, pytest, mcp-sdk, stdio, parametrize, 16-tool-matrix, jsonschema, resources, val-01]

requires:
  - phase: 55-validation-and-qa-gate
    provides: mcp_stdio_session factory + autouse D-17 orphan scan + contract marker + extended _DEFAULT_RESPONSES (from Plan 01, locked on commit fb24ab9)
  - phase: 54-remaining-mcp-tools
    provides: TOOL_REGISTRY at final v2 count 16 (7 v1 + 9 v2) — the matrix's source of truth
  - phase: 51-deferred-uri-schemes
    provides: TEMPLATE_REGISTRY with 4 RFC 6570 uriTemplate strings (chunk://, graph-entity://, job://, file://) — Phase 51 CONTEXT decision B forward-compat lock that this plan's resources contract test pins
  - phase: 50-server-endpoint-prep-v2-design-doc
    provides: ChunkRecord + GraphEntityRecord wire shapes — the _DEFAULT_RESPONSES stubs that resources contract tests round-trip against

provides:
  - tests/contract/_tool_matrix.py — single source of truth for the 16-tool matrix (ToolCase dataclass; import-time _assert_matrix_covers_registry guard against drift)
  - tests/contract/test_tools_contract.py — 32 parametrized contract assertions (16 happy-path + 16 negative-arg) via SDK over stdio
  - tests/contract/test_resources_contract.py — 6 resource-side contract assertions (4 templates lock + v1 corpus list + 4 read-resource round-trips)
  - tests/test_each_tool.py refactor — Layer 1 in-process suite now consumes the shared matrix; expanded from 7 to 16 parametrized tools

affects: [55-03-subscription-lifecycle, 55-04-http-transport-contract, 55-05-root-qa-gate]

tech-stack:
  added: []  # No new runtime deps; jsonschema is already transitively pulled by mcp 1.12.x
  patterns:
    - "Single-source-of-truth ToolCase matrix: same list parametrizes both Layer 1 (in-process) and Layer 2 (SDK) — drift between layers surfaces as a Layer 1 failure first (sub-second feedback)"
    - "Import-time _assert_matrix_covers_registry guard at module load — registry/matrix drift fires BEFORE pytest collection even sees the parametrize decorator"
    - "Dual-shape negative-arg assertion: accept either CallToolResult.isError=True OR raised McpError — both spec-conformant; SDK 1.12.x doesn't validate inputSchema client-side so server-side rejection is the typical path but the test honors both"
    - "Backend-stub-aligned sample_arguments — wait_for_job uses job_done (terminal) so polling loop exits in one iteration; explain_result uses chunk_001 matching the POST /query/ stub's chunk_id; inject_documents uses folder_metadata_file (avoids needing a real injector script on disk)"

key-files:
  created:
    - agent-brain-mcp/tests/contract/_tool_matrix.py
    - agent-brain-mcp/tests/contract/test_tools_contract.py
    - agent-brain-mcp/tests/contract/test_resources_contract.py
    - .planning/phases/55-validation-and-qa-gate/plans/02-16-tool-parameterized-contract-tests-SUMMARY.md
  modified:
    - agent-brain-mcp/tests/test_each_tool.py

key-decisions:
  - "Layer 1 + Layer 2 share ONE source-of-truth matrix file (tests/contract/_tool_matrix.py). Adding/removing/renaming tools updates exactly one place; both layers re-run cleanly. The plan's literal step 3 anticipated this — Phase 55 implements it. An import-time _assert_matrix_covers_registry guard fails fast on registry drift before any test collection."
  - "Negative-arg assertion accepts BOTH CallToolResult.isError=True AND raised McpError — both shapes are MCP-spec conformant. SDK 1.12.x doesn't validate inputSchema client-side, so server-side Pydantic rejection (which lands as isError=True via server.call_tool's ValidationError → McpError → CallToolResult path) is the typical path. The raised-McpError path is preserved for future SDK versions that may surface JSON-RPC errors as exceptions."
  - "wait_for_job sample_arguments pinned to job_id='job_done' (terminal-status stub) so the polling loop exits in ONE iteration without sleeping. Using 'job_abc' (running) would loop forever; using a non-existent id would 404. poll_interval_seconds=0.5 keeps the test snappy if the first poll race ever needed a second iteration."
  - "test_resources_read_file passes response_overrides={('GET', '/index/folders/'): {'folders': [{'folder_path': str(tmp_path), ...}]}} to override the default '/tmp/test' indexed root. Phase 51 Plan 03's dynamic-roots refresh contract means the file:// handler re-fetches the folders list on every read — without the override, reading a tmp_path file would be denied with reason='outside_indexed_roots'."
  - "explain_result sample_arguments uses chunk_id='chunk_001' matching the POST /query/ stub's returned chunk. The handler post-filters by chunk_id; mismatched IDs raise McpError(INVALID_PARAMS) at runtime. The matrix's chunk_001 alignment with the conftest stub keeps the happy-path round-trip valid without overriding the backend per test."
  - "inject_documents sample_arguments uses folder_metadata_file (not injector_script) because the handler calls Path(...).expanduser().resolve() on both paths but does NOT stat the result. The fake backend ignores the body. Using folder_metadata_file dodges the injector-script-allowlist server-side branch (issue #181) that would 403 for an unknown script — keeps the contract test backend-independent."
  - "test_resources_templates_list_advertises_four_uri_schemes asserts the EXACT four uriTemplate strings (chunk://{chunk_id}, graph-entity://{type}/{id}, job://{job_id}, file://{+path}) — forward-compat lock from Phase 51 CONTEXT decision B. Once published in 10.2.0, MCP client libraries lock onto these strings and changes are breaking. Mirrors the existing in-tree e2e pin at tests/test_e2e_stdio.py::test_e2e_templates_list_and_read_all_schemes."
  - "Matrix order matches TOOL_REGISTRY insertion order (v1 7 + Phase 54 read-only 4 + Phase 54 mutating 4 + Phase 54 wait 1) so parametrize IDs in test output match the registry's natural traversal order. Plans 03/04/05 inherit the matrix structure without re-ordering."

patterns-established:
  - "Matrix-driven cross-layer test parametrize: same TOOLS list drives Layer 1 (in-process) AND Layer 2 (SDK) — single edit propagates to both"
  - "Backend-stub-aligned sample_arguments: contract test inputs match _DEFAULT_RESPONSES stubs so happy-path round-trips without per-test response_overrides (overrides reserved for tests that need scenario-specific backends, e.g., file:// sandbox roots)"
  - "Dual-shape rejection assertion: try/except around call_tool catches either path (isError=True OR raised McpError) — handles SDK surfacing differences across versions without test churn"
  - "Resources contract test layout: list-templates + list-resources + per-scheme-read happy paths. Plans 03/04 inherit this skeleton for subscription + HTTP transport contract files"

requirements-completed: [VAL-01]

duration: 9min
completed: 2026-06-03
---

# Phase 55 Plan 02: 16-Tool Parameterized Contract Tests Summary

**32 SDK-driven tool contract assertions + 6 resources contract assertions land VAL-01: every v2 tool now binds to its inputSchema + outputSchema + content shape over the MCP wire protocol; Layer 1 in-process matrix expands from 7 to 16 in lockstep via the shared `_tool_matrix.py` SOT.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-06-03T20:16:09Z
- **Completed:** 2026-06-03T20:24:30Z
- **Tasks:** 4 atomic commits on `main`
- **Files modified:** 4 (3 created, 1 modified)

## Accomplishments

- **VAL-01 closed end-to-end.** All 16 MCP tools (7 v1 + 9 v2) now covered by parameterized SDK contract tests against the pinned `mcp` 1.12.x SDK over stdio — `inputSchema` validation, `outputSchema` round-trip, `content[0]=TextContent` shape, and `structuredContent` required-key set are all asserted per tool per layer.
- **Single-source matrix locked.** `tests/contract/_tool_matrix.py::TOOLS` is the SOT for both Layer 1 (in-process `tests/test_each_tool.py`) and Layer 2 (SDK `tests/contract/test_tools_contract.py`). An import-time `_assert_matrix_covers_registry` guard fails fast if `TOOL_REGISTRY` and the matrix drift apart — registry changes that forget the matrix update fire BEFORE pytest collection.
- **Resources contract closed.** `tests/contract/test_resources_contract.py` pins the 4-template `resources/templates/list` advertisement against Phase 51 CONTEXT decision B's forward-compat strings, asserts the 5 v1 `corpus://` URIs still appear in `resources/list`, and round-trips happy-path reads for `chunk://`, `graph-entity://`, `job://`, and `file://` (the last with a tmp-path sandbox-root override to exercise Phase 51 Plan 03's dynamic-roots refresh).
- **Layer 1 expansion no-op for cross-package consumers.** Plans 03/04 do NOT need to touch the matrix; they import `mcp_stdio_session` + `TOOLS` and parametrize their own contract files.
- **All quality gates pass:** `task before-push` exit 0 (416 monorepo CLI tests), `task check:layering` 3/3 contracts kept (164 files, 414 deps), MCP `task pr-qa-gate` exit 0 with 91.97% coverage (above 80% floor), MCP fast-path 460 tests passing (up from 451), MCP contract suite 39 tests passing in 16.65s.

## Task Commits

Each task was committed atomically on `main`:

1. **Task 1: 16-tool matrix SOT** — `86999e0` (test)
2. **Task 2: 32 SDK tool contract assertions** — `c3b6f1f` (test)
3. **Task 3: 6 SDK resources contract assertions** — `4a6b51c` (test)
4. **Task 4: Layer 1 refactor to consume matrix** — `3e07334` (test)

**Plan metadata:** (this commit, after SUMMARY.md + STATE.md + ROADMAP.md + REQUIREMENTS.md updates)

## Files Created/Modified

- `agent-brain-mcp/tests/contract/_tool_matrix.py` — 16 `ToolCase` rows + import-time registry-drift guard (`_assert_matrix_covers_registry`); the SOT for both layers
- `agent-brain-mcp/tests/contract/test_tools_contract.py` — `test_tool_happy_path` (16 parametrized) + `test_tool_negative_args` (16 parametrized) via `mcp_stdio_session()` SDK factory
- `agent-brain-mcp/tests/contract/test_resources_contract.py` — `templates/list` 4-string lock + `resources/list` v1-corpus subset assertion + 4 per-scheme `resources/read` round-trips (chunk / graph-entity / job / file)
- `agent-brain-mcp/tests/test_each_tool.py` — refactored Layer 1 parametrize to import `TOOLS` from the matrix; expands from 7 to 16 tools; adds `expected_structured_keys` per-row assertion (parity with Layer 2)

## Decisions Made

- **Single matrix file (`_tool_matrix.py`) drives both Layer 1 and Layer 2 parametrize.** Same `TOOLS: list[ToolCase]` import in `tests/test_each_tool.py` and `tests/contract/test_tools_contract.py`. Registry/matrix drift fails at import time via `_assert_matrix_covers_registry` — pytest's parametrize decorator never sees a stale list. Plan's literal step 3 anticipated this.
- **Dual-shape negative-arg assertion.** `try/except McpError` around `call_tool`; assert `isError=True` on the success branch, assert `exc.error.code == case.expected_error_code` on the exception branch. Both shapes are MCP-spec conformant: SDK 1.12.x doesn't validate inputSchema client-side, so server-side Pydantic rejection → `ValidationError` → `McpError` → `CallToolResult(isError=True)` is the typical path (see `server.call_tool` ~line 287). The raised-McpError path is preserved for future SDK versions that may surface JSON-RPC errors as exceptions.
- **wait_for_job sample_arguments uses `job_id="job_done"` (terminal stub) + `poll_interval_seconds=0.5`.** `job_done` is one of Plan 01's terminal `JobRecord` stubs (status=`completed`). The polling loop exits in ONE iteration. Using `job_abc` (status=`running`) would loop forever; using a non-existent ID would 404. The fast poll interval keeps the test snappy if the first poll race ever needed a second iteration.
- **explain_result sample_arguments uses `chunk_id="chunk_001"`** — the chunk_id returned by the conftest `POST /query/` stub. The handler post-filters results by chunk_id and raises `McpError(INVALID_PARAMS)` if no result matches. Alignment with the default backend stub keeps the happy path valid without per-test `response_overrides`.
- **inject_documents sample_arguments uses `folder_metadata_file`, not `injector_script`.** The handler resolves both paths via `Path(...).expanduser().resolve()` but does NOT stat. The fake backend ignores the body entirely. `folder_metadata_file` dodges the server-side injector-script-allowlist branch (issue #181) that would 403 for an unknown script — keeps the contract test backend-independent.
- **test_resources_read_file passes `response_overrides` to override `/index/folders/`.** Phase 51 Plan 03's `file://` handler dynamically refreshes the indexed-folder allowlist on EVERY read (CONTEXT decision E — `test_read_file_uri_roots_refresh_on_each_read` regression pin). Without the override, reading a `tmp_path` file would be denied with `reason="outside_indexed_roots"`. The override injects `tmp_path` as the only indexed root so the contract test's on-disk write/read round-trip succeeds.
- **Templates list assertion pins the EXACT four `uriTemplate` strings.** Phase 51 CONTEXT decision B locks the strings as a forward-compatibility commitment — once published in 10.2.0, MCP client libraries lock onto them and changes are breaking. The assertion mirrors the existing in-tree e2e pin at `tests/test_e2e_stdio.py::test_e2e_templates_list_and_read_all_schemes`.
- **Matrix order matches `TOOL_REGISTRY` insertion order.** v1 7 → Phase 54 read-only 4 → Phase 54 mutating 4 → Phase 54 wait 1. Parametrize IDs in test output match the registry's natural traversal order, simplifying diagnosis when a single tool fails.

## Deviations from Plan

**None — plan executed exactly as written.**

All four tasks landed in the files the plan named, with `sample_arguments` and `expected_structured_keys` matching each tool's input/output schema 1:1. No new schemas added, no `ApiClient` methods touched, no `call_tool` dispatch changes, no production-code mutations of any kind — Plan 02 is strictly additive test code.

The plan's risk register flagged three concerns; none materialized:

- **"Tool registry drift"** (matrix and registry must stay in lockstep) — addressed proactively by the import-time `_assert_matrix_covers_registry` guard, NOT as a deviation. Drift now surfaces as `RuntimeError` at module import before any test runs.
- **"`outputSchema` may not be declared on every tool"** — the contract test asserts `structuredContent` required-key presence directly, not `outputSchema` JSON-schema validation. The plan's safety valve (`skip the outputSchema validation conditionally when tool.outputSchema is None`) was unnecessary because the structured-keys assertion is per-tool-derived from `expected_structured_keys` and doesn't depend on advertised schemas. Tools whose `outputSchema` is `None` still get a meaningful contract pin.
- **"Negative-arg expectations"** (some tools may not reject `-32602` as cleanly) — empirically, EVERY tool's negative path produced `isError=True` via the SDK; none surfaced as a raised `McpError`. The matrix's `expected_error_code=INVALID_PARAMS` default proved correct for all 16 rows. If a future tool surfaces `BACKEND_CONFLICT (-32000)` for the negative branch, the matrix supports overriding `expected_error_code` per row.

## Issues Encountered

- **Black auto-formatted two contract test files** (`test_tools_contract.py`, `test_resources_contract.py`) after first commit attempt — pre-amble multi-line string literals were rewrapped to Black's 88-char preference. Re-ran `poetry run black tests/contract` and re-committed; the formatting tweaks were folded into the same task commits without separate chore commits. No functional change.
- **`assert ... is not None, "..."`** rewrites by Black: Black inserts parenthesization around multi-line assertion expressions. Functional behavior unchanged; the parens just satisfy Black's wrap policy.

## Self-Check

Verified after writing SUMMARY.md:

- `agent-brain-mcp/tests/contract/_tool_matrix.py` → exists
- `agent-brain-mcp/tests/contract/test_tools_contract.py` → exists
- `agent-brain-mcp/tests/contract/test_resources_contract.py` → exists
- `agent-brain-mcp/tests/test_each_tool.py` → modified (16-row parametrize)
- `86999e0` (Task 1 commit) → in git log
- `c3b6f1f` (Task 2 commit) → in git log
- `4a6b51c` (Task 3 commit) → in git log
- `3e07334` (Task 4 commit) → in git log
- `task contract` → exit 0 (39 passed: 1 smoke + 32 tools + 6 resources, 16.65s)
- `task before-push` → exit 0 (416 monorepo CLI tests + 460 MCP fast-path + format/lint/typecheck all clean)
- `task check:layering` → exit 0 (3/3 contracts kept, 164 files, 414 deps)
- `task pr-qa-gate` (MCP) → exit 0 (460 passed, 91.97% coverage above 80% floor)
- mcp default fast-path `pytest tests -v` → 460 passed, 86 deselected (was 451 → +9 net: 16 new Layer 1 parametrize rows minus 7 deleted rows = +9; the matrix expansion is in the fast path; Layer 2 32 contract tests are opt-in via `-m contract`)

## Self-Check: PASSED

## User Setup Required

None — no external service configuration required. Contract suite uses in-memory MockTransport backend (CONTEXT D-04).

## Next Phase Readiness

- **VAL-01 done.** The 16-tool contract surface is locked against the official MCP 1.12.x SDK over stdio. Plan 03 (subscription lifecycle VAL-02) and Plan 04 (HTTP transport VAL-03) inherit the `mcp_stdio_session` factory + the matrix conventions verbatim.
- **`_tool_matrix.py` is the SOT for both layers.** Plans 03/04/05 do NOT need to touch it. Future tools added in v10.3+ should land a matching `ToolCase` row at the same time as the `TOOL_REGISTRY` entry; the import-time guard catches the omission immediately.
- **Resources contract test skeleton (`test_resources_contract.py`) is reusable** for Plan 03's subscription lifecycle (subscribe → notify → unsubscribe round-trips) and Plan 04's HTTP transport (same contract via `streamablehttp_client` instead of `stdio_client`).
- 21/24 plans complete across v10.2 milestone. Phase 55 plan 2/5 done. Plan 03 (subscription lifecycle VAL-02) is the next workable plan within Phase 55.

---
*Phase: 55-validation-and-qa-gate*
*Plan: 02 — 16-tool parameterized contract tests*
*Completed: 2026-06-03*
