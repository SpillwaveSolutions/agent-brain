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

- ✓ **STOR-01**: Storage abstraction protocol (11 methods) — v6.0
- ✓ **STOR-02**: Backend factory with env/YAML/default selection — v6.0
- ✓ **STOR-03**: ChromaDB backend wraps existing vector_store/bm25_manager — v6.0
- ✓ **STOR-04**: Contract tests for backend protocol compliance — v6.0
- ✓ **STOR-05**: Legacy parameter backward compatibility — v6.0
- ✓ **PGVEC-01**: pgvector extension for vector similarity search — v6.0
- ✓ **PGVEC-02**: Cosine, L2, inner product distance metrics — v6.0
- ✓ **PGVEC-03**: HNSW index with configurable m/ef_construction — v6.0
- ✓ **PGVEC-04**: Embedding dimension validation — v6.0
- ✓ **PGFTS-01**: tsvector full-text search with GIN index — v6.0
- ✓ **PGFTS-02**: Weighted relevance (A/B/C) for title/summary/content — v6.0
- ✓ **PGFTS-03**: Configurable language for stemming — v6.0
- ✓ **PGFTS-04**: RRF hybrid fusion for vector + keyword results — v6.0
- ✓ **INFRA-01**: Docker Compose for pgvector:pg16 development setup — v6.0
- ✓ **INFRA-02**: Async connection pooling with SQLAlchemy — v6.0
- ✓ **INFRA-03**: `/health/postgres` endpoint with pool metrics — v6.0
- ✓ **INFRA-04**: Auto schema initialization on backend startup — v6.0
- ✓ **INFRA-05**: Poetry extras for optional PostgreSQL dependencies — v6.0
- ✓ **CONF-01**: YAML storage.backend + storage.postgres configuration — v6.0
- ✓ **CONF-02**: Connection params (host, port, pool size, HNSW) — v6.0
- ✓ **CONF-03**: DATABASE_URL env var override — v6.0
- ✓ **V6TEST-01**: Contract tests with pytest markers + skip-without-DB — v6.0
- ✓ **V6TEST-02**: CI PostgreSQL service container in GitHub Actions — v6.0
- ✓ **V6TEST-03**: Backend wiring smoke tests (mock-based) — v6.0
- ✓ **V6TEST-04**: Service-level PostgreSQL E2E tests — v6.0
- ✓ **PLUG-01**: `/agent-brain-config` command for backend selection — v6.0
- ✓ **PLUG-02**: YAML generation for PostgreSQL config — v6.0
- ✓ **PLUG-03**: `/agent-brain-setup` with Docker detection — v6.0
- ✓ **PLUG-04**: PostgreSQL error pattern recognition in setup agent — v6.0
- ✓ **PLUG-05**: docker-compose.postgres.yml template — v6.0
- ✓ **PLUG-06**: Plugin version bump to v5.0.0 — v6.0
- ✓ **DOCS-01**: PostgreSQL setup guide — v6.0
- ✓ **DOCS-02**: Full configuration reference — v6.0
- ✓ **DOCS-03**: ChromaDB vs PostgreSQL performance tradeoffs guide — v6.0
- ✓ **PLUG-07**: Port auto-discovery for PostgreSQL (5432-5442 range) — v6.0.4
- ✓ **PLUG-08**: Plugin version bumped to v6.0.3 — v6.0.4
- ✓ **INFRA-06**: install.sh REPO_ROOT path corrected (doc-serve to agent-brain) — v6.0.4
- ✓ **FOLD-01..10**: Folder management — list, add, remove indexed folders via CLI/API — v7.0
- ✓ **FTYPE-01..07**: File type presets — `--include-type` shorthand for glob patterns — v7.0
- ✓ **INJECT-01..08**: Content injection pipeline — custom scripts and folder-level JSON metadata — v7.0
- ✓ **EVICT-01..10**: Manifest tracking and chunk eviction — incremental indexing with stale chunk removal — v7.0
- ✓ **XCUT-01..06**: Cross-cutting quality (dual-backend, atomic writes, --help, OpenAPI, >70% coverage, before-push) — v7.0

### Active

## Current Milestone: v8.0 Performance & Developer Experience

**Goal:** Improve developer workflow with automatic index maintenance and faster query/indexing through caching and optimized transport.

**Target features:**
- Embedding cache — avoid re-embedding unchanged content, reduce API calls and latency
- File watcher — per-folder config (read-only vs auto-reindex), configurable debounce (default 30s)
- Background incremental updates — auto-triggered from watcher, seamless index maintenance
- Query cache — cache frequent query results with TTL-based invalidation
- UDS transport — hybrid TCP + Unix domain socket (UDS for local speed, TCP for remote/health)

### Out of Scope

- **MCP Server**: User prefers Skill + CLI model over MCP — too heavyweight, context-hungry
- **Web UI**: CLI-first philosophy — agents are primary consumers
- **Multi-tenancy**: Local-first philosophy — one instance per project
- **AlloyDB-specific features**: Standard PostgreSQL + pgvector for maximum portability
- **ChromaDB-to-PostgreSQL migration tool**: Users re-index from source when switching backends
- **GraphRAG on PostgreSQL**: Stays ChromaDB-only for now, deferred to future milestone
- **Alembic schema migrations**: Manual SQL scripts via Docker Compose for now

## Context

**Current State (v7.0 shipped 2026-03-05):**
- 829 tests passing (77% server coverage)
- Dual-backend architecture: ChromaDB (default) + PostgreSQL (optional)
- Folder management: list, add, remove indexed folders via CLI/API
- File type presets: 11 built-in presets for `--include-type` shorthand
- Content injection: custom Python scripts and folder-level JSON metadata
- Manifest-based incremental indexing: only processes changed/new files
- Chunk eviction: automatic stale chunk removal for deleted/changed files
- 7 embedding/summarization/reranking providers supported
- Full GraphRAG with schema-based entity types (ChromaDB only)

**Technology Stack:**
- Python 3.10+ with Poetry packaging
- FastAPI + Uvicorn server
- ChromaDB vector store (default) + PostgreSQL/pgvector (optional)
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
| StorageBackendProtocol abstraction | Clean separation, contract-testable, dual-backend support | ✓ Good |
| pgvector + tsvector over BM25 for PostgreSQL | Native DB features, no separate index files, better scaling | ✓ Good |
| Async SQLAlchemy for PostgreSQL connections | Non-blocking I/O, connection pooling built-in | ✓ Good |
| RRF fusion for PostgreSQL hybrid search | Same algorithm as ChromaDB, consistent cross-backend behavior | ✓ Good |
| GraphRAG stays ChromaDB-only | Avoids complexity, deferred to future milestone | ✓ Good |
| Conditional ChromaDB init in main.py lifespan | PostgreSQL backend skips ChromaDB setup entirely | ✓ Good |
| Exclude historical files from doc-serve path cleanup | Legacy/planning files document what was true at the time | ✓ Good |
| Structural verification only for Phase 11 requirements | Functional correctness already validated in Phase 10 | ✓ Good |
| Atomic JSONL writes via temp + Path.replace() | POSIX atomic, safe for process crashes during write | ✓ Good |
| Two-step ChromaDB delete (query IDs then delete) | Guards against empty ids=[] collection wipe bug | ✓ Good |
| Hardcode FILE_TYPE_PRESETS in CLI | Avoid cross-package dependency on server | ✓ Good |
| ContentInjector writes only to chunk.metadata.extra | Prevents injectors from overwriting schema fields | ✓ Good |
| ManifestTracker SHA-256 keyed manifest paths | Flat directory, no path-separator issues across OS | ✓ Good |
| mtime fast-path before SHA-256 checksum | O(1) for ~95% of unchanged files | ✓ Good |
| eviction_summary as dict[str, Any] on JobRecord | Pydantic-friendly serialization, no server import in CLI | ✓ Good |

---
*Last updated: 2026-03-06 after v8.0 milestone started*
