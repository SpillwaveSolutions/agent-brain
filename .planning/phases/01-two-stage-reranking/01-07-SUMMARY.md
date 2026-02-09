---
phase: 01-two-stage-reranking
plan: 07
subsystem: documentation
tags: [docs, readme, user-guide, reranking]

# Dependency graph
requires:
  - phase: 01-05
    provides: QueryService integration with reranking
provides:
  - README documentation for reranking configuration
  - USER_GUIDE explanation of two-stage retrieval
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Documentation follows existing feature sections (GraphRAG pattern)"

key-files:
  modified:
    - agent-brain-server/README.md
    - docs/USER_GUIDE.md

key-decisions:
  - "README section placed after GraphRAG section, before Development Installation"
  - "USER_GUIDE section placed after Search Modes, before Indexing"
  - "Table of Contents updated to include new section"

# Metrics
duration: 5min
completed: 2026-02-07
---

# Phase 01 Plan 07: Documentation Updates Summary

**Updated README and USER_GUIDE with comprehensive two-stage reranking documentation**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-07
- **Completed:** 2026-02-07
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

### Task 1: Updated Server README

Added new section "Two-Stage Reranking (Feature 123)" to `/agent-brain-server/README.md` with:

- Feature overview explaining Stage 1 and Stage 2 retrieval
- Complete environment variable documentation:
  - `ENABLE_RERANKING` - Master switch (default: false)
  - `RERANKER_PROVIDER` - Provider selection (sentence-transformers or ollama)
  - `RERANKER_MODEL` - Model name for the provider
  - `RERANKER_TOP_K_MULTIPLIER` - Stage 1 retrieval multiplier (default: 10)
  - `RERANKER_MAX_CANDIDATES` - Cap on Stage 1 candidates (default: 100)
  - `RERANKER_BATCH_SIZE` - Batch size for inference (default: 32)
- Provider options table with latency estimates
- YAML configuration example
- Graceful degradation behavior explanation
- Response fields documentation (`rerank_score`, `original_rank`)
- Example JSON response

Section placed after GraphRAG Configuration, before Development Installation.

### Task 2: Updated USER_GUIDE

Added new section "Two-Stage Retrieval with Reranking" to `/docs/USER_GUIDE.md` with:

- Table of Contents entry for the new section
- How it works explanation:
  - Without reranking (default behavior)
  - With reranking enabled (two-stage process)
- Why reranking helps (bi-encoder vs cross-encoder)
- When to enable/disable reranking guidelines
- Configuration via environment variable and YAML
- Provider choices comparison:
  - sentence-transformers: Recommended, HuggingFace CrossEncoder, ~50ms
  - ollama: Fully local, chat completions, ~500ms
- Response fields documentation

Section placed after Search Modes, before Indexing.

## Files Modified

1. **agent-brain-server/README.md**
   - Added ~75 lines documenting reranking configuration
   - Includes code examples, tables, and JSON samples

2. **docs/USER_GUIDE.md**
   - Updated Table of Contents with new section link
   - Added ~65 lines explaining two-stage retrieval for users

## Verification

Both files contain:
- [x] `ENABLE_RERANKING` environment variable documentation
- [x] YAML configuration example
- [x] Provider options with trade-offs
- [x] Graceful degradation mention
- [x] Response fields (`rerank_score`, `original_rank`)

## Must-Haves Verification

| Requirement | Status |
|-------------|--------|
| README documents how to enable reranking | DONE |
| USER_GUIDE explains two-stage retrieval concept | DONE |
| Environment variables are documented | DONE |
| YAML config example is provided | DONE |
| Provider options documented with latency | DONE |
| Graceful degradation is explained | DONE |

## Deviations from Plan

- Added `RERANKER_BATCH_SIZE` to README (was defined in settings.py but not in original plan)
- Added response fields section to USER_GUIDE (brief mention for user awareness)

## Next Steps

Phase 01 documentation is complete. Remaining work:
- Plan 01-06: Unit tests for reranking functionality
- Consider integration tests with reranking enabled

---
*Phase: 01-two-stage-reranking*
*Wave: 4 (Documentation)*
*Completed: 2026-02-07*
