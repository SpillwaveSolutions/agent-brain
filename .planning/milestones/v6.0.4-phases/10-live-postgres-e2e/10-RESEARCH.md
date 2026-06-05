# Phase 10: Live PostgreSQL E2E Validation - Research

**Researched:** 2026-02-12
**Domain:** End-to-end PostgreSQL backend validation with Docker Compose, live database testing, cross-backend consistency validation
**Confidence:** HIGH

## Summary

Phase 10 validates the complete PostgreSQL backend implementation (Phases 5-9) through end-to-end testing with a real database. This is operational validation—not new features, but proving that the configure -> setup -> index -> query workflow works with PostgreSQL in production-like conditions.

The infrastructure already exists: Docker Compose template for pgvector/pgvector:pg16, GitHub Actions CI with PostgreSQL service containers, contract test suite structure, and connection pool load testing framework. The gap is that all existing tests use mocks or skip when PostgreSQL is unavailable. This phase writes integration tests that require a live database, validates hybrid search result consistency between backends, and exercises connection pools under concurrent load.

**Critical insight:** The existing contract tests (test_backend_contract.py, test_hybrid_search_contract.py) use parametrized fixtures to run identical test logic against both ChromaDB and PostgreSQL backends—but they skip PostgreSQL tests when DATABASE_URL is not set. The infrastructure is already correct; we just need E2E tests that exercise the full stack (API -> services -> PostgresBackend -> live database) and validate operational requirements like pool exhaustion resistance and cross-backend consistency.

**Primary recommendation:** Write pytest integration tests marked with @pytest.mark.postgres that require DATABASE_URL, use the existing Docker Compose template for local testing, leverage GitHub Actions PostgreSQL service container for CI, validate top-5 hybrid search result overlap between backends (set-based similarity or Spearman rank correlation), and use asyncio.gather() to simulate 50 concurrent queries + background indexing for pool load testing.

## Standard Stack

### Core (Already Installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | ^8.3.0 | Test framework | Already in use, 654+ tests passing |
| pytest-asyncio | ^0.24.0 | Async test support | Already in use, required for async backend tests |
| Docker Compose | v2 | PostgreSQL orchestration | Docker Desktop standard, pgvector template exists |
| GitHub Actions | N/A | CI/CD with service containers | Already configured with PostgreSQL service in pr-qa-gate.yml |

### Supporting (Already Available)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio | stdlib | Concurrent request simulation | Pool load testing (50 concurrent queries) |
| httpx AsyncClient | via pytest | API integration tests | Full-stack E2E tests (API -> database) |
| pytest.mark.skipif | pytest | Conditional test execution | Skip postgres tests when DATABASE_URL not set |

### No New Dependencies Required
All required libraries, test fixtures, and CI infrastructure already exist from Phases 5-9. This phase uses existing tools to write new tests.

**Docker Compose Setup:**
```bash
# Template already exists at:
# agent-brain-server/templates/docker-compose.postgres.yml
# agent-brain-plugin/templates/docker-compose.postgres.yml

# Start PostgreSQL for local testing
docker compose -f agent-brain-server/templates/docker-compose.postgres.yml up -d

# Set DATABASE_URL for tests
export DATABASE_URL="postgresql://agent_brain:agent_brain_dev@localhost:5432/agent_brain"

# Run postgres-marked tests
cd agent-brain-server
poetry run pytest tests/integration/test_postgres_e2e.py -v
```

## Architecture Patterns

### Recommended Test Structure
```
agent-brain-server/tests/
├── integration/                      # Integration tests (existing - 7 files)
│   ├── test_postgres_e2e.py         # NEW: Full-stack E2E with live database
│   └── test_backend_wiring.py       # EXISTS: Mock-based service wiring tests
├── contract/                         # Backend contract tests (existing)
│   ├── conftest.py                  # EXISTS: storage_backend parametrized fixture
│   ├── test_backend_contract.py     # EXISTS: 11 protocol methods tested
│   └── test_hybrid_search_contract.py  # EXISTS: Cross-backend consistency
└── load/                            # Load/stress tests (existing)
    └── test_postgres_pool.py        # EXISTS: Pool load test (currently mock-based)
```

**What's new:** Integration test that exercises API endpoints with live PostgreSQL backend and validates full workflow from HTTP request to database persistence. Also converts the existing mock-based pool load test to use real PostgreSQL connections.

### Pattern 1: Full-Stack E2E Test with Live PostgreSQL

**What:** Integration test that starts with HTTP API calls, flows through services, and verifies data persistence in real PostgreSQL database.

**When to use:** Validating end-to-end workflow (configure backend -> setup postgres -> run server -> index -> query) that the v6.0 audit identified as broken.

**Example:**
```python
# tests/integration/test_postgres_e2e.py

import os
import pytest
from httpx import AsyncClient
from pathlib import Path

# Skip if PostgreSQL not available
pytestmark = pytest.mark.postgres

def _postgres_available() -> bool:
    """Check if PostgreSQL database is available for testing."""
    try:
        import asyncpg  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("DATABASE_URL"))

@pytest.fixture(scope="module")
def postgres_env(monkeypatch):
    """Configure environment for PostgreSQL backend."""
    # Set backend to postgres
    monkeypatch.setenv("AGENT_BRAIN_STORAGE_BACKEND", "postgres")

    # Ensure DATABASE_URL is set (required for postgres backend)
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set - PostgreSQL not available")

    yield

@pytest.fixture
async def app_with_postgres(postgres_env):
    """Create FastAPI app with real PostgreSQL backend."""
    # Import app AFTER env vars are set
    from agent_brain_server.api.main import app

    # App lifespan will initialize PostgresBackend via factory
    # because AGENT_BRAIN_STORAGE_BACKEND=postgres
    yield app

    # Cleanup: reset database state
    storage_backend = app.state.storage_backend
    if storage_backend:
        await storage_backend.reset()
        await storage_backend.close()

@pytest.fixture
async def postgres_client(app_with_postgres) -> AsyncClient:
    """Async HTTP client for E2E tests."""
    from httpx import ASGITransport
    transport = ASGITransport(app=app_with_postgres)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

class TestPostgresE2E:
    """End-to-end tests with live PostgreSQL backend."""

    @pytest.mark.skipif(
        not _postgres_available(),
        reason="PostgreSQL not available (requires DATABASE_URL)"
    )
    async def test_full_workflow_index_and_query(
        self, postgres_client: AsyncClient, tmp_path: Path
    ):
        """Validate complete workflow: index documents -> query -> get results.

        Success criteria #1: E2E test with real database returns results.
        """
        # 1. Verify server health with postgres backend
        health_response = await postgres_client.get("/health")
        assert health_response.status_code == 200
        health_data = health_response.json()
        assert health_data["status"] in ["healthy", "initializing"]

        # 2. Create test documents
        doc1 = tmp_path / "python_guide.md"
        doc1.write_text("# Python Programming\n\nPython is great for data science.")

        doc2 = tmp_path / "javascript_guide.md"
        doc2.write_text("# JavaScript Development\n\nJavaScript runs in browsers.")

        # 3. Index documents via API
        index_response = await postgres_client.post(
            "/index",
            json={
                "folder_path": str(tmp_path),
                "chunk_size": 512,
                "chunk_overlap": 50,
                "recursive": False,
            }
        )
        assert index_response.status_code == 200

        # 4. Wait for indexing to complete (synchronous for test simplicity)
        # In production, job queue handles async indexing
        import asyncio
        await asyncio.sleep(2)

        # 5. Query for indexed content
        query_response = await postgres_client.post(
            "/query",
            json={
                "query": "Python programming language",
                "mode": "hybrid",  # BM25 + vector
                "top_k": 5,
            }
        )
        assert query_response.status_code == 200
        query_data = query_response.json()

        # Validate results structure
        assert "results" in query_data
        results = query_data["results"]
        assert len(results) > 0

        # Top result should be Python document (relevance check)
        top_result = results[0]
        assert "python" in top_result["text"].lower()
        assert 0.0 <= top_result["score"] <= 1.0

        # 6. Verify document count in database
        count_response = await postgres_client.get("/query/count")
        assert count_response.status_code == 200
        count_data = count_response.json()
        assert count_data["count"] >= 2  # At least 2 chunks indexed

    @pytest.mark.skipif(
        not _postgres_available(),
        reason="PostgreSQL not available"
    )
    async def test_health_postgres_endpoint_metrics(
        self, postgres_client: AsyncClient
    ):
        """Validate /health/postgres returns pool metrics.

        Success criteria #4: /health/postgres returns accurate pool metrics.
        """
        response = await postgres_client.get("/health/postgres")
        assert response.status_code == 200
        data = response.json()

        # Validate pool metrics structure
        assert "pool" in data
        pool = data["pool"]
        assert "active" in pool
        assert "idle" in pool
        assert "size" in pool

        # Pool should be initialized with sensible values
        assert pool["size"] > 0
        assert pool["idle"] >= 0
        assert pool["active"] >= 0
```

**Benefits:**
- Validates the ENTIRE flow from HTTP -> FastAPI -> Services -> PostgresBackend -> asyncpg -> PostgreSQL
- Catches integration failures that unit tests miss (config errors, connection issues, SQL syntax)
- Runs in CI via GitHub Actions PostgreSQL service container automatically

### Pattern 2: Cross-Backend Hybrid Search Consistency Validation

**What:** Compare top-5 hybrid search results between ChromaDB and PostgreSQL backends for the same corpus and query to ensure behavioral equivalence.

**When to use:** Validating that PostgreSQL backend produces "similar" results to ChromaDB (not identical, but consistent ranking for same content).

**Example:**
```python
# tests/integration/test_postgres_e2e.py (continued)

import pytest
from collections import Counter

def _calculate_set_overlap(list1: list[str], list2: list[str]) -> float:
    """Calculate Jaccard similarity between two lists."""
    set1 = set(list1)
    set2 = set(list2)
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0

class TestCrossBackendConsistency:
    """Validate cross-backend result consistency.

    Success criteria #2: Hybrid top-5 results similar between backends.
    """

    @pytest.mark.skipif(
        not _postgres_available(),
        reason="Requires both ChromaDB and PostgreSQL"
    )
    async def test_hybrid_search_similarity_chroma_vs_postgres(
        self, tmp_path: Path
    ):
        """Compare hybrid search top-5 between ChromaDB and PostgreSQL.

        Expectation: At least 60% overlap in top-5 chunk IDs for same corpus.
        This is NOT exact match (different distance metrics, score ranges)
        but validates consistent ranking for high-relevance results.
        """
        # 1. Create test corpus
        corpus = [
            ("doc1", "Python is a high-level programming language"),
            ("doc2", "JavaScript is used for web development"),
            ("doc3", "Rust offers memory safety without garbage collection"),
            ("doc4", "Python has excellent data science libraries like pandas"),
            ("doc5", "TypeScript adds static typing to JavaScript"),
        ]

        query = "Python programming language features"

        # 2. Test with ChromaDB backend
        from agent_brain_server.storage.chroma.backend import ChromaBackend
        from agent_brain_server.storage.vector_store import VectorStoreManager
        from agent_brain_server.indexing.bm25_index import BM25IndexManager

        chroma_vector_store = VectorStoreManager()
        chroma_vector_store.persist_dir = str(tmp_path / "chroma")
        chroma_bm25 = BM25IndexManager()
        chroma_bm25.persist_dir = str(tmp_path / "bm25")

        chroma_backend = ChromaBackend(
            vector_store=chroma_vector_store,
            bm25_manager=chroma_bm25
        )
        await chroma_backend.initialize()

        # Index corpus in ChromaDB
        embeddings = [[0.1] * 8] * len(corpus)  # Mock embeddings
        ids = [doc_id for doc_id, _ in corpus]
        documents = [text for _, text in corpus]
        metadatas = [{"source": f"{doc_id}.md"} for doc_id, _ in corpus]

        await chroma_backend.upsert_documents(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

        # Hybrid search with ChromaDB
        query_embedding = [0.1] * 8  # Mock query embedding
        chroma_results = await chroma_backend.hybrid_search(
            query=query,
            query_embedding=query_embedding,
            top_k=5,
            alpha=0.5,  # Equal weight BM25 + vector
        )
        chroma_ids = [r.chunk_id for r in chroma_results[:5]]

        # 3. Test with PostgreSQL backend
        from agent_brain_server.storage.postgres import PostgresBackend, PostgresConfig

        config = PostgresConfig.from_database_url(os.environ["DATABASE_URL"])
        postgres_backend = PostgresBackend(config=config)
        await postgres_backend.initialize()

        # Index same corpus in PostgreSQL
        await postgres_backend.upsert_documents(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

        # Hybrid search with PostgreSQL
        postgres_results = await postgres_backend.hybrid_search(
            query=query,
            query_embedding=query_embedding,
            top_k=5,
            alpha=0.5,
        )
        postgres_ids = [r.chunk_id for r in postgres_results[:5]]

        # 4. Compare top-5 results
        overlap = _calculate_set_overlap(chroma_ids, postgres_ids)

        # Success criteria: at least 60% overlap
        # (accounts for different distance metrics, score normalization)
        assert overlap >= 0.6, (
            f"Top-5 hybrid results differ too much: "
            f"ChromaDB={chroma_ids}, Postgres={postgres_ids}, "
            f"overlap={overlap:.1%}"
        )

        # Cleanup
        await chroma_backend.reset()
        await postgres_backend.reset()
        await postgres_backend.close()
```

**Benefits:**
- Validates behavioral equivalence without requiring exact match
- Accounts for legitimate differences (distance metrics, score normalization)
- Catches major ranking discrepancies that would break user workflows

### Pattern 3: Connection Pool Load Test with Live Database

**What:** Simulate 50 concurrent queries + background indexing to verify connection pool doesn't exhaust under load.

**When to use:** Validating production-readiness of pool configuration (success criteria #3).

**Example:**
```python
# tests/load/test_postgres_pool.py (REPLACE existing mock-based test)

import asyncio
import os
import pytest
from agent_brain_server.storage.postgres import PostgresBackend, PostgresConfig

pytestmark = pytest.mark.postgres

def _postgres_available() -> bool:
    try:
        import asyncpg  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("DATABASE_URL"))

@pytest.mark.skipif(
    not _postgres_available(),
    reason="PostgreSQL not available"
)
class TestPostgresPoolLoad:
    """Load tests for PostgreSQL connection pool.

    Success criteria #3: 50 concurrent queries + background indexing
    without pool exhaustion.
    """

    async def test_concurrent_query_load(self):
        """Simulate 50 concurrent queries without pool exhaustion."""
        # 1. Setup backend with pool
        config = PostgresConfig.from_database_url(os.environ["DATABASE_URL"])
        config.pool_size = 10
        config.pool_max = 20

        backend = PostgresBackend(config=config)
        await backend.initialize()

        # 2. Index sample documents
        embeddings = [[0.1] * 8] * 10
        ids = [f"doc-{i}" for i in range(10)]
        documents = [f"Document {i} content" for i in range(10)]
        metadatas = [{"index": i} for i in range(10)]

        await backend.upsert_documents(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

        # 3. Simulate 50 concurrent queries
        query_embedding = [0.1] * 8

        async def query_task():
            """Single query task."""
            results = await backend.vector_search(
                query_embedding=query_embedding,
                top_k=5,
                similarity_threshold=0.0
            )
            return len(results)

        # Run 50 concurrent queries
        tasks = [query_task() for _ in range(50)]
        results = await asyncio.gather(*tasks)

        # All queries should succeed (no pool exhaustion)
        assert len(results) == 50
        assert all(r > 0 for r in results)

        # Cleanup
        await backend.reset()
        await backend.close()

    async def test_concurrent_queries_with_background_indexing(self):
        """Simulate queries + background indexing concurrently.

        This validates pool behavior under mixed read/write load.
        """
        config = PostgresConfig.from_database_url(os.environ["DATABASE_URL"])
        config.pool_size = 10
        config.pool_max = 20

        backend = PostgresBackend(config=config)
        await backend.initialize()

        # Initial index
        embeddings = [[0.1] * 8] * 5
        ids = [f"doc-{i}" for i in range(5)]
        documents = [f"Document {i}" for i in range(5)]
        metadatas = [{"i": i} for i in range(5)]

        await backend.upsert_documents(ids, embeddings, documents, metadatas)

        # Background indexing task
        async def indexing_task():
            """Background indexing of new documents."""
            for batch in range(5):
                batch_ids = [f"bg-{batch}-{i}" for i in range(10)]
                batch_embeddings = [[0.2] * 8] * 10
                batch_docs = [f"Background doc {batch}-{i}" for i in range(10)]
                batch_meta = [{"batch": batch, "i": i} for i in range(10)]

                await backend.upsert_documents(
                    batch_ids, batch_embeddings, batch_docs, batch_meta
                )
                await asyncio.sleep(0.1)

        # Query tasks
        async def query_task():
            query_embedding = [0.1] * 8
            results = await backend.vector_search(
                query_embedding=query_embedding,
                top_k=5,
                similarity_threshold=0.0
            )
            return len(results)

        # Run 50 queries + background indexing concurrently
        query_tasks = [query_task() for _ in range(50)]
        indexing = indexing_task()

        results, _ = await asyncio.gather(
            asyncio.gather(*query_tasks),
            indexing
        )

        # All queries should succeed despite concurrent indexing
        assert len(results) == 50
        assert all(r > 0 for r in results)

        # Cleanup
        await backend.reset()
        await backend.close()
```

**Benefits:**
- Tests real connection pool behavior (not mocked)
- Validates pool configuration (10 min, 20 max) handles production load
- Simulates realistic mixed workload (queries + indexing)

## Common Pitfalls

### Pitfall 1: Assuming Exact Result Match Between Backends

**What goes wrong:** Tests that require identical top-5 chunk IDs between ChromaDB and PostgreSQL will fail because they use different distance metrics (cosine vs. inner product default), different normalization, and different BM25 implementations.

**Why it happens:** ChromaDB uses cosine similarity by default, PostgreSQL pgvector uses inner product by default (unless explicitly configured with <=> operator). BM25 implementations may differ slightly in term frequency scoring.

**How to avoid:** Use set-based overlap (Jaccard similarity) or rank correlation (Spearman) instead of exact match. Accept 60-80% overlap as "consistent" for top-5 results.

**Warning signs:** Contract tests pass (identical API behavior) but E2E tests fail on "different results" assertions.

### Pitfall 2: PostgreSQL Container Not Ready When Tests Start

**What goes wrong:** Tests fail with connection refused or "database does not exist" errors because PostgreSQL container is still initializing when pytest runs.

**Why it happens:** Docker Compose healthcheck passes when pg_isready succeeds, but pgvector extension may not be created yet. Tests start before database is fully ready.

**How to avoid:** Add retry logic with exponential backoff in test fixtures OR wait for /health/postgres endpoint to return healthy status before running E2E tests.

**Warning signs:** Tests pass locally (Postgres already running) but fail in CI with connection errors.

### Pitfall 3: Port Conflicts in Local Development

**What goes wrong:** Docker Compose fails to start because port 5432 is already in use by another PostgreSQL instance or previous container.

**Why it happens:** Multiple PostgreSQL instances running, previous docker-compose.yml didn't clean up, or system PostgreSQL running on default port.

**How to avoid:** Use dynamic port allocation in docker-compose.yml ($POSTGRES_PORT environment variable), add cleanup step to E2E test fixtures, or configure tests to use non-default port.

**Warning signs:** "port is already allocated" error when running docker compose up.

### Pitfall 4: Mixing DATABASE_URL and YAML Config

**What goes wrong:** Tests fail because DATABASE_URL environment variable overrides YAML config.postgres settings, leading to connection to wrong database or wrong credentials.

**Why it happens:** Phase 6 decision: DATABASE_URL overrides YAML connection string. Tests set YAML config but DATABASE_URL env var takes precedence.

**How to avoid:** In test fixtures, either (1) use DATABASE_URL exclusively OR (2) clear DATABASE_URL env var when testing YAML config path. Never mix both in same test.

**Warning signs:** Tests connect to unexpected database, credentials fail despite correct YAML config.

### Pitfall 5: Forgetting to Reset Database State Between Tests

**What goes wrong:** Test failures due to data contamination from previous tests (stale documents, embedding metadata mismatch).

**Why it happens:** PostgreSQL backend persists data in database. Unlike ChromaDB with temp directories, PostgreSQL data survives between tests unless explicitly reset.

**How to avoid:** Call `await backend.reset()` in test teardown (fixture finally block) and use unique database names per test OR use transactions with rollback.

**Warning signs:** Tests pass individually but fail when run in sequence (pytest -x vs pytest).

## Code Examples

Verified patterns from existing codebase:

### Parametrized Backend Fixture (Already Exists)
```python
# Source: tests/contract/conftest.py
# Use this pattern for new E2E tests

@pytest.fixture(params=["chroma", "postgres"])
async def storage_backend(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[StorageBackendProtocol, None]:
    backend_type = request.param

    if backend_type == "chroma":
        backend = await _create_chroma_backend(tmp_path)
        try:
            yield backend
        finally:
            await backend.reset()
        return

    pytest.importorskip("asyncpg")
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")

    backend = await _create_postgres_backend(tmp_path, monkeypatch)
    try:
        yield backend
    finally:
        await backend.reset()
        await backend.close()
        clear_settings_cache()
```

### Docker Compose Template (Already Exists)
```yaml
# Source: agent-brain-server/templates/docker-compose.postgres.yml
services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: agent-brain-postgres
    environment:
      POSTGRES_USER: agent_brain
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-agent_brain_dev}
      POSTGRES_DB: agent_brain
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - agent-brain-postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agent_brain -d agent_brain"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    restart: unless-stopped
```

### GitHub Actions Service Container (Already Configured)
```yaml
# Source: .github/workflows/pr-qa-gate.yml
services:
  postgres:
    image: pgvector/pgvector:pg16
    env:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: agent_brain_test
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
    ports:
      - 5432:5432

# Tests run with:
env:
  DATABASE_URL: postgresql://postgres:postgres@localhost:5432/agent_brain_test
run: task server:pr-qa-gate
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Mock all postgres tests | Run contract tests with real DB in CI | Phase 7 (Feb 2026) | Contract tests validate real behavior in CI |
| Skip postgres tests locally | Docker Compose template for local testing | Phase 6 (Feb 2026) | Developers can run postgres tests locally |
| Separate test files per backend | Parametrized fixtures (indirect=True) | Phase 7 (Feb 2026) | DRY: write test logic once, run on all backends |
| Manual connection pool sizing | SQLAlchemy async engine with defaults | Phase 6 (Feb 2026) | Automatic pool management, pre-ping validation |

**Current limitations:**
- Contract tests run in CI but current codebase has only mock-based integration tests (Phase 9 used mocks to avoid requiring PostgreSQL)
- No cross-backend result consistency validation (required for success criteria #2)
- Connection pool load test exists but uses mocks (test_postgres_pool.py needs real database)

**Phase 10 closes these gaps:**
- Writes integration tests that require live database
- Validates cross-backend consistency with real data
- Converts pool load test to use real connections

## Open Questions

1. **Cross-backend similarity threshold**
   - What we know: Different distance metrics and BM25 implementations mean results won't be identical
   - What's unclear: What's acceptable overlap percentage? 60%? 80%?
   - Recommendation: Start with 60% Jaccard overlap for top-5, adjust based on empirical testing. Document as "behavioral consistency" not "exact match."

2. **CI test timeout**
   - What we know: PostgreSQL service container healthcheck has 30s start_period
   - What's unclear: How long should E2E tests wait for database readiness?
   - Recommendation: Use 60s timeout for E2E tests (2x healthcheck start period), fail fast with clear error message if database not ready.

3. **Local vs CI database configuration**
   - What we know: CI uses postgres/postgres credentials, Docker Compose template uses agent_brain/agent_brain_dev
   - What's unclear: Should tests accept either configuration or enforce one?
   - Recommendation: Tests should work with any valid DATABASE_URL (credential-agnostic), use environment variable for flexibility.

## Sources

### Primary (HIGH confidence)
- Existing codebase analysis:
  - `.planning/phases/06-postgresql-backend/06-RESEARCH.md` - PostgreSQL backend architecture decisions
  - `.planning/phases/07-testing-ci/07-RESEARCH.md` - Contract testing patterns and CI setup
  - `agent-brain-server/tests/contract/conftest.py` - Parametrized backend fixtures
  - `agent-brain-server/tests/contract/test_backend_contract.py` - Existing contract test patterns
  - `agent-brain-server/tests/integration/test_backend_wiring.py` - Mock-based wiring validation
  - `.github/workflows/pr-qa-gate.yml` - PostgreSQL service container configuration
- Docker Compose:
  - `agent-brain-server/templates/docker-compose.postgres.yml` - Production template
  - `docs/POSTGRESQL_SETUP.md` - Docker Compose usage documentation

### Secondary (MEDIUM confidence)
- pytest documentation (pytest.org):
  - Parametrized fixtures with indirect=True
  - pytest.mark.skipif conditional execution
  - pytest-asyncio for async test support
- GitHub Actions documentation:
  - Service containers for databases
  - PostgreSQL service container patterns

### Tertiary (LOW confidence - flagged for validation)
- Cross-backend similarity thresholds (needs empirical testing with real data to determine acceptable overlap)
- Optimal pool size for concurrent load (10/20 is Phase 6 default, may need tuning based on E2E results)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All dependencies already installed and working
- Architecture: HIGH - Contract test infrastructure exists, just needs E2E tests added
- Pitfalls: HIGH - Based on actual Phase 6-9 implementation experience and existing test patterns
- Cross-backend consistency validation: MEDIUM - Pattern is clear but acceptable threshold needs empirical testing

**Research date:** 2026-02-12
**Valid until:** 2026-03-14 (30 days - stable technology, existing codebase)
**Blocking dependencies:** None - all infrastructure from Phases 5-9 is complete

**Success criteria mapping:**
1. E2E test with real database → Pattern 1 (Full-Stack E2E Test)
2. Cross-backend consistency → Pattern 2 (Hybrid Search Consistency)
3. Connection pool under load → Pattern 3 (Pool Load Test)
4. /health/postgres metrics → Pattern 1 (validate in E2E test)
5. All existing tests pass → Run `task before-push` after E2E tests added
