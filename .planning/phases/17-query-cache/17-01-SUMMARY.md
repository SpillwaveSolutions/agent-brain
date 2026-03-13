---
phase: 17-query-cache
plan: "01"
subsystem: query-cache
tags: [cache, performance, query, cachetools]
dependency_graph:
  requires: [16-embedding-cache]
  provides: [QueryCacheService, query-cache-settings, query-cache-model-field]
  affects: [agent-brain-server]
tech_stack:
  added: [cachetools>=5.3, types-cachetools]
  patterns: [TTLCache, module-singleton, asyncio-lock]
key_files:
  created:
    - agent-brain-server/agent_brain_server/services/query_cache.py
    - agent-brain-server/tests/test_query_cache.py
  modified:
    - agent-brain-server/agent_brain_server/config/settings.py
    - agent-brain-server/agent_brain_server/models/health.py
    - agent-brain-server/pyproject.toml
    - agent-brain-server/poetry.lock
decisions:
  - "cachetools TTLCache used for in-memory query caching with configurable TTL and max_size"
  - "graph and multi modes excluded from caching (non-deterministic LLM results)"
  - "Generation counter in cache key enables instant invalidation without per-entry eviction"
  - "Lock-free reads with asyncio.Lock for writes and invalidations"
  - "cachetools 7.0.5 resolved (was 6.2.4 transitive dep) — compatible with >=5.3 constraint"
metrics:
  duration: "~15 min"
  completed: "2026-03-12"
  tasks: 2
  files: 6
---

# Phase 17 Plan 01: QueryCacheService with TTLCache — Summary

**One-liner:** In-memory TTL query cache with SHA-256:generation keys, asyncio locking, and 15 passing unit tests covering all QCACHE requirements.

## What Was Built

Created a standalone `QueryCacheService` in `agent_brain_server/services/query_cache.py` that:

- Uses `cachetools.TTLCache` with configurable `ttl` (default 300s) and `max_size` (default 256 entries)
- Keys results by `SHA-256(canonical_json_params):index_generation` — generation changes on every invalidation, making stale keys unreachable without explicit eviction
- Lock-free reads via `.get()` for performance; `asyncio.Lock` guards `.put()` and `invalidate_all()`
- `is_cacheable_mode(mode)` returns `False` for `graph` and `multi` (non-deterministic results), `True` for `vector`, `bm25`, `hybrid`
- Module-level singleton functions: `get_query_cache()`, `set_query_cache()`, `reset_query_cache()`

**Settings additions:**
- `QUERY_CACHE_TTL: int = 300` — 5-minute default TTL
- `QUERY_CACHE_MAX_SIZE: int = 256` — 256-entry default

**Model addition:**
- `query_cache: dict[str, Any] | None` field on `IndexingStatus` for health endpoint reporting

## Tests

15 unit tests in `tests/test_query_cache.py` — all pass:

| Test | Covers |
|------|--------|
| `test_cache_miss_returns_none` | Miss counter increments |
| `test_cache_hit_returns_cached_result` | Hit counter increments, value returned |
| `test_cache_key_deterministic` | Same params → same key |
| `test_cache_key_different_params` | Different params → different keys |
| `test_cache_key_includes_generation` | Key changes after invalidate_all |
| `test_invalidate_all_clears_cache` | Entry unreachable post-invalidation |
| `test_invalidate_all_increments_generation` | Generation counter goes 0→1→2 |
| `test_graph_mode_not_cached` | graph mode excluded |
| `test_multi_mode_not_cached` | multi mode excluded |
| `test_vector_bm25_hybrid_cacheable` | vector/bm25/hybrid included |
| `test_get_stats_structure` | All stat keys present |
| `test_settings_configure_cache` | ttl/max_size respected |
| `test_singleton_pattern` | set/get/reset flow |
| `test_cache_ttl_expiry` | Entry expires after TTL |
| `test_sorted_list_fields_key_stability` | List order doesn't affect key |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Dep] cachetools not in pyproject.toml — added >=5.3 constraint**
- **Found during:** Task 1 (cachetools was transitive dep only)
- **Issue:** Plan said to add `cachetools>=5.3,<6` but cachetools 7.0.5 resolved. Upper bound dropped to allow latest
- **Fix:** Added `cachetools = ">=5.3"` (no upper bound) — compatible API
- **Files modified:** pyproject.toml, poetry.lock

**2. [Rule 3 - Blocking] Worktree Python 3.13 venv failed (chroma-hnswlib build error)**
- **Found during:** Task 1 dependency install
- **Issue:** Worktree venv used Python 3.13 which fails to build `chroma-hnswlib` (missing C++ headers)
- **Fix:** Deleted broken venv, reconfigured poetry to use Python 3.10.14 (Homebrew), reinstalled
- **Files modified:** None (venv config only)

## Commits

| Hash | Description |
|------|-------------|
| 9c2e4d5 | feat(17-01): add QueryCacheService with TTLCache and unit tests |

## Self-Check

- [x] `agent-brain-server/agent_brain_server/services/query_cache.py` — created
- [x] `agent-brain-server/tests/test_query_cache.py` — created (15 tests)
- [x] `agent-brain-server/agent_brain_server/config/settings.py` — QUERY_CACHE_TTL, QUERY_CACHE_MAX_SIZE added
- [x] `agent-brain-server/agent_brain_server/models/health.py` — query_cache field added
- [x] All 15 unit tests pass
- [x] mypy clean on query_cache.py
- [x] ruff clean on query_cache.py
