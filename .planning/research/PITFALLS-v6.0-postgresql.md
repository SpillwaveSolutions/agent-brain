# Pitfalls Research: PostgreSQL Backend Integration

**Domain:** Adding PostgreSQL/pgvector/tsvector as dual storage backend to existing ChromaDB-based RAG system
**Researched:** 2026-02-10
**Confidence:** MEDIUM-HIGH

## Critical Pitfalls

### Pitfall 1: Async/Sync Architecture Mismatch

**What goes wrong:**
ChromaDB is synchronous. PostgreSQL with asyncpg is async. Mixing sync and async code creates blocking operations in the event loop, causing performance degradation and "another operation is in progress" errors when handling concurrent requests.

**Why it happens:**
Developers port sync ChromaDB patterns to PostgreSQL without restructuring for async. The existing `VectorStoreManager` uses `async with self._lock` but calls ChromaDB's sync methods inside, which works because ChromaDB is sync. With PostgreSQL, await-ing inside locks while mixing sync/async operations breaks concurrency.

**How to avoid:**
1. **Create separate async abstraction layer** - Don't try to make existing sync code async-compatible
2. **Use `asyncio.to_thread()` for ChromaDB** - Run ChromaDB operations in thread pool to maintain async interface
3. **Design storage interface as fully async** - Force ChromaDB implementation to wrap in async
4. **Never call sync database methods inside async functions** - Use asyncpg throughout, not psycopg2

**Warning signs:**
- Tests pass but production has "connection pool exhausted" errors
- Single-threaded test passes, concurrent tests hang
- `RuntimeError: Task got bad yield` in logs
- Uvicorn worker timeouts under load

**Phase to address:**
Phase 1 (Storage Abstraction) - Must design async-first interface before implementing any backends.

**Prevention verification:**
- Load test with 50 concurrent requests succeeds
- Both backends pass identical async test suite
- No blocking I/O detected in async profiling

---

### Pitfall 2: Embedding Dimension Mismatch After Provider Switch

**What goes wrong:**
Existing ChromaDB index has embeddings from OpenAI text-embedding-3-large (3072 dimensions). User switches to PostgreSQL backend and changes embedding provider to Ollama (different dimensions). System attempts to query PostgreSQL with incompatible dimension vectors, causing `expected 3072 dimensions, not 1024` errors.

**Why it happens:**
Agent Brain already has dimension validation (PROV-07), but it validates against **config** not against **existing stored data**. PostgreSQL enforces dimension constraints at schema level via `vector(N)` column type. ChromaDB allows heterogeneous dimensions with partial indexing.

**How to avoid:**
1. **Store embedding metadata in collection/table metadata** (already exists in ChromaDB implementation)
2. **Validate on first query/index operation** - Check stored metadata before any operations
3. **Provide clear migration path** - Tool to re-index with new dimensions
4. **Schema validation on startup** - Compare provider config to database schema
5. **Add `--force-reindex` flag** - For intentional dimension changes

**Warning signs:**
- `ProviderMismatchError` only appears after switching backends (not caught in config validation)
- PostgreSQL schema has `vector(3072)` but provider config shows 1024 dimensions
- Tests with fresh database pass, tests with existing data fail

**Phase to address:**
Phase 1 (Storage Abstraction) - Dimension validation must be part of backend interface.
Phase 2 (PostgreSQL Implementation) - Schema validation on connection.

**Prevention verification:**
- Test: Create index with OpenAI → switch to Ollama → verify error before bad query
- Test: `agent-brain-server` startup fails fast if schema/config mismatch detected
- CI contract test validates dimension compatibility check exists

---

### Pitfall 3: tsvector Language Configuration Mismatch

**What goes wrong:**
Developer creates GIN index with `to_tsvector('english', content)` but queries use `to_tsvector(content)` (default config). PostgreSQL doesn't use the index, causing full table scans and query timeouts as data grows.

**Why it happens:**
PostgreSQL requires exact expression matching for index usage. A GIN index on `to_tsvector('english', content)` only matches queries with the same 2-argument form and same language. Generic `to_tsvector(content)` defaults to `pg_catalog.default_text_search_config` which might not be 'english'.

**How to avoid:**
1. **Explicit language in queries** - Always use 2-argument form: `to_tsvector('english', content)`
2. **Match index definition** - Query expression must exactly match index expression
3. **Store language config in metadata** - Like embedding provider, store tsvector config
4. **Use expression index with language column** - If multi-language, index on (language, to_tsvector(language, content))
5. **EXPLAIN ANALYZE in integration tests** - Verify index usage, not just correctness

**Warning signs:**
- BM25 queries fast on ChromaDB, slow on PostgreSQL despite GIN index existing
- `EXPLAIN ANALYZE` shows "Seq Scan" instead of "Bitmap Index Scan"
- Query time increases linearly with document count instead of logarithmically
- PostgreSQL CPU usage spikes during full-text queries

**Phase to address:**
Phase 2 (PostgreSQL Implementation) - tsvector index creation and query builder.
Phase 3 (Testing) - Performance tests validate index usage.

**Prevention verification:**
- All BM25 queries run `EXPLAIN ANALYZE` in tests, assert index usage
- Integration test with 10k documents verifies query time < 100ms
- CI fails if tsvector query doesn't use index

---

### Pitfall 4: Connection Pool Exhaustion in FastAPI

**What goes wrong:**
PostgreSQL enforces `max_connections` limit (default 100). Under concurrent load, FastAPI spawns many requests. Each request holds a connection during long-running indexing operations. Pool exhaustion blocks new requests, causing timeout cascade.

**Why it happens:**
ChromaDB is embedded - no connection limits. Developers port without considering connection pooling. asyncpg pool defaults to 10 connections, but FastAPI's concurrency can spawn 50+ requests simultaneously during bulk indexing.

**How to avoid:**
1. **Configure pool size based on workload** - min_size=10, max_size=20 for typical workloads
2. **Set max_inactive_connection_lifetime** - Default 300s can cause stale connections
3. **Use pgbouncer or pgpool in production** - Don't rely on application pooling alone
4. **Acquire connections narrowly** - `async with pool.acquire() as conn:` only during query, not entire request
5. **Implement connection pool monitoring** - Expose metrics for pool size/usage
6. **Separate pools for reads vs writes** - Prevent long indexing from blocking queries

**Warning signs:**
- `asyncpg.exceptions.TooManyConnectionsError` in production logs
- 99th percentile latency spikes during indexing
- Connection pool acquire timeout errors
- PostgreSQL `max_connections` exhausted warnings

**Phase to address:**
Phase 2 (PostgreSQL Implementation) - Connection pool configuration and lifecycle management.
Phase 3 (Testing) - Load testing with concurrent operations.

**Prevention verification:**
- Load test: 100 concurrent queries + background indexing succeeds
- Metrics show pool never exceeds configured max_size
- Graceful degradation when pool exhausted (queue, not crash)
- Health endpoint includes pool status

---

### Pitfall 5: Docker Compose pgvector Extension Not Available

**What goes wrong:**
Developer uses standard `postgres:16` image in Docker Compose. Application starts, attempts `CREATE EXTENSION vector`, gets `ERROR: extension "vector" is not available`. Application crashes on startup.

**Why it happens:**
pgvector is not included in official PostgreSQL images. Requires either pre-built images like `ankane/pgvector` or custom Dockerfile to compile pgvector from source. Alpine-based images require different build dependencies than Debian.

**How to avoid:**
1. **Use pre-built pgvector images** - `pgvector/pgvector:pg17` or `ankane/pgvector`
2. **For Alpine, use ksisoft/pgvector:16.3-alpine** - Pre-built Alpine variant
3. **Document extension requirement** - README must specify pgvector dependency
4. **Health check validates extension** - `SELECT * FROM pg_extension WHERE extname = 'vector'`
5. **Init script creates extension** - Docker entrypoint runs `CREATE EXTENSION IF NOT EXISTS vector`

**Warning signs:**
- Local Docker setup fails with "extension vector is not available"
- CI database setup scripts fail silently
- `docker-compose up` succeeds but server health check fails

**Phase to address:**
Phase 2 (PostgreSQL Implementation) - Docker Compose configuration for local dev.
Phase 4 (Documentation) - Setup instructions.

**Prevention verification:**
- `docker-compose up` succeeds on fresh clone
- `scripts/quick_start_guide.sh` validates pgvector availability
- CI uses same Docker Compose configuration as local dev

---

### Pitfall 6: Test Infrastructure Requires PostgreSQL Running

**What goes wrong:**
Existing Agent Brain CI runs 505 tests without external dependencies (ChromaDB is embedded). Adding PostgreSQL tests creates dependency on PostgreSQL server. CI fails on GitHub Actions unless PostgreSQL service container configured. Local `task before-push` fails if PostgreSQL not running.

**Why it happens:**
Developers write PostgreSQL tests without conditional skip logic. pytest collects all tests, PostgreSQL tests fail if server unavailable. Existing ChromaDB tests don't have this problem.

**How to avoid:**
1. **Use pytest markers** - `@pytest.mark.postgres` to tag PostgreSQL tests
2. **Conditional skip with fixture** - Check PostgreSQL availability, skip if unavailable
3. **pytest-postgresql plugin** - Manages PostgreSQL lifecycle for tests
4. **Separate test suites** - Unit tests (no DB) vs integration tests (require DB)
5. **GitHub Actions service container** - PostgreSQL service for CI
6. **Local docker-compose for tests** - Make local testing as easy as CI

**Warning signs:**
- CI passes on feature branch, fails on main because different runner lacks PostgreSQL
- `task before-push` requires manual PostgreSQL setup
- Test count decreases when PostgreSQL unavailable (tests skipped silently)
- Integration tests pass locally, fail in CI

**Phase to address:**
Phase 3 (Testing) - Test infrastructure and CI configuration.

**Prevention verification:**
- Tests marked with `@pytest.mark.postgres` (like existing `@pytest.mark.openai`)
- `task before-push` passes without PostgreSQL (skips marked tests)
- `task test-postgres` runs full suite with PostgreSQL
- CI runs both test targets
- README documents how to run PostgreSQL tests locally

---

### Pitfall 7: Leaky Storage Abstraction Exposes Backend Details

**What goes wrong:**
Storage abstraction claims to hide backend differences, but ChromaDB-specific exceptions, query patterns, or metadata formats leak through. Code in `QueryService` or `IndexingService` checks `if isinstance(store, ChromaVectorStore)` to handle quirks. Adding PostgreSQL requires more conditionals, creating brittle coupling.

**Why it happens:**
Abstraction designed around ChromaDB's API, not from first principles. Backend-specific details (like ChromaDB's "distance" vs PostgreSQL's "similarity") leak into business logic. Score normalization, metadata serialization, and error types differ between backends.

**How to avoid:**
1. **Design protocol/ABC first** - Define storage interface independent of any backend
2. **Normalize at boundary** - Convert backend-specific formats (distance→similarity) in adapter
3. **Backend-agnostic exceptions** - `StorageError` wraps `chromadb.errors` and `asyncpg.exceptions`
4. **Adapter pattern** - `ChromaDBAdapter` and `PostgresAdapter` implement same interface
5. **Contract tests** - Same test suite runs against both backends, validates identical behavior

**Warning signs:**
- Services import backend-specific modules (`from chromadb import Collection`)
- Conditional logic based on backend type in non-storage code
- Different exception types bubble up from different backends
- Metadata format changes based on backend

**Phase to address:**
Phase 1 (Storage Abstraction) - Design backend-agnostic interface before any implementation.

**Prevention verification:**
- Services never import ChromaDB or asyncpg directly (only storage module)
- Contract tests validate identical behavior across backends
- Mock tests use only abstract interface, not concrete implementation
- Type hints use Protocol/ABC, not concrete classes

---

### Pitfall 8: LlamaIndex PGVectorStore Version Incompatibility

**What goes wrong:**
Agent Brain uses `llama-index-core ^0.14.0`. Install `llama-index-vector-stores-postgres`, get Pydantic validation error: `PGVectorStore is not fully defined`. Existing ChromaDB code breaks mysteriously.

**Why it happens:**
LlamaIndex ecosystem has breaking changes between versions. `llama-index-vector-stores-postgres` released Nov 2025 may require different llama-index-core version. PGVectorStore has restrictive schema creation permissions that fail in CI environments with limited database users.

**How to avoid:**
1. **Pin exact versions** - `llama-index-vector-stores-postgres==X.Y.Z` in pyproject.toml
2. **Test with minimal permissions** - CI database user shouldn't have schema creation rights
3. **Separate optional dependency group** - `[tool.poetry.extras] postgres = [...]`
4. **Version compatibility matrix** - Document tested version combinations
5. **Consider not using LlamaIndex for PostgreSQL** - Use asyncpg directly, implement adapter

**Warning signs:**
- Pydantic errors on PGVectorStore initialization
- `llama-index-vector-stores-postgres` install changes llama-index-core version
- Tests pass locally, fail in CI due to database permissions
- Import errors after adding PostgreSQL dependencies

**Phase to address:**
Phase 2 (PostgreSQL Implementation) - Dependency resolution and adapter implementation.

**Prevention verification:**
- `poetry lock --check` verifies no version conflicts
- CI test with restricted database user (no CREATE SCHEMA permission)
- Integration test validates PGVectorStore initialization
- Consider implementing custom PostgreSQL adapter without LlamaIndex dependency

---

### Pitfall 9: HNSW Index Creation Blocks Production

**What goes wrong:**
Developer adds 100k documents to PostgreSQL during migration. Creating HNSW index with `CREATE INDEX CONCURRENTLY` takes 8+ hours, consumes 64GB of `maintenance_work_mem`, and degrades query performance during build. Production queries timeout.

**Why it happens:**
HNSW indexes are memory-intensive and slow to build on existing data. PostgreSQL allocates memory based on `maintenance_work_mem`, and if the graph doesn't fit, build time explodes. Adding data after HNSW index creation is 1000x slower (milliseconds → seconds per insert).

**How to avoid:**
1. **Create indexes before bulk loading** - Empty table → create index → load data is faster
2. **Increase maintenance_work_mem for build** - SET maintenance_work_mem='16GB' for session
3. **Build index offline during migration** - Not on production database
4. **Use IVFFlat for initial phase** - Faster build, acceptable recall, migrate to HNSW later
5. **Tune HNSW parameters** - Lower `m` and `ef_construction` for faster builds, lower recall
6. **Monitor index build progress** - Don't build blindly, track percentage completion

**Warning signs:**
- Index creation stuck at 29.2% for 8+ hours
- PostgreSQL memory usage spikes to 40GB+
- `CREATE INDEX CONCURRENTLY` still blocking queries
- Insert operations become 1000x slower after index creation

**Phase to address:**
Phase 2 (PostgreSQL Implementation) - Index strategy and build process.
Phase 5 (Migration) - Re-indexing from ChromaDB to PostgreSQL.

**Prevention verification:**
- Document index build time expectations (e.g., "10k docs: 5min, 100k docs: 2 hours")
- Migration script builds indexes before bulk load
- Index tuning params documented with recall/performance tradeoffs
- Monitoring dashboard shows index build progress

---

### Pitfall 10: BM25 Score Incompatibility Between ChromaDB and PostgreSQL

**What goes wrong:**
Hybrid search combines BM25 (keyword) and vector (semantic) scores. ChromaDB BM25 scores range 0-10. PostgreSQL ts_rank scores range 0-1. Reciprocal Rank Fusion (RRF) expects normalized scores. Inconsistent score ranges break hybrid ranking.

**Why it happens:**
Different BM25 implementations produce different score ranges. Agent Brain's RRF implementation (Feature 113) fuses results from multiple retrievers. Score mismatch causes vector search to dominate or BM25 to dominate unpredictably based on backend.

**How to avoid:**
1. **Normalize scores at retriever boundary** - Map both to 0-1 before RRF
2. **Backend-specific score normalization** - ChromaDB divides by max_score, PostgreSQL uses ts_rank_cd
3. **Test hybrid search with identical corpus** - Verify similar results from both backends
4. **Document score ranges** - Each backend documents expected score distribution
5. **Consider re-implementing BM25** - Use same rank-bm25 library for both backends

**Warning signs:**
- Hybrid search results differ wildly between ChromaDB and PostgreSQL
- RRF heavily favors one retriever over another
- Score distribution visualization shows different ranges
- Top-k results completely different for same query on different backends

**Phase to address:**
Phase 2 (PostgreSQL Implementation) - BM25 implementation and score normalization.
Phase 3 (Testing) - Hybrid search parity tests.

**Prevention verification:**
- Contract test: Same query on both backends produces similar top-5 results
- Score distribution test: Both backends produce scores in documented range
- Hybrid search test: RRF weights both retrievers fairly on both backends

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Use synchronous PostgreSQL driver (psycopg2) | Simpler code, matches ChromaDB pattern | Blocks event loop, kills concurrency under load | Never - FastAPI is async |
| Skip connection pooling, create connection per request | Fewer configuration options | Connection exhaustion, slow startup per request | Never in production |
| Hardcode 'english' for tsvector | Works for English docs | Fails for multi-language corpus | Acceptable for Phase 1, must parameterize Phase 2 |
| Don't test with PostgreSQL unavailable | All tests require PostgreSQL setup | CI fragility, local dev friction | Never - breaks existing CI |
| Use LlamaIndex PGVectorStore without version pinning | Latest features | Breaking changes, version conflicts | Never - pin exact versions |
| Build HNSW index on live production database | No migration downtime | Hours of degraded performance | Only if dataset < 10k docs |
| Single storage backend in Phase 1 | Faster development | No validation of abstraction quality | Never - defeats purpose of abstraction |
| Copy ChromaDB test fixtures for PostgreSQL | Faster test writing | Divergent test coverage, missed bugs | Acceptable for initial phase, must deduplicate |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **asyncpg** | Create pool in route handler | Create pool in app lifespan, store in app.state |
| **pgvector** | Use `CREATE EXTENSION vector` without error handling | `CREATE EXTENSION IF NOT EXISTS vector`, check availability first |
| **LlamaIndex PGVectorStore** | Import without version check | Pin version, test Pydantic compatibility |
| **Docker Compose PostgreSQL** | Use official postgres:16 image | Use pgvector/pgvector:pg17 or ankane/pgvector |
| **tsvector GIN index** | Create generic index on `to_tsvector(content)` | Specify language: `CREATE INDEX ON docs USING GIN (to_tsvector('english', content))` |
| **Connection pooling** | Use default pool size (10) | Tune based on workload: 20-50 for production |
| **Schema migrations** | Manual SQL scripts | Use Alembic for async engine, version control migrations |
| **HNSW index tuning** | Use default parameters | Tune `m`, `ef_construction` based on recall/performance tradeoff |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| **HNSW index on large dataset** | Index creation takes hours, blocks queries | Build index before bulk load, tune maintenance_work_mem | > 50k documents |
| **Connection pool too small** | Timeout spikes during concurrent load | Pool size >= expected concurrent requests | > 20 concurrent users |
| **tsvector without GIN index** | Queries slow as docs grow | Create GIN index on tsvector column | > 5k documents |
| **Missing connection pool lifecycle** | Stale connections, memory leaks | Close pool in app shutdown, set max_inactive_connection_lifetime | Long-running server |
| **BM25 with ts_rank (not ts_rank_cd)** | Slow queries on long documents | Use ts_rank_cd with normalization | Documents > 1000 words |
| **No batch inserts** | Slow indexing, connection exhaustion | Batch embeddings + upserts, 100 documents per transaction | > 1000 documents |
| **Synchronous PostgreSQL queries** | Event loop blocking under load | Use asyncpg with async/await throughout | > 10 concurrent requests |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| **Database credentials in code** | Credentials leak in version control | Use environment variables, never commit .env |
| **SQL injection in tsvector queries** | Arbitrary SQL execution | Use parameterized queries, validate language config |
| **Unrestricted pgvector dimensions** | Resource exhaustion attacks (huge vectors) | Validate dimension limits in API, enforce at schema |
| **No connection pool max_size** | DoS via connection exhaustion | Set max_size, implement backpressure/queueing |
| **Exposing raw SQL errors to API** | Information disclosure (schema, versions) | Catch asyncpg exceptions, return generic errors |
| **Missing vector dimension validation** | Incompatible embeddings corrupt index | Validate dimensions match schema before insert |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| **No migration path between backends** | User trapped with ChromaDB, can't try PostgreSQL | Provide `agent-brain migrate` command |
| **Backend switch breaks existing queries** | User switches backend, queries return different results | Document score normalization, provide comparison tool |
| **Index build with no progress indicator** | User waits for hours, thinks system hung | Log index build progress, expose via health endpoint |
| **Connection errors with no context** | "Connection refused" doesn't tell user to start PostgreSQL | "PostgreSQL not running. Run: docker-compose up postgres" |
| **Backend configuration unclear** | User doesn't know how to switch to PostgreSQL | Clear docs: "Set STORAGE_BACKEND=postgres in .env" |
| **No performance comparison guidance** | User doesn't know which backend to choose | Document: "ChromaDB: simple setup. PostgreSQL: production scale" |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **PostgreSQL backend:** Often missing connection pool lifecycle (startup/shutdown) — verify health check fails gracefully when pool closed
- [ ] **tsvector search:** Often missing GIN index creation — verify EXPLAIN ANALYZE shows index usage
- [ ] **HNSW index:** Often missing parameter tuning docs — verify README explains m, ef_construction tradeoffs
- [ ] **Storage abstraction:** Often missing error normalization — verify PostgreSQL errors don't leak through interface
- [ ] **Test markers:** Often missing @pytest.mark.postgres — verify tests skip when PostgreSQL unavailable
- [ ] **Migration tool:** Often missing data validation — verify migrated embeddings match source
- [ ] **Docker Compose:** Often missing pgvector extension — verify CREATE EXTENSION vector succeeds
- [ ] **Score normalization:** Often missing backend-specific logic — verify hybrid search weights both retrievers fairly
- [ ] **Connection pooling:** Often missing monitoring/metrics — verify pool status exposed in health endpoint
- [ ] **Dimension validation:** Often missing schema check — verify startup fails if config/schema mismatch

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| **Dimension mismatch** | MEDIUM | 1. Drop pgvector index, 2. Alter column dimension, 3. Re-index all documents, 4. Rebuild HNSW |
| **Connection pool exhaustion** | LOW | 1. Restart server, 2. Increase pool max_size, 3. Deploy with new config |
| **HNSW index stuck building** | MEDIUM | 1. Cancel index build (CTRL+C or pg_cancel_backend), 2. Drop partial index, 3. Build with lower ef_construction |
| **Leaky abstraction** | HIGH | 1. Refactor to Protocol/ABC, 2. Extract adapters, 3. Add contract tests, 4. Migrate services |
| **tsvector query not using index** | LOW | 1. Check index definition with `\d+ table`, 2. Update query to match exactly, 3. Re-run EXPLAIN ANALYZE |
| **PostgreSQL extension missing** | LOW | 1. Use pgvector Docker image, 2. Rebuild containers, 3. CREATE EXTENSION vector |
| **BM25 score mismatch** | MEDIUM | 1. Implement score normalizer, 2. Add score range tests, 3. Tune RRF weights |
| **Version conflict** | MEDIUM | 1. Pin llama-index versions, 2. Test in isolation, 3. Consider custom adapter without LlamaIndex |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Async/sync mismatch | Phase 1 (Storage Abstraction) | Load test with 50 concurrent requests |
| Embedding dimension mismatch | Phase 1 (Storage Abstraction) + Phase 2 (PostgreSQL) | Schema validation on startup, integration test with dimension change |
| tsvector language config | Phase 2 (PostgreSQL Implementation) | EXPLAIN ANALYZE in tests validates index usage |
| Connection pool exhaustion | Phase 2 (PostgreSQL Implementation) | Load test with 100 concurrent ops, pool metrics exposed |
| Docker pgvector extension | Phase 2 (PostgreSQL Implementation) | docker-compose up succeeds on fresh clone |
| Test infrastructure | Phase 3 (Testing & CI) | task before-push passes without PostgreSQL |
| Leaky abstraction | Phase 1 (Storage Abstraction) | Services never import backend-specific modules |
| LlamaIndex version incompatibility | Phase 2 (PostgreSQL Implementation) | poetry lock --check passes, CI test with restricted DB user |
| HNSW index blocking | Phase 2 (PostgreSQL Implementation) + Phase 5 (Migration) | Document build time, migration builds index before load |
| BM25 score incompatibility | Phase 2 (PostgreSQL Implementation) + Phase 3 (Testing) | Contract test validates similar results across backends |

---

## Sources

**PostgreSQL/pgvector Integration:**
- [Postgres Vector Store | LlamaIndex Python Documentation](https://developers.llamaindex.ai/python/examples/vector_stores/postgres/)
- [Using llama index with existing postgres db and pgvector extension · Issue #6058](https://github.com/jerryjliu/llama_index/issues/6058)
- [Question: How to add new fields to the table it creates · Issue #17022](https://github.com/run-llama/llama_index/issues/17022)
- [pgvector: Key features, tutorial, and pros and cons [2026 guide]](https://www.instaclustr.com/education/vector-database/pgvector-key-features-tutorial-and-pros-and-cons-2026-guide/)

**Dimension Mismatch Issues:**
- [GitHub - pgvector/pgvector: Open-source vector similarity search for Postgres](https://github.com/pgvector/pgvector)
- [How to deal with different vector-dimensions for embeddings and search with pgvector?](https://community.openai.com/t/how-to-deal-with-different-vector-dimensions-for-embeddings-and-search-with-pgvector/602141)
- [PGVectorStore: Error: different vector dimensions 4 and 1 · Issue #3509](https://github.com/langchain-ai/langchainjs/issues/3509)

**tsvector and GIN Index Configuration:**
- [Understanding Postgres GIN Indexes: The Good and the Bad](https://pganalyze.com/blog/gin-index)
- [PostgreSQL: Documentation: 18: 12.2. Tables and Indexes](https://www.postgresql.org/docs/current/textsearch-tables.html)
- [How to index data with tsearch? – select * from depesz;](https://www.depesz.com/2022/03/01/how-to-index-data-with-tsearch/)
- [PostgreSQL Full-Text Search: A Powerful Alternative to Elasticsearch](https://iniakunhuda.medium.com/postgresql-full-text-search-a-powerful-alternative-to-elasticsearch-for-small-to-medium-d9524e001fe0)

**Connection Pooling and FastAPI:**
- [How to maintain global pool of db connection · Discussion #9097](https://github.com/fastapi/fastapi/discussions/9097)
- [Building an Async Product Management API with FastAPI, Pydantic, and PostgreSQL](https://neon.com/guides/fastapi-async)
- [FastAPI without ORM: Getting started with asyncpg](https://www.sheshbabu.com/posts/fastapi-without-orm-getting-started-with-asyncpg/)
- [Handling PostgreSQL Connection Limits in FastAPI Efficiently](https://medium.com/@rameshkannanyt0078/handling-postgresql-connection-limits-in-fastapi-efficiently-379ff44bdac5)

**Docker Compose and pgvector Extension:**
- [Setting Up PostgreSQL with pgvector in Docker: A Step-by-Step Guide](https://medium.com/@adarsh.ajay/setting-up-postgresql-with-pgvector-in-docker-a-step-by-step-guide-d4203f6456bd)
- [Docker with postgres and pgvector extension](https://www.thestupidprogrammer.com/blog/docker-with-postgres-and-pgvector-extension/)
- [Automating Postgres and pgvector Setup with Docker](https://alpeshkumar.com/docker/automating-postgres-and-pgvector-setup-with-docker/)

**Async/Sync Migration Patterns:**
- [Architectural Consistency When Working with a PostgreSQL Async Database](https://oppkey.github.io/fastopp/2025/10/07/postgresql-async/)
- [Efficient PostgreSQL Connection Management with Singleton Pattern](https://medium.com/@ashkangoleh/efficient-postgresql-connection-management-with-singleton-pattern-and-async-sync-engines-in-71b349e4c61d)
- [PostgreSQL 18 Async I/O in Production: Real-World Benchmarks](https://postgresqlhtx.com/postgresql-18-async-i-o-in-production-real-world-benchmarks-configuration-patterns-and-storage-performance-in-2026/)

**Test Infrastructure and pytest-postgresql:**
- [pytest-postgresql · PyPI](https://pypi.org/project/pytest-postgresql/)
- [How to Skip Tests in Pytest: Markers, Conditions, and Examples](https://www.browserstack.com/guide/pytest-skip)
- [Running tests against PostgreSQL in a service container](https://til.simonwillison.net/github-actions/postgresq-service-container)
- [GitHub - dbfixtures/pytest-postgresql](https://github.com/dbfixtures/pytest-postgresql)

**LlamaIndex Version Compatibility:**
- [Bug: llama_index.vector_stores import PGVectorStore forces schema creation · Issue #9710](https://github.com/run-llama/llama_index/issues/9710)
- [Bug: initializing llama-index with pgvector does not work · Issue #15884](https://github.com/run-llama/llama_index/issues/15884)
- [llama-index-vector-stores-postgres · PyPI](https://pypi.org/project/llama-index-vector-stores-postgres/)

**Storage Abstraction and Leaky Abstractions:**
- [Leaky Abstractions. Engineering Insights | by Talin | Machine Words](https://medium.com/machine-words/leaky-abstractions-2c42dd6e53d5)
- [Modern Law of Leaky Abstractions](https://codecube.net/2026/1/modern-law-leaky-abstractions/)
- [Leaky Abstractions | Alex Kondov](https://alexkondov.com/leaky-abstractions/)

**HNSW Index Performance:**
- [HNSW index creation is stuck on dozens millions entries · Issue #822](https://github.com/pgvector/pgvector/issues/822)
- [HNSW Indexes with Postgres and pgvector | Crunchy Data Blog](https://www.crunchydata.com/blog/hnsw-indexes-with-postgres-and-pgvector)
- [Performance Issue with Large Tables and HNSW Indexes · Issue #455](https://github.com/pgvector/pgvector/issues/455)
- [The Case Against pgvector | Alex Jacobs](https://alex-jacobs.com/posts/the-case-against-pgvector/)
- [Adding data after building hnsw index is much slower · Issue #559](https://github.com/pgvector/pgvector/issues/559)

---
*Pitfalls research for: PostgreSQL/pgvector Backend Integration for Agent Brain*
*Researched: 2026-02-10*
*Context: Adding PostgreSQL as dual storage backend to existing ChromaDB-based RAG system with 505 tests, 70% coverage*
