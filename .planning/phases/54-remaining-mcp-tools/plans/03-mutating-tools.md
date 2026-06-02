# Plan 03: Mutating tools — add_documents, inject_documents, remove_folder, clear_cache

**Phase:** 54 — 9 remaining MCP tools
**Requirements covered:** TOOL-02 (`add_documents`), TOOL-03 (`inject_documents`), TOOL-06 (`remove_folder`), TOOL-08 (`clear_cache`)
**Depends on:** Plan 01 (schemas + ApiClient methods)
**Parallel-safe with:** Plan 02 (read-only tools) — disjoint handler functions across `tools/*.py` modules; mechanical merge conflicts in `tools/__init__.py::TOOL_REGISTRY` and `server.py::_summarize()` only
**Status:** Not started

## Goal

Implement and register the four mutating Phase 54 tools. `add_documents` and `inject_documents` are job-spawning index operations that return `{job_id, status}` for downstream `wait_for_job` polling (Plan 04). `remove_folder` and `clear_cache` are destructive — both gated by a `confirm: Literal[True]` Pydantic guard per the v1 `cancel_job` safety pattern (CONTEXT Greenfield).

The `inject_documents` tool wraps the same `POST /index/` endpoint as v1's `index_folder` but with required injector script / folder-metadata fields. The `add_documents` tool wraps the path-list endpoint `POST /index/add` and deliberately omits the removed-by-issue-#180 `allow_external` parameter.

## Acceptance Criteria

- [ ] Four new tool handlers exist and are registered in `TOOL_REGISTRY`:
  - `add_documents` → `handle_add_documents` in `agent_brain_mcp/tools/index.py` (extends v1's existing module)
  - `inject_documents` → `handle_inject_documents` in `agent_brain_mcp/tools/inject.py` (new module)
  - `remove_folder` → `handle_remove_folder` in `agent_brain_mcp/tools/folders.py` (extends Plan 02's module)
  - `clear_cache` → `handle_clear_cache` in `agent_brain_mcp/tools/cache.py` (extends Plan 02's module)
- [ ] All four handlers are **sync** (server wraps in `asyncio.to_thread`).
- [ ] `ToolSpec` annotations per CONTEXT decision B:
  - `add_documents`: `openWorldHint: True`
  - `inject_documents`: `openWorldHint: True`
  - `remove_folder`: `destructiveHint: True`
  - `clear_cache`: `destructiveHint: True`
- [ ] `inject_documents` MCP-side pre-validation: when both `injector_script` and `folder_metadata_file` are None, the Pydantic input model rejects (root validator from Plan 01). The handler also defensively re-checks and raises `McpError(INVALID_PARAMS, "At least one of injector_script or folder_metadata_file is required")` if reached. (Per Decision D.)
- [ ] `inject_documents` tool description explicitly mentions: "Injector scripts must be hash-allowlisted server-side (see issue #181). Unallowlisted scripts will fail with a 403 surfaced as INVALID_PARAMS." (CONTEXT `<specifics>`.)
- [ ] `inject_documents` `injector_script` path handling expands `~` and calls `.resolve()` before passing to the server, matching CLI behavior in `inject.py` (CONTEXT Discretion item).
- [ ] `add_documents` schema does **NOT** include `allow_external` — removed from server in issue #180, exposing it would be a confusing no-op. (CONTEXT `<specifics>`.)
- [ ] `remove_folder` and `clear_cache` schemas require `confirm: Literal[True]` — Pydantic rejects before handler runs. (CONTEXT Greenfield.)
- [ ] `remove_folder` 409-when-job-active behavior surfaces as `McpError(INVALID_PARAMS)` via `errors.raise_for_status`. Tool description mentions: "Removing a folder while an indexing job is active for it will fail with INVALID_PARAMS — cancel the job first." (Decision G.)
- [ ] `_summarize()` in `server.py` extended with four new branches:
  - `add_documents → job <id> (queued)`
  - `inject_documents → job <id> (queued)` (or `dry_run: <message>` for dry runs)
  - `remove_folder → <folder>: <chunks> chunks removed`
  - `clear_cache → cache cleared`
- [ ] Unit tests in `agent-brain-mcp/tests/test_add_documents_tool.py` cover: (a) happy path, (b) `force=True` propagates to query param, (c) empty paths list rejected by Pydantic.
- [ ] Unit tests in `agent-brain-mcp/tests/test_inject_documents_tool.py` cover: (a) happy path with `injector_script`, (b) happy path with `folder_metadata_file`, (c) both-None rejected by Pydantic, (d) dry-run path returns `job_id="dry_run"` shape, (e) 403 from server surfaces as `INVALID_PARAMS` with server detail.
- [ ] Unit tests in `agent-brain-mcp/tests/test_remove_folder_tool.py` cover: (a) happy path, (b) missing `confirm: true` rejected by Pydantic, (c) 409-on-active-job surfaces as `INVALID_PARAMS`.
- [ ] Unit tests in `agent-brain-mcp/tests/test_clear_cache_tool.py` cover: (a) happy path, (b) missing `confirm: true` rejected by Pydantic.
- [ ] `task mcp:test`, `task mcp:pr-qa-gate`, `task check:layering`, `task before-push` all pass.

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-mcp/agent_brain_mcp/tools/index.py` | modify | Append `handle_add_documents`. Keep v1's `handle_index_folder` untouched. |
| `agent-brain-mcp/agent_brain_mcp/tools/inject.py` | create | New module — `handle_inject_documents` only. ~60 LOC including path-expansion + defensive validation. |
| `agent-brain-mcp/agent_brain_mcp/tools/folders.py` | modify | Append `handle_remove_folder` (Plan 02 created the module with `handle_list_folders`). |
| `agent-brain-mcp/agent_brain_mcp/tools/cache.py` | modify | Append `handle_clear_cache` (Plan 02 created the module with `handle_cache_status`). |
| `agent-brain-mcp/agent_brain_mcp/tools/__init__.py` | modify | Add 4 `ToolSpec` entries to `TOOL_REGISTRY`. Add imports. Update `__all__`. |
| `agent-brain-mcp/agent_brain_mcp/server.py` | modify | Add 4 branches to `_summarize()` (coordinated with Plan 02). |
| `agent-brain-mcp/tests/test_add_documents_tool.py` | create | 3 tests. |
| `agent-brain-mcp/tests/test_inject_documents_tool.py` | create | 5 tests. |
| `agent-brain-mcp/tests/test_remove_folder_tool.py` | create | 3 tests. |
| `agent-brain-mcp/tests/test_clear_cache_tool.py` | create | 2 tests. |
| `agent-brain-mcp/tests/test_tools_list.py` | modify | Bump expected tool count or keep `>= 11` from Plan 02 (after Plan 03 ships, count is 15 — `>= 15` until Plan 04). |

## Implementation Steps

1. Re-read `agent-brain-server/agent_brain_server/api/routers/index.py`:
   - `POST /index/add` (lines 405-519) — request body is `AddDocumentsRequest` (or similar — confirm field names). Returns `{job_id, status}`. **Confirm `allow_external` is no longer a query/body param** (issue #180).
   - `POST /index/` (lines 158-402) — request body is `IndexRequest`. The `inject_documents` MCP tool sets `injector_script` and/or `folder_metadata_file` in this body.
2. Re-read `agent-brain-server/agent_brain_server/api/routers/folders.py::DELETE /index/folders/` (lines 61-156):
   - Request body is `FolderDeleteRequest` (note: body, not path/query — CONTEXT `<canonical_refs>` and v1 design §2).
   - 409 on active job per FOLD-07; lines 100-114 show the conflict logic.
3. Re-read `agent-brain-server/agent_brain_server/api/routers/cache.py::DELETE /index/cache/` for clear-cache response shape.
4. Open `tools/index.py` and append `handle_add_documents`:
   ```python
   def handle_add_documents(client: ApiClient, args: AddDocumentsInput) -> AddDocumentsOutput:
       body = {"paths": args.paths}  # Note: allow_external removed in issue #180
       response = client.add_documents(body, force=args.force)
       return AddDocumentsOutput(**response)
   ```
5. Create `tools/inject.py` with `handle_inject_documents`:
   ```python
   def handle_inject_documents(client: ApiClient, args: InjectDocumentsInput) -> InjectDocumentsOutput:
       # Defensive re-check (Pydantic root validator should already reject)
       if not args.injector_script and not args.folder_metadata_file:
           raise McpError(
               error=ErrorData(
                   code=INVALID_PARAMS,
                   message="At least one of injector_script or folder_metadata_file is required",
               )
           )
       body = {
           "folder_path": args.folder_path,
           "dry_run": args.dry_run,
           "allow_external": args.allow_external,
           "include_code": args.include_code,
       }
       if args.injector_script:
           # Match CLI inject.py: expand ~ and resolve to absolute path
           body["injector_script"] = str(Path(args.injector_script).expanduser().resolve())
       if args.folder_metadata_file:
           body["folder_metadata_file"] = str(Path(args.folder_metadata_file).expanduser().resolve())
       if args.chunk_size is not None:
           body["chunk_size"] = args.chunk_size
       if args.chunk_overlap is not None:
           body["chunk_overlap"] = args.chunk_overlap

       response = client.inject_documents(body, force=args.force)
       return InjectDocumentsOutput(**response)
   ```
   Note: `Path(...).expanduser().resolve()` is the CLI's pattern in `inject.py`; mirroring it for UX consistency. Read CLI inject.py before finalizing to confirm exact resolve semantics.
6. Open `tools/folders.py` (created in Plan 02) and append `handle_remove_folder`:
   ```python
   def handle_remove_folder(client: ApiClient, args: RemoveFolderInput) -> RemoveFolderOutput:
       # confirm: Literal[True] enforced by Pydantic; defensive re-check optional
       body = {"folder_path": args.folder_path}
       response = client.delete_folder(body)
       return RemoveFolderOutput(**response)
   ```
7. Open `tools/cache.py` (created in Plan 02) and append `handle_clear_cache`:
   ```python
   def handle_clear_cache(client: ApiClient, args: ClearCacheInput) -> ClearCacheOutput:
       response = client.clear_cache()
       return ClearCacheOutput(**response)
   ```
8. Open `tools/__init__.py` and append 4 `ToolSpec` entries. Annotations per CONTEXT decision B:
   ```python
   "add_documents": ToolSpec(
       name="add_documents",
       description="Index a list of document paths. Returns a job_id for polling via wait_for_job or get_job.",
       handler=handle_add_documents,
       input_model=AddDocumentsInput,
       output_model=AddDocumentsOutput,
       annotations={"openWorldHint": True, "destructiveHint": False},
   ),
   "inject_documents": ToolSpec(
       name="inject_documents",
       description=(
           "Index a folder with content injection (custom enrichment script or "
           "folder-level metadata JSON). Returns a job_id for polling. "
           "Injector scripts must be hash-allowlisted server-side (see issue #181); "
           "unallowlisted scripts will fail with INVALID_PARAMS. "
           "At least one of injector_script or folder_metadata_file is required."
       ),
       handler=handle_inject_documents,
       input_model=InjectDocumentsInput,
       output_model=InjectDocumentsOutput,
       annotations={"openWorldHint": True, "destructiveHint": False},
   ),
   "remove_folder": ToolSpec(
       name="remove_folder",
       description=(
           "Remove all indexed chunks for a folder. Requires confirm=true. "
           "Removing a folder while an indexing job is active for it will fail "
           "with INVALID_PARAMS — cancel the job first."
       ),
       handler=handle_remove_folder,
       input_model=RemoveFolderInput,
       output_model=RemoveFolderOutput,
       annotations={"destructiveHint": True},
   ),
   "clear_cache": ToolSpec(
       name="clear_cache",
       description="Clear the embedding cache. Requires confirm=true. Cannot be undone.",
       handler=handle_clear_cache,
       input_model=ClearCacheInput,
       output_model=ClearCacheOutput,
       annotations={"destructiveHint": True},
   ),
   ```
9. Extend `server.py::_summarize()` with the 4 new branches (coordinate alphabetical ordering with Plan 02).
10. Write `tests/test_add_documents_tool.py`:
    - Happy path: `respx`-mock `POST /index/add?force=false`, assert handler returns `AddDocumentsOutput(job_id="<uuid>", status="queued")`.
    - `force=True`: assert the query string contains `force=true`.
    - Empty paths: assert `AddDocumentsInput(paths=[])` raises `pydantic.ValidationError` (the `min_length=1` from Plan 01).
11. Write `tests/test_inject_documents_tool.py`:
    - Happy path with script: assert request body contains absolute resolved `injector_script` path.
    - Happy path with metadata: assert request body contains absolute resolved `folder_metadata_file` path.
    - Both None: assert `InjectDocumentsInput(folder_path="/x")` raises `pydantic.ValidationError`.
    - Dry-run: mock server to return `{"job_id": "dry_run", "status": "completed", "message": "validation ok"}`. Assert `InjectDocumentsOutput.job_id == "dry_run"`.
    - 403 surfaces: mock server to return 403 with `{"detail": "Script not in hash allowlist"}`. Assert `McpError(INVALID_PARAMS)` raised with the server detail in the message.
12. Write `tests/test_remove_folder_tool.py`:
    - Happy path with `confirm=True`.
    - Missing confirm: `RemoveFolderInput(folder_path="/x")` (no `confirm` arg) raises `pydantic.ValidationError`.
    - 409 on active job: mock 409 response; assert `McpError(INVALID_PARAMS)` raised.
13. Write `tests/test_clear_cache_tool.py`:
    - Happy path with `confirm=True`.
    - Missing confirm: `ClearCacheInput()` raises `pydantic.ValidationError`.
14. Update `tests/test_tools_list.py` — `len(TOOL_REGISTRY) >= 15` (Plan 04 brings it to 16).
15. Run `task mcp:test`, `task mcp:pr-qa-gate`, `task check:layering`, `task before-push`.

## Verification

```bash
# Mutating tool tests
cd agent-brain-mcp && poetry run pytest \
  tests/test_add_documents_tool.py \
  tests/test_inject_documents_tool.py \
  tests/test_remove_folder_tool.py \
  tests/test_clear_cache_tool.py \
  -v

# Tools list now includes the 4 new mutating tools (8 total v2 tools so far)
cd agent-brain-mcp && poetry run pytest tests/test_tools_list.py -v

# Full package gate
cd agent-brain-mcp && task pr-qa-gate

# Layering
cd /Users/richardhightower/clients/spillwave/src/agent-brain && task check:layering

# Root gate (MANDATORY)
cd /Users/richardhightower/clients/spillwave/src/agent-brain && task before-push

# Manual smoke: call add_documents via stdio
cd agent-brain-mcp && echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | \
  poetry run agent-brain-mcp --backend http --backend-url http://127.0.0.1:8000 | \
  jq '.result.tools[] | select(.name | test("add_documents|inject_documents|remove_folder|clear_cache"))'
```

## Risk Notes

- **`allow_external` accidentally re-introduced** — easy to copy-paste from v1's `IndexFolderInput` schema. Plan 03 reviewer MUST grep for `allow_external` in the new `AddDocumentsInput` (Plan 01) and `add_documents` handler — should not appear. If it does, that's a security regression.
- **Path expansion for `injector_script`** — `Path(...).expanduser().resolve()` will resolve symlinks too, which may surprise users. Confirm CLI behavior in `inject.py` and match exactly (don't innovate).
- **`confirm: Literal[True]` is a Pydantic v2 pattern** — older v1 syntax differs. Reuse the existing v1 `CancelJobInput.confirm` style as the template; don't roll your own.
- **`remove_folder` 409 mapping** — `errors.raise_for_status` converts to `INVALID_PARAMS`. If you want a more specific error code (e.g., `-32000 InvalidRequest`), that's a Decision G deviation — punt to Phase 55 if it matters for SDK contract tests.
- **`tools/__init__.py` merge conflict with Plan 02** — both plans add `TOOL_REGISTRY` entries. Resolve by alphabetical sort. Second-to-merge plan re-reads + rebases.
- **`_summarize()` merge conflict with Plan 02** — same situation. Order branches alphabetically by tool name.
- **`inject_documents` body structure** — the server's `POST /index/` route accepts ~15 fields; we send only ~8. The remaining server defaults (`watch_mode`, `code_chunk_strategy`, etc.) apply. Confirm the server doesn't 422 on missing-optional-with-no-default fields.
- **`_request` returning dict shape mismatch** — `clear_cache()` may return an empty body on 204. Confirm `DELETE /index/cache/` actually returns JSON; if it returns 204 No Content, the ApiClient method needs to handle the empty body. (This is something to confirm in Plan 01's `delete_folder` / `clear_cache` tests.)

---
*Plan 03 of Phase 54*
