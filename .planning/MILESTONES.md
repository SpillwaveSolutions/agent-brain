# Milestones

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

