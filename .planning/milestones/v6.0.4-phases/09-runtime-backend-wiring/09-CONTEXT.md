# Phase 9: Runtime Backend Wiring - Context

**Gathered:** 2026-02-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire factory-selected storage backend into QueryService and IndexingService so backend selection (Chroma vs Postgres) controls runtime behavior. Currently, `main.py` creates the backend from the factory but passes legacy `vector_store + bm25_manager` to services, causing them to always use ChromaDB regardless of config. This phase fixes the wiring gap identified in the v6.0 milestone audit.

</domain>

<decisions>
## Implementation Decisions

### Legacy path handling
- Remove or deprecate legacy `vector_store` / `bm25_manager` constructor params from services — Claude's discretion on approach
- Since installation is driven by agentic skills, breaking the old constructor API is acceptable
- For 500+ existing tests: Claude decides whether to refactor all tests or add a test helper that wraps legacy params into ChromaBackend
- Factory (`get_storage_backend()`) is the canonical way to get a backend — Claude decides if main.py can also construct directly or must go through factory
- Scope: server only — CLI talks via HTTP and never constructs services directly

### Chroma initialization scope
- When backend is 'postgres', skip creation of VectorStoreManager and BM25IndexManager entirely
- No chroma_data/ or bm25_index/ dirs should be created when using postgres — Claude decides cleanest approach
- GraphRAG (SimplePropertyGraphStore) initialization when using postgres: Claude decides based on actual code dependencies
- Verify DocumentLoader has no ChromaDB assumptions baked in — check it during implementation

### Test strategy
- Add a wiring smoke test (mock-based, always runs in `task before-push`) that verifies factory wiring logic
- When backend='postgres', services must hold PostgresBackend instance (not ChromaBackend)
- Claude decides: mock-based integration test vs contract test extension vs both
- Claude decides: whether to also test via FastAPI TestClient (app-level lifespan wiring) or unit test only
- No change to postgres test skip behavior — postgres-marked tests still skip without database

### Graph store handling
- Graph queries (mode='graph', mode='multi') are ChromaDB only — disabled when using postgres backend
- When user requests graph/multi mode on postgres: Claude decides best UX (error with message vs fallback to hybrid)
- Health endpoint: show `graph_store: 'unavailable'` when on postgres backend (not omit — clear signal)
- Update plugin documentation in this phase to note graph queries require ChromaDB backend

### Claude's Discretion
- Whether to fully remove legacy constructor params or deprecate with warning
- Test refactoring approach (bulk update vs test helper wrapper)
- Factory as sole construction path vs allowing direct override
- GraphRAG initialization behavior on postgres backend
- Filesystem cleanup approach (clean vs create-but-don't-use)
- Graph/multi mode fallback behavior on postgres
- App-level vs unit-level test depth

</decisions>

<specifics>
## Specific Ideas

- The fix is primarily in `agent-brain-server/agent_brain_server/api/main.py` lines 281-292 where services are instantiated
- Services already accept `storage_backend` parameter — the wiring just needs to pass it
- The audit identified the exact gap: "Storage backend selection does not drive runtime QueryService/IndexingService wiring"
- The E2E flow "configure backend -> setup postgres -> run server -> query" must work after this fix

</specifics>

<deferred>
## Deferred Ideas

- **Portable agent skills**: Convert agent-brain commands into portable skills compatible with Codex, Gemini, OpenCode, Copilot. Make install/manage commands work across systems for both chroma and postgres backends. This is a new capability — its own phase.
- **GraphRAG on PostgreSQL**: Move graph store to postgres (JSONB or dedicated graph tables) — already tracked in REQUIREMENTS.md as PGADV-02

</deferred>

---

*Phase: 09-runtime-backend-wiring*
*Context gathered: 2026-02-12*
