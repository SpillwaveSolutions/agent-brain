# Agent Brain Roadmap

**Created:** 2026-02-07
**Migrated from:** .speckit/ (GitHub Spec-Driven Development)
**Core Value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API

## Phase Summary

| Phase | Name | Feature | Requirements | Status |
|-------|------|---------|--------------|--------|
| 1 | Two-Stage Reranking | 123 | RERANK-01 to RERANK-05 | **COMPLETE** (7/7 plans) |
| 2 | Pluggable Providers | 103 | PROV-01 to PROV-07 | **COMPLETE** (4/4 plans) |
| 3 | Schema-Based GraphRAG | 122 | SCHEMA-01 to SCHEMA-05 | **COMPLETE** (2/2 plans) |
| 4 | Provider Integration Testing | 124 | TEST-01 to TEST-06 | **COMPLETE** (2/2 plans) |

---

## Phase 1: Two-Stage Reranking

**Feature:** 123
**Goal:** Add optional two-stage retrieval with Ollama-based reranking for +3-4% precision improvement
**Priority:** IMMEDIATE

### Requirements Covered

- RERANK-01: Two-stage retrieval with optional reranking
- RERANK-02: Ollama-based reranker (local-first)
- RERANK-03: Graceful degradation on failure
- RERANK-04: <100ms additional latency
- RERANK-05: Configuration via environment variables

### Architecture

```
Stage 1: Fast Retrieval (BM25 + Vector + Graph, top_k=100)
    |
RRF Fusion -> ~50 candidates
    |
Stage 2: Ollama Reranking (optional, top_k=10)
    |
Final Results
```

### Success Criteria

1. [x] User can enable reranking with `ENABLE_RERANKING=true`
2. [x] Queries use two-stage retrieval when reranking enabled
3. [x] Reranking works with SentenceTransformers CrossEncoder (primary) or Ollama (alternative)
4. [x] System returns stage 1 results if reranker fails (graceful degradation)
5. [x] Reranking adds <100ms latency for 100 candidates (CrossEncoder ~50ms)
6. [x] All existing tests pass (backward compatible) + 55 new tests

### Files to Create

```
agent_brain_server/providers/reranker/
├── __init__.py
├── base.py          # RerankerProvider protocol + BaseRerankerProvider
└── ollama.py        # OllamaRerankerProvider implementation
```

### Files to Modify

| File | Changes |
|------|---------|
| config/settings.py | Add ENABLE_RERANKING, RERANKER_* settings |
| config/provider_config.py | Add RerankerConfig class |
| models/query.py | Add rerank_score, original_rank fields |
| services/query_service.py | Add _rerank_results(), integrate into execute_query() |

### Plans

**Plans:** 7 plans in 4 waves

| Plan | Wave | Status | Objective |
|------|------|--------|-----------|
| [01-01-PLAN.md](.planning/phases/01-two-stage-reranking/01-01-PLAN.md) | 1 | Complete | Add reranking settings and configuration |
| [01-02-PLAN.md](.planning/phases/01-two-stage-reranking/01-02-PLAN.md) | 1 | Complete | Create RerankerProvider protocol and base class |
| [01-03-PLAN.md](.planning/phases/01-two-stage-reranking/01-03-PLAN.md) | 2 | Complete | Implement SentenceTransformerRerankerProvider |
| [01-04-PLAN.md](.planning/phases/01-two-stage-reranking/01-04-PLAN.md) | 2 | Complete | Implement OllamaRerankerProvider |
| [01-05-PLAN.md](.planning/phases/01-two-stage-reranking/01-05-PLAN.md) | 3 | Complete | Integrate reranking into query_service.py |
| [01-06-PLAN.md](.planning/phases/01-two-stage-reranking/01-06-PLAN.md) | 4 | Complete | Add unit and integration tests |
| [01-07-PLAN.md](.planning/phases/01-two-stage-reranking/01-07-PLAN.md) | 4 | Complete | Update documentation |

---

## Phase 2: Pluggable Providers

**Feature:** 103
**Goal:** Configuration-driven model selection for embeddings and summarization
**Priority:** HIGH

### Requirements Covered

- PROV-01 to PROV-07

### Success Criteria

1. [ ] Provider switching via config.yaml only (no code changes)
2. [ ] OpenAI, Ollama, Cohere embeddings work
3. [ ] Anthropic, OpenAI, Gemini, Grok, Ollama summarization work
4. [ ] Fully offline operation with Ollama
5. [ ] API keys read from environment variables
6. [ ] Provider config validated on startup

### Configuration Example

```yaml
embedding:
  provider: ollama
  model: nomic-embed-text
  params:
    base_url: http://localhost:11434

summarization:
  provider: anthropic
  model: claude-haiku-4-5
  params:
    api_key_env: ANTHROPIC_API_KEY
```

### Research Findings

See: `.planning/phases/02-pluggable-providers/02-RESEARCH.md`

**Status:** Most infrastructure exists. Key gaps:
- PROV-07 (dimension mismatch) - NOT implemented
- PROV-06 (strict validation) - Partial, only warns
- PROV-03/04 - Need E2E verification tests

### Plans

**Plans:** 4 plans in 2 waves

| Plan | Wave | Status | Objective |
|------|------|--------|-----------|
| [02-01-PLAN.md](.planning/phases/02-pluggable-providers/02-01-PLAN.md) | 1 | Complete | Dimension mismatch prevention (PROV-07) |
| [02-02-PLAN.md](.planning/phases/02-pluggable-providers/02-02-PLAN.md) | 1 | Complete | Strict startup validation (PROV-06) |
| [02-03-PLAN.md](.planning/phases/02-pluggable-providers/02-03-PLAN.md) | 2 | Complete | Provider switching E2E test (PROV-03) |
| [02-04-PLAN.md](.planning/phases/02-pluggable-providers/02-04-PLAN.md) | 2 | Complete | Ollama offline E2E test (PROV-04) |

---

## Phase 3: Schema-Based GraphRAG

**Feature:** 122
**Goal:** Add domain-specific entity schema for improved code understanding
**Priority:** MEDIUM

### Requirements Covered

- SCHEMA-01: Domain-specific entity types defined (Package, Module, Class, Method, Function, Interface, Enum)
- SCHEMA-02: Documentation entity types defined (DesignDoc, UserDoc, PRD, Runbook, README, APIDoc)
- SCHEMA-03: Enhanced relationship predicates (calls, extends, implements, references, depends_on)
- SCHEMA-04: Entity type filtering in graph queries
- SCHEMA-05: LLM extraction prompts use schema vocabulary

### Entity Type Schema

| Category | Entity Types |
|----------|-------------|
| Code | Package, Module, Class, Method, Function, Interface, Enum |
| Documentation | DesignDoc, UserDoc, PRD, Runbook, README, APIDoc |
| Infrastructure | Service, Endpoint, Database, ConfigFile |

### Relationship Predicates

| Predicate | Description |
|-----------|-------------|
| `calls` | Function/method invocation |
| `extends` | Class inheritance |
| `implements` | Interface implementation |
| `references` | Documentation references code |
| `depends_on` | Package/module dependency |

### Success Criteria

1. [x] Entity types defined as Literal types with runtime validation helpers
2. [x] CodeMetadataExtractor categorizes entities by type (normalize_entity_type)
3. [x] LLM extraction uses schema vocabulary in prompts
4. [x] Graph queries support type filtering (query_by_type)
5. [x] Existing graph functionality preserved (backward compatible)

### Plans

**Plans:** 2 plans in 2 waves

| Plan | Wave | Status | Objective |
|------|------|--------|-----------|
| [03-01-PLAN.md](.planning/phases/03-schema-graphrag/03-01-PLAN.md) | 1 | Complete | Schema definitions + extractor integration (SCHEMA-01/02/03/05) |
| [03-02-PLAN.md](.planning/phases/03-schema-graphrag/03-02-PLAN.md) | 2 | Complete | Type filtering in graph queries (SCHEMA-04) |

---

## Phase 4: Provider Integration Testing

**Feature:** 124
**Goal:** Validate all provider combinations with E2E tests
**Priority:** MEDIUM

### Requirements Covered

- TEST-01: E2E test suite for OpenAI provider
- TEST-02: E2E test suite for Anthropic provider
- TEST-03: E2E test suite for Ollama provider
- TEST-04: E2E test suite for Cohere provider
- TEST-05: Provider health check endpoint (/health/providers)
- TEST-06: Verified provider configuration documentation

### Test Matrix

| Provider | Embeddings | Summarization | Status |
|----------|------------|---------------|--------|
| OpenAI | text-embedding-3-large | gpt-4-mini | Needs E2E |
| Anthropic | — | claude-haiku-4-5 | Needs E2E |
| Ollama | nomic-embed-text | llama3.2 | Working |
| Cohere | embed-english-v3.0 | — | Needs E2E |

### Success Criteria

1. [x] E2E test for each provider
2. [x] Provider health check endpoint
3. [x] Verified configuration documentation
4. [x] All providers pass CI

### Plans

**Plans:** 2 plans in 2 waves

| Plan | Wave | Status | Objective |
|------|------|--------|-----------|
| [04-01-PLAN.md](.planning/phases/04-provider-integration-testing/04-01-PLAN.md) | 1 | Complete | Provider E2E test suites (TEST-01/02/03/04/05) |
| [04-02-PLAN.md](.planning/phases/04-provider-integration-testing/04-02-PLAN.md) | 2 | Complete | CI workflow + configuration documentation (TEST-06) |

---

## Future Phases (v2)

### Phase 5: PostgreSQL/AlloyDB Backend (Feature 104)

- pgvector for similarity search
- tsvector for full-text (replaces BM25)
- JSONB for graph storage
- Migration tool from ChromaDB

### Phase 6: AWS Bedrock Provider (Feature 105)

- Bedrock embeddings (Titan, Cohere)
- Bedrock summarization (Claude, Llama, Mistral)

### Phase 7: Vertex AI Provider (Feature 106)

- Vertex embeddings (textembedding-gecko)
- Vertex summarization (Gemini)

### Future Optimizations

- Embedding cache with content hashing
- File watcher for auto-indexing
- Background incremental updates
- Query caching with LRU
- UDS transport for sub-ms latency

---

## Completed Phases (Archive)

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
*Last updated: 2026-02-10 - Phase 4 COMPLETE (2/2 plans, verified 11/11 must-haves)*
