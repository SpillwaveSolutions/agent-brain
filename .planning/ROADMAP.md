# Agent Brain Roadmap

**Created:** 2026-02-07
**Core Value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API

## Milestones

- ✅ **v3.0 Advanced RAG** — Phases 1-4 (shipped 2026-02-10)
- ✅ **v6.0 PostgreSQL Backend** — Phases 5-10 (shipped 2026-02-13)
- ✅ **v6.0.4 Plugin & Install Fixes** — Phase 11 (shipped 2026-02-22)

## Phases

<details>
<summary>✅ v3.0 Advanced RAG (Phases 1-4) — SHIPPED 2026-02-10</summary>

- [x] Phase 1: Two-Stage Reranking (7/7 plans) — Feature 123
- [x] Phase 2: Pluggable Providers (4/4 plans) — Feature 103
- [x] Phase 3: Schema-Based GraphRAG (2/2 plans) — Feature 122
- [x] Phase 4: Provider Integration Testing (2/2 plans) — Feature 124

**Full details:** [v3.0-ROADMAP.md](milestones/v3.0-ROADMAP.md)

</details>

<details>
<summary>✅ v6.0 PostgreSQL Backend (Phases 5-10) — SHIPPED 2026-02-13</summary>

- [x] Phase 5: Storage Backend Abstraction Layer (2/2 plans) — 2026-02-10
- [x] Phase 6: PostgreSQL Backend Implementation (3/3 plans) — 2026-02-11
- [x] Phase 7: Testing & CI Integration (2/2 plans) — 2026-02-12
- [x] Phase 8: Plugin & Documentation (2/2 plans) — 2026-02-12
- [x] Phase 9: Runtime Backend Wiring (2/2 plans) — 2026-02-12
- [x] Phase 10: Live PostgreSQL E2E Validation (1/1 plans) — 2026-02-12

**Full details:** [v6.0.4-ROADMAP.md](milestones/v6.0.4-ROADMAP.md)

</details>

<details>
<summary>✅ v6.0.4 Plugin & Install Fixes (Phase 11) — SHIPPED 2026-02-22</summary>

- [x] Phase 11: Plugin Port Discovery & Install Fix (1/1 plans) — 2026-02-22

**Full details:** [v6.0.4-ROADMAP.md](milestones/v6.0.4-ROADMAP.md)

</details>

## Progress

**Execution Order:**
Phases execute in numeric order: 5 → 6 → 7 → 8 → 9 → 10 → 11

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Two-Stage Reranking | v3.0 | 7/7 | Complete | 2026-02-08 |
| 2. Pluggable Providers | v3.0 | 4/4 | Complete | 2026-02-09 |
| 3. Schema-Based GraphRAG | v3.0 | 2/2 | Complete | 2026-02-10 |
| 4. Provider Integration Testing | v3.0 | 2/2 | Complete | 2026-02-10 |
| 5. Storage Abstraction | v6.0 | 2/2 | Complete | 2026-02-10 |
| 6. PostgreSQL Backend | v6.0 | 3/3 | Complete | 2026-02-11 |
| 7. Testing & CI | v6.0 | 2/2 | Complete | 2026-02-12 |
| 8. Plugin & Documentation | v6.0 | 2/2 | Complete | 2026-02-12 |
| 9. Runtime Backend Wiring | v6.0 | 2/2 | Complete | 2026-02-12 |
| 10. Live PostgreSQL E2E Validation | v6.0 | 1/1 | Complete | 2026-02-12 |
| 11. Plugin Port Discovery & Install Fix | v6.0.4 | 1/1 | Complete | 2026-02-22 |

## Future Phases

### Phase 11+: AWS Bedrock Provider (Feature 105)

- Bedrock embeddings (Titan, Cohere)
- Bedrock summarization (Claude, Llama, Mistral)

### Phase 12+: Vertex AI Provider (Feature 106)

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
*Last updated: 2026-02-22 — All milestones complete (v3.0, v6.0, v6.0.4)*
