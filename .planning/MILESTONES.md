# Milestones

## v10.3 MCP v3 — CLI-via-MCP + Framework Matrix (Shipped: 2026-06-14)

**Phases completed:** 8 phases, 24 plans, 0 tasks

**Key accomplishments:**

- (none recorded)

---

## v10.2 MCP v2 — Subscriptions, HTTP Transport, & Tool Completion (Shipped: 2026-06-03)

**Phases completed:** 6 phases (50-55), 24 plans, ~530 new tests
**Tests:** 1685+ monorepo tests passing
**Coverage:** agent-brain-mcp 91.83% / agent-brain-uds 99% (both above 80% floor)
**Quality gate:** `task before-push` from repo root exit 0 in 162s (the DR-5 closure attestation)

**Key accomplishments:**

1. **TOOL_REGISTRY at exactly 16 tools** (7 v1 + 9 v2) — `explain_result`, `add_documents`, `inject_documents`, `wait_for_job` (async, emits progress), `list_folders`, `remove_folder`, `cache_status`, `clear_cache`, `list_file_types`. Locked by `_tool_matrix.py` SOT shared across Layer 1 (in-process) and Layer 2 (SDK) contract tests with import-time drift guard.
2. **Resource subscriptions** — 3 subscribable URIs (`job://` 1s, `corpus://status` 30s, `corpus://folders` configurable 5s) with policy-defined cadences, `SubscriptionTerminated` auto-cancel on terminal job status, per-session registry, and disconnect cleanup via `run_stdio` try/finally — validated end-to-end against the official MCP SDK.
3. **Streamable HTTP transport** — `agent-brain-mcp --transport http` via `StreamableHTTPSessionManager` + uvicorn; loopback-only enforced at CLI entry + in-process; `PortInUseError(exit_code=2)` for EADDRINUSE; pre-flight `socket.bind` probe because uvicorn 0.32.x swallows OSError as SystemExit(1); explicit `security_settings=loopback_transport_security()` because `StreamableHTTPSessionManager` does not auto-enable like `FastMCP`.
4. **4 URI schemes addressable** via `resources/read` (`chunk://`, `graph-entity://`, `job://`, `file://`) with `resources/templates/list` advertising RFC 6570 templates; `file://` gated by Phase 50 sandbox helpers (hard whitelist, 4 deny reasons, 10 MiB cap).
5. **DR-5 closed** — `agent-brain-mcp` and `agent-brain-uds` folded into root `task before-push` + `task pr-qa-gate` inside the existing `before_push_lock_guard.sh` wrapping (issue #174). Caught a real bug on first run: `agent-brain-uds` `test_smoke.py` was silently broken since 10.1.0 PyPI bump (hardcoded `__version__ == "10.0.7"` — loosened to semver regex).
6. **Two-layer contract test suite** — Layer 1 in-process `fake_httpx_client` + Layer 2 SDK-driven subprocess sharing single SOT — 49 SDK contract tests (32 tool happy+negative + 6 resource + 3 subscription happy-path + 1 disconnect-cleanup + 6 HTTP transport + 1 mount-path).
7. **Real-world SDK API drift discovered and worked around at every phase**: MCP SDK 1.12.x hardcodes `subscribe=False` (`_patched_get_capabilities` wrapper); uvicorn 0.32 swallows `OSError` as `SystemExit(1)` (pre-flight bind probe); `StreamableHTTPSessionManager` does not auto-enable `transport_security` (explicit param); `_MetaInjectingServerSession` exploits Pydantic `extra="allow"` on `Implementation` to carry both transport axes (server build + listen) in `_meta`.

**Archive:** [v10.2-ROADMAP.md](milestones/v10.2-ROADMAP.md) | [v10.2-REQUIREMENTS.md](milestones/v10.2-REQUIREMENTS.md)

---

## v9.5.0 Config Validation & Language Support (Shipped: 2026-03-31)

**Phases completed:** 5 phases, 8 plans, 11 tasks

**Key accomplishments:**

- (none recorded)

---

## v9.3.0 LangExtract + Config Spec (Shipped: 2026-03-22)

**Phases completed:** 2 phases, 2 plans, 0 tasks

**Key accomplishments:**

- (none recorded)

---

## v9.4.0 Documentation Accuracy Audit and Reliability Closure (Shipped: 2026-03-20)

**Phases completed:** 10 phases, 23 plans, 0 tasks

**Key accomplishments:**

- Closed all documentation-audit requirements (18/18) and resolved final gap-closure flow in Phase 40.
- Removed stale `.claude/agent-brain/` path guidance from active setup and architecture docs.
- Stabilized setup UX with policy-island command routing and script-backed install/config checks.
- Added first-class AST+LangExtract wizard option plus automatic API port discovery.
- Landed server reliability/provider updates: state-dir path hardening, Ollama resilience, and Gemini SDK migration.

---

## v3.0 Advanced RAG (Shipped: 2026-02-10)

**Phases completed:** 4 phases, 15 plans, 20 tasks
**Tests:** 505 passing (70% coverage)
**Server LOC:** 12,858 Python | **Test LOC:** 13,171 Python

**Key accomplishments:**

1. Two-stage reranking with SentenceTransformers CrossEncoder + Ollama providers (+3-4% precision)
2. Pluggable provider system — YAML-driven config for embeddings (OpenAI/Ollama/Cohere), summarization (Anthropic/OpenAI/Gemini/Grok/Ollama), and reranking
3. Schema-based GraphRAG with 17 entity types, 8 relationship predicates, and type-filtered queries
4. Dimension mismatch prevention and strict startup validation for provider configs
5. Comprehensive E2E test suites for all providers with graceful API key skipping
6. GitHub Actions CI workflow with matrix strategy for provider testing

**Archive:** [v3.0-ROADMAP.md](milestones/v3.0-ROADMAP.md) | [v3.0-REQUIREMENTS.md](milestones/v3.0-REQUIREMENTS.md)

---

## v6.0 PostgreSQL Backend (Shipped: 2026-02-13)

**Phases completed:** 6 phases (5-10), 12 plans, 18 tasks
**Tests:** 772 passing (74% server / 54% CLI coverage)

**Key accomplishments:**

1. StorageBackendProtocol abstraction with 11 async methods — backend-agnostic services
2. PostgreSQL backend with pgvector for vector search and tsvector for full-text search
3. RRF hybrid fusion producing consistent rankings across ChromaDB and PostgreSQL
4. Docker Compose development environment for pgvector:pg16
5. Contract tests validating identical behavior across backends
6. Plugin commands for PostgreSQL configuration and setup with Docker detection
7. Runtime backend wiring — factory-selected backend drives QueryService and IndexingService
8. Live E2E validation with real PostgreSQL (service-level tests)

**Archive:** [v6.0.4-ROADMAP.md](milestones/v6.0.4-ROADMAP.md) | [v6.0.4-REQUIREMENTS.md](milestones/v6.0.4-REQUIREMENTS.md)

---

## v6.0.4 Plugin & Install Fixes (Shipped: 2026-02-22)

**Phases completed:** 1 phase (11), 1 plan, 3 tasks

**Key accomplishments:**

1. Cleaned 17 stale `.claude/doc-serve/` path references across 8 active documentation files
2. Verified and closed requirements PLUG-07 (port auto-discovery), PLUG-08 (v6.0.3), INFRA-06 (install.sh paths)
3. Quality gate validated: 772 tests passing, 74%/54% coverage, zero regressions

**Archive:** [v6.0.4-ROADMAP.md](milestones/v6.0.4-ROADMAP.md) | [v6.0.4-REQUIREMENTS.md](milestones/v6.0.4-REQUIREMENTS.md)

---

## v7.0 Index Management & Content Pipeline (Shipped: 2026-03-05)

**Phases completed:** 3 phases (12-14), 7 plans
**Tests:** 829 passing (77% server coverage)

**Key accomplishments:**

1. Folder management via CLI/API — list, add, remove indexed folders with chunk counts and last-indexed time
2. File type presets — `--include-type python,docs` shorthand replacing manual glob patterns (11 built-in presets)
3. Content injection pipeline — custom Python scripts and folder-level JSON metadata enrichment during indexing
4. Manifest-based incremental indexing — per-folder SHA-256 manifests, mtime fast-path, only processes changed/new files
5. Chunk eviction — automatic stale chunk removal for deleted/changed files via bulk `delete_by_ids`
6. CLI eviction summary — colored display of added/changed/deleted/unchanged file counts and chunk metrics
7. Force reindex bypass — `--force` flag clears manifest and re-indexes all files from scratch

**Archive:** [v7.0-ROADMAP.md](milestones/v7.0-ROADMAP.md) | [v7.0-REQUIREMENTS.md](milestones/v7.0-REQUIREMENTS.md)

---

## v8.0 Performance & Developer Experience (Shipped: 2026-03-15)

**Phases completed:** 5 phases (15-16, 19, 24-25), 9 plans
**Tests:** 1100+ passing (77% server coverage)

**Key accomplishments:**

1. File watcher with per-folder `watch_mode` (auto/off) and configurable debounce — automatic reindexing on file changes
2. Background incremental updates via job queue with duplicate prevention and source indicator (manual vs auto)
3. Embedding cache with aiosqlite two-layer storage (memory LRU + disk) — zero API cost for unchanged content on reindex
4. Provider fingerprint auto-wipe on embedding model change — prevents dimension mismatches
5. Setup wizard with full config prompts, permissions bootstrap, and helper script (`ab-setup-check.sh`)
6. GraphRAG gate for PostgreSQL backend, BM25/tsvector awareness, cache awareness in wizard
7. Plugin and skill updates for embedding cache management

**Archive:** [v8.0-ROADMAP.md](milestones/v8.0-ROADMAP.md) | [v8.0-REQUIREMENTS.md](milestones/v8.0-REQUIREMENTS.md)

---

## v9.0 Multi-Runtime Support (Shipped: 2026-03-16)

**Phases completed:** 1 phase (multi-runtime converter system)
**Tests:** 1180+ passing

**Key accomplishments:**

1. `RuntimeConverter` protocol with canonical format + multi-runtime translation
2. Plugin parser infrastructure — YAML frontmatter extraction, command/agent/skill/manifest parsing
3. Claude converter (near-identity with path replacement)
4. OpenCode converter (lowercase tool names, boolean tools object, color-to-hex)
5. Gemini converter (semantic tool names, metadata filtering)
6. `install-agent` CLI command with `--agent`, `--project/--global`, `--dry-run`, `--json` options
7. Tool mapping system with per-runtime dictionaries

---

## v9.1.0 Generic Skills-Based Runtime Portability (Shipped: 2026-03-16)

**Phases completed:** 3 phases (26-28), 4 plans
**Tests:** 1180+ passing

**Key accomplishments:**

1. `SkillRuntimeConverter` — generic skill-directory converter for any skill-based runtime
2. Parser extensions for templates and scripts in PluginBundle
3. Codex named adapter with `.codex/skills/agent-brain/` installation
4. AGENTS.md idempotent generation with HTML comment markers
5. `--dir` option for arbitrary skill directory targets
6. All 5 converters (Claude, OpenCode, Gemini, Codex, skill-runtime) tested

---
