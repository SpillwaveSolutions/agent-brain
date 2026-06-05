# Plan 01: Parameterized URI dispatcher + `job://` handler

**Phase:** 51 — URI schemes + templates
**Requirements covered:** URI-03
**Depends on:** none — first plan in phase (Phase 50 must have shipped, but no new Phase 50 outputs are consumed in this plan; only the existing `GET /index/jobs/{job_id}` endpoint is touched)
**Parallel-safe with:** none (foundational — Plans 02 and 03 depend on this)
**Status:** Not started

## Goal

Establish the parameterized URI dispatcher infrastructure inside `agent_brain_mcp` so that `resources/read` can route by URI scheme as well as by exact URI string, and land the simplest of the four deferred schemes (`job://<job_id>`) as the exemplar that proves the dispatcher works. This plan does not touch the server, does not add new ApiClient methods (reuses existing `get_job`), and does not change MCP capabilities — it only widens the read-resource dispatch surface and proves URI-03.

Output of this plan: an MCP client calling `resources/read` with `job://<existing-job-id>` receives the same JSON body as `GET /index/jobs/<job-id>`, while every existing `corpus://*` read continues to work unchanged.

## Acceptance Criteria

- [ ] `agent_brain_mcp/resources/parameterized.py` exists with a `ParsedURI` dataclass (fields: `scheme`, `chunk_id`, `entity_type`, `entity_id`, `job_id`, `path`; only the scheme-relevant fields populated) and a `PARAMETERIZED_HANDLERS` registry keyed by scheme name.
- [ ] `parse_uri(uri: str) -> ParsedURI | None` raises `McpError(INVALID_PARAMS)` with structured `data` (`{"uri": <input>, "reason": "missing_job_id" | "missing_chunk_id" | "missing_type" | "missing_id" | "missing_path"}`) when a recognized scheme is present but required segments are missing; returns `None` when the scheme is not in the parameterized set (so the caller can fall through to `RESOURCE_REGISTRY`).
- [ ] `agent_brain_mcp/server.py`'s `read_resource` handler dispatches: scheme-prefix lookup first (for `chunk`, `graph-entity`, `job`, `file`), then the existing `RESOURCE_REGISTRY.get(uri_str)` path for `corpus://*`, with the existing `INVALID_PARAMS` "Unknown resource" error preserved as the final fallback.
- [ ] An MCP client calling `resources/read` with `job://<existing-job-id>` receives a JSON payload byte-identical to `GET /index/jobs/<job-id>`.
- [ ] An MCP client calling `resources/read` with `job://` (no id) receives `McpError(INVALID_PARAMS)` with `data: {"uri": "job://", "reason": "missing_job_id"}`.
- [ ] An MCP client calling `resources/read` with `job://nonexistent-uuid` receives `McpError(INVALID_PARAMS)` (404 → `INVALID_PARAMS` via existing `errors.raise_for_status`) with `data: {"scheme": "job", "job_id": "nonexistent-uuid", "httpStatus": 404, "cause": "..."}`.
- [ ] All five existing `corpus://*` resources continue to be readable via `resources/read` (no regression).
- [ ] All five existing `corpus://*` resources continue to appear in `resources/list` (no change to `resources/list` shape — that's Plan 04's `resources/templates/list` work).
- [ ] Server capability advertisement is unchanged (`resources.subscribe = False`, `resources.listChanged = False`).
- [ ] `task mcp:test`, `task mcp:contract`, `task check:layering`, `task before-push`, and `task pr-qa-gate` all exit 0.

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-mcp/agent_brain_mcp/resources/parameterized.py` | create | `ParsedURI` dataclass, `parse_uri()`, `PARAMETERIZED_HANDLERS: dict[str, Callable]` with only the `"job"` entry populated in this plan. ~120 LOC. |
| `agent-brain-mcp/agent_brain_mcp/resources/__init__.py` | modify | Re-export `parse_uri`, `PARAMETERIZED_HANDLERS`, `ParsedURI` alongside existing `RESOURCE_REGISTRY` re-exports. ~5 LOC. |
| `agent-brain-mcp/agent_brain_mcp/server.py` | modify | Insert scheme-prefix lookup in `read_resource` handler (around current line 147). Call `parse_uri(uri_str)`; if non-None, dispatch through `PARAMETERIZED_HANDLERS[parsed.scheme]`; else fall through to `RESOURCE_REGISTRY.get(uri_str)`. Preserve `asyncio.to_thread` pattern for the handler invocation. ~25 LOC delta. |
| `agent-brain-mcp/tests/test_resources_read_parameterized.py` | create | Mirrors `tests/test_resources_read.py`. Parameterized across schemes; only `job://` cases populated in this plan. Covers: success, missing id, 404 from backend, malformed URI. ~110 LOC. |
| `agent-brain-mcp/tests/conftest.py` | modify | Extend `fake_httpx_client` URL routing to handle `GET /index/jobs/<id>` stubs (may already partially exist for v1 `get_job` tool tests — verify and reuse). ~15 LOC delta. |

**Estimated total: ~275 LOC (including tests).**

## Implementation Steps

1. **Read `agent-brain-mcp/agent_brain_mcp/resources/corpus.py`** to confirm the existing `ResourceSpec` dataclass shape and `RESOURCE_REGISTRY` structure. The parameterized handler shape mirrors it with an added `params: ParsedURI` arg.

2. **Create `agent-brain-mcp/agent_brain_mcp/resources/parameterized.py`:**
   - `@dataclass(frozen=True) ParsedURI` with `scheme: str`, optional fields per scheme (`chunk_id: str | None`, `entity_type: str | None`, `entity_id: str | None`, `job_id: str | None`, `path: str | None`).
   - `parse_uri(uri: str) -> ParsedURI | None` — uses `urllib.parse.urlsplit`. Returns `None` if scheme not in `{"chunk", "graph-entity", "job", "file"}`. For recognized schemes, validates the required segments and raises `McpError(INVALID_PARAMS)` with the structured `data` blob from CONTEXT.md decision C if validation fails. For `job://<id>`, the id is `urlsplit(...).netloc` after `urlsplit` (since `job` has no `//` authority by convention — verify behavior in test).
   - `PARAMETERIZED_HANDLERS: dict[str, Callable[[ApiClient, ParsedURI], Awaitable[str]]]` initialized with only `"job": handle_job_uri` populated. Reserve keys `"chunk"`, `"graph-entity"`, `"file"` with `NotImplementedError`-raising placeholders so Plans 02 and 03 just swap the implementation.
   - `async def handle_job_uri(client: ApiClient, params: ParsedURI) -> str`:
     - Calls `await asyncio.to_thread(client.get_job, params.job_id)`.
     - Returns `json.dumps(response, indent=2, default=str)` matching the v1 corpus.py output shape.
     - HTTP errors propagate through the existing `errors.raise_for_status` already inside `client.get_job` — no extra mapping here.

3. **Modify `agent-brain-mcp/agent_brain_mcp/server.py` `read_resource` (around line 147):**
   - Before the existing `spec = RESOURCE_REGISTRY.get(uri_str)` line, parse the URI: `parsed = parse_uri(uri_str)`.
   - If `parsed is not None`: dispatch to `PARAMETERIZED_HANDLERS[parsed.scheme]` and return `[ReadResourceContents(content=result, mime_type="application/json")]`. Run via `await PARAMETERIZED_HANDLERS[parsed.scheme](self._api_client, parsed)` (no `to_thread` needed at this layer — the handler does its own `to_thread` for the sync httpx call).
   - If `parsed is None`: fall through to existing `RESOURCE_REGISTRY.get(uri_str)` logic unchanged.
   - Preserve the existing `Unknown resource: <uri>` `INVALID_PARAMS` error as the final fallback for unrecognized URIs.

4. **Modify `agent-brain-mcp/agent_brain_mcp/resources/__init__.py`** to re-export `parse_uri`, `PARAMETERIZED_HANDLERS`, `ParsedURI`.

5. **Extend `tests/conftest.py`'s `fake_httpx_client`** to route `GET /index/jobs/<id>` to a stub that returns a fixture `JobDetailResponse` (status `running`, sample fields). For 404 case, return a 404 with a matching error body.

6. **Create `tests/test_resources_read_parameterized.py`:**
   - `async def test_read_job_uri_success(fake_httpx_client)` — assert the read payload matches the stub `JobDetailResponse`.
   - `async def test_read_job_uri_missing_id()` — assert `McpError(INVALID_PARAMS)` raised with `data["reason"] == "missing_job_id"`.
   - `async def test_read_job_uri_404(fake_httpx_client)` — fake client returns 404; assert `McpError(INVALID_PARAMS)` with `data["scheme"] == "job"` and `data["job_id"] == "nonexistent-uuid"`.
   - `async def test_read_corpus_uri_still_works(fake_httpx_client)` — regression: assert all 5 `corpus://*` URIs continue to read correctly through the unchanged fallback path.
   - `async def test_read_unknown_scheme_falls_through(fake_httpx_client)` — `resources/read` with `mystery://abc` returns `Unknown resource:` `INVALID_PARAMS` (existing behavior, fall-through path).

7. **Run the gates:**
   ```bash
   cd agent-brain-mcp && poetry run pytest -v
   task mcp:test
   task mcp:contract
   task check:layering
   task before-push
   task pr-qa-gate
   ```

## Verification

- `poetry run pytest agent-brain-mcp/tests/test_resources_read_parameterized.py -v` — all `job://` cases pass.
- `poetry run pytest agent-brain-mcp/tests/test_resources_read.py -v` — existing `corpus://*` tests pass unchanged (regression check).
- `poetry run pytest agent-brain-mcp/tests/test_resources_list.py -v` — `resources/list` still returns exactly 5 entries.
- `poetry run pytest agent-brain-mcp/tests/test_initialize.py -v` — capability negotiation unchanged.
- Manual smoke (against a running server with a real job):
  ```bash
  agent-brain start --uds
  agent-brain index ./docs --wait
  # capture a job id
  JOB_ID=$(agent-brain jobs --json | jq -r '.[0].job_id')
  echo "$JOB_ID"
  # craft a JSON-RPC tape that reads job://$JOB_ID via MCP
  scripts/mcp-read-job-uri.sh "$JOB_ID" | agent-brain-mcp --backend uds | jq -e '.result.contents[0].uri == "job://'$JOB_ID'"'
  agent-brain stop
  ```
- All five quality gates (`task mcp:test`, `task mcp:contract`, `task check:layering`, `task before-push`, `task pr-qa-gate`) exit 0.

## Risk Notes

- **Risk:** `urlsplit("job://abc")` parses `abc` as `netloc` (URL authority), but `urlsplit("job://abc/def")` parses `abc` as netloc and `/def` as path. For `job://`, only the netloc segment carries meaning. Verify the parser handles both `job://abc` and `job://abc/` (trailing slash) the same way. Add explicit tests for both forms.
- **Risk:** Reordering the dispatch in `read_resource` could regress the `corpus://*` path if the new code path accidentally matches `corpus` as a scheme. Mitigation: `parse_uri` explicitly returns `None` for any scheme not in the four-scheme allow-list, including `corpus`.
- **Risk:** `INVALID_PARAMS` is used for both "malformed URI" and "404 backend response." Both are valid MCP semantics ("the caller asked for something that doesn't exist"), but the `data` payload shape differs (one has `reason`, the other has `httpStatus + scheme + scheme-specific id`). Document this in the parameterized.py docstring so reviewers understand the two shapes are intentional.
- **Risk:** Adding `parse_uri` raising inside a non-handler path (called before dispatch) means an unhandled exception could escape `read_resource`. Mitigation: wrap the parse call in a try/except so `McpError` propagates cleanly through the MCP framework's error-response path; any other exception becomes `INTERNAL_ERROR` via the existing v1 error wrapper.
- **Quality gate:** Per CLAUDE.md the project's #1 rule is "NEVER PUSH WITHOUT TESTING." All five gates must exit 0 before this plan is considered done.

---
*Plan 01 of Phase 51*
