# Phase 7: Testing & CI Integration - Research

**Researched:** 2026-02-11
**Domain:** Contract testing, CI/CD with PostgreSQL service containers, load testing
**Confidence:** HIGH

## Summary

Phase 7 validates that ChromaDB and PostgreSQL backends implement identical behavior through contract tests, extends CI to support PostgreSQL testing, and validates connection pool performance under concurrent load.

The primary challenge is creating a test suite that runs against both backends without code duplication while handling PostgreSQL's optional dependency status. The solution uses pytest's parametrization with `indirect=True` to pass backend fixtures to shared test logic, custom markers to skip PostgreSQL tests when the database is unavailable, and GitHub Actions service containers to provide PostgreSQL in CI.

Load testing validates connection pool behavior (50 concurrent queries + background indexing) using Python's asyncio primitives rather than heavyweight tools like Locust. For hybrid search result similarity validation, simple set-based overlap or Spearman correlation provides pragmatic alternatives to complex ranking metrics like NDCG.

**Primary recommendation:** Use pytest parametrize with backend factory fixtures, @pytest.mark.postgres marker with skipif logic, GitHub Actions PostgreSQL service container, and asyncio-based load tests to validate pool configuration.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | ^8.3.0 | Testing framework | Already in use, excellent parametrization support |
| pytest-asyncio | ^0.24.0 | Async test support | Already in use, required for async backend tests |
| pytest-cov | ^6.0.0 | Coverage reporting | Already in use, required for PR QA gate |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio | stdlib | Concurrent load testing | Lightweight alternative to Locust for pool validation |
| GitHub Actions | N/A | CI/CD platform | Already in use for pr-qa-gate.yml workflow |
| PostgreSQL 14+ | latest | Service container | GitHub Actions postgres:14 image standard |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest parametrize | Separate test files per backend | Parametrize eliminates duplication, easier maintenance |
| asyncio for load tests | Locust | Locust overkill for connection pool validation, asyncio sufficient |
| Set overlap for result similarity | NDCG/DCG ranking metrics | NDCG more rigorous but overkill for "similar top-5" requirement |
| GitHub Actions service | External PostgreSQL CI service | Service containers free, integrated, isolated per workflow |

**No new dependencies needed** — all required libraries already in pyproject.toml dev dependencies.

## Architecture Patterns

### Recommended Test Structure
```
agent-brain-server/tests/
├── contract/               # Backend contract tests (existing)
│   ├── conftest.py        # Backend factory fixtures
│   ├── test_backend_contract.py  # NEW: Parametrized protocol tests
│   └── test_hybrid_search_contract.py  # NEW: Result similarity tests
├── unit/                  # Unit tests with mocks (existing - 654 tests)
│   └── storage/
│       ├── test_chroma_backend.py      # Existing mocked tests
│       └── test_postgres_backend.py    # Existing mocked tests (95 new)
├── integration/           # Integration tests (existing)
│   └── test_postgres_real.py  # NEW: Real PostgreSQL tests (@pytest.mark.postgres)
└── load/                  # NEW: Load/stress tests
    └── test_postgres_pool.py  # NEW: Connection pool load test
```

### Pattern 1: Parametrized Contract Tests with Backend Factory
**What:** Use pytest parametrize with `indirect=True` to run identical test logic against multiple backend implementations
**When to use:** Testing that backends implement StorageBackendProtocol identically
**Example:**
```python
# Source: pytest docs + interface contract testing patterns
# tests/contract/conftest.py

import pytest
from agent_brain_server.storage.factory import create_storage_backend

@pytest.fixture
def backend_type(request):
    """Parametrized backend type fixture."""
    return request.param

@pytest.fixture
async def storage_backend(backend_type, tmp_path):
    """Factory fixture that creates backend based on backend_type parameter.

    This fixture is used with indirect parametrization:
        @pytest.mark.parametrize("storage_backend", ["chroma", "postgres"], indirect=True)
    """
    if backend_type == "chroma":
        # Create ChromaBackend with temp directory
        config = {"backend": "chroma", "chroma_dir": str(tmp_path)}
        backend = create_storage_backend(config)
        await backend.initialize()
        yield backend
        await backend.reset()

    elif backend_type == "postgres":
        # Skip if PostgreSQL not available
        pytest.importorskip("asyncpg")
        if not _postgres_available():
            pytest.skip("PostgreSQL database not available")

        config = {"backend": "postgres", "database_url": get_test_db_url()}
        backend = create_storage_backend(config)
        await backend.initialize()
        yield backend
        await backend.reset()
        await backend.close()

def _postgres_available() -> bool:
    """Check if PostgreSQL is available for testing."""
    try:
        import asyncpg
        # Try to connect to test database
        # Return True if successful, False otherwise
        return True  # Implement actual check
    except Exception:
        return False
```

```python
# tests/contract/test_backend_contract.py

import pytest
from agent_brain_server.storage.protocol import SearchResult

@pytest.mark.parametrize("storage_backend", ["chroma", "postgres"], indirect=True)
class TestStorageBackendContract:
    """Contract tests ensuring identical behavior across backends."""

    async def test_upsert_and_count(self, storage_backend):
        """All backends must return correct count after upsert."""
        count = await storage_backend.upsert_documents(
            ids=["id1", "id2"],
            embeddings=[[0.1]*3072, [0.2]*3072],
            documents=["doc1", "doc2"],
            metadatas=[{}, {}]
        )
        assert count == 2

        total = await storage_backend.get_count()
        assert total == 2

    async def test_vector_search_returns_search_results(self, storage_backend):
        """All backends must return SearchResult objects with normalized scores."""
        # Setup: insert test data
        await storage_backend.upsert_documents(
            ids=["id1"],
            embeddings=[[0.5]*3072],
            documents=["test document"],
            metadatas=[{"source": "test.py"}]
        )

        # Search
        results = await storage_backend.vector_search(
            query_embedding=[0.5]*3072,
            top_k=5,
            similarity_threshold=0.0
        )

        # Contract assertions
        assert len(results) >= 1
        assert all(isinstance(r, SearchResult) for r in results)
        assert all(0.0 <= r.score <= 1.0 for r in results)  # Normalized scores
        assert all(hasattr(r, 'chunk_id') for r in results)
```

**Benefits:**
- Write contract test logic once, run against all backends
- Automatic detection of behavior differences
- Easy to add new backends (just add to parametrize list)
- Forces consistent protocol implementation

### Pattern 2: Conditional Test Skipping with @pytest.mark.postgres
**What:** Mark PostgreSQL-specific tests to skip gracefully when database unavailable
**When to use:** Tests requiring real PostgreSQL connection (not mocked)
**Example:**
```python
# Source: pytest skip/xfail documentation
# tests/integration/test_postgres_real.py

import pytest

# Check if PostgreSQL dependencies available at import time
pytestmark = pytest.mark.postgres  # Mark entire module

def _postgres_available() -> bool:
    """Runtime check for PostgreSQL availability."""
    try:
        import asyncpg
        from agent_brain_server.storage.postgres.config import PostgresConfig

        config = PostgresConfig()
        # Try to connect (implementation detail)
        return True
    except Exception:
        return False

@pytest.mark.skipif(
    not _postgres_available(),
    reason="PostgreSQL database not available (requires DATABASE_URL env var)"
)
class TestPostgresRealConnection:
    """Integration tests requiring real PostgreSQL database."""

    async def test_connection_pool_metrics(self):
        """Test connection pool metrics with real database."""
        from agent_brain_server.storage.factory import create_storage_backend

        backend = create_storage_backend({"backend": "postgres"})
        await backend.initialize()

        # Real database operations
        await backend.upsert_documents(...)

        # Check pool metrics
        metrics = backend.connection_manager.get_pool_metrics()
        assert metrics["pool_size"] > 0
        assert metrics["pool_max_size"] == 10  # From config

        await backend.close()
```

**Configuration in pyproject.toml:**
```toml
# Already present in pyproject.toml lines 111-118
[tool.pytest.ini_options]
markers = [
    "postgres: marks tests that require PostgreSQL database",
]
```

**Running tests:**
```bash
# Run all tests (postgres tests skip without DATABASE_URL)
pytest

# Run only postgres tests (useful in CI with service container)
pytest -m postgres

# Skip postgres tests explicitly
pytest -m "not postgres"

# What task before-push does (runs all, postgres tests skip gracefully)
task before-push
```

### Pattern 3: GitHub Actions PostgreSQL Service Container
**What:** Provide PostgreSQL instance in GitHub Actions CI for marked tests
**When to use:** Running @pytest.mark.postgres tests in pr-qa-gate workflow
**Example:**
```yaml
# Source: GitHub Actions docs + Simon Willison TIL
# .github/workflows/pr-qa-gate.yml additions

jobs:
  qa-gate:
    name: Quality Assurance Gate
    runs-on: ubuntu-latest

    # Add PostgreSQL service container
    services:
      postgres:
        image: postgres:14
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

    steps:
      # ... existing steps ...

      - name: Run tests with PostgreSQL
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          # PostgreSQL connection for marked tests
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/agent_brain_test
        run: |
          # Install PostgreSQL extras
          cd agent-brain-server
          poetry install --extras postgres
          # Run all tests (postgres-marked tests now run)
          poetry run pytest --cov=agent_brain_server --cov-fail-under=50
```

**Key details:**
- Service container runs postgres:14 image
- Health check with pg_isready ensures database ready before tests
- Port mapping 5432:5432 exposes to runner
- DATABASE_URL env var tells tests where to connect
- poetry install --extras postgres installs asyncpg/sqlalchemy

### Pattern 4: Asyncio-Based Connection Pool Load Test
**What:** Validate connection pool handles 50 concurrent queries + background indexing without exhaustion
**When to use:** Verifying pool_max_size configuration sufficient for expected load
**Example:**
```python
# Source: asyncio gather patterns + asyncpg pool testing
# tests/load/test_postgres_pool.py

import asyncio
import pytest
from agent_brain_server.storage.factory import create_storage_backend

@pytest.mark.postgres
@pytest.mark.slow
async def test_connection_pool_under_load():
    """Validate pool handles 50 concurrent queries + background indexing.

    Success criteria from Phase 7:
    - 50 concurrent query tasks
    - 1 background indexing task
    - No connection pool exhaustion errors
    - Pool metrics show size <= max_size
    """
    backend = create_storage_backend({"backend": "postgres"})
    await backend.initialize()

    # Seed test data
    ids = [f"doc_{i}" for i in range(100)]
    embeddings = [[0.1]*3072 for _ in range(100)]
    documents = [f"document {i}" for i in range(100)]
    metadatas = [{"idx": i} for i in range(100)]

    await backend.upsert_documents(ids, embeddings, documents, metadatas)

    query_embedding = [0.5]*3072

    async def query_task(task_id: int):
        """Single query task."""
        results = await backend.vector_search(
            query_embedding=query_embedding,
            top_k=5,
            similarity_threshold=0.0
        )
        assert len(results) > 0
        return task_id

    async def background_indexing_task():
        """Simulate background indexing."""
        for i in range(10):
            await backend.upsert_documents(
                ids=[f"bg_{i}"],
                embeddings=[[0.2]*3072],
                documents=[f"background doc {i}"],
                metadatas=[{"source": "background"}]
            )
            await asyncio.sleep(0.1)  # Simulate processing time

    # Create 50 concurrent query tasks + 1 background task
    query_tasks = [query_task(i) for i in range(50)]
    bg_task = background_indexing_task()

    # Run concurrently
    results = await asyncio.gather(*query_tasks, bg_task, return_exceptions=True)

    # Verify no exceptions (no pool exhaustion)
    errors = [r for r in results if isinstance(r, Exception)]
    assert len(errors) == 0, f"Pool exhaustion or errors: {errors}"

    # Check pool metrics
    metrics = backend.connection_manager.get_pool_metrics()
    assert metrics["pool_size"] <= metrics["pool_max_size"], \
        f"Pool exceeded max_size: {metrics['pool_size']} > {metrics['pool_max_size']}"

    await backend.close()
```

**Why asyncio instead of Locust:**
- Lightweight: No external dependencies needed
- Integration: Tests actual backend code paths, not HTTP API
- Sufficient: 50 concurrent async operations validates pool configuration
- Faster: Runs in test suite, not separate load test infrastructure

### Pattern 5: Hybrid Search Result Similarity Validation
**What:** Validate ChromaDB and PostgreSQL hybrid search produce "similar" top-5 results
**When to use:** Contract test ensuring backends return comparable results for same query
**Example:**
```python
# Source: Set-based similarity + Spearman correlation
# tests/contract/test_hybrid_search_contract.py

import pytest
from agent_brain_server.storage.factory import create_storage_backend

@pytest.mark.parametrize("storage_backend", ["chroma", "postgres"], indirect=True)
async def test_hybrid_search_produces_similar_results(storage_backend, request):
    """Validate hybrid search top-5 similar across backends."""
    # Seed identical test data
    test_docs = [
        ("id1", [0.1]*3072, "Python is a programming language", {"lang": "en"}),
        ("id2", [0.2]*3072, "FastAPI is a web framework", {"lang": "en"}),
        ("id3", [0.3]*3072, "PostgreSQL is a database", {"lang": "en"}),
        ("id4", [0.4]*3072, "ChromaDB is a vector store", {"lang": "en"}),
        ("id5", [0.5]*3072, "pytest is a testing framework", {"lang": "en"}),
    ]

    ids = [d[0] for d in test_docs]
    embeddings = [d[1] for d in test_docs]
    documents = [d[2] for d in test_docs]
    metadatas = [d[3] for d in test_docs]

    await storage_backend.upsert_documents(ids, embeddings, documents, metadatas)

    # Perform hybrid search (keyword + vector)
    query_embedding = [0.15]*3072
    results = await storage_backend.vector_search(
        query_embedding=query_embedding,
        top_k=5,
        similarity_threshold=0.0
    )

    # Store results by backend type for comparison
    backend_type = request.node.callspec.params["storage_backend"]
    if not hasattr(test_hybrid_search_produces_similar_results, "_results"):
        test_hybrid_search_produces_similar_results._results = {}

    result_ids = [r.chunk_id for r in results[:5]]
    test_hybrid_search_produces_similar_results._results[backend_type] = result_ids

    # After both backends run, compare
    stored = test_hybrid_search_produces_similar_results._results
    if len(stored) == 2:
        chroma_ids = set(stored["chroma"])
        postgres_ids = set(stored["postgres"])

        # Jaccard similarity: |A ∩ B| / |A ∪ B|
        overlap = len(chroma_ids & postgres_ids)
        union = len(chroma_ids | postgres_ids)
        similarity = overlap / union if union > 0 else 0.0

        # Require >= 60% overlap in top-5 results
        assert similarity >= 0.6, \
            f"Top-5 results differ too much: chroma={chroma_ids}, postgres={postgres_ids}, similarity={similarity:.2%}"
```

**Alternative: Spearman correlation for rank order:**
```python
from scipy.stats import spearmanr

def compare_rankings(chroma_results, postgres_results):
    """Compare result rankings using Spearman correlation."""
    # Create rank mappings
    all_ids = set([r.chunk_id for r in chroma_results + postgres_results])

    chroma_ranks = {r.chunk_id: i for i, r in enumerate(chroma_results)}
    postgres_ranks = {r.chunk_id: i for i, r in enumerate(postgres_results)}

    # Fill missing ranks with len+1 (not in top-k)
    chroma_vals = [chroma_ranks.get(id, len(chroma_results)) for id in all_ids]
    postgres_vals = [postgres_ranks.get(id, len(postgres_results)) for id in all_ids]

    # Calculate Spearman correlation (-1 to 1, higher=more similar)
    correlation, _ = spearmanr(chroma_vals, postgres_vals)
    assert correlation >= 0.5, f"Rankings differ: Spearman={correlation:.2f}"
```

**Simpler approach recommended:** Set overlap (Jaccard) sufficient for "similar top-5" requirement, avoids scipy dependency.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Backend parametrization | Duplicate test files per backend | pytest parametrize with indirect=True | Eliminates duplication, single source of truth |
| PostgreSQL in CI | External CI database service | GitHub Actions service container | Free, isolated, integrated, standard postgres image |
| Load testing framework | Custom concurrent test harness | asyncio.gather() | Stdlib, sufficient for pool validation, no new deps |
| Test skipping logic | Manual if/else in tests | @pytest.mark.skipif | Declarative, clear intent, pytest native |
| Ranking similarity metrics | Custom NDCG/DCG implementation | Set overlap (Jaccard) or scipy.stats.spearmanr | Simple, sufficient for "similar top-5" validation |

**Key insight:** pytest parametrization eliminates the temptation to duplicate contract tests per backend. The factory fixture pattern is well-established for this use case.

## Common Pitfalls

### Pitfall 1: Running PostgreSQL Tests Locally Without Database
**What goes wrong:** Developer runs `task before-push` without PostgreSQL installed → all postgres-marked tests fail → frustration/confusion
**Why it happens:** Tests not properly marked or skipif condition missing
**How to avoid:**
- Use `@pytest.mark.postgres` on all PostgreSQL integration tests
- Add `@pytest.mark.skipif(not _postgres_available(), reason="...")`
- Ensure conftest.py backend factory fixture checks availability
- Document in test file docstrings: "Requires DATABASE_URL env var"
**Warning signs:** "asyncpg.exceptions.InvalidCatalogNameError" or "connection refused" in local test runs

### Pitfall 2: Service Container Not Ready Before Tests
**What goes wrong:** GitHub Actions runs tests before PostgreSQL service container is healthy → connection failures → flaky CI
**Why it happens:** Missing or incorrect health check configuration
**How to avoid:**
- Always include `--health-cmd pg_isready` in service container options
- Set reasonable intervals: `--health-interval 10s --health-timeout 5s --health-retries 5`
- GitHub Actions waits for healthy status before starting job steps
**Warning signs:** Intermittent CI failures with "connection refused" that pass on retry

### Pitfall 3: Assuming Identical Results Across Backends
**What goes wrong:** Contract test expects exact result IDs/scores to match → fails due to BM25 vs tsvector scoring differences
**Why it happens:** Different backends use different keyword search algorithms (BM25 vs PostgreSQL tsvector)
**How to avoid:**
- Test for "similar" top-5 results (set overlap >= 60%) not identical
- Accept different score values (both normalized 0-1 but algorithms differ)
- Focus on protocol compliance (SearchResult shape) not exact scores
- Document known differences in test docstrings
**Warning signs:** Contract tests fail with "expected [id1, id2] but got [id2, id1]" (order difference acceptable)

### Pitfall 4: Connection Pool Exhaustion in Load Tests
**What goes wrong:** Load test creates 100 concurrent tasks with pool_max_size=10 → asyncpg.TooManyConnectionsError
**Why it happens:** Not understanding that pool_max_size limits concurrent database connections
**How to avoid:**
- Load test should validate configured pool size is sufficient (50 queries + background indexing fits in pool_max_size=10)
- Use asyncio.Semaphore if needed to limit concurrency
- Monitor pool metrics during test: `assert metrics["pool_size"] <= metrics["pool_max_size"]`
- Phase 6 already configured pool_max_size=10, pool_min_size=2 — validate this config works
**Warning signs:** asyncpg.exceptions.TooManyConnectionsError, "sorry, too many clients already"

### Pitfall 5: Installing PostgreSQL Extras in Wrong Poetry Environment
**What goes wrong:** CI installs server with `poetry install` but forgets `--extras postgres` → asyncpg not available → all postgres tests skip
**Why it happens:** pyproject.toml line 64 defines `postgres = ["asyncpg", "sqlalchemy"]` as optional
**How to avoid:**
- Update CI workflow: `poetry install --extras postgres` when DATABASE_URL present
- Update local dev docs: `poetry install --extras postgres` to run integration tests
- Backend factory fixture already uses lazy import to avoid breaking ChromaDB-only installs
**Warning signs:** All postgres-marked tests show "SKIPPED" in CI even with DATABASE_URL set

## Code Examples

Verified patterns from pytest documentation and existing codebase:

### Backend Factory Fixture with Parametrize
```python
# Source: tests/conftest.py patterns + pytest parametrize docs
# tests/contract/conftest.py

import pytest
import tempfile
from pathlib import Path
from agent_brain_server.storage.factory import create_storage_backend
from agent_brain_server.storage.chroma.backend import ChromaBackend
from agent_brain_server.storage.postgres.backend import PostgresBackend

@pytest.fixture
async def chroma_backend(tmp_path: Path):
    """Create ChromaBackend with temporary directory."""
    # Use tmp_path fixture for isolated test environment
    backend = ChromaBackend()
    backend.vector_store.persist_directory = str(tmp_path / "chroma")
    await backend.initialize()

    yield backend

    # Cleanup
    await backend.reset()

@pytest.fixture
async def postgres_backend():
    """Create PostgresBackend with test database.

    Requires DATABASE_URL environment variable pointing to test database.
    Tests using this fixture should be marked with @pytest.mark.postgres.
    """
    pytest.importorskip("asyncpg")  # Skip if asyncpg not installed

    import os
    if "DATABASE_URL" not in os.environ:
        pytest.skip("DATABASE_URL not set - PostgreSQL tests require database")

    from agent_brain_server.storage.postgres.config import PostgresConfig

    config = PostgresConfig()  # Reads DATABASE_URL from env
    backend = PostgresBackend(config)
    await backend.initialize()

    yield backend

    # Cleanup
    await backend.reset()
    await backend.close()

@pytest.fixture(params=["chroma", "postgres"])
async def storage_backend(request, chroma_backend, postgres_backend):
    """Parametrized fixture providing both backends for contract tests.

    Usage:
        async def test_something(storage_backend):
            # Test runs twice: once with chroma_backend, once with postgres_backend
            await storage_backend.upsert_documents(...)

    Tests using this will automatically run against both backends.
    PostgreSQL tests skip gracefully if database unavailable.
    """
    if request.param == "chroma":
        return chroma_backend
    elif request.param == "postgres":
        return postgres_backend
```

### Skipif with Postgres Marker
```python
# Source: pytest skip documentation
# tests/integration/test_postgres_connection_pool.py

import pytest
import os

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        "DATABASE_URL" not in os.environ,
        reason="DATABASE_URL environment variable required for PostgreSQL tests"
    )
]

@pytest.mark.slow
async def test_connection_pool_metrics():
    """Integration test requiring real PostgreSQL database."""
    from agent_brain_server.storage.postgres.backend import PostgresBackend
    from agent_brain_server.storage.postgres.config import PostgresConfig

    config = PostgresConfig()
    backend = PostgresBackend(config)

    await backend.initialize()

    # Get pool metrics (Phase 6 implementation)
    metrics = backend.connection_manager.get_pool_metrics()

    assert "pool_size" in metrics
    assert "pool_max_size" in metrics
    assert metrics["pool_max_size"] == 10  # Default from config
    assert metrics["pool_size"] >= 0
    assert metrics["pool_size"] <= metrics["pool_max_size"]

    await backend.close()
```

### Contract Test Example
```python
# Source: StorageBackendProtocol + parametrize pattern
# tests/contract/test_backend_contract.py

import pytest
from agent_brain_server.storage.protocol import SearchResult, EmbeddingMetadata

@pytest.mark.asyncio
class TestStorageBackendProtocol:
    """Contract tests validating StorageBackendProtocol compliance."""

    async def test_upsert_returns_count(self, storage_backend):
        """All backends must return count of upserted documents."""
        count = await storage_backend.upsert_documents(
            ids=["test1", "test2", "test3"],
            embeddings=[[0.1]*3072, [0.2]*3072, [0.3]*3072],
            documents=["doc 1", "doc 2", "doc 3"],
            metadatas=[{"idx": 1}, {"idx": 2}, {"idx": 3}]
        )

        assert count == 3

    async def test_vector_search_returns_search_results(self, storage_backend):
        """All backends must return SearchResult objects with normalized scores."""
        # Setup
        await storage_backend.upsert_documents(
            ids=["doc1"],
            embeddings=[[0.5]*3072],
            documents=["test document"],
            metadatas=[{"source": "test.py"}]
        )

        # Search
        results = await storage_backend.vector_search(
            query_embedding=[0.5]*3072,
            top_k=5,
            similarity_threshold=0.0
        )

        # Protocol assertions
        assert len(results) >= 1
        result = results[0]

        # Must be SearchResult instance
        assert isinstance(result, SearchResult)

        # Must have required fields
        assert hasattr(result, "text")
        assert hasattr(result, "metadata")
        assert hasattr(result, "score")
        assert hasattr(result, "chunk_id")

        # Score must be normalized 0-1
        assert 0.0 <= result.score <= 1.0

        # Metadata must be dict
        assert isinstance(result.metadata, dict)

    async def test_keyword_search_returns_search_results(self, storage_backend):
        """All backends must return SearchResult objects from keyword search."""
        # Setup
        await storage_backend.upsert_documents(
            ids=["doc1", "doc2"],
            embeddings=[[0.1]*3072, [0.2]*3072],
            documents=["Python programming language", "JavaScript web development"],
            metadatas=[{"lang": "python"}, {"lang": "javascript"}]
        )

        # Keyword search
        results = await storage_backend.keyword_search(
            query="Python programming",
            top_k=5
        )

        # Should find at least one result
        assert len(results) >= 1

        # All results must be SearchResult objects
        assert all(isinstance(r, SearchResult) for r in results)

        # Scores must be normalized 0-1
        assert all(0.0 <= r.score <= 1.0 for r in results)

    async def test_get_count_returns_int(self, storage_backend):
        """All backends must return integer count."""
        # Empty index
        count = await storage_backend.get_count()
        assert isinstance(count, int)
        assert count == 0

        # After inserting
        await storage_backend.upsert_documents(
            ids=["doc1", "doc2"],
            embeddings=[[0.1]*3072, [0.2]*3072],
            documents=["doc1", "doc2"],
            metadatas=[{}, {}]
        )

        count = await storage_backend.get_count()
        assert count == 2

    async def test_reset_clears_all_data(self, storage_backend):
        """All backends must clear data on reset."""
        # Insert data
        await storage_backend.upsert_documents(
            ids=["doc1"],
            embeddings=[[0.1]*3072],
            documents=["test"],
            metadatas=[{}]
        )

        assert await storage_backend.get_count() > 0

        # Reset
        await storage_backend.reset()

        # Count should be 0
        assert await storage_backend.get_count() == 0

    async def test_embedding_metadata_storage(self, storage_backend):
        """All backends must store and retrieve embedding metadata."""
        # Initially None
        metadata = await storage_backend.get_embedding_metadata()
        assert metadata is None or isinstance(metadata, EmbeddingMetadata)

        # Set metadata
        await storage_backend.set_embedding_metadata(
            provider="openai",
            model="text-embedding-3-large",
            dimensions=3072
        )

        # Retrieve
        metadata = await storage_backend.get_embedding_metadata()
        assert metadata is not None
        assert metadata.provider == "openai"
        assert metadata.model == "text-embedding-3-large"
        assert metadata.dimensions == 3072
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Duplicate test files per backend | Parametrized contract tests | 2024+ | Single source of truth, easier maintenance |
| Manual test skipping with try/except | @pytest.mark.skipif declarative skipping | pytest 3.0+ | Clear intent, less boilerplate |
| External CI database services | GitHub Actions service containers | 2020+ | Free, isolated, standard images |
| Locust/JMeter for load testing | asyncio.gather for async load tests | Python 3.7+ | Lightweight, integrated, sufficient for pool validation |
| NDCG for ranking comparison | Set overlap (Jaccard similarity) | N/A | Simpler, no scipy dependency, sufficient for "similar top-5" |

**Deprecated/outdated:**
- Separate integration test files per backend (use parametrize instead)
- Manual skipif logic in test bodies (use markers and fixtures)
- pytest-postgresql plugin for fixtures (overkill, use service container + manual fixtures)

## Open Questions

1. **Should we use NDCG or simpler set overlap for hybrid search similarity?**
   - What we know: NDCG is rigorous ranking metric, Jaccard overlap is simpler
   - What's unclear: Does "similar top-5" requirement need ranking order or just set overlap?
   - Recommendation: Start with Jaccard overlap (60% threshold), upgrade to Spearman if needed

2. **What's acceptable overlap threshold for "similar" top-5 results?**
   - What we know: BM25 vs tsvector use different keyword scoring algorithms
   - What's unclear: How much variance is acceptable? 60%? 80%?
   - Recommendation: Start with 60% (3 of 5 overlap), adjust based on empirical testing

3. **Should connection pool load test be in CI or local-only?**
   - What we know: Load test takes ~10 seconds, CI already runs PostgreSQL service
   - What's unclear: Does every PR need load test or just periodic validation?
   - Recommendation: Mark `@pytest.mark.slow`, run in CI (validates config), skippable locally with `-m "not slow"`

4. **Should we test all 11 StorageBackendProtocol methods in contract tests?**
   - What we know: Protocol defines 11 methods (initialize, upsert, vector_search, keyword_search, get_count, get_by_id, reset, get/set_embedding_metadata, validate_embedding_compatibility, is_initialized)
   - What's unclear: Do all need contract tests or just critical paths?
   - Recommendation: Test all 11 for completeness — contract tests are cheap, missing a method is expensive

## Sources

### Primary (HIGH confidence)
- [pytest parametrize documentation](https://docs.pytest.org/en/stable/example/parametrize.html) - Parametrization patterns
- [pytest skip/xfail documentation](https://docs.pytest.org/en/stable/how-to/skipping.html) - Conditional skipping
- [GitHub Actions PostgreSQL service container docs](https://docs.github.com/en/actions/use-cases-and-examples/using-containerized-services/creating-postgresql-service-containers) - Service container setup
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/) - Async fixture patterns
- [asyncpg documentation](https://magicstack.github.io/asyncpg/current/usage.html) - Connection pool usage
- Existing test files: `tests/conftest.py`, `tests/contract/test_query_modes.py`, `tests/unit/storage/test_chroma_backend.py`, `tests/unit/storage/test_postgres_backend.py`
- Existing CI: `.github/workflows/pr-qa-gate.yml`
- `pyproject.toml` markers configuration (lines 111-118)
- `StorageBackendProtocol` definition (`storage/protocol.py`)

### Secondary (MEDIUM confidence)
- [Advanced Pytest Patterns with Parametrization and Factory Methods](https://www.fiddler.ai/blog/advanced-pytest-patterns-harnessing-the-power-of-parametrization-and-factory-methods) - Factory fixture pattern
- [Interface Contract Testing in C#](https://medium.com/@asher.garland/interface-contract-testing-a-reusable-test-suite-for-interface-first-design-in-c-31ad3da331a9) - Contract testing philosophy (language-agnostic)
- [Running tests against PostgreSQL in a service container](https://til.simonwillison.net/github-actions/postgresq-service-container) - Simon Willison TIL
- [Pytest async fixtures](https://til.simonwillison.net/pytest/async-fixtures) - Simon Willison TIL
- [NDCG metric explanation](https://www.evidentlyai.com/ranking-metrics/ndcg-metric) - Ranking similarity metrics
- [Locust documentation](https://docs.locust.io/) - Load testing (evaluated, not using)

### Tertiary (LOW confidence)
- [asyncpg pool exceeds max_size issue](https://github.com/MagicStack/asyncpg/issues/1107) - Known pool behavior quirk (verify in load test)
- [pytest-async-sqlalchemy](https://pypi.org/project/pytest-async-sqlalchemy/) - Alternative fixture approach (overkill for our needs)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools already in use, no new dependencies
- Architecture: HIGH - Parametrize pattern well-documented, existing contract/ directory provides structure
- GitHub Actions: HIGH - Service containers standard practice, official docs clear
- Load testing: MEDIUM - asyncio sufficient but need empirical validation of pool_max_size=10
- Result similarity: MEDIUM - Set overlap simple but threshold (60%) needs validation

**Research date:** 2026-02-11
**Valid until:** 2026-03-11 (30 days - stable technologies)

**Technologies verified:**
- pytest 8.3.0 (stable, current)
- pytest-asyncio 0.24.0 (current)
- GitHub Actions service containers (current as of 2026-02)
- PostgreSQL 14+ (LTS, current for service containers)
- asyncpg 0.29.0 (current, installed via poetry extras)
