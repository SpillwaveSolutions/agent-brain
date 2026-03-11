---
status: testing
phase: 16-embedding-cache
source: 16-01-SUMMARY.md, 16-02-SUMMARY.md
started: 2026-03-10T17:00:00Z
updated: 2026-03-11T12:00:00Z
round: 2
---

## Current Test

[all tests executed — diagnosing issues]

## Tests

### 1. Cold Start Smoke Test
expected: Server boots, `agent-brain status` returns healthy with no errors.
result: pass

### 2. Second Reindex Makes Zero Embedding API Calls
expected: Index a folder, then reindex same folder. Second run shows zero new embedding API calls (all cache hits). `agent-brain status` shows nonzero hit rate.
result: pass

### 3. Cache Survives Server Restart
expected: After indexing, stop and restart the server. `agent-brain cache status` shows nonzero entry_count. Reindex shows cache hits (not all misses).
result: issue
reported: "Cache persistence works across restart, but only provable with query-seeded cache entry. Intended index/reindex flow is broken because first-time indexing produces 0 chunks."
severity: blocker
root_cause: "indexing_service.py:327 reads doc.metadata['source'] for manifest diffing, but document_loader.py:404 only sets LoadedDocument.source, not metadata['source']. Result: 0 chunks indexed."

### 4. Cache Status Command
expected: `agent-brain cache status` shows a table with entry_count, hit_rate, hits, misses, mem_entries, size_bytes.
result: pass

### 5. Cache Status JSON Output
expected: `agent-brain cache status --json` outputs raw JSON dict with same fields.
result: pass

### 6. Cache Clear with Confirmation
expected: `agent-brain cache clear` (without --yes) prompts "This will flush N cached embeddings. Continue? [y/N]". Entering 'n' cancels.
result: issue
reported: "Cancel path works, but prompt says Continue? [y/n] instead of Continue? [y/N]."
severity: cosmetic

### 7. Cache Clear with --yes Flag
expected: `agent-brain cache clear --yes` clears immediately, shows "Cleared N cached embeddings (X.Y MB freed)".
result: issue
reported: "CLI calls /index/cache without trailing slash, gets 307 redirect to /index/cache/, then crashes with JSONDecodeError. Nothing cleared."
severity: blocker
root_cause: "api_client.py:484 DELETEs /index/cache without trailing slash, but DELETE route is mounted at cache.py:59 with trailing slash."

### 8. Cache Clear While Indexing
expected: Start an indexing job, then run `agent-brain cache clear --yes`. Clear succeeds without error. Running job completes normally (regenerates embeddings).
result: issue
reported: "Same cache clear --yes bug (307 redirect/JSONDecodeError). Indexing job itself completes but produces 0 chunks."
severity: blocker
root_cause: "Same two root causes: api_client.py trailing slash + indexing_service.py metadata['source'] missing."

### 9. Provider/Model Change Auto-Wipe
expected: Change embedding provider or model in config.yaml, restart server. Server log shows cache was wiped. `agent-brain cache status` shows 0 entries.
result: pass

### 10. Status Shows Cache Metrics
expected: `agent-brain status` shows an embedding cache summary line: entry count, hit rate, hits, misses. With `--verbose` or `--json`, shows additional detail.
result: issue
reported: "Status shows cache summary line and --json includes detail, but there is no --verbose option."
severity: minor

### 11. Health Endpoint Cache Section
expected: `curl localhost:PORT/health/status` includes `embedding_cache` section when cache has entries. Omitted for fresh installs.
result: issue
reported: "Includes embedding_cache when cache has entries, but for fresh/empty cache returns embedding_cache: null instead of omitting the field."
severity: minor

### 12. Cache Help Text
expected: `agent-brain cache --help` shows "cache status" and "cache clear" subcommands with descriptions.
result: pass

### 13. Backward Compatibility — No Cache Impact on Existing Workflow
expected: Existing `agent-brain index`, `agent-brain query`, `agent-brain status` commands work exactly as before. Cache is transparent.
result: issue
reported: "agent-brain index queues jobs but first-time indexing produces 0 chunks. agent-brain query returns 500 on the empty index path."
severity: blocker
root_cause: "indexing_service.py:327 reads doc.metadata['source'] for manifest diffing, but document_loader.py:404 only sets LoadedDocument.source, not metadata['source']."

## Summary

total: 13
passed: 6
issues: 7
pending: 0
skipped: 0

## Gaps

- truth: "Cache clear --yes clears cache without error"
  status: failed
  reason: "User reported: CLI calls /index/cache without trailing slash, gets 307 redirect, crashes with JSONDecodeError."
  severity: blocker
  test: 7
  root_cause: "api_client.py:484 DELETEs /index/cache without trailing slash, but DELETE route is mounted at cache.py:59 with trailing slash."
  artifacts:
    - path: "agent-brain-cli/agent_brain_cli/client/api_client.py"
      issue: "Line 484 — missing trailing slash on /index/cache DELETE"
    - path: "agent-brain-server/agent_brain_server/api/routers/cache.py"
      issue: "Line 59 — route mounted with trailing slash"
  missing:
    - "Add trailing slash to DELETE URL in api_client.py or remove redirect_slashes"
  debug_session: ""

- truth: "First-time indexing produces chunks and populates the index"
  status: failed
  reason: "User reported: indexing produces 0 chunks. Manifest diffing reads doc.metadata['source'] which is never set."
  severity: blocker
  test: 3
  root_cause: "indexing_service.py:327 reads doc.metadata['source'] for manifest diffing, but document_loader.py:404 only sets LoadedDocument.source, not metadata['source']."
  artifacts:
    - path: "agent-brain-server/agent_brain_server/services/indexing_service.py"
      issue: "Line 327 — reads doc.metadata['source'] for dedup"
    - path: "agent-brain-server/agent_brain_server/services/document_loader.py"
      issue: "Line 404 — sets LoadedDocument.source but not metadata['source']"
  missing:
    - "Ensure document_loader populates metadata['source'] or indexing_service reads LoadedDocument.source"
  debug_session: ""

- truth: "Cache clear confirmation prompt uses [y/N] (default No)"
  status: failed
  reason: "User reported: prompt says [y/n] instead of [y/N]."
  severity: cosmetic
  test: 6

- truth: "agent-brain status --verbose shows additional cache detail"
  status: failed
  reason: "User reported: no --verbose option exists."
  severity: minor
  test: 10

- truth: "Health endpoint omits embedding_cache for fresh installs"
  status: failed
  reason: "User reported: returns embedding_cache: null instead of omitting the field."
  severity: minor
  test: 11
