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

