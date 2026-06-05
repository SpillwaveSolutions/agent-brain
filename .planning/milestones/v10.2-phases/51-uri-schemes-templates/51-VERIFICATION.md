---
phase: 51-uri-schemes-templates
verified: 2026-06-03T07:15:00Z
status: passed
score: 5/5 success criteria verified
re_verification:
  previous_status: null
  previous_score: null
  gaps_closed: []
  gaps_remaining: []
  regressions: []
requirements_coverage:
  URI-01: satisfied
  URI-02: satisfied
  URI-03: satisfied
  URI-04: satisfied
  URI-05: satisfied
key_links_verified:
  - from: agent_brain_mcp.server.read_resource
    to: agent_brain_mcp.resources.parameterized.PARAMETERIZED_HANDLERS
    via: scheme-prefix dispatch + dual-return ReadResourceContents check
    status: wired
  - from: agent_brain_mcp.security.__init__
    to: agent_brain_server.security.file_sandbox
    via: pure re-export (no logic)
    status: wired-share-not-fork
  - from: agent_brain_mcp.resources.parameterized.TEMPLATE_REGISTRY
    to: server.list_resource_templates handler
    via: list(TEMPLATE_REGISTRY) returned verbatim
    status: wired
  - from: agent_brain_mcp.server.MIN_BACKEND_VERSION
    to: server.check_backend_version startup gate
    via: constant comparison at main_async startup
    status: wired
---

# Phase 51: URI schemes + templates Verification Report

**Phase Goal:** All four deferred URI schemes (`chunk://`, `graph-entity://`, `job://`, `file://`) are addressable via MCP `resources/read`, and `resources/templates/list` advertises them so model clients can discover them programmatically. Plus the MCP backend-version floor is raised to `10.2.0` so MCP processes refuse to connect to pre-Phase-50 servers.

**Verified:** 2026-06-03
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | MCP client can call `resources/read` with `chunk://<chunk_id>` and receive ChunkRecord JSON | VERIFIED | `parameterized.py:240 _handle_chunk_uri` wired in `PARAMETERIZED_HANDLERS["chunk"]` (line 555); `client.py:126 get_chunk()` hits `GET /query/chunk/{id}`; `test_resources_read_parameterized.py::TestReadResourceChunkUri` (3 cases: success + missing_id + 404-refines-data) + e2e `test_e2e_stdio.py::test_e2e_templates_list_and_read_all_schemes` exercises `chunk://stub-chunk-id` through real MCP SDK |
| 2 | MCP client can call `resources/read` with `graph-entity://<type>/<id>` and receive GraphEntityRecord JSON | VERIFIED | `parameterized.py:308 _handle_graph_entity_uri` wired in `PARAMETERIZED_HANDLERS["graph-entity"]` (line 556); `client.py:136 get_graph_entity()` hits `GET /graph/entity/{type}/{id}`; parser allows hierarchical ids with embedded `/` (line 165); `TestReadResourceGraphEntityUri` covers 8 cases including 503 graphrag_disabled + kuzu_unavailable reason extraction; e2e read exercises `graph-entity://Function/stub-name` |
| 3 | MCP client can call `resources/read` with `job://<job_id>` and receive current job state | VERIFIED | `parameterized.py:202 _handle_job_uri` wired in `PARAMETERIZED_HANDLERS["job"]` (line 554); routes through existing `ApiClient.get_job()`; `TestReadResourceJobUri` (5 cases: success + full-detail passthrough + missing-id + 404 + trailing-slash); e2e read exercises `job://stub-job-id` via real MCP SDK |
| 4 | MCP client can call `resources/read` with `file://<abs-path>` and either receive file contents or a sandbox denial error | VERIFIED | `parameterized.py:361 _handle_file_uri` wired in `PARAMETERIZED_HANDLERS["file"]` (line 557); roots fetched on EVERY read via `client.list_folders()` (no cache, line 419); `is_path_allowed` + `canonicalize_path` from shared shim; `test_resources_read_file.py` covers all 4 Phase 50 deny reasons (outside_indexed_roots, hidden_file, symlink_escape, size_limit) + text/binary dispatch + `..` traversal + hidden-inside-root allowance + roots-refresh-on-each-read regression test |
| 5 | MCP client calling `resources/templates/list` receives templates for all four schemes | VERIFIED | `parameterized.py:586 TEMPLATE_REGISTRY` has exactly 4 entries with the byte-identical Phase 51 CONTEXT decision B strings: `chunk://{chunk_id}`, `graph-entity://{type}/{id}`, `job://{job_id}`, `file://{+path}`. `server.py:166 @server.list_resource_templates()` returns `list(TEMPLATE_REGISTRY)`. mimeType policy: `application/json` for JSON schemes; omitted for `file://` (sniffed per-read). `test_resources_templates_list.py` (13 tests) pins the exact strings + `{+path}` reserved-expansion operator + corpus regression |

**Score:** 5/5 truths verified — all success criteria met.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agent-brain-mcp/agent_brain_mcp/resources/parameterized.py` | Dispatcher + 4 handlers + TEMPLATE_REGISTRY | VERIFIED | 647 LOC; all 4 handlers wired; TEMPLATE_REGISTRY at line 586 with exact CONTEXT decision B strings |
| `agent-brain-mcp/agent_brain_mcp/security/__init__.py` | Pure re-export shim (no logic) | VERIFIED | 55 lines, docstring explicitly forbids logic, re-exports `DEFAULT_MAX_READ_BYTES`, `canonicalize_path`, `is_path_allowed`, `list_sandbox_roots` from `agent_brain_server.security.file_sandbox` |
| `agent-brain-mcp/agent_brain_mcp/server.py` | Scheme dispatcher + templates handler + MIN_BACKEND_VERSION=10.2.0 | VERIFIED | Line 61: `MIN_BACKEND_VERSION = "10.2.0"`; line 166: `@server.list_resource_templates()` returns `list(TEMPLATE_REGISTRY)`; lines 196-231: scheme-prefix dispatch with dual-return `isinstance(ReadResourceContents)` check; legacy corpus path preserved at line 234 |
| `agent-brain-mcp/agent_brain_mcp/client.py` | `get_chunk` + `get_graph_entity` methods | VERIFIED | Line 126: `get_chunk(chunk_id)`; line 136: `get_graph_entity(entity_type, entity_id)`; both go through existing `_get` → `raise_for_status` pipeline |
| `agent-brain-mcp/agent_brain_mcp/resources/__init__.py` | Re-exports TEMPLATE_REGISTRY, PARAMETERIZED_HANDLERS, etc. | VERIFIED | Line 12-19: imports + re-exports all 6 names |
| `agent-brain-mcp/pyproject.toml` | `agent-brain-rag` and `agent-brain-uds` pinned `^10.2.0` | VERIFIED | Lines 41-42: both pinned at `^10.2.0` |
| `agent-brain-mcp/tests/test_resources_templates_list.py` | Templates list + uriTemplate strings + corpus regression | VERIFIED | 13 tests across 3 classes; pins exact strings (lines 28-31) + `{+path}` operator (line 85-95) + mimeType policy (lines 37-41) + corpus-not-advertised-as-template regression (line 156) |
| `agent-brain-mcp/tests/test_resources_read_file.py` | file:// e2e + all sandbox deny reasons | VERIFIED | 352 LOC, 17 tests covering parse_uri + e2e + every Phase 50 deny rule + roots-refresh-on-each-read regression |
| `agent-brain-mcp/tests/test_resources_read_parameterized.py` | dispatcher + job/chunk/graph-entity handlers | VERIFIED | Contains TestReadResourceJobUri/ChunkUri/GraphEntityUri classes covering happy-path + error-path for all 3 server-backed schemes |
| `agent-brain-mcp/tests/test_version_compat.py` | Floor bumped to 10.2.0 + pre-Phase-50 rejection | VERIFIED | Line 47: `assert MIN_BACKEND_VERSION == "10.2.0"`; tests reject 10.1.5 (line 68) and 10.1.99 boundary (line 80) |
| `agent-brain-mcp/tests/test_e2e_stdio.py` | e2e SDK exercise of templates/list + 4 schemes | VERIFIED | Line 239: `test_e2e_templates_list_and_read_all_schemes`; reads chunk/graph-entity/job/file URIs through real MCP Python SDK + stdio subprocess |
| `agent-brain-server/agent_brain_server/security/file_sandbox.py` | Phase 50 deliverable with expected public API | VERIFIED | Exports `canonicalize_path`, `is_path_allowed`, `list_sandbox_roots`, `DEFAULT_MAX_READ_BYTES` matching Plan 03 SUMMARY claim |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `server.read_resource` | `parse_uri()` + `PARAMETERIZED_HANDLERS[scheme]` | scheme-prefix dispatch (lines 196-198) | WIRED | Dispatch runs BEFORE legacy `RESOURCE_REGISTRY.get()` so corpus paths stay byte-identical to v1 |
| `parameterized._handle_file_uri` | `agent_brain_mcp.security.is_path_allowed` | shim re-export | WIRED, SHARED-NOT-FORKED | Shim is logic-free (verified by reading every line of `security/__init__.py`); imports come straight from `agent_brain_server.security.file_sandbox` |
| `_handle_file_uri` | `ApiClient.list_folders()` | re-fetched on every read | WIRED, NO-CACHE | Line 419: `await asyncio.to_thread(client.list_folders)` runs once per `file://` read; CONTEXT decision E pinned by regression test (`test_read_file_uri_roots_refresh_on_each_read`) |
| `server.list_resource_templates` | `TEMPLATE_REGISTRY` | `list(TEMPLATE_REGISTRY)` returned verbatim | WIRED | MCP SDK auto-detects `resourceTemplates` capability from handler presence — no explicit capability flag bump needed; verified `resources.subscribe` stays False at server.py:341-347 |
| `server.main_async` | `check_backend_version(MIN_BACKEND_VERSION)` | startup gate (line 383) | WIRED | MCP process refuses to start against backend below 10.2.0 with structured McpError carrying `backendVersion` and `minimum` in data |
| `_handle_chunk_uri` / `_handle_graph_entity_uri` / `_handle_job_uri` | `errors.raise_for_status` | inherited via `ApiClient._get` | WIRED | 404 → INVALID_PARAMS, 503 → SERVICE_INDEXING preserved; each handler catches `McpError` and refines `data` with scheme + scheme-specific id (decision D); original error code preserved |
| `_handle_graph_entity_uri` | `_extract_graph_entity_reason` slug extraction | substring scan against `{graphrag_disabled, kuzu_unavailable}` | WIRED | 503 detail.error promoted to `data["reason"]` so MCP clients route on the slug without parsing `cause` strings — #178 Kuzu SIGSEGV mitigation contract |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| URI-01 | Plan 51-02 | Client can read `chunk://<chunk_id>` via MCP `resources/read` | SATISFIED | `_handle_chunk_uri` + `ApiClient.get_chunk` + 3 TestReadResourceChunkUri cases + e2e SDK test |
| URI-02 | Plan 51-02 | Client can read `graph-entity://<type>/<id>` via MCP `resources/read` | SATISFIED | `_handle_graph_entity_uri` + `ApiClient.get_graph_entity` + 8 TestReadResourceGraphEntityUri cases (incl. hierarchical-id + 503 kuzu_unavailable routing) + e2e test |
| URI-03 | Plan 51-01 | Client can read `job://<job_id>` via MCP `resources/read` | SATISFIED | `_handle_job_uri` + reuses existing `ApiClient.get_job` + 5 TestReadResourceJobUri cases + e2e test |
| URI-04 | Plan 51-03 | Client can read `file://<abs-path>` gated by indexed roots and sandbox | SATISFIED | `_handle_file_uri` + shared `security` shim + 11 e2e TestReadResourceFileUri cases (all 4 deny reasons + traversal + hidden-inside-root + roots-refresh regression) + 6 TestParseUriFile parser tests + e2e SDK test reading inside `E2E_SANDBOX_ROOT` |
| URI-05 | Plan 51-04 | Server responds to MCP `resources/templates/list` with templates for all 4 schemes | SATISFIED | `TEMPLATE_REGISTRY` with byte-identical CONTEXT decision B strings + `@server.list_resource_templates()` handler + 13 test_resources_templates_list.py tests pinning exact strings, mimeType policy, `{+path}` operator, and corpus regression + e2e SDK test |

**No orphaned requirements.** Every URI-0X requirement maps to a plan, has implementation evidence, and is marked complete in REQUIREMENTS.md (lines 23-27 and 95-99).

### Anti-Patterns Scan

| File | Issue Type | Severity | Result |
|------|-----------|----------|--------|
| `parameterized.py` | TODO/FIXME/placeholder | Info | None — `_handle_not_implemented` retained intentionally as documented future-extension hook (lines 518-537); not active code path |
| `security/__init__.py` | Logic in re-export shim | Blocker if present | None — file is 55 lines of pure import re-export, docstring explicitly forbids logic |
| `server.py` | Capability advertisement drift | Blocker if changed | None — `resources.subscribe` still False at line 341-347; Phase 52 contract preserved |
| `server.py` | Backend version floor | Blocker | None — `MIN_BACKEND_VERSION = "10.2.0"` at line 61 with inline rationale comment |
| `pyproject.toml` | install-time pin lockstep | Blocker | None — both `agent-brain-rag` and `agent-brain-uds` at `^10.2.0` (lines 41-42), matching runtime floor |

**No anti-patterns found.**

### Phase 50 → Phase 51 Surface Contract

**HELD.** The shim `agent-brain-mcp/agent_brain_mcp/security/__init__.py` imports the four names listed in Phase 50 Plan 04 SUMMARY:
- `DEFAULT_MAX_READ_BYTES` (constant) — found at `file_sandbox.py:75`
- `canonicalize_path` (function) — found at `file_sandbox.py:107`
- `is_path_allowed` (function) — found at `file_sandbox.py:155`
- `list_sandbox_roots` (function) — found at `file_sandbox.py:238`

Verified by `grep` of public symbols and by `poetry run pytest` succeeding (an import-time mismatch would have raised `ImportError`).

### Sandbox: SHARED, NOT FORKED

**VERIFIED.** Read all 55 lines of `agent-brain-mcp/agent_brain_mcp/security/__init__.py`. Module contains:
- Docstring explicitly forbidding logic ("THIS MODULE MUST NOT CONTAIN LOGIC")
- A single `from agent_brain_server.security.file_sandbox import (...)` statement
- A single `__all__` list re-exporting the 4 imported names

No additional functions, classes, constants, or business logic. The `agent_brain_server` module remains the single source of truth for path policy. Drift between server-side and MCP-side `file://` reads is structurally impossible without a deliberate refactor.

### Layering Contract

**HELD.** `task check:layering` exits 0:
```
Contracts: 3 kept, 0 broken.
- server has no upward deps KEPT
- uds touches only server.models KEPT
- mcp never calls server internals KEPT
```

The `mcp-never-calls-server-internals` contract explicitly forbids imports from `agent_brain_server.services`, `.api`, `.indexing`, `.storage`, `.config`, `.providers`, `.runtime`, `.storage_paths`, `.job_queue`. It does NOT forbid `agent_brain_server.security` — which is the canonical mechanism by which Plan 03's shim is permitted. PLAN.md line 84 documents the intent ("MAY import from `agent_brain_server.models` (existing) and `agent_brain_server.security` (NEW — Plan 03 adds this import)"). No `.importlinter` config change was required (consistent with that line in PLAN.md), and the existing forbidden-modules list already covered the internals MCP must not touch.

### Regression: All 5 Static `corpus://*` Resources Still Work

**VERIFIED.** Grep of `agent-brain-mcp/agent_brain_mcp/resources/corpus.py` shows all 5 entries (`corpus://config`, `corpus://status`, `corpus://health`, `corpus://providers`, `corpus://folders`) unchanged. `test_resources_list.py` and `test_resources_read.py` test classes pass (90 tests in the combined run of all resources tests). Dispatcher routes `corpus://*` URIs through the legacy `RESOURCE_REGISTRY.get(uri_str)` path (server.py:234), which was unchanged from v1 except for the single-slash strip bug fix in Plan 01 (which preserves `corpus://config` verbatim — verified by Plan 01 across 7 URI shapes).

### Capability Advertisement

**VERIFIED.** `resources.subscribe = False` is preserved. The `@server.list_resource_templates()` handler is added without flipping any capability flag — the MCP SDK auto-detects `resourceTemplates` capability from handler presence (per the spec revision pinned in `pyproject.toml`: `mcp = ^1.12.0` → 2026-03-26 spec). The `get_capabilities()` call at `server.py:341` continues to specify `notification_options=NotificationOptions(prompts_changed=False, resources_changed=False, tools_changed=False)` and no subscribe override. Phase 52 will own the flip.

### Quality Gates

All gates pass at HEAD:

| Check | Command | Result |
|-------|---------|--------|
| pytest (MCP) | `poetry run pytest -q` (from `agent-brain-mcp/`) | PASS — 141 passed, 34 deselected (e2e) |
| pytest (Phase 51 tests only) | `pytest test_resources_*.py test_version_compat.py` | PASS — 90 passed |
| import-linter | `task check:layering` | PASS — 3 contracts kept, 0 broken |

### Test Count Trajectory (Across Plans)

| Plan | Count | Delta |
|------|-------|-------|
| Pre-Phase-51 baseline | 74 | — |
| 51-01 close | 91 | +17 dispatcher + job:// |
| 51-02 close | 108 | +17 chunk + graph-entity |
| 51-03 close | 124 | +16 file:// (net of -1 placeholder cleanup) |
| 51-04 close | 141 | +17 templates/list + version-floor + e2e |
| **Verification** | **141** | **+67 net new Phase 51 tests** |

### Spot Checks Performed

1. **TEMPLATE_REGISTRY exact strings** — read `parameterized.py:586-636`, confirmed all 4 entries with exact CONTEXT decision B strings (`chunk://{chunk_id}`, `graph-entity://{type}/{id}`, `job://{job_id}`, `file://{+path}`). `file://` template explicitly omits `mimeType` per per-read sniff policy.
2. **MIN_BACKEND_VERSION constant** — read `server.py:61`, confirmed `MIN_BACKEND_VERSION = "10.2.0"` with the inline release-train rationale comment. `test_version_compat.py:47` asserts this constant.
3. **Sandbox re-export shim is logic-free** — read every line of `agent-brain-mcp/agent_brain_mcp/security/__init__.py`. Confirmed pure docstring + single import + `__all__`. Zero functions, classes, or executable expressions beyond the import statement.
4. **Layering contract enforcement** — ran `task check:layering`, confirmed 3/3 contracts kept. Inspected `.importlinter` and confirmed `agent_brain_server.security` is not on the forbidden list (intentional allowance per PLAN.md line 84).
5. **Dispatcher dual-return** — read `server.py:223-231`, confirmed `isinstance(content, ReadResourceContents)` check that lets `file://` carry its own mime + bytes while keeping the 3 JSON schemes wrapped as `application/json`.

### Deviations from Plan (for design-doc flagging)

1. **Plan 03 added a defense-in-depth pre-flight `stat().st_size` check beyond what `is_path_allowed` already does** (parameterized.py:472-488). The plan called for sandbox-then-read; the implementation re-checks the size cap inside the handler. This is documented in Plan 03 SUMMARY's `key-decisions` and is non-breaking — purely a future-caller safety net. No design doc action required, but worth noting as a deviation toward stricter behavior.
2. **Plan 03 tightened `parse_uri` to reject the two-slash `file://relative/path` form** at the parser layer (parameterized.py:187-192). The plan's parser specification accepted any `file://...` and let the sandbox reject. Plan 03's `Rule 1 - Bug` auto-fix tightened this for an explicit security reason (preventing relative-path smuggling). Worth flagging in the v2 design doc as a forward-compat commitment ("file:// only accepts the canonical three-slash form"); this could trip clients sending non-canonical URIs.
3. **Server dispatcher widened to dual-return `str | ReadResourceContents`** (Plan 03 deviation #2). Plan called for the file:// handler returning bytes through the standard JSON wrap; implementation widened the dispatcher to accept `ReadResourceContents` directly so `file://` can carry per-file MIME and binary payloads. Non-breaking for the 3 JSON schemes. Worth noting in the design doc's wire-shape section so Phase 53 (Streamable HTTP) and Phase 55 (contract tests) reviewers see the protocol unchanged but the dispatcher widened.

None of these are blockers; all are documented in their respective Plan SUMMARYs.

### Gaps Summary

**No gaps.** Phase 51 ships. All 5 success criteria verified, all 5 requirement IDs satisfied, layering and sandbox contracts hold, regression check passes (5 corpus URIs intact, capability advertisement unchanged), and all quality gates green at HEAD (141 tests, 3 layering contracts, mypy/Black/Ruff per Plan 04 SUMMARY).

Ready for v10.2.0 release. Phase 52 (resource subscriptions) and Phase 53 (Streamable HTTP) can begin in parallel.

---

*Verified: 2026-06-03*
*Verifier: Claude (gsd-verifier)*
