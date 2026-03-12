# Project Research Summary

**Project:** Agent Brain v8.0 — Performance & Developer Experience
**Domain:** RAG System — File Watching, Embedding/Query Caching, UDS Transport
**Researched:** 2026-03-06
**Confidence:** HIGH (stack and pitfalls), MEDIUM (dual UDS+TCP transport pattern)

## Executive Summary

Agent Brain v8.0 adds five new capabilities on top of the mature v7.0 RAG system: persistent embedding cache, in-memory query cache with event-driven invalidation, file system watcher with per-folder policies, background incremental indexing, and a hybrid UDS+TCP transport. These features are additive — the existing validated stack (FastAPI, ChromaDB, LlamaIndex, Poetry, Click, asyncio job queue, ManifestTracker) stays intact. The new features integrate through dependency injection at the lifespan layer, not by restructuring existing code.

The recommended approach is to build in four sequenced phases ordered by dependency and blast radius: embedding cache first (because all other features benefit from it), query cache second (independent, high value), file watcher and background incremental third (requires embedding cache to be cost-effective), and UDS transport last (independent but touches server startup code with the widest blast radius). Three new production dependencies are needed: `watchfiles` (already a Uvicorn transitive dep), `aiosqlite` (async SQLite for disk-persistent embedding cache), and `cachetools` (TTLCache + LRUCache primitives). The `types-cachetools` stub must accompany cachetools for mypy strict mode.

The highest-risk elements are cache coherence on provider switch (stale vectors from wrong embedding space cause silent wrong results), the watchdog-to-asyncio thread boundary (calling async from a watchdog handler crashes at runtime but passes unit tests), and query cache staleness (TTL-only invalidation serves wrong results after reindex). All three have clear prevention patterns: include `provider:model` fingerprint in every cache key, use `watchfiles` native `async for` interface to avoid the thread boundary entirely, and include an `index_generation` counter in every query cache key rather than relying on TTL expiry.

---

## Key Findings

### Recommended Stack

The v8.0 stack additions are intentionally minimal. All three new production dependencies are lightweight, async-native, and avoid adding external services. `watchfiles` (Rust-backed, already a Uvicorn transitive dep) is the correct choice for file watching — it exposes a native `async for` interface that eliminates the thread-safety complexity of `watchdog`. `aiosqlite` provides async-native SQLite for the disk-persistent embedding cache — avoiding `diskcache` (last release 2023, sync-only) and Redis (violates local-first design). `cachetools` TTLCache provides in-memory LRU+TTL query cache with standard `asyncio.Lock` for async safety. The CLI requires no new dependencies — `httpx` already in scope gains UDS transport via `httpx.AsyncHTTPTransport(uds=...)`.

**Core technologies (new):**
- `watchfiles ^1.1`: File system watching — Rust-backed via `notify` crate, `awatch()` is a native async generator with built-in debounce; already in Uvicorn's dependency tree
- `aiosqlite ^0.20`: Async SQLite for persistent embedding cache — non-blocking, no external services, cache survives server restarts
- `cachetools ^7.0.3`: LRUCache + TTLCache primitives — pair with `asyncio.Lock` for async safety; `types-cachetools` required for mypy strict mode
- `httpx ^0.27` (existing): CLI UDS transport client — `AsyncHTTPTransport(uds=...)` for same-host low-latency connections

**What NOT to use:**
- `watchdog`: Requires threading bridge for asyncio; watchfiles is the better choice and already a transitive dep
- `diskcache`: Unmaintained (2023), sync-only, would require `run_in_executor` wrapping
- Redis: Adds external service dependency; violates local-first philosophy
- Dual lifespan on both Uvicorn servers: Must set `lifespan="off"` on UDS server or all services double-initialize against same storage paths causing corruption

### Expected Features

The v8.0 feature set is divided into three launch tiers based on dependency and validation needs.

**Must have (table stakes — P1 for v8.0):**
- Embedding cache persisting across restarts — users expect OpenAI API calls not to repeat for unchanged files; 80-95% cache hit rate on subsequent reindexes
- File watcher respecting folder watch mode — users who mark a folder `read_only` expect zero auto-reindex
- Watcher debounce consolidating burst changes (default 30s) — git checkout of 150 files must trigger one reindex job, not 150
- Background updates that do not block queries — watcher enqueues to existing JSONL job queue; queries remain unblocked
- UDS socket cleanup on startup — stale `.sock` from crashed process must not block restart
- Watcher default exclusions: `.git/`, `__pycache__/`, `node_modules/`, `*.pyc`, `.DS_Store`

**Should have (competitive differentiators — P2):**
- Query cache with event-driven invalidation — repeat identical queries return sub-millisecond; invalidated immediately on reindex completion
- Per-folder configurable debounce — high-churn test-output folders need 60s; fast-turnaround source needs 10s
- Embedding cache keyed by `(content_hash, provider_name, model_name)` — silently invalidated on provider switch; no dimension mismatch
- UDS as default transport for same-host CLI — 30-66% latency reduction per CLI call
- Watcher auto-pause when same folder's job already PENDING or RUNNING

**Defer to v9.0+:**
- Semantic (embedding-similarity) query cache — lookup cost exceeds benefit; doubles latency on cache miss
- Persistent query cache surviving restarts — invalidation on restart is unsolvable without external state
- Sub-1s debounce — causes reindex storms during active editing
- Watcher over NFS/SMB — inotify/kqueue do not work over network mounts

**Anti-features (commonly requested, do not build):**
- Watching `.git/` for branch change auto-reindex — hundreds of temp file events per operation
- Global TTL-only query cache — 5 minutes of stale results after reindex is unacceptable for local dev tooling
- Real-time watcher with less than 1s debounce — editor save events fire 2-4x per save; sub-1s causes rapid reindex storms

### Architecture Approach

v8.0 follows a strict injection-first pattern: all new services (`EmbeddingCache`, `QueryCache`, `FileWatcherService`) are created in the FastAPI lifespan handler and injected into existing services via optional constructor parameters (`None` default). No global cache state. Tests pass `None` (no mock needed). Production passes real instances. The existing service layer is modified at two narrow points: `EmbeddingGenerator.embed_texts()` gains a cache bypass check, and `JobWorker._process_job()` gains a `query_cache.invalidate_all()` call on job DONE. Everything else (routers, storage backends, manifest tracker, job queue) remains unchanged.

The dual UDS+TCP transport requires two `uvicorn.Server` instances sharing the same FastAPI `app` object via `asyncio.gather()`. The TCP server runs `lifespan="on"` (initializes `app.state`); the UDS server runs `lifespan="off"` (reads `app.state` without re-initializing). A custom `_NoSignalServer` subclass suppresses duplicate signal handler registration on the UDS server.

**Major components:**
1. `EmbeddingCache` (new, `services/embedding_cache.py`) — SHA-256 keyed LRU in-memory + optional aiosqlite disk persistence; injected into `EmbeddingGenerator`
2. `QueryCache` (new, `services/query_cache.py`) — TTLCache keyed by `(index_generation, query, mode, top_k, ...)`; injected into `QueryService` and `JobWorker`
3. `FileWatcherService` (new, `services/file_watcher_service.py`) — watchfiles `awatch()` async generator with per-folder debounce; enqueues to `JobQueueService`
4. `FolderRecord` (modify, `services/folder_manager.py`) — extend Pydantic model with `watch_enabled: bool = False` and `watch_debounce_seconds: int = 30`; backward-compatible via `data.get(key, default)` deserialization
5. Dual Uvicorn transport (modify, `api/main.py`) — `asyncio.gather(tcp_server.serve(), uds_server.serve())`; UDS path written to `runtime.json` for CLI discovery

**Data flow (file change to fresh query result):**
```
File modified
  -> watchfiles awatch() -> debounce 30s -> FileWatcherService._consume_events()
  -> job_service.enqueue(force=False) -> JobWorker._process_job()
  -> ManifestTracker mtime fast-path (95% unchanged files skipped)
  -> EmbeddingGenerator.embed_texts()
     -> EmbeddingCache: hit = 0 API calls; miss = provider call + cache.put()
  -> StorageBackendProtocol.upsert_documents() -> ManifestTracker.save()
  -> job DONE -> query_cache.invalidate_all()
  -> Next query: QueryCache miss -> fresh storage lookup
```

### Critical Pitfalls

1. **Cache incoherence on embedding provider/model change** — avoid by including `provider_name:model_name` fingerprint in every cache key from day one; detect config change on startup via sentinel key in cache; wipe entire cache on namespace mismatch. Silent wrong results with no error is the failure mode when omitted.

2. **Thundering herd on git checkout (per-file debounce)** — avoid by debouncing at folder granularity, not file granularity. A single timer per watched folder; any event in the folder resets the same timer. 500 file events must produce exactly 1 job. Also check for PENDING job on same folder before enqueuing.

3. **Watchdog/watchfiles thread boundary violation** — using `watchfiles awatch()` eliminates this entirely by providing a native `async for` interface. If `watchdog` is ever used instead, all event handling must cross the thread boundary via `loop.call_soon_threadsafe()` only. Calling `await` or `asyncio.create_task()` directly from a watchdog handler causes `RuntimeError: no running event loop` at runtime but passes in single-threaded unit tests.

4. **UDS socket stale after crash** — avoid by calling `Path(sock_path).unlink(missing_ok=True)` before every bind. The OS does not clean up Unix domain socket files on process death. Add integration test: `kill -9` then restart must succeed without manual cleanup.

5. **Query cache staleness after reindex (TTL-only)** — avoid by including `index_generation` (monotonically incrementing counter) in every cache key. Increment only on successful job completion, not on job start. TTL is the fallback safety net only. Without this, users see stale search results for minutes after explicit reindex.

**Additional pitfalls (moderate severity):**
- Debounce timer handle leak when folder is removed mid-debounce — cancel pending handle in `remove_folder_watcher()` before stopping the watcher
- Embedding cache disk corruption on crash — use atomic temp+rename writes (already established pattern in `ManifestTracker`); wrap startup cache load in try/except that clears and continues without blocking startup
- Query cache memory OOM from unbounded size — implement size-aware eviction with byte tracking; 64 MB ceiling for query cache, 256 MB for embedding cache as conservative developer-laptop defaults
- Per-folder watcher config schema drift — extend `FolderRecord` Pydantic model with typed fields; never store watcher config in freeform `extra` dict
- Double lifespan on both Uvicorn servers — must set `lifespan="off"` on UDS server; both servers share the same `app` object so TCP lifespan initializes `app.state` once

---

## Implications for Roadmap

Based on research, suggested phase structure with explicit dependency ordering:

### Phase 1: Embedding Cache

**Rationale:** Independent of all other v8.0 features. Delivers immediate, measurable API cost reduction for every existing reindex workflow. All subsequent phases (especially file watcher + background incremental) depend on this being in place to be cost-effective — without the embedding cache, automatic reindexing re-embeds all chunks on every file change. Build this first, validate it works, then add the automation that benefits from it.

**Delivers:** Persistent SHA-256 keyed embedding cache (`aiosqlite` backend); LRU in-memory layer; cache integrated into `EmbeddingGenerator.embed_texts()`; provider/model fingerprint in cache key; atomic write pattern (temp+rename); corrupt-cache recovery on startup; cache size settings in `config/settings.py`

**Features addressed (from FEATURES.md):**
- Embedding cache persists across restarts (P1 table stakes)
- Provider-switch cache invalidation (P1 correctness requirement)

**Pitfalls to prevent (from PITFALLS.md):**
- Cache incoherence on provider change (include `provider:model` in key from day one — Pitfall 1)
- Cache disk corruption on crash (atomic writes + startup recovery — Pitfall 8)
- Unbounded cache size (configure max bytes on construction — Pitfall 9 pattern)

**Research flag:** Standard patterns — well-documented aiosqlite + SHA-256 hash pattern. Skip `research-phase`.

---

### Phase 2: Query Cache

**Rationale:** Independent of phases 3 and 4. High value for repeat-query workflows (Claude Code skill calls same queries dozens of times per session). Must be built with `index_generation` counter from day one — retrofitting cache key schema after the fact is error-prone. The `JobWorker` modification (invalidation on job DONE) is a one-line change. Build this before the watcher so the invalidation hook is in place before automatic reindexing begins.

**Delivers:** In-memory TTLCache for `QueryResponse` objects; `index_generation` counter in cache key; `invalidate_all()` called by `JobWorker` on DONE; GraphRAG/multi mode excluded from cache (non-deterministic LLM step); cache size config; hit/miss counters exposed in `/health/status`

**Features addressed:**
- Query cache reduces repeat query latency (P2 should have)
- Cache metrics in `/health/status` (P3 nice to have)

**Pitfalls to prevent:**
- Query cache staleness after reindex (`index_generation` in key — Pitfall 5)
- Cache memory OOM (size-aware eviction, 64 MB ceiling — Pitfall 9)
- TTL-only invalidation anti-pattern
- Non-deterministic graph/multi modes cached (explicit mode exclusion check)

**Research flag:** Standard patterns — `cachetools.TTLCache` + `asyncio.Lock` is well-documented. Skip `research-phase`.

---

### Phase 3: File Watcher and Background Incremental Updates

**Rationale:** Depends on Phase 1 (embedding cache) being in place — watcher-triggered incremental reindexes would be prohibitively expensive without the embedding cache absorbing unchanged-content hits. The watcher itself is a new component; background incremental updates reuse existing `JobQueueService` + `IndexingService` + `ManifestTracker` without modification. This phase also extends `FolderRecord` with typed watcher config fields — this must be a Pydantic model extension, not an `extra` dict.

**Delivers:** `FileWatcherService` with `watchfiles awatch()` async generator; per-folder `watch_enabled` + `watch_debounce_seconds` in `FolderRecord`; watcher state surfaced in `agent-brain status`; default exclusion patterns (`.git/`, `__pycache__/`, `node_modules/`, editor temp files); backward-compatible v7.0 manifest deserialization; watcher auto-pause when folder job already PENDING; `read_only` watch mode for vendor/dependency folders

**Features addressed:**
- File watcher with per-folder watch mode (P1 must have)
- Configurable debounce per folder (P2 should have)
- Background incremental updates (P1 must have)
- Watcher exclusions (P1 — critical for usability)
- Watcher auto-pause during active indexing (P2 should have)

**Pitfalls to prevent:**
- Thundering herd on git checkout (per-folder debounce, not per-file — Pitfall 2)
- Thread boundary violation (watchfiles native `async for` eliminates the problem — Pitfall 3)
- Debounce timer handle leak on folder removal (cancel timer before stopping watcher — Pitfall 6)
- Config schema drift (extend `FolderRecord` Pydantic model, not `extra` dict — Pitfall 10)
- Manifest lock contention between watcher and manual `--force` (job supersession for PENDING jobs — Pitfall 7)

**Research flag:** Needs brief research during planning. Confirm `watchfiles awatch()` debounce-per-folder pattern with asyncio lifespan shutdown interaction. Verify the asyncio timer cancel-restart approach on `FileWatcherService.stop()`.

---

### Phase 4: UDS Transport

**Rationale:** Independent of phases 1-3. Shipped last because it touches the server startup code (`api/main.py` `run()` function) — the widest blast radius of any v8.0 change. The existing test suite will catch regressions if the TCP-only path is broken. The dual-server pattern has MEDIUM confidence (community-verified, not official Uvicorn docs); this needs careful integration testing before release.

**Delivers:** Dual `uvicorn.Server` instances via `asyncio.gather()` with shared `app` object; `lifespan="off"` on UDS server; `_NoSignalServer` subclass suppressing duplicate signal registration; `uds_path` + `uds_url` written to `runtime.json`; CLI auto-detects and prefers UDS socket from `runtime.json`; graceful fallback to TCP when socket absent or connection refused; stale socket cleanup before bind; UDS socket mode `0o600`

**Features addressed:**
- UDS as default transport for same-host CLI (P1 must have)
- Socket file cleanup on startup (table stakes)
- CLI fallback to TCP on permission/connection error

**Pitfalls to prevent:**
- Stale socket blocking startup after crash (unlink before bind — Pitfall 4)
- Double lifespan initialization corrupting shared state (`lifespan="off"` on UDS server — Architecture anti-pattern 1)
- World-readable socket permissions (set `0o600`)
- Socket path too long (Linux 104-char limit — document and validate)

**Research flag:** Needs validation during planning. Confirm `asyncio.gather(tcp_server.serve(), uds_server.serve())` pattern against the exact Uvicorn version pinned in `pyproject.toml`. Mandatory integration test: `kill -9` server, restart, verify startup success without manual socket cleanup.

---

### Phase Ordering Rationale

- **Embedding cache first:** Every feature that incurs API cost benefits from the cache. Watcher-triggered auto-reindex without a cache would be financially destructive on large codebases. This is the dependency anchor for Phase 3.
- **Query cache second:** Independent of the watcher, but the `JobWorker` invalidation hook should be present before watcher starts generating automatic reindex events. The `index_generation` counter and invalidation path are easier to validate in isolation before the watcher adds concurrency.
- **Watcher third:** Requires embedding cache for cost control. Benefits from query cache invalidation hook already being in place. Most new code; highest feature complexity; the only phase that introduces cross-thread coordination.
- **UDS last:** Highest blast radius (server startup modification). Most MEDIUM-confidence pattern (dual Uvicorn servers). All earlier phases are single-server safe and validate the existing test suite is intact before touching startup.
- **Phases 1-2 and 4 have no cross-dependencies:** If scheduling requires it, Phase 4 can be parallelized with Phases 2-3 since it touches orthogonal code paths (server startup, not service layer).

### Research Flags

**Needs `research-phase` during planning:**
- **Phase 3 (File Watcher):** Confirm `watchfiles awatch()` debounce-per-folder cancel-restart pattern with lifespan shutdown interaction. The asyncio task cancellation path needs explicit testing to ensure pending debounce timers are cancelled cleanly on server shutdown.
- **Phase 4 (UDS Transport):** Validate `asyncio.gather(tcp_server.serve(), uds_server.serve())` pattern against the exact Uvicorn version pinned in `pyproject.toml`. Community gist is MEDIUM confidence; official docs confirm `--uds` is mutually exclusive with `--host/--port` but do not document the two-server pattern directly. TCP startup ordering relative to UDS exposure needs verification.

**Standard patterns (skip `research-phase`):**
- **Phase 1 (Embedding Cache):** `aiosqlite` + SHA-256 is a fully documented, stable pattern. Cache key design is the only non-obvious decision; follow PITFALLS.md Pitfall 1 guidance exactly.
- **Phase 2 (Query Cache):** `cachetools.TTLCache` + `asyncio.Lock` is standard. The `index_generation` counter pattern is the key design insight; implement per PITFALLS.md Pitfall 5.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All three new deps (`watchfiles`, `aiosqlite`, `cachetools`) are stable, well-documented libraries. Alternatives evaluated and eliminated with clear rationale. `watchfiles` already in Uvicorn dep tree. |
| Features | HIGH | Feature priority matrix is clear. Table stakes vs. anti-features distinction is well-reasoned. MVP phasing matches dependency order. Note: FEATURES.md references `watchdog` in its phase descriptions but STACK.md correctly recommends `watchfiles` — roadmap must standardize on `watchfiles`. |
| Architecture | HIGH (phases 1-3) / MEDIUM (phase 4 UDS) | All injection patterns and data flows for phases 1-3 read directly from the codebase. The dual Uvicorn server pattern for Phase 4 is MEDIUM: confirmed working via community sources, not official Uvicorn docs. `lifespan="off"` on the UDS server is the critical invariant. |
| Pitfalls | HIGH | Critical pitfalls cross-referenced with official CPython/asyncio issue trackers, ChromaDB bug reports, and POSIX documentation. The 10 pitfalls with the "Looks Done But Isn't" checklist provide actionable pre-ship verification criteria. |

**Overall confidence:** HIGH for phases 1-3, MEDIUM for phase 4 (UDS transport dual-server pattern).

### Gaps to Address

- **watchfiles vs. watchdog inconsistency:** FEATURES.md phase 2 description references `watchdog` but STACK.md correctly recommends `watchfiles`. All implementation specs must standardize on `watchfiles`. The `watchdog` library should not appear in any new code.

- **Dual UDS+TCP server startup ordering:** The `asyncio.gather(tcp_server.serve(), uds_server.serve())` pattern starts both servers concurrently. If TCP lifespan (which initializes `app.state`) has not completed before the first UDS request arrives, the UDS handler will receive an uninitialized `app.state`. Verify whether Uvicorn's startup sequence guarantees lifespan completion before accepting connections, or add explicit synchronization.

- **SQLite WAL mode for embedding cache:** Under concurrent read/write during indexing, WAL mode (`PRAGMA journal_mode=WAL`) may be needed for aiosqlite. Test with concurrent connections during active indexing before shipping Phase 1.

- **watchfiles as transitive dep verification:** Run `poetry show watchfiles` in `agent-brain-server` before implementing Phase 3 to determine if an explicit pin is needed or if the transitive dep from Uvicorn is sufficient for stability guarantees.

- **Query cache: GraphRAG mode exclusion is mandatory:** The query cache must NOT cache `graph` or `multi` mode results (non-deterministic LLM extraction step). This must appear as an explicit check on `request.mode` in the Phase 2 implementation spec.

- **Cache size constants:** 64 MB for query cache and 256 MB for embedding cache are proposed defaults. These need to be validated against real-world chunk sizes on a medium-scale codebase (10-50K chunks) before being committed as defaults in `settings.py`.

---

## Sources

### Primary (HIGH confidence)

**Stack:**
- [watchfiles PyPI v1.1.1](https://pypi.org/project/watchfiles/) — version, async API, debounce parameter
- [watchfiles helpmanual awatch API](https://watchfiles.helpmanual.io/api/watch/) — debounce parameter (default 1600ms), watch_filter, recursive, force_polling
- [aiosqlite PyPI v0.20](https://pypi.org/project/aiosqlite/) — async SQLite wrapper, Python 3.8+ support
- [cachetools PyPI v7.0.3](https://pypi.org/project/cachetools/) — TTLCache API, thread safety requirement
- [cachetools readthedocs](https://cachetools.readthedocs.io/) — TTLCache(maxsize, ttl), asyncio.Lock pairing requirement
- [Uvicorn Settings](https://www.uvicorn.org/settings/) — `--uds` parameter for UDS binding; mutually exclusive with `--host/--port`
- [HTTPX Transports docs](https://www.python-httpx.org/advanced/transports/) — `httpx.AsyncHTTPTransport(uds=...)` for UDS client connections

**Architecture (codebase read directly — HIGH confidence):**
- `api/main.py`, `services/indexing_service.py`, `services/query_service.py`, `job_queue/job_worker.py`, `services/folder_manager.py`, `services/manifest_tracker.py`, `indexing/embedding.py`, `storage/protocol.py`, `config/settings.py`, `runtime.py`

**Pitfalls:**
- [CPython issue #111246](https://github.com/python/cpython/issues/111246) — UDS socket not removed on process close
- [ChromaDB issue #4368](https://github.com/chroma-core/chroma/issues/4368) — InvalidDimensionException on embedding model switch
- [asyncio Event Loop thread safety docs](https://docs.python.org/3/library/asyncio-eventloop.html) — `call_soon_threadsafe()` requirement

### Secondary (MEDIUM confidence)

- [Multiple uvicorn instances gist](https://gist.github.com/tenuki/ff67f87cba5c4c04fd08d9c800437477) — asyncio.gather() dual TCP+UDS pattern
- [Uvicorn dual-server discussion issue #541](https://github.com/Kludex/uvicorn/issues/541) — community-verified dual server approach
- [watchdog asyncio bridge gist](https://gist.github.com/mivade/f4cb26c282d421a62e8b9a341c7c65f6) — `call_soon_threadsafe()` pattern (for watchdog; watchfiles eliminates this)
- [BullMQ job deduplication docs](https://docs.bullmq.io/guide/jobs/deduplication) — job supersession pattern for debounce

### Tertiary (LOW confidence — validate during implementation)

- `asyncio.gather()` ordering guarantees for dual Uvicorn startup — TCP must fully complete lifespan before UDS begins serving; may need explicit startup sequencing guard beyond what `asyncio.gather()` provides by default

---
*Research completed: 2026-03-06*
*Ready for roadmap: yes*
