# Plan 02: `GET /query/chunk/{id}` endpoint + `get_chunk_by_id` on `StorageBackendProtocol`

**Phase:** 50 — Server endpoint prep + v2 design doc
**Requirements covered:** URI-01 prerequisite (URI-01 itself lands in Phase 51)
**Depends on:** Plan 01 (v2 design doc must land first — locked response shape is in §2)
**Parallel-safe with:** Plans 03, 04
**Status:** Not started

## Goal

Add `GET /query/chunk/{id}` to `agent-brain-server` for O(1) chunk lookup. The endpoint returns a single chunk's content + metadata (no embeddings) keyed by `chunk_id`. This is the server-side prerequisite for the MCP `chunk://<chunk_id>` resource scheme (URI-01) that lands in Phase 51.

The lookup primitive is a new `get_chunk_by_id(chunk_id)` method on `StorageBackendProtocol`, implemented by both the ChromaDB and Postgres backends. This follows the v6.0 storage abstraction pattern — protocol-level contract tests give cross-backend behavior coverage for free.

## Acceptance Criteria

- [ ] `StorageBackendProtocol` declares `async def get_chunk_by_id(self, chunk_id: str) -> ChunkRecord | None` in `agent-brain-server/agent_brain_server/storage/protocol.py`
- [ ] `ChromaBackend.get_chunk_by_id` (in `agent_brain_server/storage/chroma/backend.py`) returns the chunk by primary-key lookup against the underlying ChromaDB collection; returns `None` if not found
- [ ] `PostgresBackend.get_chunk_by_id` (in `agent_brain_server/storage/postgres/backend.py`) returns the chunk by primary-key SQL lookup on the `chunks` table; returns `None` if not found
- [ ] Postgres chunks table has an index on `chunk_id` ensuring O(1) lookup (verify in schema init; add migration / `CREATE INDEX IF NOT EXISTS` if missing)
- [ ] New Pydantic response model `ChunkRecord` exists in `agent_brain_server/models/query.py` (or `models/chunks.py` if planner prefers a new file) with exactly the fields locked in Plan 01's design doc §2: `chunk_id`, `parent_doc_id`, `source`, `content`, `summary` (optional), `folder_id`, `token_count`, `language` (optional). **No `embedding` field.**
- [ ] New route `GET /query/chunk/{chunk_id}` exists (either added to `api/routers/query.py` or a new `api/routers/chunks.py` — planner's call; if new file, register it in `api/main.py`)
- [ ] Route returns `200 ChunkRecord` on success
- [ ] Route returns `404 {"error": "chunk_not_found", "chunk_id": "..."}` when `get_chunk_by_id` returns `None` (proper HTTP status code, not 200-with-found-false per CONTEXT.md decision C)
- [ ] Response payload includes all fields from `ChunkRecord` and **does not** include an `embedding` key (verified by test)
- [ ] No authentication required (matches v1 stance per CONTEXT.md decision C; auth is v4 work)
- [ ] Contract test `tests/storage/test_get_chunk_by_id.py` parametrized across ChromaDB + Postgres backends asserts: existing-id returns ChunkRecord; missing-id returns None; ChunkRecord field set matches design doc
- [ ] Integration test `tests/api/test_chunk_endpoint.py` asserts: 200 with full payload for a real chunk; 404 with structured error body for missing id; payload omits `embedding` key
- [ ] Performance assertion on Postgres: lookup completes in <50ms on a fixture corpus with ≥1,000 chunks (one test using `pytest.mark.timeout` or `time.perf_counter`); skipped without DB
- [ ] OpenAPI schema regenerated; `chunk_record` model appears in `docs/api/openapi.json` (or wherever the spec is committed)
- [ ] `task before-push` passes: Black, Ruff, mypy (strict), pytest with coverage ≥50%

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-server/agent_brain_server/storage/protocol.py` | modify | Add `async def get_chunk_by_id(self, chunk_id: str) -> ChunkRecord \| None` to protocol |
| `agent-brain-server/agent_brain_server/storage/chroma/backend.py` | modify | Implement `get_chunk_by_id` using ChromaDB `collection.get(ids=[chunk_id])` |
| `agent-brain-server/agent_brain_server/storage/postgres/backend.py` | modify | Implement `get_chunk_by_id` via SQLAlchemy `SELECT ... WHERE chunk_id = :id LIMIT 1`; ensure index exists |
| `agent-brain-server/agent_brain_server/storage/postgres/schema.py` (or wherever `CREATE TABLE chunks` lives) | modify | Add `CREATE INDEX IF NOT EXISTS idx_chunks_chunk_id ON chunks(chunk_id)` if not already present |
| `agent-brain-server/agent_brain_server/models/query.py` | modify | Add `ChunkRecord` Pydantic model with the locked field set from Plan 01 §2 |
| `agent-brain-server/agent_brain_server/api/routers/query.py` | modify | Add `GET /query/chunk/{chunk_id}` route handler that calls the active backend's `get_chunk_by_id` |
| `agent-brain-server/tests/storage/test_get_chunk_by_id.py` | create | Parametrized contract test across both backends |
| `agent-brain-server/tests/api/test_chunk_endpoint.py` | create | FastAPI integration test for the new route |
| `docs/api/openapi.json` (if it's committed; otherwise regenerated at start) | modify | Regenerate after route is added |

## Implementation Steps

1. **Re-read Plan 01's design doc §2** to confirm the exact field set for `ChunkRecord`. If the design doc commits to additional or different fields than CONTEXT.md decision C, the design doc wins (it's the locked contract).

2. **Add the Pydantic `ChunkRecord` model.** In `agent_brain_server/models/query.py`:
   ```python
   class ChunkRecord(BaseModel):
       chunk_id: str
       parent_doc_id: str
       source: str  # absolute file path
       content: str
       summary: str | None = None
       folder_id: str
       token_count: int
       language: str | None = None  # for code chunks
   ```
   No `embedding` field. Add a docstring citing the design doc.

3. **Extend `StorageBackendProtocol`.** In `storage/protocol.py`, add the method signature near the existing `delete_by_ids` (line 329) so the related primitives sit together:
   ```python
   async def get_chunk_by_id(self, chunk_id: str) -> ChunkRecord | None:
       """O(1) lookup of a single chunk by primary key. None when not found."""
       ...
   ```

4. **Implement `ChromaBackend.get_chunk_by_id`.** Use `collection.get(ids=[chunk_id], include=["documents", "metadatas"])`. Map the result (or empty result) to `ChunkRecord | None`. Embeddings are **not** requested. Reference `services/chunk_eviction_service.py` for the existing ChromaDB lookup pattern (it does `delete_by_ids` against the same collection).

5. **Implement `PostgresBackend.get_chunk_by_id`.** Use the existing async SQLAlchemy session. SQL roughly:
   ```sql
   SELECT chunk_id, parent_doc_id, source, content, summary,
          folder_id, token_count, language
   FROM chunks
   WHERE chunk_id = :id
   LIMIT 1;
   ```
   Map row → `ChunkRecord` or return `None`. **Do not** select the `embedding` column even if it exists in the table.

6. **Ensure Postgres index exists.** Inspect the existing schema-init code (probably `storage/postgres/schema.py` or similar). If `chunk_id` is not already a primary key or doesn't have an index, add `CREATE INDEX IF NOT EXISTS idx_chunks_chunk_id ON chunks(chunk_id);` to the schema init. (If `chunk_id` is already the PK, no action needed — PKs have implicit indexes.)

7. **Add the FastAPI route.** In `api/routers/query.py`, add:
   ```python
   @router.get("/chunk/{chunk_id}", response_model=ChunkRecord)
   async def get_chunk(
       chunk_id: str,
       storage: StorageBackendProtocol = Depends(get_storage_backend),
   ) -> ChunkRecord:
       record = await storage.get_chunk_by_id(chunk_id)
       if record is None:
           raise HTTPException(
               status_code=404,
               detail={"error": "chunk_not_found", "chunk_id": chunk_id},
           )
       return record
   ```
   Follow the existing dependency-injection pattern (look at the `POST /query/` handler in the same file).

8. **Write parametrized contract test.** In `tests/storage/test_get_chunk_by_id.py`, parametrize across both backends (follow the v6.0 contract-test pattern — `pytest.mark.parametrize` with backend fixtures, skip Postgres without DB). Three cases per backend:
   - Existing chunk → ChunkRecord with full field set; `embedding` is not an attribute
   - Missing chunk → None
   - Field-set assertion: `set(record.model_dump().keys()) == {expected set from design doc §2}`

9. **Write FastAPI integration test.** In `tests/api/test_chunk_endpoint.py`, using FastAPI `TestClient` and a mocked or fixture-backed storage:
   - 200 path: GET `/query/chunk/{known_id}` → response status 200 and body matches `ChunkRecord` shape; `"embedding"` not in response keys
   - 404 path: GET `/query/chunk/nonexistent-id` → response status 404 and body has `error: "chunk_not_found"` and `chunk_id: "nonexistent-id"`

10. **Add Postgres performance test.** In the contract test (or a separate `test_get_chunk_by_id_perf.py`), with a 1k-chunk Postgres fixture: assert `await backend.get_chunk_by_id(known_id)` completes in <50ms (use `time.perf_counter`). Skip if Postgres unavailable.

11. **Regenerate OpenAPI.** Run whatever the project's OpenAPI export script is (check `Taskfile.yml` or `scripts/`). Commit the regenerated spec.

12. **Run `task before-push` until green.** Fix any Black / Ruff / mypy issues. Fix any test failures.

## Verification

- **Contract test:** `cd agent-brain-server && poetry run pytest tests/storage/test_get_chunk_by_id.py -v` passes for both backends (ChromaDB always; Postgres skipped without DB).
- **Integration test:** `cd agent-brain-server && poetry run pytest tests/api/test_chunk_endpoint.py -v` passes.
- **Manual curl smoke test** (with a running server and an indexed corpus):
  ```bash
  agent-brain start
  # find a real chunk_id from a query
  CHUNK_ID=$(curl -s -X POST http://127.0.0.1:8000/query/ \
    -H "content-type: application/json" \
    -d '{"query": "test", "k": 1}' | jq -r '.results[0].chunk_id')
  # the new endpoint
  curl -s http://127.0.0.1:8000/query/chunk/$CHUNK_ID | jq .
  # expect: ChunkRecord JSON with content, source, chunk_id, etc.; NO "embedding" key
  curl -i http://127.0.0.1:8000/query/chunk/does-not-exist
  # expect: HTTP/1.1 404 Not Found; body: {"detail": {"error": "chunk_not_found", "chunk_id": "does-not-exist"}}
  agent-brain stop
  ```
- **OpenAPI smoke:** `jq '.paths."/query/chunk/{chunk_id}"' docs/api/openapi.json` (or wherever the spec is) returns the new path definition.
- **Pre-push gate:** `task before-push` exits 0. Coverage stays ≥50%.

## Risk Notes

- **Risk: ChromaDB `collection.get(ids=...)` semantics.** Verify whether the underlying ChromaDB API requires `include=[...]` to avoid pulling embeddings (which we don't want). Check the existing eviction service for the established pattern. If embeddings are pulled by default, explicitly pass `include=["documents", "metadatas"]`.
- **Risk: chunk-id collision across folders.** If `chunk_id` is not globally unique, lookup may be ambiguous. Verify against the existing chunk-id generation logic (probably in `indexing/`). If chunk-ids are folder-scoped, the endpoint signature may need `{folder_id}/{chunk_id}` — surface this in the plan-01 design doc before implementing.
- **Risk: Postgres `chunks` table column names drift.** If the actual column name is `id` rather than `chunk_id`, adjust the SELECT and the `idx_chunks_chunk_id` name accordingly. Check `storage/postgres/schema.py` first.
- **Risk: response model exposes internal columns.** Postgres `chunks` may have internal columns (`created_at`, `updated_at`, `embedding`). Map explicitly — do not use `SELECT *` then `model_validate(row.__dict__)`.
- **Risk: dependency-injection mismatch.** The existing query router may inject a `QueryService` rather than `StorageBackendProtocol` directly. Adjust to use whichever pattern is established; if going through a service is cleaner, add `QueryService.get_chunk_by_id` as a thin pass-through.

---
*Plan 02 of Phase 50*
