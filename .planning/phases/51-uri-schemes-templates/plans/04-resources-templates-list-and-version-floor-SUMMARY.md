---
phase: 51-uri-schemes-templates
plan: 04
subsystem: mcp
tags: [mcp, resources-templates-list, rfc-6570, uri-templates, min-backend-version, version-floor, forward-compat-commitment, phase-51-finalization]

# Dependency graph
requires:
  - phase: 50-server-endpoint-prep-v2-design-doc
    provides: "GET /query/chunk/{id} + GET /graph/entity/{type}/{id} server endpoints + file_sandbox module (consumed by the per-scheme URI handlers; templates list only references them by uriTemplate)"
  - phase: 51-uri-schemes-templates
    provides: "Plans 01-03 — all 4 parameterized URI handlers (chunk, graph-entity, job, file) wired and tested via PARAMETERIZED_HANDLERS"
provides:
  - "resources/templates/list MCP handler advertising 4 RFC 6570 URI templates (URI-05)"
  - "TEMPLATE_REGISTRY: list[ResourceTemplate] in agent_brain_mcp.resources.parameterized (4 entries, byte-identical to Phase 51 CONTEXT decision B)"
  - "MIN_BACKEND_VERSION = '10.2.0' runtime floor — MCP process refuses to start against agent-brain-server < 10.2.0"
  - "agent-brain-mcp/pyproject.toml install-time pin: agent-brain-rag = '^10.2.0', agent-brain-uds = '^10.2.0'"
  - "Forward-compatibility commitment on 4 uriTemplate strings (once published, MCP client libraries lock onto them)"
  - "End-to-end SDK test exercising templates/list + per-scheme reads through real MCP wire protocol"
affects:
  - "52-resource-subscriptions (SUB-04 may subscribe to job://, can rely on template advertisement for client discovery)"
  - "53-streamable-http-transport (templates list must work identically over HTTP transport — covered by Phase 55 contract tests)"
  - "54-remaining-tools (no direct dependency; tools surface independently)"
  - "55-validation-contract-tests-qa-gate (templates list contract pinned here — Phase 55 contract tests assert wire shape from a fresh MCP SDK client)"

# Tech tracking
tech-stack:
  added: []  # no new deps — uses existing mcp SDK ResourceTemplate type
  patterns:
    - "Forward-compatibility commitment via uriTemplate string-equality test (registry → regression test pins exact strings; future change requires deliberate CHANGELOG entry)"
    - "Release-train coupling enforced in two places (runtime MIN_BACKEND_VERSION + install-time pyproject pin) so both checks agree before publication"
    - "Per-template mimeType policy: static advertisement for JSON-backed schemes; None (sniffed per-read) for file:// to avoid misrouting"
    - "RFC 6570 reserved expansion ({+path}) operator preserved by explicit unit test against silent simplification"

key-files:
  created:
    - "agent-brain-mcp/tests/test_resources_templates_list.py — 193 LOC, 13 tests across 3 classes"
    - ".planning/phases/51-uri-schemes-templates/plans/04-resources-templates-list-and-version-floor-SUMMARY.md (this file)"
  modified:
    - "agent-brain-mcp/agent_brain_mcp/resources/parameterized.py — added TEMPLATE_REGISTRY list[ResourceTemplate] with 4 entries (~80 LOC delta)"
    - "agent-brain-mcp/agent_brain_mcp/resources/__init__.py — re-export TEMPLATE_REGISTRY"
    - "agent-brain-mcp/agent_brain_mcp/server.py — @server.list_resource_templates() handler + MIN_BACKEND_VERSION bump (10.0.7 → 10.2.0) + extended import + 17 LOC delta"
    - "agent-brain-mcp/pyproject.toml — agent-brain-rag + agent-brain-uds pins bumped to ^10.2.0 in lockstep with runtime floor"
    - "agent-brain-mcp/tests/test_version_compat.py — expanded from 9 cases to 15 (new floor pinned: rejects 10.1.5/10.1.99 below floor, accepts 10.2.0/10.3.0 at-or-above)"
    - "agent-brain-mcp/tests/test_e2e_stdio.py — added test_e2e_templates_list_and_read_all_schemes (145 LOC delta: new test + fake-backend stubs for chunk/graph-entity/job + E2E_SANDBOX_ROOT injection for file:// + version bumped 10.0.7 → 10.2.0)"
    - "docs/plans/2026-06-02-mcp-v2-subscriptions.md — added §3.2.1 Phase 51 ship outcome subsection"

key-decisions:
  - "uriTemplate strings are byte-identical to Phase 51 CONTEXT decision B — once published, MCP client libraries lock onto them. test_registry_uri_templates_match_expected_set protects the commitment from silent drift."
  - "file://{+path} uses RFC 6570 reserved expansion (operator +) — pinned by a dedicated unit test (test_file_template_uses_reserved_expansion) so future PRs cannot silently revert to the default expansion form, which would percent-encode / as %2F and break filesystem-path expansion."
  - "mimeType policy: static application/json for chunk/graph-entity/job (JSON bodies fully knowable at advertisement time); None for file:// (sniffed per-read by mimetypes.guess_type at the handler — advertising a static MIME would misroute file-type detection at the client side)."
  - "Release-train coupling enforced in both runtime (MIN_BACKEND_VERSION = 10.2.0) and install-time (agent-brain-rag/agent-brain-uds ^10.2.0 in pyproject) so both checks agree. agent-brain-server 10.2.0 MUST publish to PyPI BEFORE agent-brain-mcp 10.2.0; existing release-ordering flow handles propagation timing."
  - "resources.subscribe capability stays False — Phase 51 deliberately does NOT touch get_capabilities(); Phase 52 owns the flip. v1 wire shape preserved for clients that don't yet understand subscriptions."
  - "Static corpus://* resources NOT retrofitted into templates — they live in resources/list as before. Concretely-addressable static URIs (corpus://config etc.) belong on resources/list; parameterized schemes (chunk://, etc.) where every concrete URI is a different resource belong on resources/templates/list. CONTEXT decision A."
  - "MCP SDK auto-detects resourceTemplates capability from handler presence in the pinned spec revision (mcp = ^1.12.0 → 2026-03-26). No explicit capability flag bump required — verified by re-reading lowlevel/server.py:319-327."

patterns-established:
  - "Forward-compat commitment test pattern: a separate test that pins the EXACT advertised string set, paired with inline regression assertions on the operator/expansion form, prevents silent template-string drift across PRs."
  - "Release-train coupling pattern: bump runtime version-floor (MIN_BACKEND_VERSION) and install-time pin (pyproject) in the same commit so the two checks agree at all times. Add new test_floor_is_X_Y_Z assertion to pin the value against silent regression."
  - "Per-scheme mimeType policy pattern: declarative (static MIME on the template) for schemes whose body type is known at advertisement time; None (sniffed per-read) for schemes whose body type depends on the URI parameters."

requirements-completed: [URI-05]

# Metrics
duration: 12min
completed: 2026-06-03
---

# Phase 51 Plan 04: resources/templates/list + MIN_BACKEND_VERSION bump Summary

**MCP clients can now discover the four parameterized URI schemes (`chunk://`, `graph-entity://`, `job://`, `file://`) via `resources/templates/list` with byte-identical Phase 51 CONTEXT decision B `uriTemplate` strings, and the MCP process refuses to start against a pre-Phase-50 backend below the new `MIN_BACKEND_VERSION = "10.2.0"` floor — closing URI-05 and Phase 51 with 17 net new tests including an end-to-end SDK exercise of all four schemes.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-03T05:55:08Z
- **Completed:** 2026-06-03T06:06:59Z
- **Tasks:** 5 implementation tasks + 1 finalization task
- **Files modified:** 7 (2 created, 5 modified)
- **Tests added:** 17 (13 in `test_resources_templates_list.py` + 6 new in `test_version_compat.py` + 1 new e2e test; -2 was old "accepts higher version" replaced with stricter parametrized cases — net +17 vs prior 124 → 141)

## Accomplishments

- **`TEMPLATE_REGISTRY` (4 RFC 6570 templates):** Added `list[types.ResourceTemplate]` in `agent_brain_mcp/resources/parameterized.py` with the four `uriTemplate` strings byte-identical to Phase 51 CONTEXT decision B. The `{+path}` reserved-expansion operator on `file://` preserves filesystem slashes; `mimeType` is `application/json` for the three JSON-backed schemes and `None` (per-read sniff) for `file://`.
- **`@server.list_resource_templates()` handler wired:** Added the handler in `build_server()` alongside the existing `@server.list_resources()`. Returns `list(TEMPLATE_REGISTRY)`. The MCP SDK auto-detects the `resourceTemplates` capability from handler presence — no explicit capability flag bump needed; `resources.subscribe` stays `False` until Phase 52.
- **`MIN_BACKEND_VERSION` bumped `10.0.7` → `10.2.0`:** MCP process now refuses to start against an `agent-brain-server` below 10.2.0 with a clear error referencing the floor. Phase 50's new endpoints (`GET /query/chunk/{id}`, `GET /graph/entity/{type}/{id}`) ship in `agent-brain-server 10.2.0`.
- **Lockstep pyproject pin bump:** `agent-brain-rag` and `agent-brain-uds` bumped to `^10.2.0` in `agent-brain-mcp/pyproject.toml` so install-time and runtime checks agree. The release-train coupling is now enforced in two places.
- **`test_resources_templates_list.py` (13 tests across 3 classes):** Registry-level assertions (4 templates exactly, exact string set, parametrized mimeType per scheme, `{+path}` operator pinning), handler-level assertions (full MCP wire dispatch), and corpus regression (`resources/list` still returns exactly 5 `corpus://*` URIs; does NOT advertise parameterized schemes).
- **`test_version_compat.py` extended (6 new cases):** `test_floor_is_10_2_0` (regression pin), `test_accepts_10_2_0_explicit`, `test_accepts_higher_minor`, `test_rejects_10_1_5_below_floor` (CONTEXT specifics #3 — pre-Phase-50 server gets clean refusal), `test_rejects_10_2_0_minus_one_patch` (boundary check), `test_parse_version` parametrized with new `10.2.0` case.
- **`test_e2e_stdio.py` extended:** `test_e2e_templates_list_and_read_all_schemes` exercises all six URI-05 acceptance criteria through the real MCP Python SDK client + a stdio subprocess. Drives `list_resource_templates()` → 4 templates with exact strings → `read_resource()` for `chunk://stub-chunk-id`, `graph-entity://Function/stub-name`, `job://stub-job-id`, and a real `file:///<tmp>/stub.txt` inside a sandbox root injected via `E2E_SANDBOX_ROOT` env. Fake-backend stubs added for the three server-backed schemes.
- **v2 design doc enriched:** §3.2.1 "Phase 51 ship outcome" subsection documents the forward-compatibility commitment, `{+path}` operator rationale, mimeType policy, release-train coupling, #178 Kuzu SIGSEGV carry-forward, capability advertisement stance, and test count.

## Task Commits

Each task committed atomically with explicit file paths (no `git add -A` / `git add .`):

1. **Task 1: TEMPLATE_REGISTRY + re-export** — `df61962` — `feat(51-04): add TEMPLATE_REGISTRY with 4 RFC 6570 URI templates`
2. **Task 2: server handler + version-floor bump + pyproject pin + version_compat tests** — `4bfdcb4` — `feat(51-04): wire resources/templates/list + bump MIN_BACKEND_VERSION to 10.2.0`
3. **Task 3: test_resources_templates_list.py** — `76bb797` — `test(51-04): cover resources/templates/list + corpus://* regression`
4. **Task 4: test_e2e_stdio.py extension + fake-backend stubs** — `870d763` — `test(51-04): e2e SDK exercise of templates/list + per-scheme reads`
5. **Task 5: v2 design doc Phase 51 §3.2.1 subsection** — `e137191` — `docs(51-04): document Phase 51 ship outcome in v2 design doc`
6. **Plan metadata (this SUMMARY + STATE.md + ROADMAP.md + REQUIREMENTS.md)** — _next commit_

## Files Created/Modified

### Created

- `agent-brain-mcp/tests/test_resources_templates_list.py` (193 LOC) — 13 tests across `TestTemplateRegistry`, `TestListResourceTemplatesHandler`, `TestResourcesListUnchanged`.
- `.planning/phases/51-uri-schemes-templates/plans/04-resources-templates-list-and-version-floor-SUMMARY.md` (this file).

### Modified

- `agent-brain-mcp/agent_brain_mcp/resources/parameterized.py` — added `import mcp.types as types`; added `TEMPLATE_REGISTRY: list[types.ResourceTemplate]` with 4 entries; extended `__all__`. ~80 LOC.
- `agent-brain-mcp/agent_brain_mcp/resources/__init__.py` — re-export `TEMPLATE_REGISTRY` for `server.py` consumption.
- `agent-brain-mcp/agent_brain_mcp/server.py` — extended import block to include `TEMPLATE_REGISTRY`; bumped `MIN_BACKEND_VERSION = "10.0.7"` → `"10.2.0"` with inline rationale comment; added `@server.list_resource_templates()` handler inside `build_server()`.
- `agent-brain-mcp/pyproject.toml` — `agent-brain-rag` and `agent-brain-uds` bumped `^10.1.0` → `^10.2.0` with inline comment explaining lockstep with runtime floor.
- `agent-brain-mcp/tests/test_version_compat.py` — 6 new test methods + parametrized `10.2.0` case; module docstring updated for Phase 51 context.
- `agent-brain-mcp/tests/test_e2e_stdio.py` — fake-backend script now reads `E2E_SANDBOX_ROOT` env, supplies stub responses for `GET /query/chunk/{id}`, `GET /graph/entity/{type}/{id}`, `GET /index/jobs/{id}`, and bumped `/health/` version from `10.0.7` → `10.2.0`; new `test_e2e_templates_list_and_read_all_schemes` test method.
- `docs/plans/2026-06-02-mcp-v2-subscriptions.md` — appended §3.2.1 "Phase 51 ship outcome (updated 2026-06-03 after Plan 04 close)" subsection.

## Decisions Made

All seven `key-decisions` listed in the frontmatter are load-bearing for Phase 51's wire-surface stability and the release-train ordering Phase 52 will inherit. The most consequential:

1. **Forward-compatibility commitment on the four `uriTemplate` strings.** Once 10.2.0 ships, the strings are locked. The `test_registry_uri_templates_match_expected_set` test fails loudly on any silent change, forcing a deliberate CHANGELOG entry.
2. **`{+path}` reserved expansion.** RFC 6570 default expansion percent-encodes `/` as `%2F`, which breaks filesystem-path expansion. The `test_file_template_uses_reserved_expansion` test pins the operator choice so it can't be silently regressed by a "simplify" PR.
3. **Release-train coupling in two places.** Runtime (`MIN_BACKEND_VERSION`) + install-time (pyproject pin) both bumped to `10.2.0`. Server publishes to PyPI first, MCP package follows.

## Deviations from Plan

**None.** All five implementation tasks landed on-plan, in-scope, in single commits. The 6th task (SUMMARY + state metadata) is the standard plan-closure commit. No Rule 1/2/3 auto-fixes were needed during execution; no Rule 4 architectural checkpoints surfaced; no auth gates encountered.

A few defensible micro-decisions taken inline (not deviations, just within-scope refinement):

- **Test count expanded from "≥5 cases" (plan called for 5) to 13.** The plan listed 5 example cases; I expanded to cover parametrized JSON-scheme mimeType per template (3 cases), the `{+path}` operator pinning regression test (decision-load-bearing — flagged in plan risk register), and a corpus-not-advertised-as-parameterized assertion (defensive — protects against future planner adding a parameterized URI to the static registry).
- **`test_version_compat.py` got 6 new cases (plan called for 3).** Added boundary check (`test_rejects_10_2_0_minus_one_patch`) and floor-pin regression test (`test_floor_is_10_2_0`) to fully cover the bump.
- **e2e fake-backend now reads `E2E_SANDBOX_ROOT` env.** Without this, the `file://` read in the e2e test would always hit `/tmp/x` (hardcoded default) and the per-test `tmp_path` file would fall outside the sandbox. The env-injection pattern keeps backward compatibility with the existing 4 e2e tests.

## Issues Encountered

- **Black auto-reformatted the test files on first commit attempt.** Both `test_resources_templates_list.py` and `test_e2e_stdio.py` triggered Black reformatting after initial Write. Standard pattern from prior Phase 51 plans (per Plan 02 SUMMARY); resolved by re-running `poetry run black` and re-staging.
- **Ruff flagged module docstring line length (91 chars).** Tightened the docstring to fit within 88 chars without semantic loss. Black is set to line-length 88; docstrings count.

No other issues encountered. No git history cleanup needed (Plan 03's commit-snapshot-race pattern did NOT recur because Plan 04 ran alone in Wave 3).

## Verification

### Quality gates (run from `agent-brain-mcp/` and repo root):

| Check | Command | Result |
|-------|---------|--------|
| Black | `poetry run black --check agent_brain_mcp tests` | PASS (51 files unchanged) |
| Ruff | `poetry run ruff check agent_brain_mcp tests` | PASS (All checks passed) |
| mypy strict | `poetry run mypy agent_brain_mcp` | PASS (no issues in 24 source files) |
| pytest (MCP) | `poetry run pytest` | PASS (141 passed, 34 deselected — the deselected are e2e tests) |
| pytest (e2e) | `poetry run pytest -m e2e` | PASS (5 passed including new templates/list + per-scheme reads test) |
| import-linter | `task check:layering` | PASS (3 contracts kept, 0 broken) |
| Repo before-push | `task before-push` | PASS (416 tests passed across full monorepo, 80% coverage, exit 0) |

### Test count trajectory

| Plan | Test count after plan close |
|------|----------------------------|
| 51-01 close | 91 (+ regression-pinned via task before-push: 416 monorepo) |
| 51-02 close | 108 (+17 chunk/graph-entity cases) |
| 51-03 close | 124 (+16 file:// cases, -1 placeholder cleanup) |
| **51-04 close** | **141 (+17 templates/list + version-floor + e2e cases)** |

Total Phase 51 net new tests: **50** (across all four plans).

### Phase 51 surface ship

| Phase 51 acceptance criterion (ROADMAP §65-75) | Status |
|---|---|
| 1. `chunk://<chunk_id>` read | Closed by Plan 02 (URI-01) |
| 2. `graph-entity://<type>/<id>` read | Closed by Plan 02 (URI-02) |
| 3. `job://<job_id>` read | Closed by Plan 01 (URI-03) |
| 4. `file://<abs-path>` read | Closed by Plan 03 (URI-04) |
| 5. `resources/templates/list` returns all 4 templates | **Closed by Plan 04 (URI-05)** |

Phase 51 ships. All 5 success criteria met.

## User Setup Required

**None.** The templates/list discovery happens at MCP-protocol startup; no operator configuration needed. The `MIN_BACKEND_VERSION` bump and pyproject pin operate transparently — operators upgrading to `agent-brain-mcp 10.2.0` will need `agent-brain-server >= 10.2.0` on the backend, but the upgrade error message (if they don't) cleanly states the minimum.

## Next Phase Readiness

**Phase 51 is closed.** Ready to ship as part of the v10.2.0 release.

**Phase 52 (Resource subscriptions) can begin:**
- Plan 52-01's `SubscriptionManager.start_polling()` primitive for `job://` reads benefits from the Phase 51 parameterized handler infrastructure being scheme-agnostic — the same `_handle_job_uri` body becomes the polling-loop fetcher, no rewrite needed.
- Plan 52-02 can flip `resources.subscribe` capability to `True` and reuse the dispatcher unchanged.
- All four `uriTemplate` strings are public commitments; Phase 52 cannot redefine them.

**Phase 53 (Streamable HTTP transport)** can begin in parallel — independent of Phase 52. The templates/list handler is transport-agnostic; it will work identically over HTTP because `@server.list_resource_templates()` is wired into the low-level `Server` instance once per `build_server()` call, not per-transport.

**Phase 55 (Validation/contract tests)** has a clear contract to assert against: the four `uriTemplate` strings, the per-scheme `mimeType` policy, the `MIN_BACKEND_VERSION = "10.2.0"` floor. Phase 55's MCP SDK contract tests will replay the wire-shape assertions from `test_resources_templates_list.py` and `test_e2e_templates_list_and_read_all_schemes`.

**No blockers.** All seven quality gates green at HEAD.

## Self-Check: PASSED

Verified at SUMMARY-write time (before the final docs commit):

**Files exist:**
- FOUND: agent-brain-mcp/tests/test_resources_templates_list.py
- FOUND: agent-brain-mcp/agent_brain_mcp/resources/parameterized.py (modified — TEMPLATE_REGISTRY present)
- FOUND: agent-brain-mcp/agent_brain_mcp/resources/__init__.py (modified — TEMPLATE_REGISTRY re-exported)
- FOUND: agent-brain-mcp/agent_brain_mcp/server.py (modified — handler + floor bump)
- FOUND: agent-brain-mcp/pyproject.toml (modified — pin bumped)
- FOUND: agent-brain-mcp/tests/test_version_compat.py (modified — floor pinned)
- FOUND: agent-brain-mcp/tests/test_e2e_stdio.py (modified — e2e test added)
- FOUND: docs/plans/2026-06-02-mcp-v2-subscriptions.md (modified — §3.2.1 added)

**Commits exist:**
- FOUND: df61962 — feat(51-04): add TEMPLATE_REGISTRY with 4 RFC 6570 URI templates
- FOUND: 4bfdcb4 — feat(51-04): wire resources/templates/list + bump MIN_BACKEND_VERSION to 10.2.0
- FOUND: 76bb797 — test(51-04): cover resources/templates/list + corpus://* regression
- FOUND: 870d763 — test(51-04): e2e SDK exercise of templates/list + per-scheme reads
- FOUND: e137191 — docs(51-04): document Phase 51 ship outcome in v2 design doc

**Quality gates (final pass before plan-close):**
- PASSED: poetry run black --check (51 files unchanged)
- PASSED: poetry run ruff check (All checks passed)
- PASSED: poetry run mypy (no issues in 24 source files)
- PASSED: poetry run pytest (141 passed, 34 deselected)
- PASSED: poetry run pytest -m e2e (5 passed including templates/list + per-scheme reads)
- PASSED: task check:layering (3 contracts kept, 0 broken)
- PASSED: task before-push (416 tests passed monorepo-wide, 80% coverage, exit 0)

---
*Phase: 51-uri-schemes-templates*
*Plan: 04-resources-templates-list-and-version-floor*
*Completed: 2026-06-03*
