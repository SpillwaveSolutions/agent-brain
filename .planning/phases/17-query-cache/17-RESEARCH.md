# Phase 17: Query Cache - Research

**Researched:** 2026-03-12
**Domain:** In-memory query caching with TTL, index generation invalidation, and async Python
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| QCACHE-01 | Query results cached in-memory with configurable TTL (default 5 minutes) | cachetools.TTLCache or stdlib OrderedDict+timestamp; cachetools NOT in pyproject.toml — must be added |
| QCACHE-02 | Cache key includes index_generation counter — incremented on every successful reindex | index_generation does not exist yet; must be added as a module-level int on a new QueryCacheService |
| QCACHE-03 | GraphRAG and multi modes excluded from query cache (non-deterministic LLM extraction) | QueryMode.GRAPH and QueryMode.MULTI are the two enum values to exclude; detected at QueryService.execute_query time |
| QCACHE-04 | Global cache flush on any reindex job completion | JobWorker._process_job marks job DONE at line 361; call cache.invalidate_all() immediately after that |
| QCACHE-05 | Cache hit/miss metrics visible in `agent-brain status` output | Follow Phase 16 EmbeddingCacheService.get_stats() pattern; add query_cache dict to IndexingStatus model |
| QCACHE-06 | QUERY_CACHE_TTL and QUERY_CACHE_MAX_SIZE configurable via env vars or YAML | Follow Phase 16 EMBEDDING_CACHE_MAX_MEM_ENTRIES / EMBEDDING_CACHE_MAX_DISK_MB pattern in Settings |
| XCUT-04 | All new config options documented in env vars reference and YAML config | CONFIGURATION.md + PROVIDER_CONFIGURATION.md need new sections; follow Phase 16 CHANGELOG.md additions |
</phase_requirements>

## Summary

Phase 17 adds an in-memory query result cache so that repeated identical queries skip the ChromaDB/PostgreSQL vector search and BM25 retrieval entirely, returning sub-millisecond results from memory. The cache must invalidate automatically on every successful reindex completion — including watcher-triggered auto-reindex jobs — so users never see stale results.

The implementation follows the established Phase 16 pattern: a standalone service class (`QueryCacheService`) with a module-level singleton, injected into `QueryService` at the call site, wired in `api/main.py` lifespan, and exposed in `/health/status`. The key architectural decision is the cache key: it must include both the full query fingerprint (query text + mode + top_k + filters) **and** an `index_generation` counter that increments on every job DONE event, making post-reindex cache misses automatic without requiring explicit per-entry invalidation.

`cachetools` is the prescribed library (roadmap decision) but is NOT currently in `pyproject.toml`. It must be added as a dependency. `cachetools.TTLCache` is thread-safe for single-threaded asyncio use but requires an `asyncio.Lock` for compound read-modify-write operations. `graph` and `multi` query modes must be unconditionally excluded because they involve LLM entity extraction and non-deterministic graph traversal — caching them would surface stale relational data after any schema or content change.

**Primary recommendation:** New `QueryCacheService` in `services/query_cache.py` using `cachetools.TTLCache`, singleton pattern matching Phase 16, wired at lifespan startup via `app.state.query_cache`, and invalidated in `JobWorker._process_job` immediately after `job.status = JobStatus.DONE`.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| cachetools | ^5.3 | TTLCache + LRUCache with thread-safe primitives | De-facto Python in-memory cache library; TTLCache combines size limit and TTL expiry in one data structure |
| asyncio.Lock | stdlib | Serializes concurrent cache writes | Same pattern as Phase 16 EmbeddingCacheService._lock |
| Python OrderedDict | stdlib | Fallback if cachetools not used | Already used in Phase 16 for in-memory LRU; but cachetools TTLCache handles TTL without manual timestamp tracking |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hashlib.sha256 | stdlib | Deterministic cache key from query params | Converts arbitrary QueryRequest fields into a fixed-length key; same approach as embedding cache key |
| time.monotonic | stdlib | TTL expiry tracking fallback | Only needed if using pure stdlib instead of cachetools |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| cachetools.TTLCache | stdlib dict + timestamp | cachetools handles eviction and TTL expiry automatically; stdlib requires manual management and is error-prone |
| cachetools.TTLCache | redis/memcached | Redis requires a separate service; overkill for local-first single-process server |
| Global cache flush on reindex | Per-key TTL expiry only | TTL alone cannot guarantee freshness after watcher-triggered reindex which happens within seconds of file changes; global flush is required by QCACHE-04 |

**Installation:**
```bash
cd agent-brain-server && poetry add cachetools
# cachetools includes type stubs in cachetools-stubs; add for mypy:
poetry add --group dev types-cachetools
```

## Architecture Patterns

### Recommended Project Structure
```
agent_brain_server/
├── services/
│   ├── query_cache.py       # NEW: QueryCacheService (this phase)
│   ├── embedding_cache.py   # Phase 16 — reference pattern
│   ├── query_service.py     # MODIFIED: inject QueryCacheService
│   └── ...
├── job_queue/
│   └── job_worker.py        # MODIFIED: call cache.invalidate_all() on DONE
├── api/
│   ├── main.py              # MODIFIED: initialize QueryCacheService in lifespan
│   └── routers/
│       └── health.py        # MODIFIED: include query_cache in status response
├── models/
│   └── health.py            # MODIFIED: add query_cache field to IndexingStatus
└── config/
    └── settings.py          # MODIFIED: QUERY_CACHE_TTL, QUERY_CACHE_MAX_SIZE
```

### Pattern 1: QueryCacheService with cachetools TTLCache

**What:** A service wrapping `cachetools.TTLCache` with an `asyncio.Lock`, an `index_generation` counter, and hit/miss metrics.

**When to use:** When `QueryService.execute_query` is called with a cacheable mode (not graph, not multi). The service encapsulates all cache logic so `QueryService` stays thin.

**Example:**
```python
# services/query_cache.py
import asyncio
import hashlib
import json
import logging
from typing import Any

from cachetools import TTLCache

logger = logging.getLogger(__name__)

_EXCLUDED_MODES = {"graph", "multi"}

_DEFAULT_TTL = 300       # 5 minutes
_DEFAULT_MAX_SIZE = 256  # entries


class QueryCacheService:
    """In-memory TTL cache for query results.

    Cache key: SHA-256(json(query_params)):index_generation
    Excluded modes: graph, multi (non-deterministic LLM extraction)

    index_generation is incremented on every successful reindex via
    invalidate_all(). This makes post-reindex misses automatic — the
    generation suffix changes, so all old keys are orphaned and evicted
    when TTL expires or size limit is hit.

    asyncio.Lock is acquired only for writes and invalidation. Reads
    from TTLCache are thread-safe for single asyncio thread (no lock needed
    on get, consistent with Phase 16 pattern).
    """

    def __init__(self, ttl: int = _DEFAULT_TTL, max_size: int = _DEFAULT_MAX_SIZE) -> None:
        self._ttl = ttl
        self._max_size = max_size
        self._cache: TTLCache[str, Any] = TTLCache(maxsize=max_size, ttl=ttl)
        self._lock: asyncio.Lock = asyncio.Lock()
        self._index_generation: int = 0
        self._hits: int = 0
        self._misses: int = 0

    def make_cache_key(self, request_params: dict[str, Any]) -> str:
        """Compute deterministic cache key from query parameters and generation.

        Key format: SHA-256(canonical_json(params)):generation
        """
        canonical = json.dumps(request_params, sort_keys=True, default=str)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"{digest}:{self._index_generation}"

    def get(self, key: str) -> Any | None:
        """Look up cached result. No lock needed — single asyncio thread."""
        result = self._cache.get(key)
        if result is not None:
            self._hits += 1
        else:
            self._misses += 1
        return result

    async def put(self, key: str, value: Any) -> None:
        """Store result in cache under write lock."""
        async with self._lock:
            self._cache[key] = value

    async def invalidate_all(self) -> None:
        """Flush all cached results and increment index_generation.

        Called by JobWorker on every successful reindex completion.
        Incrementing generation automatically invalidates all future
        lookups against old-generation keys.
        """
        async with self._lock:
            self._index_generation += 1
            self._cache.clear()
        logger.debug(
            "Query cache invalidated; new generation=%d", self._index_generation
        )

    def get_stats(self) -> dict[str, Any]:
        """Return hit/miss counters and current cache size."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total) if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "cached_entries": len(self._cache),
            "index_generation": self._index_generation,
        }

    @staticmethod
    def is_cacheable_mode(mode: str) -> bool:
        """Return False for graph and multi modes (QCACHE-03)."""
        return mode not in _EXCLUDED_MODES


# Module-level singleton (Phase 16 pattern)
_query_cache: QueryCacheService | None = None


def get_query_cache() -> QueryCacheService | None:
    return _query_cache


def set_query_cache(cache: QueryCacheService) -> None:
    global _query_cache
    _query_cache = cache


def reset_query_cache() -> None:
    global _query_cache
    _query_cache = None
```

### Pattern 2: Integrating cache into QueryService.execute_query

**What:** Wrap the existing `execute_query` method with cache check-before/store-after logic. Cache key is built from all fields that affect results.

**When to use:** In `QueryService.execute_query`, inject `QueryCacheService` and guard around the retrieval pipeline.

**Example:**
```python
# In QueryService.__init__
def __init__(self, ..., query_cache: QueryCacheService | None = None) -> None:
    ...
    self.query_cache = query_cache

# In QueryService.execute_query (before calling _execute_*_query)
async def execute_query(self, request: QueryRequest) -> QueryResponse:
    # Check cache first (QCACHE-01, QCACHE-03)
    cache = self.query_cache
    if cache is not None and cache.is_cacheable_mode(request.mode.value):
        cache_params = {
            "query": request.query,
            "mode": request.mode.value,
            "top_k": request.top_k,
            "similarity_threshold": request.similarity_threshold,
            "alpha": request.alpha,
            "source_types": sorted(request.source_types or []),
            "languages": sorted(request.languages or []),
            "file_paths": sorted(request.file_paths or []),
        }
        cache_key = cache.make_cache_key(cache_params)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    # ... existing query execution logic ...

    # Store result in cache (QCACHE-01)
    if cache is not None and cache.is_cacheable_mode(request.mode.value):
        await cache.put(cache_key, response)

    return response
```

### Pattern 3: JobWorker cache invalidation on DONE

**What:** After marking `job.status = JobStatus.DONE` in `_process_job`, call `query_cache.invalidate_all()` before persisting the job record.

**When to use:** Only on DONE status (not FAILED, not CANCELLED). A failed job does not change the index state, so no invalidation is needed.

**Example:**
```python
# In JobWorker.__init__
self._query_cache: QueryCacheService | None = None

def set_query_cache(self, cache: QueryCacheService | None) -> None:
    self._query_cache = cache

# In JobWorker._process_job, immediately after job.status = JobStatus.DONE:
if self._query_cache is not None:
    await self._query_cache.invalidate_all()
    logger.debug("Query cache invalidated after job %s completed", job.id)
```

### Pattern 4: Lifespan wiring in api/main.py

**What:** Create `QueryCacheService` in lifespan, set the singleton, attach to `app.state`, pass to `QueryService` and `JobWorker`.

**Example:**
```python
# In lifespan, after embedding_cache initialization:
from agent_brain_server.services.query_cache import (
    QueryCacheService, set_query_cache
)

query_cache = QueryCacheService(
    ttl=settings.QUERY_CACHE_TTL,
    max_size=settings.QUERY_CACHE_MAX_SIZE,
)
set_query_cache(query_cache)
app.state.query_cache = query_cache

# Create query service with cache
query_service = QueryService(
    storage_backend=storage_backend,
    query_cache=query_cache,
)

# Wire into JobWorker
_job_worker.set_query_cache(query_cache)
```

### Pattern 5: health.py status integration

**What:** Follow Phase 16 embedding_cache pattern exactly — fetch stats from `app.state.query_cache` and include as `query_cache` key in status response.

**Example:**
```python
# In health.py indexing_status()
query_cache_info: dict[str, Any] | None = None
query_cache_svc = getattr(request.app.state, "query_cache", None)
if query_cache_svc is not None:
    query_cache_info = query_cache_svc.get_stats()

# Add to IndexingStatus:
# query_cache=query_cache_info
```

### Anti-Patterns to Avoid

- **Caching graph/multi modes:** Non-deterministic LLM entity extraction means results vary across calls. NEVER cache these modes.
- **Using asyncio.Lock for reads:** TTLCache is safe for concurrent reads in a single asyncio thread. Only lock writes and invalidation.
- **Partial cache invalidation:** The REQUIREMENTS.md explicitly declares folder-level cache invalidation out of scope for v8.0. Do not implement it.
- **Persisting query cache to disk:** Query results are large and stale quickly. Unlike embeddings, no disk persistence is needed or specified.
- **Using `asyncio.Event` or `asyncio.Queue` for invalidation signals:** Direct method call `invalidate_all()` from JobWorker is simpler and correct.
- **Caching `QueryResponse` objects directly by reference:** Pydantic models are mutable via `model_copy`. Cache a `model_dump()` serialized copy OR the model itself since Pydantic models don't hold references to live DB connections.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TTL expiry tracking | Manual timestamp dict + cleanup loop | `cachetools.TTLCache` | TTLCache evicts expired entries lazily on access; no background cleanup task needed |
| Max size eviction | Custom LRU linked list | `cachetools.TTLCache(maxsize=N)` | Built-in LRU eviction when size limit is hit |
| Thread-safe cache invalidation | Multiple locks / complex state | `asyncio.Lock` on `invalidate_all` only | asyncio single-thread model means reads need no lock; only writes contend |
| Cache key uniqueness | UUID or sequential counter | SHA-256(json(params)):generation | Deterministic + compact; same approach as embedding cache |

**Key insight:** `cachetools.TTLCache` is a drop-in dict subclass. All standard dict reads are safe without locks in asyncio. Only writes (`__setitem__`, `clear`) need the lock because they can cause size evictions.

## Common Pitfalls

### Pitfall 1: Stale results after watcher-triggered reindex
**What goes wrong:** Watcher triggers a background reindex, job completes, but next identical query returns old cached result because cache TTL hasn't expired yet.
**Why it happens:** TTL alone does not provide freshness after reindex. The `invalidate_all()` call in JobWorker only works if JobWorker holds a reference to `QueryCacheService`.
**How to avoid:** Wire `set_query_cache(query_cache)` on `_job_worker` in lifespan, after both are created. Verify with a test: assert cache is cleared after `_process_job` completes with DONE status.
**Warning signs:** Cache hit rate stays non-zero after reindex in tests.

### Pitfall 2: Cache key collision between different filter combinations
**What goes wrong:** Two queries with different `source_types` or `languages` get the same cache key if list ordering is not normalized.
**Why it happens:** `json.dumps({"languages": ["python", "typescript"]})` != `json.dumps({"languages": ["typescript", "python"]})` — lists are order-sensitive.
**How to avoid:** Always sort list fields before building cache key: `sorted(request.source_types or [])`.
**Warning signs:** Test with swapped-order filters returns wrong cached results.

### Pitfall 3: Caching error responses
**What goes wrong:** A transient storage backend error produces a cached empty result. Subsequent calls return the empty cached response instead of retrying.
**Why it happens:** `execute_query` raises `RuntimeError` if not ready, but an unexpected exception might be caught and returned as an empty `QueryResponse`.
**How to avoid:** Only call `cache.put()` after a successful return from the query pipeline (no exception raised). Never cache within a try/except that swallows errors.

### Pitfall 4: asyncio.Lock not created in the right event loop
**What goes wrong:** `asyncio.Lock()` created at module import time (before the event loop starts) causes `DeprecationWarning` in Python 3.10 and `RuntimeError` in 3.12+.
**Why it happens:** Phase 16 solved this by creating the lock in `EmbeddingCacheService.__init__`, which is called inside the lifespan (already in the event loop). The query cache must follow the same pattern — create `QueryCacheService` inside lifespan, not at module level.
**How to avoid:** Never instantiate `QueryCacheService` at module import. Always create in `lifespan()`.

### Pitfall 5: mypy strict mode with cachetools
**What goes wrong:** `cachetools.TTLCache` typing requires `types-cachetools` stubs. Without them, mypy strict mode reports `error: Library stubs not installed for "cachetools"`.
**Why it happens:** `cachetools` ships no inline type stubs. `types-cachetools` must be a dev dependency.
**How to avoid:** `poetry add --group dev types-cachetools`. Verify with `poetry run mypy agent_brain_server` before push.

### Pitfall 6: QueryResponse serialization in cache
**What goes wrong:** Storing the `QueryResponse` Pydantic model directly works, but the stored object shares float list references with the original results. Mutations downstream would corrupt cached data.
**Why it happens:** Python objects are stored by reference. `TTLCache[str, QueryResponse]` stores the same object.
**How to avoid:** Since `QueryResponse` is a Pydantic model, mutations are unlikely in normal use. But for safety, verify the query router never mutates the returned `QueryResponse`. If mutation risk exists, cache `response.model_copy(deep=True)` or `response.model_dump()` and reconstruct on hit.

## Code Examples

Verified patterns from established codebase:

### Singleton pattern (Phase 16 reference)
```python
# Source: agent_brain_server/services/embedding_cache.py lines 525-557
_embedding_cache: EmbeddingCacheService | None = None

def get_embedding_cache() -> EmbeddingCacheService | None:
    return _embedding_cache

def set_embedding_cache(cache: EmbeddingCacheService) -> None:
    global _embedding_cache
    _embedding_cache = cache

def reset_embedding_cache() -> None:
    global _embedding_cache
    _embedding_cache = None
```

### JobWorker setter injection pattern (Phase 15 reference)
```python
# Source: agent_brain_server/job_queue/job_worker.py lines 88-105
def set_file_watcher_service(self, service: FileWatcherService | None) -> None:
    self._file_watcher_service = service

def set_folder_manager(self, manager: FolderManager | None) -> None:
    self._folder_manager = manager
```

### Health status dict inclusion (Phase 16 reference)
```python
# Source: agent_brain_server/api/routers/health.py lines 194-205
embedding_cache_info: dict[str, Any] | None = None
embedding_cache_svc = getattr(request.app.state, "embedding_cache", None)
if embedding_cache_svc is not None:
    try:
        disk_stats = await embedding_cache_svc.get_disk_stats()
        if disk_stats.get("entry_count", 0) > 0:
            mem_stats = embedding_cache_svc.get_stats()
            embedding_cache_info = {**mem_stats, **disk_stats}
    except Exception:
        pass
```

### IndexingStatus model field addition (Phase 16 reference)
```python
# Source: agent_brain_server/models/health.py lines 135-142
# Embedding cache status (Phase 16)
embedding_cache: dict[str, Any] | None = Field(
    default=None,
    description=(
        "Embedding cache status with hits, misses, hit_rate, entry_count, "
        "size_bytes. Omitted for fresh installs with empty cache."
    ),
)
```

### Settings pattern (Phase 16 reference)
```python
# Source: agent_brain_server/config/settings.py lines 81-83
# Embedding Cache Configuration (Phase 16)
EMBEDDING_CACHE_MAX_DISK_MB: int = 500
EMBEDDING_CACHE_MAX_MEM_ENTRIES: int = 1_000
EMBEDDING_CACHE_PERSIST_STATS: bool = False
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual dict + timestamp expiry | cachetools.TTLCache | Project decision (Phase 17) | Automatic expiry without background cleanup |
| Per-entry invalidation | index_generation counter + global flush | Phase 17 design | Simpler than tracking which cached results touched which indexed folders; O(1) invalidation |
| No query caching | TTL cache with generation counter | Phase 17 (new) | Sub-millisecond repeated queries |

**Deprecated/outdated:**
- Folder-level query cache invalidation: Explicitly out of scope in REQUIREMENTS.md. Do not implement.
- Semantic query cache (find similar cached queries): Out of scope. "Lookup cost exceeds query cost — anti-feature."

## Open Questions

1. **`types-cachetools` package name and version**
   - What we know: `cachetools` package does not bundle type stubs as of early 2026; `types-cachetools` is the companion stubs package on PyPI
   - What's unclear: Whether `types-cachetools` needs a version pin or can be `*` / unpinned for dev
   - Recommendation: Add `types-cachetools = "*"` to `[tool.poetry.group.dev.dependencies]` and verify with `poetry run mypy`; pin if CI fails

2. **Cache key for entity_types / relationship_types filter fields**
   - What we know: `QueryRequest` has `entity_types` and `relationship_types` fields that only apply to graph/multi modes
   - What's unclear: Whether to include them in the cache key for other modes (they would always be None, so they don't affect the hash)
   - Recommendation: Include them in the cache key dict anyway (normalized to sorted lists or empty). Consistent with "all fields that affect results" — no special-casing needed since graph/multi modes are excluded from caching entirely

3. **query_cache_info display threshold in /health/status**
   - What we know: Phase 16 omits `embedding_cache` from status when `entry_count == 0` (fresh installs)
   - What's unclear: Should query_cache be omitted when hits+misses == 0 (fresh start with no queries yet)?
   - Recommendation: Always include `query_cache` in status (unlike embedding_cache which has no-op on fresh install). Query cache stats are always meaningful since they accumulate per session.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.0 + pytest-asyncio 0.24.0 |
| Config file | `agent-brain-server/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `cd agent-brain-server && poetry run pytest tests/test_query_cache.py -x` |
| Full suite command | `cd agent-brain-server && poetry run pytest --cov=agent_brain_server` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QCACHE-01 | Cache hit on second identical query, no storage call | unit | `pytest tests/test_query_cache.py::test_cache_hit_returns_cached_result -x` | ❌ Wave 0 |
| QCACHE-01 | Cache TTL expiry causes storage call | unit | `pytest tests/test_query_cache.py::test_cache_ttl_expiry -x` | ❌ Wave 0 |
| QCACHE-02 | Cache key includes index_generation; different generations miss | unit | `pytest tests/test_query_cache.py::test_cache_key_includes_generation -x` | ❌ Wave 0 |
| QCACHE-03 | graph mode bypasses cache | unit | `pytest tests/test_query_cache.py::test_graph_mode_not_cached -x` | ❌ Wave 0 |
| QCACHE-03 | multi mode bypasses cache | unit | `pytest tests/test_query_cache.py::test_multi_mode_not_cached -x` | ❌ Wave 0 |
| QCACHE-04 | invalidate_all increments generation and clears cache | unit | `pytest tests/test_query_cache.py::test_invalidate_all_clears_cache -x` | ❌ Wave 0 |
| QCACHE-04 | JobWorker calls invalidate_all on DONE | unit | `pytest tests/test_query_cache.py::test_job_worker_invalidates_cache_on_done -x` | ❌ Wave 0 |
| QCACHE-05 | /health/status includes query_cache section | unit | `pytest tests/test_query_cache.py::test_status_includes_query_cache_stats -x` | ❌ Wave 0 |
| QCACHE-06 | QUERY_CACHE_TTL and QUERY_CACHE_MAX_SIZE respected | unit | `pytest tests/test_query_cache.py::test_settings_configure_cache -x` | ❌ Wave 0 |
| XCUT-04 | Config documented (manual verification) | manual | N/A — docs review | N/A |

### Sampling Rate
- **Per task commit:** `cd agent-brain-server && poetry run pytest tests/test_query_cache.py -x`
- **Per wave merge:** `cd agent-brain-server && poetry run pytest --cov=agent_brain_server`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_query_cache.py` — covers QCACHE-01 through QCACHE-06 and XCUT-04 test points above
- [ ] No additional conftest needed — existing `conftest.py` provides `tmp_path` fixture

## Sources

### Primary (HIGH confidence)
- Codebase — `agent_brain_server/services/embedding_cache.py` — full Phase 16 implementation used as reference pattern
- Codebase — `agent_brain_server/job_queue/job_worker.py` — JobStatus.DONE transition point at line 361
- Codebase — `agent_brain_server/models/query.py` — `QueryMode.GRAPH` and `QueryMode.MULTI` enum values
- Codebase — `agent_brain_server/api/routers/health.py` — embedding_cache inclusion pattern in indexing_status
- Codebase — `agent_brain_server/config/settings.py` — settings pattern for Phase 16 cache config
- Codebase — `agent_brain_server/api/main.py` — lifespan wiring pattern for Phase 15/16 services

### Secondary (MEDIUM confidence)
- cachetools documentation (https://cachetools.readthedocs.io/) — TTLCache is dict subclass with LRU eviction + TTL; thread-safe for single-threaded asyncio (no lock on reads)
- `.planning/REQUIREMENTS.md` — QCACHE-01 through QCACHE-06 and XCUT-04 requirements text
- `.planning/ROADMAP.md` — Plan descriptions: "cachetools TTLCache + asyncio.Lock, index_generation counter, graph/multi exclusion, invalidate_all on job DONE"

### Tertiary (LOW confidence)
- None — all findings are based on official codebase inspection and roadmap decisions

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — cachetools prescribed by roadmap; Phase 16 pattern confirmed by reading full source
- Architecture: HIGH — all integration points located in source; JobWorker DONE transition confirmed at line 361
- Pitfalls: HIGH — asyncio.Lock creation timing is a known Python 3.12 issue; cache key normalization confirmed by Phase 16 SHA-256 pattern

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (30 days — stable stdlib + cachetools)
