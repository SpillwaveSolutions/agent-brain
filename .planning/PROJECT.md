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
- ✓ **VAL-05**: v2 design doc filed at `docs/plans/2026-06-02-mcp-v2-subscriptions.md` — v10.2 (Phase 50)
- ✓ **(prereq for URI-01)**: `GET /query/chunk/{chunk_id}` endpoint with O(1) lookup, ChromaDB + Postgres impls — v10.2 (Phase 50)
- ✓ **(prereq for URI-02)**: `GET /graph/entity/{type}/{id}` endpoint with Kuzu + Simple impls, `#178` SIGSEGV 503 fallback — v10.2 (Phase 50)
- ✓ **(prereq for URI-04)**: `agent_brain_server/security/file_sandbox.py` — hard whitelist policy with 4 deny reasons, 10 MiB cap — v10.2 (Phase 50)
- ✓ **URI-01**: `chunk://<chunk_id>` resource readable via MCP `resources/read` — v10.2 (Phase 51, Plan 02)
- ✓ **URI-02**: `graph-entity://<type>/<id>` resource readable via MCP `resources/read`; 503 `kuzu_unavailable` fallback wired — v10.2 (Phase 51, Plan 02)
- ✓ **URI-03**: `job://<job_id>` resource readable via MCP `resources/read` (foundational dispatcher) — v10.2 (Phase 51, Plan 01)
- ✓ **URI-04**: `file://<abs-path>` resource readable, gated by Phase 50 sandbox helpers (shared, not forked) — v10.2 (Phase 51, Plan 03)
- ✓ **URI-05**: `resources/templates/list` advertises all 4 URI templates as RFC 6570 strings; `MIN_BACKEND_VERSION` bumped to `10.2.0` — v10.2 (Phase 51, Plan 04)
- ✓ **SUB-01**: `job://<job_id>` subscription with 1s polling cadence, auto-cancel on terminal status via `SubscriptionTerminated` sentinel — v10.2 (Phase 52, Plan 03)
- ✓ **SUB-02**: `corpus://status` subscription with 30s polling cadence, `request_id` drop set defeats uvicorn UUID churn — v10.2 (Phase 52, Plan 03)
- ✓ **SUB-03**: `corpus://folders` subscription with configurable 5s active cadence (`mcp_subscription_folders_active_interval_s` setting) — v10.2 (Phase 52, Plan 03)
- ✓ **SUB-04**: `notifications/resources/updated` payload conforms to 2025-03-26 MCP spec; URI-only shape today, `_meta.revision` (64-char hex SHA-256) future-pinned in tests — v10.2 (Phase 52, Plan 04)
- ✓ **SUB-05**: Per-session subscription tracking via `(id(session), uri)` key; cleanup via `run_stdio` try/finally + `cleanup_all()` on EOF; deterministic counter-based e2e test (not psutil) — v10.2 (Phase 52, Plan 04)
- ✓ **HTTP-01**: `agent-brain-mcp --transport http` starts a Streamable HTTP listener via `StreamableHTTPSessionManager` + uvicorn; SDK round-trip drives `streamablehttp_client` and asserts v1 surface symmetry (7 tools / 5 resources / 6 prompts) — v10.2 (Phase 53, Plans 01-03)
- ✓ **HTTP-02**: Loopback-only enforcement {127.0.0.1, localhost, ::1} at CLI entry + in-process; startup banner literal `(loopback only, no auth — do NOT expose this port)`; explicit `security_settings=loopback_transport_security()` because `StreamableHTTPSessionManager` doesn't auto-enable like `FastMCP`; psutil socket-bind verification — v10.2 (Phase 53, Plans 01-03)
- ✓ **HTTP-03**: Explicit selection via `click.Choice`; no silent fallback; `PortInUseError(exit_code=2)` for EADDRINUSE; pre-flight `socket.bind` probe because uvicorn 0.32.x catches OSError as SystemExit(1); CLI hoist of validation precedes `main_async` to avoid BackendUnavailable masking — v10.2 (Phase 53, Plans 01-03)
- ✓ **TOOL-01**: `explain_result` re-runs query with `explain=true` + filters by chunk_id; INVALID_PARAMS when chunk not in top-k; `top_k=50` default per CONTEXT decision F — v10.2 (Phase 54, Plan 02)
- ✓ **TOOL-02**: `add_documents` thin wrapper over `POST /index/add?force=`; #180 `allow_external` deliberately omitted (security guarantee) — v10.2 (Phase 54, Plans 01+03)
- ✓ **TOOL-03**: `inject_documents` wraps `POST /index/` with required injector_script/folder_metadata_file (Pydantic root validator); `Path(...).expanduser().resolve()` matching CLI; tool description names #181 allowlist — v10.2 (Phase 54, Plans 01+03)
- ✓ **TOOL-04**: `wait_for_job` async handler with 1s poll cadence (le=2.0 under MCP spec); `notifications/progress` via `_build_progress_notifier` closure; CancelledError → `cancel_job` cleanup; first `emits_progress=True` ToolSpec; inline poll loop chosen over `SubscriptionManager.start_polling` for request-response shape — v10.2 (Phase 54, Plans 01+04)
- ✓ **TOOL-05**: `list_folders` thin wrapper reusing v1 `client.list_folders()` — v10.2 (Phase 54, Plan 02)
- ✓ **TOOL-06**: `remove_folder` thin wrapper with `confirm: Literal[True]` Pydantic guard; 409 surfaces as BACKEND_CONFLICT (-32000), not INVALID_PARAMS — v10.2 (Phase 54, Plans 01+03)
- ✓ **TOOL-07**: `cache_status` thin wrapper over `GET /index/cache/`; 503-uninitialized surfaces as McpError — v10.2 (Phase 54, Plan 02)
- ✓ **TOOL-08**: `clear_cache` thin wrapper with `confirm: Literal[True]` Pydantic guard — v10.2 (Phase 54, Plans 01+03)
- ✓ **TOOL-09**: `list_file_types` returns vendored `FILE_TYPE_PRESETS` (no HTTP roundtrip); module docstring cites CLI source + Phase 55 parity contract — v10.2 (Phase 54, Plans 01+02)
- ✓ **VAL-01**: 16-tool parameterized contract suite (Layer 1 + Layer 2 share `_tool_matrix.py` SOT with import-time drift guard); 32 SDK assertions over stdio + 6 resource contract assertions — v10.2 (Phase 55, Plan 02)
- ✓ **VAL-02**: Subscription lifecycle E2E (subscribe→notify→unsubscribe for all 3 URIs) + disconnect cleanup via stderr-scrape fallback (debug endpoint absent — issue #194 filed for v10.3+); 4 SDK-driven tests — v10.2 (Phase 55, Plan 03)
- ✓ **VAL-03**: Streamable HTTP contract via `mcp.client.streamable_http.streamablehttp_client` (first repo usage); 6 SDK tests over the real `--transport http` subprocess + free-port allocation; reuses Phase 53's `fake_http_server_module` — v10.2 (Phase 55, Plan 04)
- ✓ **VAL-04**: `agent-brain-mcp` and `agent-brain-uds` folded into root `task before-push` + `task pr-qa-gate` (closes DR-5 from v1 design §14 #5); +60-90s local pre-push cost (162s wall-clock); CHANGELOG `[10.2.0]` entry shipped — v10.2 (Phase 55, Plan 05)
- ✓ **SECURITY-01**: REST API key auth on data routers (`/index`, `/query`, `/graph`, etc.) via `X-API-Key` header + `verify_api_key` FastAPI dep; startup gate refuses non-loopback bind without key (exit 2); `AGENT_BRAIN_API_KEY` propagated CLI → server → MCP backend; `agent-brain init` auto-generates key into `.agent-brain/config.json` (chmod 0o600); 60 new tests — v10.2.1 (issue #179)

## Current Milestone: v10.3 MCP v3 — CLI-via-MCP + Framework Matrix

**Goal:** Make the CLI a reference MCP client and validate the MCP server against the major LLM agent frameworks (OpenAI Agents SDK, LangChain, LlamaIndex, Pydantic AI, Mastra, Vercel AI SDK, Autogen).

**Target features:**
- New `McpStdioBackend` + `McpHttpBackend` in `agent_brain_mcp/client.py` satisfying the same shape as `DocServeClient`
- CLI `--transport mcp` + `--mcp-transport stdio|http` selectors with MCP HTTP server auto-discovery via `mcp.runtime.json`
- CLI commands for prompts (`agent-brain prompt <name>`) and resources (`agent-brain resources list / read`)
- `agent-brain mcp start` helper that launches `agent-brain-mcp --transport http` and writes runtime metadata
- Framework adapter smoke tests against 7 frameworks (4 Python + 2 TypeScript + Autogen) via `task mcp:framework-matrix`
- `docs/INTEGRATIONS.md` one-page-per-framework copy-pasteable configs
- MCP stdio subprocess hygiene: pinned cwd, sanitized env, SIGTERM/SIGKILL escalation, 1000-invocation no-orphan pgrep test

**Source design:** `docs/plans/2026-05-28-mcp-uds-transport-design.md` §11 (v3 row), §15.2. **Issue:** [#187](https://github.com/SpillwaveSolutions/agent-brain/issues/187). **Spec:** `docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md`.

**Open scope question (deferred to `/gsd:discuss-phase`):** Whether to fold v9.6.0 Runtime Parity Phases 47-49 (headless Codex/OpenCode/Gemini execution verification) into v10.3 as a parallel track. The framework matrix work already exercises external CLIs, so the surface overlaps — but it could also be punted to v10.4 or beyond.

### Active

- [ ] **CLI-MCP-01..06**: CLI-via-MCP backend clients, transport selectors, prompts, resources, auto-discovery, helper
- [ ] **FRAME-01..07**: Framework adapter smoke tests (OpenAI Agents, LangChain, LlamaIndex, Pydantic AI, Mastra, Vercel AI SDK, Autogen)
- [ ] **MCPHYG-01**: MCP stdio subprocess hygiene + 1000-invocation orphan test
- [ ] **TOOLING-V3-01**: `task mcp:framework-matrix` opt-in nightly CI gate
- [ ] **DOCS-V3-01**: `docs/INTEGRATIONS.md` framework guide
- [ ] **DESIGN-V3-01**: v3 design doc filed at `docs/plans/<date>-mcp-v3-cli-via-mcp.md`

### Out of Scope

- **OAuth 2.1 for remote MCP**: Deferred to v4 (#188) — depends on v3's `McpHttpBackend` (this milestone)
- **MCP sampling / completion**: Out of scope for v2 (advanced LLM-in-the-server pattern; not required for tool/resource/subscription completeness)
- **MCP plugin auto-registration**: Out of scope for v2 (deferred to a follow-up; requires manifest design)
- **Runtime parity revival for Codex / OpenCode / Gemini (v9.6.0 phases 47–49)**: Deferred — re-evaluate once MCP v3 framework matrix work begins; converter-level + CLI-level tests already cover install behavior structurally
- **Web UI**: CLI-first philosophy — agents are primary consumers
- **Multi-tenancy**: Local-first philosophy — one instance per project
- **AlloyDB-specific features**: Standard PostgreSQL + pgvector for maximum portability
- **ChromaDB-to-PostgreSQL migration tool**: Users re-index from source when switching backends
- **GraphRAG on PostgreSQL**: Stays ChromaDB-only for now, deferred to future milestone
- **Alembic schema migrations**: Manual SQL scripts via Docker Compose for now

## Context

**Current State (v10.2 SHIPPED, 2026-06-03):**
- v10.2 shipped: MCP v2 milestone — 6 phases (50-55), 24 plans, ~530 new tests; agent-brain-mcp at 91.83% coverage, agent-brain-uds at 99%
- Full 16-tool MCP server (7 v1 + 9 v2) with resource subscriptions, Streamable HTTP transport (loopback-only), and 4 addressable URI schemes (`chunk://`, `graph-entity://`, `job://`, `file://`)
- DR-5 from MCP v1 design closed: `agent-brain-mcp` + `agent-brain-uds` folded into root `task before-push` + `task pr-qa-gate` (caught a silently-broken UDS smoke test on the first run that had been broken since 10.1.0)
- Two-layer contract test architecture: in-process `fake_httpx_client` (Layer 1) + SDK-driven subprocess (Layer 2) sharing a single `_tool_matrix.py` source of truth with import-time drift guard
- **Prior state (v9.5.0 SHIPPED, 2026-03-31):** Config Validation & Language Support milestone — 5 phases, 9 plans, 58 commits, +8,693 lines
- `install-agent` already exposes Codex, OpenCode, Gemini, and skill-runtime targets, with converter-level and CLI-level tests covering installation behavior
- Existing end-to-end CLI coverage is Claude-centric; runtime parity for project-local install plus headless execution is not yet verified for Codex, OpenCode, and Gemini
- Repo-local runtime trees are uneven today: `.opencode/plugins/agent-brain/` exists, `.gemini/` is absent, and `.codex/` is used for GSD skills rather than a generated Agent Brain install tree
- Config validate/migrate/diff commands with line numbers, fix suggestions, and wizard integration
- Object Pascal AST-aware ingestion (.pas/.pp/.dpr/.dpk) with function/class extraction
- OpenCode installer reference-quality: singular dirs, agent frontmatter, path rewriting, permission pre-auth
- Reproducible benchmark suite: MODE_SUPPORT_MATRIX, fixed query set, dual timing, baseline BENCHMARKS.md (5-10ms p50)
- Nested storage.postgres.* config validation, pool_timeout tunability
- 4 reliability bug fixes: 120s start timeout, state_dir resolution, ChromaDB telemetry, Gemini migration
- 1392+ tests passing (1001 server + 391 CLI)
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
- **Environment Safety**: Runtime parity tests must install only into repo-owned integration projects — never the user's global Codex, OpenCode, or Gemini directories

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
| Project-local runtime parity installs only | Protect local Codex/OpenCode/Gemini environments from test pollution | — Pending |
| Headless JSON status is the runtime parity contract | Gives one machine-verifiable success signal across runtimes with different UX surfaces | — Pending |
| **v10.2: TOOL_REGISTRY locked at 16 tools via `_tool_matrix.py` SOT** | Single source of truth shared by Layer 1 (in-process) and Layer 2 (SDK) contract tests with import-time drift guard prevents silent tool surface drift | ✓ Good |
| **v10.2: `_MetaInjectingServerSession` exploits Pydantic `extra="allow"`** | Carries both transport axes (server build + listen) in MCP `_meta` without forking the SDK's `Implementation` class | ✓ Good |
| **v10.2: pre-flight `socket.bind` probe before uvicorn handoff** | uvicorn 0.32.x catches `OSError` and calls `sys.exit(1)`, so a port-in-use error must be detected before the handoff to produce a clear error message | ✓ Good |
| **v10.2: synchronous subscription cleanup with `finally` as defense-in-depth** | `asyncio.CancelledError` skips coroutine bodies on pre-await cancellation; sync cleanup in `unsubscribe`/`cleanup_session`/`cleanup_all` is required for correctness | ✓ Good |
| **v10.2: DR-5 closure — fold agent-brain-mcp + agent-brain-uds into root QA gates** | +60-90s local pre-push cost (162s wall-clock) is worth catching silent regressions like the `test_smoke.py` `__version__ == "10.0.7"` assertion that was broken since 10.1.0 | ✓ Good |
| **v10.2: hard whitelist by canonical absolute path for `file://` sandbox** | Symlink resolution at read-time keeps policy current as folders change; 4 deny reasons + 10 MiB cap; no `--no-resolve` escape hatch in v2 (deferred to v3 with auth) | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `$gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `$gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-05 — MILESTONE v10.3 (MCP v3 — CLI-via-MCP + Framework Matrix) STARTED. v10.2 shipped 2026-06-03; v10.2.1 patch in flight for SECURITY-01 (#179 API key auth). v10.3 scope per [#187](https://github.com/SpillwaveSolutions/agent-brain/issues/187): CLI-via-MCP backend clients, framework adapter matrix (7 frameworks), `docs/INTEGRATIONS.md`, MCP stdio subprocess hygiene. Roadmap meta-issue [#189](https://github.com/SpillwaveSolutions/agent-brain/issues/189) sequences v3 → v4 (OAuth 2.1).*
