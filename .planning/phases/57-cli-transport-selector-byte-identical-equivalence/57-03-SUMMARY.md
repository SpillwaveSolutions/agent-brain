---
phase: 57-cli-transport-selector-byte-identical-equivalence
plan: 03
subsystem: cli-via-mcp-backends

tags: [mcp, v3, cli, backend-client, asyncio, sync-facade, pattern-a, method-wiring, destructive-op-guard, no-silent-fallback]

# Dependency graph
requires:
  - phase: 57-02
    provides: query() wired on both McpStdioBackend and McpHttpBackend with Pattern A sync facade + _coerce_query_response translator + the late-import-inside-helper pattern that Plan 57-03 mirrors for 10 more methods
  - phase: 57-01
    provides: open_backend dispatcher + --transport mcp / --mcp-transport stdio|http selector + 3 §3.5 misuse cases as exit-2 errors
  - phase: 56-03
    provides: McpStdioBackend / McpHttpBackend skeletons + NotImplementedError sentinel bodies on every method
provides:
  - "McpStdioBackend.health — asyncio.run(_async_health()) -> call_tool('server_health', {}) -> _coerce_health_status(_unwrap_payload(...))"
  - "McpStdioBackend.status — asyncio.run(_async_status()) -> read_resource(AnyUrl('corpus://status')) -> _coerce_indexing_status(_unwrap_resource_body(...))"
  - "McpStdioBackend.list_folders — asyncio.run(_async_list_folders()) -> read_resource(AnyUrl('corpus://folders')) -> _coerce_folder_info_list(...)"
  - "McpStdioBackend.get_job(id) — asyncio.run(_async_get_job(id)) -> read_resource(AnyUrl(f'job://{id}'))"
  - "McpStdioBackend.list_jobs(lim) — asyncio.run(_async_list_jobs(lim)) -> call_tool('list_jobs', {'limit': lim}) -> payload['jobs']"
  - "McpStdioBackend.cache_status — asyncio.run(_async_cache_status()) -> call_tool('cache_status', {})"
  - "McpStdioBackend.index(...) — asyncio.run(_async_index(tool_name, body)) — branches between index_folder / inject_documents based on injector_script-or-folder_metadata_file presence; body assembled by the shared _build_index_body() helper which drops CLI-only fields not in the v2 MCP tool schemas"
  - "McpStdioBackend.delete_folder(p) — asyncio.run(_async_delete_folder(p)) -> call_tool('remove_folder', {folder_path, confirm: True})"
  - "McpStdioBackend.cancel_job(id) — asyncio.run(_async_cancel_job(id)) -> call_tool('cancel_job', {job_id, confirm: True})"
  - "McpStdioBackend.clear_cache — asyncio.run(_async_clear_cache()) -> call_tool('clear_cache', {confirm: True})"
  - "McpStdioBackend.reset — raises NotImplementedError verbatim per CONTEXT.md §decisions (no _PHASE_57_NOT_WIRED sentinel)"
  - "McpHttpBackend — all 10 methods mirrored using streamablehttp_client + (read, write, *_) tuple-absorb instead of stdio_client; reset() body duplicates the same verbatim wording by design"
  - "5 shared translator helpers in agent_brain_mcp/client.py: _coerce_health_status, _coerce_indexing_status, _coerce_folder_info_list, _coerce_index_response (new) plus _coerce_query_response (Plan 57-02) — each late-imports api_client to avoid the cross-package module-load cycle"
  - "2 shared unwrap helpers: _unwrap_payload (structuredContent or content[0].text JSON fallback for call_tool results) and _unwrap_resource_body (contents[0].text JSON for read_resource results)"
  - "_build_index_body(folder_path, ..., injector_script, folder_metadata_file, dry_run) -> (body, tool_name) — narrows CLI BackendClient.index params to the v2 MCP tool input schemas (additionalProperties=false rejects unknown fields)"
  - "McpStdioBackend._stdio_params() helper — factored out so every async helper builds StdioServerParameters from self.command/cwd/env identically"
  - "agent-brain-mcp/tests/test_cli_backends_methods_wire.py — 12 stdio wire tests (fast path, runs in task before-push) + 11 e2e_http tests (opt-in via -m e2e_http); 23 total covering each wired method's wire shape + verbatim reset() on both backends"
affects:
  - "Phase 58 (mcp.runtime.json discovery + agent-brain mcp start|stop helpers) — both helper commands now build on a functional McpHttpBackend; the per-call subprocess spawn in McpStdioBackend is the Phase 60 hygiene target as flagged"
  - "Phase 59 (prompt + resources commands) — the late-import-inside-helper translator pattern is the template for prompt translators"
  - "Phase 60 (subprocess hygiene) — Pattern A per-call spawn confirmed across all 10 stdio methods; persistent-subprocess refinement target unchanged"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "5-helper translator pattern locked. Each translator does a late-import of agent_brain_cli.client.api_client inside the helper body (not at module top), avoiding the module-load cycle that would otherwise materialize between agent_brain_mcp and agent_brain_cli. Plan 57-02 introduced the pattern with _coerce_query_response; Plan 57-03 mirrored it 4× for HealthStatus, IndexingStatus, list[FolderInfo], IndexResponse. mypy strict clean on both packages under ignore_missing_imports=true."
    - "Shared _unwrap_payload + _unwrap_resource_body unwrap helpers. structuredContent preferred (typed-channel); content[0].text JSON fallback when the tool's output_schema is not declared (Plan 57-02 had this inline in _async_query; Plan 57-03 extracted to a shared helper used by 8 of the 10 wired methods on each backend). Removed the now-redundant inline json fallback from McpHttpBackend._async_query for consistency."
    - "Pattern A confirmed across all 10 methods. Each public method on each backend is a 1-line asyncio.run(self._async_*()) facade; the matching _async_* helper opens stdio_client / streamablehttp_client, opens ClientSession, calls one MCP wire method (call_tool or read_resource), then unwraps and translates. Phase 60 owns the persistent-subprocess refinement target unchanged. No overhead concern surfaced in the 22-test fast suite (~5s) or the 11-test e2e_http suite (~8s)."
    - "_stdio_params() shared between McpStdioBackend's 10 async helpers. Plan 57-02 had the StdioServerParameters construction inlined in _async_query; Plan 57-03 factored it out so every async helper builds the params identically — single source of truth for the cwd/env/--transport-stdio invariants."
    - "_build_index_body() narrows the CLI BackendClient.index() parameter set (17 params) to the v2 MCP tool input schemas (IndexFolderInput: 6 fields; InjectDocumentsInput: 8 fields). CLI-only fields without a v2 wire equivalent (recursive, supported_languages, code_chunk_strategy, include_patterns, exclude_patterns, include_types, generate_summaries, watch_mode, watch_debounce_seconds) are silently dropped. Phase 58+ may widen the MCP tool schemas if any of these becomes load-bearing on --transport mcp; v3 Phase 57 ships the narrow body."
    - "Destructive-op guard pass-through. cancel_job, remove_folder, AND clear_cache all carry confirm=True in their call_tool body. The CONTEXT note only flagged clear_cache explicitly; the underlying Phase 54 Plan 03 schema applies to all three destructive tools. Pass-through (no CLI-side prompt) is recommended in CONTEXT for parity with --transport uds — runtime behavior unchanged across transports."
    - "Verbatim reset() string literal duplicated per backend by design. The McpStdioBackend.reset() body and McpHttpBackend.reset() body each contain the identical 3-line string concatenation matching CONTEXT.md §decisions verbatim. Each backend's reset() is independently unit-tested for byte-equality of the runtime message. _RESET_NOT_SUPPORTED constant was introduced then removed — duplicating the literal is the simpler, more grep-friendly shape."

key-files:
  created:
    - "agent-brain-mcp/tests/test_cli_backends_methods_wire.py (~1150 lines, 23 tests: 12 stdio fast + 11 e2e_http opt-in)"
  modified:
    - "agent-brain-mcp/agent_brain_mcp/client.py (5 new translator helpers + 2 unwrap helpers + _build_index_body + _stdio_params; 10 wired methods × 2 backends + reset() with verbatim wording on each; obsolete McpHttpBackend.health()/.status() stubs removed; _PHASE_57_NOT_WIRED constant deleted now that zero raise sites use it; docstrings updated to reflect Phase-57-wired state)"

key-decisions:
  - "Pattern A confirmed across the full 10-method surface. Plan 57-02 deferred the Pattern B (persistent _loop + persistent subprocess) measurement to Phase 60 against agent-brain jobs --watch profiling; Plan 57-03's wire tests across all 10 methods show no compounding overhead in the 22-test fast suite. Phase 60 owns the measurement + revisit if --watch profiling shows the per-call spawn cost compounding."
  - "5 translator helpers + 2 unwrap helpers — every method's translator follows the same shape. _coerce_query_response (Plan 57-02), _coerce_health_status, _coerce_indexing_status, _coerce_folder_info_list, _coerce_index_response (this plan). list_jobs / get_job / cancel_job / cache_status / clear_cache / delete_folder return dict[str, Any] verbatim — their translators are pass-throughs via _unwrap_payload / _unwrap_resource_body, no per-method coerce needed."
  - "_build_index_body extracted to a module-level helper, NOT a method. The v2 MCP index_folder/inject_documents body shape is identical between the two backends (it's just JSON over the MCP wire); the helper is a pure function returning (body, tool_name). Phase 58/59 can call it directly when adding new MCP-tool body builders without picking a backend-class to attach to."
  - "_stdio_params() ended up as a private method on McpStdioBackend (Claude's discretion call per the SUMMARY output spec). Inlining was the alternative; the shared method is the simpler maintenance shape — Phase 60's persistent-subprocess refactor can override or extend it without re-flowing 10 _async_* helper bodies. Plan 57-02's _async_query was also retrofitted to call _stdio_params() for consistency."
  - "remove_folder, cancel_job, and clear_cache all carry confirm=True. CONTEXT note explicitly mentioned only clear_cache; the underlying Phase 54 Plan 03 destructive-op guard applies to all three. Pass-through (no CLI-side prompt) per CONTEXT recommendation — runtime behavior matches --transport uds verbatim."
  - "_build_index_body drops 9 CLI-only fields (recursive, supported_languages, code_chunk_strategy, include_patterns, exclude_patterns, include_types, generate_summaries, watch_mode, watch_debounce_seconds) before sending the body to the MCP tool. The v2 tool input schemas use additionalProperties=false at the JSON Schema layer — forwarding these would fail SDK-level validation. Phase 58+ may widen the schemas if any becomes load-bearing on --transport mcp."
  - "The injector_script wire test asserts endswith('enrich.py'), not equality. The MCP inject_documents handler resolves injector_script via Path(...).expanduser().resolve() (tools/inject.py:94) to mirror the CLI's behavior — passing a relative path through the wire layer therefore lands as an absolute path in the request body. The test verifies wire-shape pinning (the field IS present in the POST body and DOES carry the file name)."
  - "_PHASE_57_NOT_WIRED constant deleted now that zero raise sites use it. The string 'Wired in Phase 57+' is gone from the module. If a Phase 58+ skeleton ever needs an equivalent sentinel, the constant will be re-introduced with a different name (e.g., _PHASE_58_NOT_WIRED) so historical grep boundaries stay clean."
  - "Removed obsolete McpHttpBackend.health() and .status() stubs leftover from the Plan 56-03 skeleton — they were shadowed by the new wired versions further down in the class body but would have surfaced as 'method declared twice' confusion in code review."
  - "subprocess.run vs subprocess.Popen — N/A. Plan 57-03 does not introduce any direct subprocess calls in client.py; the MCP SDK's stdio_client / streamablehttp_client own the lifecycle internally (via anyio.open_process). The CONTEXT Claude's-discretion note about run-vs-Popen was specifically about the per-call spawn — that decision is delegated to the SDK. Phase 60 may revisit if the SDK exposes hooks."

patterns-established:
  - "5-helper translator pattern — every method that returns a CLI-shaped dataclass (HealthStatus, IndexingStatus, FolderInfo, QueryResponse, IndexResponse) has a dedicated _coerce_*_response helper. Methods that return dict[str, Any] verbatim use _unwrap_payload / _unwrap_resource_body directly with no per-method translator. Phase 58 (resources/prompts) and Phase 59 (more CLI dataclasses on the MCP wire) should follow this shape."
  - "_unwrap_payload + _unwrap_resource_body — shared module-level helpers preferred over inline structuredContent fallback. Plan 57-02 had the inline pattern; Plan 57-03 extracted it. Every future MCP-tool wire path should call _unwrap_payload (call_tool) or _unwrap_resource_body (read_resource)."
  - "Destructive-op guard pass-through. Any MCP tool whose input schema declares confirm: Literal[True] (currently: cancel_job, remove_folder, clear_cache; Phase 58+ may add reset_index) MUST pass confirm=True from the wire layer. CONTEXT discretion was 'pass-through for parity with --transport uds' — runtime behavior identical across transports."
  - "Verbatim reset() string-literal duplication. The reset() body on each backend contains the identical 3-line string concatenation. NO shared constant — each backend's reset() is independently grep-able and independently unit-tested for byte-equality of the runtime message."

requirements-completed:
  - CLI-MCP-03

# Metrics
duration: ~17 min
completed: 2026-06-06
---

# Phase 57 Plan 03: Wire Remaining 10 BackendClient Methods on Both MCP Backends + Deliberate `reset()` NotImplementedError Summary

**Every BackendClient method on `McpStdioBackend` and `McpHttpBackend` now wires to a real MCP tool/resource per the design doc §2.3 mapping table — `health` → `server_health`, `status` → `corpus://status` resource, `list_folders` → `corpus://folders` resource, `get_job` → `job://<id>` resource, `list_jobs` / `cache_status` → `call_tool`, `index` → `index_folder` / `inject_documents` branching via the new `_build_index_body` helper that drops CLI-only fields not in the v2 MCP input schemas, `delete_folder` / `cancel_job` / `clear_cache` all pass through `confirm: True` (Phase 54 Plan 03 destructive-op guard, CONTEXT pass-through recommendation honored). `reset()` on BOTH backends raises `NotImplementedError` with the verbatim CONTEXT.md §decisions wording (`"--transport mcp does not support reset; use --transport uds or http (no reset_index MCP tool in v2; v3 Phase 57+ open decision per design doc §4 risks)"`) — no `_PHASE_57_NOT_WIRED` sentinel anywhere in `client.py`; the constant itself was deleted. 22-test fast wire suite (12 stdio + 4 skeleton + 5 Plan 57-02 query + 1 http reset) green in ~7s; 11-test `-m e2e_http` opt-in suite green in ~8s. `task before-push` exits 0 (490 MCP tests pass; CLI/UDS/server suites all green). CLI-MCP-03 fully closed: selector + dispatcher (Plan 57-01) + full method wiring (this plan).**

## Performance

- **Duration:** ~17 min (1022 seconds)
- **Started:** 2026-06-06T23:34:56Z
- **Completed:** 2026-06-06T23:51:58Z
- **Tasks:** 4 (Task 1 read-only stdio + 6 tests, Task 2 mutating stdio + 6 tests, Task 3 HTTP mirror + 11 tests, Task 4 task before-push gate)
- **Files modified:** 2 (client.py + new test file)
- **Tests added:** 23 (12 stdio fast + 11 e2e_http opt-in)
- **task before-push outcome:** PASS (exit 0; 490 MCP tests + CLI/UDS/server suites green)

## Task Commits

Each task was committed atomically:

1. **Task 1: 6 read-only methods on McpStdioBackend** — `90c835a` (feat)
2. **Task 2: 4 mutating methods + reset() sentinel on McpStdioBackend** — `f940f76` (feat)
3. **Task 3: Mirror 10 methods + reset() onto McpHttpBackend** — `ceeca17` (feat)
4. **Task 4: task before-push exit 0** — verification only; metadata commit follows.

## Files Created/Modified

- `agent-brain-mcp/agent_brain_mcp/client.py` (modified, +~430 lines net) — added 5 translator helpers (_coerce_health_status, _coerce_indexing_status, _coerce_folder_info_list, _coerce_index_response — _coerce_query_response was Plan 57-02), 2 unwrap helpers (_unwrap_payload, _unwrap_resource_body), 1 body-builder helper (_build_index_body). McpStdioBackend gains _stdio_params() + 10 wired methods (each is a 1-line asyncio.run facade + matching _async_* helper) + reset() with verbatim wording. McpHttpBackend mirrors the same 10 methods using streamablehttp_client + (read, write, *_) tuple-absorb + the same reset() wording. _PHASE_57_NOT_WIRED constant deleted. Obsolete McpHttpBackend.health()/.status() stubs (shadowed by new wired versions) removed. Docstrings on both backends updated to reflect Phase-57-wired state. mypy strict + Black/Ruff clean.
- `agent-brain-mcp/tests/test_cli_backends_methods_wire.py` (created, ~1150 lines) — 23 tests covering each wired method's wire shape on both backends. 12 stdio tests use the fake-server-as-tmp_path-subprocess pattern (subprocess spawns the MCP SDK's stdio_client server harness wired through an httpx.MockTransport to deterministic response bodies; the test reads back a JSONL log of HTTP requests the MCP server hit to prove the right tool/resource was dispatched). 11 e2e_http tests use a uvicorn-via-streamablehttp subprocess (same MockTransport-backed handler) per test; opt-in via `-m e2e_http` marker. Both legs cover all 10 wired methods + reset(). Schema-shape responses for cache_status (hits/misses/hit_rate/mem_entries/entry_count/size_bytes), clear_cache (count/size_bytes/size_mb), cancel_job (job_id/cancelled/message), remove_folder (folder_path/chunks_deleted/message) match the Phase 54 Plan 03 Pydantic output schemas verbatim.

## Wire mapping (Plan 57-03 portion of design doc §2.3)

| BackendClient method | McpStdioBackend wire | McpHttpBackend wire | Translator |
|---|---|---|---|
| `health()` | `call_tool('server_health', {})` ✓ | `call_tool('server_health', {})` ✓ | `_coerce_health_status` |
| `status()` | `read_resource(AnyUrl('corpus://status'))` ✓ | `read_resource(AnyUrl('corpus://status'))` ✓ | `_coerce_indexing_status` |
| `query(...)` | `call_tool('search_documents', args)` ✓ (Plan 57-02) | `call_tool('search_documents', args)` ✓ (Plan 57-02) | `_coerce_query_response` |
| `index(...)` | `call_tool('index_folder' \| 'inject_documents', body)` ✓ | same ✓ | `_coerce_index_response` |
| `list_folders()` | `read_resource(AnyUrl('corpus://folders'))` ✓ | same ✓ | `_coerce_folder_info_list` |
| `delete_folder(p)` | `call_tool('remove_folder', {folder_path: p, confirm: True})` ✓ | same ✓ | `_unwrap_payload` pass-through |
| `list_jobs(lim)` | `call_tool('list_jobs', {'limit': lim})` → `payload['jobs']` ✓ | same ✓ | `_unwrap_payload['jobs']` |
| `get_job(id)` | `read_resource(AnyUrl(f'job://{id}'))` ✓ | same ✓ | `_unwrap_resource_body` pass-through |
| `cancel_job(id)` | `call_tool('cancel_job', {job_id: id, confirm: True})` ✓ | same ✓ | `_unwrap_payload` pass-through |
| `cache_status()` | `call_tool('cache_status', {})` ✓ | same ✓ | `_unwrap_payload` pass-through |
| `clear_cache()` | `call_tool('clear_cache', {confirm: True})` ✓ | same ✓ | `_unwrap_payload` pass-through |
| `reset()` | NotImplementedError (verbatim §3.5/§4 wording) | NotImplementedError (verbatim §3.5/§4 wording) | n/a |

## Decisions Made

- **Pattern A confirmed across the 10-method surface** — no overhead concern observed in the 22-test fast suite. Phase 60 owns the persistent-subprocess refinement target unchanged.
- **5 translator helpers + 2 unwrap helpers** — each method that returns a CLI-shaped dataclass has a dedicated `_coerce_*_response`; methods that return `dict[str, Any]` verbatim use `_unwrap_payload` / `_unwrap_resource_body` directly.
- **`_build_index_body` extracted as a module-level pure function** — returns `(body, tool_name)`; consumable from either backend without picking a class to attach to.
- **`_stdio_params()` ended up as a private method on `McpStdioBackend`** (Claude's discretion call) — Plan 57-02's `_async_query` was retrofitted to use it for consistency.
- **`remove_folder`, `cancel_job`, AND `clear_cache` all carry `confirm: True`** — CONTEXT note flagged only `clear_cache` explicitly; the same Phase 54 Plan 03 destructive-op guard applies to all three. Pass-through per CONTEXT recommendation.
- **`_build_index_body` drops 9 CLI-only fields** that have no v2 MCP wire equivalent. Phase 58+ may widen the tool schemas if any becomes load-bearing.
- **Injector_script test asserts `endswith('enrich.py')`** — the MCP `inject_documents` handler resolves the path to absolute (tools/inject.py:94) to mirror CLI behavior.
- **`_PHASE_57_NOT_WIRED` constant deleted** — zero raise sites use it after Task 3.
- **Removed obsolete McpHttpBackend.health()/.status() stubs** — shadowed by new wired versions; would confuse code review.
- **subprocess.run vs Popen — N/A.** The MCP SDK owns the per-call subprocess lifecycle internally (via `anyio.open_process`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] v2 MCP tool input schemas use `additionalProperties=false` — `_async_index` body was over-inclusive**

- **Found during:** Task 2 (mutating-method wiring).
- **Issue:** The plan's `_async_index` body construction forwarded the full CLI `BackendClient.index()` parameter set including `recursive`, `supported_languages`, `code_chunk_strategy`, `include_patterns`, `exclude_patterns`, `include_types`, `generate_summaries`, `watch_mode`, `watch_debounce_seconds`. The v2 MCP `IndexFolderInput` and `InjectDocumentsInput` Pydantic schemas use `extra="forbid"` (or default `additionalProperties=false` at the JSON Schema layer), so the MCP SDK's call_tool validation rejected the body before it reached the server with: `"Additional properties are not allowed ('code_chunk_strategy', 'dry_run', 'generate_summaries', 'recursive' were unexpected)"`.
- **Fix:** Extracted `_build_index_body(folder_path, chunk_size, chunk_overlap, include_code, force, injector_script, folder_metadata_file, dry_run) -> (body, tool_name)` as a module-level pure function. It forwards only the 6 fields `IndexFolderInput` accepts (folder_path, force, include_code, chunk_size, chunk_overlap — plus injector_script/folder_metadata_file/dry_run when targeting `inject_documents`). The 9 dropped CLI-only fields are documented in the helper's docstring as a Phase 58+ scope-widening candidate.
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/client.py` (added `_build_index_body`; refactored `McpStdioBackend.index` AND `McpHttpBackend.index` to delegate to it).
- **Verification:** `test_stdio_index_routes_to_index_folder_when_no_injector` and `test_stdio_index_routes_to_inject_documents_when_injector_set` pass; mirrored e2e_http tests pass.
- **Committed in:** `f940f76` (Task 2).

**2. [Rule 3 - Blocking] `cancel_job` and `remove_folder` also require `confirm: True` (not just `clear_cache`)**

- **Found during:** Task 2 (mutating-method wiring).
- **Issue:** The CONTEXT note explicitly flagged `confirm: True` for `clear_cache` and recommended pass-through. The underlying Phase 54 Plan 03 destructive-op guard ALSO applies to `cancel_job` (`CancelJobInput.confirm: Literal[True]`) and `remove_folder` (`RemoveFolderInput.confirm: Literal[True]`). Without `confirm: True` in the call_tool body, SDK validation rejected the request with `"'confirm' is a required property"`.
- **Fix:** Updated `_async_cancel_job`, `_async_delete_folder`, and `_async_clear_cache` to send `confirm: True` on both backends. Documented the destructive-op guard rationale in each method's body comment. Honored the CONTEXT "pass-through for parity with --transport uds" recommendation — no CLI-side confirmation prompt added.
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/client.py` (6 method bodies — 3 methods × 2 backends).
- **Verification:** All 3 `test_*_cancel_job_routes_to_cancel_job_tool` / `test_*_delete_folder_routes_to_remove_folder_tool` / `test_*_clear_cache_routes_to_clear_cache_tool` tests pass on both backends.
- **Committed in:** `f940f76` (Task 2) for stdio; `ceeca17` (Task 3) for HTTP.

**3. [Rule 1 - Bug] Schema-shape mismatch in fake-server test responses**

- **Found during:** Task 1 (read-only stdio wiring), Task 2 (mutating).
- **Issue:** Initial fake-server responses for `/index/cache/`, `/index/jobs/<id>` (delete), and other endpoints used field shapes that didn't match the Phase 54 Plan 03 Pydantic output schemas. `CacheStatusOutput` required hits/misses/**hit_rate**/mem_entries/entry_count/size_bytes (NOT enabled/disk_bytes); `ClearCacheOutput` required count/size_bytes/size_mb (NOT cleared/message); `CancelJobOutput` required cancelled bool (NOT status: 'cancelled'); `IndexFolderOutput` required folder_path (in addition to JobSummary fields).
- **Fix:** Updated the fake-server response bodies in both `_FAKE_STDIO_SERVER_SCRIPT` and `_FAKE_HTTP_METHODS_SERVER_SCRIPT` to match the actual Phase 54 schemas. Updated the test assertions to check schema-correct fields (`hits/hit_rate`, `count`, `cancelled is True`, `chunks_deleted`).
- **Files modified:** `agent-brain-mcp/tests/test_cli_backends_methods_wire.py`.
- **Verification:** All 12 stdio + 11 e2e_http wire tests pass.
- **Committed in:** `90c835a` (Task 1 — cache_status fix) and `f940f76` (Task 2 — cancel_job + clear_cache fix); `ceeca17` (Task 3 — HTTP mirror).

**4. [Rule 1 - Bug] `inject_documents` MCP handler resolves `injector_script` to absolute path**

- **Found during:** Task 2 (mutating).
- **Issue:** Initial test asserted `body["injector_script"] == "enrich.py"` literal-equal. The MCP `inject_documents` handler (`tools/inject.py:94`) resolves the input via `Path(args.injector_script).expanduser().resolve()` to mirror the CLI's behavior — passing a relative path through the wire layer therefore lands as an absolute path under the subprocess's cwd in the request body.
- **Fix:** Switched both stdio and http inject-script tests from literal-equal to `body["injector_script"].endswith("enrich.py")`. Added a comment explaining the path-resolution behavior.
- **Files modified:** `agent-brain-mcp/tests/test_cli_backends_methods_wire.py` (2 test assertions).
- **Verification:** `test_stdio_index_routes_to_inject_documents_when_injector_set` and `test_http_index_routes_to_inject_documents_when_injector_set` both pass.
- **Committed in:** `f940f76` (Task 2 — stdio) and `ceeca17` (Task 3 — HTTP).

**5. [Rule 1 - Bug] Two unused `# type: ignore[union-attr]` comments after the unwrap-helper refactor**

- **Found during:** Task 1 (read-only stdio), after first mypy pass.
- **Issue:** After extracting `_unwrap_payload` and `_unwrap_resource_body` and tightening their return type via `assert isinstance(parsed, dict)`, the two `# type: ignore[union-attr]` comments inside the helpers became unused. mypy strict surfaces these as `error: Unused "type: ignore" comment [unused-ignore]`.
- **Fix:** Removed the two now-unused `type: ignore` comments. The `assert isinstance(...)` narrows the type explicitly so mypy is satisfied.
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/client.py` (2 lines).
- **Verification:** `poetry run mypy agent_brain_mcp/client.py` exits 0.
- **Committed in:** `90c835a` (Task 1).

**6. [Rule 1 - Bug] Two obsolete McpHttpBackend method stubs leftover from Plan 56-03 skeleton**

- **Found during:** Task 3 (HTTP mirror).
- **Issue:** After adding the new wired `health()` and `status()` methods to McpHttpBackend (further down in the class body), the original Plan 56-03 skeleton `raise NotImplementedError(_PHASE_57_NOT_WIRED)` stubs near the top of the class were shadowed but still present. Running `grep -c "raise NotImplementedError(_PHASE_57_NOT_WIRED)"` returned 2 (not 0 as the Task 3 acceptance criterion requires); Python would silently dispatch to the new (later-defined) methods, but the dead code would confuse code review.
- **Fix:** Removed the 2 obsolete stubs.
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/client.py` (4 lines deleted).
- **Verification:** `grep -c "raise NotImplementedError(_PHASE_57_NOT_WIRED)"` returns 0; `grep -c "raise NotImplementedError"` returns exactly 2 (the two `reset()` bodies).
- **Committed in:** `ceeca17` (Task 3).

---

**Total deviations:** 6 auto-fixed (2 Rule 3 blocking — schema mismatches between BackendClient parameters and MCP tool schemas; 4 Rule 1 bugs — fake-server response shapes + unused type-ignores + obsolete stubs).
**Impact on plan:** All six were resolved within their introducing task. The two Rule 3 blockers (`additionalProperties=false` + missing `confirm: True` on cancel_job/remove_folder) document material wire-shape constraints that Phase 58+ planners should account for when widening the MCP tool surface. None required architectural changes (Rule 4) — the existing translator-helper + sync-facade shape absorbed all fixes.

## Wire-arg name mismatches discovered (Phase 58 hand-off note)

The following CLI `BackendClient` parameter names have **no v2 MCP tool input-schema equivalent** and are silently dropped by `_build_index_body` today:

- `recursive` (CLI: bool, default True; MCP tools: no equivalent — server-side `/index/` always recurses)
- `supported_languages` (CLI: list[str] | None; MCP: no equivalent — server-side defaults to all)
- `code_chunk_strategy` (CLI: str, default "ast_aware"; MCP: no equivalent — server-side hardcoded)
- `include_patterns` / `exclude_patterns` (CLI: list[str] | None; MCP: no equivalent)
- `include_types` (CLI: list[str] | None; MCP: no equivalent — CLI presets)
- `generate_summaries` (CLI: bool, default False; MCP: no equivalent — server-side default)
- `watch_mode` / `watch_debounce_seconds` (CLI: str | None / int | None; MCP: no equivalent — CLI-side feature)

Phase 58+ planners considering whether to widen `IndexFolderInput` / `InjectDocumentsInput` should weigh: (a) whether the CLI-only knobs are load-bearing on `--transport mcp` for any real operator workflow, and (b) whether widening the schema breaks v10.2's pinned MCP client compatibility (24 plans across Phases 50-55 use the current shape). Default recommendation: hold for v4 unless a concrete operator request surfaces.

## Sentinel cleanup observations

- Final `_PHASE_57_NOT_WIRED` raise count: 0 (Task 3 acceptance criterion met).
- `_PHASE_57_NOT_WIRED` constant deleted from `client.py` (the optional cleanup the plan flagged).
- Verbatim `--transport mcp does not support reset` wording: 2 occurrences (one per backend's `reset()` body). The runtime message is byte-identical and asserted independently by `test_stdio_reset_raises_verbatim_not_implemented_error` and `test_http_reset_raises_verbatim_not_implemented_error`.
- Total `raise NotImplementedError` count: exactly 2 (Task 4 acceptance criterion met).

## Issues Encountered

- **MCP SDK DeprecationWarning surfaced under e2e_http:** `mcp.client.streamable_http` will be renamed `streamable_http_client` in a future SDK release per the SDK upgrade notes (also observed in Plan 57-02). Not a Phase 57 concern; Phase 60 (or whichever phase bumps the MCP SDK pin) should swap the import. Pinned today via the SDK version constraint in `agent-brain-mcp/pyproject.toml`.
- **No zombie processes observed** during the 22-test fast suite OR the 11-test e2e_http opt-in suite. Pattern A teardown (asyncio.run exits the event loop on each call; the SDK's `stdio_client` / `streamablehttp_client` close their subprocess in the async context manager's `__aexit__`) is clean.

## User Setup Required

None — Plan 57-03 ships only code + tests. Plan 57-02's contract test (CLI-MCP-04 DoD anchor) still requires `OPENAI_API_KEY` to run the byte-identical-equivalence proof end-to-end; that requirement is unchanged.

## Next Phase Readiness

- **Phase 58 ready to execute:** `mcp.runtime.json` discovery + `agent-brain mcp start` / `agent-brain mcp stop` helper commands build on the now-functional `McpHttpBackend(url=...)`. The per-call subprocess spawn in `McpStdioBackend` is the Phase 60 hygiene target (unchanged from Plan 57-02's hand-off note).
- **CLI-MCP-03 fully closed.** Plan 57-01 shipped selector + dispatcher + 3 §3.5 misuse cases. Plan 57-02 shipped query() wiring + CLI-MCP-04 byte-equivalence DoD anchor. Plan 57-03 (this plan) shipped the remaining 10 BackendClient methods on both backends + the verbatim reset() NotImplementedError on both. Every CLI subcommand except `agent-brain reset` works end-to-end over `--transport mcp`. Marked Complete in REQUIREMENTS.md.
- **Phase 57 milestone-level outcome:** `--transport mcp` is functionally at parity with `--transport uds` / `--transport http` for all reachable methods. The operator's transport flag is honored or the CLI exits with `exit code 2` (no silent fallback). The `reset()` case is the only intentional gap — the operator receives the verbatim CONTEXT.md §decisions pointer to the alternate transport.
- **No blockers for Phase 58.**

---
*Phase: 57-cli-transport-selector-byte-identical-equivalence*
*Completed: 2026-06-06*

## Self-Check: PASSED

- FOUND: `agent-brain-mcp/agent_brain_mcp/client.py` (5 translator helpers + 2 unwrap helpers + _build_index_body + _stdio_params; 10 wired methods × 2 backends; 2 reset() bodies with verbatim wording; mypy strict + Black/Ruff clean)
- FOUND: `agent-brain-mcp/tests/test_cli_backends_methods_wire.py` (12 stdio fast tests + 11 e2e_http opt-in tests = 23 total)
- FOUND: `.planning/phases/57-cli-transport-selector-byte-identical-equivalence/57-03-SUMMARY.md` (this file)
- FOUND: commit `90c835a` (feat(57-03): wire 6 read-only methods on McpStdioBackend)
- FOUND: commit `f940f76` (feat(57-03): wire 4 mutating methods + reset() sentinel on McpStdioBackend)
- FOUND: commit `ceeca17` (feat(57-03): mirror 10 wired methods + reset() onto McpHttpBackend)
- VERIFIED: `grep -c "raise NotImplementedError(_PHASE_57_NOT_WIRED)" client.py` returns 0 (Task 3 acceptance criterion)
- VERIFIED: `grep -c "raise NotImplementedError" client.py` returns 2 (Task 4 acceptance criterion — only the two reset() bodies)
- VERIFIED: `grep -c "does not support reset" client.py` returns 2 (one per backend's reset() body; verbatim CONTEXT.md wording)
- VERIFIED: `grep -c '"server_health"' client.py` returns 2 (Task 1 acceptance — one per backend)
- VERIFIED: `grep -c '"corpus://status"' client.py` returns 2 (Task 1 acceptance — one per backend)
- VERIFIED: `grep -c '"corpus://folders"' client.py` returns 2 (Task 1 acceptance — one per backend)
- VERIFIED: `grep -c '"list_jobs"' client.py` returns 2 (Task 1 acceptance — one per backend)
- VERIFIED: `grep -c '"cache_status"' client.py` returns 2 (Task 1 acceptance — one per backend)
- VERIFIED: `grep -c '"index_folder"' client.py` returns 1 (string literal lives in shared `_build_index_body` helper; both backends call it — acceptance criterion >=1)
- VERIFIED: `grep -c '"inject_documents"' client.py` returns 1 (same shared-helper rationale)
- VERIFIED: `grep -c '"remove_folder"' client.py` returns 2 (Task 2 acceptance — one per backend)
- VERIFIED: `grep -c '"cancel_job"' client.py` returns 2 (Task 2 acceptance — one per backend)
- VERIFIED: `grep -c '"clear_cache"' client.py` returns 2 (Task 2 acceptance — one per backend)
- VERIFIED: `grep -c '"confirm": True' client.py` returns 6 (3 destructive ops × 2 backends — cancel_job, remove_folder, clear_cache)
- VERIFIED: `grep -c "streamablehttp_client" client.py` returns 25 (>=11 — Task 3 acceptance: at least one per HTTP wired method + query)
- VERIFIED: `grep -c "stdio_client" client.py` returns 25 (each stdio _async_* helper imports it)
- VERIFIED: `cd agent-brain-mcp && poetry run pytest tests/test_cli_backends_methods_wire.py tests/test_cli_backends_skeleton.py tests/test_cli_backends_query_wire.py` exits 0 (22 passed, 14 deselected, ~7s)
- VERIFIED: `cd agent-brain-mcp && poetry run pytest tests/test_cli_backends_methods_wire.py -m e2e_http` exits 0 (11 passed, 13 deselected, ~8s)
- VERIFIED: `cd agent-brain-mcp && poetry run mypy agent_brain_mcp/client.py` exits 0 (strict clean)
- VERIFIED: `task before-push` exits 0 (490 MCP tests + CLI/UDS/server suites all green; coverage 87%)
