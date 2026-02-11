# Phase 6: PostgreSQL Backend Implementation - Research

**Researched:** 2026-02-11
**Domain:** PostgreSQL + pgvector + tsvector backend for RAG systems with async connection pooling
**Confidence:** HIGH

## Summary

Phase 6 implements PostgreSQL as an alternative storage backend behind the existing StorageBackendProtocol (Phase 5). The implementation combines pgvector 0.7+ for vector similarity search with PostgreSQL's native tsvector for full-text search, provides async connection pooling via asyncpg, and delivers production-ready Docker Compose templates for local development. The backend must match ChromaDB's behavior exactly (same 11 protocol methods, 0-1 normalized scores, identical hybrid search RRF fusion results).

**Critical insight:** PostgreSQL offers native async operations (asyncpg driver), HNSW vector indexes with better performance than IVFFlat, and battle-tested tsvector full-text search with GIN indexes. The challenge is not technical capability but behavioral equivalence—PostgreSQL and ChromaDB have different distance metrics, score ranges, and metadata storage patterns. The adapter MUST normalize these differences at the boundary.

**Primary recommendation:** Use asyncpg with SQLAlchemy 2.0 async engine for connection pooling, embed SQL schema as Python strings in PostgresBackend class (auto-creates tables on first connection), validate embedding dimensions on startup (fail fast on mismatch), and use Docker Compose with named volumes for data persistence. The plugin (Phase 8) handles user-facing setup flows; this phase builds the backend infrastructure it will use.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Docker & local setup**
- Docker Compose only (no native PostgreSQL install documentation in this phase)
- PostgreSQL 16 + pgvector 0.7+ as the target versions
- Minimal compose: just PostgreSQL + pgvector container (pgAdmin is optional, offered by Phase 8 wizard)
- Port allocation: scan for available ports (reuse existing auto-port pattern), configure in `.env.agent-brain` (fallback to `.env`)
- Data persistence via named Docker volume (survives `docker compose down`, only lost with `-v`)
- Docker Compose template lives in both server package (reference copy) and plugin package (deployable template)
- Per-project deployment: Phase 8 wizard generates docker-compose.yml into `.claude/agent-brain/` state directory
- Server does NOT manage Docker lifecycle — just connects to configured host:port. Docker management is Phase 8 plugin territory.

**Connection & pooling**
- Connection config: YAML fields as primary (storage.postgres.host, port, database, user, password), DATABASE_URL env var as override
- Startup behavior: retry with exponential backoff (3-5 attempts) before failing — handles Docker containers still initializing
- Pool sizing: sensible defaults (10 connections, max 20), configurable via YAML (storage.postgres.pool_size, storage.postgres.pool_max)
- Health endpoint: dedicated `/health/postgres` endpoint with pool metrics (active, idle, size) — separate from main `/health/status`

**Schema & migrations**
- Embedded SQL in Python code — schema as SQL strings in PostgresBackend class, auto-creates tables on first connection
- Vector column dimension: dynamic from embedding provider config at startup. Validated on subsequent startups (mismatch = fail fast)
- Full-text search: single combined tsvector column with setweight() for relevance boosting across content fields
- No Alembic — if schema changes, user drops and recreates (acceptable for v1)

### Claude's Discretion

- Schema version tracking strategy (simple meta table vs. no tracking)
- Exact retry backoff timing and attempt count
- HNSW index parameter defaults (m, ef_construction)
- Table naming conventions
- Connection string parsing implementation
- Exact Docker Compose health check configuration

### Deferred Ideas (OUT OF SCOPE)

- pgAdmin as optional Docker Compose add-on — Phase 8 setup wizard can offer this
- Native PostgreSQL installation documentation — out of scope, Docker-only for Phase 6
- GraphRAG on PostgreSQL — stays ChromaDB-only for now, future milestone
- Alembic schema migrations — if needed later, separate phase
- Auto-detect Docker availability from server — Phase 8 plugin wizard territory
</user_constraints>

## Standard Stack

### Core Dependencies
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncpg | ^0.29.0 | PostgreSQL async driver | Fastest Python PostgreSQL driver, deeply asyncio-native, eliminates need for external connection poolers |
| SQLAlchemy | 2.0+ (async) | Connection pooling + ORM | Industry standard, async support in 2.0+, eliminates need for PgBouncer |
| pgvector | 0.7.0+ (PostgreSQL extension) | Vector similarity search | Official PostgreSQL extension, HNSW index support, up to 16,000 dimensions |
| PostgreSQL | 16+ | Database engine | LTS version, pgvector 0.7+ compatibility, tsvector improvements |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| psycopg2-binary | ^2.9.9 | PostgreSQL adapter (fallback) | Only if asyncpg has issues, but prefer asyncpg |
| pydantic | 2.x | PostgreSQL config validation | Already in use, consistent with StorageConfig pattern |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| asyncpg | psycopg3 async | psycopg3 is newer but asyncpg is faster (benchmarks show 2-3x), more mature |
| SQLAlchemy pooling | asyncpg.create_pool() directly | SQLAlchemy provides higher-level abstraction, pre-ping validation, stale connection handling |
| Embedded SQL schema | Alembic migrations | Alembic adds complexity, Phase 6 targets v1 with simple drop/recreate migration strategy |
| Named Docker volumes | Bind mounts | Named volumes are Docker-managed, portable, safer (no host filesystem coupling) |
| pgvector HNSW | pgvector IVFFlat | HNSW has better query performance (speed-recall tradeoff), no training step required |

**Installation:**
```bash
# Add to agent-brain-server/pyproject.toml [tool.poetry.dependencies]
# PostgreSQL backend (Phase 6)
asyncpg = { version = "^0.29.0", optional = true }
sqlalchemy = { version = "^2.0.0", extras = ["asyncio"], optional = true }
psycopg2-binary = { version = "^2.9.9", optional = true }

# Add extras group for PostgreSQL
[tool.poetry.extras]
postgres = ["asyncpg", "sqlalchemy", "psycopg2-binary"]

# Install with:
cd agent-brain-server
poetry install -E postgres
```

## Architecture Patterns

### Recommended Project Structure
```
agent-brain-server/agent_brain_server/
├── storage/
│   ├── protocol.py               # UNCHANGED: StorageBackendProtocol (Phase 5)
│   ├── factory.py                # MODIFY: Remove NotImplementedError for PostgresBackend
│   ├── chroma/                   # UNCHANGED: ChromaDB adapter (Phase 5)
│   └── postgres/                 # NEW: PostgreSQL backend (Phase 6)
│       ├── __init__.py           # Exports: PostgresBackend, PostgresConfig
│       ├── backend.py            # PostgresBackend (implements StorageBackendProtocol)
│       ├── config.py             # PostgresConfig Pydantic model + connection string parsing
│       ├── connection.py         # Connection pool manager (SQLAlchemy async engine)
│       ├── schema.py             # SQL schema strings + auto-creation logic
│       ├── vector_ops.py         # pgvector operations (upsert, search, distance metrics)
│       └── keyword_ops.py        # tsvector operations (keyword search, ts_rank)
├── config/
│   └── provider_config.py        # MODIFY: Expand StorageConfig.postgres fields
├── api/
│   ├── main.py                   # MODIFY: Add lifespan for PostgreSQL pool init/shutdown
│   └── routers/
│       └── health.py             # MODIFY: Add /health/postgres endpoint
└── templates/                    # NEW: Docker Compose templates
    └── docker-compose.postgres.yml

agent-brain-plugin/                # Phase 8 will deploy templates from here
└── templates/
    └── docker-compose.postgres.yml
```

### Pattern 1: Async Connection Pool Lifecycle

**What:** Use FastAPI lifespan context manager to initialize PostgreSQL connection pool on startup and gracefully close on shutdown. Pool is stored in app.state for access in route handlers.

**When to use:** Any async resource (database pools, HTTP clients) that needs startup/shutdown lifecycle management.

**Example:**
```python
# api/main.py (MODIFY)
from contextlib import asynccontextmanager
from fastapi import FastAPI
from agent_brain_server.storage import get_storage_backend, get_effective_backend_type
from agent_brain_server.storage.protocol import StorageBackendProtocol

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: startup and shutdown."""

    # STARTUP
    backend_type = get_effective_backend_type()
    backend = get_storage_backend()

    # Initialize storage backend (ChromaDB or PostgreSQL)
    # PostgreSQL backend creates connection pool here
    await backend.initialize()

    logger.info(f"Storage backend initialized: {backend_type}")

    # Store backend in app state for health checks
    app.state.storage_backend = backend

    yield  # Application runs

    # SHUTDOWN
    # PostgreSQL backend closes connection pool
    if hasattr(backend, 'close'):
        await backend.close()
        logger.info("PostgreSQL connection pool closed")

    logger.info("Application shutdown complete")

app = FastAPI(lifespan=lifespan)
```

**Key decisions:**
- Lifespan pattern replaced `@app.on_event("startup")` in FastAPI 0.95+
- Store backend in `app.state` for access in health check endpoints
- Call `backend.close()` only if method exists (ChromaBackend doesn't need it)

### Pattern 2: PostgreSQL Connection Pool with SQLAlchemy 2.0 Async

**What:** Use SQLAlchemy 2.0's `create_async_engine()` with asyncpg dialect for connection pooling. Provides pre-ping validation, stale connection handling, and configurable pool sizing.

**When to use:** PostgreSQL backend requires connection pooling for production workloads (FastAPI handles concurrent requests).

**Example:**
```python
# storage/postgres/connection.py (NEW)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from agent_brain_server.storage.postgres.config import PostgresConfig
import logging

logger = logging.getLogger(__name__)

class PostgresConnectionManager:
    """Manages PostgreSQL connection pool with SQLAlchemy async engine."""

    def __init__(self, config: PostgresConfig):
        self.config = config
        self._engine: AsyncEngine | None = None

    async def initialize(self) -> None:
        """Create async engine with connection pool."""
        connection_url = self.config.get_connection_url()

        self._engine = create_async_engine(
            connection_url,
            echo=self.config.debug,
            pool_size=self.config.pool_size,          # Default: 10
            max_overflow=self.config.pool_max_overflow,  # Default: 10 (max 20 total)
            pool_pre_ping=True,  # Validate connections before use
            pool_recycle=3600,   # Recycle connections after 1 hour
        )

        logger.info(
            f"PostgreSQL connection pool initialized: "
            f"pool_size={self.config.pool_size}, "
            f"max_overflow={self.config.pool_max_overflow}"
        )

    async def close(self) -> None:
        """Close connection pool and release resources."""
        if self._engine:
            await self._engine.dispose()
            logger.info("PostgreSQL connection pool closed")

    @property
    def engine(self) -> AsyncEngine:
        """Get async engine (raises if not initialized)."""
        if not self._engine:
            raise RuntimeError("Connection manager not initialized")
        return self._engine

    async def get_pool_status(self) -> dict[str, int]:
        """Get connection pool metrics for health checks."""
        if not self._engine:
            return {"status": "not_initialized"}

        pool = self._engine.pool
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total": pool.size() + pool.overflow(),
        }
```

**Key decisions:**
- `pool_pre_ping=True` validates connections before use (detects stale connections)
- `pool_recycle=3600` prevents long-lived connection issues
- SQLAlchemy handles connection reuse, no need for external PgBouncer
- Pool metrics exposed for `/health/postgres` endpoint

### Pattern 3: Dynamic Schema Creation with Embedding Dimension Validation

**What:** PostgreSQL vector column requires fixed dimensions at creation time. Schema creation extracts dimensions from embedding provider config on first startup, validates on subsequent startups.

**When to use:** Vector databases where embedding dimensions must match provider (switching providers without re-indexing breaks queries).

**Example:**
```python
# storage/postgres/schema.py (NEW)
from agent_brain_server.storage.protocol import StorageError

class PostgresSchemaManager:
    """Manages PostgreSQL schema creation and validation."""

    def __init__(self, connection_manager, embedding_dimensions: int):
        self.connection_manager = connection_manager
        self.embedding_dimensions = embedding_dimensions

    async def create_schema(self) -> None:
        """Create tables with dynamic vector dimension."""

        # SQL schema with dynamic dimension
        schema_sql = f"""
        -- Enable pgvector extension
        CREATE EXTENSION IF NOT EXISTS vector;

        -- Main documents table
        CREATE TABLE IF NOT EXISTS documents (
            chunk_id TEXT PRIMARY KEY,
            document_text TEXT NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{{}}',
            embedding vector({self.embedding_dimensions}),  -- Dynamic dimension
            tsv tsvector,  -- Full-text search
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );

        -- HNSW index for vector search (cosine distance)
        CREATE INDEX IF NOT EXISTS documents_embedding_idx
        ON documents USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);

        -- GIN index for full-text search
        CREATE INDEX IF NOT EXISTS documents_tsv_idx
        ON documents USING gin(tsv);

        -- Metadata index for filtering
        CREATE INDEX IF NOT EXISTS documents_metadata_idx
        ON documents USING gin(metadata);

        -- Metadata table for embedding provider validation
        CREATE TABLE IF NOT EXISTS embedding_metadata (
            id INTEGER PRIMARY KEY DEFAULT 1,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            dimensions INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT single_row CHECK (id = 1)
        );
        """

        async with self.connection_manager.engine.begin() as conn:
            await conn.execute(schema_sql)

    async def validate_dimensions(self) -> None:
        """Validate stored embedding dimensions match current config."""
        query = "SELECT dimensions FROM embedding_metadata WHERE id = 1"

        async with self.connection_manager.engine.connect() as conn:
            result = await conn.execute(query)
            row = result.fetchone()

            if row:
                stored_dims = row[0]
                if stored_dims != self.embedding_dimensions:
                    raise StorageError(
                        f"Embedding dimension mismatch: "
                        f"stored={stored_dims}, current={self.embedding_dimensions}. "
                        f"Cannot use index created with different dimensions. "
                        f"Run 'agent-brain reset --yes' to recreate index.",
                        backend="postgres"
                    )
```

**Key decisions:**
- Vector column dimension MUST be set at table creation (PostgreSQL requirement)
- Dimension extracted from embedding provider config on first startup
- Subsequent startups validate dimensions, fail fast on mismatch
- Error message guides user to reset command (no auto-migration in v1)

### Pattern 4: Hybrid Search with RRF (Reciprocal Rank Fusion)

**What:** Combine vector similarity search (pgvector) and keyword search (tsvector) using RRF algorithm. Focus on rankings rather than normalizing raw scores.

**When to use:** RAG systems where both semantic similarity and keyword matching improve recall.

**Example:**
```python
# storage/postgres/backend.py (NEW)
from agent_brain_server.storage.protocol import SearchResult

class PostgresBackend:
    """PostgreSQL backend implementing StorageBackendProtocol."""

    async def hybrid_search_with_rrf(
        self,
        query: str,
        query_embedding: list[float],
        top_k: int,
        vector_weight: float = 0.5,
        keyword_weight: float = 0.5,
        rrf_k: int = 60,
    ) -> list[SearchResult]:
        """Hybrid search with Reciprocal Rank Fusion.

        RRF formula: score = 1 / (rank + k)
        where rank is the position in the result list (1-indexed)
        and k is a constant (default: 60, per research literature)
        """

        # Fetch more results than needed for fusion (2x top_k)
        fetch_k = top_k * 2

        # Vector search
        vector_results = await self.vector_search(
            query_embedding=query_embedding,
            top_k=fetch_k,
            similarity_threshold=0.0,  # No threshold for RRF
        )

        # Keyword search
        keyword_results = await self.keyword_search(
            query=query,
            top_k=fetch_k,
        )

        # Build RRF scores
        rrf_scores: dict[str, float] = {}

        for rank, result in enumerate(vector_results, start=1):
            rrf_scores[result.chunk_id] = (
                rrf_scores.get(result.chunk_id, 0.0) +
                vector_weight / (rank + rrf_k)
            )

        for rank, result in enumerate(keyword_results, start=1):
            rrf_scores[result.chunk_id] = (
                rrf_scores.get(result.chunk_id, 0.0) +
                keyword_weight / (rank + rrf_k)
            )

        # Merge results and sort by RRF score
        all_results = {r.chunk_id: r for r in vector_results + keyword_results}
        sorted_ids = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)

        # Normalize RRF scores to 0-1 range for protocol compliance
        max_score = max(rrf_scores.values()) if rrf_scores else 1.0

        return [
            SearchResult(
                text=all_results[chunk_id].text,
                metadata=all_results[chunk_id].metadata,
                score=rrf_scores[chunk_id] / max_score,  # Normalized 0-1
                chunk_id=chunk_id,
            )
            for chunk_id in sorted_ids[:top_k]
        ]
```

**Key decisions:**
- RRF uses rank position, not raw scores (avoids cross-backend score normalization)
- Default k=60 based on research literature (OpenSearch, Elasticsearch use this)
- Fetch 2x results for better fusion quality
- Final scores normalized to 0-1 range (protocol requirement)

### Pattern 5: Startup Retry with Exponential Backoff

**What:** Retry PostgreSQL connection with exponential backoff to handle Docker containers still initializing.

**When to use:** Services that depend on external resources (databases, APIs) that may not be ready immediately.

**Example:**
```python
# storage/postgres/connection.py (MODIFY)
import asyncio
from typing import Any

async def initialize_with_retry(
    self,
    max_attempts: int = 5,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
) -> None:
    """Initialize connection pool with exponential backoff retry.

    Args:
        max_attempts: Maximum retry attempts (default: 5)
        initial_delay: Initial delay in seconds (default: 1.0)
        backoff_factor: Delay multiplier per attempt (default: 2.0)
    """
    attempt = 0
    delay = initial_delay

    while attempt < max_attempts:
        try:
            await self.initialize()
            logger.info(f"PostgreSQL connected on attempt {attempt + 1}")
            return
        except Exception as e:
            attempt += 1
            if attempt >= max_attempts:
                logger.error(
                    f"Failed to connect to PostgreSQL after {max_attempts} attempts: {e}"
                )
                raise StorageError(
                    f"PostgreSQL connection failed after {max_attempts} attempts. "
                    f"Ensure PostgreSQL is running and accessible at {self.config.host}:{self.config.port}",
                    backend="postgres"
                )

            logger.warning(
                f"PostgreSQL connection attempt {attempt} failed: {e}. "
                f"Retrying in {delay:.1f}s..."
            )
            await asyncio.sleep(delay)
            delay *= backoff_factor
```

**Key decisions:**
- Default 5 attempts with 1s initial delay, 2x backoff (1s, 2s, 4s, 8s, 16s)
- Total retry time: ~31 seconds (accommodates slow Docker startup)
- Clear error message guides user to check PostgreSQL status

### Pattern 6: tsvector with Weighted Relevance

**What:** Use PostgreSQL's `setweight()` to boost relevance of specific fields in full-text search. Combine multiple text fields into single tsvector column.

**When to use:** Full-text search where some fields (title, summary) are more important than others (content).

**Example:**
```python
# storage/postgres/keyword_ops.py (NEW)

async def upsert_with_tsvector(
    self,
    chunk_id: str,
    document_text: str,
    metadata: dict[str, Any],
) -> None:
    """Upsert document with weighted tsvector generation.

    Weight hierarchy: A (most important) > B > C > D (least important)
    - Title/filename: weight A
    - Summary: weight B
    - Content: weight C
    """

    # Build weighted tsvector SQL
    # Extracts title from metadata, combines with content
    upsert_sql = """
    INSERT INTO documents (chunk_id, document_text, metadata, tsv)
    VALUES ($1, $2, $3,
        setweight(to_tsvector('english', COALESCE($4, '')), 'A') ||  -- Title
        setweight(to_tsvector('english', COALESCE($5, '')), 'B') ||  -- Summary
        setweight(to_tsvector('english', $2), 'C')                    -- Content
    )
    ON CONFLICT (chunk_id) DO UPDATE SET
        document_text = EXCLUDED.document_text,
        metadata = EXCLUDED.metadata,
        tsv = EXCLUDED.tsv,
        updated_at = NOW()
    """

    title = metadata.get('filename') or metadata.get('title') or ''
    summary = metadata.get('summary') or ''

    async with self.connection_manager.engine.begin() as conn:
        await conn.execute(
            upsert_sql,
            chunk_id,
            document_text,
            metadata,
            title,
            summary,
        )

async def keyword_search(
    self,
    query: str,
    top_k: int,
    language: str = 'english',
) -> list[SearchResult]:
    """Full-text search with ts_rank relevance scoring."""

    search_sql = """
    SELECT
        chunk_id,
        document_text,
        metadata,
        ts_rank(tsv, websearch_to_tsquery($1, $2)) as score
    FROM documents
    WHERE tsv @@ websearch_to_tsquery($1, $2)
    ORDER BY score DESC
    LIMIT $3
    """

    async with self.connection_manager.engine.connect() as conn:
        result = await conn.execute(search_sql, language, query, top_k)
        rows = result.fetchall()

        # Normalize ts_rank scores to 0-1 range
        max_score = max((row.score for row in rows), default=1.0)

        return [
            SearchResult(
                chunk_id=row.chunk_id,
                text=row.document_text,
                metadata=row.metadata,
                score=row.score / max_score if max_score > 0 else 0.0,
            )
            for row in rows
        ]
```

**Key decisions:**
- Use `websearch_to_tsquery()` for user-friendly query syntax (AND, OR, quoted phrases)
- Weight hierarchy: title (A) > summary (B) > content (C)
- `ts_rank()` scores normalized to 0-1 range (protocol requirement)
- Language configurable via YAML (default: english)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Connection pooling** | Custom pool manager | SQLAlchemy async engine | Battle-tested, handles stale connections, pre-ping validation, metrics |
| **Retry logic** | Custom backoff | asyncio.sleep() + exponential formula | Simple, no dependencies, easy to configure |
| **Score normalization** | Service-level fusion | Backend-level RRF | RRF uses ranks not scores, avoids cross-backend normalization complexity |
| **SQL injection** | String concatenation | Parameterized queries ($1, $2) | asyncpg uses PostgreSQL wire protocol, prevents injection |
| **Connection string parsing** | Regex parsing | SQLAlchemy URL parsing | Handles special characters, validates components, standard format |
| **Docker Compose health checks** | Custom TCP socket checks | pg_isready + service_healthy | PostgreSQL official tool, Docker Compose native support |

**Key insight:** PostgreSQL and asyncpg provide production-grade primitives. Don't build custom pooling, retry, or health check logic. Use SQLAlchemy for pooling, asyncio for retry, pg_isready for health checks.

## Common Pitfalls

### Pitfall 1: Embedding Dimension Mismatch After Index Creation

**What goes wrong:** User indexes with OpenAI (3072 dims), switches to Ollama (768 dims) in config.yaml, server starts but queries fail with "dimension mismatch" error deep in pgvector.

**Why it happens:** PostgreSQL vector column has fixed dimensions set at table creation. Changing embedding provider without recreating schema breaks queries.

**How to avoid:**
1. **Validate on startup**: Compare stored embedding metadata (dimensions) to current provider config
2. **Fail fast**: Raise `StorageError` with clear message before first query
3. **Guide user**: Error message includes reset command: `agent-brain reset --yes`

**Warning signs:**
- Tests with fresh database pass, tests with existing data fail
- Error appears during query, not during startup
- PostgreSQL error: `expected 3072 dimensions, got 768`

**Verification:**
```python
# Test: Dimension mismatch detected before queries
async def test_dimension_mismatch_validation():
    # Index with OpenAI (3072 dims)
    backend = PostgresBackend(config_with_openai)
    await backend.initialize()
    await backend.set_embedding_metadata("openai", "text-embedding-3-large", 3072)

    # Switch to Ollama (768 dims) - should fail on initialize
    backend = PostgresBackend(config_with_ollama)
    with pytest.raises(StorageError, match="dimension mismatch"):
        await backend.initialize()
```

### Pitfall 2: Connection Pool Exhaustion Under Load

**What goes wrong:** Under concurrent load (50+ requests), server hangs, timeouts cascade, `/health` endpoint fails. Connection pool metrics show all connections checked out.

**Why it happens:** Default pool_size too small for concurrent FastAPI workload, or connections not returned to pool (missing context manager).

**How to avoid:**
1. **Size pool appropriately**: Default 10 connections + 10 overflow = 20 total (sufficient for typical workloads)
2. **Use context managers**: Always use `async with engine.begin()` or `async with engine.connect()` to ensure connections return to pool
3. **Monitor pool metrics**: Expose pool status in `/health/postgres` endpoint
4. **Load test**: Verify 50+ concurrent requests complete without timeouts

**Warning signs:**
- `/health/postgres` shows `checked_out == total` (pool exhausted)
- Response times increase linearly with concurrent requests
- `asyncio.TimeoutError` under load

**Verification:**
```python
# Test: Concurrent operations don't exhaust pool
async def test_concurrent_queries_pool_health():
    backend = PostgresBackend()
    await backend.initialize()

    # 50 concurrent queries
    tasks = [
        backend.vector_search(embedding, top_k=5, similarity_threshold=0.7)
        for _ in range(50)
    ]
    results = await asyncio.gather(*tasks)

    assert len(results) == 50

    # Pool should release connections
    pool_status = await backend.connection_manager.get_pool_status()
    assert pool_status["checked_out"] < pool_status["total"]
```

### Pitfall 3: Docker Volume Data Loss

**What goes wrong:** User runs `docker compose down -v`, PostgreSQL data deleted, all indexed documents lost. Or bind mount to wrong path (`/var/lib/postgresql` instead of `/var/lib/postgresql/data`), data not persisted.

**Why it happens:** `-v` flag removes named volumes, or incorrect bind mount path doesn't align with PostgreSQL data directory.

**How to avoid:**
1. **Use named volumes**: Docker-managed, persist across `docker compose down` (only lost with `-v`)
2. **Document volume lifecycle**: README clearly explains `down` vs `down -v`
3. **Correct mount path**: PostgreSQL stores data in `/var/lib/postgresql/data` NOT `/var/lib/postgresql`
4. **Volume labels**: Add labels to track purpose and backup requirements

**Warning signs:**
- Data lost after `docker compose down` (should persist)
- Empty mount directory on host
- PostgreSQL reinitializes database on every container restart

**Verification:**
```yaml
# docker-compose.postgres.yml
services:
  postgres:
    image: pgvector/pgvector:pg16
    volumes:
      - agent-brain-postgres-data:/var/lib/postgresql/data  # Correct path

volumes:
  agent-brain-postgres-data:
    labels:
      project: "agent-brain"
      backup: "required"  # Flag for backup scripts
```

### Pitfall 4: RRF Score Inconsistency Between Backends

**What goes wrong:** Same query on ChromaDB and PostgreSQL backends returns different top-k results. Hybrid search heavily favors one backend's results.

**Why it happens:** RRF implementation uses different k values, different result fetch sizes, or doesn't normalize final scores to 0-1 range.

**How to avoid:**
1. **Contract test**: Same test suite validates both backends produce consistent rankings
2. **Standardize RRF parameters**: k=60 (research standard), fetch 2x top_k for both backends
3. **Normalize final scores**: RRF scores to 0-1 range (protocol requirement)
4. **Test with real queries**: Use production query patterns, not synthetic data

**Warning signs:**
- ChromaDB returns [A, B, C], PostgreSQL returns [C, A, B] for same query
- Hybrid search results heavily skewed toward one backend
- Scores outside 0-1 range

**Verification:**
```python
# Contract test: RRF produces consistent rankings
@pytest.mark.parametrize("backend_type", ["chroma", "postgres"])
async def test_rrf_consistency(backend_type, monkeypatch):
    monkeypatch.setenv("AGENT_BRAIN_STORAGE_BACKEND", backend_type)
    backend = get_storage_backend()

    # Same documents, same query
    await backend.upsert_documents(ids, embeddings, docs, metas)
    results = await backend.hybrid_search_with_rrf(
        query="test query",
        query_embedding=query_emb,
        top_k=5,
    )

    # Both backends should return same top-3 (order may vary slightly)
    assert len(results) == 5
    assert all(0 <= r.score <= 1 for r in results)
    # Top-3 chunk_ids should overlap significantly
    assert len(set(r.chunk_id for r in results[:3])) >= 2
```

### Pitfall 5: tsvector Language Configuration Ignored

**What goes wrong:** User sets `storage.postgres.language: spanish` in config.yaml, but tsvector still uses English stemming. Search for "corriendo" doesn't match "correr".

**Why it happens:** SQL uses hardcoded `'english'` in `to_tsvector()` calls, doesn't read config.

**How to avoid:**
1. **Pass language to keyword ops**: PostgresConfig includes language field, passed to keyword_ops methods
2. **Dynamic SQL**: Use f-string or parameterization for language (careful: language is enum not user input)
3. **Validate language**: Pydantic enum for supported languages (english, spanish, french, etc.)
4. **Test with non-English**: Contract tests include non-English query/document pairs

**Warning signs:**
- Non-English queries return zero results
- Stemming doesn't match language (Spanish queries match English stems)
- GIN index created with wrong language

**Verification:**
```python
# Test: tsvector respects language config
async def test_tsvector_spanish_language():
    config = PostgresConfig(language="spanish")
    backend = PostgresBackend(config)

    # Index Spanish document
    await backend.upsert_documents(
        ids=["es1"],
        embeddings=[[0.1] * 768],
        documents=["El perro está corriendo en el parque"],
        metadatas=[{}],
    )

    # Query with Spanish verb stem should match
    results = await backend.keyword_search("correr", top_k=5)
    assert len(results) == 1
    assert results[0].chunk_id == "es1"
```

## Code Examples

Verified patterns from research and Phase 5 architecture:

### PostgreSQL Config Model

```python
# storage/postgres/config.py (NEW)
from pydantic import BaseModel, Field, field_validator
from typing import Any

class PostgresConfig(BaseModel):
    """Configuration for PostgreSQL backend."""

    # Connection parameters
    host: str = Field(default="localhost", description="PostgreSQL host")
    port: int = Field(default=5432, description="PostgreSQL port")
    database: str = Field(default="agent_brain", description="Database name")
    user: str = Field(default="agent_brain", description="Database user")
    password: str = Field(default="", description="Database password")

    # Connection pooling
    pool_size: int = Field(default=10, description="Connection pool size")
    pool_max_overflow: int = Field(default=10, description="Max overflow connections")

    # Full-text search
    language: str = Field(default="english", description="tsvector language")

    # HNSW index parameters
    hnsw_m: int = Field(default=16, description="HNSW index m parameter")
    hnsw_ef_construction: int = Field(
        default=64, description="HNSW ef_construction parameter"
    )

    # Runtime
    debug: bool = Field(default=False, description="Enable SQL echo")

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Validate PostgreSQL full-text search language."""
        supported = {
            "english", "spanish", "french", "german", "italian",
            "portuguese", "russian", "simple"
        }
        if v.lower() not in supported:
            raise ValueError(
                f"Unsupported language '{v}'. "
                f"Supported: {', '.join(sorted(supported))}"
            )
        return v.lower()

    def get_connection_url(self) -> str:
        """Build asyncpg connection URL.

        Format: postgresql+asyncpg://user:password@host:port/database
        """
        # URL encode password (handles special characters)
        from urllib.parse import quote_plus
        password_encoded = quote_plus(self.password) if self.password else ""

        if password_encoded:
            return (
                f"postgresql+asyncpg://{self.user}:{password_encoded}"
                f"@{self.host}:{self.port}/{self.database}"
            )
        else:
            return (
                f"postgresql+asyncpg://{self.user}"
                f"@{self.host}:{self.port}/{self.database}"
            )
```

### Health Endpoint with Pool Metrics

```python
# api/routers/health.py (MODIFY)
from fastapi import APIRouter, Request, HTTPException

router = APIRouter()

@router.get("/postgres")
async def postgres_health(request: Request) -> dict[str, Any]:
    """PostgreSQL backend health check with connection pool metrics.

    Returns:
        - status: "healthy" | "unhealthy"
        - backend: "postgres"
        - pool: connection pool metrics
        - database: database info
    """
    from agent_brain_server.storage import get_effective_backend_type, get_storage_backend

    backend_type = get_effective_backend_type()

    if backend_type != "postgres":
        raise HTTPException(
            status_code=400,
            detail=f"PostgreSQL health endpoint only available when storage backend is 'postgres', current: {backend_type}"
        )

    backend = request.app.state.storage_backend

    try:
        # Get pool metrics
        pool_status = await backend.connection_manager.get_pool_status()

        # Test query
        async with backend.connection_manager.engine.connect() as conn:
            result = await conn.execute("SELECT version()")
            version = result.scalar()

        return {
            "status": "healthy",
            "backend": "postgres",
            "pool": pool_status,
            "database": {
                "version": version,
                "host": backend.config.host,
                "port": backend.config.port,
                "database": backend.config.database,
            },
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "backend": "postgres",
            "error": str(e),
        }
```

### Docker Compose Template

```yaml
# templates/docker-compose.postgres.yml (NEW)
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: agent-brain-postgres
    environment:
      POSTGRES_USER: agent_brain
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-agent_brain_dev}
      POSTGRES_DB: agent_brain
    ports:
      - "${POSTGRES_PORT:-5432}:5432"  # Dynamic port via env var
    volumes:
      - agent-brain-postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agent_brain"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  agent-brain-postgres-data:
    name: agent-brain-postgres-data
    labels:
      project: "agent-brain"
      backup: "required"
      description: "Agent Brain PostgreSQL data with pgvector indexes"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pgvector IVFFlat index | HNSW index | pgvector 0.5.0 (2023) | Better query performance, no training step, slower build |
| Separate BM25 library (rank-bm25) | PostgreSQL tsvector + ts_rank | Built-in (PostgreSQL 8.3+, 2008) | Native integration, GIN index support, no external dependency |
| String-based score fusion | RRF (Reciprocal Rank Fusion) | Research standard (2009), adopted by OpenSearch 2.19 (2024), Elasticsearch 8.9 (2023) | Avoids cross-system score normalization |
| psycopg2 (sync) | asyncpg (native async) | asyncpg 0.18 (2019) | 2-3x faster, asyncio-native, no thread pool overhead |
| Manual connection pooling (PgBouncer) | SQLAlchemy 2.0 async engine | SQLAlchemy 2.0 (2023) | Application-level pooling, pre-ping validation, metrics |
| Manual schema migrations (SQL files) | Embedded SQL in Python | Acceptable for v1 (no Alembic) | Simple drop/recreate strategy, defer Alembic to v2 |

**Deprecated/outdated:**
- **pgvector IVFFlat**: HNSW is now standard (better speed-recall tradeoff)
- **psycopg2 for async apps**: asyncpg is purpose-built for asyncio, significantly faster
- **External BM25 libraries**: PostgreSQL tsvector is battle-tested, no external dependency

## Open Questions

1. **Schema version tracking**
   - What we know: Embedded SQL in Python, auto-creates tables on first connection
   - What's unclear: Should we track schema version in metadata table for future migrations?
   - Recommendation: Phase 6 omits schema versioning (acceptable for v1), add in Phase 7 if Alembic needed

2. **HNSW index parameters for production**
   - What we know: m=16, ef_construction=64 are sensible defaults (research literature)
   - What's unclear: Optimal values vary by dataset size, recall requirements
   - Recommendation: Use defaults, document tuning guidance in Phase 8 (user can adjust via YAML)

3. **Port scanning implementation**
   - What we know: Context says "reuse existing auto-port pattern from multi-instance architecture"
   - What's unclear: Where is this pattern? (Background task found no matches)
   - Recommendation: Implement simple socket-based port scanner (scan 5432-5442 range), fallback to 5432

4. **DATABASE_URL override precedence**
   - What we know: Context says "DATABASE_URL env var as override" for connection config
   - What's unclear: Does DATABASE_URL override all YAML fields or just connection string?
   - Recommendation: DATABASE_URL overrides connection string only (host, port, database, user, password). Pool config stays in YAML.

## Sources

### Primary (HIGH confidence)
- [pgvector GitHub Repository](https://github.com/pgvector/pgvector) - Official pgvector extension, HNSW index documentation
- [pgvector 0.8.0 Released](https://www.postgresql.org/about/news/pgvector-080-released-2952/) - Latest features, iterative scan
- [HNSW Indexes with Postgres and pgvector | Crunchy Data](https://www.crunchydata.com/blog/hnsw-indexes-with-postgres-and-pgvector) - HNSW index best practices
- [asyncpg Usage Documentation](https://magicstack.github.io/asyncpg/current/usage.html) - Official asyncpg connection pooling
- [PostgreSQL Full-Text Search Documentation](https://www.postgresql.org/docs/current/textsearch-indexes.html) - Official tsvector + GIN index docs
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) - Official FastAPI lifecycle management
- [SQLAlchemy 2.0 Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) - Official async engine docs
- Agent Brain codebase:
  - `storage/protocol.py` - StorageBackendProtocol (Phase 5)
  - `storage/factory.py` - Backend factory pattern
  - `config/provider_config.py` - StorageConfig model

### Secondary (MEDIUM confidence)
- [Hybrid Search in PostgreSQL: The Missing Manual | ParadeDB](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual) - RRF implementation with PostgreSQL
- [Introducing Reciprocal Rank Fusion for Hybrid Search - OpenSearch](https://opensearch.org/blog/introducing-reciprocal-rank-fusion-hybrid-search/) - RRF algorithm explanation
- [How to Run PostgreSQL in Docker with Persistence | OneUpTime](https://oneuptime.com/blog/post/2026-01-17-postgresql-docker-persistence/view) - Docker volume best practices
- [FastAPI Lifespan Explained | Medium](https://medium.com/algomart/fastapi-lifespan-explained-the-right-way-to-handle-startup-and-shutdown-logic-f825f38dd304) - Lifespan pattern examples
- [Building an Async Product Management API with FastAPI, Pydantic, and PostgreSQL - Neon Guides](https://neon.com/guides/fastapi-async) - FastAPI + asyncpg integration

### Tertiary (LOW confidence - flagged for validation)
- [Port Scanner using Python | GeeksforGeeks](https://www.geeksforgeeks.org/port-scanner-using-python/) - Port scanning patterns (need to verify threading approach)
- [PostgreSQL Port 5432 Guide | Pinggy](https://pinggy.io/know_your_port/localhost_5432/) - Default port info (basic reference)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - asyncpg and pgvector are industry standard, Phase 5 architecture is proven
- Architecture: HIGH - FastAPI lifespan, SQLAlchemy async engine, RRF algorithm all well-documented
- Pitfalls: MEDIUM-HIGH - Dimension mismatch and pool exhaustion verified in research, Docker volume issues common

**Research date:** 2026-02-11
**Valid until:** 2026-05-11 (90 days - PostgreSQL/pgvector are stable, asyncpg mature)

**Phase 6 scope:** PostgreSQL backend implementation with pgvector + tsvector, async connection pooling, Docker Compose template, health endpoint. Phase 8 handles user-facing setup wizard.
