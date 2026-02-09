# Agent Brain

## What This Is

Agent Brain is a local-first RAG (Retrieval-Augmented Generation) service that indexes documentation and source code, providing intelligent semantic search via REST API for CLI tools and Claude Code integration. It combines vector search, BM25 keyword search, GraphRAG, and hybrid retrieval strategies for high-quality code and documentation understanding.

## Core Value

**Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships.**

## Requirements

### Validated

- [x] **CORE-01**: Document ingestion (PDF + Markdown) — Phase 1
- [x] **CORE-02**: Context-enriched chunking with Claude summarization — Phase 1
- [x] **CORE-03**: Vector search with ChromaDB + OpenAI embeddings — Phase 1
- [x] **CORE-04**: REST API (/query, /index, /health) — Phase 1
- [x] **CORE-05**: CLI tool (agent-brain) with status, query, index, reset — Phase 1
- [x] **BM25-01**: BM25 keyword search retriever — Phase 2 (Feature 100)
- [x] **BM25-02**: Hybrid retrieval with RRF fusion — Phase 2 (Feature 100)
- [x] **BM25-03**: Retrieval mode selection (vector/bm25/hybrid) — Phase 2 (Feature 100)
- [x] **CODE-01**: AST-aware code ingestion (Python, TypeScript, JavaScript, Java, Go, Rust, C, C++) — Phase 3 (Feature 101)
- [x] **CODE-02**: Code summaries via SummaryExtractor — Phase 3 (Feature 101)
- [x] **CODE-03**: C# language support — Phase 3.2 (Feature 110)
- [x] **MULTI-01**: Per-project server instances with isolation — Phase 3.1 (Feature 109)
- [x] **MULTI-02**: Auto-port allocation — Phase 3.1 (Feature 109)
- [x] **MULTI-03**: Runtime discovery via runtime.json — Phase 3.1 (Feature 109)
- [x] **GRAPH-01**: Knowledge graph extraction (entities + relationships) — Phase 3.5 (Feature 113)
- [x] **GRAPH-02**: Graph-enhanced retrieval mode — Phase 3.5 (Feature 113)
- [x] **GRAPH-03**: Multi-mode query (vector/bm25/graph/hybrid/multi) — Phase 3.5 (Feature 113)
- [x] **PLUGIN-01**: Claude Code plugin with slash commands — Phase 3.6 (Feature 114)
- [x] **PLUGIN-02**: Specialized agents (researcher, indexer) — Phase 3.6 (Feature 114)
- [x] **QUEUE-01**: Server-side job queue with JSONL persistence — Feature 115

### Active

- [ ] **RERANK-01**: Two-stage retrieval with optional reranking — Feature 123
- [ ] **RERANK-02**: Ollama-based reranker (local-first, no API keys) — Feature 123
- [ ] **RERANK-03**: Graceful degradation on reranker failure — Feature 123
- [ ] **PROV-01**: Pluggable embedding providers (OpenAI/Ollama/Cohere) — Feature 103
- [ ] **PROV-02**: Pluggable summarization providers (Anthropic/OpenAI/Gemini/Grok/Ollama) — Feature 103
- [ ] **PROV-03**: YAML-based provider configuration — Feature 103
- [ ] **PROV-04**: Fully offline operation with Ollama — Feature 103
- [ ] **SCHEMA-01**: Domain-specific entity type schema for GraphRAG — Feature 122
- [ ] **SCHEMA-02**: Enhanced relationship predicates (calls, extends, implements) — Feature 122
- [ ] **SCHEMA-03**: Type-filtered graph queries — Feature 122
- [ ] **TEST-01**: E2E test suite per provider — Feature 124
- [ ] **TEST-02**: Provider health check endpoint — Feature 124

### Out of Scope

- **MCP Server**: User prefers Skill + CLI model over MCP — too heavyweight, context-hungry
- **Real-time file watching**: Deferred to future optimization phase
- **Embedding caching**: Deferred to future optimization phase
- **PostgreSQL backend**: Future Phase 6 (Feature 104)
- **AWS Bedrock provider**: Future Phase 7 (Feature 105)
- **Vertex AI provider**: Future Phase 8 (Feature 106)

## Context

**Brownfield Project Migration**: This project was previously managed with GitHub Spec-Driven Development (.speckit/). We're migrating to GSD (Get Shit Done) workflow for better execution tracking.

**Recently Shipped (2026-02)**:
- Feature 113: GraphRAG Integration with triplet extraction (LLM + AST-based)
- Feature 114: Agent Brain Plugin for Claude Code
- Feature 115: Server-side job queue with JSONL persistence

**Technology Stack**:
- Python 3.10+ with Poetry packaging
- FastAPI + Uvicorn server
- ChromaDB vector store
- LlamaIndex for document processing
- OpenAI embeddings + Claude Haiku summarization (default, pluggable)

**Architecture Principles** (from constitution.md):
1. Monorepo Modularity — packages independently testable
2. OpenAPI-First — contracts before code
3. Test-Alongside — tests with implementation
4. Observability — structured logging, health endpoints
5. Simplicity — YAGNI, sensible defaults

## Constraints

- **Local-First**: Must work without cloud dependencies (Ollama support critical)
- **Pre-Push Quality Gate**: `task before-push` MUST pass before any push
- **Test Coverage**: >50% coverage required for CI
- **Package Isolation**: Cross-package deps flow server ← cli/skill (never reverse)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Start reranking with Ollama | Local-first philosophy, no API keys required, already integrated | — Pending |
| Two-stage retrieval optional (off by default) | Graceful degradation, backward compatible | — Pending |
| Skill + CLI over MCP | User preference: simpler, less context overhead | ✓ Good |
| GraphRAG with SimplePropertyGraphStore | Simpler than full Kuzu integration for v1 | ✓ Good |
| JSONL job queue over Redis | Local-first, no external dependencies | ✓ Good |

---
*Last updated: 2026-02-07 after GSD migration*
