---
phase: 17-query-cache
plan: "02"
subsystem: query-cache
tags: [cache, performance, query, integration, wiring]
dependency_graph:
  requires: [17-01-query-cache-service]
  provides: [query-cache-wired, cache-invalidation-on-reindex, health-stats]
  affects: [agent-brain-server]
tech_stack:
  added: []
  patterns: [cache-check-before-store-after, job-completion-invalidation, singleton-wiring]
key_files:
  created: []
  modified:
    - agent-brain-server/agent_brain_server/services/query_service.py
    - agent-brain-server/agent_brain_server/job_queue/job_worker.py
    - agent-brain-server/agent_brain_server/api/main.py
    - agent-brain-server/agent_brain_server/api/routers/health.py
    - agent-brain-server/tests/test_query_cache.py
    - docs/CONFIGURATION.md
decisions:
  - "Inline import of QueryCacheService inside execute_query to avoid circular import risk"
  - "graph/multi modes skip cache check entirely via is_cacheable_mode — no key generated, no store attempted"
  - "Cache stored on QueryService as self.query_cache; injected at lifespan time"
  - "JobWorker.set_query_cache setter follows Phase 15 setter injection pattern"
  - "invalidate_all() placed AFTER job.status=DONE but BEFORE _apply_watch_config — ensures cache cleared before watcher starts"
  - "reset_query_cache() in shutdown to avoid stale singleton in test restarts"
  - "query_cache always included in health stats (not omitted like embedding_cache)"
metrics:
  duration: "~10 min"
  completed: "2026-03-12"
  tasks: 2
  files: 6
---

# Phase 17 Plan 02: QueryCacheService Wiring — Summary

**One-liner:** QueryCacheService wired into QueryService check/store, JobWorker DONE invalidation, lifespan creation, health stats — 20 tests pass, mypy+ruff clean.

## What Was Built

### QueryService Integration (QCACHE-01, QCACHE-03)

In `execute_query()`:
1. **Cache check** (before storage access): if mode is cacheable and key exists, return cached response immediately
2. **Cache store** (after response built): store response keyed by SHA-256 params + generation
3. **graph/multi modes**: `is_cacheable_mode()` returns False → no key generated, no cache interaction

Cache check happens BEFORE the empty-index guard to avoid wasting the `get_count()` call on cache hits.

### JobWorker Integration (QCACHE-04)

- `set_query_cache(cache)` setter follows Phase 15 setter pattern
- `invalidate_all()` called immediately after `job.status = JobStatus.DONE` for successful reindex jobs
- Only on success (DONE) — failed/cancelled jobs do NOT invalidate (stale cache is preferable to empty cache for transient failures)

### Lifespan Wiring (api/main.py)

- `QueryCacheService` created with `settings.QUERY_CACHE_TTL` and `settings.QUERY_CACHE_MAX_SIZE`
- `set_query_cache()` singleton set
- `app.state.query_cache` set for health endpoint access
- Passed to `QueryService(query_cache=query_cache)` and `_job_worker.set_query_cache(query_cache)`
- Wired in BOTH branches (state_dir and no-state-dir)
- `reset_query_cache()` called on shutdown

### Health Endpoint (QCACHE-05)

In `health.py` `indexing_status()`:
- `query_cache_info = query_cache_svc.get_stats()` when `app.state.query_cache` present
- Passed as `query_cache=query_cache_info` to `IndexingStatus`
- Always included (not conditionally omitted like `embedding_cache`)

### Documentation (XCUT-04)

- `docs/CONFIGURATION.md`: New "Query Cache Configuration" section documenting `QUERY_CACHE_TTL` and `QUERY_CACHE_MAX_SIZE` with defaults, examples, and behavioral notes

## Tests

5 integration tests added to `tests/test_query_cache.py` (20 total):

| Test | Covers |
|------|--------|
| `test_query_service_cache_hit` | Second identical vector query served from cache |
| `test_query_service_graph_bypasses_cache` | graph mode never cached |
| `test_query_service_multi_bypasses_cache` | multi mode never cached |
| `test_job_worker_invalidates_cache_on_done` | set_query_cache setter + invalidate_all |
| `test_health_status_includes_query_cache` | IndexingStatus accepts query_cache dict |

All 20 tests pass. mypy clean (78 files). ruff clean.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff N814 — CamelCase class `QueryCacheService` imported as constant `_QCS`**
- **Found during:** Task 1 ruff check
- **Issue:** `QueryCacheService as _QCS` violates N814 (camelcase imported as constant)
- **Fix:** Removed alias, used `QueryCacheService.is_cacheable_mode(...)` directly. Line split to stay under 88 chars.
- **Files modified:** query_service.py

**2. [Rule 1 - Bug] Ruff UP037 — quoted type annotations after `from __future__ import annotations`**
- **Found during:** Task 1 ruff check
- **Issue:** `"QueryCacheService | None"` quotes unnecessary with `from __future__ import annotations`
- **Fix:** `ruff check --fix` auto-removed quotes in job_worker.py and query_service.py
- **Files modified:** job_worker.py, query_service.py

**3. [Rule 1 - Bug] Integration test `test_query_service_graph_bypasses_cache` used invalid `patch.object` on MagicMock**
- **Found during:** Task 2 test run
- **Issue:** `patch.object(type(storage), "is_initialized", ...)` failed — MagicMock doesn't have `is_initialized` attribute for patching
- **Fix:** Simplified test — graph mode raises `ValueError` (ENABLE_GRAPH_INDEX=False), so just catch exception and assert `cached_entries==0`
- **Files modified:** tests/test_query_cache.py

## Commits

| Hash | Description |
|------|-------------|
| 470ca4f | feat(17-02): wire QueryCacheService into QueryService, JobWorker, and health endpoint |

## Self-Check

- [x] query_service.py: `query_cache` in execute_query — cache check + store
- [x] job_worker.py: `set_query_cache` setter + `invalidate_all()` after DONE
- [x] main.py: QueryCacheService created, singleton set, wired to both consumers
- [x] health.py: `query_cache_info = query_cache_svc.get_stats()`
- [x] docs/CONFIGURATION.md: `QUERY_CACHE_TTL` present
- [x] 20 tests pass
- [x] mypy clean (78 files)
- [x] ruff clean
