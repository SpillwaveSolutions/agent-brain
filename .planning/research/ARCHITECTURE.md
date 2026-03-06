# Architecture Research

**Domain:** RAG server — v8.0 Performance & DX feature integration
**Researched:** 2026-03-06
**Confidence:** HIGH (codebase read directly; UDS dual-server pattern MEDIUM based on official docs + verified community patterns)

---

## Standard Architecture

### System Overview (v7.0 Baseline — What Exists)

```
┌──────────────────────────────────────────────────────────────────┐
│                  TCP Transport (127.0.0.1:PORT)                    │
├──────────────────────────────────────────────────────────────────┤
│  FastAPI Application                                               │
│  ┌──────────┐ ┌────────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │ /health  │ │  /index    │ │  /query  │ │ /index/folders    │  │
│  │ /health/ │ │ /index/add │ │ /query/  │ │ /index/jobs       │  │
│  │ status   │ │ DELETE     │ │  count   │ └───────────────────┘  │
│  └──────────┘ └─────┬──────┘ └────┬─────┘                        │
├──────────────────────┼─────────────┼────────────────────────────────┤
│                Service Layer        │                                │
│  ┌───────────────────▼──────┐ ┌────▼──────────────────────────┐    │
│  │     IndexingService      │ │        QueryService            │    │
│  │  _run_indexing_pipeline  │ │  execute_query()               │    │
│  │  ManifestTracker         │ │  _execute_vector/bm25/hybrid/  │    │
│  │  ChunkEvictionService    │ │  graph/multi_query()           │    │
│  │  FolderManager           │ │  _rerank_results()             │    │
│  └───────────┬──────────────┘ └───────────────────────────────┘    │
│  ┌───────────▼──────────────┐                                       │
│  │  JobService + JobWorker   │                                       │
│  │  JSONL queue, asyncio     │                                       │
│  │  poll loop, timeout       │                                       │
│  └──────────────────────────┘                                       │
├──────────────────────────────────────────────────────────────────┤
│                   Indexing Pipeline                                 │
│  DocumentLoader → ContextAwareChunker/CodeChunker                   │
│                 → EmbeddingGenerator (pluggable providers)          │
├──────────────────────────────────────────────────────────────────┤
│            StorageBackendProtocol (11 async methods)                │
│  ┌──────────────────────┐  ┌──────────────────────────────────┐    │
│  │  ChromaDB Backend    │  │     PostgreSQL Backend            │    │
│  │  vector + BM25 disk  │  │  pgvector + tsvector             │    │
│  └──────────────────────┘  └──────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

### v8.0 Target Architecture (New Components Highlighted)

```
┌──────────────────────────────────────────────────────────────────────┐
│  [NEW] UDS Transport  unix:///state_dir/agent-brain.sock              │
│  [EXISTING] TCP Transport  127.0.0.1:PORT  (health + remote access)   │
│  Both transports share the same FastAPI app object and app.state      │
├──────────────────────────────────────────────────────────────────────┤
│  FastAPI Application (unchanged router structure)                     │
├─────────────────────────┬────────────────────────────────────────────┤
│    Existing Services     │  [NEW] Background Services                  │
│  ┌────────────────────┐ │  ┌──────────────────────────────────────┐   │
│  │  IndexingService   │ │  │     FileWatcherService               │   │
│  │  [MOD] receives    │ │  │  watchdog ObserverThread (OS thread) │   │
│  │  EmbeddingGenerator│ │  │  DebouncedFolderHandler per folder   │   │
│  │  with cache wired  │ │  │  threading.Timer cancel-restart      │   │
│  │  in                │ │  │  asyncio.Queue bridge                │   │
│  └────────────────────┘ │  │  enqueue to JobService (force=False) │   │
│  ┌────────────────────┐ │  └──────────────────────────────────────┘   │
│  │  QueryService      │ │                                              │
│  │  [MOD] checks      │ │  [NEW] EmbeddingCache                        │
│  │  QueryCache before │ │  ┌──────────────────────────────────────┐   │
│  │  any work          │ │  │  sha256(model:text) → vector          │   │
│  └────────────────────┘ │  │  cachetools LRUCache in-memory       │   │
│  ┌────────────────────┐ │  │  optional diskcache SQLite (persist) │   │
│  │  JobWorker         │ │  │  invalidate_all() on provider change  │   │
│  │  [MOD] calls       │ │  └──────────────────────────────────────┘   │
│  │  query_cache.      │ │                                              │
│  │  invalidate_all()  │ │  [NEW] QueryCache                           │
│  │  on job DONE       │ │  ┌──────────────────────────────────────┐   │
│  └────────────────────┘ │  │  hash(query+mode+top_k+...) → resp   │   │
│                          │  │  cachetools TTLCache (300s default)  │   │
│                          │  │  invalidate_all() on index update    │   │
│                          │  └──────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

| Component | Responsibility | Status | Location |
|-----------|----------------|--------|----------|
| `IndexingService` | Orchestrates load→chunk→embed→store pipeline | Existing | `services/indexing_service.py` |
| `QueryService` | All query modes + reranking | Existing | `services/query_service.py` |
| `JobWorker` | Polls JSONL queue, runs indexing with timeout | Existing | `job_queue/job_worker.py` |
| `FolderManager` | Tracks indexed folders with JSONL persistence | Existing | `services/folder_manager.py` |
| `ManifestTracker` | Per-folder SHA-256 file manifests for incremental indexing | Existing | `services/manifest_tracker.py` |
| `EmbeddingGenerator` | Pluggable provider calls for embed_texts/embed_query | Existing | `indexing/embedding.py` |
| `EmbeddingCache` | SHA-256 keyed embedding lookup, LRU + optional disk | **New** | `services/embedding_cache.py` |
| `QueryCache` | TTL-based cache for full QueryResponse objects | **New** | `services/query_cache.py` |
| `FileWatcherService` | watchdog observer + per-folder debounce + job enqueue | **New** | `services/file_watcher_service.py` |
| `FolderRecord` | Extended with `watch_enabled` + `watch_debounce_seconds` | **Modify** | `services/folder_manager.py` |
| Dual UDS+TCP Server | Two `uvicorn.Server` instances in `asyncio.gather()` | **Modify** | `api/main.py` `run()` function |
| `RuntimeState` | Extended with `uds_path` + `uds_url` fields | **Modify** | `runtime.py` |

---

## Integration Points by Feature

### 1. Embedding Cache

**Where it lives:** Inside `EmbeddingGenerator.embed_texts()` — the single choke point for all embedding calls from both `IndexingService` (Step 3 of pipeline) and `QueryService` (vector query, hybrid query, `VectorManagerRetriever`).

**New file:** `agent_brain_server/services/embedding_cache.py`

```python
# services/embedding_cache.py  (NEW)
import asyncio
import hashlib
from cachetools import LRUCache

class EmbeddingCache:
    """SHA-256 keyed embedding vector cache with optional disk persistence.

    Key includes model name to prevent cross-provider vector pollution.
    Call invalidate_all() when embedding provider or model changes.
    """

    def __init__(
        self,
        maxsize: int = 50_000,       # ~50K chunks fit in memory
        disk_path: str | None = None, # None = memory-only
    ) -> None:
        self._memory: LRUCache[str, list[float]] = LRUCache(maxsize=maxsize)
        self._lock = asyncio.Lock()
        self._disk = None
        if disk_path:
            import diskcache
            self._disk = diskcache.Cache(disk_path)

    def _key(self, text: str, model: str) -> str:
        return hashlib.sha256(f"{model}:{text}".encode()).hexdigest()

    async def get(self, text: str, model: str) -> list[float] | None:
        key = self._key(text, model)
        async with self._lock:
            hit = self._memory.get(key)
            if hit is not None:
                return hit
        if self._disk is not None:
            return self._disk.get(key)  # type: ignore[return-value]
        return None

    async def put(self, text: str, model: str, embedding: list[float]) -> None:
        key = self._key(text, model)
        async with self._lock:
            self._memory[key] = embedding
        if self._disk is not None:
            self._disk[key] = embedding

    def invalidate_all(self) -> None:
        """Call when embedding provider or model changes."""
        self._memory.clear()
        if self._disk is not None:
            self._disk.clear()
```

**Modification to `EmbeddingGenerator`** (`indexing/embedding.py`):

```python
class EmbeddingGenerator:
    def __init__(
        self,
        embedding_provider=None,
        summarization_provider=None,
        embedding_cache: "EmbeddingCache | None" = None,  # NEW
    ):
        ...
        self._cache = embedding_cache

    async def embed_texts(self, texts, progress_callback=None):
        if self._cache is None:
            return await self._embedding_provider.embed_texts(texts, progress_callback)

        results: list[list[float] | None] = [None] * len(texts)
        uncached_indices: list[int] = []

        for i, text in enumerate(texts):
            cached = await self._cache.get(text, self.model)
            if cached is not None:
                results[i] = cached
            else:
                uncached_indices.append(i)

        if uncached_indices:
            uncached_texts = [texts[i] for i in uncached_indices]
            fresh = await self._embedding_provider.embed_texts(uncached_texts)
            for list_idx, vec in zip(uncached_indices, fresh):
                results[list_idx] = vec
                await self._cache.put(texts[list_idx], self.model, vec)

        return results  # type: ignore[return-value]
```

**Lifespan wiring** (`api/main.py`):
1. Create `EmbeddingCache` after storage paths are resolved.
2. Create `EmbeddingGenerator(embedding_cache=embedding_cache)`.
3. Pass same generator into `IndexingService` and `QueryService`.
4. Store `embedding_cache` on `app.state.embedding_cache`.

**Invalidation trigger:** In `IndexingService._validate_embedding_compatibility()`, when a provider/model mismatch is detected and `force=True` is used (meaning re-embedding is happening), call `app.state.embedding_cache.invalidate_all()`. Also on startup when `check_embedding_compatibility()` detects a mismatch in `main.py`.

---

### 2. Query Cache

**Where it lives:** Top of `QueryService.execute_query()` — before embedding the query text.

**New file:** `agent_brain_server/services/query_cache.py`

```python
# services/query_cache.py  (NEW)
import asyncio
import hashlib
import json
from cachetools import TTLCache
from agent_brain_server.models import QueryRequest, QueryResponse

class QueryCache:
    """TTL-based cache for full QueryResponse objects.

    Keyed on a deterministic hash of query parameters.
    Invalidate on any index update via invalidate_all().
    """

    def __init__(self, maxsize: int = 1000, ttl: int = 300) -> None:
        self._cache: TTLCache[str, QueryResponse] = TTLCache(
            maxsize=maxsize, ttl=ttl
        )
        self._lock = asyncio.Lock()

    def _key(self, request: QueryRequest) -> str:
        payload = {
            "query": request.query,
            "mode": str(request.mode),
            "top_k": request.top_k,
            "threshold": request.similarity_threshold,
            "alpha": request.alpha,
            "source_types": sorted(request.source_types or []),
            "languages": sorted(request.languages or []),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()

    async def get(self, request: QueryRequest) -> QueryResponse | None:
        key = self._key(request)
        async with self._lock:
            return self._cache.get(key)

    async def put(self, request: QueryRequest, response: QueryResponse) -> None:
        key = self._key(request)
        async with self._lock:
            self._cache[key] = response

    def invalidate_all(self) -> None:
        """Call when a new indexing job completes successfully."""
        self._cache.clear()
```

**Modification to `QueryService`** (`services/query_service.py`):
- Add `query_cache: QueryCache | None = None` to `__init__`.
- First two lines of `execute_query()`: check cache, return if hit.
- Last lines before return: store result in cache.

**Modification to `JobWorker`** (`job_queue/job_worker.py`):
- Add `query_cache: QueryCache | None = None` to `__init__`.
- After `job.status = JobStatus.DONE` and before `await self._job_store.update_job(job)` in `_process_job()`: call `self._query_cache.invalidate_all()` if not None.

**Lifespan wiring** (`api/main.py`):
1. Create `QueryCache(ttl=settings.AGENT_BRAIN_QUERY_CACHE_TTL)`.
2. Pass into `QueryService(query_cache=query_cache)`.
3. Pass into `JobWorker(query_cache=query_cache)`.
4. Store on `app.state.query_cache`.

---

### 3. File Watcher with Per-Folder Config and Debounce

**Data model change** (`services/folder_manager.py` — `FolderRecord` dataclass):

```python
@dataclass
class FolderRecord:
    folder_path: str
    chunk_count: int
    last_indexed: str
    chunk_ids: list[str]
    # NEW — defaults preserve backward compatibility with existing JSONL files
    watch_enabled: bool = False
    watch_debounce_seconds: int = 30
```

`FolderManager._load_jsonl()` already uses `data["key"]` pattern. Change to `data.get("watch_enabled", False)` and `data.get("watch_debounce_seconds", 30)` for backward-compatible deserialization.

**New file:** `agent_brain_server/services/file_watcher_service.py`

```python
# services/file_watcher_service.py  (NEW)
import asyncio
import logging
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)


class DebouncedFolderHandler(FileSystemEventHandler):
    """Debounces all filesystem events for one folder into a single asyncio queue push."""

    def __init__(
        self,
        folder_path: str,
        debounce_seconds: int,
        loop: asyncio.AbstractEventLoop,
        event_queue: "asyncio.Queue[str]",
    ) -> None:
        self._folder_path = folder_path
        self._debounce_seconds = debounce_seconds
        self._loop = loop
        self._event_queue = event_queue
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def on_any_event(self, event) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(
                self._debounce_seconds,
                self._fire,
            )
            self._timer.daemon = True
            self._timer.start()

    def _fire(self) -> None:
        """Fire after debounce window expires. Called from threading.Timer thread."""
        asyncio.run_coroutine_threadsafe(
            self._event_queue.put(self._folder_path),
            self._loop,
        )


class FileWatcherService:
    """Manages per-folder file watchers and routes debounced events to job queue."""

    def __init__(
        self,
        folder_manager: "FolderManager",
        job_service: "JobQueueService",
    ) -> None:
        self._folder_manager = folder_manager
        self._job_service = job_service
        self._observer: Observer = Observer()
        self._event_queue: asyncio.Queue[str] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self._watches: dict[str, object] = {}

    async def start(self) -> None:
        """Start watchdog observer and asyncio consumer. Call in lifespan."""
        loop = asyncio.get_running_loop()
        self._loop = loop
        await self._sync_watches(loop)
        self._observer.start()
        self._task = asyncio.create_task(self._consume_events())
        logger.info("FileWatcherService started")

    async def stop(self) -> None:
        """Stop observer and cancel consumer task. Call in lifespan shutdown."""
        self._observer.stop()
        self._observer.join(timeout=5.0)
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("FileWatcherService stopped")

    async def _sync_watches(self, loop: asyncio.AbstractEventLoop) -> None:
        """Schedule watches for all auto-reindex folders at startup."""
        folders = await self._folder_manager.list_folders()
        for record in folders:
            if record.watch_enabled:
                self._schedule_watch(record.folder_path, record.watch_debounce_seconds, loop)

    def add_folder_watch(self, folder_path: str, debounce_seconds: int) -> None:
        """Called after folder is added with watch_enabled=True."""
        self._schedule_watch(folder_path, debounce_seconds, self._loop)

    def remove_folder_watch(self, folder_path: str) -> None:
        """Called when a folder is removed or watch disabled."""
        watch = self._watches.pop(folder_path, None)
        if watch is not None:
            self._observer.unschedule(watch)

    def _schedule_watch(
        self,
        folder_path: str,
        debounce_seconds: int,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        if folder_path in self._watches:
            return
        handler = DebouncedFolderHandler(
            folder_path=folder_path,
            debounce_seconds=debounce_seconds,
            loop=loop,
            event_queue=self._event_queue,
        )
        watch = self._observer.schedule(handler, folder_path, recursive=True)
        self._watches[folder_path] = watch
        logger.info(f"Watching {folder_path} (debounce={debounce_seconds}s)")

    async def _consume_events(self) -> None:
        """Asyncio task: pop folder paths from queue and enqueue indexing jobs."""
        while True:
            try:
                folder_path = await self._event_queue.get()
                logger.info(f"File change detected in {folder_path}, enqueueing job")
                await self._job_service.enqueue(
                    folder_path=folder_path,
                    include_code=True,
                    recursive=True,
                    force=False,  # Always incremental: ManifestTracker handles the diff
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing watcher event for: {e}", exc_info=True)
```

**API extension:** Extend `FolderAddRequest` in `models/folders.py` with `watch_enabled: bool = False` and `watch_debounce_seconds: int = 30`. In `folders.py` router, after `folder_manager.add_folder(...)`, call `app.state.file_watcher_service.add_folder_watch(path, debounce_seconds)` if `watch_enabled`.

**Lifespan wiring** (`api/main.py`): After `_job_worker.start()`, create `FileWatcherService` and `await file_watcher_service.start()`. Store on `app.state.file_watcher_service`. In shutdown, `await file_watcher_service.stop()` before `_job_worker.stop()`.

---

### 4. Background Incremental Updates (via watcher → existing pipeline)

This is NOT a separate component. It is the data flow that results from combining `FileWatcherService` (new) with `JobWorker` + `IndexingService` + `ManifestTracker` (all existing).

The full path reuses every existing piece. No new components required beyond `FileWatcherService`. The key insight is that watcher-triggered jobs always use `force=False` — the existing `ManifestTracker` mtime fast-path handles ~95% of unchanged files in O(1), so the watcher does not trigger a full re-embed on each event.

---

### 5. Hybrid UDS + TCP Transport

**Finding:** Uvicorn does NOT support binding to both TCP and UDS simultaneously from a single `uvicorn.run()` call. The `--uds` and `--host/--port` options are mutually exclusive. (Confirmed against official uvicorn docs at `uvicorn.dev/settings/`.)

**Pattern (MEDIUM confidence):** Two `uvicorn.Server` instances sharing one `app` object, running concurrently via `asyncio.gather()`.

```python
# api/main.py  (MODIFY run() function)

class _NoSignalServer(uvicorn.Server):
    """Suppress duplicate signal handler registration when running dual servers."""
    def install_signal_handlers(self) -> None:
        pass


def run(
    host: str | None = None,
    port: int | None = None,
    reload: bool | None = None,
    state_dir: str | None = None,
    uds_path: str | None = None,    # NEW optional parameter
) -> None:
    global _runtime_state, _state_dir

    resolved_host = host or settings.API_HOST
    resolved_port = port if port is not None else settings.API_PORT

    if resolved_port == 0:
        resolved_port = _find_free_port()

    # ... existing per-project state_dir / runtime setup (unchanged) ...

    # Auto-compute UDS path when state_dir is known
    if uds_path is None and state_dir and settings.AGENT_BRAIN_UDS_ENABLED:
        uds_path = str(Path(state_dir) / "agent-brain.sock")

    if uds_path:
        # Dual-server mode: TCP for remote + UDS for local
        tcp_config = uvicorn.Config(
            "agent_brain_server.api.main:app",
            host=resolved_host,
            port=resolved_port,
            loop="none",
            lifespan="on",   # TCP server owns lifespan — initializes app.state
        )
        uds_config = uvicorn.Config(
            "agent_brain_server.api.main:app",
            uds=uds_path,
            loop="none",
            lifespan="off",  # CRITICAL: UDS server must NOT re-run lifespan
        )
        tcp_server = uvicorn.Server(tcp_config)
        uds_server = _NoSignalServer(uds_config)

        async def _serve_both() -> None:
            await asyncio.gather(tcp_server.serve(), uds_server.serve())

        asyncio.run(_serve_both())
    else:
        # Single TCP server (existing behavior, backward compatible)
        uvicorn.run(
            "agent_brain_server.api.main:app",
            host=resolved_host,
            port=resolved_port,
            reload=reload if reload is not None else settings.DEBUG,
        )
```

**RuntimeState extension** (`runtime.py`):

```python
@dataclass
class RuntimeState:
    mode: str
    project_root: str
    bind_host: str
    port: int
    pid: int
    base_url: str
    uds_path: str | None = None   # NEW — absolute path to unix socket file
    uds_url: str | None = None    # NEW — "http+unix://%2F...%2Fagent-brain.sock/"
```

Write `uds_path` and `uds_url` into `runtime.json` for CLI discovery. The CLI `start` command reads `runtime.json` to build the base URL — it should prefer `uds_url` for local connections when available.

**Settings additions** (`config/settings.py`):

```python
AGENT_BRAIN_UDS_ENABLED: bool = True        # Default on for project mode
AGENT_BRAIN_UDS_PATH: str | None = None     # Override socket path
AGENT_BRAIN_QUERY_CACHE_TTL: int = 300      # seconds
AGENT_BRAIN_QUERY_CACHE_SIZE: int = 1000    # max entries
AGENT_BRAIN_EMBED_CACHE_SIZE: int = 50000   # max entries
```

**Critical constraint on `lifespan="off"`:** The FastAPI `lifespan()` context manager initializes ChromaDB, BM25Manager, PostgreSQL pool, EmbeddingGenerator, IndexingService, QueryService, and JobWorker — all stored on `app.state`. Both servers share the same `app` object. If the UDS server also runs lifespan, all services would be double-initialized against the same persistent storage paths, causing corruption. `lifespan="off"` on UDS ensures it connects to `app.state` that the TCP server has already populated.

---

## Recommended Project Structure (New and Modified Files)

```
agent-brain-server/
└── agent_brain_server/
    ├── services/
    │   ├── embedding_cache.py         # NEW: LRU + optional diskcache
    │   ├── query_cache.py             # NEW: TTLCache for QueryResponse
    │   ├── file_watcher_service.py    # NEW: watchdog + debounce + asyncio bridge
    │   ├── folder_manager.py          # MODIFY: add watch_enabled/debounce to FolderRecord
    │   ├── indexing_service.py        # MODIFY: EmbeddingGenerator injected from lifespan
    │   └── query_service.py           # MODIFY: QueryCache constructor param + check
    ├── indexing/
    │   └── embedding.py               # MODIFY: cache lookup in embed_texts()
    ├── job_queue/
    │   └── job_worker.py              # MODIFY: invalidate_all() on job DONE
    ├── models/
    │   └── folders.py                 # MODIFY: add watch fields to request/response models
    ├── api/
    │   ├── main.py                    # MODIFY: lifespan wires caches+watcher; run() dual server
    │   └── routers/
    │       └── folders.py             # MODIFY: pass watch params to FolderManager + FileWatcherService
    ├── runtime.py                     # MODIFY: uds_path, uds_url in RuntimeState
    └── config/
        └── settings.py                # MODIFY: UDS + cache config constants
```

---

## Data Flow Diagrams

### Flow 1: File Change to Auto-Reindex to Cache Invalidation

```
[File modified in watched folder]
    |
    | (OS inotify/FSEvents/kqueue via watchdog)
    v
DebouncedFolderHandler.on_any_event()  [OS thread]
    |
    | cancel previous timer, start new threading.Timer(30s)
    |
    | [30 seconds of silence pass — no more events]
    v
DebouncedFolderHandler._fire()  [threading.Timer thread]
    |
    | asyncio.run_coroutine_threadsafe(queue.put(folder_path), loop)
    |
    v
FileWatcherService._consume_events()  [asyncio task in event loop]
    |
    | await self._job_service.enqueue(folder_path, force=False)
    v
JobQueueStore JSONL append  (atomic via temp+replace)
    |
    | JobWorker polls every 1s
    v
JobWorker._process_job(job)
    |
    | await indexing_service._run_indexing_pipeline(request, force=False)
    v
ManifestTracker.load(folder_path)  →  prior manifest
    |
    | mtime fast-path: O(1) for ~95% unchanged files
    v
ChunkEvictionService.compute_diff_and_evict()
    |
    | only changed/new files pass through
    v
EmbeddingGenerator.embed_texts(new_chunk_texts)
    |
    | EmbeddingCache.get(text, model)  →  HIT: reuse vector (0 API call)
    |                                  →  MISS: provider API call → cache.put()
    v
StorageBackendProtocol.upsert_documents()
    |
    v
ManifestTracker.save(updated_manifest)
    |
    v
JobWorker marks job DONE
    |
    | self._query_cache.invalidate_all()
    v
QueryCache cleared  (next query hits storage backend fresh)
```

### Flow 2: Query with Cache

```
POST /query  (TCP or UDS transport — identical handler)
    |
    v
query_router  →  QueryService.execute_query(request)
    |
    | QueryCache.get(request)
    |   --> HIT:  return cached QueryResponse  (~0ms, no API calls)
    |   --> MISS: continue
    v
EmbeddingGenerator.embed_query(request.query)
    |
    | EmbeddingCache.get(query_text, model)
    |   --> HIT:  return cached vector
    |   --> MISS: provider API call  →  cache.put()
    v
StorageBackendProtocol.vector_search() / keyword_search()
    |
    | [optional reranker]
    v
QueryResponse assembled
    |
    | QueryCache.put(request, response)
    v
return QueryResponse
```

### Flow 3: Dual Transport Startup

```
cli()  →  run(state_dir=..., uds_path=None)
    |
    | auto-compute: uds_path = state_dir / "agent-brain.sock"
    v
RuntimeState(port=PORT, uds_path=uds_path, uds_url=...)
    |
    | write_runtime()  →  runtime.json (both TCP port and UDS path)
    v
asyncio.run(_serve_both())
    |
    | asyncio.gather(
    |   tcp_server.serve(),    # lifespan="on"  → runs lifespan(), populates app.state
    |   uds_server.serve(),    # lifespan="off" → shares app.state, no re-init
    | )
    v
[Both transports ready — same request handlers, same app.state]
```

---

## Architectural Patterns

### Pattern 1: Cache Injection via Constructor (Testability First)

**What:** Pass cache objects as optional `None`-default constructor parameters to services.

**When to use:** Any service where caching is an optimization, not a hard requirement. Tests pass `None` (no mock needed). Production lifespan passes real cache instance.

**Trade-offs:** No global cache state. Tests remain fast (no cache warm-up needed). Adding a cache to a service never breaks existing callers.

```python
class QueryService:
    def __init__(self, ..., query_cache: "QueryCache | None" = None):
        self._query_cache = query_cache
```

### Pattern 2: Thread-to-Asyncio Bridge via `run_coroutine_threadsafe`

**What:** watchdog runs event handlers in OS-managed threads. The job queue lives in the asyncio event loop. `asyncio.run_coroutine_threadsafe(coro, loop)` is the only thread-safe way to submit work to a running event loop.

**When to use:** Any time a blocking library (watchdog, DB driver, subprocess) needs to trigger an asyncio coroutine.

**Trade-offs:** Requires capturing the event loop reference in the coroutine that starts the thread, before the thread starts. Use `asyncio.get_running_loop()` inside `FileWatcherService.start()` and pass it to each `DebouncedFolderHandler`. Do NOT use `asyncio.Queue.put_nowait()` from a thread — it is not thread-safe.

### Pattern 3: Dual Uvicorn Server with Shared App State

**What:** Two `uvicorn.Server` instances reference the same `app` object. TCP server sets `lifespan="on"`. UDS server sets `lifespan="off"`. Both run via `asyncio.gather()`.

**When to use:** When local performance (UDS) and remote access (TCP health check) are both needed without running two separate processes.

**Trade-offs:** Both servers share `app.state` — the TCP lifespan initializes it once, UDS server sees it immediately. The second server must override `install_signal_handlers()` to prevent duplicate signal registration. If TCP startup fails, `app.state` will be uninitialized when UDS starts — add startup order protection by sequencing `tcp_server.serve()` startup before exposing the UDS socket.

### Pattern 4: Debounce via `threading.Timer` Cancel-Restart

**What:** On each filesystem event, cancel the pending timer and start a new one. The handler function fires only after N seconds of silence.

**When to use:** File editors typically emit multiple events per logical "save" (write to temp → atomic rename = 2+ events). 30s default ensures a full build/regeneration cycle completes before triggering reindex.

**Trade-offs:** Events during active editing are silently batched into one job. A `threading.Lock` is required because `on_any_event` may be called from multiple OS threads concurrently. The timer's thread reference must be properly cancelled on `FileWatcherService.stop()` to avoid a leak.

---

## Anti-Patterns

### Anti-Pattern 1: Running lifespan on Both Servers

**What people do:** Pass `lifespan="on"` to both TCP and UDS `uvicorn.Config`.

**Why it's wrong:** `lifespan()` in `main.py` initializes ChromaDB (opens file locks), BM25Manager (loads pickled index), PostgreSQL pool (opens connections), and all services. Running it twice from the same process against the same persistent directories causes resource conflicts and state corruption.

**Do this instead:** `lifespan="off"` on the UDS server. Both servers share the same `app` object — `app.state` is populated by the TCP server's lifespan and is immediately visible to the UDS server's handlers.

### Anti-Pattern 2: Cache Logic Inside IndexingService

**What people do:** Add cache lookup directly inside `IndexingService._run_indexing_pipeline()`, calling the provider directly.

**Why it's wrong:** `QueryService` also calls `EmbeddingGenerator.embed_query()`. Putting cache logic in `IndexingService` means query-time embeddings bypass the cache entirely.

**Do this instead:** Cache logic belongs inside `EmbeddingGenerator.embed_texts()`. Every embedding call — indexing and query both — goes through this single method and benefits from caching automatically.

### Anti-Pattern 3: Cache Key Without Model Name

**What people do:** Key the embedding cache on `sha256(text)` alone.

**Why it's wrong:** When the provider changes from `text-embedding-3-large` (3072d) to `text-embedding-3-small` (1536d), the cache serves the old 3072d vectors. The vector search then receives mismatched dimensions and crashes.

**Do this instead:** Key on `sha256(f"{model}:{text}")`. Call `embedding_cache.invalidate_all()` when the provider settings change.

### Anti-Pattern 4: Query Cache Without Invalidation Hooks

**What people do:** Cache query results with TTL only, relying entirely on expiry.

**Why it's wrong:** With a 5-minute TTL, files indexed by the watcher are invisible to queries for up to 5 minutes. This defeats the purpose of auto-reindex: the files are indexed but search results are stale.

**Do this instead:** `JobWorker` calls `query_cache.invalidate_all()` immediately when job status transitions to `DONE`. TTL is a secondary safety net.

### Anti-Pattern 5: Watcher Jobs with force=True

**What people do:** Set `force=True` on watcher-triggered indexing jobs to ensure everything is re-processed.

**Why it's wrong:** `force=True` bypasses `ManifestTracker`. On a 10K-file codebase, every watcher event triggers re-embedding of all 10K files. API costs and indexing time become proportional to codebase size rather than change size.

**Do this instead:** Always `force=False` for watcher-triggered jobs. `ManifestTracker`'s mtime fast-path handles ~95% of unchanged files in O(1). The changed files are identified correctly without a full re-scan.

### Anti-Pattern 6: FileWatcherService Directly Calls IndexingService

**What people do:** Skip the job queue and call `indexing_service.start_indexing()` directly from `_consume_events()`.

**Why it's wrong:** The job queue provides serialization (one job at a time), timeout protection, progress tracking, cancellation, and JSONL persistence for crash recovery. Bypassing it means watcher-triggered jobs have none of these guarantees. Two rapid watcher events could trigger concurrent indexing.

**Do this instead:** Always route through `job_service.enqueue()`. The job queue serializes correctly and the existing `JobWorker` poll loop handles the rest.

---

## New External Dependencies

| Library | Purpose | Status | Confidence |
|---------|---------|--------|-----------|
| `watchdog` | Cross-platform filesystem events | New explicit dep | HIGH — well-established, used by uvicorn `--reload` internally |
| `cachetools` | LRUCache + TTLCache primitives | Verify if transitive dep | HIGH — check `poetry show cachetools`; likely present via LlamaIndex |
| `diskcache` | Optional disk persistence for embedding cache (SQLite-backed) | New optional dep | MEDIUM — clean API, asyncio-incompatible natively (use `asyncio.to_thread`) |

**Verify before implementing:**
```bash
cd agent-brain-server && poetry show cachetools  # Likely already present
cd agent-brain-server && poetry show watchdog    # Likely already present (uvicorn dep)
```

If `watchdog` is already installed transitively but not declared as a direct dependency, add it to `pyproject.toml` to make the dependency explicit.

---

## Integration Points Summary

| Boundary | How | Risk |
|----------|-----|------|
| watchdog thread → asyncio event loop | `asyncio.run_coroutine_threadsafe()` | Must capture loop before starting thread; loop reference can go stale if event loop restarts |
| `FileWatcherService` → `JobQueueService` | Direct method call `enqueue()` | Both live in `app.state`, both injected by lifespan; no risk |
| `JobWorker` → `QueryCache` | Direct call `invalidate_all()` on job DONE | `QueryCache` injected as optional; no-op if None |
| `EmbeddingGenerator` → `EmbeddingCache` | Direct call `get()`/`put()` | Optional; no-op if None |
| UDS server ↔ TCP server | Shared module-level `app` object | `lifespan="off"` on UDS is mandatory — enforce in code, not just docs |
| `FolderRecord` migration | `data.get(key, default)` in `_load_jsonl()` | Existing JSONL files missing new fields read as defaults — backward compat |

---

## Build Order (Phase Dependencies)

Ordered by: (1) independent of other v8 features, (2) required by later features, (3) highest risk shipped last.

**Phase 1 — Embedding Cache**
Independent. No other v8 feature requires this, but all watcher-triggered jobs benefit from it being present first.
- New: `services/embedding_cache.py`
- Modify: `indexing/embedding.py` (add cache bypass in `embed_texts`)
- Modify: `api/main.py` lifespan (create `EmbeddingCache`, wire into `EmbeddingGenerator`)
- Modify: `config/settings.py` (add `AGENT_BRAIN_EMBED_CACHE_SIZE`)

**Phase 2 — Query Cache**
Independent. Requires `JobWorker` modification for invalidation hook.
- New: `services/query_cache.py`
- Modify: `services/query_service.py` (check cache at top of `execute_query`)
- Modify: `job_queue/job_worker.py` (call `invalidate_all()` on DONE)
- Modify: `api/main.py` lifespan (create `QueryCache`, inject into `QueryService` and `JobWorker`)
- Modify: `config/settings.py` (add `AGENT_BRAIN_QUERY_CACHE_TTL`, `AGENT_BRAIN_QUERY_CACHE_SIZE`)

**Phase 3 — File Watcher + Background Incremental**
Depends on Phase 1 (embedding cache should be present so watcher jobs benefit from it).
- Modify: `services/folder_manager.py` (`FolderRecord` + `_load_jsonl` backward compat)
- Modify: `models/folders.py` (add watch fields to API request/response models)
- New: `services/file_watcher_service.py`
- Modify: `api/routers/folders.py` (pass watch params to watcher on folder add/remove)
- Modify: `api/main.py` lifespan (start/stop `FileWatcherService`)

**Phase 4 — UDS Transport**
Independent of phases 1-3. Highest blast radius (touches server startup). Ship last.
- Modify: `runtime.py` (add `uds_path`, `uds_url` to `RuntimeState`)
- Modify: `config/settings.py` (add `AGENT_BRAIN_UDS_ENABLED`, `AGENT_BRAIN_UDS_PATH`)
- Modify: `api/main.py` `run()` function (dual `uvicorn.Server` with `asyncio.gather`)
- Modify: `agent-brain-cli` (prefer `uds_url` from `runtime.json` for local calls)

---

## Scaling Considerations

This is a local-first single-user system. Scale targets are single developer / single project.

| Concern | v7.0 Baseline | v8.0 Impact |
|---------|--------------|-------------|
| Embedding API costs | Charged per chunk on every reindex | Cache eliminates API calls for unchanged content; amortizes cost to near-zero after first full index |
| Query latency | Full embed+search per query (~50-200ms) | Cache hit: ~0ms; miss: same as before |
| File watcher overhead | N/A | watchdog uses inotify/FSEvents/kqueue (OS-native); near-zero CPU when idle |
| Many watched folders | N/A | Single `Observer` thread handles all watches; no per-folder threads |
| UDS vs TCP throughput | TCP loopback ~1ms overhead | UDS eliminates TCP stack; relevant for high-frequency CLI polling (`jobs --watch`) |

---

## Sources

- Uvicorn settings (UDS option): [uvicorn.dev/settings](https://uvicorn.dev/settings/) — HIGH confidence
- Uvicorn dual-server asyncio pattern: [github.com/Kludex/uvicorn/issues/541](https://github.com/Kludex/uvicorn/issues/541) — MEDIUM confidence (community-verified, not official docs)
- watchdog library: [pypi.org/project/watchdog](https://pypi.org/project/watchdog/) — HIGH confidence
- asyncio + watchdog thread bridge: [gist.github.com/mivade](https://gist.github.com/mivade/f4cb26c282d421a62e8b9a341c7c65f6) — MEDIUM confidence (community gist)
- cachetools TTLCache + LRUCache: [cachetools.readthedocs.io](https://cachetools.readthedocs.io/) — HIGH confidence
- diskcache SQLite-backed cache: [grantjenks.com/docs/diskcache](https://grantjenks.com/docs/diskcache/tutorial.html) — HIGH confidence
- Codebase read directly (HIGH confidence): `api/main.py`, `services/indexing_service.py`, `services/query_service.py`, `job_queue/job_worker.py`, `services/folder_manager.py`, `services/manifest_tracker.py`, `indexing/embedding.py`, `storage/protocol.py`, `config/settings.py`, `runtime.py`

---

*Architecture research for: Agent Brain v8.0 Performance & DX*
*Researched: 2026-03-06*
