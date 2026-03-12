# Feature Research

**Domain:** RAG system — Performance & Developer Experience (v8.0)
**Researched:** 2026-03-06
**Confidence:** HIGH (embedding cache, watcher debounce), MEDIUM (query cache invalidation patterns, UDS edge cases)

---

## Scope: v8.0 New Features Only

The following features are already built and excluded from this analysis:
- Manifest-based incremental indexing (SHA-256 + mtime fast-path)
- Chunk eviction for deleted/changed files
- JSONL job queue with async workers
- Folder management (list/add/remove) with file type presets
- Content injection pipeline
- Hybrid search (BM25 + vector + graph + multi modes)
- Per-project server instances with auto-port allocation

This document covers: **embedding cache**, **file watcher with per-folder policies**, **background incremental updates**, **query cache with TTL invalidation**, and **UDS transport**.

---

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Embedding cache persists across restarts | Users expect paid API calls (OpenAI embeddings ~$0.13/1M tokens) to not repeat for unchanged files | MEDIUM | SQLite or diskcache keyed by content hash. Must survive process restarts. |
| File watcher respects folder watch mode | Users who mark a folder read-only expect it to never trigger auto-reindex | LOW | Per-folder config already in v7.0 folder metadata — add `watch_mode: read_only | auto` |
| Watcher debounce consolidates burst changes | Users expect git checkout (100 files) to trigger one reindex job, not 100 | MEDIUM | 30s default debounce with timer reset on each new event per folder group |
| Query cache reduces repeat query latency | "Same query, different second" should return instantly — users notice 200ms vs 2ms | MEDIUM | In-memory LRU with TTL. Invalidate on any index write to the same folder. |
| UDS socket file cleanup on startup | Stale `.sock` file from crashed process must not block new server start | LOW | Delete socket file if exists before bind. Standard POSIX practice. |
| Background updates don't block queries | Users expect search to remain responsive while watcher-triggered reindex runs | LOW | Already have async job queue (JSONL workers). Watcher just enqueues a job. |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Per-folder watch mode (read-only vs auto-reindex) | Lets users watch vendor/node_modules as read-only (browsable) while auto-reindexing their source | MEDIUM | Extends existing folder config. `watch_mode` field in `.agent-brain/folders.json`. |
| Configurable debounce per folder | High-churn test output folders need longer debounce (60s); fast-turnaround source needs shorter (10s) | MEDIUM | Debounce value stored in folder config. Default 30s. Timer per folder, not global. |
| Embedding cache survives provider switch detection | Cache entries keyed by (content_hash, model_name, provider_name) — stale cache never silently used after config change | HIGH | Requires model+provider as part of cache key. Invalidates entire cache on provider change. |
| Query cache invalidation linked to index version | When watcher triggers reindex of folder X, only queries whose results included folder X are invalidated — not the whole cache | HIGH | Requires tracking per-query folder coverage. Simpler fallback: invalidate all on any index write. |
| UDS as default transport for same-host CLI | CLI connects 30-66% faster for every command — makes `agent-brain query` feel instant | LOW | Uvicorn `--uds` flag + httpx `AsyncHTTPTransport(uds=...)`. Fallback to TCP for health checks from remote. |
| Watcher auto-pauses during active indexing | Prevents watcher from queuing duplicate reindex jobs while a reindex is already running | MEDIUM | Check job queue for pending/running index job for same folder before enqueuing. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Watch `.git/` directory for branch changes | Users want auto-reindex on git checkout | `.git/` generates hundreds of internal temp files per operation, triggers constant events even for amend/rebase/stash | Exclude `.git/`, `.git/MERGE_HEAD` etc. by default. Users manually reindex after branch switch or use `agent-brain index --force`. |
| Semantic (embedding-based) query cache | Cache queries where meaning is similar, not just identical strings | Requires embedding every incoming query to compare similarity — doubles latency on cache miss, adds embedding API cost for cache lookup. Cache lookup becomes slower than the query itself. | Exact-match query cache keyed by normalized query string + mode + top_k. Fast O(1) lookup. |
| Real-time watcher with < 1s debounce | Users want "instant" index updates as they type | Editor save events fire 2-4x per save (temp file + final write). Sub-1s debounce causes rapid reindex storms during active coding. Queues fill up. Manifest fast-path helps but disk I/O accumulates. | 30s default debounce. Users who want lower can set it per-folder. Document the tradeoff. |
| Global query cache TTL (e.g., 5 minutes) | Simple to implement | Index can change at any time from watcher. Stale results for 5 minutes after a file change is a terrible developer experience. | Event-driven invalidation: clear cache entries for affected folders when reindex completes. TTL only as safety backstop (e.g., 10 min). |
| Persistent query cache (survives restarts) | Reduce startup warmup time | Index may have changed while server was down. Persisted cache would serve stale results with no way to detect invalidation. | In-memory cache only. Warms up quickly from repeated queries. |
| Recursive sub-folder watch modes | Different debounce for `src/` vs `src/tests/` | Path matching becomes O(n) per event. Complex overlapping patterns cause split-brain. | Folder-level granularity only. Users add separate watched folders with different configs if needed. |
| Watcher over network mounts (NFS/SMB) | Index remote project directories | inotify/kqueue don't work over NFS. Must fall back to polling, which is expensive and unreliable over network. | Document: watcher requires local filesystem. For remote dirs, use manual `agent-brain index`. |

---

## Feature Dependencies

```
[Embedding Cache]
    └── required-by --> [Background Incremental Updates]
                            (cache makes re-embedding changed files cheap enough to run automatically)
    └── enhances --> [File Watcher auto-reindex]
                            (watcher triggers incremental update; cache avoids re-embedding unchanged chunks)

[File Watcher]
    └── requires --> [Per-folder config schema] (already in v7.0 folder metadata)
    └── triggers --> [Background Incremental Update] (enqueues job to existing JSONL queue)
    └── invalidates --> [Query Cache] (on reindex completion, flush affected folder's cached queries)

[Background Incremental Updates]
    └── requires --> [JSONL Job Queue] (already built in v7.0)
    └── requires --> [Manifest Tracking + Chunk Eviction] (already built in v7.0)
    └── requires --> [Embedding Cache] (makes repeated small updates cost-effective)
    └── triggers --> [Query Cache Invalidation] (after successful reindex)

[Query Cache]
    └── invalidated-by --> [Background Incremental Updates] (any successful reindex flushes relevant entries)
    └── invalidated-by --> [Manual index API calls] (POST /index, DELETE /index)
    └── enhances --> [UDS Transport] (fast transport + cache hit = sub-millisecond query response)

[UDS Transport]
    └── requires --> [Socket file lifecycle management] (create, bind, cleanup on startup/shutdown)
    └── enhances --> [Query Cache] (UDS removes network overhead, cache removes compute overhead)
    └── independent-of --> [Embedding Cache, File Watcher, Background Updates]
```

### Dependency Notes

- **Watcher triggers background incremental update**: Watcher is purely an event producer. It calls the existing `POST /index` API (or enqueues directly to the JSONL queue) with `incremental=true`. The existing job queue handles deduplication and worker management.
- **Background update invalidates query cache**: After a reindex job completes successfully, the job worker must signal the query cache to flush entries tied to that folder. Implementation: simple version counter per folder; cache keys include folder version; increment on reindex complete.
- **Embedding cache must precede background updates**: Without a cache, automatic reindexing becomes expensive — every file in the folder would re-embed even if only one changed. Cache makes the incremental update cost proportional to changes, not folder size.
- **UDS is independent**: Can be shipped in any phase without depending on other v8.0 features. Purely a transport optimization.
- **Query cache invalidation depends on reindex completion signal**: The simplest implementation is an in-process event (asyncio Event or a counter in shared state). No external messaging needed since this is a single-process FastAPI server.

---

## MVP Definition

### Launch With (v8.0 Phase 1 — Embedding Cache + UDS)

- [x] Embedding cache — disk-persistent, keyed by (content_hash, model_name, provider_name). Use `diskcache` or SQLite. Estimated 80-95% cache hit rate on subsequent reindexes of unchanged content.
- [x] UDS transport — Uvicorn `--uds` flag, CLI auto-detects and prefers UDS over TCP for local connections. TCP remains available for health checks and remote access.

These two features are independent, low-risk, and deliver immediate measurable value (lower API cost, lower query latency).

### Add After Phase 1 Validation (v8.0 Phase 2 — File Watcher + Background Updates)

- [x] File watcher — `watchdog` library, per-folder `watch_mode` (read_only | auto_reindex), configurable debounce (default 30s)
- [x] Background incremental updates — watcher enqueues to existing JSONL job queue; embedding cache makes this cost-effective
- [x] Watcher exclusions — always exclude `.git/`, `__pycache__/`, `node_modules/`, `*.pyc`, `.DS_Store`

Phase 2 requires Phase 1 (embedding cache) to be in place, or automatic reindexing becomes prohibitively expensive for large projects.

### Add After Phase 2 Validation (v8.0 Phase 3 — Query Cache)

- [x] Query cache with TTL-backed event-driven invalidation — in-memory LRU, keyed by (query, mode, top_k, folder_set), invalidated on reindex complete
- [x] Cache metrics endpoint — hit rate, miss rate, size (add to `/health/status`)

Query cache delivers most value after the watcher is running (frequent background updates make staleness risk real; cache must invalidate correctly or users see wrong results).

### Future Consideration (v9.0+)

- [ ] Semantic query cache — cache by embedding similarity threshold — defer: lookup cost exceeds benefit
- [ ] Persistent query cache — survives restarts — defer: invalidation on restart is hard
- [ ] Watcher over NFS — defer: inotify doesn't work over NFS, would need polling with high cost
- [ ] Per-folder debounce tuning via API — defer: CLI/config file sufficient for v8.0

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Embedding cache | HIGH (direct API cost reduction, faster reindex) | MEDIUM (disk cache + key schema) | P1 |
| UDS transport | MEDIUM (30-66% latency reduction for CLI ops) | LOW (Uvicorn flag + httpx config) | P1 |
| File watcher — core loop | HIGH (zero-effort index maintenance) | MEDIUM (watchdog + debounce timer) | P1 |
| File watcher — per-folder config | MEDIUM (read-only vs auto mode) | LOW (extend existing folder config) | P1 |
| Background incremental updates | HIGH (depends on watcher; makes watcher useful) | LOW (enqueue to existing job queue) | P1 |
| Watcher exclusions (.git, pycache, etc.) | HIGH (without this, watcher is noisy unusable) | LOW (pattern filter in event handler) | P1 |
| Query cache | MEDIUM (repeated queries faster, but users rarely hammer exact same query) | MEDIUM (LRU + invalidation signal) | P2 |
| Query cache invalidation on reindex | HIGH correctness requirement (wrong without it) | MEDIUM (version counter per folder) | P2 |
| Cache metrics in /health/status | LOW (nice to have, not user-facing) | LOW (counters) | P3 |

**Priority key:** P1 = must have for v8.0 launch, P2 = should have (ship in v8.0 if feasible), P3 = nice to have

---

## User Workflow Analysis

### Workflow 1: Developer edits source code continuously

**Scenario:** User runs `agent-brain start` and edits Python files all day.

**Expected behavior:**
1. Watcher detects file save within platform event latency (< 1s on inotify/FSEvents)
2. Debounce timer resets on each new event for that folder
3. After 30s of no changes, reindex job enqueues automatically
4. Worker picks up job, runs manifest diff (mtime fast-path: O(1) per file)
5. Only changed files re-embedded. Embedding cache hits for any file content that reverted.
6. Query cache for that folder invalidated on reindex complete
7. User queries immediately see updated results

**Edge case — editor double-save**: Many editors (vim, JetBrains) write temp file then rename. Two events fire for one logical save. Debounce absorbs the double event. No duplicate jobs.

**Edge case — rapid edit-save cycles**: User in flow state, saving every 10 seconds. Debounce window resets on each save. A single reindex fires 30s after the last save. This is the intended behavior.

### Workflow 2: Git branch switch

**Scenario:** User runs `git checkout feature/new-api` in a watched folder. 150 files change.

**Expected behavior:**
1. 150 events fire in rapid succession (inotify/FSEvents batch)
2. Debounce timer resets on each event
3. After 30s of quiet, one reindex job enqueues
4. Manifest diff identifies all 150 changed files
5. Old chunks evicted, new chunks indexed (embedding cache will miss for all new content — branch switch is a genuine content change)
6. Query cache invalidated

**Edge case — `.git/` events during checkout**: `.git/ORIG_HEAD`, `.git/MERGE_HEAD`, `.git/index` all change during checkout. These are in `.git/` directory, which is always excluded from watcher. No events fire for git internals.

**Edge case — large branch switch (1000 files)**: Debounce still works. One job enqueues. Reindex takes longer but is still a single background operation. Users see no degradation during reindex (job queue + read queries remain unblocked).

### Workflow 3: User marks vendor/ folder as read-only

**Scenario:** User has `/project/vendor/` indexed for reference but doesn't want auto-reindex when dependencies update.

**Expected behavior:**
1. `agent-brain folders add /project/vendor/ --watch-mode=read-only`
2. Watcher observes events in vendor/ but takes no action
3. User can still manually trigger: `agent-brain index /project/vendor/`
4. CLI output on `agent-brain folders list` shows `watch_mode: read_only` for this folder

**Edge case — npm install in vendor/**: Generates hundreds of events. Read-only mode silently ignores all of them. No CPU spike, no accidental reindexing.

### Workflow 4: CLI query performance

**Scenario:** Claude Code skill calls `agent-brain query "how does auth work"` 50 times in a session.

**Expected behavior (with UDS)**:
1. CLI detects `.agent-brain/server.sock` exists and server is running
2. HTTP request routes over UDS instead of TCP loopback
3. Latency: ~2-3 microseconds transport vs ~3.6 microseconds TCP (36% improvement)
4. On cache hit (second identical query): total round-trip < 5ms
5. On cache miss: normal query latency (~50-200ms depending on mode)

**Edge case — socket file exists but server crashed**: UDS connect fails immediately (ECONNREFUSED). CLI falls back to TCP. If TCP also fails, returns clear error "Agent Brain server is not running."

**Edge case — permission mismatch**: Server started by user A, CLI run by user B. UDS file has 0600 or 0660 permissions. Connection refused. CLI should fail with clear error about socket permissions, not an opaque connection error.

### Workflow 5: Embedding cache on reindex

**Scenario:** User runs `agent-brain index /project` daily via cron. Most files unchanged.

**Expected behavior:**
1. Manifest fast-path skips unchanged files (mtime check)
2. For changed files, SHA-256 computed and compared to manifest
3. New content → check embedding cache by (sha256, model, provider)
4. Cache hit → use stored embedding, skip API call
5. Cache miss → call embedding API, store result in cache
6. Net result: only truly new/changed content incurs API cost

**Edge case — provider config change (OpenAI → Ollama)**: Cache key includes provider name. All existing cache entries miss. Full reindex required. This is correct — embeddings from different models are incompatible.

**Edge case — cache grows unboundedly**: Set max cache size (e.g., 2GB or configurable). Use LRU eviction within the cache store. `diskcache` handles this natively.

**Edge case — cache corruption**: Embedding cache entry corrupt (disk issue, partial write). On deserialization error, treat as cache miss and re-embed. Log warning. Never crash on cache failure.

---

## Edge Cases by Feature

### Embedding Cache Edge Cases

| Edge Case | Behavior | Implementation Note |
|-----------|----------|---------------------|
| Provider switch (OpenAI → Ollama) | Full cache miss — all files re-embedded | Cache key must include `provider_name + model_name` |
| Model version change (text-embedding-3-large → text-embedding-3-small) | Full cache miss | Part of cache key |
| Same file content, different paths | Cache hit — content hash matches | Cache keyed by content hash, not path |
| Cache file corruption or partial write | Cache miss + re-embed + log warning | Try/except on cache read, never crash |
| Cache too large (disk space) | LRU eviction of oldest entries | Configure max_size_gb in settings |
| Concurrent writes to same cache entry | Diskcache handles via file locking | Use diskcache library, not hand-rolled |
| File content temporarily matches cache but has wrong dimension | Provider mismatch guard prevents use | Cache key includes model dimension |

### File Watcher Edge Cases

| Edge Case | Behavior | Implementation Note |
|-----------|----------|---------------------|
| `.git/` directory events | Silently ignored | Always-on exclusion pattern in event handler |
| `__pycache__/` and `*.pyc` events | Silently ignored | Default exclusion list, configurable |
| Editor temp files (`*.swp`, `*.tmp`, `~*`) | Silently ignored | Add to default exclusion patterns |
| `node_modules/` events | Silently ignored | Add to default exclusion patterns |
| Folder deleted while watched | Watcher emits DirDeleted event — stop watching, log warning, mark folder as stale in config | Handle watchdog DirDeletedEvent |
| Watcher already running (server restart) | Observer thread re-created; handles re-schedule naturally | watchdog Observer is restartable |
| Symlink in watched directory | watchdog follows symlinks by default — may cause circular watch | Add symlink guard or disable follow_symlinks |
| Read-only filesystem (e.g., mounted ISO) | Events fire but are effectively no-ops if watcher ignores them | Read-only watch_mode handles this |
| OS inotify limit hit (Linux) | watchdog raises OSError — log error, fall back to polling observer | Catch OSError from Observer start, use PollingObserver as fallback |
| Debounce timer during server shutdown | Cancel pending timers on shutdown to prevent post-exit job enqueue | asyncio task cancellation in lifespan cleanup |

### Query Cache Edge Cases

| Edge Case | Behavior | Implementation Note |
|-----------|----------|---------------------|
| Reindex completes while query in flight | Query uses pre-reindex data (snapshot semantics), cache invalidated after query returns | Acceptable: index version is checked at query start |
| Two reindex jobs complete concurrently | Both trigger cache invalidation — fine, invalidation is idempotent | Clear operation is safe to call multiple times |
| Query cache key collision | SHA-256 of (query_text + mode + top_k + sorted_folder_list) — collision probability negligible | Use full string hash, not truncated |
| Top_k change for cached query | Cache miss — different top_k is a different cache key | top_k must be part of cache key |
| Cache memory pressure | LRU evicts least-recently-used entries | Set max_entries or max_bytes limit |
| GraphRAG query (non-deterministic LLM step) | Do NOT cache graph queries — LLM extraction is non-deterministic | Only cache vector/bm25/hybrid/multi modes |
| Reranker enabled/disabled | Different cache key needed — reranker flag changes results | Include reranker_enabled in cache key |

### UDS Transport Edge Cases

| Edge Case | Behavior | Implementation Note |
|-----------|----------|---------------------|
| Stale socket file from crashed server | Delete socket file on startup before bind | `Path(uds_path).unlink(missing_ok=True)` before `uvicorn --uds` |
| Permission denied on socket file | CLI fails with clear "permission denied on socket" error (not generic connection error) | Catch PermissionError specifically, show helpful message |
| macOS vs Linux abstract socket | macOS does not support abstract sockets — must use filesystem path | Always use filesystem path under `.agent-brain/` |
| Socket file in NFS/network directory | Undefined behavior on NFS — socket files may not work | Document: state dir must be on local filesystem |
| Concurrent CLI connections | UDS supports multiple simultaneous connections (it's a stream socket) | No special handling needed |
| CLI run as different user than server | Permission denied — socket file owned by server-starting user | Document: run CLI as same user as server. File mode 0660 allows group. |
| UDS path too long (Linux 104-char limit) | Uvicorn/OS fails to bind | Keep state dir path short, document limit |
| Server binds both UDS and TCP | TCP remains for health checks, remote access, and Docker environments | Bind UDS as primary, keep TCP on port |

---

## Complexity Assessment

| Feature | Complexity | Primary Risk | Mitigation |
|---------|------------|--------------|------------|
| Embedding cache (disk) | MEDIUM | Cache key correctness on provider switch | Include provider+model in key; test with provider switch |
| Embedding cache (in-memory fallback) | LOW | Cache wiped on restart | Document as expected behavior |
| UDS transport | LOW | Stale socket file, path length limits | Unlink on startup; validate path length |
| File watcher — core loop | MEDIUM | inotify watch limit on Linux, kqueue on macOS | PollingObserver fallback; document OS limits |
| File watcher — debounce | MEDIUM | Timer management across many folders | Per-folder timer dict; cancel on shutdown |
| File watcher — exclusions | LOW | Missing common patterns (IDE files) | Comprehensive default exclusion list |
| File watcher — per-folder mode | LOW | Extend existing folder config schema | Add `watch_mode` field to FolderConfig |
| Background incremental update trigger | LOW | Duplicate jobs for same folder | Check queue for pending job before enqueuing |
| Query cache | MEDIUM | Cache invalidation correctness | Event-driven invalidation on job completion; TTL as backstop |
| Query cache + GraphRAG exclusion | LOW | Non-deterministic LLM results cached | Mode check: skip cache for `graph` and `multi` modes |

---

## Competitor Feature Analysis

| Feature | LlamaIndex | Chroma | LangChain | Agent Brain v8.0 |
|---------|------------|--------|-----------|-----------------|
| Embedding cache | IngestionPipeline cache (node+transform pair keyed, persist to disk) | No built-in | SQLiteCache for LLM, not embeddings | Disk cache keyed by (content_hash, model, provider) |
| File watcher | No built-in | No | No | watchdog + per-folder mode + debounce |
| Background updates | IngestionPipeline run() (manual) | No | No | Automatic via JSONL job queue |
| Query cache | No built-in | No | Partial (LLM response cache) | In-memory LRU with event-driven invalidation |
| UDS transport | No | No | No | Uvicorn --uds + httpx UDS transport |

Agent Brain v8.0 adds automation that none of the component libraries provide out of the box.

---

## Sources

**Embedding Cache:**
- [LlamaIndex IngestionPipeline — Persistent Cache](https://docs.llamaindex.ai/en/stable/module_guides/loading/ingestion_pipeline/)
- [DiskCache: Disk Backed Cache — DiskCache 5.6.1](https://grantjenks.com/docs/diskcache/)
- [How to cache semantic search — Meilisearch](https://www.meilisearch.com/blog/how-to-cache-semantic-search)
- [CPU Optimized Embeddings: Cut RAG Costs in Half (2026)](https://www.huuphan.com/2026/02/cpu-optimized-embeddings-cut-rag-costs.html)

**File Watcher:**
- [watchdog PyPI](https://pypi.org/project/watchdog/)
- [watchdog GitHub — gorakhargosh/watchdog](https://github.com/gorakhargosh/watchdog)
- [Mastering File System Monitoring with Watchdog in Python — DEV Community](https://dev.to/devasservice/mastering-file-system-monitoring-with-watchdog-in-python-483c)
- [Modified files trigger more than one event — watchdog issue #346](https://github.com/gorakhargosh/watchdog/issues/346)
- [WatchdogApp — Jaffle 0.2.4 documentation (debounce-interval)](https://jaffle.readthedocs.io/en/latest/apps/watchdog.html)

**Query Cache / Cache Invalidation:**
- [How to Implement Cache Invalidation in FastAPI — oneuptime](https://oneuptime.com/blog/post/2026-02-02-fastapi-cache-invalidation/view)
- [Zero-Waste Agentic RAG: Designing Caching Architectures — Towards Data Science](https://towardsdatascience.com/zero-waste-agentic-rag-designing-caching-architectures-to-minimize-latency-and-llm-costs-at-scale/)
- [Cache Strategies — FastAPI Boilerplate](https://benavlabs.github.io/FastAPI-boilerplate/user-guide/caching/cache-strategies/)
- [TTL LRU Cache in Python/FastAPI — Medium](https://medium.com/@priyanshu009ch/ttl-lru-cache-in-python-fastapi-2ca2a39258dc)

**UDS Transport:**
- [FastAPI Microservices Communication via Unix Domain Sockets — Python in Plain English](https://python.plainenglish.io/fastapi-microservices-communication-via-unix-domain-sockets-with-docker-34b2ff7e88cf)
- [TCP Loopback vs Unix Domain Socket Performance: 2026 Guide — copyprogramming](https://copyprogramming.com/howto/tcp-loopback-connection-vs-unix-domain-socket-performance)
- [Benchmark TCP/IP, Unix domain socket and Named pipe](https://www.yanxurui.cc/posts/server/2023-11-28-benchmark-tcp-uds-namedpipe/)
- [UNIX Socket Permissions in Linux — linuxvox](https://linuxvox.com/blog/unix-socket-permissions-linux/)
- [Beyond HTTP: Unix Domain Sockets for High-Performance Microservices — Medium](https://medium.com/@sanathshetty444/beyond-http-unleashing-the-power-of-unix-domain-sockets-for-high-performance-microservices-252eee7b96ad)
- [FastAPI + Uvicorn Unix domain socket example — GitHub](https://github.com/realcaptainsolaris/fast_api_unix_domain)

---

*Feature research for: Agent Brain v8.0 Performance & Developer Experience*
*Researched: 2026-03-06*
