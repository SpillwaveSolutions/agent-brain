# Architecture Research: PostgreSQL Storage Backend

**Domain:** RAG Storage Abstraction (ChromaDB → PostgreSQL with pgvector + tsvector)
**Researched:** 2026-02-10
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application Layer                 │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│   │ IndexingAPI  │  │  QueryAPI    │  │  HealthAPI   │      │
│   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
├──────────┴──────────────────┴──────────────────┴─────────────┤
│                    Service Layer                              │
│   ┌──────────────────────┐  ┌──────────────────────┐         │
│   │  IndexingService     │  │  QueryService        │         │
│   │  (orchestration)     │  │  (retrieval fusion)  │         │
│   └──────┬───────────────┘  └──────┬───────────────┘         │
├──────────┴──────────────────────────┴──────────────────────────┤
│                    Storage Abstraction Layer                  │
│   ┌──────────────────────────────────────────────────┐        │
│   │         StorageBackendProtocol (NEW)             │        │
│   │  ┌─────────────────┐  ┌─────────────────┐        │        │
│   │  │   Vector Ops    │  │   Keyword Ops   │        │        │
│   │  │   (similarity)  │  │   (BM25/tsvector)│       │        │
│   │  └─────────────────┘  └─────────────────┘        │        │
│   └──────────┬────────────────────┬───────────────────┘        │
├──────────────┴────────────────────┴───────────────────────────┤
│                Backend Implementations                         │
│   ┌────────────────┐              ┌────────────────┐          │
│   │  ChromaBackend │              │  PGBackend     │          │
│   │  (existing)    │              │  (NEW)         │          │
│   │  - VectorStore │              │  - PGVectorOps │          │
│   │  - BM25Manager │              │  - TSVectorOps │          │
│   └────────┬───────┘              └────────┬───────┘          │
├────────────┴──────────────────────────────┴───────────────────┤
│                    Storage Layer                              │
│   ┌───────────┐                  ┌───────────────┐            │
│   │ ChromaDB  │                  │ PostgreSQL    │            │
│   │ (files)   │                  │ (asyncpg)     │            │
│   └───────────┘                  └───────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|----------------|----------------|
| **StorageBackendProtocol** | Abstract interface for storage operations | Python `Protocol` class with vector + keyword ops |
| **PGVectorOps** | Vector similarity search via pgvector | LlamaIndex `PGVectorStore` wrapper |
| **TSVectorOps** | Keyword search via PostgreSQL tsvector | SQLAlchemy + asyncpg + to_tsquery/ts_rank |
| **PGBackend** | PostgreSQL backend coordinator | Combines PGVectorOps + TSVectorOps + connection pool |
| **ChromaBackend** | ChromaDB backend coordinator | Adapts existing VectorStoreManager + BM25IndexManager |
| **BackendFactory** | Backend selection logic | Reads config, instantiates correct backend |
| **Connection Pool** | PostgreSQL connection lifecycle | SQLAlchemy async engine with lifespan management |

## Recommended Project Structure

```
agent-brain-server/agent_brain_server/
├── storage/                       # Storage abstraction
│   ├── __init__.py               # Exports get_storage_backend()
│   ├── protocol.py               # StorageBackendProtocol (NEW)
│   ├── factory.py                # Backend selection (NEW)
│   ├── chroma/                   # ChromaDB backend (REFACTOR)
│   │   ├── __init__.py
│   │   ├── vector_store.py       # Renamed from storage/vector_store.py
│   │   ├── bm25_adapter.py       # Wraps BM25IndexManager
│   │   └── backend.py            # ChromaBackend implementation
│   └── postgres/                 # PostgreSQL backend (NEW)
│       ├── __init__.py
│       ├── config.py             # PGConfig model
│       ├── connection.py         # Connection pool manager
│       ├── vector_ops.py         # PGVectorOps (pgvector integration)
│       ├── keyword_ops.py        # TSVectorOps (tsvector integration)
│       ├── schema.py             # SQLAlchemy models
│       └── backend.py            # PGBackend implementation
├── config/
│   ├── settings.py               # MODIFY: Add STORAGE_BACKEND="chroma"
│   └── provider_config.py        # MODIFY: Add StorageConfig to YAML schema
├── services/
│   ├── indexing_service.py       # MODIFY: Use storage protocol
│   └── query_service.py          # MODIFY: Use storage protocol
└── api/
    └── main.py                   # MODIFY: Add lifespan for PG connection pool
```

### Structure Rationale

- **storage/protocol.py**: Single Protocol class defines the contract. Services depend only on this.
- **storage/chroma/**: Existing ChromaDB code moves here. Adapters implement protocol methods.
- **storage/postgres/**: New PostgreSQL code isolated. Clear boundary for new dependencies (asyncpg, SQLAlchemy).
- **storage/factory.py**: Single source of truth for backend selection. Config-driven, not environment hacks.

## Architectural Patterns

### Pattern 1: Storage Protocol (Structural Subtyping)

**What:** Python `Protocol` class defining storage operations. Both backends implement it without inheritance.

**When to use:** Multiple backends that share the same API shape but different implementations.

**Trade-offs:**
- **Pro**: No heavyweight ORM abstraction. Simple duck typing with type safety.
- **Pro**: Existing ChromaDB code doesn't need major refactor (just wrap in protocol).
- **Con**: Protocol methods must cover both backends' capabilities. Lowest common denominator.

**Example:**
```python
from typing import Protocol, Any
from dataclasses import dataclass

@dataclass
class SearchResult:
    text: str
    metadata: dict[str, Any]
    score: float
    chunk_id: str

class StorageBackendProtocol(Protocol):
    """Protocol for storage backend operations."""

    async def initialize(self) -> None:
        """Initialize storage backend."""
        ...

    async def upsert_documents(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> int:
        """Upsert documents with embeddings."""
        ...

    async def vector_search(
        self,
        query_embedding: list[float],
        top_k: int,
        similarity_threshold: float,
        where: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Perform vector similarity search."""
        ...

    async def keyword_search(
        self,
        query: str,
        top_k: int,
        source_types: list[str] | None = None,
        languages: list[str] | None = None,
    ) -> list[SearchResult]:
        """Perform keyword search (BM25 or tsvector)."""
        ...

    async def get_count(self, where: dict[str, Any] | None = None) -> int:
        """Get document count."""
        ...

    async def get_by_id(self, chunk_id: str) -> dict[str, Any] | None:
        """Get document by ID."""
        ...

    async def reset(self) -> None:
        """Clear all documents."""
        ...

    @property
    def is_initialized(self) -> bool:
        """Check if backend is initialized."""
        ...
```

### Pattern 2: PostgreSQL Connection Pool Lifecycle

**What:** SQLAlchemy async engine managed via FastAPI lifespan context manager.

**When to use:** Any FastAPI app with async database connections.

**Trade-offs:**
- **Pro**: Connections initialized before first request, closed gracefully on shutdown.
- **Pro**: Lifespan pattern is FastAPI standard (replaces deprecated @app.on_event).
- **Con**: Requires FastAPI 0.95.0+.

**Example:**
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create connection pool
    if settings.STORAGE_BACKEND == "postgres":
        engine = create_async_engine(
            settings.POSTGRES_URL,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        app.state.pg_engine = engine
        # Initialize storage backend
        backend = get_storage_backend()
        await backend.initialize()

    yield  # Application runs

    # Shutdown: Close connections
    if hasattr(app.state, "pg_engine"):
        await app.state.pg_engine.dispose()

app = FastAPI(lifespan=lifespan)
```

### Pattern 3: LlamaIndex PGVectorStore Integration

**What:** Use LlamaIndex's `PGVectorStore` as the vector backend, wrapped in our protocol.

**When to use:** When you want pgvector but don't want to write raw SQL for vector operations.

**Trade-offs:**
- **Pro**: LlamaIndex handles pgvector index creation (HNSW), async queries, metadata filtering.
- **Pro**: Consistent with existing LlamaIndex usage (BM25Retriever, TextNode).
- **Con**: Adds llama-index-vector-stores-postgres dependency.
- **Con**: Must adapt LlamaIndex's retriever pattern to our protocol's search methods.

**Example:**
```python
from llama_index.vector_stores.postgres import PGVectorStore
from sqlalchemy.ext.asyncio import AsyncEngine

class PGVectorOps:
    """PostgreSQL pgvector operations via LlamaIndex."""

    def __init__(self, engine: AsyncEngine, table_name: str = "embeddings"):
        self.engine = engine
        self.store = PGVectorStore.from_params(
            database="agent_brain",
            host="localhost",
            password="***",
            port=5432,
            user="agent_brain",
            table_name=table_name,
            embed_dim=3072,  # From settings
            hybrid_search=False,  # We handle keyword search separately
            hnsw_kwargs={
                "hnsw_m": 16,
                "hnsw_ef_construction": 64,
                "hnsw_ef_search": 40,
            },
        )

    async def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        similarity_threshold: float = 0.0,
        where: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        # LlamaIndex query logic
        query_bundle = VectorStoreQuery(
            query_embedding=query_embedding,
            similarity_top_k=top_k,
            filters=self._build_filters(where),
        )
        result = await self.store.aquery(query_bundle)
        # Convert to SearchResult
        return [
            SearchResult(
                text=node.get_content(),
                metadata=node.metadata,
                score=score,
                chunk_id=node.node_id,
            )
            for node, score in zip(result.nodes, result.similarities)
            if score >= similarity_threshold
        ]
```

### Pattern 4: PostgreSQL tsvector for Keyword Search

**What:** Use PostgreSQL's native full-text search (tsvector + GIN index) instead of BM25Retriever.

**When to use:** When PostgreSQL backend is active and you want integrated keyword search.

**Trade-offs:**
- **Pro**: Native to PostgreSQL. No external BM25 index files.
- **Pro**: GIN index is fast for large corpora.
- **Con**: ts_rank is not true BM25 (lacks term saturation). Consider pg_textsearch extension for true BM25.
- **Con**: Requires creating tsvector column and GIN index during schema setup.

**Example:**
```python
from sqlalchemy import select, func, Column, String, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import TSVECTOR

class TSVectorOps:
    """PostgreSQL tsvector keyword search operations."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def keyword_search(
        self,
        query: str,
        top_k: int = 5,
        source_types: list[str] | None = None,
        languages: list[str] | None = None,
    ) -> list[SearchResult]:
        async with AsyncSession(self.engine) as session:
            # Build query
            stmt = (
                select(
                    EmbeddingTable.chunk_id,
                    EmbeddingTable.text,
                    EmbeddingTable.metadata,
                    func.ts_rank(
                        EmbeddingTable.text_tsvector,
                        func.to_tsquery("english", query)
                    ).label("rank")
                )
                .where(
                    EmbeddingTable.text_tsvector.op("@@")(
                        func.to_tsquery("english", query)
                    )
                )
                .order_by(func.ts_rank(
                    EmbeddingTable.text_tsvector,
                    func.to_tsquery("english", query)
                ).desc())
                .limit(top_k)
            )

            # Apply filters
            if source_types:
                stmt = stmt.where(
                    EmbeddingTable.metadata["source_type"].astext.in_(source_types)
                )
            if languages:
                stmt = stmt.where(
                    EmbeddingTable.metadata["language"].astext.in_(languages)
                )

            result = await session.execute(stmt)
            rows = result.all()

            return [
                SearchResult(
                    chunk_id=row.chunk_id,
                    text=row.text,
                    metadata=row.metadata,
                    score=row.rank,
                )
                for row in rows
            ]
```

## PostgreSQL Schema Design

### Tables

```sql
-- Main embeddings table
CREATE TABLE embeddings (
    chunk_id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    embedding vector(3072),  -- pgvector type, dimension from config
    text_tsvector tsvector,  -- For keyword search
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_embeddings_vector
    ON embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_embeddings_tsvector
    ON embeddings
    USING gin (text_tsvector);

CREATE INDEX idx_embeddings_source_type
    ON embeddings ((metadata->>'source_type'));

CREATE INDEX idx_embeddings_language
    ON embeddings ((metadata->>'language'));

-- Trigger to auto-update tsvector
CREATE OR REPLACE FUNCTION embeddings_tsvector_update()
RETURNS TRIGGER AS $$
BEGIN
    NEW.text_tsvector := to_tsvector('english', NEW.text);
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tsvector_update
    BEFORE INSERT OR UPDATE ON embeddings
    FOR EACH ROW
    EXECUTE FUNCTION embeddings_tsvector_update();

-- Metadata table (for embedding provider tracking)
CREATE TABLE storage_metadata (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### Schema Rationale

- **vector(3072)**: pgvector column, dimension matches OpenAI text-embedding-3-large.
- **HNSW index**: Better recall/speed tradeoff than IVFFlat. Parameters tuned for 1k-100k documents.
- **GIN index on tsvector**: Fast keyword search. English language default, configurable.
- **JSONB metadata**: Flexible schema for source_type, language, file_path, etc.
- **Trigger for tsvector**: Auto-update on insert/update. No manual tsvector management.

## Data Flow

### Indexing Flow (PostgreSQL Backend)

```
Document Loader
    ↓ (load files)
Chunker (CodeChunker / ContextAwareChunker)
    ↓ (create chunks)
EmbeddingGenerator
    ↓ (generate embeddings)
PGBackend.upsert_documents()
    ↓
┌────────────────────────────────────────┐
│  PGVectorOps + TSVectorOps             │
│  ┌────────────────┐                    │
│  │ BEGIN TRANSACTION                   │
│  │ INSERT INTO embeddings              │
│  │   (chunk_id, text, embedding,       │
│  │    metadata)                         │
│  │ VALUES (...)                         │
│  │ ON CONFLICT (chunk_id)               │
│  │   DO UPDATE SET ...                  │
│  │ COMMIT                               │
│  └────────────────┘                    │
│  (trigger auto-updates text_tsvector)  │
└────────────────────────────────────────┘
```

### Query Flow (Hybrid Search)

```
QueryService.execute_hybrid_query()
    ↓
┌────────────────────────────────────────┐
│  Vector Search                          │
│  PGVectorOps.similarity_search()        │
│    ↓ (pgvector HNSW index)              │
│  [top_k results with vector scores]    │
└────────────────────────────────────────┘
           ↓
┌────────────────────────────────────────┐
│  Keyword Search                         │
│  TSVectorOps.keyword_search()           │
│    ↓ (tsvector GIN index)               │
│  [top_k results with ts_rank scores]   │
└────────────────────────────────────────┘
           ↓
┌────────────────────────────────────────┐
│  Fusion Layer (existing logic)         │
│  Reciprocal Score Fusion                │
│    ↓                                    │
│  [combined results, top_k]             │
└────────────────────────────────────────┘
```

### Configuration Flow

```
config.yaml (or env vars)
    ↓
load_provider_settings()
    ↓
ProviderSettings
  - storage:
      backend: "postgres"  # or "chroma"
      postgres:
        host: "localhost"
        port: 5432
        database: "agent_brain"
        user: "agent_brain"
        password_env: "POSTGRES_PASSWORD"
        pool_size: 10
        max_overflow: 20
    ↓
BackendFactory.create_backend()
    ↓ (if backend == "postgres")
PGBackend.__init__()
  ↓ create_async_engine()
  ↓ PGVectorOps(engine)
  ↓ TSVectorOps(engine)
    ↓
await backend.initialize()
  ↓ run schema migrations
  ↓ create indexes if not exist
```

## Integration Points with Existing Code

### Files to Modify (Minimal Changes)

| File | Changes Required | Integration Point |
|------|------------------|-------------------|
| `services/indexing_service.py` | Replace `self.vector_store` with `self.storage_backend: StorageBackendProtocol` | Lines 65, 92, 418-423 (upsert_documents) |
| `services/query_service.py` | Replace `self.vector_store` + `self.bm25_manager` with `self.storage_backend` | Lines 92, 214-221 (vector), 243-269 (keyword) |
| `config/settings.py` | Add `STORAGE_BACKEND: str = "chroma"`, `POSTGRES_*` settings | New config fields |
| `config/provider_config.py` | Add `StorageConfig` to YAML schema | New YAML section |
| `api/main.py` | Add lifespan context manager for PG connection pool | New lifespan function |
| `storage/__init__.py` | Export `get_storage_backend()` factory | New factory method |

### Files to Create (New Code)

| File | Purpose |
|------|---------|
| `storage/protocol.py` | `StorageBackendProtocol` definition |
| `storage/factory.py` | Backend selection logic |
| `storage/chroma/backend.py` | ChromaBackend adapter (wraps existing code) |
| `storage/postgres/config.py` | `PGConfig` Pydantic model |
| `storage/postgres/connection.py` | Connection pool manager |
| `storage/postgres/schema.py` | SQLAlchemy table models |
| `storage/postgres/vector_ops.py` | PGVectorOps (pgvector integration) |
| `storage/postgres/keyword_ops.py` | TSVectorOps (tsvector integration) |
| `storage/postgres/backend.py` | PGBackend implementation |

### Dependency Injection Pattern

**Current (ChromaDB-only):**
```python
class QueryService:
    def __init__(
        self,
        vector_store: VectorStoreManager | None = None,
        bm25_manager: BM25IndexManager | None = None,
    ):
        self.vector_store = vector_store or get_vector_store()
        self.bm25_manager = bm25_manager or get_bm25_manager()
```

**New (Backend-agnostic):**
```python
class QueryService:
    def __init__(
        self,
        storage_backend: StorageBackendProtocol | None = None,
    ):
        from agent_brain_server.storage import get_storage_backend
        self.storage_backend = storage_backend or get_storage_backend()
```

## Scaling Considerations

| Scale | ChromaDB Backend | PostgreSQL Backend |
|-------|------------------|-------------------|
| 0-10k documents | Fine. In-memory ChromaDB. | Overkill. Use ChromaDB. |
| 10k-100k documents | Works. Persistent ChromaDB. BM25 index on disk. | Better. Indexed queries, connection pooling. |
| 100k-1M documents | Slow vector search. BM25 index grows large. | Recommended. HNSW scales well. GIN index efficient. |
| 1M+ documents | Not recommended. Memory limits. | Needs tuning (index params, pool size, sharding). |

### Scaling Priorities (PostgreSQL)

1. **First bottleneck: Vector search latency (100k+ docs)**
   - **Symptom**: Query times > 1 second for top_k=10.
   - **Fix**: Tune HNSW parameters (`hnsw_ef_search`, `hnsw_m`). Increase shared_buffers.
   - **Reference**: [HNSW Tuning Guide](https://www.crunchydata.com/blog/hnsw-indexes-with-postgres-and-pgvector)

2. **Second bottleneck: Connection pool exhaustion (high concurrency)**
   - **Symptom**: "connection pool exhausted" errors under load.
   - **Fix**: Increase `pool_size` + `max_overflow`. Use PgBouncer for connection pooling.
   - **Reference**: [FastAPI Connection Pooling](https://asifmuhammad.com/articles/database-pooling-fastapi)

3. **Third bottleneck: Index build time (large ingestion)**
   - **Symptom**: Initial indexing takes hours for 1M+ docs.
   - **Fix**: Increase `maintenance_work_mem`, use `max_parallel_maintenance_workers=7`.
   - **Reference**: [AWS HNSW Indexing](https://aws.amazon.com/blogs/database/accelerate-hnsw-indexing-and-searching-with-pgvector-on-amazon-aurora-postgresql-compatible-edition-and-amazon-rds-for-postgresql/)

## Anti-Patterns

### Anti-Pattern 1: Abstract Base Class Instead of Protocol

**What people do:** Create abstract base class with `@abstractmethod` decorators.

**Why it's wrong:** Forces inheritance, complicates testing, breaks existing ChromaDB code.

**Do this instead:** Use `typing.Protocol` for structural subtyping. No inheritance needed.

```python
# BAD: Inheritance required
class StorageBackend(ABC):
    @abstractmethod
    async def upsert_documents(self, ...): ...

class ChromaBackend(StorageBackend):  # Must inherit
    async def upsert_documents(self, ...): ...

# GOOD: Duck typing
class StorageBackendProtocol(Protocol):
    async def upsert_documents(self, ...): ...

class ChromaBackend:  # No inheritance
    async def upsert_documents(self, ...): ...  # Just implement methods
```

### Anti-Pattern 2: Global Database Engine

**What people do:** Create engine at module level: `engine = create_async_engine(...)`.

**Why it's wrong:** Engine created before FastAPI app starts. No graceful shutdown. Hard to test.

**Do this instead:** Use FastAPI lifespan to manage engine lifecycle.

```python
# BAD: Global engine
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine(...)  # Created at import time

# GOOD: Lifespan-managed engine
@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_async_engine(...)
    app.state.pg_engine = engine
    yield
    await engine.dispose()
```

### Anti-Pattern 3: Mixing BM25Retriever with PostgreSQL

**What people do:** Keep BM25IndexManager when using PostgreSQL backend.

**Why it's wrong:** Duplicates keyword search logic. BM25 index on disk + tsvector in DB = wasted storage.

**Do this instead:** When PostgreSQL backend is active, keyword search uses tsvector only. BM25IndexManager disabled.

### Anti-Pattern 4: Hardcoding Embedding Dimensions

**What people do:** `vector(3072)` in schema creation, assumes OpenAI embeddings.

**Why it's wrong:** Breaks when switching embedding providers (Ollama nomic-embed-text = 768 dimensions).

**Do this instead:** Read dimensions from settings/metadata, create schema dynamically.

```python
# BAD: Hardcoded
CREATE TABLE embeddings (embedding vector(3072));

# GOOD: Dynamic
from agent_brain_server.indexing import get_embedding_generator
dimensions = get_embedding_generator().get_embedding_dimensions()
# Use dimensions in schema creation
```

## Connection Lifecycle Management

### Lifespan Pattern (Recommended)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from agent_brain_server.config import settings
from agent_brain_server.storage import get_storage_backend

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: startup and shutdown."""

    # STARTUP
    logger.info(f"Initializing storage backend: {settings.STORAGE_BACKEND}")

    if settings.STORAGE_BACKEND == "postgres":
        # Import PostgreSQL dependencies only when needed
        from agent_brain_server.storage.postgres.connection import create_engine

        # Create connection pool
        engine = await create_engine(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            database=settings.POSTGRES_DATABASE,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            pool_size=settings.POSTGRES_POOL_SIZE,
            max_overflow=settings.POSTGRES_MAX_OVERFLOW,
        )
        app.state.pg_engine = engine
        logger.info("PostgreSQL connection pool created")

    # Initialize storage backend (runs migrations if PG)
    backend = get_storage_backend()
    await backend.initialize()

    yield  # Application runs

    # SHUTDOWN
    if settings.STORAGE_BACKEND == "postgres" and hasattr(app.state, "pg_engine"):
        logger.info("Closing PostgreSQL connection pool")
        await app.state.pg_engine.dispose()

    logger.info("Application shutdown complete")

app = FastAPI(lifespan=lifespan)
```

### Connection Pool Configuration

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

async def create_engine(
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    pool_size: int = 10,
    max_overflow: int = 20,
) -> AsyncEngine:
    """Create SQLAlchemy async engine with optimal pool settings."""

    database_url = (
        f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    )

    engine = create_async_engine(
        database_url,
        pool_size=pool_size,          # Core pool size
        max_overflow=max_overflow,    # Extra connections under load
        pool_pre_ping=True,           # Verify connections before use
        pool_recycle=3600,            # Recycle connections after 1 hour
        echo=False,                   # Don't log SQL (use DEBUG mode)
        future=True,                  # Use SQLAlchemy 2.0 style
    )

    return engine
```

## GraphRAG Considerations

**Current State:** GraphRAG (SimplePropertyGraphStore) stays on ChromaDB for this milestone.

**Rationale:**
1. GraphRAG is optional (ENABLE_GRAPH_INDEX flag).
2. PostgreSQL backend focuses on core RAG (vector + keyword).
3. Graph data is small (triplets), doesn't benefit from PostgreSQL.

**Future Consideration (Phase 2.2+):**
- Move graph storage to PostgreSQL using [Apache AGE](https://age.apache.org/) extension.
- Requires separate protocol: `GraphStoreProtocol`.
- Outside scope of this milestone.

## Build Order (Considering Dependencies)

### Stage 1: Protocol Definition (No Dependencies)

1. Create `storage/protocol.py` with `StorageBackendProtocol`.
2. Create `storage/factory.py` with `get_storage_backend()` stub.
3. Write unit tests for protocol contract (mock implementations).

### Stage 2: ChromaDB Adapter (Existing Code Refactor)

4. Move `storage/vector_store.py` → `storage/chroma/vector_store.py`.
5. Create `storage/chroma/bm25_adapter.py` wrapping `BM25IndexManager`.
6. Create `storage/chroma/backend.py` implementing `StorageBackendProtocol`.
7. Update `storage/__init__.py` to export ChromaBackend.
8. Update tests to use ChromaBackend via protocol.

### Stage 3: PostgreSQL Schema and Connection

9. Create `storage/postgres/config.py` with `PGConfig` Pydantic model.
10. Create `storage/postgres/schema.py` with SQLAlchemy models.
11. Create `storage/postgres/connection.py` with connection pool manager.
12. Write migration script to create tables and indexes.
13. Write integration tests for connection lifecycle.

### Stage 4: PostgreSQL Vector Operations

14. Add `llama-index-vector-stores-postgres` to pyproject.toml.
15. Create `storage/postgres/vector_ops.py` with `PGVectorOps`.
16. Integrate LlamaIndex `PGVectorStore`.
17. Write integration tests for vector search.

### Stage 5: PostgreSQL Keyword Operations

18. Create `storage/postgres/keyword_ops.py` with `TSVectorOps`.
19. Implement tsvector search with SQLAlchemy.
20. Write integration tests for keyword search.

### Stage 6: PostgreSQL Backend Integration

21. Create `storage/postgres/backend.py` implementing `StorageBackendProtocol`.
22. Combine `PGVectorOps` + `TSVectorOps`.
23. Update `storage/factory.py` to select backend based on config.
24. Write end-to-end tests with PostgreSQL backend.

### Stage 7: Configuration and Service Updates

25. Update `config/settings.py` with PostgreSQL settings.
26. Update `config/provider_config.py` with `StorageConfig` YAML schema.
27. Update `services/indexing_service.py` to use `storage_backend`.
28. Update `services/query_service.py` to use `storage_backend`.
29. Add lifespan to `api/main.py` for connection pool management.

### Stage 8: Documentation and Testing

30. Update developer docs with PostgreSQL setup instructions.
31. Write PostgreSQL-specific tests (CI matrix: ChromaDB + PostgreSQL).
32. Update `quick_start_guide.sh` with PostgreSQL option.
33. Run full test suite with both backends.

## Configuration Schema (YAML)

### New storage Section

```yaml
# config.yaml (or providers.yaml extended)

storage:
  backend: "postgres"  # "chroma" or "postgres"

  # PostgreSQL configuration (only used when backend=postgres)
  postgres:
    host: "localhost"
    port: 5432
    database: "agent_brain"
    user: "agent_brain"
    password_env: "POSTGRES_PASSWORD"  # Environment variable name
    pool_size: 10
    max_overflow: 20
    table_name: "embeddings"
    # HNSW index tuning
    hnsw:
      m: 16
      ef_construction: 64
      ef_search: 40
    # tsvector config
    text_search_config: "english"  # PostgreSQL text search config

# Existing sections remain
embedding:
  provider: "openai"
  model: "text-embedding-3-large"
  api_key_env: "OPENAI_API_KEY"

summarization:
  provider: "anthropic"
  model: "claude-haiku-4-5-20251001"
  api_key_env: "ANTHROPIC_API_KEY"

reranker:
  provider: "sentence-transformers"
  model: "cross-encoder/ms-marco-MiniLM-L-6-v2"
```

### Environment Variable Overrides

```bash
# Override backend via env var
export AGENT_BRAIN_STORAGE_BACKEND=postgres

# PostgreSQL connection
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DATABASE=agent_brain
export POSTGRES_USER=agent_brain
export POSTGRES_PASSWORD=secret123

# Pool tuning
export POSTGRES_POOL_SIZE=10
export POSTGRES_MAX_OVERFLOW=20
```

## Sources

**LlamaIndex Integration:**
- [Postgres - LlamaIndex](https://developers.llamaindex.ai/python/framework-api-reference/storage/vector_store/postgres/)
- [Postgres Vector Store Example](https://developers.llamaindex.ai/python/examples/vector_stores/postgres/)
- [llama-index-vector-stores-postgres PyPI](https://pypi.org/project/llama-index-vector-stores-postgres/)

**pgvector Performance:**
- [HNSW Indexes with Postgres and pgvector](https://www.crunchydata.com/blog/hnsw-indexes-with-postgres-and-pgvector)
- [AWS HNSW Indexing Performance](https://aws.amazon.com/blogs/database/accelerate-hnsw-indexing-and-searching-with-pgvector-on-amazon-aurora-postgresql-compatible-edition-and-amazon-rds-for-postgresql/)
- [pgvector GitHub](https://github.com/pgvector/pgvector)

**PostgreSQL Full-Text Search:**
- [PostgreSQL Full-text Search Documentation](https://www.postgresql.org/docs/current/textsearch-controls.html)
- [Full-text Search with SQLAlchemy](https://amitosh.medium.com/full-text-search-fts-with-postgresql-and-sqlalchemy-edc436330a0c)
- [pg_textsearch: BM25 in PostgreSQL](https://www.tigerdata.com/blog/introducing-pg_textsearch-true-bm25-ranking-hybrid-retrieval-postgres)

**FastAPI and SQLAlchemy Async:**
- [Building High-Performance Async APIs with FastAPI, SQLAlchemy 2.0, and Asyncpg](https://leapcell.io/blog/building-high-performance-async-apis-with-fastapi-sqlalchemy-2-0-and-asyncpg)
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [SQLAlchemy Connection Pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html)

**Python Protocol Pattern:**
- [PEP 544 – Protocols](https://peps.python.org/pep-0544/)
- [Building Implicit Interfaces with Protocol Classes](https://andrewbrookins.com/technology/building-implicit-interfaces-in-python-with-protocol-classes/)
- [Repository Pattern in Python](https://pybit.es/articles/repository-pattern-in-python/)

---
*Architecture research for: PostgreSQL storage backend with pgvector and tsvector*
*Researched: 2026-02-10*
*Confidence: HIGH (official docs + LlamaIndex integration + community best practices)*
