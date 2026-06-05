---
phase: 06-postgresql-backend
plan: 02
subsystem: database
tags: [postgres, pgvector, tsvector, sqlalchemy, vector-search, keyword-search, rrf, hybrid-search]

# Dependency graph
requires:
  - phase: 06-postgresql-backend
    plan: 01
    provides: PostgresConfig, PostgresConnectionManager, PostgresSchemaManager, StorageError types
  - phase: 05-storage-abstraction
    provides: StorageBackendProtocol (11 methods), SearchResult, EmbeddingMetadata, StorageError
provides:
  - VectorOps class for pgvector vector search with cosine/L2/inner_product distance metrics
  - KeywordOps class for tsvector keyword search with weighted relevance (A/B/C)
  - PostgresBackend implementing all 11 StorageBackendProtocol methods plus hybrid_search_with_rrf and close
affects: [06-03-PLAN, phase-07-testing]

# Tech tracking
tech-stack:
  added: [pgvector operators (<=>, <->, <#>), tsvector (websearch_to_tsquery, ts_rank, setweight), RRF (Reciprocal Rank Fusion)]
  patterns: [distance-to-similarity normalization, per-query max score normalization, RRF fusion with configurable weights, JSONB containment filter (@>)]

key-files:
  created:
    - agent-brain-server/agent_brain_server/storage/postgres/vector_ops.py
    - agent-brain-server/agent_brain_server/storage/postgres/keyword_ops.py
    - agent-brain-server/agent_brain_server/storage/postgres/backend.py
  modified:
    - agent-brain-server/agent_brain_server/storage/postgres/__init__.py

key-decisions:
  - "VectorOps uses json.dumps() for embedding serialization with ::vector cast in SQL"
  - "KeywordOps extracts title from metadata filename/title fields for tsvector weight A"
  - "RRF uses k=60 constant per literature recommendation"
  - "PostgresBackend.initialize() discovers dimensions from ProviderRegistry at startup"
  - "Individual upserts (not batched) for MVP -- batch optimization deferred"

patterns-established:
  - "Distance-to-similarity normalization: cosine(1-d), L2(1/(1+d)), inner_product(-d)"
  - "Per-query max normalization for keyword scores (matching ChromaBackend BM25 approach)"
  - "RRF hybrid fusion: fetch 2x top_k from each source, merge with weighted rank scores"
  - "JSONB containment filter via metadata @> :filter::jsonb for metadata-based queries"

# Metrics
duration: 4min
completed: 2026-02-11
---

# Phase 6 Plan 02: PostgreSQL Core Operations Summary

**pgvector VectorOps with 3 distance metrics, tsvector KeywordOps with weighted relevance, and PostgresBackend implementing all 11 StorageBackendProtocol methods with RRF hybrid search**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-11T17:11:43Z
- **Completed:** 2026-02-11T17:16:13Z
- **Tasks:** 2/2
- **Files created/modified:** 4

## Accomplishments
- VectorOps supporting cosine, L2, and inner_product distance metrics with all scores normalized to 0-1 (higher=better)
- KeywordOps using weighted tsvector (title=A, summary=B, content=C) with configurable language and websearch_to_tsquery()
- PostgresBackend implementing all 11 StorageBackendProtocol methods plus hybrid_search_with_rrf() and close()
- RRF hybrid search combining vector and keyword results with configurable weights (k=60)
- Updated package exports in __init__.py (PostgresBackend, PostgresConfig, PostgresConnectionManager, PostgresSchemaManager)

## Task Commits

Each task was committed atomically:

1. **Task 1: Vector and keyword operations modules** - `d639454` (feat)
2. **Task 2: PostgresBackend implementing StorageBackendProtocol** - `705954b` (feat)

## Files Created/Modified
- `agent-brain-server/agent_brain_server/storage/postgres/vector_ops.py` - VectorOps class: pgvector search with 3 distance metrics, embedding upsert
- `agent-brain-server/agent_brain_server/storage/postgres/keyword_ops.py` - KeywordOps class: tsvector search with weighted relevance, document upsert with tsvector
- `agent-brain-server/agent_brain_server/storage/postgres/backend.py` - PostgresBackend: all 11 protocol methods, RRF hybrid search, lifecycle management
- `agent-brain-server/agent_brain_server/storage/postgres/__init__.py` - Updated exports to include all 4 postgres package classes

## Decisions Made
- Used `json.dumps()` for embedding vector serialization with `::vector` cast in SQL (SQLAlchemy text() binding)
- KeywordOps extracts title from `metadata.get('filename') or metadata.get('title')` for tsvector weight A
- RRF constant k=60 per academic literature and research recommendations
- PostgresBackend.initialize() discovers embedding dimensions dynamically from ProviderRegistry at startup
- Individual document upserts for MVP (batch optimization deferred to future optimization pass)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff E501 line-too-long in KeywordOps SQL**
- **Found during:** Task 1 (keyword_ops.py)
- **Issue:** setweight() SQL lines in INSERT statement exceeded 88 char line limit
- **Fix:** Restructured SQL with line breaks inside setweight() calls to stay under limit
- **Files modified:** keyword_ops.py
- **Verification:** ruff check passes
- **Committed in:** d639454 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 formatting fix)
**Impact on plan:** Cosmetic only. No scope creep.

## Issues Encountered
None - all tasks completed on first attempt after auto-fix.

## Verification Results
- mypy strict (--ignore-missing-imports): 7 source files (all postgres modules), no errors
- ruff check: all passed
- black --check: all formatted correctly
- Import verification: `from agent_brain_server.storage.postgres import PostgresBackend, PostgresConfig` succeeds
- Protocol method check: all 11 methods present on PostgresBackend
- Existing test suite: 559 passed, 0 failed (no regressions)

## User Setup Required
None - no external service configuration required. PostgreSQL database not needed until Plan 03 integration testing.

## Next Phase Readiness
- Plan 03 (Integration) can now register PostgresBackend in the storage factory
- All 7 postgres modules (config, connection, schema, vector_ops, keyword_ops, backend, __init__) are complete and type-checked
- PostgresBackend can be instantiated with a PostgresConfig and initialized against a running PostgreSQL+pgvector instance
- Docker Compose template from Plan 01 provides the PostgreSQL service

## Self-Check: PASSED

- All 4 files: FOUND
- All 2 commits: FOUND (d639454, 705954b)

---
*Phase: 06-postgresql-backend*
*Completed: 2026-02-11*
