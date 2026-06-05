# Phase 9: Runtime Backend Wiring - Research

**Researched:** 2026-02-12
**Domain:** FastAPI dependency injection, Python service wiring, test migration strategies
**Confidence:** HIGH

## Summary

Phase 9 closes the v6.0 milestone audit gap by wiring the factory-selected storage backend into QueryService and IndexingService at runtime. The gap is simple: `main.py` creates `storage_backend` from the factory but still passes legacy `vector_store + bm25_manager` to services, causing them to always use ChromaDB regardless of config. The fix is straightforward — both services already accept `storage_backend` as a parameter and have backward-compatible constructors.

The primary technical challenge is managing 500+ existing tests that use the legacy constructor API. Research shows four viable approaches: (1) bulk refactor all tests, (2) add test helper that wraps legacy params into ChromaBackend, (3) keep both paths indefinitely, or (4) deprecate with warnings then remove. The codebase uses pytest with extensive mocking patterns, contract tests for protocol validation, and CI with PostgreSQL service containers.

GraphRAG (SimplePropertyGraphStore) is ChromaDB-only and controlled by `ENABLE_GRAPH_INDEX` flag. When using postgres backend, graph queries should either error with a clear message or fall back to hybrid mode. The health endpoint already has infrastructure to report backend-specific status (`/health/postgres` exists).

**Primary recommendation:** Use backward-compatible constructor approach with lazy ChromaBackend wrapping (services already implement this pattern). Add mock-based wiring smoke test that verifies factory selection drives service backend type. Skip Chroma/BM25 initialization entirely when backend is postgres. Document graph query limitations in plugin docs.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Legacy path handling:**
- Remove or deprecate legacy `vector_store` / `bm25_manager` constructor params from services — Claude's discretion on approach
- Since installation is driven by agentic skills, breaking the old constructor API is acceptable
- For 500+ existing tests: Claude decides whether to refactor all tests or add a test helper that wraps legacy params into ChromaBackend
- Factory (`get_storage_backend()`) is the canonical way to get a backend — Claude decides if main.py can also construct directly or must go through factory
- Scope: server only — CLI talks via HTTP and never constructs services directly

**Chroma initialization scope:**
- When backend is 'postgres', skip creation of VectorStoreManager and BM25IndexManager entirely
- No chroma_data/ or bm25_index/ dirs should be created when using postgres — Claude decides cleanest approach
- GraphRAG (SimplePropertyGraphStore) initialization when using postgres: Claude decides based on actual code dependencies
- Verify DocumentLoader has no ChromaDB assumptions baked in — check it during implementation

**Test strategy:**
- Add a wiring smoke test (mock-based, always runs in `task before-push`) that verifies factory wiring logic
- When backend='postgres', services must hold PostgresBackend instance (not ChromaBackend)
- Claude decides: mock-based integration test vs contract test extension vs both
- Claude decides: whether to also test via FastAPI TestClient (app-level lifespan wiring) or unit test only
- No change to postgres test skip behavior — postgres-marked tests still skip without database

**Graph store handling:**
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

### Deferred Ideas (OUT OF SCOPE)

- **Portable agent skills**: Convert agent-brain commands into portable skills compatible with Codex, Gemini, OpenCode, Copilot
- **GraphRAG on PostgreSQL**: Move graph store to postgres (JSONB or dedicated graph tables) — tracked as PGADV-02

</user_constraints>

## Standard Stack

### Core Dependencies (Already Installed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | ^0.104.0 | ASGI web framework | Industry standard for async Python APIs, built-in DI |
| Pydantic | ^2.0 | Data validation | Type-safe config, request/response models |
| pytest | ^7.4.0 | Testing framework | De facto Python test standard |
| pytest-asyncio | ^0.21.0 | Async test support | Required for async service tests |
| pytest-mock | ^3.11.0 | Mocking utilities | Cleaner mock syntax than unittest.mock alone |

### Testing Infrastructure

| Component | Current Implementation | Use Case |
|-----------|----------------------|----------|
| Contract tests | `tests/contract/test_backend_contract.py` | Protocol behavior validation |
| Fixtures | `tests/contract/conftest.py` | Backend parametrization (chroma/postgres) |
| Service containers | GitHub Actions `.github/workflows/pr-qa-gate.yml` | PostgreSQL pgvector for CI |
| Task runner | `Taskfile.yml` | Monorepo task orchestration |

### Installation

Already installed — no new dependencies required for Phase 9.

## Architecture Patterns

### Current Service Wiring (Problem)

**File:** `agent-brain-server/agent_brain_server/api/main.py` (lines 281-292)

```python
# main.py lifespan creates storage_backend from factory
storage_backend = get_storage_backend()
await storage_backend.initialize()
app.state.storage_backend = storage_backend

# BUT services are still created with legacy params
indexing_service = IndexingService(
    vector_store=vector_store,        # ❌ Always ChromaDB
    bm25_manager=bm25_manager,        # ❌ Always ChromaDB BM25
    document_loader=document_loader,
)
query_service = QueryService(
    vector_store=vector_store,        # ❌ Always ChromaDB
    bm25_manager=bm25_manager,        # ❌ Always ChromaDB BM25
)
```

**Gap:** Factory selects backend, but services ignore it and use ChromaDB directly.

### Target Service Wiring (Solution)

**Pattern:** Pass `storage_backend` instead of `vector_store + bm25_manager`

```python
# main.py lifespan
storage_backend = get_storage_backend()
await storage_backend.initialize()
app.state.storage_backend = storage_backend

# Services use storage_backend (postgres or chroma)
indexing_service = IndexingService(
    storage_backend=storage_backend,  # ✅ Honors config
    document_loader=document_loader,
)
query_service = QueryService(
    storage_backend=storage_backend,  # ✅ Honors config
)
```

**Why it works:** Services already have backward-compatible constructors that wrap legacy params into ChromaBackend if needed (implemented in Phase 5).

### Backward-Compatible Constructor Pattern

**Pattern:** Services accept both old and new APIs, choosing intelligently

**Source:** `agent-brain-server/agent_brain_server/services/indexing_service.py` (lines 50-87)

```python
def __init__(
    self,
    vector_store: VectorStoreManager | None = None,      # Legacy
    bm25_manager: BM25IndexManager | None = None,        # Legacy
    storage_backend: StorageBackendProtocol | None = None,  # New
    # ... other params
):
    # New path: use storage_backend if provided
    if storage_backend is not None:
        self.storage_backend = storage_backend
    # Legacy path: wrap provided stores in ChromaBackend
    elif vector_store is not None or bm25_manager is not None:
        from agent_brain_server.storage.chroma.backend import ChromaBackend
        self.storage_backend = ChromaBackend(
            vector_store=vector_store,
            bm25_manager=bm25_manager,
        )
    # Default: use factory
    else:
        self.storage_backend = get_storage_backend()
```

**Impact on Phase 9:**
- ✅ Services already support `storage_backend` parameter
- ✅ Tests using legacy API continue working (ChromaBackend wrapper)
- ✅ New `main.py` wiring uses modern path
- ❌ Legacy params still exist in constructor signature (deprecation decision pending)

### Conditional Backend Initialization

**Pattern:** Skip Chroma/BM25 creation when using postgres backend

```python
# main.py lifespan (current - BEFORE fix)
chroma_dir = str(storage_paths["chroma_db"])
bm25_dir = str(storage_paths["bm25_index"])

vector_store = VectorStoreManager(persist_dir=chroma_dir)  # Always created
await vector_store.initialize()

bm25_manager = BM25IndexManager(persist_dir=bm25_dir)     # Always created
bm25_manager.initialize()

# Target pattern (AFTER fix)
backend_type = get_effective_backend_type()

if backend_type == "chroma":
    chroma_dir = str(storage_paths["chroma_db"])
    bm25_dir = str(storage_paths["bm25_index"])

    vector_store = VectorStoreManager(persist_dir=chroma_dir)
    await vector_store.initialize()
    app.state.vector_store = vector_store  # For backward compat

    bm25_manager = BM25IndexManager(persist_dir=bm25_dir)
    bm25_manager.initialize()
    app.state.bm25_manager = bm25_manager  # For backward compat

# PostgreSQL backend: no chroma/bm25 initialization
storage_backend = get_storage_backend()
await storage_backend.initialize()
app.state.storage_backend = storage_backend
```

**Why:** Avoids creating unused ChromaDB directories when using PostgreSQL.

### Test Patterns

#### Pattern 1: Legacy Constructor with Mock (500+ existing tests)

**Source:** `tests/unit/services/test_query_service_reranking.py`

```python
@pytest.fixture
def mock_dependencies(self):
    mock_vector_store = MagicMock()
    mock_vector_store.is_initialized = True
    mock_bm25 = MagicMock()
    return {
        "vector_store": mock_vector_store,
        "bm25_manager": mock_bm25,
    }

@pytest.fixture
def query_service(self, mock_dependencies):
    return QueryService(
        vector_store=mock_dependencies["vector_store"],  # Legacy API
        bm25_manager=mock_dependencies["bm25_manager"],
    )
```

**Status:** Works with Phase 5 backward-compat constructor (wraps into ChromaBackend).

#### Pattern 2: Contract Test with Backend Parametrization

**Source:** `tests/contract/conftest.py`

```python
@pytest.fixture(params=["chroma", "postgres"])
async def storage_backend(request, tmp_path):
    backend_type = request.param

    if backend_type == "chroma":
        # Real ChromaDB with tmp isolation
        backend = ChromaBackend(...)
        await backend.initialize()
        yield backend
        await backend.reset()
    elif backend_type == "postgres":
        # PostgreSQL with DATABASE_URL check
        pytest.importorskip("asyncpg")
        if not os.environ.get("DATABASE_URL"):
            pytest.skip("DATABASE_URL not set")
        backend = PostgresBackend(...)
        await backend.initialize()
        yield backend
        await backend.reset()
```

**Use:** Validates identical protocol behavior across backends.

#### Pattern 3: Wiring Smoke Test (New for Phase 9)

**Target:** `tests/integration/test_backend_wiring.py` (mock-based, always runs)

```python
@pytest.mark.asyncio
async def test_factory_backend_wired_to_services():
    """Verify factory-selected backend drives service wiring."""
    with patch("agent_brain_server.storage.factory.get_effective_backend_type") as mock_type:
        # Test 1: When backend is 'chroma'
        mock_type.return_value = "chroma"
        backend = get_storage_backend()
        service = QueryService(storage_backend=backend)
        assert isinstance(service.storage_backend, ChromaBackend)

        # Test 2: When backend is 'postgres'
        reset_storage_backend_cache()
        mock_type.return_value = "postgres"
        backend = get_storage_backend()
        service = QueryService(storage_backend=backend)
        assert isinstance(service.storage_backend, PostgresBackend)
```

**Why mock-based:** Runs in `task before-push` without requiring PostgreSQL database.

### Anti-Patterns to Avoid

- **Mixing legacy and new paths in main.py:** Don't create `vector_store` then pass `storage_backend` — choose one initialization path per backend type
- **Hardcoded ChromaDB assumptions:** Don't assume `storage_backend` has `.vector_store` or `.bm25_manager` attributes — use protocol methods only
- **Silent fallbacks in graph queries:** Don't silently switch from graph to hybrid — either error with clear message or log warning
- **Creating unused directories:** Don't create `chroma_data/` when using postgres backend

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Service wiring | Custom registry pattern | FastAPI `app.state` + lifespan | Built-in DI, no extra complexity |
| Backend selection | Complex if/else chains | Factory pattern (already exists) | Single source of truth, testable |
| Test migration | Bulk find/replace | Backward-compat constructor | Preserves 500+ tests, gradual migration |
| Mock setup | Manual mock creation per test | pytest fixtures + conftest.py | Reusable, consistent across tests |

**Key insight:** The factory + backward-compat constructor pattern (implemented in Phase 5) already solves the hard problems. Phase 9 is wiring, not redesign.

## Common Pitfalls

### Pitfall 1: Breaking 500+ Existing Tests

**What goes wrong:** Removing legacy constructor params immediately fails all existing tests.

**Why it happens:** Tests use `QueryService(vector_store=mock, bm25_manager=mock)` pattern extensively.

**How to avoid:** Keep backward-compatible constructors (they wrap legacy params into ChromaBackend). Either (1) deprecate with warning, or (2) accept both paths indefinitely.

**Warning signs:** Test suite shows hundreds of failures after service constructor changes.

**Decision point:** User allows breaking changes since "installation is driven by agentic skills" — but backward-compat constructors avoid churn while preserving flexibility.

### Pitfall 2: Creating Unused ChromaDB Directories on Postgres Backend

**What goes wrong:** Server creates `chroma_data/` and `bm25_index/` directories even when using postgres backend.

**Why it happens:** `main.py` always initializes VectorStoreManager and BM25IndexManager regardless of backend selection.

**How to avoid:** Conditional initialization based on `get_effective_backend_type()`. Only create ChromaDB managers when `backend_type == "chroma"`.

**Warning signs:** Filesystem shows `chroma_data/` directory after starting server with `AGENT_BRAIN_STORAGE_BACKEND=postgres`.

### Pitfall 3: Graph Queries Failing Silently on Postgres

**What goes wrong:** User requests `mode='graph'` query on postgres backend, gets unexpected results or silent fallback to hybrid.

**Why it happens:** GraphRAG uses SimplePropertyGraphStore which depends on ChromaDB (controlled by `ENABLE_GRAPH_INDEX` flag).

**How to avoid:** Explicit check in QueryService: if backend is postgres and mode is graph/multi, either raise error with message "Graph queries require ChromaDB backend" or log warning and fall back to hybrid.

**Warning signs:** Health endpoint shows `graph_store: null` but graph queries don't error clearly.

**User decision:** "Claude decides best UX (error with message vs fallback to hybrid)" — recommendation is explicit error for clarity.

### Pitfall 4: Missing Backend Type Check in Wiring Test

**What goes wrong:** Wiring test verifies services are created but doesn't check backend type matches config.

**Why it happens:** Mocking `get_storage_backend()` return value without verifying type constraint.

**How to avoid:** Assert `isinstance(service.storage_backend, PostgresBackend)` when `backend_type == "postgres"`.

**Warning signs:** Test passes but runtime still uses ChromaDB when config says postgres.

## Code Examples

Verified patterns from codebase review:

### Factory-Driven Service Creation

**Source:** Target pattern for `main.py` lifespan

```python
# agent-brain-server/agent_brain_server/api/main.py (lines 237-293)

# Determine backend type early
backend_type = get_effective_backend_type()
logger.info(f"Storage backend: {backend_type}")

# Conditional ChromaDB initialization
if backend_type == "chroma":
    # Determine persistence directories
    chroma_dir = (
        str(storage_paths["chroma_db"])
        if storage_paths
        else settings.CHROMA_PERSIST_DIR
    )
    bm25_dir = (
        str(storage_paths["bm25_index"])
        if storage_paths
        else settings.BM25_INDEX_PATH
    )

    # Initialize ChromaDB components
    vector_store = VectorStoreManager(persist_dir=chroma_dir)
    await vector_store.initialize()
    app.state.vector_store = vector_store  # Backward compat
    logger.info("Vector store initialized")

    bm25_manager = BM25IndexManager(persist_dir=bm25_dir)
    bm25_manager.initialize()
    app.state.bm25_manager = bm25_manager  # Backward compat
    logger.info("BM25 index manager initialized")

# Initialize storage backend (wraps ChromaDB or creates PostgreSQL pool)
storage_backend = get_storage_backend()
await storage_backend.initialize()
app.state.storage_backend = storage_backend
logger.info("Storage backend initialized")

# Load project config for exclude patterns
exclude_patterns = None
if state_dir:
    project_config = load_project_config(state_dir)
    exclude_patterns = project_config.get("exclude_patterns")

# Create document loader
document_loader = DocumentLoader(exclude_patterns=exclude_patterns)

# Create services with storage_backend (new path)
indexing_service = IndexingService(
    storage_backend=storage_backend,
    document_loader=document_loader,
)
app.state.indexing_service = indexing_service

query_service = QueryService(
    storage_backend=storage_backend,
)
app.state.query_service = query_service
```

**Why this works:**
- Factory selects backend based on config
- Services receive backend instance directly
- Backward compat fields (`app.state.vector_store`) preserved for existing code
- No ChromaDB directories created when using postgres

### Graph Query Validation

**Source:** Pattern for QueryService graph mode check

```python
# agent-brain-server/agent_brain_server/services/query_service.py

async def query(self, request: QueryRequest) -> QueryResponse:
    # Check if graph mode is requested on postgres backend
    backend_type = get_effective_backend_type()

    if request.mode in [QueryMode.GRAPH, QueryMode.MULTI]:
        if backend_type == "postgres":
            raise ValueError(
                f"Graph queries (mode='{request.mode}') require ChromaDB backend. "
                f"Current backend: {backend_type}. "
                f"To use graph queries, set AGENT_BRAIN_STORAGE_BACKEND=chroma."
            )
        if not self.graph_index_manager or not self.graph_index_manager.is_available:
            raise ValueError(
                f"Graph queries requested but graph index is not available. "
                f"Ensure ENABLE_GRAPH_INDEX=true and index has been built."
            )

    # Continue with query execution
    # ...
```

**Alternative (fallback with warning):**

```python
if request.mode in [QueryMode.GRAPH, QueryMode.MULTI]:
    if backend_type == "postgres":
        logger.warning(
            f"Graph mode '{request.mode}' not supported on postgres backend. "
            f"Falling back to hybrid mode."
        )
        request.mode = QueryMode.HYBRID
```

**Recommendation:** Explicit error (first pattern) for clarity and fail-fast behavior.

### Health Endpoint Graph Store Status

**Source:** Pattern for `/health/status` response

```python
# agent-brain-server/agent_brain_server/api/routers/health.py

service_status = await indexing_service.get_status()

# Add graph store availability based on backend
backend_type = get_effective_backend_type()
graph_index_info = service_status.get("graph_index")

if backend_type == "postgres":
    # Override graph index status for postgres backend
    graph_index_info = {
        "enabled": False,
        "available": False,
        "reason": "Graph queries require ChromaDB backend (current: postgres)",
    }

return IndexingStatus(
    # ... other fields
    graph_index=graph_index_info,
)
```

**Why:** Clear signal to users that graph features are unavailable on postgres backend.

### Mock-Based Wiring Test

**Source:** New test for Phase 9

```python
# agent-brain-server/tests/integration/test_backend_wiring.py

import pytest
from unittest.mock import patch, MagicMock
from agent_brain_server.storage import get_storage_backend, reset_storage_backend_cache
from agent_brain_server.storage.chroma.backend import ChromaBackend
from agent_brain_server.services import QueryService, IndexingService


@pytest.mark.asyncio
async def test_chroma_backend_wired_to_services():
    """When backend type is 'chroma', services use ChromaBackend."""
    with patch("agent_brain_server.storage.factory.get_effective_backend_type") as mock_type:
        mock_type.return_value = "chroma"

        backend = get_storage_backend()
        assert isinstance(backend, ChromaBackend)

        # Services use the factory-selected backend
        query_service = QueryService(storage_backend=backend)
        assert isinstance(query_service.storage_backend, ChromaBackend)

        indexing_service = IndexingService(storage_backend=backend)
        assert isinstance(indexing_service.storage_backend, ChromaBackend)


@pytest.mark.asyncio
async def test_postgres_backend_wired_to_services():
    """When backend type is 'postgres', services use PostgresBackend."""
    reset_storage_backend_cache()

    with patch("agent_brain_server.storage.factory.get_effective_backend_type") as mock_type:
        mock_type.return_value = "postgres"

        # Mock PostgreSQL imports to avoid requiring asyncpg
        with patch("agent_brain_server.storage.factory.PostgresBackend") as mock_pg:
            mock_backend_instance = MagicMock()
            mock_pg.return_value = mock_backend_instance

            backend = get_storage_backend()
            assert backend is mock_backend_instance

            # Services use the factory-selected backend
            query_service = QueryService(storage_backend=backend)
            assert query_service.storage_backend is mock_backend_instance


@pytest.mark.asyncio
async def test_factory_backend_selection_drives_services():
    """Factory backend selection (not legacy params) drives service behavior."""
    reset_storage_backend_cache()

    # Even if vector_store/bm25_manager are on app.state, storage_backend takes precedence
    mock_backend = MagicMock()

    query_service = QueryService(storage_backend=mock_backend)
    assert query_service.storage_backend is mock_backend

    indexing_service = IndexingService(storage_backend=mock_backend)
    assert indexing_service.storage_backend is mock_backend
```

**Why mock-based:** Runs in `task before-push` without requiring PostgreSQL database or network.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Services accept only `vector_store + bm25_manager` | Services accept `storage_backend` or legacy params | Phase 5 (2026-02-10) | Enables backend-agnostic services |
| `main.py` creates services with ChromaDB managers | `main.py` passes `storage_backend` from factory | Phase 9 (this phase) | Backend selection actually works |
| Tests hardcode ChromaDB mocks | Tests use protocol-based mocks or parametrized backends | Ongoing | Gradual migration |
| Graph queries always available | Graph queries conditional on backend type | Phase 9 (this phase) | Clear error for unsupported backends |

**Deprecated/outdated:**
- **Direct VectorStoreManager/BM25IndexManager instantiation in services:** Use `storage_backend` parameter instead
- **Assuming ChromaDB is always available:** Check backend type before graph queries

## Open Questions

### 1. Should we fully remove legacy constructor params or keep them?

**What we know:**
- Services have backward-compatible constructors (wrap legacy params into ChromaBackend)
- 500+ tests use legacy API
- User said "breaking the old constructor API is acceptable"

**What's unclear:**
- Long-term maintenance burden of supporting both APIs
- Value of forcing test migration vs gradual adoption

**Recommendation:** Keep backward-compatible constructors for now. They enable gradual migration without breaking existing tests. Add deprecation warning in constructor docstring. Schedule removal for v7.0 milestone if needed.

### 2. Should graph queries on postgres error or fall back to hybrid?

**What we know:**
- GraphRAG uses SimplePropertyGraphStore (ChromaDB only)
- User wants clear signal when graph is unavailable
- User gave discretion: "error with message vs fallback to hybrid"

**What's unclear:**
- User experience preference (fail-fast vs graceful degradation)

**Recommendation:** Explicit error (fail-fast) for v6.0. Clear error message tells user exactly what's wrong and how to fix it. Fallback can be added later if users request it.

### 3. Should wiring test be mock-based or app-level (TestClient)?

**What we know:**
- Mock-based test runs in `task before-push` without database
- App-level test via TestClient exercises full lifespan
- User gave discretion: "mock-based integration test vs contract test extension vs both"

**What's unclear:**
- Whether app-level test adds meaningful coverage beyond mock test

**Recommendation:** Start with mock-based test for Phase 9 (fast, no deps). Contract tests already validate backend behavior. App-level TestClient test can be added in Phase 10 (live E2E validation).

## Sources

### Primary (HIGH confidence)

- **Codebase:** `agent-brain-server/agent_brain_server/api/main.py` — Current service wiring (lines 281-292)
- **Codebase:** `agent-brain-server/agent_brain_server/services/query_service.py` — Backward-compat constructor (lines 81-100)
- **Codebase:** `agent-brain-server/agent_brain_server/services/indexing_service.py` — Backward-compat constructor (lines 50-87)
- **Codebase:** `agent-brain-server/agent_brain_server/storage/factory.py` — Backend factory implementation
- **Codebase:** `tests/contract/test_backend_contract.py` — Protocol contract test pattern
- **Codebase:** `.planning/phases/05-storage-abstraction/05-02-PLAN.md` — Phase 5 backward-compat design
- **Codebase:** `.planning/v6.0-MILESTONE-AUDIT.md` — Gap identification (lines 48-51)

### Secondary (MEDIUM confidence)

- **Codebase:** `Taskfile.yml` — Task runner commands and quality gates
- **Codebase:** `.github/workflows/pr-qa-gate.yml` — CI pipeline with postgres service container
- **Codebase:** `tests/unit/services/test_query_service_reranking.py` — Existing test patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — All dependencies already installed, no new libs needed
- Architecture: HIGH — Patterns already implemented in Phase 5, just need wiring
- Pitfalls: HIGH — Verified from codebase analysis and prior phase documentation

**Research date:** 2026-02-12
**Valid until:** 2026-03-15 (30 days for stable monorepo architecture)
