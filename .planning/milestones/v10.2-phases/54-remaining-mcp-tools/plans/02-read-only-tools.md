# Plan 02: Read-only tools — explain_result, list_folders, cache_status, list_file_types

**Phase:** 54 — 9 remaining MCP tools
**Requirements covered:** TOOL-01 (`explain_result`), TOOL-05 (`list_folders`), TOOL-07 (`cache_status`), TOOL-09 (`list_file_types`)
**Depends on:** Plan 01 (schemas + ApiClient methods)
**Parallel-safe with:** Plan 03 (mutating tools) — disjoint file sets across `tools/*.py` modules; both append to `TOOL_REGISTRY` and `_summarize()` (merge-conflict-prone but mechanical to resolve)
**Status:** Not started

## Goal

Implement and register the four read-only Phase 54 tools. Each handler is a sync function that consumes the schemas / ApiClient methods landed by Plan 01 and returns the matching output model. All four are flagged `readOnlyHint: True`. No destructive operations, no notification plumbing — straightforward thin wrappers over existing HTTP routes (plus one vendored static table for `list_file_types`).

The `explain_result` tool is the only non-trivial member: it re-issues the original query with `explain=True` and filters for the requested `chunk_id` (per Decision F in CONTEXT — no new server endpoint).

## Acceptance Criteria

- [ ] Four new tool handlers exist and are registered in `TOOL_REGISTRY`:
  - `explain_result` → `handle_explain_result` in `agent_brain_mcp/tools/explain.py`
  - `list_folders` → `handle_list_folders` in `agent_brain_mcp/tools/folders.py`
  - `cache_status` → `handle_cache_status` in `agent_brain_mcp/tools/cache.py`
  - `list_file_types` → `handle_list_file_types` in `agent_brain_mcp/tools/file_types.py` (extends Plan 01's module)
- [ ] All four handlers are **sync** (per CONTEXT decision B — server wraps in `asyncio.to_thread`).
- [ ] All four `ToolSpec` entries set `readOnlyHint: True` in annotations.
- [ ] `explain_result` re-issues the query with `explain=True` and post-filters by `chunk_id`. When the chunk is not present in the top-`top_k` results, raise `McpError(INVALID_PARAMS, "Chunk <id> not present in top-<top_k> results for this query/mode. Re-issue with a higher top_k or a closer query.")` per Decision F.
- [ ] `explain_result` tool description explicitly warns: "Re-executes the original query with explain=true; not suitable for high-frequency calls. Use search_documents(..., explain=true) directly for known-bulk explanation needs." (CONTEXT `<specifics>`.)
- [ ] `list_file_types` handler returns the vendored `FILE_TYPE_PRESETS` dict wrapped in `ListFileTypesOutput` with `preset_count` and `extension_count` computed from the dict (no HTTP roundtrip — Decision H).
- [ ] `_summarize()` in `server.py` extended with four new branches matching v1's terse style:
  - `explain_result → <chunk_id>: <reason fragment>` (truncate reason to first 80 chars)
  - `list_folders → <N> folder(s) indexed`
  - `cache_status → <hit_rate>% hit rate (<size>)`
  - `list_file_types → <N> presets`
- [ ] Unit tests in `agent-brain-mcp/tests/test_explain_tool.py` cover: (a) successful explanation when chunk is in results, (b) `INVALID_PARAMS` when chunk is missing, (c) mode + top_k + alpha passed through to the underlying query.
- [ ] Unit tests in `agent-brain-mcp/tests/test_folders_tool.py` cover `list_folders` happy path + empty corpus case (returns `folders: []`).
- [ ] Unit tests in `agent-brain-mcp/tests/test_cache_tool.py` cover `cache_status` happy path + 503-when-uninitialised mapping (per Decision G — surfaces as `McpError`).
- [ ] Unit tests in `agent-brain-mcp/tests/test_file_types_tool.py` cover: (a) handler returns the full vendored dict, (b) `preset_count == len(FILE_TYPE_PRESETS)`, (c) `extension_count == sum(len(v) for v in FILE_TYPE_PRESETS.values())`.
- [ ] Tool-registry assertion test added to existing `tests/test_tools_list.py`: after Plans 02+03+04 land, `len(TOOL_REGISTRY) == 16` (7 v1 + 9 v2). Plan 02 alone bumps it to 11; the final-count assertion lives in Plan 04 or Phase 55.
- [ ] `task mcp:test`, `task mcp:pr-qa-gate`, `task check:layering`, `task before-push` all pass.

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-mcp/agent_brain_mcp/tools/explain.py` | create | `handle_explain_result(client, args) -> ExplainResultOutput`. ~50 LOC including imports + error handling. |
| `agent-brain-mcp/agent_brain_mcp/tools/folders.py` | create | `handle_list_folders(client, args) -> ListFoldersOutput`. Plan 03 will extend this same file with `handle_remove_folder` — coordinate via `__all__`. |
| `agent-brain-mcp/agent_brain_mcp/tools/cache.py` | create | `handle_cache_status(client, args) -> CacheStatusOutput`. Plan 03 will extend with `handle_clear_cache`. |
| `agent-brain-mcp/agent_brain_mcp/tools/file_types.py` | modify | Add `handle_list_file_types(client, args) -> ListFileTypesOutput`. Module already exists from Plan 01 (holds the vendored dict). |
| `agent-brain-mcp/agent_brain_mcp/tools/__init__.py` | modify | Add 4 `ToolSpec` entries to `TOOL_REGISTRY`. Add imports. Update `__all__`. |
| `agent-brain-mcp/agent_brain_mcp/server.py` | modify | Add 4 branches to `_summarize()` switch (lines 213-245 in v1). |
| `agent-brain-mcp/tests/test_explain_tool.py` | create | 3 tests as enumerated above. |
| `agent-brain-mcp/tests/test_folders_tool.py` | create | 2 tests. |
| `agent-brain-mcp/tests/test_cache_tool.py` | create | 2 tests (happy path + 503). |
| `agent-brain-mcp/tests/test_file_types_tool.py` | create | 3 tests. |
| `agent-brain-mcp/tests/test_tools_list.py` | modify | Bump expected tool count to 11 (or skip the exact-count assertion and just assert `>= 11` until Plan 04 lands). |

## Implementation Steps

1. Read `agent-brain-mcp/agent_brain_mcp/tools/jobs.py` and `tools/meta.py` for the canonical handler style. Handler signature template:
   ```python
   def handle_<name>(client: ApiClient, args: <Input>) -> <Output>:
       response = client.<method>(...)
       return <Output>(**response)
   ```
2. Create `tools/explain.py`. The handler:
   1. Construct query body: `{"query": args.query, "mode": args.mode, "top_k": args.top_k, "alpha": args.alpha, "explain": True}`.
   2. Call `client.query(body)`.
   3. Iterate `response["results"]` and find the entry with `chunk_id == args.chunk_id`. The `chunk_id` field on a query result is the canonical identifier — confirm by reading `agent-brain-server/agent_brain_server/models/query.py`.
   4. If not found, raise `McpError(code=INVALID_PARAMS, message="Chunk <id> not present in top-<top_k> results for this query/mode. Re-issue with a higher top_k or a closer query.", data={"chunk_id": args.chunk_id, "top_k": args.top_k})`.
   5. Extract the result's `explanation` sub-dict and return `ExplainResultOutput` populated from the matching result + its explanation.
3. Create `tools/folders.py`. `handle_list_folders` is a 3-line wrapper: call `client.list_folders()`, parse into `ListFoldersOutput`. (Plan 03 will add `handle_remove_folder` here.)
4. Create `tools/cache.py`. `handle_cache_status` is a 3-line wrapper: call `client.cache_status()`, parse into `CacheStatusOutput`. (Plan 03 will add `handle_clear_cache` here.) Confirm the response shape matches by reading `agent-brain-server/agent_brain_server/api/routers/cache.py`.
5. Open `tools/file_types.py` (created in Plan 01 with the vendored dict). Add `handle_list_file_types`:
   ```python
   def handle_list_file_types(client: ApiClient, args: ListFileTypesInput) -> ListFileTypesOutput:
       # No HTTP call — static data per Decision H in CONTEXT.
       presets = dict(FILE_TYPE_PRESETS)  # defensive copy
       return ListFileTypesOutput(
           presets=presets,
           preset_count=len(presets),
           extension_count=sum(len(v) for v in presets.values()),
       )
   ```
   Note the `client` parameter is unused but required for ToolSpec signature uniformity. Add `# noqa: ARG001` if Ruff complains.
6. Open `tools/__init__.py` and append 4 `ToolSpec` entries to `TOOL_REGISTRY`. Follow v1's existing pattern:
   ```python
   "explain_result": ToolSpec(
       name="explain_result",
       description=(
           "Get provenance and scoring breakdown for a specific result chunk. "
           "Re-executes the original query with explain=true; not suitable for "
           "high-frequency calls. Use search_documents(..., explain=true) directly "
           "for known-bulk explanation needs."
       ),
       handler=handle_explain_result,
       input_model=ExplainResultInput,
       output_model=ExplainResultOutput,
       annotations={"readOnlyHint": True, "openWorldHint": True},
   ),
   "list_folders": ToolSpec(
       name="list_folders",
       description="List all indexed folders with chunk counts and last-indexed metadata.",
       handler=handle_list_folders,
       input_model=ListFoldersInput,
       output_model=ListFoldersOutput,
       annotations={"readOnlyHint": True},
   ),
   "cache_status": ToolSpec(
       name="cache_status",
       description="Show embedding cache statistics (hit rate, size, entries).",
       handler=handle_cache_status,
       input_model=CacheStatusInput,
       output_model=CacheStatusOutput,
       annotations={"readOnlyHint": True},
   ),
   "list_file_types": ToolSpec(
       name="list_file_types",
       description="List available file type presets and their associated glob patterns.",
       handler=handle_list_file_types,
       input_model=ListFileTypesInput,
       output_model=ListFileTypesOutput,
       annotations={"readOnlyHint": True},
   ),
   ```
   Coordinate `__all__` updates so handler names are exported.
7. Open `server.py` and extend `_summarize()` (around lines 213-245) with the 4 new branches per acceptance criteria.
8. Write `tests/test_explain_tool.py`:
   - Mock `client.query` via `respx` to return a results array containing the requested `chunk_id` with a valid `explanation` sub-dict. Assert `handle_explain_result` returns the matching `ExplainResultOutput`.
   - Mock `client.query` to return results NOT containing `args.chunk_id`. Assert `McpError` with `code=INVALID_PARAMS` is raised, and the message contains the chunk_id and top_k.
   - Assert `mode`, `top_k`, `alpha`, `explain=True` are propagated into the request body sent to `client.query`.
9. Write `tests/test_folders_tool.py`, `tests/test_cache_tool.py`, `tests/test_file_types_tool.py` per acceptance criteria.
10. Update `tests/test_tools_list.py` — bump expected count to 11 OR change to `>= 11`. Recommend `>= 11` until Plan 04 lands then Phase 55 asserts exactly 16.
11. Run `task mcp:test`. Then `task mcp:pr-qa-gate`. Then `task check:layering`. Then `task before-push`.

## Verification

```bash
# New tool tests
cd agent-brain-mcp && poetry run pytest tests/test_explain_tool.py tests/test_folders_tool.py tests/test_cache_tool.py tests/test_file_types_tool.py -v

# Tools list now includes the 4 new tools
cd agent-brain-mcp && poetry run pytest tests/test_tools_list.py -v

# Full package gate
cd agent-brain-mcp && task pr-qa-gate

# Layering
cd /Users/richardhightower/clients/spillwave/src/agent-brain && task check:layering

# Root gate (MANDATORY)
cd /Users/richardhightower/clients/spillwave/src/agent-brain && task before-push

# Stdio smoke test — list tools via official MCP SDK should now show 11 tools
cd agent-brain-mcp && poetry run python -c "
from agent_brain_mcp.tools import TOOL_REGISTRY
print(f'Tools registered: {len(TOOL_REGISTRY)}')
for name in sorted(TOOL_REGISTRY):
    print(f'  - {name}: readOnlyHint={TOOL_REGISTRY[name].annotations.get(\"readOnlyHint\", False)}')
"
```

## Risk Notes

- **`explain_result` chunk-not-found UX** — the `top_k=50` default (vs search default of 10) is intentional. If MCP clients pass small `top_k` and the chunk isn't there, the error message must guide them to bump it. Test the error message wording — it's user-facing.
- **`_summarize()` merge conflict with Plan 03** — both plans add branches to the same switch. Coordinate by alphabetical ordering of tool names within the switch; resolve in whichever plan lands second.
- **`tools/folders.py` and `tools/cache.py` shared with Plan 03** — those files start out in this plan and gain a second handler in Plan 03. The `__all__` lists need updating in both plans; merge-conflict-prone. Recommend the second-merging plan does a quick re-read before pushing.
- **`list_file_types` "unused client parameter"** — Ruff will flag it. Add `# noqa: ARG001` inline and a comment explaining the ToolSpec uniformity rationale.
- **`cache_status` 503-when-uninitialised** — server returns 503 if the cache isn't initialised. `errors.raise_for_status` maps that to a generic `McpError(INVALID_PARAMS)` per Decision G. Test that path with a respx-mocked 503 response.

---
*Plan 02 of Phase 54*
