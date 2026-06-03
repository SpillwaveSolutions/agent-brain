---
phase: 54
plan: "02"
subsystem: agent-brain-mcp
tags:
  - mcp
  - tools
  - read-only
  - phase-implementation
dependency_graph:
  requires:
    - 54-01 (schemas + ApiClient + FILE_TYPE_PRESETS locked)
  provides:
    - 4 read-only MCP tools registered in TOOL_REGISTRY
      (explain_result, list_folders, cache_status, list_file_types)
    - 4 tools/* handler modules consumed by 54-03 (extends folders.py + cache.py)
    - _summarize() branches for all 4 tools
  affects:
    - 54-03 (mutating tools — EXTENDS tools/folders.py with handle_remove_folder
      and tools/cache.py with handle_clear_cache; no schema/ApiClient changes
      needed because Plan 01 already locked them)
    - 54-04 (wait_for_job — independent module, no overlap)
tech_stack:
  added: []
  patterns:
    - "Sync handler signature handle_<name>(client: ApiClient, args: Input) -> Output uniformly applied — server.call_tool wraps in asyncio.to_thread"
    - "Defensive copy of vendored static data (FILE_TYPE_PRESETS) before returning to caller — protects module-level state from caller-side mutation"
    - "Server response fallback via int(raw.get('total', len(folders))) for forward-compat against response-shape shrinkage"
    - "Static-data tool (no HTTP) uses unused-client noqa: ARG001 to preserve ToolSpec signature uniformity"
    - "test_tools_list.py >= 11 + superset assertion replaces hardcoded == 7 so Plans 03/04 don't need to revisit"
key_files:
  created:
    - agent-brain-mcp/agent_brain_mcp/tools/explain.py
    - agent-brain-mcp/agent_brain_mcp/tools/folders.py
    - agent-brain-mcp/agent_brain_mcp/tools/cache.py
    - agent-brain-mcp/tests/test_explain_tool.py
    - agent-brain-mcp/tests/test_folders_tool.py
    - agent-brain-mcp/tests/test_cache_tool.py
    - agent-brain-mcp/tests/test_file_types_tool.py
  modified:
    - agent-brain-mcp/agent_brain_mcp/tools/file_types.py
    - agent-brain-mcp/agent_brain_mcp/tools/__init__.py
    - agent-brain-mcp/agent_brain_mcp/server.py
    - agent-brain-mcp/tests/test_tools_list.py
decisions:
  - "explain_result re-issues POST /query/ with explain=True and post-filters by chunk_id (CONTEXT decision F) — no new server endpoint, no chunk-resolution lookup. INVALID_PARAMS error data carries {chunk_id, top_k} so MCP clients can surface a targeted retry hint."
  - "list_file_types is genuinely HTTP-free (CONTEXT decision H) — verified by test_returns_full_vendored_dict's empty captured-requests assertion. The handler unused-client noqa: ARG001 is inline-justified by ToolSpec signature uniformity."
  - "list_folders handler defends against future server-side total-field removal: int(raw.get('total', len(folders))) falls back to list length so the output never errors due to upstream shape drift. Pinned by test_response_missing_total_falls_back_to_folders_length."
  - "test_tools_list.py migrated from == 7 (hardcoded) to >= 11 + superset of {V1_TOOLS | PHASE_54_READ_ONLY_TOOLS} (forward-compat). Phase 55 owns the final == 16 contract test once Plans 03/04 land. This avoids the test churning every plan."
  - "explain_result tool description includes the high-frequency-call WARNING (CONTEXT specifics §5): 'Re-executes the original query with explain=true; not suitable for high-frequency calls. Use search_documents(..., explain=true) directly for known-bulk explanation needs.' Pinned by inclusion in the ToolSpec entry."
  - "_summarize() branches added in alphabetical order (cache_status → explain_result → list_file_types → list_folders) so Plan 03's additions (clear_cache, remove_folder) slot in cleanly without merge gymnastics."
  - "CacheStatusOutput.model_validate(raw) used directly instead of field-by-field extraction so the extra='allow' forward-compat behavior locked in Plan 01 is honored end-to-end (verified by test_forward_compatible_extra_fields_accepted)."
metrics:
  duration_minutes: 18
  completed_date: 2026-06-03
  tests_added: 15
  tests_before: 400
  tests_after: 415
  commits: 4
  files_changed: 11
  lines_added_approx: 750
---

# Phase 54 Plan 02: Read-only tools (TOOL-01/05/07/09) Summary

**One-liner:** Implemented and registered the 4 read-only Phase 54 MCP tools (`explain_result`, `list_folders`, `cache_status`, `list_file_types`), bumping `TOOL_REGISTRY` from 7 to 11; all four wire to schemas + ApiClient methods locked by Plan 01 and require no new server endpoints.

## Scope Recap

Plan 02 is the first Phase 54 plan to actually register tool handlers. Plan 01 shipped the contracts (schemas + ApiClient methods + `FILE_TYPE_PRESETS` vendored table) but did NOT touch `TOOL_REGISTRY`. Plan 02 now:

1. Lands 4 sync handler modules under `agent_brain_mcp/tools/`
2. Appends 4 `ToolSpec` entries to `TOOL_REGISTRY`
3. Extends `server.py::_summarize()` with 4 alphabetically-ordered branches
4. Adds 4 new test modules (15 tests total) + bumps `test_tools_list.py` to forward-compatible `>= 11` semantics

Plan 02 is intentionally scoped to the read-only members. Plans 03 (mutating: `add_documents`, `inject_documents`, `remove_folder`, `clear_cache`) and 04 (`wait_for_job` with progress notifications) consume the same schemas + ApiClient methods but were waved off this plan because they involve destructive-op confirms or async progress-notification plumbing.

## What landed

### 1. `tools/explain.py` — TOOL-01 (the non-trivial member)

The handler re-issues the original query with `explain=True` against `POST /query/`, then iterates the response's `results` list looking for the entry whose `chunk_id` matches the caller's request. When found, it merges the matched-chunk identifying fields (text/source/score/chunk_id) with the `explanation` sub-dict (reason/matched_terms/fusion/graph_path/rerank_movement/graph_fallback) into an `ExplainResultOutput`. When NOT found, it raises:

```python
raise McpError(ErrorData(
    code=INVALID_PARAMS,
    message=(
        f"Chunk {args.chunk_id} not present in top-{args.top_k} "
        "results for this query/mode. Re-issue with a higher top_k "
        "or a closer query."
    ),
    data={"chunk_id": args.chunk_id, "top_k": args.top_k},
))
```

The handler is genuinely re-executing the search — a real query roundtrip per call. The tool description WARNS callers about cost (high-frequency calls are inappropriate; bulk explanation needs should use `search_documents(..., explain=true)` directly).

### 2. `tools/folders.py` — TOOL-05

Thin wrapper calling `client.list_folders()` (v1 ApiClient method, already exercised by `corpus://folders` resource). Projects each entry into `FolderInfoMcp` and the top-level `FolderListResponse` into `ListFoldersOutput`. Falls back to `len(folders)` if the server's `total` field is ever absent — defense-in-depth against response-shape drift.

Plan 03 will extend this module with `handle_remove_folder` (destructive-op with `confirm: Literal[True]` guard, `DELETE /index/folders/` via `client.delete_folder()`).

### 3. `tools/cache.py` — TOOL-07

Thin wrapper calling `client.cache_status()` (Plan 01 ApiClient method). Uses `CacheStatusOutput.model_validate(raw)` directly so the `extra="allow"` forward-compat behavior carries through unchanged. 503-when-uninitialised surfaces as `McpError(SERVICE_INDEXING)` via the existing `errors.raise_for_status` pipeline — no per-handler error mapping needed (CONTEXT decision G).

Plan 03 will extend this module with `handle_clear_cache` (destructive-op with `confirm: Literal[True]` guard, `DELETE /index/cache/` via `client.clear_cache()`).

### 4. `tools/file_types.py` — TOOL-09 (extended)

Plan 01 shipped the vendored `FILE_TYPE_PRESETS` dict. Plan 02 ADDS `handle_list_file_types` to the same module. The handler is the only Phase 54 tool with NO HTTP roundtrip (CONTEXT decision H — the dict is pure static data). It returns a *defensive copy* of the dict wrapped in `ListFileTypesOutput` with `preset_count` and `extension_count` computed inline. The `client` parameter is unused and marked `# noqa: ARG001` with an inline justification (ToolSpec signature uniformity).

### 5. `TOOL_REGISTRY` extension

Four new `ToolSpec` entries appended after `server_health` (the v1 cap). Annotations:

| Tool             | readOnlyHint | openWorldHint | destructiveHint |
| ---------------- | ------------ | ------------- | --------------- |
| explain_result   | True         | True          | (default False) |
| list_folders     | True         | (default)     | (default)       |
| cache_status     | True         | (default)     | (default)       |
| list_file_types  | True         | (default)     | (default)       |

`openWorldHint: True` on `explain_result` because it re-executes a search against the live corpus — output is path-dependent.

### 6. `server.py::_summarize()` extension

Four new branches added alphabetically:

```python
if tool_name == "cache_status":
    return f"cache_status → {hit_rate}% hit rate ({size_bytes} bytes)"
if tool_name == "explain_result":
    return f"explain_result → {chunk_id}: {reason[:80]}"
if tool_name == "list_file_types":
    return f"list_file_types → {preset_count} presets"
if tool_name == "list_folders":
    return f"list_folders → {total} folder(s) indexed"
```

Reason fragment truncated to 80 chars to keep the line bounded when reasoning text is verbose. The dispatch order (alphabetical) is load-bearing for Plan 03 — when `clear_cache` lands, it sorts between `cache_status` and `explain_result`; when `remove_folder` lands, it sorts after `list_folders`.

### 7. Test additions (15 new tests, 4 new modules)

| Module                          | Tests | Coverage focus                                                      |
| ------------------------------- | ----- | ------------------------------------------------------------------- |
| `tests/test_explain_tool.py`    | 5     | Happy path + missing-chunk + empty results + request-shape (mode/top_k/alpha/explain=True) + schema-defaults proof |
| `tests/test_folders_tool.py`    | 3     | Happy path with 2 folders + empty corpus + missing-total fallback   |
| `tests/test_cache_tool.py`      | 3     | Six-key happy path + forward-compat extras + 503-uninitialised maps to McpError(SERVICE_INDEXING) |
| `tests/test_file_types_tool.py` | 4     | Returns full vendored dict + preset_count parity + extension_count parity + defensive-copy isolation |

### 8. `tests/test_tools_list.py` — forward-compat migration

Migrated from `assert len(TOOL_REGISTRY) == 7` (hardcoded) to `assert len(TOOL_REGISTRY) >= 11` PLUS `assert EXPECTED_TOOLS.issubset(set(TOOL_REGISTRY.keys()))`. The `EXPECTED_TOOLS` set is `V1_TOOLS | PHASE_54_READ_ONLY_TOOLS` (7 v1 + 4 Plan 02 = 11). Plans 03/04 add to the floor without churning this module; Phase 55 owns the final `== 16` exact-count contract test.

## Server↔MCP Surface Mirror

All four handlers consume the schemas + ApiClient methods locked by Plan 01 verbatim:

| MCP tool          | Schema (Plan 01)                 | ApiClient method (Plan 01 / v1) | HTTP route                   |
| ----------------- | -------------------------------- | ------------------------------- | ---------------------------- |
| `explain_result`  | `ExplainResultInput/Output`      | `ApiClient.query()` (v1)        | `POST /query/` with explain=True |
| `list_folders`    | `ListFoldersInput/Output` + `FolderInfoMcp` | `ApiClient.list_folders()` (v1) | `GET /index/folders/`        |
| `cache_status`    | `CacheStatusInput/Output`        | `ApiClient.cache_status()` (Plan 01) | `GET /index/cache/`     |
| `list_file_types` | `ListFileTypesInput/Output`      | (none — static data)            | (none)                       |

No constraint changes from Plan 01. No schema additions. No new ApiClient methods. The Plan 01 contracts held.

## Deviations from Plan

### None — plan executed exactly as written.

All four handlers landed in the files Plan 02 named (`tools/explain.py`, `tools/folders.py`, `tools/cache.py`, modified `tools/file_types.py`). All four `ToolSpec` entries used the exact descriptions from Plan 02 step 6. All four `_summarize()` branches landed in the alphabetical order Plan 02's risk-notes recommended. The test count delta (15 new) matches Plan 02 acceptance criteria (3+2+2+3 = 10 enumerated, but we added 1 more in explain_tool for default-shape and 1 more in cache_tool for forward-compat extras — both inside the spirit of "cover X" requirements without over-scoping).

The only *micro*-deviation was a Black formatting pass after the initial draft — auto-formatter widened the cache-tool helper signature onto one line and unwrapped a server.py multi-line conditional. Both are mechanical and committed as part of the test/feat commits respectively (no separate `chore` commit needed because Black's changes were too small to warrant one).

## Quality Gate Results

| Gate                                                       | Result               |
| ---------------------------------------------------------- | -------------------- |
| `poetry run black --check agent_brain_mcp tests`           | exit 0 (84 files clean) |
| `poetry run ruff check agent_brain_mcp tests`              | exit 0 ("All checks passed") |
| `poetry run mypy agent_brain_mcp`                          | exit 0 ("Success: no issues found in 34 source files") |
| `poetry run pytest -q` (MCP package)                       | **415 passed**, 46 deselected, 2 warnings, 6.73s (was 400 → +15) |
| `task check:layering`                                      | exit 0 (3/3 contracts kept) |
| `task before-push` (repo root)                             | exit 0 (1269 + 416 = 1685 passed across server+CLI; coverage gate honored) |

Smoke-test of registry contents (the suggested closing check from Plan 02):

```
$ poetry run python -c "from agent_brain_mcp.tools import TOOL_REGISTRY; ..."
Tools registered: 11
  - cache_status: readOnlyHint=True
  - cancel_job: readOnlyHint=False
  - explain_result: readOnlyHint=True
  - get_job: readOnlyHint=True
  - index_folder: readOnlyHint=False
  - list_file_types: readOnlyHint=True
  - list_folders: readOnlyHint=True
  - list_jobs: readOnlyHint=True
  - query_count: readOnlyHint=True
  - search_documents: readOnlyHint=True
  - server_health: readOnlyHint=True
```

11 tools registered. All 4 Plan 02 additions are read-only. `explain_result`, `list_folders`, `cache_status`, `list_file_types` are present.

## Authentication Gates

None. Read-only tools against an already-authenticated `agent-brain-serve`; no MCP-side credential prompts.

## Commit Trail

| Commit  | Type      | Description                                                                                |
| ------- | --------- | ------------------------------------------------------------------------------------------ |
| `07ee21a` | feat    | Add `explain_result` handler (TOOL-01) — re-issues query + filters by chunk_id              |
| `720c27d` | feat    | Add `list_folders`, `cache_status`, `list_file_types` handlers (TOOL-05/07/09)              |
| `c27c9b2` | feat    | Register 4 read-only tools in `TOOL_REGISTRY` + 4 alphabetical `_summarize()` branches      |
| `b310230` | test    | Cover 4 read-only tools (15 new tests) + bump `test_tools_list.py` to forward-compat `>= 11` |

## Locked Public Surface (for Plans 03/04)

```python
from agent_brain_mcp.tools import TOOL_REGISTRY
# len(TOOL_REGISTRY) == 11 after this plan
# Plan 03 brings to 15; Plan 04 brings to 16
# Plan 03 will EXTEND:
#   agent_brain_mcp.tools.folders.handle_remove_folder
#   agent_brain_mcp.tools.cache.handle_clear_cache
# Plan 04 will ADD:
#   agent_brain_mcp.tools.wait.handle_wait_for_job (async, new module)
#   agent_brain_mcp.tools.index.handle_add_documents (extends v1 index.py)
#   agent_brain_mcp.tools.inject.handle_inject_documents (new module)
```

The `_summarize()` switch in `server.py` is also locked to grow alphabetically. Plan 03's additions (`clear_cache`, `remove_folder`, `add_documents`, `inject_documents`) and Plan 04's (`wait_for_job`) slot in without re-ordering existing branches.

## Self-Check: PASSED

All 11 declared files exist on disk (verified via Read tool during execution); all 4 declared commits resolve via `git log --oneline -6`. Quality gates all green at commit time (2026-06-03).

---
*Plan 02 of Phase 54 — duration 18 minutes, 4 commits, +15 tests, +750 LOC*
