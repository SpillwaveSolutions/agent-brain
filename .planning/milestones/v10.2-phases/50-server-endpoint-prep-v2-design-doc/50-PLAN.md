# Phase 50 Plan: Server endpoint prep + v2 design doc

**Goal:** Server-side prerequisites for v2 are in place — new lookup endpoints exist, the sandbox design for `roots/list`-gated `file://` reads is decided, and the v2 design doc is filed before any MCP-layer code lands.

**Requirements:** VAL-05

**Plan count:** 4

## Plans

| # | Title | Requirements | Depends on | Parallel-safe with | Est. LOC |
|---|-------|--------------|------------|---------------------|----------|
| 01 | v2 design doc — surgical design for subscriptions, transports, endpoints, sandbox | VAL-05 | none — first plan | none (approval gate) | ~350 doc |
| 02 | `GET /query/chunk/{id}` endpoint + `get_chunk_by_id` on `StorageBackendProtocol` | URI-01 prereq | 01 (design doc landed) | 03, 04 | ~280 |
| 03 | `GET /graph/entity/{type}/{id}` endpoint + `get_entity_by_id` on graph store | URI-02 prereq | 01 (design doc landed) | 02, 04 | ~320 |
| 04 | `file_sandbox` security module + `roots/list` policy doc | URI-04 prereq | 01 (design doc landed) | 02, 03 | ~250 |

**Total estimated LOC:** ~1,200 (including tests and design doc; code change ~850)

## Execution Order

- **Wave 1 (sequential, blocking gate):** Plan 01 — v2 design doc must land and be reviewed before any endpoint code. Per CONTEXT.md decision D, reviewers can challenge wire shapes before they ship.
- **Wave 2 (parallel, after 01):** Plans 02, 03, 04 may execute concurrently. They touch disjoint surfaces:
  - 02 touches `storage/protocol.py`, `storage/chroma/`, `storage/postgres/`, `api/routers/query.py` (or new `chunks.py`), `models/`
  - 03 touches `storage/graph_store.py`, new `api/routers/graph.py`, `models/`
  - 04 touches new `security/file_sandbox.py`, `config/settings.py`, the design doc gets an addendum section

## Coverage Check

Every Phase 50 requirement maps to at least one plan:

- **VAL-05** (file v2 design doc): Plan 01

Phase 50 also produces **prerequisites** for downstream phases (no requirement IDs assigned, but explicitly tracked):

- **URI-01** prereq (`GET /query/chunk/{id}`): Plan 02
- **URI-02** prereq (`GET /graph/entity/{type}/{id}`): Plan 03
- **URI-04** prereq (`roots/list` sandbox design + helper): Plan 04

## Cross-Phase Dependencies

**This phase blocks:**

- **Phase 51** (URI schemes + templates) — needs all four contracts:
  - Plan 02's `GET /query/chunk/{id}` for URI-01 (`chunk://<id>`)
  - Plan 03's `GET /graph/entity/{type}/{id}` for URI-02 (`graph-entity://<type>/<id>`)
  - Plan 04's `file_sandbox` module + `roots/list` policy for URI-04 (`file://<abs-path>`)
- **Phases 51-55** all read against the locked response shapes committed in Plan 01's design doc. Plan 01 is the contract that all subsequent phases plan against.

**This phase is blocked by:** nothing — Phase 50 is the first phase of the v10.2 milestone (v10.1.2 already shipped).

**Contracts produced for downstream consumers:**

- `ChunkRecord` Pydantic response model (new in Plan 02) → consumed by Phase 51's `chunk://` resource handler
- `GraphEntityRecord` Pydantic response model (new in Plan 03) → consumed by Phase 51's `graph-entity://` resource handler
- `file_sandbox.is_path_allowed(path, roots)` + `canonicalize_path(...)` (new in Plan 04) → consumed by Phase 51's `file://` resource handler
- `StorageBackendProtocol.get_chunk_by_id(chunk_id)` (new in Plan 02) → contract for ChromaDB + Postgres backends
- `GraphStore.get_entity_by_id(type, id)` (new in Plan 03) → contract for Kuzu + SimplePropertyGraphStore backends

## Risk Register

Top risks identified during planning:

1. **Design doc bikeshedding delays Wave 2** — Plan 01 is a hard gate (per CONTEXT.md decision D). If review cycles drag past one working day, downstream plans starve. Mitigation: keep doc surgical (~200-400 lines, mirrors v1 reference); commit decisions A/B/C/D verbatim from CONTEXT.md; reviewers focus on §2 (architecture deltas) and §4 (risk register).
2. **Kuzu backend support for `get_entity_by_id`** — issue #178 (Kuzu SIGSEGV) is open; if Kuzu corrupts during testing, Plan 03 cannot prove the multi-backend path. Mitigation: ship 503 response when GraphRAG store is unhealthy; document `graphrag.store_type: simple` as the operator workaround; cite #178 in the design doc's risk register (per CONTEXT.md specifics).
3. **`get_chunk_by_id` performance regression on Postgres** — Postgres backend lookup must be O(1) via primary-key index. If the chunks table lacks an index on `chunk_id`, lookups are O(n) on large corpora. Mitigation: Plan 02 includes a Postgres-backend test that asserts <50ms lookup on a 10k-chunk fixture; add `CREATE INDEX` if needed.
4. **Sandbox false-negatives** — denying legitimate reads inside indexed roots. Mitigation: Plan 04 includes a positive-test corpus (allowed read inside `folders.list()` root canonicalized to absolute path) and a negative-test corpus (symlink escape, `.env`, oversized file, path outside roots). Default-deny posture is conservative; expansion can land in v3 if user feedback demands.
5. **Embeddings accidentally included in `ChunkRecord`** — per decision C, embeddings are excluded (large + rarely needed). Mitigation: Plan 02's Pydantic model explicitly omits the embedding field; test asserts `embedding` key is not present in the response payload.
6. **Forward-compatibility with #179 (Bearer-token auth)** — if #179 merges mid-v10.2, the new endpoints inherit an opt-in auth surface that wasn't planned for. Mitigation: Plan 01 design doc calls this out explicitly in "Future / Related Work" (per CONTEXT.md specifics); endpoints follow existing router patterns so middleware applies uniformly.

---
*Phase plan generated: 2026-06-02*
