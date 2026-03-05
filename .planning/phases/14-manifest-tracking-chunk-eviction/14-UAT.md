---
status: complete
phase: 14-manifest-tracking-chunk-eviction
source: 14-01-SUMMARY.md, 14-02-SUMMARY.md
started: 2026-03-05T22:30:00Z
updated: 2026-03-05T22:45:00Z
---

## Current Test

[testing complete]

## Tests

### 1. First-time indexing creates manifest
expected: Index a folder for the first time. A manifest JSON file should appear at `<state_dir>/manifests/<sha256_hash>.json`. Job completes with status COMPLETED.
result: pass

### 2. Incremental re-index skips unchanged files
expected: Re-index the same folder without changing any files. The job should complete quickly with zero chunks created and zero chunks evicted. `agent-brain jobs <JOB_ID>` should show "Files unchanged" with a non-zero count and "Chunks created: 0".
result: pass

### 3. Changed file triggers re-indexing
expected: Modify a file in the indexed folder (add/change content), then re-index. The job should detect the change: eviction summary shows 1 file changed, old chunks evicted, new chunks created. Unchanged files are skipped.
result: pass

### 4. Deleted file chunks evicted
expected: Delete a file from the indexed folder, then re-index. The eviction summary should show 1 file deleted, its chunks evicted from the index. The deleted file's content should no longer appear in search results.
result: pass

### 5. Force reindex bypasses manifest
expected: Run `agent-brain index /path --force`. All files should be re-indexed regardless of manifest state. Eviction summary should show all prior chunks evicted and all files processed as new.
result: pass

### 6. CLI job detail shows eviction summary
expected: After any indexing job with manifest tracking, `agent-brain jobs <JOB_ID>` displays an "Eviction Summary" section showing files added, changed, deleted, unchanged counts and chunks evicted/created counts.
result: pass

### 7. Manifests directory created in state path
expected: After server startup with a configured state directory, a `manifests/` subdirectory exists inside the state directory alongside other subdirectories (chromadb, bm25, etc).
result: pass

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0

## Gaps

[none]
