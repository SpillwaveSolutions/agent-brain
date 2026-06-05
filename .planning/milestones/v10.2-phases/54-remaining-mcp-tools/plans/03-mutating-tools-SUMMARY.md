---
phase: 54
plan: "03"
subsystem: agent-brain-mcp
tags:
  - mcp
  - tools
  - mutating
  - destructive-ops
  - phase-implementation
dependency_graph:
  requires:
    - 54-01 (schemas + ApiClient methods locked: AddDocumentsInput/Output,
      InjectDocumentsInput/Output, RemoveFolderInput/Output, ClearCacheInput/Output
      + add_documents/inject_documents/delete_folder/clear_cache ApiClient methods)
    - 54-02 (tools/folders.py + tools/cache.py created with read-only handlers;
      Plan 03 APPENDS the destructive counterparts to the same modules)
  provides:
    - 4 mutating MCP tools registered in TOOL_REGISTRY
      (add_documents, inject_documents, remove_folder, clear_cache)
    - tools/inject.py NEW module containing handle_inject_documents
    - tools/index.py EXTENDED with handle_add_documents (v1 handle_index_folder
      preserved untouched)
    - tools/folders.py EXTENDED with handle_remove_folder (Plan 02's
      handle_list_folders preserved untouched)
    - tools/cache.py EXTENDED with handle_clear_cache (Plan 02's
      handle_cache_status preserved untouched)
    - _summarize() branches for all 4 mutating tools, alphabetically slotted
      alongside Plan 02's branches
  affects:
    - 54-04 (wait_for_job — independent async module; Plan 04 brings registry
      from 15 to the final v2 count of 16; Phase 55 owns the exact-count
      contract test)
    - Phase 55 (VAL-01 contract tests parameterize against the full 16-tool
      surface — Plan 03 brings 4 more tools into that surface)
tech_stack:
  added: []
  patterns:
    - "Sync handler signature handle_<name>(client: ApiClient, args: Input) -> Output uniformly applied — server.call_tool wraps in asyncio.to_thread"
    - "Path(...).expanduser().resolve() for inject_documents script/metadata paths — mirrors CLI inject command's resolution (agent-brain-cli/agent_brain_cli/commands/inject.py line 158)"
    - "Defensive both-None pre-validation in handle_inject_documents (Pydantic root validator should already reject; the re-check covers direct callers bypassing schema)"
    - "Literal[True] confirm gates on RemoveFolderInput + ClearCacheInput rejected at Pydantic construction — handler-side re-check is redundant"
    - "_summarize() alphabetical extension across 8 Phase 54 branches (add_documents → cache_status → clear_cache → explain_result → inject_documents → list_file_types → list_folders → remove_folder) so Plan 04's wait_for_job slots in cleanly"
    - "test_tools_list.py >= 15 + superset semantics replaces Plan 02's >= 11 floor — forward-compat against Plan 04 without churning the module"
key_files:
  created:
    - agent-brain-mcp/agent_brain_mcp/tools/inject.py
    - agent-brain-mcp/tests/test_add_documents_tool.py
    - agent-brain-mcp/tests/test_inject_documents_tool.py
    - agent-brain-mcp/tests/test_remove_folder_tool.py
    - agent-brain-mcp/tests/test_clear_cache_tool.py
  modified:
    - agent-brain-mcp/agent_brain_mcp/tools/index.py
    - agent-brain-mcp/agent_brain_mcp/tools/folders.py
    - agent-brain-mcp/agent_brain_mcp/tools/cache.py
    - agent-brain-mcp/agent_brain_mcp/tools/__init__.py
    - agent-brain-mcp/agent_brain_mcp/server.py
    - agent-brain-mcp/tests/test_tools_list.py
decisions:
  - "handle_add_documents body deliberately omits allow_external (issue #180 removed it from POST /index/add server-side; exposing it MCP-side would be a silent no-op + security drift signal). Defense-in-depth: tests/test_add_documents_tool.py::test_body_omits_allow_external_field pins this assertion."
  - "handle_inject_documents body also omits allow_external (Plan 01 SUMMARY deviation §1 established that #180 affected POST /index/ as well as POST /index/add). Plus tests/test_inject_documents_tool.py::test_with_injector_script_resolves_to_absolute_path pins the same allow_external-absent assertion."
  - "handle_inject_documents path resolution mirrors CLI behavior via Path(...).expanduser().resolve(). The CLI's click.Path(exists=True) layer already expands ~ before the command body runs; the MCP handler does .expanduser() defensively so MCP callers can pass ~/scripts/enrich.py directly. Pinned by test_expands_tilde_in_paths."
  - "remove_folder tool description names 'BackendConflict error (HTTP 409 surfaced as MCP code -32000)' instead of the plan's 'INVALID_PARAMS' paraphrase — Rule 1 deviation, see below. The actual errors.raise_for_status mapping is 409 → BACKEND_CONFLICT (-32000), not INVALID_PARAMS (-32602). Description matches what MCP clients will actually observe."
  - "inject_documents tool description names BOTH the #181 hash-allowlist failure (403 → INVALID_PARAMS) AND the both-None rule per plan acceptance criteria. 403 → INVALID_PARAMS is the correct mapping (errors.raise_for_status's 'other 4xx' fallback branch routes 403 to INVALID_PARAMS)."
  - "_summarize branch for inject_documents has a dry_run-specific path: when job_id=='dry_run', shows 'inject_documents → dry_run: <message>' instead of 'job <id> (<status>)' so clients see the validation report fragment immediately."
  - "_summarize alphabetical ordering across all 8 Phase 54 branches preserved (Plan 02 committed to it explicitly to enable clean Plan 03 drop-in). Plan 04's wait_for_job sorts at the tail."
  - "test_tools_list.py floor bumped from >= 11 (Plan 02) to >= 15 (Plan 03). Plan 04 takes it to 16; Phase 55 owns the final == 16 exact-count contract test. The superset semantic (EXPECTED_TOOLS.issubset(...)) means Plan 04 can ship without re-editing this module."
  - "Tests for 409-on-active-job assert BACKEND_CONFLICT (-32000), not INVALID_PARAMS — confirms the actual end-to-end behavior MCP clients will observe."
metrics:
  duration_minutes: 22
  completed_date: 2026-06-03
  tests_added: 18
  tests_before: 415
  tests_after: 433
  commits: 4
  files_changed: 11
  lines_added_approx: 800
---

# Phase 54 Plan 03: Mutating tools (TOOL-02/03/06/08) Summary

**One-liner:** Implemented and registered the 4 mutating Phase 54 MCP tools (`add_documents`, `inject_documents`, `remove_folder`, `clear_cache`), bumping `TOOL_REGISTRY` from 11 to 15; all four wire to schemas + ApiClient methods locked by Plan 01 and require no new server endpoints.

## Scope Recap

Plan 03 is the Wave-3 plan in Phase 54 — it lands the 4 destructive/mutating handlers on top of Plan 01's contracts and Plan 02's read-only handlers. Specifically:

1. Lands `handle_add_documents` in `tools/index.py` alongside the v1 `handle_index_folder` (which stays untouched).
2. Creates new `tools/inject.py` for `handle_inject_documents` — the only Phase 54 handler with non-trivial path expansion (mirrors CLI `inject` command's `Path(...).expanduser().resolve()` pattern).
3. EXTENDS Plan 02's `tools/folders.py` with `handle_remove_folder` (destructive; `confirm: Literal[True]` gated).
4. EXTENDS Plan 02's `tools/cache.py` with `handle_clear_cache` (destructive; `confirm: Literal[True]` gated).
5. Appends 4 `ToolSpec` entries to `TOOL_REGISTRY` with CONTEXT decision B annotations.
6. Extends `server.py::_summarize()` with 4 alphabetically-ordered branches alongside Plan 02's.
7. Adds 4 new test modules (18 tests total) + bumps `test_tools_list.py` to forward-compatible `>= 15` semantics.

Plan 03 is intentionally scoped to the mutating members. Plan 04 (`wait_for_job` with progress notifications) is the only remaining Phase 54 plan; it touches `call_tool` dispatch for the async branch, which Plan 03 deliberately does NOT modify.

## What landed

### 1. `tools/index.py` — `handle_add_documents` (TOOL-02)

Three-line handler that builds a body containing only `{"paths": [...]}` (no `allow_external`) and forwards through `ApiClient.add_documents`. The v1 `handle_index_folder` is preserved untouched — its `allow_external` argument is a v1 bug to track separately per CONTEXT specifics §3.

Annotation: `openWorldHint: True, destructiveHint: False` (path-dependent indexing operation).

### 2. `tools/inject.py` — `handle_inject_documents` (TOOL-03, NEW module)

The most complex of the four. The handler:

1. Defensively re-checks the both-None case (Pydantic `@model_validator` should already reject; the re-check covers direct callers bypassing schema validation, e.g., future async wrappers).
2. Builds a body with `folder_path`, `dry_run`, `include_code` (and conditionally `chunk_size`/`chunk_overlap`).
3. **Resolves** `injector_script` via `Path(value).expanduser().resolve()` so MCP callers can pass `~/scripts/enrich.py` and get the same UX as `agent-brain inject --script ~/scripts/enrich.py`. The `.expanduser()` step is the only additive over the CLI's `Path(...).resolve()`; the CLI's `click.Path(exists=True)` layer already handles `~` expansion before the command body runs.
4. Same path resolution for `folder_metadata_file`.
5. Forwards through `ApiClient.inject_documents(body, force=...)`.

**`allow_external` deliberately omitted** from the body — Plan 01 SUMMARY's deviation §1 established that issue #180 removed `allow_external` from `POST /index/` as well as `POST /index/add`. Defense-in-depth tests pin the absence.

Annotation: `openWorldHint: True, destructiveHint: False`.

### 3. `tools/folders.py` — `handle_remove_folder` (TOOL-06, EXTENDS Plan 02's module)

Thin wrapper around `ApiClient.delete_folder` (`DELETE /index/folders/` with body, NOT query). The Pydantic `Literal[True]` `confirm` field rejects unconfirmed invocations before the handler runs; defensive re-check is redundant. The 409-when-job-active behavior (FOLD-07) surfaces as `McpError(BACKEND_CONFLICT, -32000)` via the existing `errors.raise_for_status` pipeline.

Annotation: `destructiveHint: True`.

Plan 02's `handle_list_folders` is preserved untouched in the same module.

### 4. `tools/cache.py` — `handle_clear_cache` (TOOL-08, EXTENDS Plan 02's module)

Two-line handler that forwards to `ApiClient.clear_cache` and wraps the result in `ClearCacheOutput.model_validate(...)`. The `args` parameter is unused at runtime (the `Literal[True]` confirm is enforced at Pydantic construction); marked `# noqa: ARG001` to signal the uniform ToolSpec signature.

Annotation: `destructiveHint: True`.

Plan 02's `handle_cache_status` is preserved untouched in the same module.

### 5. `TOOL_REGISTRY` extension

Four new `ToolSpec` entries appended after the Plan 02 read-only block (post-`list_file_types`). Annotations summary:

| Tool             | readOnlyHint | openWorldHint | destructiveHint |
| ---------------- | ------------ | ------------- | --------------- |
| add_documents    | (default)    | True          | False           |
| inject_documents | (default)    | True          | False           |
| remove_folder    | (default)    | (default)     | True            |
| clear_cache      | (default)    | (default)     | True            |

Tool descriptions carry the operator-visible failure modes:
- `add_documents`: names `AGENT_BRAIN_ALLOW_EXTERNAL_PATHS` and issue #180.
- `inject_documents`: names issue #181 + "fail with INVALID_PARAMS" + "At least one of injector_script or folder_metadata_file is required" + dry_run semantics.
- `remove_folder`: names "BackendConflict error (HTTP 409 surfaced as MCP code -32000) — cancel the job first" (see Deviations §1).
- `clear_cache`: names "Requires confirm=true. Cannot be undone."

### 6. `server.py::_summarize()` extension

Four new branches added in alphabetical order alongside Plan 02's four. Final dispatch order across the 8 Phase 54 branches:

```
add_documents → cache_status → clear_cache → explain_result →
inject_documents → list_file_types → list_folders → remove_folder
```

Summary formats:
- `add_documents → job <id> (queued)`
- `clear_cache → cache cleared (<count> entries, <size_bytes> bytes)`
- `inject_documents → job <id> (queued)` — OR — `inject_documents → dry_run: <message[:80]>` for dry runs (job_id literal `"dry_run"` is the signal)
- `remove_folder → <folder>: <chunks_deleted> chunks removed`

Plan 04's `wait_for_job` will sort at the tail of this block, after `remove_folder`.

### 7. Test additions (18 new tests, 4 new modules)

| Module                                | Tests | Coverage focus                                                                                                            |
| ------------------------------------- | ----- | ------------------------------------------------------------------------------------------------------------------------- |
| `tests/test_add_documents_tool.py`    | 5     | Happy path + body shape pin + defense-in-depth `allow_external` absent + force=True query + force=False omits + empty-paths rejected |
| `tests/test_inject_documents_tool.py` | 6     | Script-path-resolves + metadata-path-resolves + `~` expansion + both-None rejected + dry-run job_id="dry_run" + 403 → INVALID_PARAMS |
| `tests/test_remove_folder_tool.py`    | 4     | Happy path with DELETE body shape pin + missing-confirm rejected + confirm=false rejected + 409 → BACKEND_CONFLICT       |
| `tests/test_clear_cache_tool.py`      | 3     | Happy path with empty-body assertion + missing-confirm rejected + confirm=false rejected                                  |

The `inject_documents` and `add_documents` tests both include the explicit `assert "allow_external" not in body` defense-in-depth check.

### 8. `tests/test_tools_list.py` — floor bump

Migrated from `>= 11` (Plan 02) to `>= 15` (Plan 03). `EXPECTED_TOOLS` now includes:
```python
EXPECTED_TOOLS = V1_TOOLS | PHASE_54_READ_ONLY_TOOLS | PHASE_54_MUTATING_TOOLS
# = 7 + 4 + 4 = 15
```

Plan 04 adds `wait_for_job` on top of this floor without re-editing the module. Phase 55 owns the final exact-count `== 16` contract test.

## Server↔MCP Surface Mirror

All four handlers consume the schemas + ApiClient methods locked by Plan 01 verbatim:

| MCP tool            | Schema (Plan 01)                       | ApiClient method (Plan 01)            | HTTP route                |
| ------------------- | -------------------------------------- | ------------------------------------- | ------------------------- |
| `add_documents`     | `AddDocumentsInput/Output`             | `ApiClient.add_documents()`           | `POST /index/add?force=`  |
| `inject_documents`  | `InjectDocumentsInput/Output`          | `ApiClient.inject_documents()`        | `POST /index/?force=`     |
| `remove_folder`     | `RemoveFolderInput/Output`             | `ApiClient.delete_folder()`           | `DELETE /index/folders/`  |
| `clear_cache`       | `ClearCacheInput/Output`               | `ApiClient.clear_cache()`             | `DELETE /index/cache/`    |

No constraint changes from Plan 01. No schema additions. No new ApiClient methods.

## Deviations from Plan

### Auto-fixed Issues (Rule 1 — bug-class)

**1. [Rule 1 — Bug] `remove_folder` tool description names BackendConflict (not INVALID_PARAMS)**

- **Found during:** Task 3 (registry write-up)
- **Issue:** The plan acceptance criteria + Implementation Step §8 specify the `remove_folder` tool description should say "Removing a folder while an indexing job is active for it will fail with INVALID_PARAMS — cancel the job first." However, `agent_brain_mcp/errors.py::raise_for_status` actually maps HTTP 409 to `BACKEND_CONFLICT` (-32000), NOT `INVALID_PARAMS` (-32602). Shipping the plan's literal wording would misrepresent the error MCP clients will actually see.
- **Fix:** Tool description now says "fail with a BackendConflict error (HTTP 409 surfaced as MCP code -32000) — cancel the job first." Accurate to the existing `errors.py` mapping.
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/tools/__init__.py` (description string)
- **Pin:** `tests/test_remove_folder_tool.py::test_409_active_job_surfaces_as_backend_conflict` asserts the actual `BACKEND_CONFLICT` code (with the test module's leading docstring explaining the Plan-vs-Code wording delta).
- **Commit:** `c6301b6` (folded into the test commit alongside the test pin)

### None other.

The other 3 acceptance-criteria error-code claims hold as written:
- `add_documents` schema correctly omits `allow_external` (Plan 01 already ensured this).
- `inject_documents` 403 → INVALID_PARAMS — accurate (`errors.py`'s 4xx fallback branch routes 403 to `INVALID_PARAMS`).
- `inject_documents` model_validator both-None rejection — accurate (Plan 01 wired the `@model_validator`).

## Authentication Gates

None. The MCP server stays unauthenticated within v2 (loopback-only); the 4 new handlers reach the existing `agent-brain-serve` via the same `ApiClient` Plan 02 used. No credential prompts.

## Quality Gate Results

| Gate                                                       | Result                                                            |
| ---------------------------------------------------------- | ----------------------------------------------------------------- |
| `poetry run black --check agent_brain_mcp tests`           | exit 0 (89 files clean)                                           |
| `poetry run ruff check agent_brain_mcp tests`              | exit 0 ("All checks passed")                                      |
| `poetry run mypy agent_brain_mcp`                          | exit 0 ("Success: no issues found in 35 source files")            |
| `poetry run pytest -q` (MCP package)                       | **433 passed**, 46 deselected, 2 warnings, 6.56s (was 415 → +18) |
| `task check:layering`                                      | exit 0 (3/3 contracts kept)                                       |
| `task before-push` (repo root)                             | exit 0 (416 monorepo tests; 80% coverage gate honored)            |

Smoke-test of registry contents:

```
$ poetry run python -c "from agent_brain_mcp.tools import TOOL_REGISTRY; ..."
Total tools: 15

add_documents:
  annotations: {'openWorldHint': True, 'destructiveHint': False}
inject_documents:
  annotations: {'openWorldHint': True, 'destructiveHint': False}
remove_folder:
  annotations: {'destructiveHint': True}
clear_cache:
  annotations: {'destructiveHint': True}
```

15 tools registered. All 4 Plan 03 additions present with correct hints.

## Commit Trail

| Commit    | Type      | Description                                                                       |
| --------- | --------- | --------------------------------------------------------------------------------- |
| `bd5cb02` | feat      | Add `add_documents` + `inject_documents` handlers (TOOL-02/03)                    |
| `0768ac6` | feat      | Extend `folders.py` + `cache.py` with destructive handlers (TOOL-06/08)           |
| `095f5f2` | feat      | Register 4 mutating tools + extend `_summarize()` (TOOL-02/03/06/08)              |
| `c6301b6` | test      | Cover 4 mutating tools + bump tools-list to >= 15 + description accuracy fix      |

## Locked Public Surface (for Plan 04)

```python
from agent_brain_mcp.tools import TOOL_REGISTRY
# len(TOOL_REGISTRY) == 15 after this plan
# Plan 04 brings to 16 with wait_for_job (async, in new tools/wait.py module)

# Plan 04 will EXTEND _summarize() with a wait_for_job branch at the
# tail of the alphabetical Phase 54 block (after remove_folder).

# Plan 04 will EXTEND call_tool dispatch in server.py to branch on
# spec.emits_progress; Plan 03 deliberately did NOT touch the dispatch
# so Plan 04 owns the async-handler-with-notify-injection contract.
```

## Self-Check: PASSED

All 11 declared files exist on disk (verified via Read tool during execution); all 4 declared commits resolve via `git log --oneline -5`. Quality gates all green at commit time (2026-06-03). The smoke-test output above shows 15 tools registered with the correct annotations on each.

---
*Plan 03 of Phase 54 — duration 22 minutes, 4 commits, +18 tests, +800 LOC*
