# Agent Brain Roadmap

**Created:** 2026-02-07
**Core Value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API

## Milestones

- ✅ **v3.0 Advanced RAG** — Phases 1-4 (shipped 2026-02-10)
- ✅ **v6.0 PostgreSQL Backend** — Phases 5-10 (shipped 2026-02-13)
- ✅ **v6.0.4 Plugin & Install Fixes** — Phase 11 (shipped 2026-02-22)
- ✅ **v7.0 Index Management & Content Pipeline** — Phases 12-14 (shipped 2026-03-05)
- 🚧 **v8.0 Performance & Developer Experience** — Phases 15-18 (in progress)

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

<details>
<summary>✅ v7.0 Index Management & Content Pipeline (Phases 12-14) — SHIPPED 2026-03-05</summary>

- [x] Phase 12: Folder Management & File Type Presets (3/3 plans) — 2026-02-25
- [x] Phase 13: Content Injection Pipeline (2/2 plans) — 2026-03-05
- [x] Phase 14: Manifest Tracking & Chunk Eviction (2/2 plans) — 2026-03-05

</details>

---

## 🚧 v8.0 Performance & Developer Experience (In Progress)

**Milestone Goal:** Improve developer workflow with automatic index maintenance and faster query/indexing through caching and optimized transport.

### Phase 15: File Watcher and Background Incremental Updates

**Goal:** Folders configured with `watch_mode: auto` automatically stay indexed after every file change, without any manual reindex command.

**Depends on:** Phase 14 (ManifestTracker and IndexingService must exist; watcher-triggered jobs leverage incremental diff via force=False)

**Requirements:** WATCH-01, WATCH-02, WATCH-03, WATCH-04, WATCH-05, WATCH-06, WATCH-07, BGINC-01, BGINC-02, BGINC-03, BGINC-04, XCUT-03

**Success Criteria** (what must be TRUE):
1. Running `agent-brain folders add ./src --watch auto` causes the folder to be re-indexed automatically within 30 seconds of any file change
2. A `git checkout` that touches 150 files triggers exactly one reindex job — not 150 separate jobs
3. `agent-brain folders list` shows `watch_mode` (off/auto) and watcher status (watching/idle) per folder
4. `agent-brain jobs` shows watcher-triggered jobs with a `source: auto` indicator distinguishing them from manually triggered jobs
5. Folders marked `watch_mode: off` are never auto-reindexed regardless of file activity
6. Plugin slash commands are updated for `--watch` flag and `watch_mode` display

**Plans:** 2 plans

Plans:
- [x] 15-01-PLAN.md — FileWatcherService + data model extensions (FolderRecord, JobRecord, Settings, lifespan wiring, health endpoint)
- [x] 15-02-PLAN.md — CLI --watch/--debounce flags, folders list watch columns, jobs source column, job worker watcher notification, plugin docs

---

### Phase 16: Embedding Cache

**Goal:** Users pay zero OpenAI API cost for unchanged content on any reindex run triggered by the watcher or manually.

**Depends on:** Phase 15 (File Watcher must be in place — embedding cache provides the cost control that makes automatic watcher-driven reindexing economically viable)

**Requirements:** ECACHE-01, ECACHE-02, ECACHE-03, ECACHE-04, ECACHE-05, ECACHE-06

**Success Criteria** (what must be TRUE):
1. Reindexing a folder for the second time with no file changes makes zero embedding API calls
2. `agent-brain status` shows embedding cache hit rate, total hits, and total misses
3. `agent-brain cache clear` flushes the cache and subsequent reindex incurs full API cost again
4. Switching embedding provider or model (via YAML/env) automatically invalidates all cached embeddings — no dimension mismatch errors
5. Cache survives server restart — a reindex after restart still shows nonzero hit rate for unchanged files

**Plans:** 2/2 plans complete

Plans:
- [x] 16-01-PLAN.md — EmbeddingCacheService (aiosqlite two-layer cache, SHA-256+provider:model:dims key, LRU eviction, provider auto-wipe) + EmbeddingGenerator integration + API endpoints + settings
- [x] 16-02-PLAN.md — CLI `cache` command group (status, clear --yes) + status command cache display + health endpoint embedding_cache section

---

### Phase 17: Query Cache

**Goal:** Repeat queries return results in sub-millisecond with guaranteed freshness after any reindex — including watcher-triggered auto-reindex jobs.

**Depends on:** Phase 15 (watcher generates automatic reindex events that must invalidate cache), Phase 16 (index_generation counter must be established before query cache relies on it for freshness guarantees)

**Requirements:** QCACHE-01, QCACHE-02, QCACHE-03, QCACHE-04, QCACHE-05, QCACHE-06, XCUT-04

**Success Criteria** (what must be TRUE):
1. Running the same query twice in succession (no reindex between) returns the second result from cache with no storage backend call
2. Running a reindex job causes the very next identical query to hit storage (cache is cleared on job completion)
3. `agent-brain status` shows query cache hit rate, total hits, and total misses
4. `graph` and `multi` query modes are never served from cache — each call reaches storage
5. `QUERY_CACHE_TTL` and `QUERY_CACHE_MAX_SIZE` are documented in env vars reference and YAML config reference

**Plans:** TBD

Plans:
- [ ] 17-01: QueryCache service (cachetools TTLCache + asyncio.Lock, index_generation counter, graph/multi exclusion, invalidate_all on job DONE)
- [ ] 17-02: Integration into QueryService + JobWorker; cache hit/miss metrics in /health/status; env var config; config documentation

---

### Phase 18: UDS Transport and Quality Gate

**Goal:** CLI-to-server communication on the same host uses Unix domain sockets for lower latency, and the full v8.0 feature set passes all quality checks.

**Depends on:** Phases 15-17 (all service-layer changes must be complete before touching server startup — widest blast radius)

**Requirements:** UDS-01, UDS-02, UDS-03, UDS-04, UDS-05, UDS-06, XCUT-01, XCUT-02

**Success Criteria** (what must be TRUE):
1. `agent-brain status` shows both TCP endpoint and UDS socket path; CLI connects via UDS automatically when on the same host
2. Killing the server with `kill -9` and restarting it succeeds without manual socket file cleanup
3. Setting `transport.uds_enabled: false` in YAML config causes server to listen on TCP only and CLI falls back to TCP without error
4. All new v8.0 code (file watcher, embedding cache, query cache, UDS transport) has >70% test coverage
5. `task before-push` exits with code 0 with all v8.0 features in place

**Plans:** TBD

Plans:
- [ ] 18-01: Dual Uvicorn server (asyncio.gather TCP+UDS, _NoSignalServer subclass, lifespan="off" on UDS, stale socket cleanup, runtime.json uds_path)
- [ ] 18-02: CLI UDS auto-detection (httpx AsyncHTTPTransport(uds=), runtime.json discovery, TCP fallback); UDS endpoint in status output; quality gate validation

---

### Phase 19: Plugin and skill updates for embedding cache management

**Goal:** Users can manage the embedding cache entirely through the Claude Code plugin without dropping to the terminal -- slash commands, skill guidance, agent awareness, and configuration docs all surface the cache feature.

**Requirements:** XCUT-03

**Depends on:** Phase 16 (embedding cache backend must be complete)

**Plans:** 1/1 plans complete

Plans:
- [ ] 19-01-PLAN.md — Create agent-brain-cache slash command + update help, API reference, skills, agent, and config docs for cache awareness

---

## Progress

**Execution Order:**
Phases execute in numeric order: 15 → 16 → 17 → 18

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
| 12. Folder Management & File Type Presets | v7.0 | 3/3 | Complete | 2026-02-25 |
| 13. Content Injection Pipeline | v7.0 | 2/2 | Complete | 2026-03-05 |
| 14. Manifest Tracking & Chunk Eviction | v7.0 | 2/2 | Complete | 2026-03-05 |
| 15. File Watcher & Background Incremental | v8.0 | 2/2 | Complete | 2026-03-07 |
| 16. Embedding Cache | v8.0 | Complete    | 2026-03-10 | 2026-03-10 |
| 17. Query Cache | v8.0 | 0/2 | Not started | - |
| 18. UDS Transport & Quality Gate | v8.0 | 0/2 | Not started | - |
| 19. Plugin Cache Docs | 1/1 | Complete    | 2026-03-12 | - |

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
*Last updated: 2026-03-12 — Phase 19 planned: 1 plan in 1 wave*
