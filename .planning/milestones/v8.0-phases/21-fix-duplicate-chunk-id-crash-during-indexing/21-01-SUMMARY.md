---
phase: 21-fix-duplicate-chunk-id-crash-during-indexing
plan: 01
subsystem: storage
tags: [bug-fix, deduplication, chromadb, postgresql, upsert]
dependency_graph:
  requires: []
  provides: [dedup-guard-chromadb, dedup-guard-postgres]
  affects: [agent_brain_server.storage.vector_store, agent_brain_server.storage.postgres.backend]
tech_stack:
  added: []
  patterns: [dict-based-O(N)-deduplication, last-occurrence-wins]
key_files:
  created:
    - agent-brain-server/tests/unit/storage/test_vector_store_deduplication.py
  modified:
    - agent-brain-server/agent_brain_server/storage/vector_store.py
    - agent-brain-server/agent_brain_server/storage/postgres/backend.py
    - agent-brain-server/agent_brain_server/indexing/embedding.py
    - agent-brain-server/tests/test_embedding_cache.py
decisions:
  - "Deduplication placed after length check, before lock acquisition in vector_store.py — correct placement per pitfall documentation"
  - "Last-occurrence-wins semantics — consistent with upsert contract"
  - "strict=True on zip() calls — enforces B905 linting rule and catches length mismatches"
  - "Pre-existing zip() B905 errors in embedding.py and test_embedding_cache.py fixed as part of task"
metrics:
  duration: 10 min
  completed_date: "2026-03-13"
  tasks: 2
  files_modified: 5
  files_created: 1
---

# Phase 21 Plan 01: Fix Duplicate Chunk ID Crash During Indexing Summary

**One-liner:** Dict-based O(N) deduplication with last-occurrence-wins in ChromaDB and PostgreSQL upsert paths prevents DuplicateIDError crash from Confluence exports.

## What Was Built

Added defensive deduplication to `VectorStoreManager.upsert_documents()` and `PostgresBackend.upsert_documents()`. When a batch upsert contains duplicate chunk IDs (which happens when indexing Confluence exports where the same filename appears in multiple subdirectories), the storage layer now silently deduplicates the batch using last-occurrence semantics, logs a WARNING with the count and sample IDs, and proceeds without crashing.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (TDD RED) | Failing tests for deduplication behaviors | 36513fd | tests/unit/storage/test_vector_store_deduplication.py |
| 1 (TDD GREEN) | Deduplication implementation in both backends | 121b1ba | storage/vector_store.py, storage/postgres/backend.py |
| 2 | Full test suite validation + linting fixes | d9ce994 | vector_store.py, backend.py, test_vector_store_deduplication.py, embedding.py, test_embedding_cache.py |

## Verification

- All 5 deduplication tests pass: `test_upsert_deduplicates_batch`, `test_upsert_no_duplicates_unchanged`, `test_upsert_logs_warning_on_duplicates`, `test_upsert_empty_batch`, `test_postgres_upsert_deduplicates`
- All 573 unit tests pass
- mypy: 0 errors in 77 source files
- ruff: All checks passed for modified files

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Pre-existing linting] Fixed B905 zip() errors in embedding.py and test_embedding_cache.py**
- **Found during:** Task 2 (before-push)
- **Issue:** `zip()` calls in `agent_brain_server/indexing/embedding.py:186` and `tests/test_embedding_cache.py:122,362,386` were missing `strict=True`
- **Fix:** Added `strict=True` parameter to all four zip() calls
- **Files modified:** embedding.py, test_embedding_cache.py
- **Commit:** d9ce994

**2. [Rule 1 - Bug] Fixed F841 unused variable `seen_set` in vector_store.py**
- **Found during:** Task 2 (ruff linting)
- **Issue:** `seen_set = set(seen.keys())` was assigned but never used
- **Fix:** Removed the unused assignment
- **Files modified:** vector_store.py
- **Commit:** d9ce994

**3. [Rule 1 - Bug] Fixed import order in test_vector_store_deduplication.py**
- **Found during:** Task 2 (ruff I001)
- **Issue:** Import block was not isort-sorted (blank line between stdlib and third-party)
- **Fix:** ruff --fix applied automatically
- **Commit:** d9ce994

**Note on pre-existing environment failures:**
- `tests/test_embedding_cache.py::test_health_status_omits_embedding_cache_when_empty` fails due to missing `hnswlib` module (pre-existing environment issue — Python 3.13 venv missing C-extension build). Confirmed failing before this plan's changes. Out of scope.
- `task before-push` CLI step fails due to `chroma-hnswlib` C++ build failure on macOS (known issue documented in MEMORY.md). Out of scope.

## Decisions Made

1. Dict-based deduplication placed AFTER the existing length-check guard and BEFORE lock acquisition — preserves existing validation and makes dedup logic isolated and testable
2. `strict=True` on zip() calls enforces that all four parallel lists remain length-aligned — any upstream bug that produces mismatched lists will raise immediately instead of silently truncating
3. Pre-existing B905 zip() linting errors in unrelated files fixed because `task before-push` requires all-green linting to proceed

## Self-Check: PASSED

Files created/modified exist:
- FOUND: agent-brain-server/tests/unit/storage/test_vector_store_deduplication.py
- FOUND: agent-brain-server/agent_brain_server/storage/vector_store.py
- FOUND: agent-brain-server/agent_brain_server/storage/postgres/backend.py

Commits exist:
- FOUND: 36513fd (TDD RED: test file)
- FOUND: 121b1ba (TDD GREEN: implementation)
- FOUND: d9ce994 (linting fixes)
