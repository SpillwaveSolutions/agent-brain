# Pitfalls Research: v8.0 Performance & Developer Experience

**Domain:** RAG System — File Watching, Embedding Cache, Query Cache, UDS Transport
**Researched:** 2026-03-06
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Cache Incoherence on Embedding Provider or Model Change

**What goes wrong:**
The embedding cache keys on content hash (SHA-256 of text), but embeddings from `text-embedding-3-large` are not interchangeable with embeddings from `nomic-embed-text` (Ollama). If the user switches providers in `providers.yaml`, stale cached embeddings are served with wrong vector dimensions or wrong geometric space. ChromaDB raises `InvalidDimensionException` on insert, or worse — inserts silently succeed because both providers happen to share a dimension (e.g., both 1536-dim), but the vector spaces are incompatible. Semantic search returns garbage results with no error signal.

**Why it happens:**
Developers cache on content hash alone — it's cheap and correct for same-provider runs. Provider config is separate from the cache key. Nobody tests "switch provider while cache is warm." The v7.0 provider system already has dimension validation on startup (`PROV-07`), but embedding cache bypasses that path by returning a vector before any provider call happens.

**How to avoid:**
Include provider config fingerprint in the cache key:
```python
import hashlib

def _cache_key(text: str, provider_name: str, model_name: str) -> str:
    config_sig = hashlib.sha256(
        f"{provider_name}:{model_name}".encode()
    ).hexdigest()[:16]
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    return f"{config_sig}:{content_hash}"
```
On startup, read the current provider config and compute a `cache_namespace` string. If it differs from what is stored in the cache metadata, wipe the cache before accepting any reads. Store the namespace as a sentinel key (`__provider_config__`) in the cache on first write.

**Warning signs:**
- `InvalidDimensionException` from ChromaDB after provider config change
- Search quality drops sharply after switching from OpenAI to Ollama with no error
- Cache hit rate is 100% immediately after provider switch (should be 0% on cold namespace)
- Embedding cache size doesn't shrink after `providers.yaml` change

**Phase to address:**
Phase (Embedding Cache) — embed provider + model name into cache key design from day one. Do not add cache key version field later as a patch — it must be in the initial schema.

---

### Pitfall 2: Watcher Thundering Herd on Git Checkout

**What goes wrong:**
A `git checkout main` or `git rebase` on a 500-file project emits hundreds or thousands of `FileModifiedEvent` / `FileCreatedEvent` / `FileDeletedEvent` events within milliseconds. With a naive 30s debounce per folder, all events are batched, which is correct. But if the debounce is per-file rather than per-folder, each of the 500 files schedules its own 30s timer. The timer heap grows to 500 entries. When all timers fire simultaneously, 500 `asyncio.create_task()` calls enqueue 500 index jobs — the job queue absorbs them FIFO and indexes each file individually rather than as a single folder run. This saturates the job queue, re-embeds everything (expensive API calls), and defeats incremental indexing.

**Why it happens:**
Per-file debounce seems natural because the OS reports changes per-file. Developers implement debounce at the event level, not at the folder level. The manifest-based incremental system handles "what changed" correctly, but redundant jobs mean redundant manifest loads/saves and redundant chunk eviction passes.

**How to avoid:**
Debounce at folder granularity, not file granularity. Use a single `asyncio.Handle` per watched folder:
```python
class FolderWatcher:
    _pending_handle: asyncio.TimerHandle | None = None

    def on_event(self, event: FileSystemEvent) -> None:
        # Any event in this folder resets the single folder-level timer
        if self._pending_handle is not None:
            self._pending_handle.cancel()
        loop = asyncio.get_event_loop()
        self._pending_handle = loop.call_later(
            self.debounce_seconds,
            self._schedule_index_job
        )
```
One timer per folder. One job enqueued per debounce window regardless of how many files changed.

Additionally, before enqueuing a new job, check if a job for the same folder is already PENDING or RUNNING in the job queue. If yes, skip enqueuing (the running job will process whatever changed).

**Warning signs:**
- Job queue depth > 1 for the same folder after git operations
- `asyncio` pending handles count grows proportionally to file count watched
- Repeated duplicate job IDs for same folder in quick succession in logs
- API cost spikes on `git rebase` or `git stash pop`

**Phase to address:**
Phase (File Watcher) — require per-folder debounce design in the watcher implementation spec. Add integration test: emit 200 FileCreatedEvent in 100ms, verify exactly 1 job enqueued.

---

### Pitfall 3: Watcher Events Dispatched on Watchdog Thread, Not Event Loop Thread

**What goes wrong:**
`watchdog` calls `on_modified()` / `on_created()` from a background OS thread, not the asyncio event loop. Any `await` call inside a watchdog `EventHandler` crashes with `RuntimeError: no running event loop` or silently schedules work on the wrong loop. Calling `asyncio.create_task()` from outside the loop raises the same error. The handler appears to work in unit tests (single-threaded) but fails at runtime.

**Why it happens:**
Watchdog's `Observer` runs in a dedicated thread. Python asyncio event loops are not thread-safe. Developers unfamiliar with asyncio thread safety write:
```python
class MyHandler(FileSystemEventHandler):
    async def on_modified(self, event):  # WRONG: on_modified cannot be async
        await self._enqueue_job(event)   # RuntimeError at runtime
```

**How to avoid:**
Bridge the thread boundary with `loop.call_soon_threadsafe()`:
```python
class WatcherHandler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop, callback: Callable) -> None:
        self._loop = loop
        self._callback = callback

    def on_modified(self, event: FileSystemEvent) -> None:
        # Always dispatch to the event loop — never await here
        self._loop.call_soon_threadsafe(
            self._callback, event
        )
```
The callback is a synchronous function that manipulates the debounce timer. All async work happens in tasks created within the event loop thread.

Alternatively, use `watchfiles` (the `anyio`-native successor to `watchdog`) which handles the thread bridge internally and exposes an `async for` interface.

**Warning signs:**
- `RuntimeError: no running event loop` in watchdog handler logs
- File events logged but no jobs enqueued
- Works in `pytest` but fails in running server
- Intermittent missing events under load

**Phase to address:**
Phase (File Watcher) — explicitly document thread-safety requirement in watcher component design. Unit test the thread bridge in isolation before wiring to job queue.

---

### Pitfall 4: UDS Socket File Survives Crash, Blocks Next Startup

**What goes wrong:**
When Agent Brain crashes (OOM kill, `kill -9`, power loss), the Unix Domain Socket file at e.g. `~/.claude/agent-brain/<project>/agent-brain.sock` is NOT automatically cleaned up by the OS. On next startup, `asyncio.start_unix_server()` raises `OSError: [Errno 98] Address already in use` and the server fails to start. This is a documented CPython issue (cpython#111246) — `create_unix_server()` does not remove existing socket files. Users see a cryptic startup error and must manually delete the socket file.

**Why it happens:**
UDS socket files are filesystem objects. Unlike TCP ports that are released by the kernel when a process dies, socket files persist. Every process restart after a non-clean shutdown leaves a stale socket. This is a well-known POSIX footgun — the POSIX spec requires the application to clean up.

**How to avoid:**
Before binding, attempt to unlink the socket path, ignoring `FileNotFoundError`:
```python
import os
from pathlib import Path

def _cleanup_stale_socket(sock_path: Path) -> None:
    """Remove stale UDS socket file if present."""
    try:
        sock_path.unlink()
    except FileNotFoundError:
        pass  # Already gone, fine
    except PermissionError:
        raise RuntimeError(
            f"Cannot remove stale socket {sock_path}. "
            "Another process may own it. Check for running instances."
        )

async def start_uds_server(sock_path: Path, app: FastAPI) -> None:
    _cleanup_stale_socket(sock_path)
    server = await asyncio.start_unix_server(handler, path=str(sock_path))
    ...
```

Also register a cleanup atexit handler and handle SIGTERM/SIGINT to delete the socket on clean shutdown. The existing `locking.py` already does PID-based staleness detection — apply the same pattern to the UDS socket path.

**Warning signs:**
- `OSError: [Errno 98] Address already in use` on startup after crash
- Socket file exists at `<state_dir>/agent-brain.sock` but no server process running (check with `lsof`)
- `agent-brain start` fails immediately after `kill -9` on the server
- UDS socket file accumulates multiple stale copies across directories

**Phase to address:**
Phase (UDS Transport) — add pre-bind cleanup as the first step in UDS server startup. Add integration test: start server, kill -9 it, start again — verify it starts successfully.

---

### Pitfall 5: Query Cache Serving Stale Results After Reindex

**What goes wrong:**
Query cache stores `(query_text, retrieval_mode, top_k) -> [results]` with a TTL. A user runs `agent-brain reindex /project` to update 50 files. The index is now fresh, but any cached queries that would return those updated chunks remain in the cache until TTL expiry. The user queries for something that was just updated and receives the pre-reindex answer. This is functionally incorrect for a local dev tool where users expect freshness after explicit reindex.

**Why it happens:**
TTL-based invalidation is simple to implement and sufficient for web caches. But local RAG differs: index changes are deterministic (user triggered them) and the expected behavior is "query reflects whatever was last indexed." Unlike a web cache where content changes gradually, a `reindex` is a step-function change. A 5-minute TTL means 5 minutes of incorrect results after every reindex.

**How to avoid:**
Maintain an `index_generation` counter (a monotonically incrementing integer or `datetime` timestamp) that increments on every successful reindex. Include `index_generation` in every cache key:
```python
def _query_cache_key(
    query: str, mode: str, top_k: int, index_generation: int
) -> str:
    return f"{index_generation}:{mode}:{top_k}:{hashlib.sha256(query.encode()).hexdigest()}"
```
When `index_generation` increments, all prior cache keys become unreachable (different key prefix). No explicit invalidation scan needed. Old entries expire via TTL naturally.

For the watcher-triggered background incremental updates, increment `index_generation` only when the job completes successfully — not when it starts. This prevents partial-update windows where some queries get new results and some get stale results simultaneously.

**Warning signs:**
- User reports "I just reindexed but still seeing old results"
- Query cache hit rate stays high immediately after reindex (should be 0% on new generation)
- Cached results reference file content that no longer exists at that path
- Discrepancy between `/query/count` (updated) and search results (stale)

**Phase to address:**
Phase (Query Cache) — `index_generation` must be part of the cache key schema from initial design. Background incremental watcher jobs must call the same "increment generation" hook that manual reindex does.

---

### Pitfall 6: Debounce Timer Handle Leaks in Long-Running Server

**What goes wrong:**
Each call to `loop.call_later()` returns an `asyncio.TimerHandle`. The watcher stores the handle to cancel it on the next event (resetting the debounce). But if a watched folder is removed (via `agent-brain folder remove`) while a pending timer exists, the handle is never cancelled. The timer fires after 30s, calls `_schedule_index_job(folder_path)`, and the job queue processes a job for a folder that no longer exists in the folder manager. The job fails, logs an error, but the real leak is that the cancelled-folder watcher object is still referenced by the timer closure, preventing garbage collection. Over hours/days with frequent folder additions/removals, memory grows.

**Why it happens:**
Debounce timer cleanup is decoupled from folder lifecycle management. The watcher component and the folder manager component are separate. When `FolderManager.remove_folder()` is called, it has no reference to the watcher's pending timer handle.

**How to avoid:**
On folder removal, explicitly cancel any pending timer handle for that folder before stopping the watcher:
```python
async def remove_folder_watcher(self, folder_path: str) -> None:
    watcher = self._watchers.get(folder_path)
    if watcher is None:
        return
    # Cancel pending debounce timer BEFORE stopping observer
    if watcher.pending_handle is not None:
        watcher.pending_handle.cancel()
        watcher.pending_handle = None
    watcher.observer.stop()
    watcher.observer.join(timeout=5.0)
    del self._watchers[folder_path]
```
The `FolderWatcher` must expose its pending handle to the managing component. Test this path explicitly: add folder, generate events to create a pending timer, remove folder, verify no job is enqueued after the debounce window.

**Warning signs:**
- Memory usage grows over time with watcher enabled and folders being added/removed
- "Folder not found" errors in job worker logs ~30s after folder removal
- `asyncio` timer handle count grows monotonically (inspect with `loop.call_soon_threadsafe` debugging)
- Failed jobs for folder paths that appear nowhere in the folder manager's manifest

**Phase to address:**
Phase (File Watcher) — watcher teardown must cancel pending timer before stopping OS observer. Integration test: add folder, trigger events, remove folder before debounce fires, verify no job enqueued.

---

### Pitfall 7: Manifest Lock Contention Between Watcher Jobs and Manual Reindex

**What goes wrong:**
`ManifestTracker` uses a single `asyncio.Lock` for all manifest operations. The watcher triggers background incremental index jobs automatically. If a user simultaneously runs `agent-brain index /project --force` (manual reindex), two jobs now contend for the same manifest lock. The `asyncio.Lock` serializes them correctly — but the second job re-reads the manifest after the first job wrote it, sees all files as "unchanged" (because the first job just updated all checksums), and produces an empty `chunks_to_create` list. The eviction verification logic in `job_worker.py` handles the zero-change case as a success (lines 433-443), so the job completes with no error — but the user's `--force` flag was effectively ignored.

**Why it happens:**
The manifest lock is per-`ManifestTracker` instance, not per-folder. `--force` bypasses the manifest check (deletes manifest first), but if job 1 completes and writes a fresh manifest just before job 2 reads it, job 2 treats it as a normal incremental run. Race condition window is narrow but real.

**How to avoid:**
`--force` jobs should acquire the manifest lock, delete the manifest, then proceed with indexing — atomically, without releasing the lock between delete and index. Do not delete the manifest before enqueuing the job; delete it as the first step inside the job worker under the lock.

Alternatively: use folder-path-scoped locks rather than a global manifest lock. Each folder gets its own lock, preventing cross-folder contention while still serializing watcher vs. manual jobs for the same folder.

Additionally: the job queue should support a "supersede" mode where a new `--force` job for a folder cancels any PENDING (not RUNNING) jobs for the same folder.

**Warning signs:**
- `--force` flag does not cause full reindex when watcher is active
- Job completes "successfully" with zero new chunks despite `--force`
- Manifest file timestamp is newer than job start time (indicates another job wrote it first)
- Log message "Zero-change incremental run" on a `--force` job

**Phase to address:**
Phase (File Watcher + Background Incremental) — coordinate watcher-triggered jobs and manual jobs through a unified "job supersession" mechanism. Test: start watcher, trigger 30s debounce, immediately run `--force`, verify force job wins.

---

### Pitfall 8: Embedding Cache Disk Corruption on Crash

**What goes wrong:**
If the embedding cache is written to disk as individual files (one per cache entry) or as a single SQLite database, a server crash mid-write leaves a partially written file. On next startup, loading the cache raises `json.JSONDecodeError`, `pickle.UnpicklingError`, or `sqlite3.DatabaseError: database disk image is malformed`. If the startup code does not handle these exceptions, the server fails to start entirely — the cache meant to improve availability now blocks it.

**Why it happens:**
Developers use `pickle.dump()` or `json.dump()` directly to a cache file path without atomic write protection (same pattern solved in `ManifestTracker` with temp+replace, but not applied to cache writes). SQLite with WAL mode is resilient, but only if WAL was enabled before the crash. Raw file writes are not atomic.

**How to avoid:**
Use the same temp-file + atomic rename pattern already established in `ManifestTracker._write_manifest()`:
```python
def _write_cache_entry(self, key: str, value: bytes) -> None:
    path = self._cache_path(key)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(value)
    tmp.replace(path)  # Atomic on POSIX
```

For SQLite-backed cache (`diskcache`), enable WAL mode on connection open:
```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
```

On startup, wrap cache load in a try/except that deletes corrupt entries and continues:
```python
try:
    cache.load()
except (json.JSONDecodeError, OSError) as e:
    logger.warning(f"Cache corrupt, clearing: {e}")
    shutil.rmtree(cache_dir)
    cache_dir.mkdir()
```
A corrupt cache is recoverable by clearing it — never let it block server startup.

**Warning signs:**
- Server fails to start after `kill -9` with cache-related exception in traceback
- `json.JSONDecodeError` or `UnpicklingError` in startup logs
- `.tmp` files accumulating in the cache directory (incomplete writes that did not reach atomic rename)
- Cache file size is 0 bytes or suspiciously small

**Phase to address:**
Phase (Embedding Cache) — atomic writes from day one. Startup code must include try/except around cache load with automatic fallback to empty cache.

---

### Pitfall 9: Query Cache Memory Pressure Without Bounded Size

**What goes wrong:**
Query cache stores full result sets (lists of retrieved chunks with content). Each cache entry can be 10–50 KB (5–20 chunks × 500–2500 bytes of content each). An in-memory cache with no size limit grows to fill available RAM as query diversity increases. A server handling 500 unique queries per hour with 20 KB average result size accumulates 10 MB/hour with no eviction. After a few days of continuous use, the server is killed by the OS OOM manager. The next startup clears the cache, but the problem recurs.

**Why it happens:**
Python's `functools.lru_cache` is bounded by call count, not memory. A naive `dict` cache has no bound at all. Developers set "large" counts (e.g., `maxsize=10000`) without considering entry sizes. Query results are variable-size; count-based limits do not protect against a few large results consuming all memory.

**How to avoid:**
Implement size-aware eviction. Track total bytes stored, evict LRU entries when threshold is exceeded:
```python
MAX_CACHE_BYTES = 64 * 1024 * 1024  # 64 MB hard limit

class QueryCache:
    def __init__(self, max_bytes: int = MAX_CACHE_BYTES) -> None:
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._total_bytes: int = 0
        self._max_bytes = max_bytes

    def set(self, key: str, value: bytes) -> None:
        entry_size = len(value)
        while self._total_bytes + entry_size > self._max_bytes and self._cache:
            _, evicted = self._cache.popitem(last=False)
            self._total_bytes -= len(evicted)
        self._cache[key] = value
        self._total_bytes += entry_size
```

Expose `cache_size_bytes` and `cache_entry_count` in the `/health/status` endpoint so operators can tune the limit. Start with a 64 MB ceiling for the query cache and 256 MB for the embedding cache as conservative defaults for a developer laptop.

**Warning signs:**
- Server memory usage grows monotonically without apparent plateau
- OOM kills with no other obvious memory consumer
- `/health/status` shows large document counts but cache metrics absent
- RSS growing proportionally to unique query count in logs

**Phase to address:**
Phase (Query Cache) — implement size-aware cache from day one. Never use unbounded dict. Add `GET /health/cache` endpoint with size metrics.

---

### Pitfall 10: Per-Folder Watcher Config Schema Drift from Folder Manager Schema

**What goes wrong:**
The file watcher introduces per-folder config fields: `watch_enabled`, `debounce_seconds`, `read_only` (watch but do not auto-reindex). These live in the folder manager's persistent manifest. Over time, the watcher config schema diverges from the folder manager schema — the folder manager validates its own fields with Pydantic, but the watcher config is stored as a nested dict in `extra_config` and never validated. A user sets `debounce_seconds: "thirty"` (string instead of int) in the CLI or directly in the JSON. The server starts and silently uses the default debounce because the string fails `isinstance(v, (int, float))`, but no error is raised.

**Why it happens:**
Watcher config is added after the folder manager is built. Rather than extending the existing `FolderRecord` Pydantic model, developers add a freeform `extra` dict to avoid touching the existing schema. The `extra` dict is never validated.

**How to avoid:**
Extend `FolderRecord` (or whatever model stores folder state) with explicit typed watcher fields:
```python
class FolderRecord(BaseModel):
    path: str
    added_at: datetime
    # Watcher config — typed, validated
    watch_enabled: bool = False
    debounce_seconds: float = 30.0
    read_only: bool = False  # Watch but never auto-reindex
    include_patterns: list[str] = Field(default_factory=list)
```
Pydantic validates on load. Invalid YAML/JSON raises `ValidationError` with a clear message rather than silently using defaults. The folder manager's existing atomic write path handles persisting the extended model without changes.

**Warning signs:**
- Watcher uses different debounce than configured in CLI
- `agent-brain folder config` shows correct values but behavior is wrong
- Silent fallback to default in logs ("using default debounce: 30s") when folder has explicit config
- Schema mismatch errors when upgrading from pre-watcher to watcher-enabled version

**Phase to address:**
Phase (File Watcher) — watcher config fields must be part of `FolderRecord` Pydantic model, not a separate dict. Run migration test: load a v7.0 folder manifest JSON (without watcher fields), verify it loads cleanly with watcher defaults applied.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Cache key on content hash only (no provider signature) | Simple, one hash lookup | Cache poisoning on provider switch, silent wrong results | Never — add provider+model to key from day one |
| Per-file debounce instead of per-folder | Easier to implement | Thundering herd on git checkout, 500 jobs instead of 1 | Never for this use case |
| Calling asyncio from watchdog thread directly | Looks correct in tests | RuntimeError at runtime, missing events | Never — always use `call_soon_threadsafe()` |
| Unbounded in-memory cache dict | Zero-overhead implementation | OOM kill after sustained use, no eviction metrics | Only for unit tests with mock data |
| Skip atomic write for cache entries | Simpler code | Corrupt cache blocks startup after crash | Never — existing `ManifestTracker` pattern is one function to reuse |
| No UDS cleanup on startup | One less thing to worry about | Startup failure after every crash, confusing error message | Never — two lines of code with try/except |
| Watcher config in freeform `extra` dict | No model changes needed | Silent misconfiguration, no validation | Never — extend the Pydantic model |
| Increment `index_generation` at job start (not job end) | Generation advances as soon as work begins | Race window where half the queries get new results and half get old | Never — advance on successful completion only |

---

## Integration Gotchas

Common mistakes when connecting to existing Agent Brain components.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Embedding cache + provider system | Cache key omits provider/model name | Include `provider:model` fingerprint in cache key namespace |
| Watcher + job queue | Enqueue job per file event | Enqueue job per folder per debounce window; check for existing PENDING job before enqueuing |
| Watchdog + asyncio event loop | Calling async functions from watchdog handler | Use `loop.call_soon_threadsafe()` to cross the thread boundary |
| UDS socket + startup | Binding without pre-cleanup | Unlink socket path before bind, handle `FileNotFoundError` |
| Query cache + reindex | TTL-only invalidation | Include `index_generation` counter in cache key |
| Cache + server startup | `json.JSONDecodeError` propagates and crashes server | Wrap cache load in try/except, clear and continue on corruption |
| Per-folder watcher config + folder manager | Adding config as freeform dict | Extend `FolderRecord` Pydantic model with typed watcher fields |
| Watcher + manifest tracker lock | Concurrent watcher job + manual `--force` job | Implement job supersession for PENDING jobs on same folder path |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Embedding cache with no size limit | Memory grows 100–200 MB/day for active codebases | Set hard byte limit (256 MB default), evict LRU | ~50k unique text chunks in cache |
| Query cache with no size limit | OOM kill after days of continuous use | Size-aware eviction with byte tracking | ~5k large result sets (~20 chunks each) |
| Per-file debounce timers | 500 tasks created on git checkout | Per-folder single timer, reset on any folder event | Projects with >50 files and frequent VCS operations |
| Synchronous cache disk I/O on embedding path | Blocking event loop during cache read on cold start | Use `asyncio.to_thread()` for disk-based cache reads | Cache files >1 MB each |
| No cache hit rate metrics | Cannot distinguish "cache working" from "cache bypassed" | Expose `cache_hits` / `cache_misses` counters in `/health/status` | At any scale — blind operation is always wrong |
| UDS + TCP dual transport without connection pooling | Connection overhead per request over TCP | Use persistent httpx `AsyncClient` with connection pool | >10 req/s over TCP transport |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| UDS socket with world-readable permissions (0o777) | Any local user can query the index | Set socket mode to 0o600 (owner only) after bind |
| Embedding cache stored in world-readable directory | Cache entries contain indexed code content | Store cache in `<state_dir>` (per-project), not `/tmp` |
| Cache key predictable without hash | Cache poisoning via crafted query | Use SHA-256 of full key tuple, never concatenate raw strings |
| UDS socket path in system temp directory (`/tmp`) | Other users can observe socket and attempt connection | Use `<state_dir>/agent-brain.sock` (per-project, mode 0o700 directory) |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Silent background reindex with no indication | "Why is indexing happening? I didn't ask for it" | Log watcher-triggered jobs clearly: "Auto-reindex triggered for /project (3 files changed)" |
| Debounce hides that changes were detected | User edits file, expects instant indexing, nothing happens for 30s | Show "Changes detected, indexing in 30s..." in `agent-brain status` |
| Cache metrics absent from status | Cannot tell if caching is working | Expose hit rate, size, and entry count in `agent-brain status` and `/health/status` |
| UDS transport not auto-detected | User must know to set `--uds` flag | CLI auto-detects UDS socket file from `runtime.json`, falls back to TCP |
| Background watcher error not surfaced | File watcher crashes silently, no auto-reindex happening | Expose watcher state (running/stopped/error) in `agent-brain status` |
| No way to disable watcher per-folder without removing it | Watcher auto-reindexes read-only mounts (NFS, Docker volumes) | Support `read_only: true` per-folder config: watch for changes but never enqueue jobs |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Embedding Cache:** Cache key includes `provider:model` fingerprint — verify switching `providers.yaml` causes cache miss, not cache hit
- [ ] **Embedding Cache:** Startup detects provider config change and clears cache namespace — verify no stale vectors served after provider switch
- [ ] **Embedding Cache:** Atomic writes for cache entries — verify `.tmp` file used, not direct write
- [ ] **Embedding Cache:** Corrupt cache on startup clears gracefully — verify server starts after `dd if=/dev/urandom` into cache file
- [ ] **File Watcher:** Debounce is per-folder, not per-file — verify 500 events in 100ms produces exactly 1 job
- [ ] **File Watcher:** Watchdog handler uses `call_soon_threadsafe()` — verify no `RuntimeError` in server logs under load
- [ ] **File Watcher:** Pending timer cancelled on folder removal — verify no job enqueued after folder removed mid-debounce
- [ ] **File Watcher:** Watcher config schema uses typed Pydantic fields — verify `ValidationError` on invalid `debounce_seconds: "thirty"`
- [ ] **UDS Transport:** Socket cleanup before bind — verify server starts after `kill -9` without manual socket deletion
- [ ] **UDS Transport:** Socket mode is 0o600 — verify `ls -la <sock_path>` shows `-rw-------`
- [ ] **Query Cache:** `index_generation` in cache key — verify all cache entries are missed after successful reindex
- [ ] **Query Cache:** Size-aware eviction — verify memory does not exceed limit after 10k unique queries
- [ ] **Query Cache:** Hit/miss metrics in `/health/status` — verify counters increment correctly
- [ ] **Background Incremental:** Watcher job does not supersede running manual job — verify manual `--force` job wins if it starts after watcher job is PENDING

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Cache serves wrong-dimension embeddings after provider switch | MEDIUM | `rm -rf <state_dir>/embedding-cache/`, restart server — cache cold starts |
| Thundering herd floods job queue with 500+ jobs | LOW | Cancel all PENDING jobs via `agent-brain jobs --cancel-all`, restart watcher |
| UDS socket stale, server won't start | LOW | `rm <state_dir>/agent-brain.sock`, restart server |
| Query cache serving stale results post-reindex | LOW | `POST /cache/clear` (if endpoint exists) or restart server to clear in-memory cache |
| Corrupt embedding cache blocks startup | LOW | `rm -rf <state_dir>/embedding-cache/`, restart — all embeddings re-fetched on next index run |
| Memory OOM from unbounded cache | MEDIUM | Restart server (cache clears), set `EMBEDDING_CACHE_MAX_MB` and `QUERY_CACHE_MAX_MB` env vars |
| Watcher timer leak after folder removals | LOW | Restart server — timers are in-memory, restart clears them; fix underlying cancel-on-remove bug |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Cache incoherence on provider change | Phase: Embedding Cache | Integration test: index with OpenAI, switch to Ollama, verify cache miss and no dimension error |
| Thundering herd on git checkout | Phase: File Watcher | Unit test: 500 events in 100ms → exactly 1 job enqueued |
| Watchdog thread / asyncio thread boundary | Phase: File Watcher | Unit test: call handler from non-loop thread, verify no RuntimeError |
| UDS socket stale on crash | Phase: UDS Transport | Integration test: kill -9 server, restart, verify startup success |
| Query cache stale after reindex | Phase: Query Cache | Integration test: index, query (cache warm), reindex, query same text → cache miss, fresh results |
| Debounce timer leak on folder remove | Phase: File Watcher | Integration test: add folder, trigger events, remove folder, verify no job after debounce window |
| Manifest lock contention watcher vs manual | Phase: Background Incremental | Integration test: concurrent watcher job + force reindex, verify force wins |
| Cache corrupt on crash | Phase: Embedding Cache | Integration test: corrupt cache file mid-write, verify startup clears and continues |
| Cache memory unbounded | Phase: Query Cache + Embedding Cache | Load test: 50k unique texts cached, verify RSS stays under limit |
| Per-folder config schema drift | Phase: File Watcher | Migration test: load v7.0 manifest, verify watcher defaults applied without error |

---

## Sources

### UDS Socket Cleanup
- [CPython issue #111246: Listening asyncio UNIX socket isn't removed on close](https://github.com/python/cpython/issues/111246)
- [Python asyncio issue #425: unlink stale unix socket before binding](https://github.com/python/asyncio/issues/425)
- [Python bug tracker #34139: Remove stale unix datagram socket before binding](https://bugs.python.org/issue34139)

### Watchdog Thread Safety and Asyncio Integration
- [Using watchdog with asyncio (gist)](https://gist.github.com/mivade/f4cb26c282d421a62e8b9a341c7c65f6)
- [asyncio Event Loop documentation — thread safety](https://docs.python.org/3/library/asyncio-eventloop.html)
- [Smarter File Watching with rate-limiting and change history](https://medium.com/@RampantLions/smarter-file-watching-in-python-rate-limiting-and-change-history-with-watchdog-2114e45e7774)

### Asyncio Task Cancellation and Timer Cleanup
- [Asyncio Task Cancellation Best Practices](https://superfastpython.com/asyncio-task-cancellation-best-practices/)
- [PEP 789 — Preventing task-cancellation bugs](https://peps.python.org/pep-0789/)

### Embedding Cache and Provider Coherence
- [ChromaDB embedding dimension mismatch — crewAI issue #2464](https://github.com/crewAIInc/crewAI/issues/2464)
- [ChromaDB Bug: InvalidDimensionException on model switch — chroma issue #4368](https://github.com/chroma-core/chroma/issues/4368)
- [Mastering Embedding Caching: Advanced Techniques for 2025](https://sparkco.ai/blog/mastering-embedding-caching-advanced-techniques-for-2025)

### Query Cache Invalidation
- [Semantic Caching in Agentic AI: cache eligibility and invalidation](https://www.ashwinhariharan.com/semantic-caching-in-agentic-ai-determining-cache-eligibility-and-invalidation/)
- [How to cache semantic search: a complete guide](https://www.meilisearch.com/blog/how-to-cache-semantic-search)
- [Data freshness rot as the silent failure mode in production RAG systems](https://glenrhodes.com/data-freshness-rot-as-the-silent-failure-mode-in-production-rag-systems-and-treating-document-shelf-life-as-a-first-class-reliability-concern/)

### Cache Memory Management
- [Memory-aware LRU cache decorator (gist)](https://gist.github.com/wmayner/0245b7d9c329e498d42b)
- [Caching in Python Using the LRU Cache Strategy — Real Python](https://realpython.com/lru-cache-python/)
- [Time-based LRU cache in Python](https://jamesg.blog/2024/08/18/time-based-lru-cache-python)

### Disk Cache Corruption
- [DiskCache SQLite concurrent access issue #85](https://github.com/grantjenks/python-diskcache/issues/85)
- [How To Corrupt An SQLite Database File](https://www.sqlite.org/howtocorrupt.html)
- [DiskCache Tutorial — WAL mode and crash safety](https://grantjenks.com/docs/diskcache/tutorial.html)

### Job Deduplication Patterns
- [BullMQ Job Deduplication — Debounce and Throttle modes](https://docs.bullmq.io/guide/jobs/deduplication)
- [Race conditions when watching the file system — atom/github issue #345](https://github.com/atom/github/issues/345)

### Uvicorn UDS Support
- [Uvicorn Settings — --uds flag](https://www.uvicorn.org/settings/)
- [FastAPI Unix Domain Socket example](https://github.com/realcaptainsolaris/fast_api_unix_domain)

---

*Pitfalls research for: v8.0 Performance & Developer Experience (file watching, embedding cache, query cache, UDS transport)*
*Researched: 2026-03-06*
*Confidence: HIGH — critical pitfalls cross-referenced with official CPython/asyncio issue trackers and ChromaDB bug reports*
