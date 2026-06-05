---
phase: 54-remaining-mcp-tools
verified: 2026-06-03T00:00:00Z
status: passed
score: 9/9 must-haves verified
re_verification: false
---

# Phase 54: 9 remaining MCP tools — Verification Report

**Phase Goal:** The MCP server exposes all 16 tools from the original design — clients can drive the full indexing/folder/cache/file-type lifecycle and observe long-running jobs via progress notifications. All 9 derived from existing FastAPI server routes with NO new server endpoints.

**Verified:** 2026-06-03
**Status:** passed
**Re-verification:** No — initial verification.

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria + Objective)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | `explain_result` returns provenance + scoring for a chunk; warns about cost; raises INVALID_PARAMS when chunk not in top-k | PASS | `tools/explain.py:29-85`; description in `tools/__init__.py:193-204` includes "not suitable for high-frequency calls"; error raised at lines 75-85 with `{chunk_id, top_k}` data payload |
| 2 | `add_documents` returns `{job_id, status}`; body omits `allow_external` (#180) | PASS | `tools/index.py:52-81`; explicit comment at lines 72-74; body at line 75 is `{"paths": list(args.paths)}`; verified by test `test_body_omits_allow_external_field` |
| 3 | `inject_documents` returns `{job_id, status}`; path expansion + #181 mention + both-None rule | PASS | `tools/inject.py:43-109`; `Path(...).expanduser().resolve()` at lines 94, 97; description in `tools/__init__.py:256-266` names "#181", "INVALID_PARAMS", "dry_run='dry_run'", and the both-None rule |
| 4 | `wait_for_job` ASYNC; ≤2s cadence; emits progress; cancellation cleanup; soft timeout | PASS | `tools/wait.py:145-246`; `async def` at line 145; `poll_interval_seconds` ge=0.5/le=2.0 in schemas.py:335-343; `notify(...)` at lines 194, 201; CancelledError + `cancel_job` cleanup at lines 226-245; timeout returns `status='timeout', final=False` without raising at lines 217-223; `emits_progress=True` ONLY on this tool (`tools/__init__.py:315`) |
| 5 | `list_folders` returns folder list + total | PASS | `tools/folders.py:36-68`; calls v1 `client.list_folders()`; projects `FolderInfoMcp` + total |
| 6 | `remove_folder` destructive; `confirm: Literal[True]`; 409 BackendConflict mapping | PASS | `tools/folders.py:71-110`; `RemoveFolderInput.confirm: Literal[True]` in `schemas.py:374`; description in `tools/__init__.py:274-279` names "BackendConflict error (HTTP 409 surfaced as MCP code -32000)" — matches actual `errors.py:94-96` mapping |
| 7 | `cache_status` 503 surfaces as McpError; forward-compat | PASS | `tools/cache.py:36-60`; `CacheStatusOutput.model_validate(raw)` line 60 honors `extra="allow"` (schemas.py:531); 503 surfaces via `errors.raise_for_status` → SERVICE_INDEXING (-32002) at `errors.py:100-102` |
| 8 | `clear_cache` destructive; `confirm: Literal[True]` | PASS | `tools/cache.py:63-92`; `ClearCacheInput.confirm: Literal[True]` in `schemas.py:398` |
| 9 | `list_file_types` returns vendored presets; no HTTP roundtrip; CLI source cited | PASS | `tools/file_types.py:90-116`; pure static; module docstring lines 1-32 cite CLI source and Phase 55 parity contract; CLI presets at `agent-brain-cli/agent_brain_cli/commands/types.py:20-61` are byte-identical to MCP copy at `tools/file_types.py:46-87` |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `agent_brain_mcp/tools/explain.py` | `handle_explain_result` + INVALID_PARAMS on miss | VERIFIED | 85 LOC, async signature, error data carries `{chunk_id, top_k}` |
| `agent_brain_mcp/tools/index.py` | `handle_add_documents` added; v1 `handle_index_folder` untouched | VERIFIED | v1 handler at lines 31-49 keeps `allow_external` arg; new handler at lines 52-81 deliberately omits it |
| `agent_brain_mcp/tools/inject.py` | `handle_inject_documents` NEW module; path expansion | VERIFIED | 110 LOC NEW file; uses `Path(...).expanduser().resolve()`; defensive both-None re-check at lines 68-77 |
| `agent_brain_mcp/tools/wait.py` | ASYNC `handle_wait_for_job`; ProgressNotifier; _TERMINAL_STATES | VERIFIED | 246 LOC NEW file; `_TERMINAL_STATES` is 6-element frozenset at lines 63-72; `ProgressNotifier` type alias at line 81; full async polling loop with cleanup |
| `agent_brain_mcp/tools/folders.py` | `handle_list_folders` + `handle_remove_folder` | VERIFIED | 110 LOC; both handlers present; uses v1 `client.list_folders()` + Plan 01 `client.delete_folder()` |
| `agent_brain_mcp/tools/cache.py` | `handle_cache_status` + `handle_clear_cache` | VERIFIED | 92 LOC; both handlers present; uses Plan 01 `client.cache_status()` + `client.clear_cache()` |
| `agent_brain_mcp/tools/file_types.py` | `FILE_TYPE_PRESETS` (16 presets) + `handle_list_file_types` | VERIFIED | 119 LOC; 16 presets match CLI byte-for-byte (lines 46-87); defensive copy at line 111 |
| `agent_brain_mcp/schemas.py` | 18 schemas (9 input + 9 output) | VERIFIED | All 9 input classes have `ConfigDict(extra="forbid")` (lines 194, 232, 264, 332, 357, 368, 385, 396, 409); `json_schema()` helper at line 28 enforces `additionalProperties: false` |
| `agent_brain_mcp/client.py` | 5 new ApiClient methods | VERIFIED | `add_documents` (155), `inject_documents` (173), `cache_status` (196), `clear_cache` (205), `delete_folder` (216) |
| `agent_brain_mcp/tools/__init__.py` | TOOL_REGISTRY = 16 entries; `ToolSpec.emits_progress` field | VERIFIED | `emits_progress: bool = False` field at line 89/101/109; registry holds 16 entries (lines 113-316) |
| `agent_brain_mcp/server.py` | `call_tool` branches on `emits_progress`; `_build_progress_notifier` closure factory | VERIFIED | branch at lines 297-315; factory at lines 720-795; no-op closure when `progressToken is None` at lines 776-784 |
| `tests/test_tools_list.py` | `test_registry_has_exactly_sixteen_tools` + `test_only_wait_for_job_emits_progress` | VERIFIED | Both at lines 68-78; `EXPECTED_TOOLS` union at line 59 |
| `tests/test_e2e_stdio.py` | Updated to `== 16` (was `== 7`) | VERIFIED | Line 160 asserts `len(tools.tools) == 16` with inline comment citing the registry pin |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `tools/explain.py` | `agent-brain-serve` | `client.query(body)` with `explain=True` | WIRED | line 59; reuses existing POST /query/ — no new endpoint |
| `tools/index.py::handle_add_documents` | `agent-brain-serve` | `client.add_documents(body, force=...)` | WIRED | line 76 → POST /index/add per client.py:171 |
| `tools/inject.py` | `agent-brain-serve` | `client.inject_documents(body, force=...)` | WIRED | line 104 → POST /index/ per client.py:194 |
| `tools/wait.py` | `agent-brain-serve` | `client.get_job(job_id)` + cleanup `client.cancel_job(job_id)` | WIRED | get_job at line 179; cancel_job at line 236 |
| `tools/wait.py` | MCP client | `notify(progress, total, message)` | WIRED | line 194 (per poll) + line 201 (final). `_build_progress_notifier` in server.py:720 captures `progressToken` from `request_context.meta` |
| `tools/folders.py::handle_list_folders` | `agent-brain-serve` | `client.list_folders()` | WIRED | line 52 → GET /index/folders/ per client.py:124 |
| `tools/folders.py::handle_remove_folder` | `agent-brain-serve` | `client.delete_folder(body)` | WIRED | line 105 → DELETE /index/folders/ with body per client.py:225 |
| `tools/cache.py::handle_cache_status` | `agent-brain-serve` | `client.cache_status()` | WIRED | line 59 → GET /index/cache/ per client.py:203 |
| `tools/cache.py::handle_clear_cache` | `agent-brain-serve` | `client.clear_cache()` | WIRED | line 91 → DELETE /index/cache/ per client.py:214 |
| `tools/file_types.py` | (none) | static `FILE_TYPE_PRESETS` dict | WIRED | line 111 returns defensive copy; no HTTP roundtrip (verified by absence of `client.*` calls in handler body) |
| `server.py::call_tool` | sync handlers | `asyncio.to_thread(spec.handler, api, args)` | WIRED | line 315 — v1 contract preserved for 15/16 tools |
| `server.py::call_tool` | async progress handler | `await spec.handler(api, args, notify=notify)` | WIRED | line 309 — only invoked when `spec.emits_progress` (line 297) |
| `_summarize()` | wait_for_job branch | line 705-716 in server.py | WIRED | format: `wait_for_job → <job_id>: <status> (<pct>%) after <elapsed>s` matches CONTEXT specifics §6 |
| TOOL_REGISTRY | All 18 schemas in schemas.py | imports in `tools/__init__.py:17-50` | WIRED | All 9 input + 9 output models imported and bound to ToolSpec entries |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| TOOL-01 | Plan 02 | `explain_result` returns provenance + scoring for a chunk | SATISFIED | `tools/explain.py`; registered in TOOL_REGISTRY line 192-204; passes test_explain_tool.py (5 tests) |
| TOOL-02 | Plan 03 | `add_documents` with path list returns job_id | SATISFIED | `tools/index.py:52-81`; registered line 241-254; passes test_add_documents_tool.py (6 tests including #180 omission) |
| TOOL-03 | Plan 03 | `inject_documents` with script/folder returns job_id | SATISFIED | `tools/inject.py`; registered line 255-271; passes test_inject_documents_tool.py (6 tests including #181 mention + dry_run + ~ expansion) |
| TOOL-04 | Plan 04 | `wait_for_job` emits notifications/progress at least every 2s | SATISFIED | `tools/wait.py`; emits_progress=True at line 315; poll_interval upper-bound 2.0s in WaitForJobInput; passes 18 tests + 1 e2e |
| TOOL-05 | Plan 02 | `list_folders` returns folders + chunk counts + metadata | SATISFIED | `tools/folders.py:36-68`; registered line 205-214; passes test_folders_tool.py (3 tests) |
| TOOL-06 | Plan 03 | `remove_folder` removes folder chunks | SATISFIED | `tools/folders.py:71-110`; `confirm: Literal[True]`; registered line 272-284; passes test_remove_folder_tool.py (4 tests including 409 → BACKEND_CONFLICT) |
| TOOL-07 | Plan 02 | `cache_status` returns cache statistics | SATISFIED | `tools/cache.py:36-60`; registered line 215-222; passes test_cache_tool.py (3 tests including 503 → SERVICE_INDEXING) |
| TOOL-08 | Plan 03 | `clear_cache` clears cache | SATISFIED | `tools/cache.py:63-92`; `confirm: Literal[True]`; registered line 285-294; passes test_clear_cache_tool.py (3 tests) |
| TOOL-09 | Plan 02 | `list_file_types` returns presets | SATISFIED | `tools/file_types.py:90-116`; registered line 223-232; passes test_file_types_tool.py (4 tests) |

**Coverage: 9/9 requirements SATISFIED. No orphans. No gaps.**

### Anti-Patterns Found

Scanned all 9 modified/new files for TODO/FIXME/placeholder/empty implementations.

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | — | No blocker anti-patterns found | — | All handlers contain substantive implementations: no `return None`, no `return {}` placeholder, no TODO/FIXME in handler bodies, no console.log-only handlers |

The `# noqa: ARG001` markers (in `tools/file_types.py:91-92`, `tools/cache.py:38, 65`, `tools/folders.py:38`) are intentional and inline-documented as preserving the uniform ToolSpec `(client, args)` signature when the handler genuinely doesn't need one of the parameters. Not anti-patterns; explicit signature uniformity.

### Critical Contracts Verification

| Contract | Status | Evidence |
| -------- | ------ | -------- |
| TOOL_REGISTRY has EXACTLY 16 entries | VERIFIED | Counted manually in `tools/__init__.py:113-316`: 7 v1 + 4 read-only + 4 mutating + 1 progress = 16. Pinned by `test_registry_has_exactly_sixteen_tools` (live test run: passed) |
| `ToolSpec.emits_progress: bool = False` field exists | VERIFIED | `tools/__init__.py:89, 101, 109` |
| `server.call_tool` branches on `spec.emits_progress` | VERIFIED | `server.py:297-315` (`if spec.emits_progress: ... await spec.handler(api, args, notify=notify)` else `await asyncio.to_thread(spec.handler, api, args)`) |
| `_build_progress_notifier` closure in server.py | VERIFIED | `server.py:720-795`; captures `progressToken`, `request_id`, `session`; no-ops cleanly when token absent (lines 776-784) and when no request context (lines 755-765) |
| All 18 schemas with `additionalProperties: false` | VERIFIED | All 9 input models have `ConfigDict(extra="forbid")`; `json_schema()` helper at `schemas.py:21-29` calls `schema.setdefault("additionalProperties", False)` on every object schema. `CacheStatusOutput` (line 531) uses `extra="allow"` intentionally for forward-compat — this is an output, not an input, so MCP client pre-validation impact is nil |
| All 5 new ApiClient methods | VERIFIED | `client.py:155` (add_documents), 173 (inject_documents), 196 (cache_status), 205 (clear_cache), 216 (delete_folder) |
| `FILE_TYPE_PRESETS` mirrors CLI | VERIFIED | Byte-for-byte equal to `agent-brain-cli/agent_brain_cli/commands/types.py:20-61`. Same 16 preset keys, same patterns, same `code` block (24 patterns). Source citation in module docstring at lines 13-16 and 43-44 |
| Layering contract intact | VERIFIED | `task check:layering` exit 0; 164 files / 414 dependencies analyzed; 3 of 3 contracts kept (server has no upward deps, uds touches only server.models, mcp never calls server internals) |
| v1 `handle_index_folder` UNTOUCHED | VERIFIED | `tools/index.py:31-49` retains the `allow_external` parameter; comment in `tools/index.py:6-13` documents this is "a v1 bug to track separately, NOT a Phase 54 fix" |
| No new server endpoints | VERIFIED | All 5 new ApiClient routes wrap existing FastAPI endpoints: `POST /index/add` (v1), `POST /index/` (v1), `GET /index/cache/` (v1), `DELETE /index/cache/` (v1), `DELETE /index/folders/` (v1). Verified by reading route strings in client.py |
| Phase 52 contract preserved | VERIFIED | `SubscriptionManager`, `start_polling`, `SubscribableUriRejected` all still exported from `agent_brain_mcp.subscriptions` (`subscriptions/__init__.py:39-51`). Plan 04's choice of inline poll loop (vs reusing `start_polling`) documented in plan 04 SUMMARY frontmatter `decisions[0]` and `tools/wait.py` module docstring (lines 14-29). Both implementations are valid per the objective's "both are valid" clause |

### Regression Verification

| Phase | Test Surface | Status |
| ----- | ------------ | ------ |
| Phase 50 (server endpoints) | Phase 50 endpoints reused by client.py:126 (get_chunk) + 136 (get_graph_entity) — no regression | PASS |
| Phase 51 (URI schemes) | `parse_uri`, `PARAMETERIZED_HANDLERS`, `TEMPLATE_REGISTRY` all still wired in server.py:53-59, 332-345, 347-414 | PASS |
| Phase 52 (subscriptions) | `SubscriptionManager` instantiated in build_server (server.py:254); subscribe/unsubscribe handlers preserved at server.py:459-558; cleanup_all in run_stdio:982-988 | PASS |
| Phase 53 (HTTP transport) | `run_http` import (server.py:51), backend/listen transport labeling (server.py:599-624), `_MetaInjectingServerSession` (server.py:798-863), `_install_meta_injecting_session` (server.py:865-933) all preserved | PASS |
| Full MCP fast-lane | 451 tests passed, 47 deselected, 2 warnings, 9.83s (live run) | PASS |
| Full MCP e2e | 16 e2e tests passed, 28 skipped, 454 deselected | PASS |
| `task check:layering` | 3/3 contracts kept, 0 broken | PASS |

No regressions detected across Phases 50-53. The v1 e2e tool-count assertion in `test_e2e_stdio.py:160` was correctly bumped from 7 to 16 (Rule-1 auto-fix in Plan 04 SUMMARY) — this is a test fix, not a behavior regression.

### Deviations from Plan (Flagged for Design Doc)

These intentional deviations are documented in plan SUMMARYs and verified accurate to the actual code; worth surfacing for v2 design doc updates.

1. **BACKEND_CONFLICT (-32000) vs INVALID_PARAMS for 409 on `remove_folder`** — Plan 03 acceptance criteria literally said "INVALID_PARAMS" but `errors.raise_for_status` at `errors.py:94-96` maps 409 → BACKEND_CONFLICT. The tool description in `tools/__init__.py:274-279` correctly names "BackendConflict error (HTTP 409 surfaced as MCP code -32000)" — matches reality. Design doc should clarify the 409 mapping and remove any lingering INVALID_PARAMS references for this case.

2. **`_TERMINAL_STATES` 6-element superset** — Plan/CONTEXT enumerated `{succeeded, failed, cancelled, dry_run}` (4 elements). Actual `tools/wait.py:63-72` ships a 6-element frozenset adding `completed` and `done` to absorb server-version drift (JobStatus enum value is "done"; some paths emit "completed" as an alias). Documented in plan 04 SUMMARY frontmatter `decisions[1]` and `tools/wait.py` module docstring lines 10-30. Design doc should adopt the 6-element set as the canonical terminal-states contract.

3. **Inline poll loop in `wait_for_job` (vs reusing Phase 52 `start_polling`)** — Plan 04 explicitly chose inline polling. Reasoning is captured in `04-wait-for-job-SUMMARY.md` lines 88-102 + `tools/wait.py` module docstring: `start_polling` returns void and uses a callback model (right for subscriptions, wrong for tool-call request-response). Both implementations remain valid per the objective. Design doc should note this discrimination so future tool authors don't conflate the two patterns.

4. **v1 e2e tool-count assertion bumped `7 → 16`** — `tests/test_e2e_stdio.py:160` was correctly updated by Plan 04. The v1 e2e test was forward-incompatible by design and only surfaced during Plan 04's e2e suite execution (Plans 02/03 e2e was not the default run). Not a contract change — the test was always going to need updating.

5. **`include_code` default flip in `InjectDocumentsInput`** — Plan 01 SUMMARY notes this intentional divergence: server's `IndexRequest.include_code` defaults to False; MCP's `InjectDocumentsInput.include_code` defaults to True. Reasoning: CLI inject command defaults to True (users invoking inject typically want code indexed). Locked in `schemas.py:294-297`. Design doc should reflect that injector-driven indexing defaults code-inclusive.

6. **`allow_external` deliberately omitted from BOTH `add_documents` AND `inject_documents`** — Plan 01 SUMMARY deviation §1 expanded scope from "just `add_documents`" to "both" because issue #180 removed `allow_external` from BOTH `POST /index/add` and `POST /index/`. Verified at `tools/index.py:72-75` and `tools/inject.py:79-87`. Design doc should call out that the v1 `index_folder` tool's `allow_external` parameter is a known v1 bug (deferred remediation, not Phase 54 scope).

### Human Verification Required

None — all automated checks pass. The MCP-spec wire shape conformance (e.g., `notifications/progress` payload field order, JSON-RPC related_request_id semantics) is delegated to Phase 55 VAL-01 contract tests against the official MCP SDK, which is the architecturally correct seam.

### Gaps Summary

No gaps. All 9 TOOL requirements (TOOL-01..TOOL-09) are SATISFIED with code-level evidence. The TOOL_REGISTRY contains exactly 16 entries; `wait_for_job` is the only `emits_progress=True` tool; `_build_progress_notifier` closure factory + `call_tool` async dispatch branch are wired in `server.py`; all 5 new `ApiClient` methods wrap existing routes (no new server endpoints); `FILE_TYPE_PRESETS` is byte-identical to the CLI source of truth; layering contracts are intact (3/3 kept); 451 fast-lane MCP tests + 16 e2e tests pass; v1 `handle_index_folder` is untouched; Phase 52 exports are preserved.

The phase goal is achieved: the MCP server exposes all 16 tools from the original design, and clients can observe long-running jobs via `notifications/progress` with a 1s default cadence under the MCP-spec ≤2s requirement.

---

_Verified: 2026-06-03_
_Verifier: Claude (gsd-verifier) — Phase 54 final goal-backward verification_
