# Plan 03 Summary: GET /graph/entity/{type}/{id} endpoint

**Phase:** 50 — Server endpoint prep + v2 design doc
**Requirement:** prerequisite for URI-02 (Phase 51)
**Status:** Complete
**Commits:** 91038ad, f53b61e, 1d22395, 3b5d62b
**Date:** 2026-06-02

## What was built

Shipped `GET /graph/entity/{entity_type}/{entity_id}` on `agent-brain-server`, returning a v2-spec `GraphEntityRecord` (entity + 1-hop incoming/outgoing neighbors) backed by a new `GraphStoreManager.get_entity_by_id(type, id) -> GraphEntityRecord | None` primitive that drives both `SimplePropertyGraphStore` and `KuzuPropertyGraphStore` through the shared LlamaIndex `PropertyGraphStore` contract. The router validates `entity_type` against the SCHEMA-01 `ENTITY_TYPES` vocabulary (no parallel list maintained) and exposes four status codes per CONTEXT decision B: `200` on hit, `503 graphrag_disabled` when GraphRAG is off, `503 kuzu_unavailable` when the Kuzu backend raises a corruption signature (#178), `400 invalid_entity_type` with the canonical `valid_types` list, and `404 entity_not_found` when the type is valid but no matching entity exists.

The Kuzu backend has a known LlamaIndex-integration quirk: `get_triplets` and `get_rel_map` return outgoing-only edges with unreliable `Relation.source_id`/`target_id`. To preserve the locked wire shape (both incoming and outgoing neighbors), the manager drops down to direct parameterized Cypher for incoming edges when `store_type == "kuzu"` — the entire Cypher path is wrapped in the same broad-exception → `KuzuUnavailableError` guard so a SIGSEGV-adjacent failure still surfaces as 503 rather than crashing the server.

## Files Modified

| File                                                                       | Action   | Notes |
|----------------------------------------------------------------------------|----------|-------|
| `agent-brain-server/agent_brain_server/models/graph.py`                    | modified | Added `GraphEntityRecord`, `GraphEntityRecordNode`, `GraphEntityRecordNeighbor`, `GraphEntityRecordNeighbors` (v2 wire shape) |
| `agent-brain-server/agent_brain_server/models/__init__.py`                 | modified | Exported the four new models |
| `agent-brain-server/agent_brain_server/storage/graph_store.py`             | modified | Added `KuzuUnavailableError`, `get_entity_by_id(type, id)`, helpers `_label_of`/`_id_of`, and a Kuzu-specific Cypher fallback for incoming edges |
| `agent-brain-server/agent_brain_server/api/routers/graph.py`               | created  | New router with `GET /graph/entity/{entity_type}/{entity_id}` |
| `agent-brain-server/agent_brain_server/api/routers/__init__.py`            | modified | Re-exported `graph_router` |
| `agent-brain-server/agent_brain_server/api/main.py`                        | modified | Registered `graph_router` under `/graph` prefix |
| `agent-brain-server/tests/unit/storage/test_get_entity_by_id.py`           | created  | Parametrized contract suite across SimplePropertyGraphStore + Kuzu (skip-if-unavailable) + KuzuUnavailableError sentinel tests |
| `agent-brain-server/tests/unit/api/test_graph_entity_endpoint.py`          | created  | FastAPI TestClient suite covering all four response paths, URL-encoded path components, and OpenAPI schema |

## Verification

- [x] Black format check passed (`poetry run black --check agent_brain_server tests` — 192 files unchanged)
- [x] Ruff lint check passed (`poetry run ruff check agent_brain_server tests` — All checks passed)
- [x] mypy strict check passed (`poetry run mypy agent_brain_server` — 84 source files, no issues)
- [x] pytest passed (`poetry run pytest -x` — 1269 passed, 28 skipped; 25 new tests under this plan: 13 contract + 12 endpoint)
- [x] Contract test run: 13 passed across SimplePropertyGraphStore (8) and Kuzu (5).
- [x] Endpoint integration run: 12 passed (200/503-disabled/503-kuzu/400/404 + URL-decoding + OpenAPI).

### Verification matrix

| Check          | Command                                              | Result                       |
|----------------|------------------------------------------------------|------------------------------|
| Format         | `poetry run black --check agent_brain_server tests`  | PASS                         |
| Lint           | `poetry run ruff check agent_brain_server tests`     | PASS                         |
| Types (strict) | `poetry run mypy agent_brain_server`                 | PASS                         |
| Tests          | `poetry run pytest -x -q`                            | PASS (1269 / 28 skipped)     |

## Design notes / Deviations

- **`GraphEntityRecord` is sibling-named, not a replacement for the legacy `GraphEntity`.** The existing `models/graph.py` already has a `GraphEntity` Pydantic class used by the extraction pipeline with a different shape (`name`, `entity_type`, `source_chunk_ids`, scoped properties). To avoid touching extraction call sites in this plan, the v2 endpoint models are introduced as a parallel set: `GraphEntityRecord` (top-level), `GraphEntityRecordNode` (entity payload), `GraphEntityRecordNeighbor`, `GraphEntityRecordNeighbors`. A future plan can converge the two if/when the extraction surface migrates to the v2 vocabulary.
- **Single implementation drives both backends through the LlamaIndex `PropertyGraphStore` ABC.** `SimplePropertyGraphStore` and `KuzuPropertyGraphStore` both inherit `PropertyGraphStore`, so `store.get(ids=[id])` and `store.get_triplets(ids=[id])` work uniformly for the primary path. No per-backend protocol branching in `get_entity_by_id` for the "happy" path.
- **Kuzu-specific Cypher fallback for incoming edges.** Investigation revealed that `llama-index-graph-stores-kuzu` 0.9.x (kuzu 0.11.x) returns **outgoing-only** triplets from both `get_triplets()` and `get_rel_map()`, and `Relation.source_id`/`target_id` inside Kuzu's returned tuples are unreliable (both fields set to the target name). To preserve the locked wire contract (both incoming and outgoing neighbors visible), the manager runs a direct parameterized Cypher `MATCH (n)-[r]->(m {id: $tid}) RETURN n.id, n.label, n.name, r` against `self._kuzu_db` when `store_type == "kuzu"`. The entire Cypher path is wrapped in the same `(IndexError, RuntimeError, OSError)` → `KuzuUnavailableError` guard as the rest of the Kuzu calls, so a corruption mid-Cypher still surfaces as 503 rather than crashing.
- **Kuzu does NOT preserve custom `Relation.properties`.** The current Kuzu schema only persists the predicate as a `label` property — caller-supplied keys like `source_chunk_id` are dropped. The contract test conditions the property assertion on `manager.store_type != "kuzu"` and documents this as a backend-level limitation. SimplePropertyGraphStore preserves relation properties intact.
- **503 `graphrag_disabled` checked BEFORE 400 `invalid_entity_type`.** Decision B specifies disabled-state is a distinct error code; the router pre-empts the type-validation branch so the body doesn't leak "your type is valid but graphrag is off" vs "your type is bogus". One integration test pins this ordering explicitly.
- **`_VALID_ENTITY_TYPES` is sourced from `ENTITY_TYPES` (single source of truth).** The router imports `ENTITY_TYPES` from `agent_brain_server.models` and freezes it at module import time. SCHEMA-01 vocabulary drift (e.g. a future 18th type) automatically flows through both the 400 body and the test that asserts `set(valid_types) == set(ENTITY_TYPES)`. The current test also pins `len(ENTITY_TYPES) == 17` so the drift is visible in the diff when the schema grows.
- **Lazy-init the graph manager on first request.** In production the server's `lifespan` runs a Kuzu preflight (`get_graph_store_manager().preflight_check()`). For simple-store deployments that skip the preflight, the router calls `mgr.initialize()` itself if `not mgr.is_initialized` — wrapped in the same `KuzuUnavailableError` translation so a Kuzu blow-up during init still returns 503, not 500.
- **No OpenAPI export script committed.** Same posture as Plan 02: the spec is served live at `/openapi.json` and the new route + its four nested models appear in `app.openapi()["components"]["schemas"]`. The endpoint integration test pins this contract (`TestOpenAPI` class). No standalone `docs/api/openapi.json` exists in the repo.
- **Tests landed under `tests/unit/storage/` and `tests/unit/api/`** (matching the codebase's established locations for contract and endpoint tests). The plan suggested `tests/storage/` and `tests/api/` — functionally equivalent, but `tests/unit/` is where the existing fixtures live so we keep co-location.

### #178 Kuzu SIGSEGV handling — explicit notes

The Kuzu SIGSEGV risk (R1 in the design doc's risk register) is handled in three layers, all converging on `503 kuzu_unavailable`:

1. **`KuzuUnavailableError`** — module-level sentinel in `agent_brain_server.storage.graph_store`. Raised by `get_entity_by_id` whenever Kuzu raises `IndexError`, `RuntimeError`, or `OSError` (the pybind11 / catalog-corruption signatures observed in #178) from any of `store.get(ids=...)`, `store.get_triplets(ids=...)`, or the Cypher fallback `conn.execute(...)` / `result.get_next()`.
2. **Backend-conditional behavior.** SimplePropertyGraphStore does NOT trigger the sentinel even if it raises one of those exception types — the simple backend has no corruption mode, so we degrade to `None` and log a warning. This avoids spurious 503s if an unrelated bug surfaces in the simple backend.
3. **Router translation.** `api/routers/graph.py` catches `KuzuUnavailableError` from both the lazy-init path (`mgr.initialize()`) and the lookup path (`mgr.get_entity_by_id(...)`) and translates each to `503 {"error": "kuzu_unavailable", "hint": "...set graphrag.store_type=simple..."}`. The hint cites the operator workaround verbatim so on-call has the fix in front of them.

Two contract tests pin the sentinel-raising behavior (one each for the `get` and `get_triplets` failure modes), and two endpoint tests pin the 503 translation (lookup-time and init-time). The end-to-end story: a #178 SIGSEGV during a `/graph/entity/...` request returns a 503 with a usable hint, the server keeps running, the operator switches `graphrag.store_type` to `simple` in config, and reads recover without process restart.

### Auto-fixed deviations

- **[Rule 3 – Blocking] Plan suggested entity_names disambiguation in tests, but the backend collapses by name.** The plan's contract spec implies two entities with same name + different labels can coexist. SimplePropertyGraphStore uses `name` as the node id, so adding `(AuthService, Function)` after `(AuthService, Class)` overwrites the first. Test fixture topology adjusted to use unique names per entity. The router still correctly rejects "right name, wrong type" via the post-fetch `_label_of(n) == entity_type` filter — see test `test_missing_entity_returns_none`.
- **[Rule 1 – Bug] Kuzu's get_rel_map() also returns outgoing-only.** Initial impl assumed `get_rel_map` would close the incoming-edge gap left by `get_triplets`. Empirical Kuzu probe showed both methods are outgoing-only. Replaced the `get_rel_map` fallback with direct parameterized Cypher. Added a comment block in `get_entity_by_id` documenting the Kuzu library quirk for future maintainers.

## Self-Check: PASSED

- Created files exist:
  - `agent-brain-server/agent_brain_server/api/routers/graph.py` — FOUND
  - `agent-brain-server/tests/unit/storage/test_get_entity_by_id.py` — FOUND
  - `agent-brain-server/tests/unit/api/test_graph_entity_endpoint.py` — FOUND
- Commit hashes exist in the working branch's `git log --oneline`:
  - `91038ad` feat(50-03): add GraphEntityRecord model + get_entity_by_id on graph store
  - `f53b61e` feat(50-03): add GET /graph/entity/{type}/{id} endpoint with 503/400/404
  - `1d22395` test(50-03): parametrized contract tests + Kuzu incoming-edge fallback
  - `3b5d62b` test(50-03): FastAPI integration tests for graph-entity endpoint
