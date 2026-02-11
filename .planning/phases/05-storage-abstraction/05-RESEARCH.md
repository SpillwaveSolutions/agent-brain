# Phase 5: Storage Backend Abstraction Layer - Research

**Researched:** 2026-02-10
**Domain:** Storage abstraction layer for RAG systems (ChromaDB + PostgreSQL dual backend)
**Confidence:** HIGH

## Summary

Phase 5 creates an async-first storage protocol to decouple services from concrete storage implementations, enabling ChromaDB and PostgreSQL backends without leaky abstractions. The architecture follows the proven YAML-based provider configuration pattern from v3.0, applies Python Protocol (PEP 544) for structural subtyping, and uses `asyncio.to_thread()` to wrap ChromaDB's synchronous API in an async interface.

**Critical insight:** ChromaDB is synchronous, PostgreSQL (asyncpg) is async. The storage protocol MUST be async-first to support PostgreSQL efficiently. ChromaDB adapter wraps sync calls in `asyncio.to_thread()` to maintain unified async interface without blocking the event loop.

**Primary recommendation:** Design the storage protocol interface completely independent of either backend, normalize backend-specific behaviors (score ranges, exception types, metadata formats) at the adapter boundary, and use contract tests to verify identical behavior across both backends.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| typing.Protocol | stdlib | Storage backend interface | PEP 544 structural subtyping, no inheritance required |
| asyncio | stdlib | Async/await primitives + to_thread wrapper | ChromaDB sync → async adaptation without blocking |
| Pydantic | 2.x | YAML config validation (StorageConfig) | Consistent with existing provider config pattern |
| PyYAML | 6.x | Config file parsing | Existing provider config dependency |

### Backend-Specific (Optional)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| chromadb | ^0.4.0 | Vector + metadata storage (existing) | Default backend, embedded use |
| asyncpg | ^0.29.0 | PostgreSQL async driver | PostgreSQL backend only |
| SQLAlchemy | 2.x (async) | ORM + connection pooling | PostgreSQL backend only |
| llama-index-vector-stores-postgres | ^0.4.0 | pgvector integration (optional) | If using LlamaIndex for PG (see alternatives) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| LlamaIndex PGVectorStore | asyncpg + raw SQL for pgvector | More control, fewer dependencies, but more code |
| Protocol | Abstract Base Class (ABC) | ABC forces inheritance, breaks existing ChromaDB code |
| YAML config | Environment variables only | YAML provides better structure for complex config |

**Installation:**
```bash
# Core dependencies (already installed)
# asyncio, typing are stdlib

# PostgreSQL backend (optional, Phase 6+)
cd agent-brain-server
poetry add asyncpg sqlalchemy[asyncio] psycopg2-binary
# If using LlamaIndex integration:
poetry add llama-index-vector-stores-postgres
```

## Architecture Patterns

### Recommended Project Structure
```
agent-brain-server/agent_brain_server/
├── storage/
│   ├── __init__.py               # MODIFY: Export get_storage_backend()
│   ├── protocol.py               # NEW: StorageBackendProtocol
│   ├── factory.py                # NEW: Backend selection logic
│   ├── chroma/                   # NEW: ChromaDB adapter
│   │   ├── __init__.py
│   │   ├── backend.py            # NEW: ChromaBackend (implements protocol)
│   │   ├── vector_store.py       # MOVE: from storage/vector_store.py
│   │   └── bm25_adapter.py       # NEW: Wraps BM25IndexManager
│   └── postgres/                 # NEW: PostgreSQL backend (Phase 6)
│       ├── __init__.py
│       ├── backend.py            # PostgresBackend (implements protocol)
│       ├── config.py             # PostgresConfig Pydantic model
│       ├── connection.py         # Connection pool manager
│       ├── vector_ops.py         # pgvector operations
│       └── keyword_ops.py        # tsvector operations
├── config/
│   ├── settings.py               # MODIFY: Add STORAGE_BACKEND
│   └── provider_config.py        # MODIFY: Add StorageConfig to schema
├── services/
│   ├── indexing_service.py       # MODIFY: Use storage_backend protocol
│   └── query_service.py          # MODIFY: Use storage_backend protocol
└── api/
    └── main.py                   # MODIFY: Add lifespan for PG pool (Phase 6)
```

### Pattern 1: Async-First Storage Protocol

**What:** Python `Protocol` class defining all storage operations as async methods, implemented by both ChromaDB (sync wrapped in asyncio.to_thread) and PostgreSQL (native async).

**When to use:** Multiple storage backends with different sync/async characteristics that must share identical interface.

**Example:**
```python
# storage/protocol.py
from typing import Protocol, Any
from dataclasses import dataclass

@dataclass
class SearchResult:
    """Backend-agnostic search result."""
    text: str
    metadata: dict[str, Any]
    score: float  # Normalized 0-1 range
    chunk_id: str

class StorageBackendProtocol(Protocol):
    """Protocol for storage backend operations.

    All methods are async. Backends must normalize:
    - Scores to 0-1 range (vector and keyword)
    - Exceptions to StorageError
    - Metadata serialization to JSON-compatible dicts
    """

    async def initialize(self) -> None:
        """Initialize storage backend (create indexes, validate schema)."""
        ...

    async def upsert_documents(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> int:
        """Upsert documents with embeddings.

        Returns:
            Number of documents upserted
        """
        ...

    async def vector_search(
        self,
        query_embedding: list[float],
        top_k: int,
        similarity_threshold: float,
        where: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Vector similarity search.

        Args:
            query_embedding: Query vector
            top_k: Max results
            similarity_threshold: Minimum score (0-1 normalized)
            where: Metadata filters (backend-specific translation)

        Returns:
            Results with normalized scores (0-1, higher=better)
        """
        ...

    async def keyword_search(
        self,
        query: str,
        top_k: int,
        source_types: list[str] | None = None,
        languages: list[str] | None = None,
    ) -> list[SearchResult]:
        """Keyword search (BM25 or tsvector).

        Returns:
            Results with normalized scores (0-1, higher=better)
        """
        ...

    async def get_count(self, where: dict[str, Any] | None = None) -> int:
        """Get document count with optional metadata filter."""
        ...

    async def get_by_id(self, chunk_id: str) -> dict[str, Any] | None:
        """Get document by chunk ID."""
        ...

    async def reset(self) -> None:
        """Clear all documents (destructive)."""
        ...

    async def get_embedding_metadata(self) -> EmbeddingMetadata | None:
        """Get stored embedding provider metadata."""
        ...

    async def set_embedding_metadata(
        self, provider: str, model: str, dimensions: int
    ) -> None:
        """Store embedding provider metadata."""
        ...

    @property
    def is_initialized(self) -> bool:
        """Check if backend is initialized and ready."""
        ...
```

**Key decisions:**
- **All async**: Even ChromaDB (sync) wraps operations in `asyncio.to_thread()` to avoid event loop blocking
- **Normalized scores**: Both backends return 0-1 range (ChromaDB distance → similarity, ts_rank normalized)
- **Metadata validation**: Store and validate embedding dimensions at backend level, not service level

### Pattern 2: ChromaDB Sync-to-Async Adapter

**What:** Wrap existing synchronous ChromaDB operations in `asyncio.to_thread()` to provide async interface without refactoring existing code.

**When to use:** When integrating synchronous libraries into async codebases (FastAPI).

**Example:**
```python
# storage/chroma/backend.py
import asyncio
from typing import Any
from agent_brain_server.storage.protocol import StorageBackendProtocol, SearchResult
from agent_brain_server.storage.chroma.vector_store import VectorStoreManager
from agent_brain_server.indexing.bm25_index import BM25IndexManager

class ChromaBackend:
    """ChromaDB backend implementing StorageBackendProtocol.

    Wraps existing VectorStoreManager and BM25IndexManager in async interface.
    """

    def __init__(
        self,
        vector_store: VectorStoreManager | None = None,
        bm25_manager: BM25IndexManager | None = None,
    ):
        from agent_brain_server.storage import get_vector_store
        from agent_brain_server.indexing.bm25_index import get_bm25_manager

        self.vector_store = vector_store or get_vector_store()
        self.bm25_manager = bm25_manager or get_bm25_manager()

    async def initialize(self) -> None:
        """Initialize ChromaDB collections (already async)."""
        await self.vector_store.initialize()
        # BM25 manager initializes lazily on first use

    async def upsert_documents(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> int:
        """Upsert via VectorStoreManager (already async)."""
        await self.vector_store.upsert_embeddings(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        # Update BM25 index (sync operation, wrap in thread)
        await asyncio.to_thread(
            self.bm25_manager.add_documents,
            ids=ids,
            texts=documents,
            metadatas=metadatas,
        )

        return len(ids)

    async def vector_search(
        self,
        query_embedding: list[float],
        top_k: int,
        similarity_threshold: float,
        where: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Vector search (already returns SearchResult from VectorStoreManager)."""
        # VectorStoreManager.similarity_search already async and returns SearchResult
        return await self.vector_store.similarity_search(
            query_embedding=query_embedding,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            where=where,
        )

    async def keyword_search(
        self,
        query: str,
        top_k: int,
        source_types: list[str] | None = None,
        languages: list[str] | None = None,
    ) -> list[SearchResult]:
        """BM25 search (sync, wrap in thread)."""
        # Build metadata filter
        metadata_filter = {}
        if source_types:
            metadata_filter["source_type"] = source_types
        if languages:
            metadata_filter["language"] = languages

        # BM25 search is synchronous
        results = await asyncio.to_thread(
            self.bm25_manager.search,
            query=query,
            top_k=top_k,
            metadata_filter=metadata_filter if metadata_filter else None,
        )

        # Normalize BM25 scores to 0-1 range
        # BM25 scores are typically 0-10, normalize by dividing by max
        max_score = max((r.score for r in results), default=1.0)
        normalized_results = [
            SearchResult(
                text=r.text,
                metadata=r.metadata,
                score=r.score / max_score if max_score > 0 else 0.0,
                chunk_id=r.chunk_id,
            )
            for r in results
        ]

        return normalized_results

    async def get_count(self, where: dict[str, Any] | None = None) -> int:
        """Get count from ChromaDB."""
        return await self.vector_store.count(where=where)

    async def reset(self) -> None:
        """Reset both vector store and BM25 index."""
        await self.vector_store.reset()
        await asyncio.to_thread(self.bm25_manager.reset)

    @property
    def is_initialized(self) -> bool:
        return self.vector_store.is_initialized
```

**Key insight:** `asyncio.to_thread()` runs blocking operations in a thread pool (default 32 threads or CPU count + 4), preventing event loop blocking. Use for all BM25IndexManager operations (currently sync).

### Pattern 3: Backend Factory with YAML Config

**What:** Factory function selects backend based on YAML configuration (reuses v3.0 provider config pattern).

**When to use:** Configuration-driven selection between multiple implementations.

**Example:**
```python
# config/provider_config.py (MODIFY)
class StorageConfig(BaseModel):
    """Configuration for storage backend."""

    backend: str = Field(
        default="chroma",
        description="Storage backend: 'chroma' or 'postgres'"
    )

    # PostgreSQL configuration (only used when backend=postgres)
    postgres: dict[str, Any] = Field(
        default_factory=dict,
        description="PostgreSQL connection parameters"
    )

class ProviderSettings(BaseModel):
    """Top-level provider configuration."""

    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    summarization: SummarizationConfig = Field(default_factory=SummarizationConfig)
    reranker: RerankerConfig = Field(default_factory=RerankerConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)  # NEW
```

```python
# storage/factory.py (NEW)
from functools import lru_cache
from agent_brain_server.config.provider_config import load_provider_settings
from agent_brain_server.storage.protocol import StorageBackendProtocol

@lru_cache
def get_storage_backend() -> StorageBackendProtocol:
    """Get storage backend based on configuration.

    Returns:
        Storage backend instance (ChromaBackend or PostgresBackend)
    """
    settings = load_provider_settings()
    backend_type = settings.storage.backend.lower()

    if backend_type == "chroma":
        from agent_brain_server.storage.chroma.backend import ChromaBackend
        return ChromaBackend()
    elif backend_type == "postgres":
        from agent_brain_server.storage.postgres.backend import PostgresBackend
        return PostgresBackend(settings.storage.postgres)
    else:
        raise ValueError(
            f"Unknown storage backend: {backend_type}. "
            f"Valid options: chroma, postgres"
        )

def reset_storage_backend_cache() -> None:
    """Clear cached backend instance (for testing)."""
    get_storage_backend.cache_clear()
```

**YAML config example:**
```yaml
# config.yaml
storage:
  backend: "chroma"  # or "postgres"

  # PostgreSQL config (only used when backend=postgres)
  postgres:
    host: "localhost"
    port: 5432
    database: "agent_brain"
    user: "agent_brain"
    password_env: "POSTGRES_PASSWORD"  # Env var name
    pool_size: 10
    max_overflow: 20
```

### Pattern 4: FastAPI Lifespan for Connection Pools (Phase 6)

**What:** Use FastAPI lifespan context manager to initialize PostgreSQL connection pool on startup and close on shutdown.

**When to use:** Any async resource (database connections, HTTP clients) that needs startup/shutdown lifecycle.

**Example:**
```python
# api/main.py (MODIFY in Phase 6)
from contextlib import asynccontextmanager
from fastapi import FastAPI
from agent_brain_server.config.provider_config import load_provider_settings
from agent_brain_server.storage import get_storage_backend

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: startup and shutdown."""

    # STARTUP
    settings = load_provider_settings()

    # Initialize storage backend (creates connection pool if PostgreSQL)
    backend = get_storage_backend()
    await backend.initialize()

    logger.info(f"Storage backend initialized: {settings.storage.backend}")

    yield  # Application runs

    # SHUTDOWN
    # PostgreSQL backend closes connection pool
    if hasattr(backend, 'close'):
        await backend.close()

    logger.info("Application shutdown complete")

app = FastAPI(lifespan=lifespan)
```

**Key insight:** Lifespan pattern replaced deprecated `@app.on_event("startup")` in FastAPI 0.95+. Use `@asynccontextmanager` for async resource initialization.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Sync-to-async wrapper** | Custom thread pool manager | `asyncio.to_thread()` | Handles context variable copying, uses asyncio's thread pool, one-liner |
| **Storage abstraction** | ABC with inheritance | `typing.Protocol` | Structural subtyping, no inheritance required, works with existing code |
| **Connection pooling** | Custom pool manager | SQLAlchemy async engine | Battle-tested, handles stale connections, pre-ping validation |
| **YAML config parsing** | Custom parser | Pydantic + PyYAML | Type validation, env var resolution, consistent with existing providers |
| **Score normalization** | Service-level normalization | Backend adapter normalization | Single responsibility, backend-specific logic stays in adapter |

**Key insight:** Don't create generic "storage ORM" that tries to map all backends to common query DSL. Agent Brain has simple operations (upsert, vector search, keyword search). Protocol defines these directly, adapters translate to backend-specific calls.

## Common Pitfalls

### Pitfall 1: Event Loop Blocking with Synchronous ChromaDB

**What goes wrong:** ChromaDB operations are synchronous. Calling them directly in async FastAPI handlers blocks the event loop, causing timeout cascades under concurrent load.

**Why it happens:** Developer ports ChromaDB code to storage protocol without wrapping sync calls in `asyncio.to_thread()`. Tests with single request pass, concurrent load tests hang.

**How to avoid:**
1. **Protocol mandates async**: All storage methods are `async def`, forcing adapters to handle sync/async properly
2. **Use asyncio.to_thread()**: Wrap ALL ChromaDB and BM25IndexManager operations
3. **Load test**: Verify 50+ concurrent requests complete without timeouts

**Warning signs:**
- Single-threaded pytest passes, concurrent tests timeout
- Uvicorn worker timeouts under load
- `RuntimeError: Task got bad yield`

**Verification:**
```python
# Test: Concurrent operations don't block
async def test_concurrent_operations():
    backend = get_storage_backend()
    tasks = [
        backend.vector_search(embedding, top_k=5, similarity_threshold=0.7)
        for _ in range(50)
    ]
    results = await asyncio.gather(*tasks)
    assert len(results) == 50
```

### Pitfall 2: Leaky Storage Abstraction

**What goes wrong:** Services import ChromaDB or asyncpg directly, check backend type with `isinstance()`, or handle backend-specific exceptions. Adding PostgreSQL requires modifying service code.

**Why it happens:** Protocol designed around ChromaDB's API, not from first principles. Backend details (distance vs similarity, exception types) leak through.

**How to avoid:**
1. **Services depend only on protocol**: Never import `chromadb` or `asyncpg` in services
2. **Normalize at boundary**: Convert distance to similarity, wrap exceptions in `StorageError`
3. **Contract tests**: Same test suite validates both backends behave identically

**Warning signs:**
- Services import `from chromadb import Collection`
- Conditional logic: `if isinstance(backend, ChromaBackend)`
- Different exception types from different backends

**Verification:**
```python
# Contract test: Both backends pass identical test suite
@pytest.mark.parametrize("backend_type", ["chroma", "postgres"])
async def test_vector_search_contract(backend_type, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", backend_type)
    reset_storage_backend_cache()
    backend = get_storage_backend()

    # Same operations, identical results
    await backend.upsert_documents(ids, embeddings, docs, metas)
    results = await backend.vector_search(query_emb, top_k=5, threshold=0.7)

    assert len(results) == 5
    assert all(0 <= r.score <= 1 for r in results)
```

### Pitfall 3: Score Range Inconsistency

**What goes wrong:** ChromaDB returns distance (0 = perfect match), PostgreSQL returns similarity (1 = perfect match). BM25 scores are 0-10, tsvector scores are 0-1. Hybrid search fusion weights backends inconsistently.

**Why it happens:** Adapter doesn't normalize scores. Service receives raw backend scores, reciprocal rank fusion breaks.

**How to avoid:**
1. **Protocol mandates 0-1 normalized scores**: Higher = better match
2. **Adapter normalizes**: ChromaDB `score = 1 - distance`, BM25 `score / max_score`
3. **Test score distribution**: Verify all backends return [0, 1] range

**Warning signs:**
- Hybrid search heavily favors one backend
- Vector scores > 1 or negative scores
- Different top-k results from same query on different backends

**Verification:**
```python
# Test: All backends return normalized scores
async def test_normalized_scores(backend):
    results = await backend.vector_search(query_emb, top_k=10, threshold=0.0)
    assert all(0 <= r.score <= 1 for r in results), "Scores not normalized to [0, 1]"
    assert results[0].score >= results[-1].score, "Scores not descending"
```

### Pitfall 4: Missing Embedding Metadata Validation

**What goes wrong:** User indexes with OpenAI (3072 dims), switches to Ollama (768 dims), queries fail with "dimension mismatch" error deep in backend.

**Why it happens:** Protocol doesn't mandate embedding metadata storage/validation. Backend only discovers mismatch during query execution.

**How to avoid:**
1. **Protocol includes metadata methods**: `get_embedding_metadata()`, `set_embedding_metadata()`
2. **Validate on startup**: Compare stored metadata to current provider config
3. **Fail fast**: Raise `ProviderMismatchError` before first query

**Warning signs:**
- Tests with fresh database pass, tests with existing data fail
- Error appears during query, not during startup
- PostgreSQL schema errors: "expected 3072 dimensions, not 768"

**Verification:**
```python
# Test: Dimension mismatch detected before indexing
async def test_dimension_mismatch_validation(backend):
    # Index with OpenAI (3072 dims)
    await backend.set_embedding_metadata("openai", "text-embedding-3-large", 3072)

    # Switch to Ollama (768 dims) - should fail validation
    with pytest.raises(ProviderMismatchError):
        backend.validate_embedding_compatibility(
            provider="ollama",
            model="nomic-embed-text",
            dimensions=768,
            stored_metadata=await backend.get_embedding_metadata()
        )
```

### Pitfall 5: Config Override Precedence Confusion

**What goes wrong:** User sets `storage.backend: postgres` in YAML but `AGENT_BRAIN_STORAGE_BACKEND=chroma` env var doesn't override. Or vice versa.

**Why it happens:** No clear precedence documented. Environment variables should override YAML (like provider config), but factory doesn't check env vars.

**How to avoid:**
1. **Document precedence**: Env vars > YAML > defaults
2. **Check env var first**: `os.getenv("AGENT_BRAIN_STORAGE_BACKEND") or settings.storage.backend`
3. **Log effective config**: "Using storage backend: postgres (from AGENT_BRAIN_STORAGE_BACKEND)"

**Warning signs:**
- User sets env var, wrong backend loads
- No log message showing which config source was used
- Tests pass with YAML, fail with env var override

**Verification:**
```python
# Test: Environment variable overrides YAML config
def test_env_var_override(tmp_path, monkeypatch):
    # Write YAML with chroma
    config_file = tmp_path / "config.yaml"
    config_file.write_text("storage:\n  backend: chroma\n")
    monkeypatch.setenv("AGENT_BRAIN_CONFIG", str(config_file))

    # Override with env var
    monkeypatch.setenv("AGENT_BRAIN_STORAGE_BACKEND", "postgres")

    reset_storage_backend_cache()
    backend = get_storage_backend()

    assert isinstance(backend, PostgresBackend), "Env var should override YAML"
```

## Code Examples

Verified patterns from existing codebase and research:

### Service Layer Integration

```python
# services/query_service.py (MODIFY)
from agent_brain_server.storage.protocol import StorageBackendProtocol
from agent_brain_server.storage import get_storage_backend

class QueryService:
    """Executes semantic, keyword, and hybrid search queries."""

    def __init__(
        self,
        storage_backend: StorageBackendProtocol | None = None,
        embedding_generator: EmbeddingGenerator | None = None,
    ):
        # Use factory to get backend
        self.storage_backend = storage_backend or get_storage_backend()
        self.embedding_generator = embedding_generator or get_embedding_generator()

    def is_ready(self) -> bool:
        return self.storage_backend.is_initialized

    async def execute_vector_search(
        self, query: str, top_k: int, threshold: float
    ) -> list[QueryResult]:
        # Generate embedding
        query_embedding = await self.embedding_generator.embed_query(query)

        # Use protocol method (backend-agnostic)
        results = await self.storage_backend.vector_search(
            query_embedding=query_embedding,
            top_k=top_k,
            similarity_threshold=threshold,
        )

        return [
            QueryResult(
                text=r.text,
                metadata=r.metadata,
                score=r.score,  # Already normalized 0-1
                chunk_id=r.chunk_id,
            )
            for r in results
        ]

    async def execute_keyword_search(
        self, query: str, top_k: int
    ) -> list[QueryResult]:
        # Use protocol method (ChromaDB uses BM25, PostgreSQL uses tsvector)
        results = await self.storage_backend.keyword_search(
            query=query,
            top_k=top_k,
        )

        return [QueryResult.from_search_result(r) for r in results]
```

**Key insight:** Service never imports ChromaDB or BM25IndexManager. Depends only on `StorageBackendProtocol` interface.

### Indexing Service Integration

```python
# services/indexing_service.py (MODIFY)
from agent_brain_server.storage.protocol import StorageBackendProtocol
from agent_brain_server.storage import get_storage_backend

class IndexingService:
    """Orchestrates document indexing with AST extraction and embedding."""

    def __init__(
        self,
        storage_backend: StorageBackendProtocol | None = None,
        embedding_generator: EmbeddingGenerator | None = None,
    ):
        self.storage_backend = storage_backend or get_storage_backend()
        self.embedding_generator = embedding_generator or get_embedding_generator()

    async def index_documents(
        self, file_paths: list[Path]
    ) -> dict[str, Any]:
        # ... existing chunking and embedding logic ...

        # Validate embedding compatibility
        stored_metadata = await self.storage_backend.get_embedding_metadata()
        if stored_metadata:
            # Check if dimensions match
            current_dims = self.embedding_generator.get_embedding_dimensions()
            if stored_metadata.dimensions != current_dims:
                raise ProviderMismatchError(
                    current_provider=self.embedding_generator.provider,
                    current_model=self.embedding_generator.model,
                    indexed_provider=stored_metadata.provider,
                    indexed_model=stored_metadata.model,
                )
        else:
            # First indexing - store metadata
            await self.storage_backend.set_embedding_metadata(
                provider=self.embedding_generator.provider,
                model=self.embedding_generator.model,
                dimensions=self.embedding_generator.get_embedding_dimensions(),
            )

        # Upsert to storage (backend handles both vector and keyword indexing)
        count = await self.storage_backend.upsert_documents(
            ids=chunk_ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        return {"indexed_count": count}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `@asynccontextmanager` lifespan | FastAPI 0.95+ (2023) | Cleaner resource management, colocates init/cleanup |
| Abstract Base Classes (ABC) | `typing.Protocol` (PEP 544) | Python 3.8+ (2019) | No inheritance required, structural subtyping |
| `asyncio.run_in_executor()` | `asyncio.to_thread()` | Python 3.9+ (2020) | Simpler API, handles context vars automatically |
| Global database engine | App state with lifespan | FastAPI best practice (2023) | Graceful shutdown, testable |

**Deprecated/outdated:**
- **ABC with @abstractmethod**: Still works, but Protocol is more Pythonic for duck typing
- **run_in_executor with custom pool**: asyncio.to_thread() uses default pool, sufficient for most cases

## Open Questions

1. **LlamaIndex PGVectorStore vs custom asyncpg adapter (Phase 6)**
   - What we know: LlamaIndex provides pgvector integration, but adds dependency and version coupling risk
   - What's unclear: Performance comparison, ease of customization
   - Recommendation: Phase 5 doesn't implement PostgreSQL backend, defer decision to Phase 6 planning

2. **BM25 score normalization strategy**
   - What we know: ChromaDB BM25 scores are ~0-10, need normalization
   - What's unclear: Divide by max_score (per-query) vs fixed scaling factor
   - Recommendation: Per-query max_score normalization (preserves relative ranking)

3. **Metadata filter translation**
   - What we know: ChromaDB uses `where={"source_type": "python"}`, PostgreSQL uses JSONB operators
   - What's unclear: How complex filters should be (AND, OR, nested?)
   - Recommendation: Phase 5 supports simple equality filters only, defer complex filters to Phase 7

## Sources

### Primary (HIGH confidence)
- [PEP 544 – Protocols: Structural subtyping (static duck typing)](https://peps.python.org/pep-0544/) - Official Python protocol specification
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) - Official FastAPI async resource management
- [asyncio.to_thread() documentation](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread) - Official Python asyncio docs
- Agent Brain codebase:
  - `config/provider_config.py` - Existing YAML provider config pattern (v3.0)
  - `storage/vector_store.py` - Existing VectorStoreManager with embedding metadata validation
  - `services/query_service.py` - Current service dependency on vector_store + bm25_manager

### Secondary (MEDIUM confidence)
- [Python Protocols: Unveiling the Magic of Duck Typing and Beyond](https://coderivers.org/blog/python-protocol/) - Protocol best practices
- [How to Use Asyncio to_thread()](https://superfastpython.com/asyncio-to_thread/) - asyncio.to_thread() patterns
- [FastAPI Lifespan Events: Managing Resources and Background Tasks](https://www.sarimahmed.net/blog/fastapi-lifespan/) - Lifespan pattern examples
- .planning/research/ARCHITECTURE.md - Milestone research (PostgreSQL backend architecture)
- .planning/research/PITFALLS.md - Milestone research (async/sync mismatch, leaky abstraction)

### Tertiary (LOW confidence - flagged for validation)
- [Protocols and structural subtyping - mypy documentation](https://mypy.readthedocs.io/en/stable/protocols.html) - Type checking with protocols

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Python stdlib patterns (Protocol, asyncio.to_thread), existing Pydantic config
- Architecture: HIGH - Based on existing v3.0 provider pattern, proven YAML-driven config
- Pitfalls: MEDIUM-HIGH - Async/sync mismatch verified in research, leaky abstraction from milestone research

**Research date:** 2026-02-10
**Valid until:** 2026-04-10 (60 days - stable Python/FastAPI patterns)

**Phase 5 scope:** Storage protocol definition + ChromaDB adapter only. PostgreSQL backend deferred to Phase 6.
