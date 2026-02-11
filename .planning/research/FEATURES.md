# Feature Landscape: PostgreSQL Backend with pgvector + tsvector

**Domain:** RAG storage backend with PostgreSQL
**Researched:** 2026-02-10
**Confidence:** HIGH (Context7 + Official Docs + Recent Community Sources)

## Table Stakes

Features users expect from a PostgreSQL RAG backend. Missing = product feels incomplete.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| **pgvector vector storage** | Core capability, users choosing PostgreSQL want pgvector | Low | Add pgvector extension, SQLAlchemy integration | Official pgvector extension widely adopted |
| **Cosine distance search** | Industry standard for normalized embeddings (OpenAI, etc.) | Low | Existing embedding pipeline | ChromaDB already uses cosine, direct mapping |
| **L2 (Euclidean) distance** | Expected for completeness, some models use it | Low | Same as cosine | Common alternative to cosine |
| **Inner product distance** | Best performance for normalized vectors | Low | Same as cosine | Most efficient for pre-normalized embeddings |
| **tsvector full-text search** | PostgreSQL's native FTS, users expect it | Medium | PostgreSQL built-in, no external deps | Alternative to BM25 disk index |
| **GIN index for tsvector** | Required for performant FTS at scale | Low | PostgreSQL built-in | Standard optimization pattern |
| **HNSW index for vectors** | Modern ANN index, expected for production use | Medium | pgvector 0.5.0+, careful tuning | Balances query speed and build time |
| **IVFFlat index option** | Faster build times for batch workloads | Low | pgvector built-in | Alternative to HNSW for different use cases |
| **Storage backend abstraction** | Users need to select ChromaDB vs PostgreSQL | Medium | Refactor VectorStoreManager to interface | Enables backend selection without code changes |
| **Backend config in YAML** | Standard expectation for service configuration | Low | Existing config infrastructure | Extends current config patterns |
| **Docker Compose setup** | Dev environment standard for databases | Low | Docker only, no code changes | pgvector/pgvector:pg17 image available |
| **Hybrid RRF fusion** | Existing feature, must work with PostgreSQL | High | Existing RRF logic, adapt for PG queries | Already implemented for ChromaDB + BM25 |
| **Language configuration** | tsvector expects language-aware stemming | Medium | PostgreSQL text search config | english/simple/etc., affects ranking quality |

## Differentiators

Features that set the PostgreSQL backend apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|--------------|-------|
| **BM25 via pg_textsearch** | True BM25 ranking vs ts_rank | Medium-High | pg_textsearch extension (Timescale, new) | Native PostgreSQL lacks BM25, ts_rank is weaker |
| **Hybrid search in single query** | PostgreSQL can do vector + FTS in one SQL call | Medium | SQL query expertise | ChromaDB + disk BM25 requires separate queries |
| **Transactional consistency** | ACID guarantees for index updates | Low (built-in) | None, PostgreSQL native | ChromaDB lacks strong consistency |
| **SQL-based filtering** | WHERE clauses on metadata before vector search | Medium | SQLAlchemy query builder | More flexible than ChromaDB metadata filters |
| **DiskANN index support** | pgvectorscale extension for faster, lower-memory ANN | High | pgvectorscale (Timescale extension) | Recent 2026 option, balances HNSW/IVFFlat tradeoffs |
| **Statistical Binary Quantization** | Reduce vector storage size, faster similarity | Medium-High | pgvectorscale extension | Advanced optimization, not table stakes |
| **Graph + vector in one DB** | Store GraphRAG + vectors + FTS in PostgreSQL | Medium | Existing GraphStoreManager, PG schema | Simplifies deployment vs multi-DB setup |
| **Backup/restore ecosystem** | pg_dump, pg_restore, replication tools | Low (built-in) | None, PostgreSQL tooling | Operations advantage vs ChromaDB snapshots |
| **Multi-tenancy with schemas** | Isolate collections per tenant/project | Medium | PostgreSQL schemas, security model | Better than collection-based isolation |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Replace ChromaDB entirely** | ChromaDB is simpler for local-first, no DB setup | Keep ChromaDB as default, PostgreSQL as optional backend |
| **Auto-migration ChromaDB → PostgreSQL** | Complex, error-prone, users can rebuild index | Document manual migration: export → rebuild → verify |
| **PostgreSQL-only deployment** | Breaks local-first promise, requires DB management | PostgreSQL is opt-in, ChromaDB remains default |
| **Build custom BM25 in Python** | Reinventing wheel, pg_textsearch/VectorChord-BM25 exist | Use tsvector ts_rank for MVP, document BM25 extension option |
| **Support all pgvector distance metrics** | Cosine/L2/inner product cover 99% of use cases | Skip hamming, jaccard unless user demand emerges |
| **Real-time index updates** | PostgreSQL HNSW build is slow (32x IVFFlat), batching preferred | Design for batch reindexing, not per-document updates |
| **Automatic index type selection** | HNSW vs IVFFlat depends on workload, user must decide | Provide clear guidance in docs, sensible defaults |

## Feature Dependencies

```
Storage Backend Abstraction
  ├─> PostgreSQL Vector Storage (pgvector)
  │    ├─> HNSW Index (production)
  │    ├─> IVFFlat Index (batch workloads)
  │    └─> Distance Metrics (cosine/L2/inner)
  ├─> PostgreSQL Full-Text Search (tsvector)
  │    ├─> GIN Index
  │    └─> Language Configuration
  └─> Hybrid RRF Fusion (existing)
       └─> Adapts to PostgreSQL queries

Backend Selection Config
  └─> YAML config (backend: chromadb|postgresql)

Docker Development Setup
  └─> docker-compose.yml with pgvector/pgvector:pg17

Optional Enhancements:
  ├─> BM25 (pg_textsearch extension)
  ├─> DiskANN (pgvectorscale extension)
  └─> Graph + Vector co-location
```

## MVP Recommendation

**Prioritize (Phase 1):**
1. **Storage backend abstraction layer** — Interface for VectorStoreManager, swappable implementations
2. **pgvector vector storage** — Cosine/L2/inner product, HNSW index, basic CRUD
3. **tsvector full-text search** — GIN index, language config (english default), ts_rank scoring
4. **Backend selection via YAML** — `storage.backend: chromadb|postgresql`, connection config
5. **Docker Compose setup** — pgvector/pgvector:pg17, volume mounts, init scripts
6. **Hybrid RRF adaptation** — Modify existing RRF to work with PostgreSQL result sets

**Defer to Phase 2+:**
- **BM25 via pg_textsearch** — Requires extension management, may not be available in all PG instances
- **DiskANN/pgvectorscale** — Advanced optimization, not needed for initial validation
- **Multi-tenancy with schemas** — Complex security model, single-tenant is simpler MVP
- **SQL-based metadata filtering** — Nice-to-have, ChromaDB parity is metadata dict filtering
- **Graph co-location** — Existing GraphStoreManager is separate, no urgency to merge

**Defer indefinitely (anti-features):**
- Auto-migration ChromaDB → PostgreSQL
- PostgreSQL-only deployment
- Custom BM25 implementation
- Real-time per-document index updates

## Implementation Notes

### pgvector Index Selection

**HNSW (default for production):**
- Query speed: 15.5x faster than IVFFlat (40.5 QPS vs 2.6 QPS)
- Build time: 32x slower than IVFFlat (4065s vs 128s)
- Index size: 2.8x larger (729MB vs 257MB)
- Use when: Latency-critical, read-heavy workloads, high recall requirements

**IVFFlat (batch workloads):**
- Build time: 32x faster than HNSW
- Index size: 2.8x smaller
- Query speed: 15.5x slower
- Use when: Batch reindexing, periodic updates, storage-constrained environments
- Caveat: Not resilient to updates (centroids not recalculated)

**Recommendation:** Default to HNSW for Agent Brain's interactive query use case, document IVFFlat for users who batch-rebuild indexes overnight.

### tsvector vs BM25

**tsvector with ts_rank (MVP):**
- Built-in PostgreSQL, no extensions required
- Weaker ranking: linear TF weighting, no IDF, no doc-length normalization
- GIN index for performance
- Language-aware stemming (english, simple, etc.)
- Good enough for MVP, widely deployed

**BM25 extensions (future enhancement):**
- **pg_textsearch** (Timescale): OSS, true BM25, hybrid search support
- **VectorChord-BM25** (TensorChord): 3x faster than Elasticsearch claim
- **ParadeDB**: Commercial-friendly OSS, BM25 + hybrid search
- Requires extension installation, may not be available in managed PostgreSQL

**MVP decision:** Use tsvector + ts_rank, document BM25 extension path for users who need it.

### Hybrid Search Implementation

**Existing (ChromaDB + disk BM25):**
1. Vector query → ChromaDB (cosine similarity)
2. BM25 query → disk index (rank-bm25 library)
3. RRF fusion in Python (combine rankings, re-score)

**PostgreSQL approach:**
1. Vector query → pgvector (CTE or subquery)
2. FTS query → tsvector (CTE or subquery)
3. RRF fusion in SQL or Python
   - **SQL approach:** Single query with UNION ALL + RRF formula
   - **Python approach:** Separate queries, existing RRF logic

**Recommendation:** Start with Python RRF (reuse existing code), optimize to SQL later if performance demands.

### Storage Abstraction Pattern

**Interface (ABC):**
```python
class VectorStoreBackend(ABC):
    @abstractmethod
    async def initialize(self) -> None: ...
    @abstractmethod
    async def add_chunks(self, chunks, embeddings, metadatas) -> None: ...
    @abstractmethod
    async def similarity_search(self, embedding, top_k, threshold) -> list[SearchResult]: ...
    @abstractmethod
    async def count_chunks(self) -> int: ...
    @abstractmethod
    async def clear(self) -> None: ...
```

**Implementations:**
- `ChromaDBBackend` (existing VectorStoreManager logic)
- `PostgreSQLBackend` (new, pgvector + SQLAlchemy)

**Selection:**
```yaml
# config.yaml
storage:
  backend: postgresql  # or chromadb (default)
  postgresql:
    host: localhost
    port: 5432
    database: agent_brain
    user: postgres
    password: secret
    vector_index: hnsw  # or ivfflat
    fts_language: english
```

### Distance Metric Mapping

**Current (ChromaDB):**
- Cosine distance (default)

**PostgreSQL pgvector:**
- `<=>` cosine distance (1 - cosine similarity)
- `<->` L2 (Euclidean) distance
- `<#>` negative inner product (max inner product = min negative)

**Recommendation:** Default to cosine (`<=>`), expose all three in config for advanced users.

### Docker Compose Structure

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg17
    environment:
      POSTGRES_USER: agent_brain
      POSTGRES_PASSWORD: dev_password
      POSTGRES_DB: agent_brain
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agent_brain"]
      interval: 5s
      timeout: 5s
      retries: 5
```

**init.sql:**
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS chunks (
  id TEXT PRIMARY KEY,
  embedding vector(3072),  -- EMBEDDING_DIMENSIONS
  text TEXT NOT NULL,
  metadata JSONB,
  tsvector_content tsvector
);
CREATE INDEX ON chunks USING HNSW (embedding vector_cosine_ops);
CREATE INDEX ON chunks USING GIN (tsvector_content);
```

## Comparison: ChromaDB vs PostgreSQL

| Aspect | ChromaDB | PostgreSQL + pgvector | Winner |
|--------|----------|----------------------|--------|
| **Setup complexity** | Zero config, local files | Docker/managed DB required | ChromaDB |
| **Query latency (single)** | Very fast (~ms) | Very fast (~ms), close to ChromaDB | Tie |
| **Query latency (concurrent)** | Degrades (23.08s avg under load) | Better (9.81s avg under load) | PostgreSQL |
| **Index build time** | Fast | Slow (HNSW 32x slower than IVFFlat) | ChromaDB |
| **Consistency** | Eventual | ACID transactions | PostgreSQL |
| **Hybrid search** | Separate BM25 index + fusion | Single DB, single query option | PostgreSQL |
| **Operational maturity** | Young project, limited tooling | pg_dump, replication, monitoring | PostgreSQL |
| **Scalability (vectors)** | Millions-billions optimized | Thousands-millions (pgvectorscale extends) | ChromaDB |
| **RAG use case fit** | Purpose-built, excellent | General-purpose, very good | ChromaDB |
| **Agent Brain fit (local-first)** | Perfect, no setup | Requires DB, more complex | ChromaDB |

**Verdict:** ChromaDB remains best default for Agent Brain's local-first philosophy. PostgreSQL is valuable optional backend for users who:
- Already run PostgreSQL infrastructure
- Need ACID consistency for production apps
- Want unified DB for vectors + relational data + graph
- Require enterprise ops tooling (backup/restore/replication)

## Confidence Assessment

| Finding | Level | Source |
|---------|-------|--------|
| pgvector capabilities | HIGH | Official pgvector GitHub, PostgreSQL docs |
| HNSW vs IVFFlat performance | HIGH | AWS Deep Dive (2025), multiple benchmarks |
| tsvector vs BM25 ranking | HIGH | ParadeDB blog, Timescale pg_textsearch docs |
| Hybrid search patterns | MEDIUM | Community blogs (2025-2026), verified patterns |
| ChromaDB vs PostgreSQL perf | MEDIUM | Multiple benchmarks, 2026 comparisons (varied workloads) |
| Docker setup | HIGH | Official pgvector/pgvector Docker Hub image |
| Storage abstraction pattern | HIGH | Python repository pattern (standard practice) |
| RRF implementation | HIGH | ParadeDB guide, DBI Services RAG series |
| BM25 extension options | MEDIUM | New 2025-2026 extensions, less mature than pgvector |

## Sources

### pgvector and Vector Search
- [GitHub - pgvector/pgvector](https://github.com/pgvector/pgvector)
- [pgvector: Embeddings and vector similarity | Supabase Docs](https://supabase.com/docs/guides/database/extensions/pgvector)
- [pgvector: Key features, tutorial, and pros and cons [2026 guide]](https://www.instaclustr.com/education/vector-database/pgvector-key-features-tutorial-and-pros-and-cons-2026-guide/)
- [PostgreSQL + pgvector specifically for your RAG use case | Medium](https://medium.com/@TechSnazAI/postgresql-pgvector-specifically-for-your-rag-use-case-dbbaf41d5822)
- [Optimize generative AI applications with pgvector indexing | AWS](https://aws.amazon.com/blogs/database/optimize-generative-ai-applications-with-pgvector-indexing-a-deep-dive-into-ivfflat-and-hnsw-techniques/)
- [Choosing your Index with PGVector | PIXION Blog](https://pixion.co/blog/choosing-your-index-with-pg-vector-flat-vs-hnsw-vs-ivfflat)
- [PGVector: HNSW vs IVFFlat | Medium](https://medium.com/@bavalpreetsinghh/pgvector-hnsw-vs-ivfflat-a-comprehensive-study-21ce0aaab931)

### tsvector and Full-Text Search
- [PostgreSQL: Documentation: Text Search](https://www.postgresql.org/docs/current/textsearch-controls.html)
- [PostgreSQL BM25 Full-Text Search | VectorChord](https://blog.vectorchord.ai/postgresql-full-text-search-fast-when-done-right-debunking-the-slow-myth)
- [From ts_rank to BM25. Introducing pg_textsearch | Tiger Data](https://www.tigerdata.com/blog/introducing-pg_textsearch-true-bm25-ranking-hybrid-retrieval-postgres)
- [GitHub - timescale/pg_textsearch](https://github.com/timescale/pg_textsearch)
- [GitHub - tensorchord/VectorChord-bm25](https://github.com/tensorchord/VectorChord-bm25)
- [Implementing BM25 in PostgreSQL | ParadeDB](https://www.paradedb.com/learn/search-in-postgresql/bm25)

### Hybrid Search and RRF
- [Hybrid Search in PostgreSQL: The Missing Manual | ParadeDB](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual)
- [RAG Series - Hybrid Search with Re-ranking](https://www.dbi-services.com/blog/rag-series-hybrid-search-with-re-ranking/)
- [Hybrid search with PostgreSQL and pgvector | Jonathan Katz](https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/)
- [pgvector Hybrid Search: Benefits, Use Cases, and Quick Tutorial](https://www.instaclustr.com/education/vector-database/pgvector-hybrid-search-benefits-use-cases-and-quick-tutorial/)

### ChromaDB vs PostgreSQL Comparisons
- [Pgvector vs Chroma DB Which Works Better for RAG | Medium](https://medium.com/@mysterious_obscure/pgvector-vs-chroma-db-which-works-better-for-rag-based-applications-3df813ad7307)
- [Chroma vs pgvector | Vector Database Comparison](https://zilliz.com/comparison/chroma-vs-pgvector)
- [ChromaDB vs PGVector: The Epic Battle | Medium](https://dev523.medium.com/chromadb-vs-pgvector-the-epic-battle-of-vector-databases-a43216772b34)
- [Best vector databases for production RAG in 2026](https://engineersguide.substack.com/p/best-vector-databases-rag)

### Docker and Development Setup
- [Setting Up PostgreSQL with pgvector in Docker | Medium](https://medium.com/@adarsh.ajay/setting-up-postgresql-with-pgvector-in-docker-a-step-by-step-guide-d4203f6456bd)
- [Docker with postgres and pgvector extension](https://www.thestupidprogrammer.com/blog/docker-with-postgres-and-pgvector-extension/)
- [pgvector/pgvector - Docker Image](https://hub.docker.com/r/pgvector/pgvector)
- [Setting up Postgres and pgvector with Docker for RAG | UserJot](https://userjot.com/blog/setting-up-postgres-pgvector-docker-rag)

### Python Integration
- [GitHub - pgvector/pgvector-python](https://github.com/pgvector/pgvector-python)
- [Postgres Vector Store | LlamaIndex Python Documentation](https://developers.llamaindex.ai/python/examples/vector_stores/postgres/)
- [Detailed Walkthrough of Llama Index with PostgreSQL | Medium](https://medium.com/@vg-shyamala/detailed-walkthrough-of-a-python-code-integrating-llama-index-with-postgresql-and-pgvectorstore-2e07d387bdf2)
- [Repository Pattern - Cosmic Python](https://www.cosmicpython.com/book/chapter_02_repository.html)
- [The Repository Pattern in Python | Medium](https://medium.com/@kmuhsinn/the-repository-pattern-in-python-write-flexible-testable-code-with-fastapi-examples-aa0105e40776)

### GIN Indexes
- [PostgreSQL: Documentation: GIN Indexes](https://www.postgresql.org/docs/current/gin.html)
- [Understanding Postgres GIN Indexes | pganalyze](https://pganalyze.com/blog/gin-index)
- [How to Build Full-Text Search with GIN Indexes | OneUpTime](https://oneuptime.com/blog/post/2026-01-25-full-text-search-gin-postgresql/view)
