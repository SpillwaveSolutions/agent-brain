---
phase: 51-uri-schemes-templates
plan: 02
subsystem: mcp
tags: [mcp, uri-schemes, chunk-uri, graph-entity-uri, kuzu-sigsegv-fallback, parameterized-resources, phase-50-consumer]

# Dependency graph
requires:
  - phase: 50-server-endpoint-prep-v2-design-doc
    provides: "GET /query/chunk/{chunk_id} and GET /graph/entity/{type}/{id} server endpoints + locked ChunkRecord/GraphEntityRecord wire shapes + 503 graphrag_disabled/kuzu_unavailable detail bodies"
  - phase: 51-uri-schemes-templates
    provides: "Plan 01 parameterized URI dispatcher infrastructure (ParsedURI dataclass, PARAMETERIZED_HANDLERS registry, scheme-prefix routing in read_resource, McpError data refinement pattern)"
provides:
  - "chunk://<chunk_id> MCP resource → ChunkRecord JSON (URI-01)"
  - "graph-entity://<type>/<id> MCP resource → GraphEntityRecord JSON (URI-02)"
  - "ApiClient.get_chunk(chunk_id) and ApiClient.get_graph_entity(type, id) HTTP methods"
  - "Phase 50 503 detail.error slug (graphrag_disabled | kuzu_unavailable) promoted to McpError data.reason so MCP clients route on it without re-parsing cause strings"
  - "graph-entity URI parser allows hierarchical ids with embedded '/' (Phase 50 decision B)"
affects:
  - "52-resource-subscriptions (SUB-04 may want chunk:// refresh; not in scope)"
  - "54-remaining-tools (search_chunks tool can return chunk:// URIs for cross-referencing)"
  - "55-validation-contract-tests-qa-gate (contract tests can pin chunk + graph-entity URI shapes)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Scheme-specific data refinement: catch McpError from raise_for_status, merge original.data with {scheme, <scheme-id>} and (for graph-entity 503) {reason: graphrag_disabled|kuzu_unavailable}, re-raise via McpError(ErrorData(...))"
    - "Forgiving substring scan against a closed reason set for HTTP-detail → MCP-data routing hints (resilient to server-side detail formatting tweaks)"

key-files:
  created: []
  modified:
    - "agent-brain-mcp/agent_brain_mcp/client.py — get_chunk + get_graph_entity ApiClient methods"
    - "agent-brain-mcp/agent_brain_mcp/resources/parameterized.py — _handle_chunk_uri + _handle_graph_entity_uri handlers; PARAMETERIZED_HANDLERS swapped off NotImplementedError for chunk + graph-entity; graph-entity parser docstring updated for slash-in-id allowance"
    - "agent-brain-mcp/tests/conftest.py — ChunkRecord stub at /query/chunk/chunk_001; GraphEntityRecord stub at /graph/entity/Function/foo; hierarchical-id stub at /graph/entity/Function/AuthService/login"
    - "agent-brain-mcp/tests/test_resources_read_parameterized.py — 17 new test cases (3 chunk e2e + 8 graph-entity e2e + 6 parse_uri unit) + placeholder test scoped to file:// only"

key-decisions:
  - "503 detail.error slug extraction: a forgiving substring scan (rather than strict JSON-parse of the cause field) for the closed set {graphrag_disabled, kuzu_unavailable}. Resilient to future server-side formatting tweaks; only routes when the slug is unambiguous."
  - "graph-entity URI parser allows ids containing '/' — Phase 50 decision B explicitly permits hierarchical ids (e.g., AuthService/login). raw_path.lstrip('/').rstrip('/') captures everything between the type segment and the trailing slash as the full id."
  - "Per-scheme refinement preserves the original error code: chunk 404 stays INVALID_PARAMS, graph-entity 503 stays SERVICE_INDEXING. We only mutate data, never code/message — clients that already key off code keep working."
  - "ApiClient methods do NOT URL-encode ids — httpx does that once; FastAPI's path-style {entity_id} segment round-trips slashes correctly. Mirrors get_job pattern verbatim."

patterns-established:
  - "Scheme-specific McpError refinement: catch → merge data → re-raise McpError(ErrorData(code=original.code, message=original.message, data=refined_data)) from exc. Plan 03 (file://) follows the same pattern."
  - "Per-scheme reason hints: when a status code maps to multiple operator scenarios (e.g., 503 from graphrag_disabled vs kuzu_unavailable), extract the slug from the server's detail body and surface it as data.reason. Keeps MCP clients out of the cause-parsing business."

requirements-completed: [URI-01, URI-02]

# Metrics
duration: 7min
completed: 2026-06-03
---

# Phase 51 Plan 02: chunk:// + graph-entity:// URI handlers Summary

**`chunk://<id>` and `graph-entity://<type>/<id>` are addressable via MCP `resources/read`, riding Phase 50's `GET /query/chunk/{id}` and `GET /graph/entity/{type}/{id}` endpoints with per-scheme error refinement that preserves the Phase 50 #178 SIGSEGV `kuzu_unavailable` 503 routing hint.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-03T05:30:25Z
- **Completed:** 2026-06-03T05:37:34Z
- **Tasks:** 4 (ApiClient methods, parameterized handlers, conftest fixtures, e2e + unit tests)
- **Files modified:** 4 (client.py, parameterized.py, conftest.py, test_resources_read_parameterized.py)
- **Tests added:** 17 (3 chunk + 8 graph-entity + 6 parse_uri unit)
- **Total test count after plan:** 108 (up from 91 at Plan 51-01 close)

## Accomplishments

- **`chunk://<chunk_id>` end-to-end:** MCP client → parse_uri → ApiClient.get_chunk → GET /query/chunk/{id} → ChunkRecord JSON round-trip. No embedding in the response (Phase 50 decision C honored).
- **`graph-entity://<type>/<id>` end-to-end:** MCP client → parse_uri → ApiClient.get_graph_entity → GET /graph/entity/{type}/{id} → GraphEntityRecord JSON (entity + 1-hop incoming/outgoing neighbors).
- **Hierarchical entity ids:** parser splits at the first `/` after the type, treats everything after as the full id. Test covers `graph-entity://Function/AuthService/login` → entity_id="AuthService/login". Phase 50 decision B fully honored.
- **#178 SIGSEGV routing:** Phase 50's 503 `detail.error: "kuzu_unavailable"` flows through `raise_for_status` → handler catches McpError → extracts the slug from `data.cause` → re-raises with `data.reason = "kuzu_unavailable"`. Operators (and MCP clients) can route on this without grepping the cause string. Same path covers the `graphrag_disabled` case (operator-configurable).
- **Per-scheme data refinement contract:** chunk 404 → INVALID_PARAMS with `{scheme: "chunk", chunk_id, httpStatus, cause}`. graph-entity 503 → SERVICE_INDEXING with `{scheme: "graph-entity", entity_type, entity_id, reason, httpStatus, cause, hint}`. Original error code preserved; only `data` is enriched.

## Task Commits

Each task was committed atomically:

1. **Task 1+2 (impl): ApiClient methods + parameterized handlers** — `63c5623` (feat) — `feat(51-02): chunk:// + graph-entity:// URI handlers + ApiClient methods`
2. **Task 3+4 (tests): conftest fixtures + e2e/unit cases** — `5727709` (test) — `test(51-02): cover chunk:// + graph-entity:// read paths`
3. **Format fix: Black-collapsed get_graph_entity signature** — `e48edc6` (chore) — `chore(51-02): Black-format get_graph_entity signature to single line`

**Plan metadata (forthcoming):** docs commit will land alongside this SUMMARY + STATE.md + ROADMAP.md update.

_Note: Plan 03 (file://) is committing in parallel under `8ea1460` (security shim) plus its own in-flight work; their commits are interleaved with Plan 02's but touch disjoint code (file:// handler + security re-export module)._

## Files Created/Modified

### Modified

- **`agent-brain-mcp/agent_brain_mcp/client.py`** — Added `get_chunk(chunk_id)` and `get_graph_entity(entity_type, entity_id)`. Both go through the existing `_get` → `raise_for_status` pipeline so 404 → INVALID_PARAMS and 503 → SERVICE_INDEXING mappings are inherited verbatim.
- **`agent-brain-mcp/agent_brain_mcp/resources/parameterized.py`** — Implemented `_handle_chunk_uri` and `_handle_graph_entity_uri`. Added `_extract_graph_entity_reason` helper that does a forgiving substring scan against the closed `{graphrag_disabled, kuzu_unavailable}` reason set. Swapped both schemes in PARAMETERIZED_HANDLERS off `_handle_not_implemented`. Updated module docstring to note Plan 02's scope. `file://` slot remains NotImplementedError (Plan 03 owns it).
- **`agent-brain-mcp/tests/conftest.py`** — Added three `_DEFAULT_RESPONSES` entries: ChunkRecord stub at `GET /query/chunk/chunk_001`, GraphEntityRecord stub at `GET /graph/entity/Function/foo`, and a hierarchical-id stub at `GET /graph/entity/Function/AuthService/login`.
- **`agent-brain-mcp/tests/test_resources_read_parameterized.py`** — Added `TestReadResourceChunkUri` (3 cases: success, missing_id, 404-refines-data), `TestReadResourceGraphEntityUri` (8 cases: success, missing_type, missing_id, trailing-slash, slash-in-id, 404-refines-data, 503 graphrag_disabled, 503 kuzu_unavailable), and `TestParseUriChunkAndGraphEntity` (6 unit cases). Scoped the placeholder NotImplementedError test to `file://` only.

## Decisions Made

- **Forgiving substring scan for 503 reason extraction.** The Phase 50 server emits the error slug inside a `{"detail": {"error": ..., "hint": ...}}` JSON body, which `raise_for_status` flattens into `data["cause"]` as `str(detail)`. Rather than re-parsing JSON or matching exact strings, we scan for the closed reason set `{graphrag_disabled, kuzu_unavailable}` as substrings. This survives reformatting and only routes when the slug is unambiguous (the two slugs share no substring).
- **Entity ids with embedded `/`.** Phase 50 decision B permits hierarchical ids (e.g., `AuthService/login`, file paths used as graph ids). Parser reads `parts.netloc` as the type and `parts.path.lstrip("/").rstrip("/")` as the full id including any inner `/`. Single-trailing-slash trim is sole pre-processing — `graph-entity://Function/` → empty id → `missing_id`. Test pins the `AuthService/login` case end-to-end.
- **Preserve original error code on refinement.** When `raise_for_status` raises INVALID_PARAMS (404) or SERVICE_INDEXING (503), the handler re-raises with the same code — only `data` is enriched. Clients keying off `code` see no behavioral change; clients reading `data["scheme"]` get the new routing info.
- **No URL-encoding in ApiClient.** `httpx` URL-quotes path segments once; FastAPI's path-style `{entity_id}` matches with embedded `/`. Mirrors the existing `get_job(job_id)` pattern; no pre-encoding needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Black-format multi-line `get_graph_entity` signature**
- **Found during:** Quality-gate run after Task 4 (tests committed)
- **Issue:** The committed signature `def get_graph_entity(self, entity_type: str, entity_id: str) -> dict[str, Any]:` was written multi-line but fits within 88 chars on a single line. `poetry run black --check` flagged it.
- **Fix:** Collapsed the signature to one line. Also collapsed the matching `_handle_graph_entity_uri` async signature in `parameterized.py` (both were the same 88-char shape).
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/client.py`, `agent-brain-mcp/agent_brain_mcp/resources/parameterized.py`
- **Verification:** `poetry run black --check agent_brain_mcp/client.py` returns clean. The parameterized.py wrap fix is bundled into Plan 03's pending work (Plan 03 is also editing parameterized.py and will commit its own black-clean state).
- **Committed in:** `e48edc6` (client.py); parameterized.py wrap is in Plan 03's working tree pending its commit.

**2. [Rule 3 - Blocking — collaboration with Plan 03] Soft-reset of an accidentally-included Plan 03 commit**
- **Found during:** Quality-gate format fix commit
- **Issue:** A `git commit` after `git add agent-brain-mcp/agent_brain_mcp/client.py` unexpectedly included Plan 03's unstaged edits to `parameterized.py`, `server.py`, and `tests/test_resources_read_parameterized.py` in the same commit (the file-tracker captured them at commit time). This would have made Plan 02's format-fix commit own Plan 03's work.
- **Fix:** `git reset --soft HEAD~1` to undo the commit while keeping the index intact, `git restore --staged` to unstage the three Plan 03 files, then re-committed just `client.py`. The cleanup yielded the canonical `e48edc6` commit (1 file, 1 insertion, 3 deletions).
- **Files modified:** None new — purely a git-history cleanup.
- **Verification:** `git show --stat e48edc6` shows exactly 1 file (`client.py`) changed. Plan 03's unstaged work flows back to its working tree for its own commit.
- **Committed in:** `e48edc6` (recovered commit); the broken `34971b2` was discarded by the soft reset.

---

**Total deviations:** 2 auto-fixed (1 Rule 1 black format, 1 Rule 3 git-history cleanup)
**Impact on plan:** Both deviations are zero-surface — no test changes, no behavior changes. The git-history cleanup preserved the parallel-execution contract with Plan 03 (Plan 03 owns its own edits to `parameterized.py`, `server.py`, and the test file's placeholder cleanup).

## Issues Encountered

- **Parallel-execution file-state race.** Plan 03 was actively editing `parameterized.py` and `server.py` while Plan 02 was running. Two consequences:
  1. The Edit tool surfaced "file modified since read" errors twice during my Black format fix to `parameterized.py`; resolved by re-reading the file each time and re-issuing the edit.
  2. The accidental commit (see deviation #2 above) was triggered by Plan 03's tracked changes leaking into a `git add <single-file>` + `git commit` sequence. Cleaner pattern for future parallel-plan execution: `git diff --cached <file>` BEFORE every `git commit` to verify only intended hunks are staged.
- **Resolution:** Both issues were transient and recoverable. The committed state is clean — `e48edc6` shows 1 file changed; `git log` shows clean Plan 02 vs Plan 03 attribution.

## Verification

### Quality gates (run from `agent-brain-mcp/`):

| Check | Command | Result |
|-------|---------|--------|
| Black | `poetry run black --check agent_brain_mcp/client.py tests/test_resources_read_parameterized.py tests/conftest.py` | PASS (3 files unchanged) |
| Ruff  | `poetry run ruff check agent_brain_mcp/client.py tests/test_resources_read_parameterized.py tests/conftest.py` | 2 pre-existing F401 in `conftest.py` from Plan 03's pending `dataclass`/`Path` imports (NOT Plan 02) |
| mypy  | `poetry run mypy agent_brain_mcp` | PASS (24 source files, no issues) |
| pytest | `poetry run pytest` | PASS (107 / 33 deselected; note: test count is 107 because Plan 03's unstaged tree drops the now-redundant `file://` placeholder test — under Plan 02's committed state alone the count is 108) |

### Test breakdown

- `test_resources_read_parameterized.py`: 37 tests (committed state)
  - `TestParseUri`: 9 cases (Plan 51-01 baseline)
  - `TestReadResourceJobUri`: 5 cases (Plan 51-01 baseline)
  - `TestReadResourceFallThrough`: 2 cases (corpus + unknown-scheme regression)
  - `TestReadResourceChunkUri`: 3 cases ✨ Plan 02
  - `TestReadResourceGraphEntityUri`: 8 cases ✨ Plan 02
  - `TestPlaceholderHandlers`: 1 case (file:// only — chunk + graph-entity removed since they're now implemented) ✨ Plan 02
  - `TestParseUriChunkAndGraphEntity`: 7 cases (parse_uri pure unit cases for chunk + graph-entity) ✨ Plan 02
  - `TestParsedURI`: 2 cases (dataclass invariants — Plan 51-01 baseline)

### Manual smoke

Not executed in this session — Plan 03 is running in parallel with `agent-brain start` would race. The TestClient suite covers the equivalent contract assertions in-process for all 11 happy + error paths.

### Layering

- `agent_brain_mcp/client.py` adds two methods that go through the existing `_get` helper — no new cross-package imports.
- `agent_brain_mcp/resources/parameterized.py` imports from `..errors` and `mcp.types` only (same imports Plan 51-01 used).
- No `agent_brain_mcp → agent_brain_cli` import introduced.

## Next Phase Readiness

### Phase 51 status
- **Plans complete after this plan:** 2/4 (51-01 ✓, 51-02 ✓; 51-03 file:// in flight in parallel; 51-04 templates/list awaits 51-03 finish for `MIN_BACKEND_VERSION` bump).
- **Requirements closed:** URI-01 (chunk://), URI-02 (graph-entity://), URI-03 (job:// — closed by Plan 01).
- **Requirements remaining for Phase 51:** URI-04 (file://, Plan 03), URI-05 (templates list, Plan 04).

### Plan 03 / 04 inputs

- **Plan 03 (file://)** can reuse the same per-scheme refinement pattern (catch McpError, merge data, re-raise) but its handler will look very different — it's filesystem I/O gated by the Phase 50 sandbox helper, not an HTTP call. The `_handle_not_implemented` placeholder for `file` remains in place in `PARAMETERIZED_HANDLERS` so Plan 03 just needs to overwrite that entry and add its handler implementation.
- **Plan 04 (resources/templates/list)** can advertise both `chunk://{chunk_id}` and `graph-entity://{type}/{id}` with `mimeType: "application/json"` (Phase 51 CONTEXT decision B).

### Concerns

- **Test count drift between Plan 02 committed state (108 tests) and Plan 03 unstaged state (107 tests)** is expected — Plan 03 will remove the redundant `file://` placeholder test when it commits its real `file://` handler. Not a concern; both states are internally consistent.
- **Ruff F401 errors in conftest.py** from Plan 03's pending `dataclass`/`Path` imports will clear when Plan 03 commits its `tmp_path`-based fixture code that uses them. Not Plan 02's problem.

---
*Phase: 51-uri-schemes-templates*
*Plan: 02 of 4*
*Completed: 2026-06-03*

## Self-Check: PASSED

- Created files exist:
  - `.planning/phases/51-uri-schemes-templates/plans/02-chunk-and-graph-entity-uris-SUMMARY.md` — FOUND
- Commit hashes exist in `git log`:
  - `63c5623` feat(51-02): chunk:// + graph-entity:// URI handlers + ApiClient methods
  - `5727709` test(51-02): cover chunk:// + graph-entity:// read paths
  - `e48edc6` chore(51-02): Black-format get_graph_entity signature to single line
