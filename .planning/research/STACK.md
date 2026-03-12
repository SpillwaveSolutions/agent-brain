# Stack Research — v8.0 Performance & Developer Experience

**Domain:** File watching, embedding/query caching, hybrid UDS+TCP transport for local RAG service
**Researched:** 2026-03-06
**Confidence:** HIGH (core libraries), MEDIUM (dual-transport pattern)

---

## Executive Summary

v8.0 adds five NEW capabilities to the existing Agent Brain RAG system. **CRITICAL**: This stack analysis covers ONLY what's NEW — the existing validated stack (FastAPI, ChromaDB, LlamaIndex, PostgreSQL, Poetry, Click, etc.) is already in place and NOT re-covered here.

**Key findings:**
- **File watching**: `watchfiles` (Rust-backed, async-native, already a Uvicorn dependency) wins clearly over `watchdog`
- **Embedding cache**: `aiosqlite` + stdlib `hashlib` — persistent across restarts, async-safe, zero new heavy deps
- **Query cache**: `cachetools.TTLCache` with `asyncio.Lock` — lightweight, in-memory, TTL-based invalidation
- **UDS transport**: Uvicorn natively supports `--uds`; dual TCP+UDS requires two `uvicorn.Server` instances via `asyncio.gather()`
- **httpx CLI client**: Already in the stack; add `HTTPTransport(uds=...)` for UDS connection

---

## New Feature Requirements

| Feature | Stack Additions | Rationale |
|---------|----------------|-----------|
| File watcher (per-folder config, debounce) | `watchfiles ^1.1` | Already a Uvicorn transitive dep, asyncio-native, Rust-backed |
| Embedding cache (SHA256 → vector, persistent) | `aiosqlite ^0.20` | Async SQLite, persists across restarts, no extra services |
| Query cache with TTL | `cachetools ^7.0` | Already used in ecosystem; TTLCache + asyncio.Lock pattern |
| Background incremental updates | stdlib `asyncio` | Task creation + watchfiles event loop integration |
| UDS transport (hybrid TCP + UDS) | Uvicorn config only | Native `--uds` flag; two-server pattern for dual binding |

---

## Recommended Stack (NEW Components Only)

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| watchfiles | ^1.1.1 | File system event watching with asyncio | Rust-backed via `notify` crate; `awatch()` is a native async generator; debounce built into Rust layer (default 1600ms, configurable); already a transitive dependency of Uvicorn — zero new install cost |
| aiosqlite | ^0.20.0 | Async SQLite for persistent embedding cache | Non-blocking async wrapper around stdlib sqlite3; SHA256 hash → embedding blob cache persists across server restarts; zero new services; fits local-first philosophy |
| cachetools | ^7.0.3 | In-memory TTL query cache | `TTLCache(maxsize=N, ttl=seconds)` is purpose-built for LRU+TTL semantics; 7.0.3 released 2026-03-05; pair with `asyncio.Lock` for async safety |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | ^0.27 (already present) | CLI UDS transport client | Use `httpx.AsyncHTTPTransport(uds="/path/to/socket")` when CLI detects local instance; already in agent-brain-cli dependencies |

### Development Tools

No new dev tooling needed. Existing Black, Ruff, mypy, pytest coverage all apply.

---

## Installation (NEW Dependencies Only)

```bash
# agent-brain-server pyproject.toml additions
poetry add watchfiles        # file watcher (^1.1)
poetry add aiosqlite         # async SQLite embedding cache (^0.20)
poetry add cachetools        # TTL query cache (^7.0)

# agent-brain-cli pyproject.toml — httpx already present; no additions needed

# Verify watchfiles not already pulled as transitive dep before adding
poetry show watchfiles
```

**IMPORTANT**: `cachetools` requires `types-cachetools` for mypy strict mode:
```bash
poetry add --group dev types-cachetools
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| watchfiles ^1.1 | watchdog ^4.0 | Use watchdog only if Windows-first deployment and inotify/FSEvents not available; watchdog requires explicit asyncio bridging via threading.Event or hachiko wrapper; watchfiles is Uvicorn's own choice since v0.18 |
| aiosqlite for embedding cache | diskcache ^5.6 | Use diskcache if cache needs shared across multiple processes; aiosqlite preferred because it's async-native, diskcache is sync-only (last release 2023-08-31), would require run_in_executor wrapping |
| aiosqlite for embedding cache | Redis | Use Redis only for distributed multi-machine deployments; violates local-first philosophy, adds service dependency |
| cachetools TTLCache | aiocache | Use aiocache for multi-backend needs (Redis, memcached); cachetools is simpler, pure Python, no dependencies, fits single-process FastAPI server |
| cachetools TTLCache | functools.lru_cache | Use lru_cache for sync code without TTL; no TTL support, not thread-safe with async code |
| Two uvicorn.Server instances | nginx reverse proxy | Use nginx only in production deployment behind load balancer; for local developer use, two-server pattern is self-contained |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| watchdog | Requires threading.Event bridge for asyncio; watchfiles is already in Uvicorn's dependency tree, zero cost; watchdog adds ~3MB and threading complexity | watchfiles awatch() |
| diskcache | Last release 2023-08-31 (unmaintained); sync-only API requires run_in_executor in async context; adds C extension compile step | aiosqlite (async-native, stdlib-backed) |
| Redis for caching | Adds external service dependency; violates local-first philosophy; overkill for single-process server | cachetools TTLCache (in-memory) + aiosqlite (persistent) |
| celery / rq for background tasks | Heavy frameworks for simple asyncio task; existing JSONL job queue already handles indexing jobs | asyncio.create_task() wrapping watchfiles awatch() loop |
| threading.Thread for watcher | Creates thread-safety complexity with asyncio event loop; watchfiles awatch() runs natively in the same event loop | watchfiles awatch() as asyncio background task |
| aiocache | Adds dependency for use case that cachetools covers; aiocache's SQLite backend has poor async performance | cachetools + aiosqlite separately |

---

## Integration Patterns

### Pattern 1: watchfiles Per-Folder Watcher with Debounce

```python
import asyncio
from watchfiles import awatch, Change

async def folder_watcher(
    folders: list[str],
    debounce_ms: int = 30_000,  # 30s default per PROJECT.md spec
    watch_filter: callable = None,
) -> None:
    """Watch multiple folders; yield batched changes with debounce."""
    async for changes in awatch(
        *folders,
        debounce=debounce_ms,     # watchfiles native debounce (ms)
        watch_filter=watch_filter,
        recursive=True,
    ):
        # changes is set[tuple[Change, str]] — batched by debounce window
        paths_changed = {path for _, path in changes}
        await trigger_incremental_index(paths_changed)
```

**Per-folder read-only vs auto-reindex config** is handled at the application layer:
- Load folder config (already stored in JSONL manifest/folder config from v7.0)
- Filter `changes` set to exclude paths under read-only folders before calling indexer
- watchfiles itself watches all paths; the routing decision is a Python dict lookup

### Pattern 2: Persistent Embedding Cache with aiosqlite

```python
import asyncio
import hashlib
import json
import aiosqlite
from pathlib import Path

class EmbeddingCache:
    """SHA256 content hash → embedding vector, persisted in SQLite."""

    def __init__(self, cache_path: Path) -> None:
        self._path = cache_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self._path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                content_hash TEXT PRIMARY KEY,
                model_id      TEXT NOT NULL,
                embedding     BLOB NOT NULL,
                created_at    REAL NOT NULL
            )
        """)
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_model ON embeddings(model_id)"
        )
        await self._db.commit()

    @staticmethod
    def content_hash(text: str, model_id: str) -> str:
        """Cache key: SHA256(content + model_id) — model change invalidates."""
        return hashlib.sha256(f"{model_id}:{text}".encode()).hexdigest()

    async def get(self, text: str, model_id: str) -> list[float] | None:
        hash_key = self.content_hash(text, model_id)
        async with self._db.execute(
            "SELECT embedding FROM embeddings WHERE content_hash = ? AND model_id = ?",
            (hash_key, model_id),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return json.loads(row[0])
        return None

    async def put(self, text: str, model_id: str, embedding: list[float]) -> None:
        hash_key = self.content_hash(text, model_id)
        import time
        await self._db.execute(
            "INSERT OR REPLACE INTO embeddings VALUES (?, ?, ?, ?)",
            (hash_key, model_id, json.dumps(embedding), time.time()),
        )
        await self._db.commit()
```

### Pattern 3: In-Memory Query Cache with TTL

```python
import asyncio
from cachetools import TTLCache

class QueryCache:
    """In-memory LRU+TTL cache for query results."""

    def __init__(self, maxsize: int = 512, ttl: int = 300) -> None:
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._lock = asyncio.Lock()  # asyncio.Lock for async safety

    def _cache_key(self, query: str, mode: str, top_k: int) -> str:
        return f"{mode}:{top_k}:{query}"

    async def get(self, query: str, mode: str, top_k: int) -> list | None:
        async with self._lock:
            return self._cache.get(self._cache_key(query, mode, top_k))

    async def put(self, query: str, mode: str, top_k: int, results: list) -> None:
        async with self._lock:
            self._cache[self._cache_key(query, mode, top_k)] = results

    async def invalidate_all(self) -> None:
        """Call after any indexing operation to prevent stale results."""
        async with self._lock:
            self._cache.clear()
```

**TTL invalidation strategy**: Clear entire query cache on every index write.
Query results reference chunk IDs that may be evicted/replaced during indexing.
Cache hit rates remain high for read-heavy developer workflows between index runs.

### Pattern 4: Dual TCP + UDS Transport

Uvicorn does NOT support single-instance dual binding. The solution is two `uvicorn.Server` instances sharing the same FastAPI app object:

```python
import asyncio
import uvicorn
from app.main import app  # single FastAPI app instance

async def serve_dual_transport(
    host: str = "127.0.0.1",
    port: int = 8000,
    uds_path: str = "/tmp/agent-brain.sock",
) -> None:
    """Run both TCP (for health/remote) and UDS (for local speed)."""
    tcp_config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    uds_config = uvicorn.Config(app, uds=uds_path, log_level="warning")

    tcp_server = uvicorn.Server(tcp_config)
    uds_server = uvicorn.Server(uds_config)

    # Run both; stop when either exits (e.g., SIGTERM)
    done, pending = await asyncio.wait(
        [
            asyncio.create_task(tcp_server.serve()),
            asyncio.create_task(uds_server.serve()),
        ],
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
```

**CLI UDS client** uses httpx transport override:
```python
import httpx

def get_httpx_client(uds_path: str | None = None) -> httpx.AsyncClient:
    """Return async client that prefers UDS when available locally."""
    if uds_path and Path(uds_path).exists():
        transport = httpx.AsyncHTTPTransport(uds=uds_path)
        # URL host is ignored for UDS; use placeholder
        return httpx.AsyncClient(transport=transport, base_url="http://agent-brain")
    return httpx.AsyncClient(base_url="http://127.0.0.1:8000")
```

---

## Stack Patterns by Variant

**If offline / Ollama-only deployment:**
- All patterns apply unchanged — aiosqlite, cachetools, watchfiles are pure Python or Rust, no network required
- Embedding cache hit rate is especially high: Ollama models are deterministic for same content

**If performance is critical:**
- Increase `TTLCache(maxsize=1024)` for busier query patterns
- Use `debounce=5000` (5s) instead of 30s for faster developer feedback when latency matters more than API cost
- UDS transport is ~20% lower latency than TCP loopback for local CLI calls

**If running on Linux without inotify:**
- Set `force_polling=True` in `awatch()` — watchfiles falls back to polling automatically, but explicit is safer in container/CI environments

**If running on macOS development machine:**
- FSEvents (macOS-native) is used automatically by watchfiles Rust backend
- No special configuration needed

---

## Version Compatibility

| Package | Version | Compatible With | Notes |
|---------|---------|-----------------|-------|
| watchfiles ^1.1.1 | Python 3.9–3.14 | uvicorn ^0.18+ (transitive dep match) | Already in dependency graph; verify with `poetry show watchfiles` before explicit add |
| aiosqlite ^0.20.0 | Python 3.8+ | asyncio (stdlib) | Pure Python async wrapper; no C extensions; compatible with Python 3.10 server venv |
| cachetools ^7.0.3 | Python 3.8+ | asyncio.Lock (stdlib) | Thread lock not sufficient for async; must pair with asyncio.Lock, not threading.Lock |
| types-cachetools | matches cachetools | mypy strict | Required for mypy strict mode; add to dev dependencies group |
| httpx ^0.27 (existing) | Python 3.8+ | httpx.AsyncHTTPTransport(uds=...) | UDS transport is built-in; no separate package needed |

---

## What Already Exists (DO NOT ADD)

| Capability | Already Available | Location |
|------------|-------------------|----------|
| JSONL job queue for indexing | `services/job_queue.py` | Background index jobs dispatched here |
| Folder config storage | JSONL manifest from v7.0 | Per-folder metadata already persisted |
| httpx async client | `agent-brain-cli` deps | Just needs UDS transport configuration |
| asyncio task infrastructure | stdlib | `asyncio.create_task()` for background watcher |
| SHA256 content hashing | `hashlib` stdlib via v7.0 | ManifestTracker already uses SHA256 |
| Incremental indexing logic | `services/indexing_service.py` | Watcher calls existing IndexingService |

---

## Open Questions / Research Gaps

1. **watchfiles as explicit dep vs transitive**: Must verify with `poetry show watchfiles` in agent-brain-server venv before deciding whether to add explicitly. If already present as transitive dep of uvicorn, explicit pin preferred for stability.

2. **SQLite WAL mode for embedding cache**: Under concurrent read/write during indexing, WAL mode (`PRAGMA journal_mode=WAL`) may be needed. Test with concurrent aiosqlite connections before shipping.

3. **Query cache invalidation granularity**: Current recommendation is full cache clear on any write. If write-heavy use cases emerge, per-folder invalidation keyed by folder path would reduce cache churn. Defer until profiling shows it matters.

4. **UDS socket file path**: Must be stored in `runtime.json` (existing per-instance state file from v2.0 MULTI features) so CLI can discover the socket path without configuration.

---

## Sources

- [watchfiles PyPI — v1.1.1](https://pypi.org/project/watchfiles/) — version, Python support matrix
- [watchfiles awatch API docs](https://watchfiles.helpmanual.io/api/watch/) — debounce parameter (default 1600ms), watch_filter, recursive, force_polling
- [GitHub samuelcolvin/watchfiles](https://github.com/samuelcolvin/watchfiles) — Rust-backed via notify crate; Uvicorn replaced watchdog with watchfiles since v0.18
- [aiosqlite PyPI — v0.20](https://pypi.org/project/aiosqlite/) — async SQLite wrapper, Python 3.8+ support
- [cachetools PyPI — v7.0.3](https://pypi.org/project/cachetools/) — released 2026-03-05, TTLCache API
- [cachetools readthedocs v7.0.3](https://cachetools.readthedocs.io/en/stable/) — TTLCache(maxsize, ttl), thread safety note: NOT thread-safe, requires Lock
- [Uvicorn Settings docs](https://www.uvicorn.org/settings/) — `--uds` parameter for Unix domain socket binding; mutually exclusive with `--host/--port`
- [Multiple uvicorn instances gist](https://gist.github.com/tenuki/ff67f87cba5c4c04fd08d9c800437477) — asyncio.gather() pattern for dual TCP+UDS serving
- [HTTPX Transports docs](https://www.python-httpx.org/advanced/transports/) — `httpx.AsyncHTTPTransport(uds=...)` for UDS client connections
- [diskcache PyPI — v5.6.3](https://pypi.org/project/diskcache/) — last release 2023-08-31, sync-only (eliminated in favor of aiosqlite)

---

*Stack research for: v8.0 Performance & Developer Experience (file watching, caching, UDS transport)*
*Researched: 2026-03-06*
*Confidence: HIGH for watchfiles/aiosqlite/cachetools; MEDIUM for dual UDS+TCP server pattern (asyncio.gather approach confirmed via community gist, not official Uvicorn docs)*
