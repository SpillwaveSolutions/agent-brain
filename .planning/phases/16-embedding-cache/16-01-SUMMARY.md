---
phase: 16-embedding-cache
plan: 01
subsystem: caching
tags: [aiosqlite, lru-cache, sha256, sqlite, wal-mode, float32, embedding-cache, openai]

# Dependency graph
requires:
  - phase: 15-file-watcher
    provides: "FileWatcherService + auto-reindex trigger — cache makes repeated reindexing economically viable"
  - phase: 14-manifest-eviction
    provides: "ManifestTracker SHA-256 hashing — cache keys reuse same hash function for content dedup"
provides:
  - "EmbeddingCacheService: two-layer cache (OrderedDict LRU + aiosqlite WAL) with SHA-256 content keys"
  - "GET /index/cache + DELETE /index/cache API endpoints for status and clear"
  - "embedding_cache section in /health/status when cache has entries"
  - "EmbeddingGenerator.embed_text/embed_texts transparently cache-intercepted (ECACHE-06)"
  - "Provider fingerprint auto-wipe on startup for provider/model/dims change (ECACHE-04)"
  - "EMBEDDING_CACHE_MAX_DISK_MB / MAX_MEM_ENTRIES / PERSIST_STATS settings"
affects:
  - "17-query-cache: index_generation counter; query cache invalidation on reindex"
  - "18-uds-quality-gate: api/main.py lifespan further modified"

# Tech tracking
tech-stack:
  added: []  # aiosqlite 0.22.0 already a transitive dep; Python stdlib only
  patterns:
    - "Lazy import to break circular import: indexing.embedding -> services.embedding_cache -> services.__init__ -> indexing_service -> indexing.__init__"
    - "Two-layer cache: OrderedDict LRU (hot path, no I/O) + aiosqlite WAL (persistent, single-digit ms)"
    - "float32 BLOB via struct.pack for ~12 KB/entry at 3072 dims vs 24 KB float64"
    - "Batch SQL IN (?, ...) query in get_batch() for embed_texts() efficiency"
    - "Module-level singleton with get/set/reset following established embedding.py pattern"

key-files:
  created:
    - "agent-brain-server/agent_brain_server/services/embedding_cache.py"
    - "agent-brain-server/agent_brain_server/api/routers/cache.py"
    - "agent-brain-server/tests/test_embedding_cache.py"
  modified:
    - "agent-brain-server/agent_brain_server/indexing/embedding.py"
    - "agent-brain-server/agent_brain_server/api/main.py"
    - "agent-brain-server/agent_brain_server/models/health.py"
    - "agent-brain-server/agent_brain_server/api/routers/__init__.py"
    - "agent-brain-server/agent_brain_server/api/routers/health.py"
    - "agent-brain-server/agent_brain_server/config/settings.py"
    - "agent-brain-server/agent_brain_server/storage_paths.py"
    - "agent-brain-server/tests/unit/test_storage_paths.py"

key-decisions:
  - "Lazy import in embed_text/embed_texts instead of module-level import to break circular: indexing -> services -> indexing"
  - "persist_stats=False default: session-only counters avoid extra write contention on every cache hit"
  - "In-memory LRU default 1000 entries (~12 MB at 3072 dims) — configurable via EMBEDDING_CACHE_MAX_MEM_ENTRIES"
  - "get_batch() implemented from the start for embed_texts() efficiency over sequential awaits"
  - "embedding_cache section in /health/status omitted when entry_count == 0 (per CONTEXT.md decision)"
  - "Lazy import via PLC0415 noqa comment — ruff accepts this for justified circular-import breaks"

patterns-established:
  - "Circular import break: use lazy import inside method body with # noqa: PLC0415 when services/ imports indexing/ imports services/"
  - "Two-layer cache pattern: OrderedDict LRU promotes disk hits to memory on access"
  - "Provider fingerprint: metadata row in SQLite for O(1) startup check vs O(N) per-entry check"
  - "float32 BLOB: struct.pack(f'{dims}f', *embedding) — ~12 KB per 3072-dim vector, cosine similarity unaffected"

requirements-completed:
  - ECACHE-01
  - ECACHE-02
  - ECACHE-04
  - ECACHE-06

# Metrics
duration: 10min
completed: 2026-03-10
---

# Phase 16 Plan 01: Embedding Cache Summary

**Two-layer embedding cache (OrderedDict LRU + aiosqlite WAL) wired into EmbeddingGenerator via lazy import, with GET/DELETE /index/cache API endpoints and 22 passing unit tests**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-10T16:34:32Z
- **Completed:** 2026-03-10T16:44:02Z
- **Tasks:** 2
- **Files modified:** 11 (3 created, 8 modified)

## Accomplishments

- Created `EmbeddingCacheService` with SHA-256(text):provider:model:dims keys, float32 BLOB storage, LRU eviction, provider fingerprint auto-wipe (ECACHE-01/02/04)
- Wired cache into `EmbeddingGenerator.embed_text()` and `embed_texts()` with batch SQL lookup — zero API calls for unchanged content on re-index (ECACHE-06)
- Added `GET /index/cache` (status) and `DELETE /index/cache` (clear) API endpoints; `embedding_cache` section in `/health/status`
- 22 unit tests pass covering all 8 required test cases; `task before-push` exits 0 with 893 tests passing

## Task Commits

Each task was committed atomically:

1. **Task 1: EmbeddingCacheService + settings + storage paths** - `02de86f` (feat)
2. **Task 2: EmbeddingGenerator integration + lifespan init + API endpoints + tests** - `1061cc6` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified

- `agent-brain-server/agent_brain_server/services/embedding_cache.py` - Full EmbeddingCacheService implementation (345 lines, 91% coverage)
- `agent-brain-server/agent_brain_server/api/routers/cache.py` - GET/DELETE /index/cache endpoints
- `agent-brain-server/tests/test_embedding_cache.py` - 22 unit tests for cache service
- `agent-brain-server/agent_brain_server/indexing/embedding.py` - Cache interception in embed_text/embed_texts (lazy import)
- `agent-brain-server/agent_brain_server/api/main.py` - _build_provider_fingerprint(), cache init in lifespan, cache_router registration
- `agent-brain-server/agent_brain_server/models/health.py` - embedding_cache field on IndexingStatus
- `agent-brain-server/agent_brain_server/api/routers/__init__.py` - Export cache_router
- `agent-brain-server/agent_brain_server/api/routers/health.py` - Populate embedding_cache section when entry_count > 0
- `agent-brain-server/agent_brain_server/config/settings.py` - Three EMBEDDING_CACHE_* settings
- `agent-brain-server/agent_brain_server/storage_paths.py` - embedding_cache subdirectory
- `agent-brain-server/tests/unit/test_storage_paths.py` - Add embedding_cache to expected keys

## Decisions Made

- **Lazy import pattern** for embedding_cache in embedding.py: direct module-level import caused a circular import (`indexing.__init__` → `embedding` → `services.embedding_cache` → `services.__init__` → `indexing_service` → `indexing.__init__`). Resolved with lazy import inside method body with `# noqa: PLC0415`.
- **persist_stats=False default**: session-only counters avoid a write on every cache hit. Persistent stats would add contention with no significant user benefit.
- **get_batch() from the start**: implemented batch SQL lookup in `embed_texts()` — avoids N sequential `await cache.get(k)` calls for large batches.
- **embedding_cache omitted in /health/status when entry_count == 0**: clean for fresh installs per CONTEXT.md decision.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Resolved circular import via lazy import in embed_text/embed_texts**
- **Found during:** Task 2 (EmbeddingGenerator integration)
- **Issue:** Direct module-level `from agent_brain_server.services.embedding_cache import ...` in `embedding.py` triggered a circular import during Python module init: `indexing.__init__` → `embedding.py` → `services.embedding_cache` → `services/__init__` → `indexing_service` → `indexing.__init__`. Test collection failed with `ImportError: cannot import name 'EmbeddingGenerator' from partially initialized module`.
- **Fix:** Moved the import inside `embed_text()` and `embed_texts()` method bodies using `from ... import ... # noqa: PLC0415`. Python lazy-loads on first call, at which point all packages are fully initialized.
- **Files modified:** `agent_brain_server/indexing/embedding.py`
- **Verification:** `task before-push` ran all 893 tests successfully; `poetry run python -c "from agent_brain_server.indexing.embedding import EmbeddingGenerator; print('Import OK')"` succeeds.
- **Committed in:** `1061cc6` (Task 2 commit)

**2. [Rule 2 - Missing Critical] Updated test_storage_paths.py to include embedding_cache key**
- **Found during:** Task 2 verification (`task before-push`)
- **Issue:** `test_returns_expected_keys` in `tests/unit/test_storage_paths.py` asserted exact key set — the new `embedding_cache` key caused 1 test failure.
- **Fix:** Added `"embedding_cache"` to the `expected_keys` set with a `# Phase 16` comment.
- **Files modified:** `agent-brain-server/tests/unit/test_storage_paths.py`
- **Verification:** Test passes; all 893 tests pass.
- **Committed in:** `1061cc6` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking import error, 1 missing test coverage)
**Impact on plan:** Both auto-fixes required for correctness. No scope creep. Plan objectives fully met.

## Issues Encountered

The circular import was caught by `task before-push` test collection, not at import time in the isolated cache test. This is because `tests/test_embedding_cache.py` only imports from `services.embedding_cache` directly (no circular path), while `tests/contract/conftest.py` imports from `agent_brain_server.indexing.bm25_index`, which triggers the full `indexing/__init__.py` initialization chain. The lazy import pattern cleanly resolved this.

## User Setup Required

None - no external service configuration required. The cache initializes automatically from environment variables with safe defaults (500 MB disk, 1000 in-memory LRU entries, session-only stats).

## Next Phase Readiness

- Phase 16 embedding cache is complete and operational
- Phase 17 (Query Cache) can now build on top of this infrastructure
- Phase 17 needs an `index_generation` counter from this phase's groundwork — the EmbeddingCacheService clear() method already resets session counters, which can serve as a trigger point
- CLI `agent-brain cache` command group (cache status + cache clear) can be added in a follow-on plan if needed

---
*Phase: 16-embedding-cache*
*Completed: 2026-03-10*
