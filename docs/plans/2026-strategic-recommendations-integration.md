# Agent Brain 2026 Strategic Recommendations Integration Plan

## Overview

This plan integrates the comprehensive 2026 strategic recommendations document into Agent Brain's existing roadmap and planning structure. **The immediate next phase is implementing two-stage reranking.**

## Current State Summary

### Completed Features (Just Shipped)
- **Feature 113**: GraphRAG Integration with triplet extraction (LLM + AST-based)
- **Feature 114**: Agent Brain Plugin for Claude Code
- **Feature 115**: Server-side job queue with JSONL persistence

### Existing Roadmap (from `docs/roadmaps/product-roadmap.md`)
| Phase | Feature | Status |
|-------|---------|--------|
| 5 | Pluggable Providers (103) | NEXT |
| 6 | PostgreSQL/AlloyDB Backend (104) | Future |
| 7 | AWS Bedrock Provider (105) | Future |
| 8 | Vertex AI Provider (106) | Future |

---

## Next Phase: Two-Stage Reranking (Feature 123)

**Priority**: IMMEDIATE - This is the next feature to implement.

**Why Reranking**:
- Mentioned by both user and Armando Padilla as high-value addition
- 2026 research shows +3-4% accuracy improvement with sub-100ms latency
- Builds on existing multi-mode retrieval without breaking changes

---

## Feature 123: Two-Stage Reranking (NEXT PHASE)

### Architecture

```
Stage 1: Fast Retrieval (BM25 + Vector + Graph, top_k=100)
    ↓
RRF Fusion → ~50 candidates
    ↓
Stage 2: Cohere/Jina Reranking (optional, top_k=10)
    ↓
Final Results
```

### Recommended Starting Point: Ollama-Based Reranking

**Why Ollama First**:
1. Already integrated for embeddings and summarization
2. Runs locally - no API keys required
3. Works for clients that prohibit public cloud providers
4. Models like `bge-reranker-v2-m3` or `rerank-lite` available
5. Consistent with project's local-first philosophy

**Ollama Reranker Models**:
- `bge-reranker-v2-m3` - Multilingual, good quality
- `bge-reranker-large` - Higher quality, more resources
- `jina-reranker-v2-base` - Alternative option

### Configuration

```python
# settings.py - New settings
ENABLE_RERANKING: bool = False          # Master switch (off by default)
RERANKER_PROVIDER: str = "ollama"       # "ollama", "cohere", "jina"
RERANKER_MODEL: str = "bge-reranker-v2-m3"  # Ollama model
RERANKER_TOP_K: int = 10                # Final results after reranking
RERANKER_INITIAL_TOP_K: int = 100       # Stage 1 fetch size
OLLAMA_RERANKER_URL: str = "http://localhost:11434"  # Ollama endpoint
```

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
| `config/settings.py` | Add reranking settings |
| `config/provider_config.py` | Add `RerankerConfig` class |
| `models/query.py` | Add `rerank_score`, `original_rank` fields |
| `services/query_service.py` | Add `_rerank_results()` method, integrate into `execute_query()` |

### Implementation Steps

1. **Create reranker provider infrastructure** (base.py)
   - `RerankResult` model
   - `RerankerProvider` protocol
   - `BaseRerankerProvider` abstract class

2. **Implement Ollama reranker** (ollama.py)
   - Uses Ollama's `/api/embed` or custom rerank endpoint
   - Cross-encoder style scoring via chat completions
   - No API keys required - runs locally

3. **Add configuration** (settings.py, provider_config.py)
   - New settings with sensible defaults
   - `RerankerConfig` Pydantic model

4. **Integrate into query flow** (query_service.py)
   - `_rerank_results()` async method
   - Update `execute_query()` to use two-stage when enabled
   - Graceful fallback on reranker failure

5. **Update response models** (query.py)
   - Add reranking metadata fields

6. **Add tests**
   - Unit tests for reranker provider
   - Integration tests for two-stage query flow

### Example Usage

```bash
# Pull reranker model
ollama pull bge-reranker-v2-m3

# Enable reranking (no API key needed!)
export ENABLE_RERANKING=true
export RERANKER_PROVIDER=ollama
export RERANKER_MODEL=bge-reranker-v2-m3

# Query with reranking (transparent to user)
agent-brain query "how does authentication work" --mode hybrid
```

### Graceful Degradation

If reranking fails (API error, timeout, no API key):
- Log warning
- Return original stage 1 results
- No user-facing error

---

## Future Features (After Reranking)

### Feature 122: Schema-Based GraphRAG Enhancement

**Purpose**: Add domain-specific schema for entities to improve code understanding.

**Proposed Entity Types**:
| Category | Entity Types |
|----------|-------------|
| Code | Package, Module, Class, Method, Function, Interface, Enum |
| Documentation | DesignDoc, UserDoc, PRD, Runbook, README, APIDoc |
| Infrastructure | Service, Endpoint, Database, ConfigFile |

**Relationship Types to Add**:
| Predicate | Description |
|-----------|-------------|
| `calls` | Function/method invocation |
| `extends` | Class inheritance |
| `implements` | Interface implementation |
| `references` | Documentation references code |
| `depends_on` | Package/module dependency |

**Implementation Approach**:
1. Define `EntityTypeSchema` Pydantic enum in `models/graph.py`
2. Extend `CodeMetadataExtractor` to categorize entities by type
3. Add schema validation during triplet extraction
4. Update LLM extraction prompt to use schema vocabulary
5. Add filtering by entity type in graph queries

**Files to Modify**:
- `agent_brain_server/models/graph.py` - Add entity type enums
- `agent_brain_server/indexing/graph_extractors.py` - Schema-aware extraction
- `agent_brain_server/indexing/graph_index.py` - Type-filtered queries

### Feature 123: Two-Stage Retrieval with Reranking

**Purpose**: Add optional ColBERTv2-style reranking for precision improvement.

**Architecture**:
```
Stage 1: Fast Retrieval (BM25 + Vector + Graph, top_k=100)
    ↓
RRF Fusion → ~50 candidates
    ↓
Stage 2: ColBERTv2/Jina Reranking (optional, top_k=10)
    ↓
Final Results
```

**Implementation Options** (choose one):
1. **RAGatouille** - Python wrapper for ColBERTv2 (self-hosted)
2. **Jina Reranker API** - Hosted reranking service
3. **Cohere Rerank** - Already have Cohere provider infrastructure

**Configuration**:
```python
# settings.py
ENABLE_RERANKING: bool = False
RERANK_PROVIDER: str = "cohere"  # cohere, jina, colbert
RERANK_MODEL: str = "rerank-v3.5"
RERANK_TOP_K: int = 10
```

**New Files**:
- `agent_brain_server/services/reranking_service.py`
- `agent_brain_server/providers/reranking/` (base, cohere, jina, colbert)

### Feature 124: Provider Integration Testing

**Purpose**: Validate all provider combinations work correctly.

**Test Matrix**:
| Provider | Embeddings | Summarization | Status |
|----------|------------|---------------|--------|
| OpenAI | text-embedding-3-large | gpt-4-mini | Needs test |
| Anthropic | - | claude-haiku-4-5 | Needs test |
| Ollama | nomic-embed-text | llama3.2 | Working |
| Cohere | embed-english-v3.0 | - | Needs test |
| Voyage 4 | voyage-4-large | - | Not implemented |

**Deliverables**:
1. E2E test suite for each provider
2. Provider health check endpoint
3. Documentation updates with verified configurations

---

## Architecture Decisions to Document

### Transport Layer Strategy

**User Preference**: Skill + CLI model over MCP

**Proposed Transports** (in priority order):
1. **HTTP** - Simple, universal compatibility
2. **Unix Domain Socket (UDS)** - Fast local path (planned for Phase 4)
3. **MCP** - Optional ecosystem integration

**Rationale**: MCP perceived as bloated, context-hungry. UDS with Rust CLI provides fast local path without heavyweight protocol.

### Batching Strategy

**Proposal**: CLI-layer request batching

```bash
# Batch multiple queries in single round-trip
agent-brain query-batch \
  "what calls process_payment" \
  "how does authentication work" \
  "where is User defined"
```

**Benefit**: Amortizes connection handshake cost across multiple queries.

---

## Updated Roadmap Proposal

### Phase 5: Pluggable Providers (Feature 103) - CURRENT
- Complete provider abstraction for embeddings + summarization
- Add Voyage 4 provider (14% better than OpenAI)
- Integration tests for all providers

### Phase 5.1: Schema-Based GraphRAG (Feature 122) - NEW
- Domain-specific entity types
- Enhanced relationship predicates
- Type-filtered graph queries

### Phase 5.2: Provider Integration Testing (Feature 124) - NEW
- E2E test suite per provider
- Verified configuration documentation

### Phase 6: PostgreSQL Backend (Feature 104) - EXISTING
- pgvector for similarity search
- tsvector for full-text (replaces BM25)
- JSONB for graph storage
- Migration tool from ChromaDB

### Phase 6.1: Two-Stage Reranking (Feature 123) - NEW
- Optional ColBERTv2/Cohere/Jina reranking
- Sub-100ms additional latency
- +3-4% precision improvement

### Phase 7+: Future Optimizations
- Embedding cache with content hashing (50-80% index speedup)
- File watcher for auto-indexing
- Background incremental updates
- Query caching with LRU

---

## Implementation Sequence

### Immediate (This Sprint)
1. Create Feature 122 spec in `.speckit/features/122-schema-graphrag/`
2. Create Feature 123 spec in `.speckit/features/123-reranking/`
3. Create Feature 124 spec in `.speckit/features/124-provider-testing/`
4. Update `docs/roadmaps/product-roadmap.md` with new phases

### Short-term (Next 2-4 Weeks)
1. Implement Feature 122 (Schema GraphRAG)
2. Add E2E tests for OpenAI/Anthropic providers
3. Document verified provider configurations

### Medium-term (1-2 Months)
1. Implement Feature 123 (Reranking) - start with Cohere (existing infra)
2. Continue PostgreSQL backend spec refinement
3. Begin Rust CLI prototype (UDS transport)

---

## Files to Create/Update

### New Spec Directories
```
.speckit/features/
├── 122-schema-graphrag/
│   ├── spec.md
│   ├── plan.md
│   └── tasks.md
├── 123-reranking/
│   ├── spec.md
│   ├── plan.md
│   └── tasks.md
└── 124-provider-testing/
    ├── spec.md
    ├── plan.md
    └── tasks.md
```

### Roadmap Updates
- `docs/roadmaps/product-roadmap.md` - Add new phases
- `docs/roadmaps/spec-mapping.md` - Add 122-124 mappings

### Strategic Documentation
- `docs/strategic/2026-recommendations.md` - Archive the analysis
- `docs/strategic/architecture-evolution.md` - Target architecture vision

---

## Verification

After implementation:
1. Run `task before-push` to validate all changes
2. Verify new specs have proper structure (spec.md, plan.md, tasks.md)
3. Confirm roadmap reflects accurate priority order
4. Test GraphRAG schema extraction with sample codebase
5. Validate reranking improves top-5 precision

---

## Summary

This plan integrates the 2026 strategic recommendations by:

1. **Implementing two-stage reranking as the immediate next phase** (Feature 123)
   - Start with Ollama (local-first, no API keys)
   - Optional, off by default, graceful degradation
   - Expected +3-4% precision improvement
2. **Schema-based GraphRAG** as follow-on enhancement (Feature 122)
3. **Provider testing** (Feature 124) before PostgreSQL
4. **PostgreSQL backend** (existing Phase 6)
5. **Additional optimizations** (embedding cache, file watcher, etc.)

---

## Next Steps

With this plan documented, the next action is to begin implementing Feature 123 (Two-Stage Reranking) following the implementation steps outlined above.
