# Phase 54: 9 remaining MCP tools — Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Bring the `agent-brain-mcp` tool surface from the v1 minimum (7 tools) to the full 16-tool design by adding the 9 deferred tools, all derived from existing FastAPI server routes with no new server endpoints:

1. **`explain_result`** — wraps existing `POST /query/` with `explain=true` to return per-result provenance and scoring breakdown (TOOL-01)
2. **`add_documents`** — wraps `POST /index/add` (TOOL-02)
3. **`inject_documents`** — wraps `POST /index/` with `injector_script` / `folder_metadata_file` (TOOL-03)
4. **`wait_for_job`** — server-side blocking poll over `GET /index/jobs/{id}` that emits MCP `notifications/progress` at least every 2s until terminal status, then returns the final job record (TOOL-04 — the only Phase 54 tool that depends on Phase 52 notification plumbing)
5. **`list_folders`** — wraps `GET /index/folders/` (TOOL-05)
6. **`remove_folder`** — wraps `DELETE /index/folders/` (TOOL-06)
7. **`cache_status`** — wraps `GET /index/cache/` (TOOL-07)
8. **`clear_cache`** — wraps `DELETE /index/cache/` (TOOL-08)
9. **`list_file_types`** — static list of FILE_TYPE_PRESETS exposed by the server (TOOL-09 — no HTTP roundtrip needed if presets duplicated MCP-side; one roundtrip if proxied)

Phase 54 stops at the MCP tool surface. Contract tests against the official MCP SDK (VAL-01) live in Phase 55. The progress-notification machinery (the `notifications/progress` send method, progress-token tracking) is **shared infrastructure built in Phase 52** — Phase 54 consumes it for `wait_for_job`.

</domain>

<decisions>
## Implementation Decisions

### A. Schema derivation from server routes (lockstep with HTTP)
- **Each tool's input/output Pydantic model is a hand-written MCP-facing model in `agent-brain-mcp/agent_brain_mcp/schemas.py`** — NOT a re-export of `agent_brain_server.models`. v1 already established this pattern (schemas.py header explicitly states: "v1 input/output models are deliberately defined here rather than reused from `agent_brain_server.models` — the server models include fields irrelevant to MCP callers"). Phase 54 continues that posture.
- **Schemas are minimal projections** of the HTTP request/response bodies — only fields useful to MCP callers. Example: `IndexFolderInput` in v1 exposes `folder_path`, `force`, `allow_external`, `include_code`, `chunk_size`, `chunk_overlap` — not the full `IndexRequest` (which has ~15 fields including `watch_mode`, `code_chunk_strategy`, etc.). New v2 tools follow same posture.
- **Field constraints (ge=, le=, Literal[...]) match server constraints 1:1.** Drift here causes silent client/server validation mismatch. Reviewers should compare side-by-side with the route's Pydantic model before merge.
- **`additionalProperties: false` is set on all input schemas** (already wired in `json_schema()` helper) — MCP clients pre-validate before send.

### B. Tool registration follows the v1 `TOOL_REGISTRY` pattern verbatim
- **One module per tool group under `agent_brain_mcp/tools/`** — `tools/explain.py`, `tools/inject.py`, `tools/folders.py`, `tools/cache.py`, `tools/file_types.py`, plus extending existing `tools/jobs.py` for `wait_for_job` and `tools/index.py` for `add_documents`.
- **Each handler signature:** `handle_<name>(client: ApiClient, args: <Input>) -> <Output>`. Sync handlers; the server's `call_tool` wraps each in `asyncio.to_thread` so blocking httpx calls don't freeze the stdio event loop (v1 plan §6.4 / §12.3 #12). **EXCEPTION: `wait_for_job` is async** — see decision E.
- **Each tool added to `TOOL_REGISTRY` dict** with `ToolSpec(name, description, handler, input_model, output_model, annotations)`. Annotations follow v1 conventions:
  - `readOnlyHint: True` for `explain_result`, `cache_status`, `list_folders`, `list_file_types`, `wait_for_job`
  - `destructiveHint: True` for `clear_cache`, `remove_folder` (both delete data)
  - `openWorldHint: True` for `add_documents`, `inject_documents` (mutate index state, results path-dependent)
- **`_summarize()` in `server.py` extended with one branch per new tool** — keeps text-content summary identical to v1 (e.g., `add_documents → job <id> (queued)`, `wait_for_job → <id>: succeeded (100%)`).

### C. New `ApiClient` methods cover every new route used
- New methods in `agent_brain_mcp/client.py`:
  - `add_documents(body, *, force)` → `POST /index/add?force=`
  - `inject_documents(body, *, force)` → `POST /index/` (same endpoint as `index_folder`; the `inject_*` variant just always sets `injector_script` and/or `folder_metadata_file` in body)
  - `cache_status()` → `GET /index/cache/`
  - `clear_cache()` → `DELETE /index/cache/`
  - `delete_folder(body)` → `DELETE /index/folders/` (note: `FolderDeleteRequest` is body, not query/path)
  - `query_with_explain(body)` → reuses existing `query(body)` with `explain=True` set in body
- **`list_folders()` already exists** in v1 client (used by the `corpus://folders` resource). Reused as-is for the new tool.
- **`list_file_types()` does NOT need an ApiClient method** — Phase 54 hardcodes the preset table in `agent_brain_mcp/tools/file_types.py` mirroring `agent-brain-cli/agent_brain_cli/commands/types.py:FILE_TYPE_PRESETS`. Rationale: CLI already duplicates it, server has no `GET /index/types` route, the table is ~25 lines of pure data. **DR-tracked:** if presets ever become dynamic (config-driven), revisit and add a server endpoint.

### D. `inject_documents` is `index_folder` with required injector fields
- **`InjectDocumentsInput`:**
  - `folder_path: str` (required)
  - `injector_script: str | None` — absolute path; at least one of `injector_script` or `folder_metadata_file` MUST be provided (Pydantic root validator)
  - `folder_metadata_file: str | None`
  - `dry_run: bool = False`
  - `force: bool = False`, `allow_external: bool = False`
  - `include_code: bool = True`, `chunk_size: int | None`, `chunk_overlap: int | None`
- **Pre-validation MCP-side:** if both `injector_script` and `folder_metadata_file` are None, raise `McpError(INVALID_PARAMS)` with message "At least one of injector_script or folder_metadata_file is required" — matches CLI's `inject_command` semantics. Don't ship the request and rely on a server 400; surface fast.
- **Server-side allowlist enforcement (issue #181)**: not enforced MCP-side. The 403 from the server's `assert_allowlisted` flows through `raise_for_status` and surfaces as a structured `McpError`. **Document this clearly in the tool description** so MCP clients know unallowlisted scripts will fail server-side with a useful hint.
- **Dry-run path:** when `dry_run=True`, the server returns a `job_id="dry_run"`, `status="completed"`, and a `message` containing the validation report. `InjectDocumentsOutput` carries the same shape — clients differentiate by checking `job_id == "dry_run"`.

### E. `wait_for_job` design (THE notification-emitting tool — depends on Phase 52)
- **Async handler signature:** `async def handle_wait_for_job(client: ApiClient, args: WaitForJobInput, *, notify: ProgressNotifier) -> WaitForJobOutput`. The `notify` callable is **injected by `server.call_tool`** when the tool spec is flagged as progress-emitting. This requires extending `ToolSpec` with an `emits_progress: bool = False` field and `server.call_tool` branching on it.
- **Poll cadence: 1 second** between `GET /index/jobs/{id}` calls. Spec requires ≤2s; 1s gives margin and matches the `job://` subscription cadence from Phase 52 (consistency wins over slightly fewer roundtrips).
- **Progress notification payload:** `{"progressToken": <token>, "progress": <0.0-1.0>, "total": 1.0, "message": "<server progress message>"}`. `progress` = `progress_percent / 100` from `GetJobOutput`. `progressToken` is the MCP-spec token attached to the `wait_for_job` request — handler doesn't generate it, it propagates from the client request meta.
- **Terminal states:** `succeeded`, `failed`, `cancelled`, `dry_run` (treats as completed). On terminal status, send one final `notifications/progress` with `progress=1.0`, then return the final job record as `WaitForJobOutput`.
- **Timeout:** `timeout_seconds: int | None = None` in input. If set and exceeded, return `WaitForJobOutput(status="timeout", ...)` with the last-known job state — do NOT raise. Rationale: MCP `notifications/cancelled` is the client's escape hatch; `timeout_seconds` is a polite soft cap.
- **`WaitForJobInput`:**
  - `job_id: str` (required)
  - `poll_interval_seconds: float = 1.0` (ge=0.5, le=2.0 — server-enforced upper bound so clients can't violate the ≤2s requirement by accident)
  - `timeout_seconds: int | None = None` (ge=1)
- **`WaitForJobOutput`:** same shape as `GetJobOutput` (job_id, status, progress_percent, message, started_at, completed_at) plus `final: bool = True` and `elapsed_seconds: float`.
- **Cancellation propagation:** if the MCP server receives `notifications/cancelled` for the request, the handler must propagate via `asyncio.CancelledError` and call `client.cancel_job(job_id)` in `finally:` so the underlying job is also cancelled (don't leak a runaway indexing job because the client gave up). Document this in the tool description.

### F. `explain_result` design (TOOL-01)
- **Input:** `ExplainResultInput` carries the **original query** plus the `chunk_id` of the result to explain — NOT a server-side result-id lookup. Rationale: the server doesn't persist search results; explanations are produced inline by the query pipeline. To get an explanation for a chunk, we re-execute the query with `explain=True` and filter to that chunk_id.
- **Schema:**
  - `query: str` (required — same query that produced the result)
  - `chunk_id: str` (required)
  - `mode: Literal["semantic", "bm25", "hybrid", "graph", "multi"] = "hybrid"` (must match original query mode for the explanation to match the original ranking)
  - `top_k: int = 50` (ge=1, le=200; bumped from search default of 10 so we have a high probability of finding the target chunk in the explained candidate pool — if it doesn't appear, return an error rather than synthesizing)
  - `alpha: float = 0.5`
- **Handler:** calls `client.query({...explain: True})` then post-filters results for `chunk_id == args.chunk_id`. If not found, raise `McpError(INVALID_PARAMS, "Chunk <id> not present in top-<top_k> results for this query/mode. Re-issue with a higher top_k or a closer query.")`.
- **Output `ExplainResultOutput`:** mirror `QueryResult.explanation` shape from `agent_brain_server/models/query.py:ResultExplanation` — `reason`, `matched_terms`, `fusion`, `graph_path`, `rerank_movement`, `graph_fallback` — plus the matched `text`, `source`, `score`, and `chunk_id` for context.
- **NOT calling a new `GET /query/explain` endpoint** — Phase 50/51 did NOT add one. If a future phase adds chunk-resolution by id (it does — Phase 50 ships `GET /query/chunk/{id}`), `explain_result` MAY be refactored to call query+filter on the chunk's text. Defer; Phase 54 ships the query+filter approach.

### G. Error mapping is uniform via existing `errors.raise_for_status`
- **All new tools share the v1 error path:** `ApiClient._request` calls `errors.raise_for_status(response)`, which converts HTTP 4xx/5xx into `McpError` with structured `ErrorData`. No per-tool error mapping needed.
- **403 from injector allowlist** (issue #181) surfaces as `McpError(code=INVALID_PARAMS, message="<server detail>")`. Tool description for `inject_documents` MUST mention this so MCP clients can surface the user-facing hint.
- **409 from `remove_folder` when an indexing job is active** for that folder (FOLD-07): surfaces as `McpError(code=INVALID_PARAMS, message="<server detail>")`. Tool description mentions the conflict condition.
- **503 from `cache_status` / `clear_cache` when cache is not initialised:** same generic mapping.
- **No new error codes added.** MCP SDK doesn't expose application-specific codes well in v1 phase; we stay with `INVALID_PARAMS` + structured `data` for now (matches v1).

### H. `list_file_types` returns the SAME table the CLI ships
- **Output `ListFileTypesOutput`:** `{"presets": {"python": ["*.py", "*.pyi", "*.pyw"], "docs": [...], ...}, "preset_count": int, "extension_count": int}`. Matches `agent-brain types list --json` output shape so MCP clients see the same data as CLI users.
- **Source of truth:** copy the FILE_TYPE_PRESETS dict from `agent-brain-cli/agent_brain_cli/commands/types.py` into `agent-brain-mcp/agent_brain_mcp/tools/file_types.py`. **This is the SECOND copy** (CLI has one, MCP would have one). Risk: drift if server adds a preset. Mitigation: Phase 55 contract test parameterizes against both copies and asserts equality. Deferred ideal: a `GET /index/types` endpoint hosting the canonical list (out of scope for v2).

### Claude's Discretion
- Whether `wait_for_job`'s `poll_interval_seconds` upper bound is 2.0 (matches spec) or stricter (1.5 for safety margin)
- Whether to add an `annotations: dict[str, str] | None` field on `ExplainResultInput` for future LangExtract-driven explanation tuning (recommend: no, YAGNI)
- Exact tool description wording — match v1's conversational style (e.g., "Search indexed documents using semantic, BM25, hybrid, graph, or multi-stage retrieval.")
- Whether to bundle all 9 tools into a single PR or split (3 PRs feels natural: explain+inject, wait+folders, cache+types) — planner decides based on review surface
- Whether `inject_documents`'s `injector_script` field accepts only absolute paths or also expands `~` (recommend: expand `~` and call `.resolve()`, matching CLI inject command)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### MCP design lineage
- `docs/plans/2026-05-28-mcp-uds-transport-design.md` — v1 master design; §15.1 lists the 9 deferred tools by name and notes `wait_for_job` is the only one needing notification plumbing. Phase 54 implementations should match the description style used in §6.2.
- `docs/roadmaps/mcp/v2-subscriptions-and-resources.md` — scope contract; defines DoD for `wait_for_job` (must emit `notifications/progress` every ≤2s) and the 9-tool inventory.
- `.planning/phases/50-server-endpoint-prep-v2-design-doc/50-CONTEXT.md` — Phase 50's decisions on schema-derivation posture, error mapping, sandbox stance. Carry forward: "no new server endpoints" for Phase 54 (50 already shipped the only new endpoints v2 needs).

### Existing MCP v1 patterns (to extend, not rewrite)
- `agent-brain-mcp/agent_brain_mcp/tools/__init__.py` — `TOOL_REGISTRY` pattern; Phase 54 extends this dict, does NOT replace it.
- `agent-brain-mcp/agent_brain_mcp/tools/jobs.py` — v1 `get_job`, `list_jobs`, `cancel_job` handlers. `wait_for_job` lives next to them (or in a new `wait.py` module — planner's call). Cursor encoding pattern in `_decode_cursor` is reusable for any future paginated tools.
- `agent-brain-mcp/agent_brain_mcp/tools/index.py` — v1 `index_folder` handler. `add_documents` and `inject_documents` follow this style exactly.
- `agent-brain-mcp/agent_brain_mcp/schemas.py` — v1 input/output models. New schemas go here. Header note ("v1 input/output models are deliberately defined here") is the binding rationale for hand-written schemas in Phase 54.
- `agent-brain-mcp/agent_brain_mcp/client.py` — `ApiClient` thin httpx wrapper; new methods go here (one per route). Lines 80-125 already show the pattern (one method per endpoint).
- `agent-brain-mcp/agent_brain_mcp/server.py` — `build_server()` wires the registry. `call_tool` (lines 105-133) is what needs the `emits_progress` branch for `wait_for_job`. `_summarize()` (lines 213-245) needs one branch per new tool.
- `agent-brain-mcp/agent_brain_mcp/errors.py` — `raise_for_status`, `INVALID_PARAMS`, `raise_backend_unavailable`. New tools reuse — no new error functions needed.

### Server routes Phase 54 wraps (1:1 schema matching)
- `agent-brain-server/agent_brain_server/api/routers/index.py` — `POST /index/` (lines 158-402), `POST /index/add` (lines 405-519), `DELETE /index/` (lines 522-566). `add_documents` mirrors `POST /index/add`. `inject_documents` mirrors `POST /index/` with required injector fields.
- `agent-brain-server/agent_brain_server/api/routers/folders.py` — `GET /index/folders/` (lines 27-58), `DELETE /index/folders/` (lines 61-156). `list_folders` and `remove_folder` are 1:1 wraps. Note the 409-on-active-job behavior for remove (lines 100-114) — surfaces in MCP via `errors.raise_for_status`.
- `agent-brain-server/agent_brain_server/api/routers/cache.py` — `GET /index/cache/` and `DELETE /index/cache/`. `cache_status` and `clear_cache` are trivial wraps; 503-when-uninitialised behavior (lines 44-48, 71-75) flows through.
- `agent-brain-server/agent_brain_server/api/routers/query.py` — `POST /query/`; `explain=true` flag (lines 90-93) is what `explain_result` consumes.

### Server response models (mirror MCP-side)
- `agent-brain-server/agent_brain_server/models/query.py:ResultExplanation` (lines 153-208) — exact shape `ExplainResultOutput` mirrors. The six fields (`reason`, `matched_terms`, `fusion`, `graph_path`, `rerank_movement`, `graph_fallback`) carry over verbatim.
- `agent-brain-server/agent_brain_server/models/folders.py` — `FolderInfo`, `FolderListResponse`, `FolderDeleteRequest`, `FolderDeleteResponse`. `ListFoldersOutput` and `RemoveFolderOutput` mirror.
- `agent-brain-server/agent_brain_server/models/job.py` — `JobRecord` shape; `WaitForJobOutput` extends `GetJobOutput` with `final` and `elapsed_seconds`.

### CLI parity references (for static data)
- `agent-brain-cli/agent_brain_cli/commands/types.py` — `FILE_TYPE_PRESETS` dict (lines 19-90). Phase 54's `list_file_types` tool ships an identical dict (decision H). Phase 55 contract test asserts equality.
- `agent-brain-cli/agent_brain_cli/commands/inject.py` — CLI `inject` command. Tool description for `inject_documents` should match the CLI's "At least one of --script or --folder-metadata must be provided" wording so MCP and CLI error messages align (line 138-141 in inject.py).

### MCP protocol (external)
- MCP spec — `notifications/progress` payload shape (`progressToken`, `progress`, `total`, optional `message`). Phase 54 design doc updates (within the Phase 50 v2 doc) must cite the spec version. Phase 52 builds the send-notification primitive; Phase 54 consumes it.

### Existing requirements
- `.planning/REQUIREMENTS.md` — TOOL-01 through TOOL-09 (lines 37-45). All 9 land in Phase 54.
- `.planning/ROADMAP.md` Phase 54 (lines 105-116) — phase boundaries and 5 success criteria.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`TOOL_REGISTRY` dict pattern** (`tools/__init__.py:76`) — append-only extension. Phase 54 adds 9 entries; v1's 7 entries stay untouched.
- **`ApiClient` thin wrapper** (`client.py`) — already has `list_folders()` (line 123), `index_folder()` (line 100), `get_job()` (line 114), `cancel_job()` (line 120), `query()` (line 94). 5 new methods needed; ~25 LOC total.
- **`json_schema()` helper** (`schemas.py:21`) — auto-sets `additionalProperties: false` and converts Pydantic to JSON Schema. New schemas just need the BaseModel; helper handles MCP-spec compliance.
- **`_summarize()` switch in `server.py`** (`server.py:213`) — one if-branch per tool generates the human-readable text content. Phase 54 adds 9 branches.
- **`errors.raise_for_status`** — uniform HTTP→McpError mapping. No per-tool error handling needed for new tools (except the MCP-spec progress flow in `wait_for_job`).
- **`_decode_cursor` / `_encode_cursor` in `tools/jobs.py`** — if any new tool needs pagination, reuse this; otherwise irrelevant for Phase 54 (none of the 9 paginate).

### Established Patterns
- **Hand-written MCP-facing models** (schemas.py docstring) — never reuse `agent_brain_server.models`. Phase 54 schemas live in `schemas.py` and are minimal projections.
- **Sync handlers + `asyncio.to_thread`** (`server.py:130`) — handlers are sync; the server wraps in `to_thread`. `wait_for_job` is the **first async handler** in the codebase — requires `ToolSpec.emits_progress` flag + branched dispatch in `call_tool`. New pattern; document it.
- **`Literal[True]` for destructive confirms** (`schemas.py:CancelJobInput.confirm`) — Pydantic raises ValidationError before the handler runs. `clear_cache` and `remove_folder` may want the same `confirm: Literal[True]` guard. **Recommend: add it** — both are irreversible.
- **One module per logical group under `tools/`** — `tools/jobs.py` holds 3 job tools, `tools/meta.py` holds 2 meta tools. Phase 54 should:
  - Add `tools/wait.py` for `wait_for_job` (async handler is special-cased anyway; isolating it is cleanest)
  - Add `tools/folders.py` for `list_folders` + `remove_folder`
  - Add `tools/cache.py` for `cache_status` + `clear_cache`
  - Add `tools/file_types.py` for `list_file_types`
  - Add `handle_explain_result` to a new `tools/explain.py`
  - Add `handle_add_documents` to existing `tools/index.py`
  - Add `handle_inject_documents` to a new `tools/inject.py` (or extend `tools/index.py`)

### Integration Points
- **`server.py:build_server` reads `TOOL_REGISTRY`** — adding to the dict is sufficient for `tools/list`. No additional wiring.
- **`server.py:call_tool` needs the `emits_progress` branch** — when `spec.emits_progress`, invoke `await spec.handler(api, args, notify=notify)` instead of `await asyncio.to_thread(spec.handler, api, args)`. **The `notify` injection point ships in Phase 52** (subscriptions). Phase 54 depends on that work.
- **Tool registration in `tools/__init__.py`** — extend imports + dict literal; `__all__` already exports the right names.

### Greenfield (no existing pattern)
- **Progress-notification-emitting tools.** Phase 52 ships the `notifications/progress` send primitive; Phase 54 is the first **consumer**. The `notify: ProgressNotifier` parameter shape comes from Phase 52's design.
- **Async tool handlers.** All v1 handlers are sync. `wait_for_job` introduces the async pattern. Document it explicitly in `tools/__init__.py` docstring so future tool authors don't miss it.
- **Confirmation-guarded destructive tools beyond `cancel_job`.** Decision: extend the `Literal[True]` confirm pattern to `clear_cache` and `remove_folder`. New: explicit safety check pattern recommended.

</code_context>

<specifics>
## Specific Ideas

- **`wait_for_job`'s `notify` injection contract is Phase 52's deliverable** — Phase 54 cannot start `wait_for_job` until Phase 52's `ProgressNotifier` shape is decided. Phases 54-other-8-tools can proceed independently of Phase 52, but `wait_for_job` blocks. Planner should split Phase 54 into a "8 tools (Phase 52-independent)" plan and a "`wait_for_job` (Phase 52-dependent)" plan so the 8 can land first.
- **The injector allowlist 403 (issue #181)** is a recent (May 2026) security hardening. `inject_documents`'s tool description MUST mention "scripts must be allowlisted server-side" so MCP clients aren't surprised — match the CLI's error UX in `inject.py:269-278`.
- **The `allow_external` query parameter was removed from `POST /index/add` in issue #180** (security; server-side setting only). `add_documents`'s schema MUST NOT expose `allow_external` as a parameter — it's a no-op now. Existing `index_folder` tool (v1) still has it; that's a v1 bug to track separately, NOT a Phase 54 fix.
- **`list_file_types` static-data duplication risk:** Phase 55's contract test should assert `set(MCP_PRESETS.keys()) == set(CLI_PRESETS.keys())` AND `MCP_PRESETS == CLI_PRESETS`. If divergent, fail the build. This is the lightweight enforcement for decision H.
- **`explain_result` re-runs the query** — it's not free. Tool description should warn: "Re-executes the original query with `explain=true`; not suitable for high-frequency calls. Use `search_documents(..., explain=true)` directly for known-bulk explanation needs." Frame it as a developer-tool, not a hot-path.
- **The `_summarize` text content** is what shows up in MCP clients' chat UI. Match v1's terse style (one line per tool result). For `wait_for_job`: `wait_for_job → <job_id>: <status> (<progress>%) after <elapsed>s`.

</specifics>

<deferred>
## Deferred Ideas

- **`GET /index/types` server endpoint** — would eliminate the FILE_TYPE_PRESETS duplication (CLI + MCP). Out of scope for v2; revisit in v3 if dynamic presets land.
- **`POST /query/explain` server endpoint with chunk_id lookup** — would let `explain_result` skip the re-query. Phase 50 ships `GET /query/chunk/{id}`; a future endpoint could combine chunk lookup + explanation generation. Defer until measurement shows explain_result is hot.
- **MCP progress notifications for `add_documents` / `inject_documents`** — currently these return `{job_id, status}` immediately. Clients call `wait_for_job` separately for progress. A future enhancement could let `add_documents` itself emit progress. Defer; explicit separation is cleaner for v2.
- **Tool-level rate limiting** — `clear_cache` and `remove_folder` are destructive; in a multi-tenant or shared-instance scenario, rate limiting could matter. Out of scope for v2 (local-first, single-user); revisit alongside #179 auth work.
- **`list_jobs` pagination cursor exposed via `wait_for_job` for "wait for any of these"** — bulk-wait. Out of scope; v2 single-job is sufficient.
- **`explain_result` for graph-only results without re-query** — would need the server to retain `(query, mode) → results` for some TTL. Architectural shift; defer to v3 if framework adapters need it.
- **`abort_all_jobs` mass-cancel tool** — useful for testing/development. Not in original 16-tool design; defer.
- **Confirm prompts ("are you sure?") on `clear_cache` / `remove_folder`** — v2 uses Pydantic `Literal[True]` guard (decision F via §Greenfield). A richer MCP `elicitation` prompt is out of scope for v2 (spec says no elicitation/sampling in v2).
- **`list_file_types` flat alternative output** (`{"presets": [...names], "extensions": [...exts]}`) — current dict shape is richer; flat lists could come later if MCP clients want them.

</deferred>

---

*Phase: 54-remaining-mcp-tools*
*Context gathered: 2026-06-02*
