# Agent Brain Roadmap

**Created:** 2026-02-07
**Core Value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API

## Milestones

- ✅ **v3.0 Advanced RAG** — Phases 1-4 (shipped 2026-02-10)
- 🚧 **v5.0 PostgreSQL Backend** — Phases 5-8 (in progress)

## Phases

<details>
<summary>✅ v3.0 Advanced RAG (Phases 1-4) — SHIPPED 2026-02-10</summary>

- [x] Phase 1: Two-Stage Reranking (7/7 plans) — Feature 123
- [x] Phase 2: Pluggable Providers (4/4 plans) — Feature 103
- [x] Phase 3: Schema-Based GraphRAG (2/2 plans) — Feature 122
- [x] Phase 4: Provider Integration Testing (2/2 plans) — Feature 124

**Full details:** [v3.0-ROADMAP.md](milestones/v3.0-ROADMAP.md)

</details>

### 🚧 v5.0 PostgreSQL Backend (In Progress)

**Milestone Goal:** Add PostgreSQL as a configurable storage backend with pgvector for vector search and tsvector for full-text search, running alongside ChromaDB as a dual-backend architecture.

#### Phase 5: Storage Backend Abstraction Layer
**Goal**: Create async-first storage protocol to enable backend-agnostic services and prevent leaky abstractions
**Depends on**: Phase 4 (v3.0 completed)
**Requirements**: STOR-01, STOR-02, STOR-03, STOR-04, CONF-01, CONF-02, CONF-03
**Success Criteria** (what must be TRUE):
  1. Services depend only on StorageBackendProtocol interface, not concrete backend classes
  2. Backend selection works via YAML config (storage.backend: "chroma" or "postgres")
  3. ChromaBackend adapter passes all storage protocol operations without breaking existing functionality
  4. Environment variable AGENT_BRAIN_STORAGE_BACKEND overrides config file selection
  5. Server startup validates backend configuration and fails fast on misconfiguration
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD

#### Phase 6: PostgreSQL Backend Implementation
**Goal**: Implement PostgreSQL backend with pgvector for vector search, tsvector for full-text search, and proper async connection pooling
**Depends on**: Phase 5
**Requirements**: PGVEC-01, PGVEC-02, PGVEC-03, PGVEC-04, PGFTS-01, PGFTS-02, PGFTS-03, PGFTS-04, INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05
**Success Criteria** (what must be TRUE):
  1. User can switch to PostgreSQL backend via config change and restart server
  2. Vector similarity search works with cosine, L2, and inner product distance metrics
  3. HNSW index parameters (m, ef_construction) are configurable via YAML
  4. Full-text search uses tsvector with GIN indexes and configurable language
  5. Hybrid retrieval with RRF fusion produces consistent rankings between ChromaDB and PostgreSQL backends
  6. Health endpoint reports PostgreSQL backend status including connection pool metrics
  7. Docker Compose provides local PostgreSQL + pgvector development environment
  8. Server prevents embedding dimension mismatches via startup validation
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD
- [ ] 06-03: TBD

#### Phase 7: Testing & CI Integration
**Goal**: Validate identical behavior across ChromaDB and PostgreSQL backends with contract tests and extend CI to support PostgreSQL testing
**Depends on**: Phase 6
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04, STOR-05
**Success Criteria** (what must be TRUE):
  1. Contract test suite validates identical behavior expectations for ChromaDB and PostgreSQL backends
  2. task before-push passes without PostgreSQL installed (postgres-marked tests skip gracefully)
  3. GitHub Actions CI runs PostgreSQL tests via service container
  4. Load test validates 50 concurrent queries plus background indexing without connection pool exhaustion
  5. Hybrid search produces similar top-5 results across both backends (validated via test)
**Plans**: TBD

Plans:
- [ ] 07-01: TBD
- [ ] 07-02: TBD

#### Phase 8: Plugin & Documentation
**Goal**: Update Claude Code plugin for PostgreSQL configuration and document backend selection, setup, and performance tradeoffs
**Depends on**: Phase 7
**Requirements**: PLUG-01, PLUG-02, PLUG-03, PLUG-04, PLUG-05, PLUG-06, DOCS-01, DOCS-02, DOCS-03
**Success Criteria** (what must be TRUE):
  1. /agent-brain-config command guides user through storage backend selection (ChromaDB vs PostgreSQL)
  2. /agent-brain-setup detects Docker and offers to start PostgreSQL via Docker Compose
  3. Setup assistant agent recognizes PostgreSQL-related errors and suggests fixes
  4. Docker Compose setup guide exists in documentation
  5. Performance tradeoffs guide helps users choose between ChromaDB and PostgreSQL
  6. Plugin version bumped to v5.0.0 with updated metadata
**Plans**: TBD

Plans:
- [ ] 08-01: TBD
- [ ] 08-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 5 → 6 → 7 → 8

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Two-Stage Reranking | v3.0 | 7/7 | Complete | 2026-02-08 |
| 2. Pluggable Providers | v3.0 | 4/4 | Complete | 2026-02-09 |
| 3. Schema-Based GraphRAG | v3.0 | 2/2 | Complete | 2026-02-10 |
| 4. Provider Integration Testing | v3.0 | 2/2 | Complete | 2026-02-10 |
| 5. Storage Abstraction | v5.0 | 0/? | Not started | - |
| 6. PostgreSQL Backend | v5.0 | 0/? | Not started | - |
| 7. Testing & CI | v5.0 | 0/? | Not started | - |
| 8. Plugin & Documentation | v5.0 | 0/? | Not started | - |

## Future Phases

### Phase 9+: AWS Bedrock Provider (Feature 105)

- Bedrock embeddings (Titan, Cohere)
- Bedrock summarization (Claude, Llama, Mistral)

### Phase 10+: Vertex AI Provider (Feature 106)

- Vertex embeddings (textembedding-gecko)
- Vertex summarization (Gemini)

### Future Optimizations

- Embedding cache with content hashing
- File watcher for auto-indexing
- Background incremental updates
- Query caching with LRU
- UDS transport for sub-ms latency

---

## Completed Phases (Legacy Archive)

### Phase 1 (Legacy): Core Document RAG — COMPLETED
Features 001-005: Document ingestion, vector search, REST API, CLI

### Phase 2 (Legacy): BM25 & Hybrid Retrieval — COMPLETED
Feature 100: BM25 keyword search, hybrid retrieval with RRF

### Phase 3 (Legacy): Source Code Ingestion — COMPLETED
Feature 101: AST-aware code ingestion, code summaries

### Phase 3.1-3.6 (Legacy): Extensions — COMPLETED
- 109: Multi-instance architecture
- 110: C# code indexing
- 111: Skill instance discovery
- 112: Agent Brain naming
- 113: GraphRAG integration
- 114: Agent Brain plugin
- 115: Server-side job queue

---
*Roadmap created: 2026-02-07*
*Last updated: 2026-02-10 — v5.0 roadmap created with 4 phases covering 34 requirements*
