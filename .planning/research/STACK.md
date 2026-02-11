# Technology Stack: PostgreSQL Dual Storage Backend

**Project:** Agent Brain - PostgreSQL Integration
**Researched:** 2026-02-10
**Confidence:** HIGH

## Executive Summary

Add PostgreSQL + pgvector as an optional dual storage backend to Agent Brain's existing ChromaDB implementation. Use **asyncpg** (NOT psycopg) for maximum async performance with FastAPI, **SQLAlchemy 2.0** for abstraction and migrations, **LlamaIndex PostgreSQL vector store** for consistency with existing architecture, and **native tsvector/tsquery** for full-text search. ChromaDB remains default; PostgreSQL selectable via YAML config following established provider pattern.

**Key Decision**: asyncpg over psycopg3 because benchmarks show 5x faster performance, and Agent Brain is already async-first with FastAPI.

---

## NEW Dependencies for PostgreSQL Backend

### Core PostgreSQL + Vector Support

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **asyncpg** | `^0.30.0` | Async PostgreSQL driver | 5x faster than psycopg3, native async, perfect fit for FastAPI. Recommended by SQLAlchemy for async PostgreSQL backends. |
| **SQLAlchemy** | `^2.0.0` | ORM + migration support | Already in stack as transitive dependency; explicitly add for async engine, connection pooling, schema management. Use `create_async_engine` with asyncpg. |
| **pgvector** | Extension (v0.8.1+) | PostgreSQL vector similarity | Industry-standard vector extension for PostgreSQL. No Python package needed — installed in PostgreSQL itself. |
| **llama-index-vector-stores-postgres** | `^0.7.2` | LlamaIndex PostgreSQL integration | Official LlamaIndex vector store for PostgreSQL with pgvector support. Maintains consistency with existing LlamaIndex architecture. Released Nov 2025. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **alembic** | `^1.15.0` | Database migrations | Schema versioning for PostgreSQL backend. Use async patterns: `async_engine_from_config`, `async with connectable.connect()`. |
| **psycopg2-binary** | `^2.9.10` | Alembic sync fallback | Alembic requires sync driver for migration generation. Binary wheel avoids compilation issues. Only for migrations, NOT runtime. |

---

## Docker Infrastructure

### PostgreSQL with pgvector

| Component | Version | Purpose | Why |
|-----------|---------|---------|-----|
| **pgvector/pgvector** Docker image | `pgvector/pgvector:pg16` or `pgvector/pgvector:0.8.1-pg16` | PostgreSQL 16 + pgvector extension | Official pgvector image. Supports Postgres 16 (current stable). Use `pg16` tag for latest or version-pinned `0.8.1-pg16` for reproducibility. |
| **Docker Compose** | `^3.8` | Local dev environment | Already used in project. Add postgres service with volume persistence. |

**Recommended Docker Compose Configuration:**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: agent_brain
      POSTGRES_PASSWORD: development
      POSTGRES_DB: agent_brain
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-GOAL", "pg_isready", "-U", "agent_brain"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| **Async Driver** | asyncpg | psycopg3 (async mode) | psycopg3 is 5x slower than asyncpg in benchmarks. asyncpg is purpose-built for asyncio, while psycopg3 added async support later. |
| **ORM Layer** | SQLAlchemy 2.0 (async) | Raw asyncpg SQL | SQLAlchemy provides connection pooling, async context managers, migration support (Alembic), and type safety. Worth the abstraction for maintainability. |
| **Vector Store** | llama-index-vector-stores-postgres | Custom pgvector implementation | LlamaIndex integration maintains consistency with existing ChromaDB VectorStore abstraction. Avoid reinventing the wheel. |
| **Full-Text Search** | Native tsvector/tsquery | Recreate BM25 in PostgreSQL | Native PostgreSQL FTS with GIN indexes is production-proven, supports 20+ languages, and requires no additional dependencies. BM25 disk index won't work with PostgreSQL anyway. |
| **Sync Driver (migrations only)** | psycopg2-binary | psycopg2 | Binary wheel avoids C compilation issues on macOS (existing project issue). Development convenience. |
| **PostgreSQL Image** | pgvector/pgvector:pg16 | Official postgres + manual pgvector install | Official pgvector image has extension pre-installed and tested. Reduces setup complexity. |

---

## Storage Abstraction Layer Pattern

### Repository Pattern with Async Protocol

Follow Python's Protocol pattern (similar to existing provider pattern) for storage backend abstraction:

```python
from typing import Protocol
from llama_index.core.schema import Document, TextNode

class VectorStoreBackend(Protocol):
    """Protocol for vector storage backends."""

    async def add_documents(self, documents: list[Document]) -> None:
        """Add documents to vector store."""
        ...

    async def query(
        self,
        query_embedding: list[float],
        top_k: int,
        filters: dict | None = None,
    ) -> list[TextNode]:
        """Query vector store with embedding."""
        ...

    async def delete_all(self) -> None:
        """Clear all documents."""
        ...


class KeywordSearchBackend(Protocol):
    """Protocol for keyword search backends."""

    async def add_documents(self, documents: list[Document]) -> None:
        """Index documents for keyword search."""
        ...

    async def search(
        self,
        query: str,
        top_k: int,
    ) -> list[TextNode]:
        """Keyword search."""
        ...
```

### Configuration Pattern

Extend existing `ProviderSettings` in `config/provider_config.py`:

```yaml
# config.yaml
storage:
  backend: "postgresql"  # or "chromadb" (default)
  postgresql:
    host: "localhost"
    port: 5432
    database: "agent_brain"
    user: "agent_brain"
    password_env: "POSTGRES_PASSWORD"
    pool_size: 10
    max_overflow: 20

embedding:
  provider: "openai"
  model: "text-embedding-3-large"
```

---

## Integration Points with Existing Stack

### 1. LlamaIndex VectorStore Interface

**Current**: `ChromaVectorStore` from `llama-index-vector-stores-chroma`
**New**: `PGVectorStore` from `llama-index-vector-stores-postgres`

Both implement `BasePydanticVectorStore` interface — drop-in replacement.

**Key Integration**:
```python
from llama_index.vector_stores.postgres import PGVectorStore

# Async initialization (required for asyncpg)
vector_store = await PGVectorStore.from_params(
    host="localhost",
    port=5432,
    database="agent_brain",
    user="agent_brain",
    password=os.getenv("POSTGRES_PASSWORD"),
    table_name="document_vectors",
    embed_dim=3072,  # text-embedding-3-large
    hybrid_search=True,  # Enable tsvector full-text search
    hnsw_kwargs={
        "hnsw_m": 16,
        "hnsw_ef_construction": 64,
        "hnsw_ef_search": 40,
    },
)
```

### 2. Full-Text Search Replacement

**Current**: Disk-based BM25 index (`rank-bm25`, `llama-index-retrievers-bm25`)
**New**: PostgreSQL native tsvector with GIN indexes

**Why tsvector Instead of Recreating BM25**:
- Native PostgreSQL feature (no additional dependencies)
- GIN indexes provide O(log n) search performance
- Supports 20+ languages via text search configurations
- Already integrated in LlamaIndex PGVectorStore via `hybrid_search=True`
- BM25 disk index architecture incompatible with PostgreSQL (would require custom implementation)

**Schema**:
```sql
CREATE TABLE document_vectors (
    id UUID PRIMARY KEY,
    content TEXT,
    content_tsvector TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    embedding vector(3072),
    metadata JSONB
);

CREATE INDEX idx_content_tsvector ON document_vectors USING GIN(content_tsvector);
CREATE INDEX idx_embedding_hnsw ON document_vectors USING hnsw(embedding vector_cosine_ops);
```

### 3. FastAPI Async Context Management

**Current**: Synchronous ChromaDB client
**New**: Async SQLAlchemy session with connection pooling

**Lifespan Pattern**:
```python
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    engine = create_async_engine(
        f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}",
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # Verify connections before use
    )
    app.state.engine = engine

    yield

    # Shutdown
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
```

**Dependency Injection**:
```python
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(app.state.engine) as session:
        yield session

@app.post("/index")
async def index_documents(
    session: AsyncSession = Depends(get_db_session),
):
    # Use session for database operations
    ...
```

### 4. Configuration Loading

Extend existing `config/provider_config.py` pattern:

```python
from pydantic import BaseModel

class StorageBackendType(str, Enum):
    CHROMADB = "chromadb"
    POSTGRESQL = "postgresql"

class PostgreSQLConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    database: str = "agent_brain"
    user: str = "agent_brain"
    password_env: str = "POSTGRES_PASSWORD"
    pool_size: int = 10
    max_overflow: int = 20

class StorageConfig(BaseModel):
    backend: StorageBackendType = StorageBackendType.CHROMADB
    postgresql: PostgreSQLConfig | None = None
```

---

## What NOT to Add (Avoid Over-Engineering)

| Anti-Pattern | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **psycopg3 async driver** | 5x slower than asyncpg in benchmarks. psycopg3 added async support later; asyncpg is purpose-built. | Use asyncpg with SQLAlchemy 2.0 async engine. |
| **Custom pgvector wrapper** | LlamaIndex already provides `PGVectorStore` with full pgvector support. | Use `llama-index-vector-stores-postgres` for consistency. |
| **BM25 reimplementation in PostgreSQL** | Complex, unmaintained, worse performance than native tsvector. | Use PostgreSQL native full-text search with GIN indexes. |
| **Synchronous database access** | Agent Brain is async-first with FastAPI. Blocking I/O kills performance. | Use asyncpg + SQLAlchemy async engine + async context managers. |
| **Multiple connection pool libraries** | SQLAlchemy 2.0 has built-in async connection pooling with `AsyncAdaptedQueuePool`. | Configure pool via `create_async_engine(pool_size=10, max_overflow=20)`. |
| **pgvecto.rs** | Separate project (Rust-based pgvector alternative). Adds complexity, non-standard. | Stick with official pgvector extension (C-based, PostgreSQL standard). |
| **Sync migrations with async runtime** | Mixing sync/async causes connection pool conflicts. | Use Alembic async patterns: `async_engine_from_config`, `async with connectable.connect()`. |

---

## Installation Instructions

### 1. Add Dependencies to pyproject.toml

```toml
[tool.poetry.dependencies]
# ... existing dependencies ...

# PostgreSQL Backend (optional)
asyncpg = {version = "^0.30.0", optional = true}
sqlalchemy = {version = "^2.0.0", optional = true}
llama-index-vector-stores-postgres = {version = "^0.7.2", optional = true}
alembic = {version = "^1.15.0", optional = true}

[tool.poetry.group.dev.dependencies]
# ... existing dev dependencies ...
psycopg2-binary = "^2.9.10"  # For Alembic migrations only

[tool.poetry.extras]
# ... existing extras ...
postgresql = [
    "asyncpg",
    "sqlalchemy",
    "llama-index-vector-stores-postgres",
    "alembic",
]
```

### 2. Install with Extra

```bash
cd agent-brain-server
poetry install --extras postgresql

# Or install all extras
poetry install --all-extras
```

### 3. Start PostgreSQL with Docker Compose

```bash
# Create docker-compose.yml in project root
docker-compose up -d postgres

# Verify pgvector extension
docker exec -it <container> psql -U agent_brain -d agent_brain -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 4. Set Environment Variables

```bash
# .env
POSTGRES_PASSWORD=development
AGENT_BRAIN_CONFIG=.claude/agent-brain/config.yaml
```

### 5. Initialize Schema with Alembic

```bash
# Generate initial migration
poetry run alembic revision --autogenerate -m "Initial PostgreSQL schema"

# Apply migration
poetry run alembic upgrade head
```

---

## Confidence Assessment

| Component | Confidence | Source |
|-----------|------------|--------|
| asyncpg driver | HIGH | Official SQLAlchemy docs recommend asyncpg for async PostgreSQL. Benchmarks show 5x faster than psycopg3. |
| SQLAlchemy 2.0 | HIGH | Current stable release (v2.1 as of 2026). Official documentation for async patterns. |
| pgvector extension | HIGH | Official PostgreSQL extension. Docker image `pgvector/pgvector:pg16` verified on Docker Hub. |
| LlamaIndex integration | HIGH | `llama-index-vector-stores-postgres` v0.7.2 released Nov 2025 (current). Official LlamaIndex package. |
| tsvector/tsquery | HIGH | Native PostgreSQL feature since 8.3 (2008). Production-proven for full-text search. |
| Alembic migrations | HIGH | Standard migration tool for SQLAlchemy. Async patterns documented in SQLAlchemy 2.0. |
| Docker Compose | HIGH | Existing tool in project. PostgreSQL + pgvector image verified. |

**Overall Confidence: HIGH**

All recommendations based on official documentation, current versions (verified Feb 2026), and established patterns in the Python/PostgreSQL ecosystem.

---

## Migration Considerations

### From ChromaDB to PostgreSQL (User Data)

**Not required for initial implementation** — backends are independent. Users can:

1. **Keep ChromaDB** (default) — no migration needed
2. **Switch to PostgreSQL** — starts fresh, re-index documents
3. **Run both** (advanced) — different projects use different backends

### Code Changes

| Current | PostgreSQL | Compatibility Layer |
|---------|-----------|---------------------|
| `ChromaVectorStore` | `PGVectorStore` | Abstracted via `VectorStoreBackend` protocol |
| Disk-based BM25 index | PostgreSQL tsvector | Abstracted via `KeywordSearchBackend` protocol |
| Sync ChromaDB client | Async SQLAlchemy session | Async-first API (FastAPI already async) |
| `CHROMA_PERSIST_DIR` env var | `POSTGRES_*` env vars | Config-driven via YAML (`storage.backend`) |

---

## Testing Strategy

### Unit Tests

- Mock `asyncpg.Connection` with `pytest-asyncio`
- Test repository protocol implementations
- Verify SQL query generation

### Integration Tests

- Use Docker Compose with ephemeral PostgreSQL container
- Test pgvector HNSW index creation
- Verify tsvector full-text search with GIN indexes
- Test connection pooling under load

### Performance Benchmarks

Compare PostgreSQL vs ChromaDB:
- Index 10,000 documents (vector + full-text)
- Query latency (p50, p95, p99)
- Concurrent queries (100 simultaneous requests)

Expected: PostgreSQL slightly slower for pure vector search (ChromaDB is specialized), faster for hybrid search (tsvector + vector in single query).

---

## Sources

### PostgreSQL + pgvector
- [GitHub - pgvector/pgvector: Open-source vector similarity search for Postgres](https://github.com/pgvector/pgvector)
- [PostgreSQL Extensions: pgvector | Tiger Data](https://www.tigerdata.com/learn/postgresql-extensions-pgvector)
- [pgvector: Key features, tutorial, and pros and cons [2026 guide]](https://www.instaclustr.com/education/vector-database/pgvector-key-features-tutorial-and-pros-and-cons-2026-guide/)
- [pgvector/pgvector - Docker Image](https://hub.docker.com/r/pgvector/pgvector)

### Python Async PostgreSQL
- [Psycopg 3 vs Asyncpg - fernandoarteaga.dev](https://fernandoarteaga.dev/blog/psycopg-vs-asyncpg/)
- [Building High-Performance Async APIs with FastAPI, SQLAlchemy 2.0, and Asyncpg | Leapcell](https://leapcell.io/blog/building-high-performance-async-apis-with-fastapi-sqlalchemy-2-0-and-asyncpg)
- [Asynchronous I/O (asyncio) — SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Connection Pooling — SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/core/pooling.html)

### LlamaIndex Integration
- [llama-index-vector-stores-postgres · PyPI](https://pypi.org/project/llama-index-vector-stores-postgres/)
- [Postgres Vector Store | LlamaIndex Python Documentation](https://developers.llamaindex.ai/python/examples/vector_stores/postgres/)

### PostgreSQL Full-Text Search
- [PostgreSQL: Documentation: 18: 8.11. Text Search Types](https://www.postgresql.org/docs/current/datatype-textsearch.html)
- [PostgreSQL: Documentation: 18: 12.3. Controlling Text Search](https://www.postgresql.org/docs/current/textsearch-controls.html)
- [PostgreSQL Full-Text Search: Using `to_tsvector` and `to_tsquery` - Sling Academy](https://www.slingacademy.com/article/postgresql-full-text-search-using-to-tsvector-and-to-tsquery/)

### FastAPI Best Practices
- [FastAPI Best Practices for Production: Complete 2026 Guide | FastLaunchAPI Blog](https://fastlaunchapi.dev/blog/fastapi-best-practices-production-2026)
- [Building an Async Product Management API with FastAPI, Pydantic, and PostgreSQL - Neon Guides](https://neon.com/guides/fastapi-async)
- [How to Handle Millions of PostgreSQL Connections in FastAPI Using Async and Connection Pooling | Medium](https://medium.com/write-a-catalyst/how-to-handle-millions-of-postgresql-connections-in-fastapi-using-async-and-connection-pooling-8d63b24f4e43)

### Storage Abstraction Patterns
- [Repository Pattern - Cosmic Python](https://www.cosmicpython.com/book/chapter_02_repository.html)
- [The Repository Pattern | Klaviyo Engineering](https://klaviyo.tech/the-repository-pattern-e321a9929f82)
- [What Is The Repository Pattern And How To Use It In Python? - Pybites](https://pybit.es/articles/repository-pattern-in-python/)
