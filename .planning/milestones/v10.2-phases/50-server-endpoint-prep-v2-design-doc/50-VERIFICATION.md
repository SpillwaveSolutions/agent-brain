---
phase: 50
phase_name: Server endpoint prep + v2 design doc
status: passed
verified: 2026-06-02
verifier: gsd-verifier
---

# Phase 50 Verification

## Goal Achievement

**Goal:** "Server-side prerequisites for v2 are in place — new lookup endpoints exist, the sandbox design for `roots/list`-gated `file://` reads is decided, and the v2 design doc is filed before any MCP-layer code lands."

**Achieved: YES.** All four success criteria from ROADMAP.md are met. The v2 design doc is filed at the canonical path with all six required sections and locked wire shapes. `GET /query/chunk/{chunk_id}` is registered with O(1) lookup via a new `get_chunk_by_id` primitive on `StorageBackendProtocol`, implemented on both ChromaDB and Postgres. `GET /graph/entity/{type}/{id}` is registered with the full 200/400/404/503 status-code matrix and explicit #178 (Kuzu SIGSEGV) handling via the `KuzuUnavailableError` sentinel. The `agent_brain_server.security.file_sandbox` module ships with `canonicalize_path`, `is_path_allowed`, `list_sandbox_roots`, and `DEFAULT_MAX_READ_BYTES`, governed by the new `MCP_SANDBOX_MAX_READ_BYTES` setting. The full quality gate is green (Black, Ruff, mypy strict, 1269/28-skipped pytest).

## Success Criteria

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | v2 design doc filed | PASS | `docs/plans/2026-06-02-mcp-v2-subscriptions.md` exists at 486 lines; all 6 required sections present (`Context`, `Architecture deltas vs v1`, `Per-phase decisions`, `Risk register`, `Test strategy`, `Out of scope`); §2.3 locks `ChunkRecord`, §2.4 locks `GraphEntityRecord`, §2.5 locks sandbox policy; §4 cites #178 (R1) + #179 (R2); cross-refs to v1 doc + scope contract + umbrella #186 present. |
| 2 | `GET /query/chunk/{id}` O(1) | PASS | Route registered in `api/routers/query.py:98` with `response_model=ChunkRecord`; `get_chunk_by_id` declared on `storage/protocol.py:352`; implemented on `storage/chroma/backend.py:508` (via `collection.get(ids=[id], include=["documents","metadatas"])`) and `storage/postgres/backend.py:633` (PK lookup, embedding column NOT selected); 404 with `chunk_not_found` structured body; tests `tests/contract/test_get_chunk_by_id.py` + `tests/integration/test_chunk_endpoint.py` present and passing. |
| 3 | `GET /graph/entity/{type}/{id}` | PASS | Router `api/routers/graph.py` created (170+ lines); registered in `api/main.py:702` under `/graph` prefix; declares status codes 200/400/404/503-graphrag-disabled/503-kuzu-unavailable per CONTEXT decision B; `get_entity_by_id` implemented on graph manager (`storage/graph_store.py:831`) backed by SimplePropertyGraphStore + Kuzu (Kuzu uses Cypher fallback for incoming-edge gap); `KuzuUnavailableError` sentinel at `graph_store.py:36` translates #178 SIGSEGV signatures to 503; tests `tests/unit/storage/test_get_entity_by_id.py` (13 cases) + `tests/unit/api/test_graph_entity_endpoint.py` (12 cases) present and passing. |
| 4 | `roots/list` sandbox decided | PASS | `agent_brain_server/security/file_sandbox.py` (261 lines) exports `canonicalize_path`, `is_path_allowed`, `list_sandbox_roots`, `DEFAULT_MAX_READ_BYTES`; 4 deny reasons implemented (`outside_indexed_roots`, `hidden_file`, `size_limit`, `symlink_escape`/`not_found`); default cap 10 MiB; new `MCP_SANDBOX_MAX_READ_BYTES` field added to `config/settings.py:135`; tests `tests/security/test_file_sandbox.py` (353 lines, 33 tests) passing. Policy is decision-only at the server level (no HTTP route shipped in Phase 50, by design — Phase 51 wires it into MCP `resources/read`). |

**Score: 4/4 success criteria verified.**

## Requirements Status

- **VAL-05** (Own v2 design doc filed at `docs/plans/YYYY-MM-DD-mcp-v2-subscriptions.md`): **Complete** — filed at `docs/plans/2026-06-02-mcp-v2-subscriptions.md`. The traceability row in `.planning/REQUIREMENTS.md:116` still reads `| VAL-05 | Phase 50 | Pending |`; the orchestrator should flip this to `Complete` when it updates STATE.md / ROADMAP.md. **DO NOT edit REQUIREMENTS.md from this report** — flagged for orchestrator follow-through.

## Codebase Evidence

### Plan 01 — v2 design doc

| Artifact | Status | Detail |
|----------|--------|--------|
| `docs/plans/2026-06-02-mcp-v2-subscriptions.md` | EXISTS | 486 lines (just outside SUMMARY's acceptance ceiling of 450; the executor flagged this as justified by mandatory locked code blocks + Mermaid diagrams; planning policy ceiling was 200-450 but criteria 4 of the plan permitted explicit extension). 6 required sections present. |
| §2.3 `ChunkRecord` locked | PRESENT | Pydantic shape committed verbatim with field list matching what Plans 02 implemented. |
| §2.4 `GraphEntityRecord` locked | PRESENT | Pydantic shape committed verbatim with `entity`+`neighbors` 1-hop structure. |
| §2.5 sandbox policy locked | PRESENT | Hard whitelist, read-time canonicalization, 4 deny reasons, 10 MB cap, no escape hatch. |
| Risk register §4 | PRESENT | R1 = #178 (Kuzu), R2 = #179 (Bearer auth), R3-R8 cover v1 compat, subscription leak, HTTP non-loopback, release-train coupling, local-process trust, diff hash misses. |
| Canonical references | PRESENT | Links to v1 doc, scope contract, umbrella #186, #178, #179. |

### Plan 02 — `GET /query/chunk/{chunk_id}`

| Artifact | Status | Detail |
|----------|--------|--------|
| `api/routers/query.py` chunk route | EXISTS | Line 98: `@router.get("/chunk/{chunk_id}", response_model=ChunkRecord)`. Returns 404 `chunk_not_found` structured body on miss. |
| `storage/protocol.py:352` `get_chunk_by_id` | EXISTS | Declared as `async def get_chunk_by_id(self, chunk_id: str) -> ChunkRecord \| None`. |
| `storage/chroma/backend.py:508` | EXISTS | Uses `collection.get(ids=[chunk_id], include=["documents", "metadatas"])` — embeddings explicitly NOT requested. |
| `storage/postgres/backend.py:633` | EXISTS | PK SELECT; `chunk_id` is already PK so implicit index covers O(1) lookup (no migration needed per executor note). |
| `models/query.py` `ChunkRecord` | EXISTS | Exported via `models/__init__.py`. |
| `tests/contract/test_get_chunk_by_id.py` | EXISTS | Parametrized across ChromaDB (always) + Postgres (skip-if-no-DATABASE_URL). |
| `tests/integration/test_chunk_endpoint.py` | EXISTS | FastAPI TestClient suite: 200/404/special-chars. |

### Plan 03 — `GET /graph/entity/{type}/{id}`

| Artifact | Status | Detail |
|----------|--------|--------|
| `api/routers/graph.py` | EXISTS | Created; registered in `api/main.py:702` under `/graph` prefix. |
| Status code matrix | PRESENT | 200 (hit), 400 `invalid_entity_type` (lines 132-141, with `valid_types` body), 404 `entity_not_found` (lines 192-203), 503 `graphrag_disabled` (lines 120-127, 166-173), 503 `kuzu_unavailable` (lines 151-158, 183-191). 503-disabled checked BEFORE 400 to avoid leaking type-existence to disabled-state callers. |
| `storage/graph_store.py:831` `get_entity_by_id` | EXISTS | Drives both backends through LlamaIndex `PropertyGraphStore` ABC for the happy path; Kuzu-only Cypher fallback for incoming edges due to LlamaIndex 0.9.x library quirk (outgoing-only triplets). |
| `storage/graph_store.py:36` `KuzuUnavailableError` | EXISTS | Module-level sentinel; raised on `IndexError`/`RuntimeError`/`OSError` from any Kuzu call site (`store.get`, `store.get_triplets`, Cypher conn.execute/get_next); SimplePropertyGraphStore intentionally does NOT trigger the sentinel. |
| `models/graph.py` v2 records | EXISTS | `GraphEntityRecord`, `GraphEntityRecordNode`, `GraphEntityRecordNeighbor`, `GraphEntityRecordNeighbors`. Introduced as sibling-named additions; legacy `GraphEntity` (extraction pipeline) left untouched. |
| `tests/unit/storage/test_get_entity_by_id.py` | EXISTS | 13 contract cases (8 simple + 5 Kuzu), plus `KuzuUnavailableError` sentinel coverage. |
| `tests/unit/api/test_graph_entity_endpoint.py` | EXISTS | 12 endpoint cases covering all 4 paths + URL-encoded path components + OpenAPI schema. |
| `_VALID_ENTITY_TYPES` sourced from `ENTITY_TYPES` | VERIFIED | Single source of truth; test pins `len(ENTITY_TYPES) == 17` so SCHEMA-01 drift surfaces in the diff. |

### Plan 04 — `file_sandbox` module

| Artifact | Status | Detail |
|----------|--------|--------|
| `agent_brain_server/security/__init__.py` | EXISTS | 812 bytes; re-exports the public API. |
| `agent_brain_server/security/file_sandbox.py` | EXISTS | 261 lines. |
| Public API | COMPLETE | `canonicalize_path`, `is_path_allowed`, `list_sandbox_roots`, `DEFAULT_MAX_READ_BYTES` all exported. |
| 4 deny reasons | PRESENT | `outside_indexed_roots`, `hidden_file`, `size_limit`, `symlink_escape` (SUMMARY also calls out `not_found` as a possible flavor; both reasoning predicates implemented). Precedence documented in docstring (symlink_escape → hidden_file → outside_indexed_roots). |
| `config/settings.py:135` `MCP_SANDBOX_MAX_READ_BYTES` | EXISTS | Default 10 \* 1024 \* 1024 (10 MiB). |
| `tests/security/test_file_sandbox.py` | EXISTS | 353 lines, 33 tests. |
| No new HTTP route in Phase 50 | VERIFIED | Sandbox is server-internal; Phase 51 wires it into MCP `resources/read`. |

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| `query.py:get_chunk_by_id` route | `StorageBackendProtocol.get_chunk_by_id` | `await storage.get_chunk_by_id(chunk_id)` (line 155) | WIRED |
| `graph.py:get_graph_entity` route | `graph_store.get_entity_by_id` | `graph_mgr.get_entity_by_id(entity_type, entity_id)` (line 176) | WIRED |
| `graph.py` router | `api/main.py` | `app.include_router(graph_router, prefix="/graph", tags=["Graph"])` (line 702) | WIRED |
| `KuzuUnavailableError` raise | `graph.py` router catch | `except KuzuUnavailableError` blocks at lines 151, 183 | WIRED |
| `models.ChunkRecord` import | `query.py` route | Line 8 import; line 99 `response_model=ChunkRecord` | WIRED |
| Sandbox module exports | `security/__init__.py` | Re-exports `canonicalize_path`, `is_path_allowed`, `list_sandbox_roots`, `DEFAULT_MAX_READ_BYTES` | WIRED |

## Tests

| Suite | Command | Result | Detail |
|-------|---------|--------|--------|
| Format (Black) | `poetry run black --check agent_brain_server tests` | PASS | 192 files unchanged |
| Lint (Ruff) | `poetry run ruff check agent_brain_server tests` | PASS | All checks passed |
| Type (mypy strict) | `poetry run mypy agent_brain_server` | PASS | 84 source files, no issues |
| Tests (pytest) | `poetry run pytest -q` | PASS | 1269 passed, 28 skipped (22.01s) |

## Deviations from Plan

Captured from executor SUMMARIES — none are blocking; all are reasonable accommodations to the actual codebase.

1. **Design doc length 486 lines vs 200-450 acceptance ceiling.** Plan 01 SUMMARY justifies the 36-line overage by the locked-code blocks + three Mermaid diagrams + ASCII architecture diagram. The doc's acceptance criterion 2 permits 200-450 with a target of ~300; 486 is +36 over the ceiling but is fully content-bearing. Not blocking — the locked decisions are present and unambiguous.
2. **No standalone `docs/api/openapi.json` regenerated.** Plans 02 and 03 originally called for it; both SUMMARIES noted no such file is committed in this repo (FastAPI serves the spec live at `/openapi.json`). Endpoint integration tests pin the route + schema appears in `app.openapi()["components"]["schemas"]`. Acceptable substitution.
3. **Tests landed under `tests/contract/`, `tests/integration/`, `tests/unit/...` not the plan's suggested `tests/storage/` / `tests/api/`.** Functionally equivalent; matches the existing repo's established layout for parametrized contract tests and FastAPI route tests.
4. **No manual curl smoke tests executed.** Plan 02 and 03 both specified curl-against-a-running-server checks; both executors skipped them because Plans 02/03/04 ran in parallel and an `agent-brain start` call would have raced with the other plans' work. FastAPI TestClient suites cover the equivalent contract surface in-process. **This is explicitly listed in the verification instructions as a SKIP.** Acceptable.
5. **Postgres `chunks` table is named `documents` and `chunk_id` is already the PK.** No `CREATE INDEX IF NOT EXISTS idx_chunks_chunk_id` migration was needed — the implicit PK index covers O(1) lookup. Plan 02 step 6 was a precaution that turned out to be unnecessary.
6. **`parent_doc_id` and `folder_id` fall back to derivations from `source`.** Neither field is currently emitted by `IndexingService`'s chunk metadata writer; the mapper derives both from the source path. The locked v2 wire shape is preserved; a future indexing-side surface for these fields can land without breaking the contract.
7. **Plan 04 executor process crashed mid-flight.** Three commits (`1b339d4`, `bea4790`, `b83e93d`) landed before a socket disconnect; the SUMMARY.md and final verification run were completed by the orchestrator (post-crash recovery). Identical net outcome to a successful executor run.
8. **`GraphEntityRecord` is sibling-named, not a replacement for legacy `GraphEntity`.** The existing extraction-pipeline `GraphEntity` Pydantic class has a different shape (`name`, `entity_type`, `source_chunk_ids`, scoped properties); v2 endpoint adds a parallel set rather than migrating call sites. A future plan can converge them.
9. **Kuzu-specific Cypher fallback for incoming edges.** `llama-index-graph-stores-kuzu` 0.9.x returns outgoing-only triplets from both `get_triplets()` and `get_rel_map()`; manager runs direct parameterized Cypher when `store_type == "kuzu"` to preserve the locked wire shape. Entire path wrapped in the same `KuzuUnavailableError` guard. Documented in the SUMMARY and in code comments.
10. **Kuzu does NOT preserve custom `Relation.properties`.** Current Kuzu schema only persists the predicate as a `label`; caller-supplied keys like `source_chunk_id` are dropped. Contract test conditions the property assertion on `manager.store_type != "kuzu"` and documents this as a backend-level limitation.

## Gaps (if any)

None. All four success criteria verified; full quality gate green; all claimed test files exist on disk; all claimed commit hashes resolve.

## Human Verification Needed (if any)

None — all criteria verified automatically. The deferred curl smoke tests (called out in deviation 4 above) are explicitly excluded from this verification per the orchestrator's instructions; the FastAPI TestClient suite covers the equivalent contract surface in-process and is part of the 1269 passing tests.

## Sign-off

**Ready for Phase 51.** Phase 50 delivers all four server-side prerequisites the v2 design doc commits to: the design doc itself is filed with locked wire shapes; both new HTTP endpoints exist with full status-code matrices and parametrized backend coverage; the `file_sandbox` module exports the four-function public API that Phase 51's `file://` URI handler will import verbatim. The quality gate (Black, Ruff, mypy strict, 1269/28-skipped pytest) is clean across the entire `agent-brain-server` package — no regressions introduced by any of the four plans.

The orchestrator should:
1. Flip `VAL-05` in `.planning/REQUIREMENTS.md:116` from `Pending` to `Complete` when updating traceability.
2. Mark Phase 50 plans `4/4` complete in `.planning/ROADMAP.md:42`.
3. Hand off to the Phase 51 planner with the locked contracts in `docs/plans/2026-06-02-mcp-v2-subscriptions.md` §2 as the source of truth for the URI scheme handlers.
