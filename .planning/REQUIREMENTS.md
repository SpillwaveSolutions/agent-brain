# Agent Brain v8.0 — Performance & Developer Experience Requirements

**Milestone:** v8.0
**Goal:** Improve developer workflow with automatic index maintenance and faster query/indexing through caching and optimized transport.
**Created:** 2026-03-06

## v8.0 Requirements

### Embedding Cache
- [x] **ECACHE-01**: Embedding cache uses content-hash + provider:model fingerprint as cache key to prevent dimension mismatches
- [x] **ECACHE-02**: Embedding cache persists to disk via aiosqlite (survives server restarts)
- [x] **ECACHE-03**: Cache hit/miss metrics visible in `agent-brain status` output
- [x] **ECACHE-04**: Cache automatically invalidates all entries when embedding provider or model changes
- [x] **ECACHE-05**: `agent-brain cache clear` CLI command to manually flush embedding cache
- [x] **ECACHE-06**: Embedding cache integrates transparently into IndexingService and QueryService embed paths

### Query Cache
- [ ] **QCACHE-01**: Query results cached in-memory with configurable TTL (default 5 minutes)
- [ ] **QCACHE-02**: Cache key includes index_generation counter — incremented on every successful reindex
- [ ] **QCACHE-03**: GraphRAG and multi modes excluded from query cache (non-deterministic LLM extraction)
- [ ] **QCACHE-04**: Global cache flush on any reindex job completion
- [ ] **QCACHE-05**: Cache hit/miss metrics visible in `agent-brain status` output
- [ ] **QCACHE-06**: `QUERY_CACHE_TTL` and `QUERY_CACHE_MAX_SIZE` configurable via env vars or YAML

### File Watcher
- [ ] **WATCH-01**: Per-folder `watch_mode` config: `off` (read-only, no watching) or `auto` (watch and auto-reindex)
- [ ] **WATCH-02**: Configurable debounce interval per folder (default 30 seconds)
- [ ] **WATCH-03**: `.git/` directory and common build output directories excluded from watching
- [ ] **WATCH-04**: Git checkout storms (100+ file events) collapsed into single reindex job via debounce
- [ ] **WATCH-05**: Watcher starts as background asyncio task in FastAPI lifespan
- [ ] **WATCH-06**: `agent-brain folders list` shows watch_mode and watcher status per folder
- [ ] **WATCH-07**: `agent-brain folders add ./src --watch auto` sets watch_mode during folder registration

### Background Incremental Updates
- [ ] **BGINC-01**: Watcher-triggered reindex jobs routed through existing job queue (not direct IndexingService call)
- [ ] **BGINC-02**: Duplicate job prevention — no new job queued if one is already pending/running for the same folder
- [ ] **BGINC-03**: Watcher-triggered jobs use `force=False` (leverage ManifestTracker incremental diff)
- [ ] **BGINC-04**: Watcher-triggered jobs visible in `agent-brain jobs` with source indicator (manual vs auto)

### UDS Transport
- [ ] **UDS-01**: Server listens on both TCP and Unix domain socket simultaneously (hybrid mode)
- [ ] **UDS-02**: UDS socket file cleaned up on server start (stale socket from crash) and stop
- [ ] **UDS-03**: UDS socket path stored in runtime.json for CLI auto-discovery
- [ ] **UDS-04**: CLI auto-detects UDS from runtime.json and prefers it over TCP for local connections
- [ ] **UDS-05**: `agent-brain status` shows both TCP and UDS endpoints
- [ ] **UDS-06**: UDS can be disabled via config (`transport.uds_enabled: false`)

### Cross-Cutting
- [ ] **XCUT-01**: All new features have >70% test coverage
- [ ] **XCUT-02**: `task before-push` passes with all new code
- [ ] **XCUT-03**: Plugin skills and commands updated for new CLI features (cache, watch_mode)
- [ ] **XCUT-04**: All new config options documented in env vars reference and YAML config

## Future Requirements

(None deferred from v8.0 scoping)

## Out of Scope

- **Folder-level query cache invalidation**: Only flush queries that touched a specific folder — deferred, global flush for v8.0
- **Embedding cache warm-up from existing index**: Pre-populate cache from stored embeddings — nice-to-have, not v8.0
- **Per-file debounce timers**: One timer per changed file — anti-pattern, per-folder debounce is correct
- **Sub-1s debounce intervals**: Creates watcher thundering herd on git operations
- **Semantic query cache**: Lookup cost exceeds query cost — anti-feature
- **Watching .git/ for branch detection**: Generates noise, not actionable events

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| WATCH-01 | Phase 15 | Pending |
| WATCH-02 | Phase 15 | Pending |
| WATCH-03 | Phase 15 | Pending |
| WATCH-04 | Phase 15 | Pending |
| WATCH-05 | Phase 15 | Pending |
| WATCH-06 | Phase 15 | Pending |
| WATCH-07 | Phase 15 | Pending |
| BGINC-01 | Phase 15 | Pending |
| BGINC-02 | Phase 15 | Pending |
| BGINC-03 | Phase 15 | Pending |
| BGINC-04 | Phase 15 | Pending |
| XCUT-03 | Phase 15 | Pending |
| ECACHE-01 | Phase 16 | Complete |
| ECACHE-02 | Phase 16 | Complete |
| ECACHE-03 | Phase 16 | Complete |
| ECACHE-04 | Phase 16 | Complete |
| ECACHE-05 | Phase 16 | Complete |
| ECACHE-06 | Phase 16 | Complete |
| QCACHE-01 | Phase 17 | Pending |
| QCACHE-02 | Phase 17 | Pending |
| QCACHE-03 | Phase 17 | Pending |
| QCACHE-04 | Phase 17 | Pending |
| QCACHE-05 | Phase 17 | Pending |
| QCACHE-06 | Phase 17 | Pending |
| XCUT-04 | Phase 17 | Pending |
| UDS-01 | Phase 18 | Pending |
| UDS-02 | Phase 18 | Pending |
| UDS-03 | Phase 18 | Pending |
| UDS-04 | Phase 18 | Pending |
| UDS-05 | Phase 18 | Pending |
| UDS-06 | Phase 18 | Pending |
| XCUT-01 | Phase 18 | Pending |
| XCUT-02 | Phase 18 | Pending |
