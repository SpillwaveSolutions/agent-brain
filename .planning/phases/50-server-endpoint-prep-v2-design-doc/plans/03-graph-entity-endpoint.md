# Plan 03: `GET /graph/entity/{type}/{id}` endpoint + `get_entity_by_id` on graph store

**Phase:** 50 — Server endpoint prep + v2 design doc
**Requirements covered:** URI-02 prerequisite (URI-02 itself lands in Phase 51)
**Depends on:** Plan 01 (v2 design doc must land first — locked response shape is in §2)
**Parallel-safe with:** Plans 02, 04

**Status:** Not started

## Goal

Add `GET /graph/entity/{type}/{id}` to `agent-brain-server` for entity + 1-hop neighbor lookup. The endpoint returns the entity's properties plus its incoming and outgoing relationships — the data needed for the MCP `graph-entity://<type>/<id>` resource scheme (URI-02) that lands in Phase 51.

The lookup primitive is a new `get_entity_by_id(type, id)` method on the graph store interface, implemented by both Kuzu and `SimplePropertyGraphStore` backends. The endpoint validates the entity type against the 17 valid types from SCHEMA-01 and returns structured errors for GraphRAG-disabled state (503), unknown type (400), and entity-not-found (404).

## Acceptance Criteria

- [ ] Graph store interface (`agent_brain_server/storage/graph_store.py`) declares `async def get_entity_by_id(self, entity_type: str, entity_id: str) -> GraphEntityRecord | None`
- [ ] `SimplePropertyGraphStore` backend implements `get_entity_by_id` returning `(entity, neighbors)` (None when entity doesn't exist)
- [ ] `Kuzu` backend implements `get_entity_by_id` (gracefully degrades to 503 if Kuzu is unhealthy — see #178 risk)
- [ ] New Pydantic response model `GraphEntityRecord` in `agent_brain_server/models/graph.py` (create file if it doesn't exist) with the shape locked in Plan 01 design doc §2:
  ```
  {
    "entity": { "type": str, "id": str, "properties": {...} },
    "neighbors": {
      "incoming": [{ "type": str, "id": str, "predicate": str, "properties": {...} }, ...],
      "outgoing": [{ "type": str, "id": str, "predicate": str, "properties": {...} }, ...]
    }
  }
  ```
- [ ] New route `GET /graph/entity/{entity_type}/{entity_id}` exists in a new `api/routers/graph.py` (or `api/routers/graph_entity.py` — planner's call); registered in `api/main.py`
- [ ] Route returns `200 GraphEntityRecord` on success (entity + 1-hop neighbors)
- [ ] Route returns `503 {"error": "graphrag_disabled", "hint": "set graphrag.enabled = true in config to enable graph-entity addressing"}` when GraphRAG is not enabled in config (CONTEXT.md decision B; **distinct from 404**)
- [ ] Route returns `400 {"error": "invalid_entity_type", "type": "...", "valid_types": [...]}` when `entity_type` is not in the 17 valid types from SCHEMA-01 (CONTEXT.md decision B)
- [ ] Route returns `404 {"error": "entity_not_found", "type": "...", "id": "..."}` when the type is valid but the entity doesn't exist
- [ ] The 17 valid entity types are sourced from the existing schema vocabulary (SCHEMA-01) — do **not** hardcode a separate list; import or reference the canonical literal types
- [ ] No authentication required (matches v1 stance; auth is v4 work)
- [ ] Contract test `tests/storage/test_get_entity_by_id.py` parametrized across `SimplePropertyGraphStore` (always) and Kuzu (skip-if-unavailable per #178 risk) asserts: existing entity returns full payload with 1-hop neighbors; missing entity returns None; entity-with-zero-neighbors returns empty incoming/outgoing arrays (not None)
- [ ] Integration test `tests/api/test_graph_entity_endpoint.py` asserts all four response paths: 200 success; 503 GraphRAG-disabled; 400 invalid type; 404 entity-not-found
- [ ] Test for type-validation: `assert set(valid_types) == set(SCHEMA-01 entity types)` — uses the same source of truth as the rest of the codebase
- [ ] OpenAPI schema regenerated; `graph_entity_record` model appears in the spec
- [ ] `task before-push` passes: Black, Ruff, mypy (strict), pytest with coverage ≥50%

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-server/agent_brain_server/storage/graph_store.py` | modify | Add `async def get_entity_by_id(self, entity_type: str, entity_id: str)` to the interface and both backend implementations |
| `agent-brain-server/agent_brain_server/models/graph.py` | create (or modify if exists) | New `GraphEntityRecord` Pydantic model with `entity` + `neighbors` shape from Plan 01 §2 |
| `agent-brain-server/agent_brain_server/api/routers/graph.py` | create | New router with `GET /graph/entity/{entity_type}/{entity_id}` route |
| `agent-brain-server/agent_brain_server/api/main.py` | modify | Register the new graph router via `app.include_router(...)` (around the existing router block) |
| `agent-brain-server/agent_brain_server/config/settings.py` | check | Confirm `graphrag.enabled` setting exists; if not, the 503 path needs a different source of truth (could be inferred from `graph_store is None` or similar) — planner decides |
| `agent-brain-server/tests/storage/test_get_entity_by_id.py` | create | Parametrized contract test across both graph backends |
| `agent-brain-server/tests/api/test_graph_entity_endpoint.py` | create | FastAPI integration test for all four response paths |
| `docs/api/openapi.json` (if committed) | modify | Regenerate after route is added |

## Implementation Steps

1. **Re-read Plan 01 design doc §2** for the `GraphEntityRecord` locked shape. The design doc wins over CONTEXT.md decision B if they disagree.

2. **Locate the SCHEMA-01 entity-type vocabulary.** Grep for where the 17 entity types are defined (`grep -rn "Literal\[" agent-brain-server/agent_brain_server/ | grep -i entity` is a good start — SCHEMA-01 used Literal types per the Key Decisions in PROJECT.md). Import or reuse this vocabulary in the new router — do not maintain a parallel list.

3. **Define `GraphEntityRecord` Pydantic models.** In `models/graph.py` (create file or extend existing):
   ```python
   class GraphEntity(BaseModel):
       type: str  # SCHEMA-01 entity type
       id: str
       properties: dict[str, Any]

   class GraphNeighbor(BaseModel):
       type: str       # neighbor entity type
       id: str         # neighbor entity id
       predicate: str  # relationship predicate (SCHEMA-03)
       properties: dict[str, Any]

   class GraphNeighbors(BaseModel):
       incoming: list[GraphNeighbor]
       outgoing: list[GraphNeighbor]

   class GraphEntityRecord(BaseModel):
       entity: GraphEntity
       neighbors: GraphNeighbors
   ```

4. **Extend graph store interface.** In `storage/graph_store.py`, add the abstract method:
   ```python
   async def get_entity_by_id(
       self, entity_type: str, entity_id: str
   ) -> GraphEntityRecord | None:
       """Fetch an entity by (type, id) with its 1-hop neighbors.

       Returns None when the entity does not exist.
       Implementations must populate both incoming and outgoing neighbor lists
       (empty lists when no neighbors exist; never None).
       """
       ...
   ```

5. **Implement on `SimplePropertyGraphStore`.** Use the existing LlamaIndex `SimplePropertyGraphStore` API to:
   - Look up the node by `(type, id)` → entity properties
   - Get relationships where the node is the subject (outgoing) and where it's the object (incoming)
   - Map each to `GraphNeighbor`
   - Wrap in `GraphEntityRecord`
   - Return `None` if the node is not found

6. **Implement on `Kuzu` backend.** Use Cypher-style queries (Kuzu supports them). Roughly:
   ```cypher
   MATCH (n:{type} {id: $id}) RETURN n;
   MATCH (n:{type} {id: $id})<-[r]-(neighbor) RETURN r, neighbor;
   MATCH (n:{type} {id: $id})-[r]->(neighbor) RETURN r, neighbor;
   ```
   Catch Kuzu exceptions (especially SIGSEGV-adjacent runtime errors per #178) and propagate as a marker the router can translate to 503. **Do not** crash the server process.

7. **Add the FastAPI route.** In `api/routers/graph.py`:
   ```python
   router = APIRouter(prefix="/graph", tags=["graph"])

   @router.get("/entity/{entity_type}/{entity_id}", response_model=GraphEntityRecord)
   async def get_graph_entity(
       entity_type: str,
       entity_id: str,
       settings: Settings = Depends(get_settings),
       graph: GraphStore | None = Depends(get_graph_store),
   ) -> GraphEntityRecord:
       # 503: GraphRAG not enabled
       if not settings.graphrag.enabled or graph is None:
           raise HTTPException(status_code=503, detail={
               "error": "graphrag_disabled",
               "hint": "set graphrag.enabled = true in config to enable graph-entity addressing",
           })
       # 400: invalid entity type
       if entity_type not in VALID_ENTITY_TYPES:
           raise HTTPException(status_code=400, detail={
               "error": "invalid_entity_type",
               "type": entity_type,
               "valid_types": sorted(VALID_ENTITY_TYPES),
           })
       # 200 / 404
       record = await graph.get_entity_by_id(entity_type, entity_id)
       if record is None:
           raise HTTPException(status_code=404, detail={
               "error": "entity_not_found",
               "type": entity_type,
               "id": entity_id,
           })
       return record
   ```
   `VALID_ENTITY_TYPES` is imported from the SCHEMA-01 vocabulary (step 2).

8. **Register the router in `api/main.py`.** Add `app.include_router(graph.router)` next to the existing router includes.

9. **Write parametrized contract test.** In `tests/storage/test_get_entity_by_id.py`, parametrize across `SimplePropertyGraphStore` (always-on) and Kuzu (skip-if-unavailable). Cases per backend:
   - Existing entity with neighbors → full `GraphEntityRecord` payload; `incoming` and `outgoing` populated
   - Existing entity with zero neighbors → `incoming == []` and `outgoing == []` (empty list, **not None**)
   - Missing entity → `None`
   - Field-set assertion on `GraphEntityRecord`

10. **Write FastAPI integration test.** In `tests/api/test_graph_entity_endpoint.py`, all four response paths:
    - **200:** GraphRAG enabled, valid type, existing entity → 200 with full payload
    - **503:** GraphRAG disabled → 503 with `error: "graphrag_disabled"` and `hint`
    - **400:** GraphRAG enabled, invalid type → 400 with `error: "invalid_entity_type"`, the invalid `type`, and a `valid_types` list whose length matches the SCHEMA-01 vocabulary
    - **404:** GraphRAG enabled, valid type, nonexistent id → 404 with `error: "entity_not_found"`

11. **Regenerate OpenAPI** and commit the spec.

12. **Run `task before-push` until green.**

## Verification

- **Contract test:** `cd agent-brain-server && poetry run pytest tests/storage/test_get_entity_by_id.py -v` passes for SimplePropertyGraphStore; Kuzu test skips gracefully if Kuzu is not installed or unhealthy.
- **Integration test:** `cd agent-brain-server && poetry run pytest tests/api/test_graph_entity_endpoint.py -v` passes all four response paths.
- **Manual curl smoke test** (GraphRAG-enabled config, indexed corpus with entities):
  ```bash
  # GraphRAG-enabled mode
  agent-brain start
  # find a real entity from a graph query
  ENTITY=$(curl -s -X POST http://127.0.0.1:8000/query/ \
    -H "content-type: application/json" \
    -d '{"query": "test", "mode": "graph", "k": 1}' | jq -r '.results[0].entity_type + "/" + .results[0].entity_id')
  curl -s "http://127.0.0.1:8000/graph/entity/$ENTITY" | jq .
  # expect: { "entity": {...}, "neighbors": {"incoming": [...], "outgoing": [...]} }

  # 400 path: invalid type
  curl -i http://127.0.0.1:8000/graph/entity/NotARealType/foo
  # expect: HTTP/1.1 400; body lists valid_types

  # 404 path: valid type, missing id
  curl -i http://127.0.0.1:8000/graph/entity/Function/does-not-exist
  # expect: HTTP/1.1 404; body has error: "entity_not_found"
  agent-brain stop

  # GraphRAG-disabled smoke (separately, with graphrag.enabled = false)
  # ... start with graph disabled ...
  curl -i http://127.0.0.1:8000/graph/entity/Function/anything
  # expect: HTTP/1.1 503; body has error: "graphrag_disabled" and hint
  ```
- **OpenAPI smoke:** `jq '.paths."/graph/entity/{entity_type}/{entity_id}"' docs/api/openapi.json` returns the new path definition.
- **Pre-push gate:** `task before-push` exits 0. Coverage stays ≥50%.

## Risk Notes

- **Risk: Kuzu SIGSEGV (#178).** Per CONTEXT.md specifics, the design doc must cite #178 in its risk register. If Kuzu crashes during a `get_entity_by_id` call, the endpoint must return 503 (not crash the server). Catch broad exceptions in the Kuzu implementation; surface as a sentinel the router translates to 503. Operator workaround: `graphrag.store_type: simple`.
- **Risk: SCHEMA-01 vocabulary drift.** If the test hardcodes 17 entity types and SCHEMA-01 later adds an 18th, the test breaks before the endpoint does. Mitigation: derive `VALID_ENTITY_TYPES` and the test fixture from the **same** source of truth (the SCHEMA-01 Literal types).
- **Risk: 1-hop neighbor explosion.** A hub entity with 10k neighbors returns a 10k-element response. v2 ships without pagination — document in the design doc that deep traversal and neighbor pagination are deferred to v3. If real corpora produce >1k neighbors per entity, consider capping at 100 per direction with a `truncated: true` marker (planner can decide; if added, surface in the design doc).
- **Risk: `graphrag.enabled` setting may not exist.** Check `config/settings.py` first. If GraphRAG-enabled state is not a single boolean but derived (e.g., from `graphrag.store_type != "none"`), use the existing convention. The 503 trigger should match how the rest of the codebase decides GraphRAG is on.
- **Risk: dependency-injection seam for graph store.** The existing query service may instantiate the graph store internally rather than expose it as a FastAPI dependency. May need to add a `get_graph_store()` dependency function next to `get_storage_backend()`. Follow the established pattern in `api/routers/query.py`.
- **Risk: GraphRAG-only-on-ChromaDB constraint.** Per PROJECT.md Key Decisions, "GraphRAG stays ChromaDB-only" — the Postgres backend does not have GraphRAG. The 503 path naturally handles this (Postgres backends have `graph is None`), but verify this is the existing behavior before assuming.

---
*Plan 03 of Phase 50*
