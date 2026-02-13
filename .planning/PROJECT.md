# Agent Brain

## What This Is

Agent Brain is a local-first RAG (Retrieval-Augmented Generation) service that indexes documentation and source code, providing intelligent semantic search via REST API for CLI tools and Claude Code integration. It combines vector search, BM25 keyword search, GraphRAG with schema-based entity types, two-stage reranking, and hybrid retrieval strategies — all with pluggable provider support for fully offline or cloud-backed operation.

## Core Value

**Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships.**

## Requirements

### Validated

- ✓ **CORE-01**: Document ingestion (PDF + Markdown) — v1.0
- ✓ **CORE-02**: Context-enriched chunking with Claude summarization — v1.0
- ✓ **CORE-03**: Vector search with ChromaDB + OpenAI embeddings — v1.0
- ✓ **CORE-04**: REST API (/query, /index, /health) — v1.0
- ✓ **CORE-05**: CLI tool (agent-brain) with status, query, index, reset — v1.0
- ✓ **BM25-01**: BM25 keyword search retriever — v2.0 (Feature 100)
- ✓ **BM25-02**: Hybrid retrieval with RRF fusion — v2.0 (Feature 100)
- ✓ **BM25-03**: Retrieval mode selection (vector/bm25/hybrid) — v2.0 (Feature 100)
- ✓ **CODE-01**: AST-aware code ingestion (10 languages) — v2.0 (Feature 101)
- ✓ **CODE-02**: Code summaries via SummaryExtractor — v2.0 (Feature 101)
- ✓ **CODE-03**: C# language support — v2.0 (Feature 110)
- ✓ **MULTI-01**: Per-project server instances with isolation — v2.0 (Feature 109)
- ✓ **MULTI-02**: Auto-port allocation — v2.0 (Feature 109)
- ✓ **MULTI-03**: Runtime discovery via runtime.json — v2.0 (Feature 109)
- ✓ **GRAPH-01**: Knowledge graph extraction (entities + relationships) — v2.0 (Feature 113)
- ✓ **GRAPH-02**: Graph-enhanced retrieval mode — v2.0 (Feature 113)
- ✓ **GRAPH-03**: Multi-mode query (vector/bm25/graph/hybrid/multi) — v2.0 (Feature 113)
- ✓ **PLUGIN-01**: Claude Code plugin with slash commands — v2.0 (Feature 114)
- ✓ **PLUGIN-02**: Specialized agents (researcher, indexer) — v2.0 (Feature 114)
- ✓ **QUEUE-01**: Server-side job queue with JSONL persistence — v2.0 (Feature 115)
- ✓ **RERANK-01**: Two-stage retrieval with optional reranking — v3.0 (Feature 123)
- ✓ **RERANK-02**: Ollama-based reranker (local-first, no API keys) — v3.0 (Feature 123)
- ✓ **RERANK-03**: Graceful degradation on reranker failure — v3.0 (Feature 123)
- ✓ **RERANK-04**: Reranking adds <100ms latency for top 100 candidates — v3.0 (Feature 123)
- ✓ **RERANK-05**: Configuration via env vars — v3.0 (Feature 123)
- ✓ **PROV-01**: YAML configuration for embedding providers — v3.0 (Feature 103)
- ✓ **PROV-02**: YAML configuration for summarization providers — v3.0 (Feature 103)
- ✓ **PROV-03**: Provider switching via config only — v3.0 (Feature 103)
- ✓ **PROV-04**: Fully offline operation with Ollama — v3.0 (Feature 103)
- ✓ **PROV-05**: API keys from environment variables — v3.0 (Feature 103)
- ✓ **PROV-06**: Provider config validated on startup — v3.0 (Feature 103)
- ✓ **PROV-07**: Embedding dimension mismatch prevention — v3.0 (Feature 103)
- ✓ **SCHEMA-01**: Domain-specific entity types (17 types across Code/Docs/Infra) — v3.0 (Feature 122)
- ✓ **SCHEMA-02**: Documentation entity types — v3.0 (Feature 122)
- ✓ **SCHEMA-03**: Enhanced relationship predicates (8 predicates) — v3.0 (Feature 122)
- ✓ **SCHEMA-04**: Entity type filtering in graph queries — v3.0 (Feature 122)
- ✓ **SCHEMA-05**: LLM extraction prompts use schema vocabulary — v3.0 (Feature 122)
- ✓ **TEST-01**: E2E test suite for OpenAI provider — v3.0 (Feature 124)
- ✓ **TEST-02**: E2E test suite for Anthropic provider — v3.0 (Feature 124)
- ✓ **TEST-03**: E2E test suite for Ollama provider — v3.0 (Feature 124)
- ✓ **TEST-04**: E2E test suite for Cohere provider — v3.0 (Feature 124)
- ✓ **TEST-05**: Provider health check endpoint — v3.0 (Feature 124)
- ✓ **TEST-06**: Verified provider configuration documentation — v3.0 (Feature 124)

### Active

**Current Milestone: v6.0 PostgreSQL Backend**

**Goal:** Add PostgreSQL as a configurable storage backend with pgvector for vector search and tsvector for full-text search, running alongside ChromaDB as a dual-backend architecture.

**Target features:**
- Storage backend abstraction layer (ChromaDB default, PostgreSQL optional)
- pgvector for vector similarity search
- tsvector for full-text search (replaces BM25 when using PostgreSQL)
- Hybrid retrieval (RRF fusion) works with PostgreSQL backend
- Backend selection via YAML provider config
- Docker Compose for local PostgreSQL + pgvector development setup
- E2E tests for PostgreSQL backend

### Out of Scope

- **MCP Server**: User prefers Skill + CLI model over MCP — too heavyweight, context-hungry
- **Real-time file watching**: Deferred to future optimization phase
- **Embedding caching**: Deferred to future optimization phase
- **Web UI**: CLI-first philosophy — agents are primary consumers
- **Multi-tenancy**: Local-first philosophy — one instance per project
- **AlloyDB-specific features**: Standard PostgreSQL + pgvector for maximum portability
- **ChromaDB-to-PostgreSQL migration tool**: Users re-index from source when switching backends
- **GraphRAG on PostgreSQL**: Stays ChromaDB-only for now, deferred to future milestone
- **Alembic schema migrations**: Manual SQL scripts via Docker Compose for now

## Context

**Current State (v3.0 shipped 2026-02-10):**
- 12,858 LOC server Python + 13,171 LOC tests
- 505 tests passing, 70% coverage
- 7 embedding/summarization/reranking providers supported
- Full GraphRAG with schema-based entity types
- CI with provider matrix testing

**Technology Stack:**
- Python 3.10+ with Poetry packaging
- FastAPI + Uvicorn server
- ChromaDB vector store
- LlamaIndex for document processing
- Pluggable providers: OpenAI, Anthropic, Ollama, Cohere, Gemini, Grok, SentenceTransformers

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
- **Package Isolation**: Cross-package deps flow server <- cli/skill (never reverse)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SentenceTransformers CrossEncoder for reranking | Better accuracy than Ollama, ~50ms latency | ✓ Good |
| Two-stage retrieval optional (off by default) | Graceful degradation, backward compatible | ✓ Good |
| YAML-driven provider config | Single config file, no code changes to switch providers | ✓ Good |
| Dual-layer validation (startup warning + indexing error) | Warns on startup, blocks only when data integrity at risk | ✓ Good |
| Literal types (not Enum) for entity schema | Better for LLM prompts, less verbose, easier to extend | ✓ Good |
| Permissive schema enforcement (log unknown, don't reject) | Enables schema evolution without breaking existing data | ✓ Good |
| Over-fetch 3x then post-filter for type queries | Ensures enough results after filtering without complex query rewriting | ✓ Good |
| Skill + CLI over MCP | User preference: simpler, less context overhead | ✓ Good |
| GraphRAG with SimplePropertyGraphStore | Simpler than full Kuzu integration for v1 | ✓ Good |
| JSONL job queue over Redis | Local-first, no external dependencies | ✓ Good |
| Minimal FastAPI app for health endpoint tests | Avoids ChromaDB initialization in test environment | ✓ Good |
| CI matrix with conditional API key checks | Tests skip gracefully, config tests always run | ✓ Good |

---
*Last updated: 2026-02-12 after v6.0 milestone started*
