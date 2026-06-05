---
phase: 16-embedding-cache
verified: 2026-03-10T18:15:00Z
status: passed
score: 9/9 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 8/9
  gaps_closed:
    - "agent-brain cache status shows cache statistics — CLI client now calls GET /index/cache/ matching server route"
  gaps_remaining: []
  regressions: []
---

# Phase 16: Embedding Cache Verification Report

**Phase Goal:** Users pay zero OpenAI API cost for unchanged content on any reindex run triggered by the watcher or manually.
**Verified:** 2026-03-10T18:15:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (commit 7fea667)

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|---------|
| 1  | Reindexing unchanged content makes zero embedding API calls on second run | VERIFIED | `embed_text()` and `embed_texts()` both check `get_embedding_cache()` before calling provider; batch `get_batch()` SQL lookup returns hits for all keys on re-run |
| 2  | Cache persists to disk via aiosqlite and survives server restart | VERIFIED | `embedding_cache.py` uses aiosqlite WAL-mode SQLite at `storage_paths["embedding_cache"]/embeddings.db`; initialized in lifespan before IndexingService |
| 3  | Switching embedding provider or model auto-wipes all cached embeddings on startup | VERIFIED | `initialize()` reads `provider_fingerprint` metadata row, deletes all embeddings on mismatch (ECACHE-04 lines 159-172 in `embedding_cache.py`) |
| 4  | EmbeddingGenerator.embed_text(), embed_texts(), and embed_query() all check cache before calling provider | VERIFIED | `embed_text()` lines 88-127 checks cache; `embed_texts()` lines 129-189 uses `get_batch()`; `embed_query()` delegates to `embed_text()` (line 219) |
| 5  | agent-brain status shows embedding cache hit rate, total hits, misses, and entry count | VERIFIED | `status.py` lines 112-123 reads `indexing.embedding_cache` and displays entry count, hit_rate, hits, misses |
| 6  | agent-brain cache clear --yes flushes cache and reports count + size freed | VERIFIED | `cache.py` `cache_clear()` calls `client.clear_cache()` and prints count + size_mb; 12 tests pass |
| 7  | agent-brain cache clear without --yes prompts for confirmation showing entry count | VERIFIED | `cache.py` lines 102-114 fetch count via `client.cache_status()`, then `Confirm.ask(f"This will flush {count:,}...")` |
| 8  | agent-brain cache status shows cache statistics | VERIFIED | `client.cache_status()` now calls `GET /index/cache/` (line 471 in api_client.py, fixed in commit 7fea667); server registers `GET /` mounted at `/index/cache` in main.py line 550 — paths match |
| 9  | /health/status API response includes embedding_cache section when cache has entries | VERIFIED | `health.py` lines 196-203 get disk stats, populate `embedding_cache_info` when `entry_count > 0`, pass to `IndexingStatus` |

**Score:** 9/9 truths verified

### Gap Closure Verification

**Gap closed:** `agent-brain cache status shows cache statistics`

The routing mismatch identified in the initial verification (CLI calling `GET /index/cache/status` against a server endpoint at `GET /index/cache/`) was fixed in commit `7fea667`.

**Before fix (line 471):**
```python
return self._request("GET", "/index/cache/status")
```

**After fix (line 471):**
```python
return self._request("GET", "/index/cache/")
```

**Server route unchanged and correct:**
- `cache.py`: `@router.get("/")` — registers `GET /` relative to prefix
- `main.py` line 550: `app.include_router(cache_router, prefix="/index/cache", tags=["Cache"])`
- Effective server endpoint: `GET /index/cache/`
- Client now calls: `GET /index/cache/` — MATCH

**Regression check:** No regressions. All previously verified items confirmed:
- `embedding_cache.py`: 496 lines (unchanged)
- `test_embedding_cache.py`: 449 lines (unchanged)
- `test_cache_command.py`: 208 lines (unchanged)
- Lifespan wiring in `main.py`: `set_embedding_cache()` call at lines 329-331 (unchanged)
- `embed_text()`/`embed_texts()` cache interception in `embedding.py` (unchanged)

### Required Artifacts

| Artifact | Min Lines | Actual Lines | Status | Details |
|----------|-----------|--------------|--------|---------|
| `agent-brain-server/agent_brain_server/services/embedding_cache.py` | 200 | 496 | VERIFIED | Full EmbeddingCacheService: LRU OrderedDict + aiosqlite, SHA-256 keys, get/put/get_batch/clear, singleton pattern |
| `agent-brain-server/agent_brain_server/api/routers/cache.py` | — | 96 | VERIFIED | GET / and DELETE / handlers, exports `router`, 503 when cache not initialized |
| `agent-brain-server/tests/test_embedding_cache.py` | 80 | 449 | VERIFIED | 22 tests covering all 8 required cases |
| `agent-brain-cli/agent_brain_cli/commands/cache.py` | 50 | 130 | VERIFIED | `cache_group` with `cache status` and `cache clear` subcommands; confirmation prompt, --yes flag |
| `agent-brain-cli/tests/test_cache_command.py` | 40 | 208 | VERIFIED | 12 tests |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `indexing/embedding.py` | `services/embedding_cache.py` | `get_embedding_cache()` lazy import in embed_text/embed_texts | WIRED | Lines 108-111 and 153-156; lazy import with `# noqa: PLC0415` |
| `api/main.py` | `services/embedding_cache.py` | lifespan initializes EmbeddingCacheService before IndexingService | WIRED | Lines 308-332; `set_embedding_cache(embedding_cache)` called; `app.state.embedding_cache` set |
| `embedding_cache.py` | `aiosqlite` | WAL-mode SQLite for persistent cache storage | WIRED | `aiosqlite.connect(self.db_path)` in initialize, get, put, get_batch, clear, get_disk_stats |
| `commands/cache.py` | `client/api_client.py` | `client.cache_status()` and `client.clear_cache()` | WIRED | Lines 33, 105, 116 in `cache.py` call `client.cache_status()` and `client.clear_cache()` |
| `client/api_client.py` | `/index/cache/` (GET status) | HTTP GET /index/cache/ | WIRED | Client calls `/index/cache/` (line 471, fixed in 7fea667); server registers `GET /` at prefix `/index/cache` (main.py line 550) |
| `commands/status.py` | `/health/status` | Reads `embedding_cache` from IndexingStatus response | WIRED | Lines 113-123 in `status.py`; `indexing.embedding_cache` parsed from response |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|---------|
| ECACHE-01 | Cache key = SHA-256(content) + provider:model:dimensions | SATISFIED | `make_cache_key()` in `embedding_cache.py`; SHA-256 + colon-separated provider:model:dimensions |
| ECACHE-02 | Cache persists to disk via aiosqlite (survives server restarts) | SATISFIED | aiosqlite WAL-mode, path at `storage_paths["embedding_cache"]/embeddings.db` |
| ECACHE-03 | Cache hit/miss metrics visible in `agent-brain status` output | SATISFIED | `status.py` embedding_cache section; `health.py` populates `embedding_cache` in `/health/status` |
| ECACHE-04 | Cache auto-invalidates when embedding provider or model changes | SATISFIED | `initialize()` provider_fingerprint mismatch triggers DELETE all + UPDATE fingerprint |
| ECACHE-05 | `agent-brain cache clear` CLI command to manually flush embedding cache | SATISFIED | `cache status` and `cache clear` both functional; routing mismatch fixed in 7fea667 |
| ECACHE-06 | Embedding cache integrates transparently into embed paths | SATISFIED | embed_text, embed_texts, embed_query (via embed_text) all cache-intercepted |

### Anti-Patterns Found

No TODO/FIXME/placeholder comments found in any phase-16 files. No stub anti-patterns detected.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `embedding_cache.py` | 272 | `return {}` | INFO | Legitimate early-return for empty input list in `get_batch()`; not a stub |

### Human Verification Required

None. All automated checks pass and the routing fix is verified programmatically.

### Summary

The single gap from initial verification is now closed. Commit `7fea667` corrected the CLI client's `cache_status()` method to call `GET /index/cache/` instead of the non-existent `GET /index/cache/status`. The server route `GET /` mounted at prefix `/index/cache` is unchanged and correct.

All 9 observable truths are now verified. All 6 requirement IDs (ECACHE-01 through ECACHE-06) are fully satisfied. The phase goal — zero OpenAI API cost for unchanged content on any reindex run — is achieved.

---

_Verified: 2026-03-10T18:15:00Z_
_Verifier: Claude (gsd-verifier)_
