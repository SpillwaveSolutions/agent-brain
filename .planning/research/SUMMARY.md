# Project Research Summary

**Project:** Agent Brain - PostgreSQL Dual Storage Backend
**Domain:** RAG storage backend migration (ChromaDB → optional PostgreSQL with pgvector)
**Researched:** 2026-02-10
**Confidence:** HIGH

## Executive Summary

Agent Brain should add PostgreSQL + pgvector as an optional dual storage backend alongside existing ChromaDB, using asyncpg + SQLAlchemy 2.0 + LlamaIndex integration for vector operations and native tsvector for keyword search. This enables production-scale deployments with ACID guarantees while maintaining ChromaDB as the simple, local-first default. The recommended approach abstracts storage behind a Protocol interface, allowing services to operate backend-agnostically with ChromaDB and PostgreSQL implementations validated through identical contract tests.

The critical path follows: (1) design async-first storage protocol to avoid sync/async mixing pitfalls, (2) implement PostgreSQL backend with proper connection pooling and index configuration, (3) validate both backends against identical test suites. The main risk is leaky abstractions exposing backend-specific details to services, mitigated by designing the protocol interface before any implementation and enforcing strict boundaries through type hints and contract tests.

Key architectural decision: Use asyncpg (not psycopg3) for 5x performance advantage, LlamaIndex PGVectorStore for consistency with existing patterns, and PostgreSQL native tsvector (not recreating BM25) for keyword search. ChromaDB remains default for local development; PostgreSQL is opt-in via YAML config for users who need enterprise features like ACID transactions, unified storage for vectors + relational data, and operational maturity.

## Key Findings

### Recommended Stack

The PostgreSQL backend requires four new dependencies: asyncpg (async driver, 5x faster than psycopg3), SQLAlchemy 2.0 (ORM + async support), llama-index-vector-stores-postgres (LlamaIndex integration), and Alembic (async migrations). Docker infrastructure uses pgvector/pgvector:pg16 official image with pgvector extension pre-installed.

**Core technologies:**
- **asyncpg ^0.30.0**: Async PostgreSQL driver — 5x faster than psycopg3, purpose-built for asyncio, required for FastAPI async-first architecture
- **SQLAlchemy ^2.0.0**: ORM + migrations — Async engine, connection pooling, type safety, Alembic support
- **llama-index-vector-stores-postgres ^0.7.2**: LlamaIndex integration — Maintains consistency with existing ChromaDB VectorStore abstraction, handles pgvector operations
- **pgvector extension (0.8.1+)**: PostgreSQL vector similarity — Industry-standard extension, HNSW + IVFFlat indexes, cosine/L2/inner product distances
- **PostgreSQL tsvector/GIN**: Keyword search — Native full-text search replaces disk-based BM25 index, GIN indexes for performance

**Critical version decisions:**
- asyncpg over psycopg3: Benchmarks show 5x performance advantage, native asyncio design
- SQLAlchemy 2.0 async engine: Required for connection lifecycle management in FastAPI
- LlamaIndex integration over raw SQL: Consistency with existing architecture patterns

### Expected Features

Research identifies clear must-have features (users expect from PostgreSQL backend), differentiators (set PostgreSQL apart from ChromaDB), and anti-features (explicitly avoid).

**Must have (table stakes):**
- pgvector vector storage with cosine/L2/inner product distances — Core capability
- HNSW index for production performance — Expected for production RAG systems
- tsvector full-text search with GIN indexes — PostgreSQL's native FTS
- Storage backend abstraction — Users select ChromaDB vs PostgreSQL via config
- Hybrid RRF fusion adapted for PostgreSQL — Existing feature must continue working
- Docker Compose setup — Standard dev environment expectation

**Should have (competitive):**
- Hybrid search in single SQL query — PostgreSQL can combine vector + FTS in one call (ChromaDB requires separate queries)
- ACID transactional consistency — Built-in PostgreSQL feature, ChromaDB lacks
- SQL-based metadata filtering — More flexible than ChromaDB's metadata dict filtering
- Backup/restore ecosystem — pg_dump, replication tools (operational advantage)

**Defer (v2+):**
- BM25 via pg_textsearch extension — Requires extension management, use tsvector ts_rank for MVP
- DiskANN/pgvectorscale optimization — Advanced, not needed for validation
- Multi-tenancy with schemas — Complex security model, single-tenant simpler
- Graph + vector co-location — Existing GraphStoreManager separate, no urgency

**Anti-features (explicitly avoid):**
- Replace ChromaDB entirely — ChromaDB remains default, PostgreSQL is optional
- Auto-migration ChromaDB → PostgreSQL — Complex, error-prone, users can rebuild
- PostgreSQL-only deployment — Breaks local-first promise
- Custom BM25 in Python — Use tsvector, document pg_textsearch extension path
- Real-time per-document updates — HNSW build slow, design for batch reindexing

### Architecture Approach

The architecture abstracts storage behind a Protocol interface with separate implementations for ChromaDB and PostgreSQL. Services depend only on the protocol, not concrete backends. PostgreSQL backend combines PGVectorOps (wraps LlamaIndex PGVectorStore) and TSVectorOps (native tsvector queries) with connection pool lifecycle managed via FastAPI lifespan pattern.

**Major components:**
1. **StorageBackendProtocol** — Python Protocol defining async storage operations (vector + keyword search, upsert, count, reset). Services depend only on this interface.
2. **ChromaBackend** — Adapts existing VectorStoreManager + BM25IndexManager to implement protocol. Wraps sync ChromaDB in async interface using asyncio.to_thread().
3. **PGBackend** — PostgreSQL implementation combining PGVectorOps (pgvector via LlamaIndex) and TSVectorOps (native tsvector). Manages asyncpg connection pool lifecycle.
4. **BackendFactory** — Config-driven backend selection (reads storage.backend from YAML, instantiates correct implementation).
5. **Connection Pool Manager** — SQLAlchemy async engine with lifespan context manager. Created on FastAPI startup, disposed on shutdown.

**Key patterns:**
- **Protocol over ABC**: Structural subtyping (no inheritance) for cleaner ChromaDB adapter
- **Lifespan management**: FastAPI lifespan context for connection pool initialization/disposal
- **Score normalization at boundary**: Backend-specific score ranges normalized before RRF fusion
- **Async-first interface**: Protocol forces async, ChromaDB wraps sync calls in asyncio.to_thread()

**Data flow:**
- Indexing: Document → Chunker → EmbeddingGenerator → Backend.upsert_documents() → PostgreSQL transaction (vector + tsvector trigger)
- Hybrid query: Vector search (PGVectorOps) + Keyword search (TSVectorOps) → RRF fusion (existing logic) → Combined results

### Critical Pitfalls

Research identified 10 critical pitfalls. Top 5 most severe:

1. **Async/Sync Architecture Mismatch** — ChromaDB is sync, PostgreSQL is async. Mixing causes event loop blocking, "connection pool exhausted" errors under load. Prevention: Design protocol as fully async from start, wrap ChromaDB in asyncio.to_thread().

2. **Embedding Dimension Mismatch After Provider Switch** — PostgreSQL enforces dimensions at schema level via vector(N). Switching from OpenAI (3072D) to Ollama (768D) causes runtime errors. Prevention: Store embedding metadata in database, validate on startup against config.

3. **tsvector Language Configuration Mismatch** — GIN index on `to_tsvector('english', content)` won't match query with `to_tsvector(content)` (default config). Causes full table scans. Prevention: Explicit language in queries matching index definition, verify with EXPLAIN ANALYZE in tests.

4. **Connection Pool Exhaustion in FastAPI** — PostgreSQL max_connections limit (default 100), asyncpg pool defaults to 10. Concurrent load + long-running indexing exhausts pool. Prevention: Configure pool based on workload (min=10, max=20), use separate pools for reads/writes.

5. **HNSW Index Creation Blocks Production** — Building HNSW on 100k+ docs takes hours, consumes 64GB+ memory, degrades query performance. Prevention: Build indexes before bulk load, use IVFFlat for initial migration, tune maintenance_work_mem.

**Additional critical concerns:**
- Leaky abstraction exposing backend details to services
- LlamaIndex PGVectorStore version incompatibility with existing llama-index-core
- Docker Compose requires pgvector/pgvector image (official postgres lacks extension)
- Test infrastructure requires PostgreSQL (breaks existing CI without pytest markers)
- BM25 score range incompatibility (ChromaDB 0-10 vs PostgreSQL ts_rank 0-1)

## Implications for Roadmap

Based on research, the recommended phase structure prioritizes abstraction over implementation to avoid leaky boundaries, then implements PostgreSQL with proper async patterns, finally validates with comprehensive testing.

### Phase 1: Storage Backend Abstraction Layer

**Rationale:** Must design async-first protocol before any backend implementation to avoid Pitfall #1 (async/sync mismatch) and Pitfall #7 (leaky abstraction). This foundation determines success of entire integration.

**Delivers:**
- `StorageBackendProtocol` interface defining async operations
- `BackendFactory` for config-driven selection
- ChromaBackend adapter wrapping existing code
- Contract test suite validating protocol compliance

**Addresses:**
- Storage backend selection via YAML (must-have feature)
- Backend abstraction (table stakes)
- Prevention of leaky abstraction pitfall

**Avoids:**
- Async/sync mismatch (design async-first from start)
- Leaky abstraction (services depend only on protocol)

**Must-haves:**
- Protocol defines vector_search, keyword_search, upsert_documents, get_count, reset
- ChromaDB operations wrapped in asyncio.to_thread() for async interface
- Type hints use Protocol, not concrete classes
- Contract tests validate identical behavior expectations

### Phase 2: PostgreSQL Backend Implementation

**Rationale:** Implement PostgreSQL after abstraction validated. Includes connection pooling, pgvector integration via LlamaIndex, and tsvector keyword search. This phase addresses most technical complexity.

**Delivers:**
- PGBackend implementing StorageBackendProtocol
- PGVectorOps using llama-index-vector-stores-postgres
- TSVectorOps with native tsvector + GIN indexes
- Connection pool lifecycle via FastAPI lifespan
- SQLAlchemy schema with pgvector + tsvector columns
- Alembic migrations for schema versioning

**Uses:**
- asyncpg ^0.30.0 for async driver
- SQLAlchemy 2.0 async engine
- llama-index-vector-stores-postgres ^0.7.2
- pgvector extension via Docker

**Addresses:**
- pgvector vector storage (must-have)
- HNSW/IVFFlat indexes (must-have)
- tsvector full-text search with GIN (must-have)
- ACID consistency (differentiator)

**Avoids:**
- Connection pool exhaustion (pool_size tuning, lifespan management)
- Dimension mismatch (metadata validation on startup)
- tsvector language config errors (explicit 'english' in queries and indexes)
- Docker pgvector extension missing (use pgvector/pgvector:pg16 image)

**Must-haves:**
- Connection pool created in FastAPI lifespan, disposed on shutdown
- Schema validation compares embedding dimensions to config on startup
- GIN index uses same language config as queries (verified via EXPLAIN ANALYZE)
- Separate PGVectorOps and TSVectorOps classes for separation of concerns
- pyproject.toml uses Poetry extras for optional PostgreSQL dependencies

### Phase 3: Testing & CI Integration

**Rationale:** Both backends must pass identical contract tests. CI must support PostgreSQL tests without breaking existing workflows (ChromaDB tests don't require PostgreSQL).

**Delivers:**
- Contract tests run against both ChromaDB and PGBackend
- pytest markers for PostgreSQL tests (@pytest.mark.postgres)
- GitHub Actions service container for PostgreSQL + pgvector
- Load tests validating concurrent performance
- EXPLAIN ANALYZE tests verifying index usage
- Score normalization tests for hybrid search parity

**Addresses:**
- Test infrastructure with PostgreSQL dependency (Pitfall #6)
- BM25 score incompatibility (Pitfall #10)
- Validation that abstraction doesn't leak

**Avoids:**
- Breaking existing CI (tests skip gracefully without PostgreSQL)
- Performance regressions (load tests catch connection pool issues)
- Index misconfiguration (EXPLAIN ANALYZE validates GIN/HNSW usage)

**Must-haves:**
- Contract test suite parameterized over [ChromaBackend, PGBackend]
- task before-push passes without PostgreSQL (skips @pytest.mark.postgres tests)
- task test-postgres runs full suite with PostgreSQL service
- Load test: 50 concurrent queries + background indexing succeeds
- Hybrid search test validates similar top-5 results across backends

### Phase 4: Configuration & Documentation

**Rationale:** Users need clear guidance on backend selection, setup, and tradeoffs. Configuration must extend existing provider_config.py pattern.

**Delivers:**
- YAML config schema with storage.backend section
- Environment variable overrides (AGENT_BRAIN_STORAGE_BACKEND)
- Docker Compose example with pgvector service
- Migration guide (ChromaDB → PostgreSQL data export/rebuild)
- Performance comparison docs (ChromaDB vs PostgreSQL tradeoffs)
- Troubleshooting guide for common pitfalls

**Addresses:**
- Docker Compose setup (must-have)
- Backend configuration clarity (UX pitfall)
- Migration path between backends (UX pitfall)

**Must-haves:**
- config.yaml with storage.backend: "chroma"|"postgres"
- PostgreSQL connection config (host, port, database, user, password_env)
- README explains: "ChromaDB for local dev, PostgreSQL for production scale"
- Migration docs clarify no auto-migration (manual rebuild expected)

### Phase Ordering Rationale

- **Phase 1 first (Abstraction)**: Protocol must be designed before implementation to prevent leaky abstraction. Research shows ChromaDB-specific details leak when abstraction designed around existing code rather than from first principles. Contract tests written during Phase 1 validate both backends in Phase 2+.

- **Phase 2 depends on Phase 1**: PostgreSQL implementation must conform to protocol designed in Phase 1. Connection pooling, async patterns, and score normalization all implement protocol interface. Cannot start Phase 2 until protocol validated with ChromaBackend adapter.

- **Phase 3 validates Phases 1+2**: Contract tests parameterized over both backends catch abstraction leaks, score normalization errors, and async/sync issues. Load tests validate connection pooling. CI configuration ensures tests don't break existing workflows.

- **Phase 4 after implementation proven**: Documentation written after implementation validated. Performance comparisons based on actual load test results. Troubleshooting guide references real pitfalls encountered.

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 2 (PostgreSQL Implementation)**: LlamaIndex PGVectorStore integration — version compatibility issues reported in GitHub issues (#9710, #15884). May need custom adapter without LlamaIndex dependency if version conflicts arise.
- **Phase 3 (Testing)**: pytest-postgresql setup — Research shows multiple approaches (docker-compose vs pytest plugin vs GitHub Actions service). Need to select based on Agent Brain's existing test patterns.

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Abstraction)**: Python Protocol pattern — well-documented in PEP 544, existing examples in repository pattern literature
- **Phase 4 (Documentation)**: Standard docs structure — Agent Brain already has USER_GUIDE.md, DEVELOPERS_GUIDE.md templates

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | asyncpg, SQLAlchemy 2.0, pgvector all current stable versions verified in official docs. Benchmarks confirm asyncpg performance advantage. |
| Features | HIGH | pgvector capabilities verified in official GitHub, PostgreSQL docs. HNSW vs IVFFlat performance from AWS Deep Dive. ChromaDB comparison from multiple 2025-2026 benchmarks. |
| Architecture | HIGH | LlamaIndex PostgreSQL integration official (v0.7.2), FastAPI lifespan pattern documented, SQLAlchemy async patterns in official docs. Protocol pattern from PEP 544. |
| Pitfalls | MEDIUM-HIGH | Async/sync pitfalls from community blogs (verified patterns). Connection pool exhaustion documented in FastAPI guides. HNSW index issues from pgvector GitHub issues. tsvector config from PostgreSQL docs. |

**Overall confidence:** HIGH

Research based on official documentation (PostgreSQL, pgvector, SQLAlchemy, LlamaIndex), current versions verified Feb 2026, established Python patterns, and recent community sources (2025-2026) from production deployments.

### Gaps to Address

Minor gaps that need validation during implementation:

- **LlamaIndex version compatibility**: llama-index-vector-stores-postgres may conflict with existing llama-index-core ^0.14.0. GitHub issues (#9710, #15884) report schema creation permission errors and Pydantic validation failures. Resolution: Test in isolation during Phase 2, consider custom asyncpg adapter if conflicts arise.

- **BM25 score normalization formula**: Research shows ChromaDB BM25 scores range 0-10, PostgreSQL ts_rank ranges 0-1, but exact normalization formula for RRF fusion needs experimentation. Resolution: Implement score distribution logging, tune normalization during Phase 3 testing.

- **HNSW parameter tuning for Agent Brain workload**: Research provides default parameters (m=16, ef_construction=64) but optimal values depend on corpus size and recall requirements. Resolution: Start with defaults, document tuning process in Phase 4 based on Phase 3 performance tests.

- **pytest-postgresql vs Docker Compose vs GitHub Actions services**: Multiple valid approaches for test infrastructure. Agent Brain's existing patterns (e2e/integration tests, scripts/quick_start_guide.sh) suggest Docker Compose, but needs confirmation. Resolution: Evaluate during Phase 3 planning against existing test structure.

## Sources

### Primary (HIGH confidence)
- [pgvector/pgvector GitHub](https://github.com/pgvector/pgvector) — pgvector capabilities, HNSW/IVFFlat indexes, distance metrics
- [PostgreSQL Full-Text Search Documentation](https://www.postgresql.org/docs/current/textsearch-controls.html) — tsvector, GIN indexes, language configuration
- [SQLAlchemy 2.0 Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) — Async engine, connection pooling patterns
- [LlamaIndex PostgreSQL Vector Store](https://developers.llamaindex.ai/python/examples/vector_stores/postgres/) — Official integration examples
- [llama-index-vector-stores-postgres PyPI](https://pypi.org/project/llama-index-vector-stores-postgres/) — Version 0.7.2, dependencies
- [asyncpg vs psycopg3 Performance](https://fernandoarteaga.dev/blog/psycopg-vs-asyncpg/) — Benchmark showing 5x advantage
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) — Connection lifecycle management

### Secondary (MEDIUM confidence)
- [AWS HNSW Indexing Performance](https://aws.amazon.com/blogs/database/optimize-generative-ai-applications-with-pgvector-indexing-a-deep-dive-into-ivfflat-and-hnsw-techniques/) — HNSW vs IVFFlat performance comparison (32x build time difference)
- [ParadeDB Hybrid Search Guide](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual) — RRF implementation, score normalization patterns
- [Tiger Data pg_textsearch Introduction](https://www.tigerdata.com/blog/introducing-pg_textsearch-true-bm25-ranking-hybrid-retrieval-postgres) — tsvector vs BM25 ranking differences
- [ChromaDB vs pgvector Comparison (Medium)](https://medium.com/@mysterious_obscure/pgvector-vs-chroma-db-which-works-better-for-rag-based-applications-3df813ad7307) — Performance under concurrent load (ChromaDB 23.08s vs PostgreSQL 9.81s)
- [Building High-Performance Async APIs (Leapcell)](https://leapcell.io/blog/building-high-performance-async-apis-with-fastapi-sqlalchemy-2-0-and-asyncpg) — FastAPI + SQLAlchemy + asyncpg patterns

### Tertiary (LOW confidence — needs validation)
- [pgvector HNSW Index Creation Issue #822](https://github.com/pgvector/pgvector/issues/822) — HNSW build stuck at 29.2%, memory requirements (user report, specific workload)
- [LlamaIndex PGVectorStore Schema Creation Bug #9710](https://github.com/run-llama/llama_index/issues/9710) — Permission errors with restricted database users (open issue, may be resolved)
- [VectorChord BM25 Performance Claims](https://blog.vectorchord.ai/postgresql-full-text-search-fast-when-done-right-debunking-the-slow-myth) — "3x faster than Elasticsearch" (vendor claim, not independently verified)

---
*Research completed: 2026-02-10*
*Ready for roadmap: yes*
