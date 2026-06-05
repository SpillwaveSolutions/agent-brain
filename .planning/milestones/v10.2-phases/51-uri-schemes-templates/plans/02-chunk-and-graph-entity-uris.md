# Plan 02: `chunk://` and `graph-entity://` handlers + ApiClient extensions

**Phase:** 51 — URI schemes + templates
**Requirements covered:** URI-01, URI-02
**Depends on:** Plan 01 (parameterized dispatcher infrastructure, `ParsedURI` dataclass, scheme-prefix routing in `read_resource`)
**Parallel-safe with:** Plan 03 (`file://` handler — touches disjoint files; `parameterized.py` modifications are append-only per scheme)
**Status:** Not started

## Goal

Land the two MCP URI schemes that ride Phase 50's new HTTP endpoints: `chunk://<chunk_id>` (URI-01, backed by `GET /query/chunk/{id}`) and `graph-entity://<type>/<id>` (URI-02, backed by `GET /graph/entity/{type}/{id}`). Both schemes share the same pattern established by Plan 01: parse URI → call ApiClient → JSON-encode response → return via `ReadResourceContents`. Extends `agent_brain_mcp/client.py` with two new methods (`get_chunk`, `get_graph_entity`) that mirror the existing `get_job` pattern.

Output of this plan: an MCP client can call `resources/read` with `chunk://<chunk_id>` or `graph-entity://<type>/<id>` and receive the chunk content + metadata, or the entity payload, as JSON.

## Acceptance Criteria

- [ ] `agent_brain_mcp/client.py` `ApiClient` has new method `get_chunk(chunk_id: str) -> dict[str, Any]` calling `GET /query/chunk/{chunk_id}` and routing the response through `errors.raise_for_status` (existing pattern from `get_job`).
- [ ] `agent_brain_mcp/client.py` `ApiClient` has new method `get_graph_entity(entity_type: str, entity_id: str) -> dict[str, Any]` calling `GET /graph/entity/{entity_type}/{entity_id}` with the same error-mapping path.
- [ ] `agent_brain_mcp/resources/parameterized.py` `PARAMETERIZED_HANDLERS["chunk"]` is implemented as `handle_chunk_uri` and parses `{chunk_id}` from `chunk://<id>` URIs.
- [ ] `agent_brain_mcp/resources/parameterized.py` `PARAMETERIZED_HANDLERS["graph-entity"]` is implemented as `handle_graph_entity_uri` and parses `{type}/{id}` from `graph-entity://<type>/<id>` URIs (path segment 0 = type, segment 1 = id).
- [ ] An MCP client calling `resources/read` with `chunk://<existing-chunk-id>` receives a JSON payload matching the `GET /query/chunk/{id}` response (chunk content + metadata, no embedding per Phase 50 decision C).
- [ ] An MCP client calling `resources/read` with `chunk://` (no id) receives `McpError(INVALID_PARAMS)` with `data["reason"] == "missing_chunk_id"`.
- [ ] An MCP client calling `resources/read` with `chunk://nonexistent` receives `McpError(INVALID_PARAMS)` with `data: {"scheme": "chunk", "chunk_id": "nonexistent", "httpStatus": 404, "cause": "..."}`.
- [ ] An MCP client calling `resources/read` with `graph-entity://Function/foo` receives the entity payload from the `GET /graph/entity/Function/foo` response.
- [ ] An MCP client calling `resources/read` with `graph-entity://Function` (missing id) receives `McpError(INVALID_PARAMS)` with `data["reason"] == "missing_id"`.
- [ ] An MCP client calling `resources/read` with `graph-entity://Function/foo` while GraphRAG is disabled receives `McpError(SERVICE_INDEXING)` with `data: {"scheme": "graph-entity", "reason": "graphrag_disabled", ...}` — Phase 50's 503 hint is passed through verbatim.
- [ ] No regression: all Plan 01 tests (`job://`, `corpus://*`) continue to pass.
- [ ] No `agent_brain_mcp → agent_brain_cli` import introduced (layering contract).
- [ ] `task mcp:test`, `task mcp:contract`, `task check:layering`, `task before-push`, `task pr-qa-gate` all exit 0.

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-mcp/agent_brain_mcp/client.py` | modify | Add `get_chunk(chunk_id)` and `get_graph_entity(entity_type, entity_id)` methods. Mirror the existing `get_job` pattern (lines ~80-124). Both go through `self._get(...)` → `errors.raise_for_status`. ~40 LOC delta. |
| `agent-brain-mcp/agent_brain_mcp/resources/parameterized.py` | modify | Replace `PARAMETERIZED_HANDLERS["chunk"]` and `["graph-entity"]` `NotImplementedError` placeholders with real handlers. Extend `parse_uri` if needed for `graph-entity` two-segment parsing (the path-split logic). ~80 LOC delta. |
| `agent-brain-mcp/tests/test_resources_read_parameterized.py` | modify | Add parametrized test cases for `chunk://` and `graph-entity://` mirroring the existing `job://` cases (success, missing id, 404, malformed). For `graph-entity`, add a 503 case asserting `SERVICE_INDEXING` with the `graphrag_disabled` hint. ~120 LOC delta. |
| `agent-brain-mcp/tests/conftest.py` | modify | Extend `fake_httpx_client` URL routing for `GET /query/chunk/<id>` (200 success + 404 stub) and `GET /graph/entity/<type>/<id>` (200 + 404 + 503 stubs). ~25 LOC delta. |

**Estimated total: ~265 LOC (including tests).**

## Implementation Steps

1. **Read `agent-brain-mcp/agent_brain_mcp/client.py`** lines 80-124 to confirm the existing `get_job` pattern (sync httpx, `self._get`, error mapping). Both new methods follow the same shape verbatim.

2. **Extend `ApiClient`:**
   ```python
   def get_chunk(self, chunk_id: str) -> dict[str, Any]:
       """GET /query/chunk/{chunk_id} — returns chunk content + metadata."""
       return self._get(f"/query/chunk/{chunk_id}")

   def get_graph_entity(self, entity_type: str, entity_id: str) -> dict[str, Any]:
       """GET /graph/entity/{type}/{id} — returns entity payload from GraphRAG store."""
       return self._get(f"/graph/entity/{entity_type}/{entity_id}")
   ```
   Both methods rely on `_get` running through `errors.raise_for_status` (existing). The 404 → `INVALID_PARAMS` and 503 → `SERVICE_INDEXING` mappings are already wired.

3. **Extend `parse_uri` in `parameterized.py`:**
   - For `chunk://<id>`: `chunk_id = urlsplit(uri).netloc`. If empty, raise `INVALID_PARAMS` with `data["reason"] = "missing_chunk_id"`.
   - For `graph-entity://<type>/<id>`: `parsed = urlsplit(uri)`. Treat `parsed.netloc` as `entity_type` and `parsed.path.lstrip("/")` as `entity_id`. Validate both: missing type → `data["reason"] = "missing_type"`; missing id → `data["reason"] = "missing_id"`.
   - Edge case: `graph-entity://Function/` (trailing slash, empty id) — same as missing id.
   - Edge case: `graph-entity://Function/foo/bar` (extra segments) — accept; treat `foo/bar` as the full id (entity ids can contain slashes per Phase 50 decision B). Document the choice in the parser docstring; cross-check with Phase 50 decision B for the canonical id shape.

4. **Implement handlers in `parameterized.py`:**
   ```python
   async def handle_chunk_uri(client: ApiClient, params: ParsedURI) -> str:
       data = await asyncio.to_thread(client.get_chunk, params.chunk_id)
       return json.dumps(data, indent=2, default=str)

   async def handle_graph_entity_uri(client: ApiClient, params: ParsedURI) -> str:
       data = await asyncio.to_thread(
           client.get_graph_entity, params.entity_type, params.entity_id
       )
       return json.dumps(data, indent=2, default=str)
   ```
   Replace the `NotImplementedError` placeholders in `PARAMETERIZED_HANDLERS`.

5. **Wrap per-scheme error enrichment.** When `_get` raises `McpError`, the existing `errors.raise_for_status` already populates `data["httpStatus"]` and `data["cause"]`. The handlers add `data["scheme"]` and the scheme-specific id field before re-raising. This is best done by catching `McpError`, augmenting `data`, and re-raising:
   ```python
   try:
       data = await asyncio.to_thread(client.get_chunk, params.chunk_id)
   except McpError as exc:
       exc.error.data = {**(exc.error.data or {}), "scheme": "chunk", "chunk_id": params.chunk_id}
       raise
   ```
   Verify the `McpError.error.data` mutation pattern matches what v1's error tests assert. If not, build a new `McpError` instance with merged `data`.

6. **Extend `tests/conftest.py`'s `fake_httpx_client` URL map:**
   - `GET /query/chunk/<id>` → 200 with stub chunk payload; `GET /query/chunk/nonexistent` → 404 with `{"detail": "chunk not found"}` body.
   - `GET /graph/entity/<type>/<id>` → 200 with stub entity payload; `GET /graph/entity/Function/missing` → 404; `GET /graph/entity/<*>/<*>` → 503 with `{"detail": "GraphRAG disabled — set graphrag.store_type to simple or kuzu and re-index"}` for the disabled-store fixture.

7. **Add test cases to `test_resources_read_parameterized.py`:**
   - `test_read_chunk_uri_success` — assert payload matches stub.
   - `test_read_chunk_uri_missing_id` — assert `INVALID_PARAMS` with `data["reason"] == "missing_chunk_id"`.
   - `test_read_chunk_uri_404` — assert `INVALID_PARAMS` with `data["scheme"] == "chunk"`, `data["chunk_id"]`, `data["httpStatus"] == 404`.
   - `test_read_graph_entity_uri_success` — assert payload matches stub for `graph-entity://Function/foo`.
   - `test_read_graph_entity_uri_missing_type` — `graph-entity://` → `INVALID_PARAMS` with `data["reason"] == "missing_type"`.
   - `test_read_graph_entity_uri_missing_id` — `graph-entity://Function` → `INVALID_PARAMS` with `data["reason"] == "missing_id"`.
   - `test_read_graph_entity_uri_404` — `graph-entity://Function/missing` → `INVALID_PARAMS` with `data["scheme"] == "graph-entity"`.
   - `test_read_graph_entity_uri_503_graphrag_disabled` — fake 503 with the Phase 50 hint; assert `SERVICE_INDEXING` raised with `data["scheme"] == "graph-entity"` and `data["reason"] == "graphrag_disabled"` (extract from the 503 detail).

8. **Run quality gates:**
   ```bash
   cd agent-brain-mcp && poetry run pytest -v
   task mcp:test
   task mcp:contract
   task check:layering
   task before-push
   task pr-qa-gate
   ```

## Verification

- `poetry run pytest agent-brain-mcp/tests/test_resources_read_parameterized.py -v` — all `chunk://` and `graph-entity://` cases plus the Plan 01 `job://` regression cases pass.
- `poetry run pytest agent-brain-mcp/tests/ -v` — full MCP test suite green (no regression in v1 tests).
- Manual smoke (against a running server with content indexed):
  ```bash
  agent-brain start --uds
  agent-brain index ./docs --wait
  # capture a chunk id from query
  CHUNK_ID=$(agent-brain query "RAG" --json | jq -r '.results[0].chunk_id')
  scripts/mcp-read-chunk-uri.sh "$CHUNK_ID" | agent-brain-mcp --backend uds | \
    jq -e '.result.contents[0].uri == "chunk://'$CHUNK_ID'"'
  # graph-entity (requires GraphRAG enabled with the simple store):
  scripts/mcp-read-graph-entity-uri.sh "Function" "QueryService" | agent-brain-mcp --backend uds | \
    jq -e '.result.contents[0].text | fromjson | .entity_type == "Function"'
  agent-brain stop
  ```
- `task check:layering` confirms no `agent_brain_mcp → agent_brain_cli` or `agent_brain_mcp → agent_brain_server.{services,api,indexing,storage}` import leaks in.
- All five quality gates exit 0.

## Risk Notes

- **Risk:** `graph-entity://Function/QueryService.find_by_id` — if entity ids contain `/` (Phase 50 decision B allows this for hierarchical ids), the URL passed to httpx must percent-encode the id segment, but the response server-side must round-trip back to the original id. Verify Phase 50's route definition (path-param vs query-param) — if it's a single path param with a catch-all (`{id:path}` in FastAPI), the parser must concatenate all segments after the type as the id. Mitigation: read Phase 50's `agent_brain_server/api/routers/` graph endpoint code before locking the parser semantics. If unclear, file a question in the design doc per-phase decisions section.
- **Risk:** The 503 → `SERVICE_INDEXING` mapping relies on Phase 50 returning a stable `{"detail": ...}` shape. If Phase 50 instead returns `{"error": "...", "hint": "..."}` (structured), the test stub and the handler's `data["reason"]` extraction must match. Mitigation: write the test against Phase 50's actual response shape; if it differs from this plan's assumption, adjust here without escalating.
- **Risk:** `McpError.error.data` mutation may not be the right pattern in the MCP SDK version pinned in `pyproject.toml`. If `McpError` is immutable, build a new `McpError(McpErrorData(code=..., message=..., data={...}))` and `raise from exc`. Verify in step 5 by reading the SDK's `mcp/types.py` `McpError` definition.
- **Risk:** Adding 8 new test cases brings the file to ~250 LOC. If it grows further (Plan 03 adds `file://` cases), consider splitting into `test_resources_read_chunk.py`, `test_resources_read_graph_entity.py`, `test_resources_read_job.py` before merging. Soft cap is ~400 LOC per test file; revisit in Plan 03.
- **Quality gate:** All five gates exit 0 before push, per CLAUDE.md #1 rule.

---
*Plan 02 of Phase 51*
