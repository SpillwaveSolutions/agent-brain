# Plan 02 Summary: GET /query/chunk/{chunk_id} endpoint

**Phase:** 50 — Server endpoint prep + v2 design doc
**Requirement:** prerequisite for URI-01 (Phase 51)
**Status:** Complete
**Commits:** f3fc9a8, 030d6b2, adf764f, af7d158, 1eb4e00, 1c5813d, 67249f0
**Date:** 2026-06-02

## What was built

Shipped `GET /query/chunk/{chunk_id}` on `agent-brain-server`, returning a v2-spec `ChunkRecord` (content plus full metadata, no embeddings) for O(1) primary-key lookups against both storage backends. Locked the response shape with a new `ChunkRecord` Pydantic model in `agent_brain_server/models/query.py`, added `get_chunk_by_id(chunk_id) -> ChunkRecord | None` to `StorageBackendProtocol`, and implemented it on `ChromaBackend` (via `collection.get(ids=[id], include=["documents", "metadatas"])`) and `PostgresBackend` (via `SELECT document_text, metadata FROM documents WHERE chunk_id = :id LIMIT 1` — `chunk_id` is already the PK so the index lookup is free).

## Files Modified

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-server/agent_brain_server/models/query.py` | modified | Added `ChunkRecord` Pydantic model with v2-locked field set |
| `agent-brain-server/agent_brain_server/models/__init__.py` | modified | Exported `ChunkRecord` |
| `agent-brain-server/agent_brain_server/storage/protocol.py` | modified | Added `async def get_chunk_by_id(chunk_id) -> ChunkRecord \| None` |
| `agent-brain-server/agent_brain_server/storage/chroma/backend.py` | modified | Implemented `get_chunk_by_id`; added `_build_chunk_record` helper |
| `agent-brain-server/agent_brain_server/storage/postgres/backend.py` | modified | Implemented `get_chunk_by_id` via PK SELECT (embedding column NOT selected) |
| `agent-brain-server/agent_brain_server/api/routers/query.py` | modified | Added `GET /query/chunk/{chunk_id}` route with 200/404/500 handling |
| `agent-brain-server/tests/contract/test_get_chunk_by_id.py` | created | Parametrized contract suite across ChromaDB + Postgres |
| `agent-brain-server/tests/integration/test_chunk_endpoint.py` | created | FastAPI TestClient suite (200/404/500/special-chars) |
| `agent-brain-server/tests/unit/storage/test_protocol.py` | modified | Added `get_chunk_by_id` stub to `MockCompleteBackend` |

## Verification

- [x] Black format check passed (`poetry run black --check agent_brain_server tests` — 190 files unchanged)
- [x] Ruff lint check passed (`poetry run ruff check agent_brain_server tests` — All checks passed)
- [x] mypy strict check passed (`poetry run mypy agent_brain_server` — 84 source files, no issues)
- [x] pytest passed (`poetry run pytest` — 1244 passed, 28 skipped; 13 new tests under this plan: 4 contract x 2 backends + 1 perf + 4 integration + 1 mock-protocol fix)
- [x] Local contract test run: 4 passed (chroma) + 5 skipped (postgres — no `DATABASE_URL`); integration test run: 4 passed.

### Verification matrix

| Check          | Command                                                     | Result |
|----------------|-------------------------------------------------------------|--------|
| Format         | `poetry run black --check agent_brain_server tests`         | PASS   |
| Lint           | `poetry run ruff check agent_brain_server tests`            | PASS   |
| Types (strict) | `poetry run mypy agent_brain_server`                        | PASS   |
| Tests          | `poetry run pytest -q`                                      | PASS (1244 / 28 skipped) |

## Design notes / Deviations

- **No schema migration needed for Postgres.** `chunks` is named `documents` in the existing schema (`PostgresSchemaManager.create_schema`) and `chunk_id` is already the PRIMARY KEY — implicit index covers O(1) lookup. No `CREATE INDEX IF NOT EXISTS idx_chunks_chunk_id` was required (plan step 6 was a precaution; existing schema satisfies it).
- **`parent_doc_id` and `folder_id` fallback semantics.** Neither field is currently emitted by `IndexingService`'s chunk metadata writer. `_build_chunk_record` and the Postgres branch derive both from `source`: `parent_doc_id` falls back to `source` (file path), `folder_id` falls back to `os.path.dirname(source)`. The fallback keeps the locked v2 shape stable; an explicit indexing-side surface for these fields can land in a later plan without breaking the wire shape.
- **`summary` source.** Plan 01 design doc says `summary: str | None = None` from `SummaryExtractor`. The existing metadata writer stores summaries under `section_summary` (LlamaIndex `SummaryExtractor` convention). The mapper looks for both `summary` and `section_summary` so future indexer changes won't break the contract.
- **Tests landed under `tests/contract/` and `tests/integration/`** (the codebase's established locations for parametrized cross-backend tests and FastAPI route tests) rather than the plan's suggested `tests/storage/` / `tests/api/` paths. Functionally equivalent — the parametrized contract conftest already lives in `tests/contract/conftest.py`.
- **No OpenAPI export script committed.** The plan suggested regenerating `docs/api/openapi.json` but no such file exists in the repo today (the spec is served live at `/openapi.json` by FastAPI). Skipped that step; OpenAPI smoke is covered indirectly by the existing `test_openapi_json_available` integration test which exercises the FastAPI-generated schema.
- **No manual curl smoke test executed.** The plan called out a curl smoke against a running server — not run here because Plans 03 and 04 are running in parallel and starting a server would race with their work. The TestClient suite covers the equivalent contract assertions in-process.

### Auto-fixed deviations

- **[Rule 3 – Blocking] Updated `MockCompleteBackend`.** Adding the new protocol method broke `test_protocol_complete_implementation` (`runtime_checkable` isinstance check). Fixed by adding a minimal `get_chunk_by_id` stub. Captured in commit `67249f0`.

## Self-Check: PASSED
