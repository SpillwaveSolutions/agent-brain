---
status: passed
phase: 16-embedding-cache
source: 16-01-SUMMARY.md, 16-02-SUMMARY.md
started: 2026-03-10T17:00:00Z
updated: 2026-03-12T19:15:00Z
round: 8
---

## Current Test

Round 8: All 13 tests passing after event-loop starvation fixes.

## Tests

### 1. Cold Start Smoke Test
expected: Server boots, `agent-brain status` returns healthy with no errors.
result: pass

### 2. Second Reindex Makes Zero Embedding API Calls
expected: Index a folder, then reindex same folder. Second run shows zero new embedding API calls (all cache hits). `agent-brain status` shows nonzero hit rate.
result: pass

### 3. Cache Survives Server Restart
expected: After indexing, stop and restart the server. `agent-brain cache status` shows nonzero entry_count. Reindex shows cache hits (not all misses).
result: pass
fix_round: 4
fix_commit: "metadata source fix in document_loader.py"

### 4. Cache Status Command
expected: `agent-brain cache status` shows a table with entry_count, hit_rate, hits, misses, mem_entries, size_bytes.
result: pass

### 5. Cache Status JSON Output
expected: `agent-brain cache status --json` outputs raw JSON dict with same fields.
result: pass

### 6. Cache Clear with Confirmation
expected: `agent-brain cache clear` (without --yes) prompts "This will flush N cached embeddings. Continue? [y/N]". Entering 'n' cancels.
result: pass
fix_round: 4
fix_commit: "Confirm prompt default changed to [y/N]"

### 7. Cache Clear with --yes Flag
expected: `agent-brain cache clear --yes` clears immediately, shows "Cleared N cached embeddings (X.Y MB freed)".
result: pass
fix_round: 4
fix_commit: "cache route no-slash aliases + api_client trailing slash fix"

### 8. Cache Clear While Indexing
expected: Start an indexing job, then run `agent-brain cache clear --yes`. Clear succeeds in < 10s. Running job completes normally.
result: pass
fix_round: 8
fix_commit: "fbdc557 + 72224eb — asyncio.to_thread() for all CPU-heavy pipeline stages"
elapsed: 0.041s (target < 10s)

### 9. Provider/Model Change Auto-Wipe
expected: Change embedding provider or model in config.yaml, restart server. Server log shows cache was wiped. `agent-brain cache status` shows 0 entries.
result: pass

### 10. Status Shows Cache Metrics
expected: `agent-brain status` shows an embedding cache summary line. With `--verbose` or `--json`, shows additional detail.
result: pass
fix_round: 5
fix_commit: "status --verbose flag added + status count source-of-truth fix"

### 11. Health Endpoint Cache Section
expected: `curl localhost:PORT/health/status` includes `embedding_cache` section when cache has entries. Omitted for fresh installs.
result: pass
fix_round: 5
fix_commit: "6757b80 — health endpoint omits embedding_cache when None"

### 12. Cache Help Text
expected: `agent-brain cache --help` shows "cache status" and "cache clear" subcommands with descriptions.
result: pass

### 13. Backward Compatibility — No Cache Impact on Existing Workflow
expected: Existing `agent-brain index`, `agent-brain query`, `agent-brain status` commands work exactly as before. Cache is transparent.
result: pass
fix_round: 4
fix_commit: "metadata source fix in document_loader.py"

## Summary

total: 13
passed: 13
issues: 0
pending: 0
skipped: 0

## Fix History

### Round 4 (metadata + cache routes)
- Fixed document_loader.py: metadata['source'] now populated for manifest diffing
- Fixed api_client.py: trailing slash on cache DELETE endpoint
- Added no-slash route aliases in cache.py
- Fixed Confirm prompt default [y/N]

### Round 5 (status + health)
- Added --verbose flag to status command
- Fixed status count to use storage_backend (single source of truth)
- Health endpoint omits embedding_cache when None (not null)

### Round 6-7 (event-loop yields)
- Added asyncio.sleep(0) yields in chunking loops
- Moved VACUUM to background task
- Added yield every 10 cache writes in embedding miss loop

### Round 8 (event-loop starvation root cause)
- Wrapped document post-processing in asyncio.to_thread()
- Wrapped chunk_single_document in asyncio.to_thread()
- Wrapped chunk_code_document tree-sitter parsing in asyncio.to_thread()
- Wrapped ChromaDB collection.upsert() in asyncio.to_thread()
- Wrapped BM25 build_index in asyncio.to_thread()
- Wrapped graph index build in asyncio.to_thread()
- Wrapped content injector in asyncio.to_thread()
- Replaced fire-and-forget VACUUM with PRAGMA wal_checkpoint(TRUNCATE)
- Added put_many() batch cache writes
