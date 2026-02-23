# Requirements: Agent Brain

**Defined:** 2026-02-10
**Core Value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships

## v6.0 Requirements

Requirements for PostgreSQL Backend milestone. Each maps to roadmap phases.

### Storage Abstraction

- [ ] **STOR-01**: Storage operations defined by async Protocol interface (vector search, keyword search, upsert, count, reset)
- [ ] **STOR-02**: ChromaDB backend implements storage Protocol via asyncio.to_thread() wrappers
- [ ] **STOR-03**: Backend factory selects ChromaDB or PostgreSQL from YAML configuration
- [ ] **STOR-04**: Services depend only on Protocol interface, not concrete backend classes
- [ ] **STOR-05**: Contract test suite validates identical behavior expectations across backends

### PostgreSQL Vector Search

- [ ] **PGVEC-01**: pgvector extension stores and queries embedding vectors via HNSW index
- [ ] **PGVEC-02**: Vector similarity search supports cosine, L2, and inner product distance metrics
- [ ] **PGVEC-03**: Embedding dimension validated against provider config on startup (prevents schema mismatch)
- [ ] **PGVEC-04**: HNSW index parameters (m, ef_construction) configurable via YAML

### PostgreSQL Full-Text Search

- [ ] **PGFTS-01**: tsvector column with GIN index provides keyword search on document content
- [ ] **PGFTS-02**: Full-text search language configurable (default: English)
- [ ] **PGFTS-03**: Hybrid retrieval with RRF fusion works across pgvector + tsvector results
- [ ] **PGFTS-04**: Score normalization ensures consistent ranking between ChromaDB and PostgreSQL backends

### Infrastructure

- [ ] **INFRA-01**: Docker Compose provides local PostgreSQL + pgvector development environment
- [ ] **INFRA-02**: Connection pooling with configurable pool size managed via FastAPI lifespan
- [ ] **INFRA-03**: Health check endpoint reports PostgreSQL backend status and connection pool metrics
- [ ] **INFRA-04**: SQL schema initialization scripts create tables, indexes, and extensions on first run
- [ ] **INFRA-05**: PostgreSQL dependencies installed as Poetry extras (optional, not required for ChromaDB)

### Configuration

- [ ] **CONF-01**: YAML config schema includes storage.backend section (chroma or postgres)
- [ ] **CONF-02**: PostgreSQL connection parameters configurable (host, port, database, user, password via env var)
- [ ] **CONF-03**: Environment variable override for backend selection (AGENT_BRAIN_STORAGE_BACKEND)

### Testing

- [ ] **TEST-01**: Contract tests parameterized over ChromaDB and PostgreSQL backends
- [ ] **TEST-02**: PostgreSQL tests use pytest marker (@pytest.mark.postgres) and skip without database
- [ ] **TEST-03**: task before-push passes without PostgreSQL (skips postgres-marked tests)
- [ ] **TEST-04**: GitHub Actions CI includes PostgreSQL service container for postgres-marked tests

### Plugin

- [ ] **PLUG-01**: /agent-brain-config command asks storage backend selection (ChromaDB vs PostgreSQL) in Q&A flow
- [ ] **PLUG-02**: /agent-brain-config generates storage.backend YAML section with PostgreSQL connection parameters
- [ ] **PLUG-03**: /agent-brain-setup detects Docker and offers to start PostgreSQL via Docker Compose
- [ ] **PLUG-04**: configuring-agent-brain skill references updated with storage backend configuration guide
- [ ] **PLUG-05**: Setup assistant agent recognizes PostgreSQL-related errors (connection refused, pgvector missing, pool exhausted)
- [ ] **PLUG-06**: Plugin version bumped to v5.0.0 with updated plugin.json metadata

### Documentation

- [ ] **DOCS-01**: Docker Compose setup guide for local PostgreSQL + pgvector development
- [ ] **DOCS-02**: Backend selection and configuration reference in provider docs
- [ ] **DOCS-03**: Performance tradeoffs guide (ChromaDB vs PostgreSQL — when to use which)

## v6.0.2 Requirements

### Plugin Enhancements
- [x] **PLUG-07**: /agent-brain-setup and /agent-brain-config auto-discover free PostgreSQL port (scan 5432-5442)
- [x] **PLUG-08**: Plugin version bumped to v6.0.2 with updated metadata

### Infrastructure Fix
- [x] **INFRA-06**: install.sh REPO_ROOT path corrected (doc-serve → agent-brain)

## Future Requirements

Deferred to subsequent milestones. Tracked but not in current roadmap.

### PostgreSQL Enhancements

- **PGADV-01**: BM25 ranking via pg_textsearch extension (true BM25 vs tsvector ts_rank)
- **PGADV-02**: GraphRAG storage on PostgreSQL (JSONB for graph entities and relationships)
- **PGADV-03**: Alembic schema migrations for production deployments
- **PGADV-04**: DiskANN/pgvectorscale optimizations for large-scale deployments
- **PGADV-05**: Multi-tenancy with PostgreSQL schema isolation

### Cloud Providers

- **CLOUD-01**: AWS Bedrock provider (embeddings: Titan, Cohere; summarization: Claude, Llama, Mistral)
- **CLOUD-02**: Vertex AI provider (embeddings: textembedding-gecko; summarization: Gemini)

### Performance Optimizations

- **PERF-01**: Embedding cache with content hashing
- **PERF-02**: File watcher for auto-indexing
- **PERF-03**: Query caching with LRU
- **PERF-04**: UDS transport for sub-ms latency

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Replace ChromaDB entirely | ChromaDB remains default for local-first simplicity |
| Auto-migration ChromaDB to PostgreSQL | Complex and error-prone; users re-index from source |
| AlloyDB-specific features | Standard PostgreSQL + pgvector for maximum portability |
| PostgreSQL-only deployment mode | Breaks local-first promise; ChromaDB must always work |
| Custom BM25 implementation in Python | Use native tsvector; document pg_textsearch extension path for future |
| Real-time per-document HNSW updates | HNSW build is slow; design for batch reindexing |
| GraphRAG on PostgreSQL | Stays on ChromaDB SimplePropertyGraphStore for this milestone |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| STOR-01 | Phase 5 | Done |
| STOR-02 | Phase 5 | Done |
| STOR-03 | Phase 5 | Done |
| STOR-04 | Phase 5 | Done |
| CONF-01 | Phase 5 | Done |
| CONF-02 | Phase 5 | Done |
| CONF-03 | Phase 5 | Done |
| PGVEC-01 | Phase 6 | Done |
| PGVEC-02 | Phase 6 | Done |
| PGVEC-03 | Phase 6 | Done |
| PGVEC-04 | Phase 6 | Done |
| PGFTS-01 | Phase 6 | Done |
| PGFTS-02 | Phase 6 | Done |
| PGFTS-03 | Phase 6 | Done |
| PGFTS-04 | Phase 6 | Done |
| INFRA-01 | Phase 6 | Done |
| INFRA-02 | Phase 6 | Done |
| INFRA-03 | Phase 6 | Done |
| INFRA-04 | Phase 6 | Done |
| INFRA-05 | Phase 6 | Done |
| TEST-01 | Phase 7 | Done |
| TEST-02 | Phase 7 | Done |
| TEST-03 | Phase 7 | Done |
| TEST-04 | Phase 7 | Done |
| STOR-05 | Phase 7 | Done |
| PLUG-01 | Phase 8 | Done |
| PLUG-02 | Phase 8 | Done |
| PLUG-03 | Phase 8 | Done |
| PLUG-04 | Phase 8 | Done |
| PLUG-05 | Phase 8 | Done |
| PLUG-06 | Phase 8 | Done |
| DOCS-01 | Phase 8 | Done |
| DOCS-02 | Phase 8 | Done |
| DOCS-03 | Phase 8 | Done |

| PLUG-07 | Phase 11 | Done |
| PLUG-08 | Phase 11 | Done |
| INFRA-06 | Phase 11 | Done |

**Coverage:**
- v6.0 requirements: 34 total (all done)
- v6.0.2 requirements: 3 total
- Mapped to phases: 37
- Unmapped: 0
- Coverage: 100%

**Phase Distribution:**
- Phase 5 (Storage Abstraction): 7 requirements
- Phase 6 (PostgreSQL Backend): 13 requirements
- Phase 7 (Testing & CI): 5 requirements
- Phase 8 (Plugin & Documentation): 9 requirements
- Phase 11 (Plugin Port Discovery & Install Fix): 3 requirements

---
*Requirements defined: 2026-02-10*
*Last updated: 2026-02-19 — Added v6.0.2 requirements (PLUG-07, PLUG-08, INFRA-06)*
