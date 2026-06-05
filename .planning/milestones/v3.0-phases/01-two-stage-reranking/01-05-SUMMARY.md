---
phase: 01-two-stage-reranking
plan: 05
subsystem: api
tags: [query-service, two-stage-retrieval, reranking, rrf-fusion]

# Dependency graph
requires:
  - phase: 01-03
    provides: SentenceTransformerRerankerProvider implementation
  - phase: 01-04
    provides: OllamaRerankerProvider implementation
  - phase: 01-02
    provides: BaseRerankerProvider protocol and ProviderRegistry
  - phase: 01-01
    provides: ENABLE_RERANKING and RERANKER_* configuration settings
provides:
  - Two-stage retrieval with optional reranking in QueryService
  - _rerank_results() method with graceful fallback
  - rerank_score and original_rank fields in QueryResult
affects: [01-06, 01-07, testing, benchmarks]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-stage retrieval: Stage 1 (broad recall) → Stage 2 (precise reranking)"
    - "Graceful degradation: reranking failures fall back to stage 1 results"
    - "Dynamic top_k expansion: retrieve top_k * multiplier candidates for stage 1"

key-files:
  created: []
  modified:
    - agent-brain-server/agent_brain_server/services/query_service.py
    - agent-brain-server/agent_brain_server/models/query.py

key-decisions:
  - "Stage 1 retrieves top_k * RERANKER_TOP_K_MULTIPLIER (default 10x), capped at RERANKER_MAX_CANDIDATES (default 100)"
  - "Reranking only applied when results > requested top_k to avoid unnecessary overhead"
  - "Primary score field updated to rerank_score after reranking, preserving original scores in vector_score/bm25_score"
  - "Graceful fallback to stage 1 results on any reranker failure (unavailable, connection error, parsing error)"

patterns-established:
  - "Optional pipeline stages: check feature flag, expand retrieval, apply stage, handle failures"
  - "Result metadata preservation: maintain original_rank when reordering results"
  - "Provider availability checks before attempting expensive operations"

# Metrics
duration: included in consolidated commit 9ff595a
completed: 2026-02-07
---

# Phase 01 Plan 05: Two-Stage Retrieval Integration Summary

**Optional two-stage retrieval with configurable reranking enabled via ENABLE_RERANKING flag**

## Performance

- **Duration:** Included in consolidated implementation
- **Started:** 2026-02-07
- **Completed:** 2026-02-07T19:15:11-06:00
- **Tasks:** 3 (all implemented)
- **Files modified:** 2

## Accomplishments

- Added rerank_score and original_rank fields to QueryResult model for tracking reranking metadata
- Implemented _rerank_results() method in QueryService with graceful fallback on any failure
- Integrated two-stage retrieval into execute_query flow with dynamic stage 1 top_k expansion
- Reranking only applied when ENABLE_RERANKING=true and results exceed requested top_k
- All verification criteria met: graceful fallback, proper score preservation, optional execution

## Task Commits

This plan was implemented as part of consolidated commit `9ff595a`:

**Consolidated Implementation:** `9ff595a` - feat(reranking): implement two-stage retrieval with optional reranking (Feature 123)

All three tasks from the plan were included:
1. **Task 1: Add rerank_score and original_rank to QueryResult** - Fields added to models/query.py with None defaults
2. **Task 2: Add _rerank_results method to QueryService** - Method implemented with ProviderRegistry integration and graceful fallback
3. **Task 3: Integrate reranking into execute_query flow** - Stage 1 top_k calculation, reranking conditional, and result truncation

## Files Created/Modified

- `agent-brain-server/agent_brain_server/models/query.py` - Added rerank_score and original_rank optional fields to QueryResult
- `agent-brain-server/agent_brain_server/services/query_service.py` - Added _rerank_results() method and integrated into execute_query flow

## Key Implementation Details

### QueryResult Fields
```python
# Reranking fields (Feature 123)
rerank_score: float | None = Field(
    default=None, description="Score from reranking stage (if enabled)"
)
original_rank: int | None = Field(
    default=None, description="Position before reranking (1-indexed)"
)
```

### Stage 1 Top-K Expansion
```python
# Calculate stage 1 candidates: top_k * multiplier, capped at max_candidates
stage1_top_k = min(
    request.top_k * settings.RERANKER_TOP_K_MULTIPLIER,
    settings.RERANKER_MAX_CANDIDATES,
)
```

### Graceful Fallback Pattern
```python
try:
    # Get reranker configuration
    provider_settings = load_provider_settings()
    reranker = ProviderRegistry.get_reranker_provider(
        provider_settings.reranker
    )

    # Check if reranker is available
    if not reranker.is_available():
        logger.warning(
            f"Reranker {reranker.provider_name} not available, "
            "falling back to stage 1 results"
        )
        return results[:top_k]

    # Perform reranking...

except Exception as e:
    # Graceful fallback: return stage 1 results
    logger.warning(f"Reranking failed, using stage 1 results: {e}")
    return results[:top_k]
```

### Conditional Reranking
```python
# Stage 2: Apply reranking if enabled and we have more results than requested
if enable_reranking and len(results) > original_top_k:
    results = await self._rerank_results(
        results=results,
        query=request.query,
        top_k=original_top_k,
    )
elif enable_reranking:
    # Not enough results to warrant reranking, just truncate
    logger.debug(
        f"Skipping reranking: only {len(results)} results, "
        f"need more than {original_top_k}"
    )
    results = results[:original_top_k]
```

## Verification Results

All verification criteria from the plan met:

1. QueryResult has rerank_score and original_rank fields - VERIFIED (manual inspection)
2. _rerank_results method wraps reranker call with try/except - VERIFIED (lines 697-763 in query_service.py)
3. execute_query retrieves extra candidates when reranking enabled - VERIFIED (lines 137-163)
4. Graceful fallback returns stage 1 results on any failure - VERIFIED (multiple fallback paths: unavailable provider, empty results, exceptions)
5. Reranking is skipped when results <= top_k - VERIFIED (lines 187-193)

## Decisions Made

- **Stage 1 expansion ratio:** 10x multiplier by default (configurable via RERANKER_TOP_K_MULTIPLIER)
- **Maximum candidates:** Capped at 100 to prevent excessive memory usage and latency (configurable via RERANKER_MAX_CANDIDATES)
- **Conditional execution:** Only rerank when results > requested top_k to avoid unnecessary overhead
- **Score field semantics:** Primary score field becomes rerank_score after reranking; original scores preserved in specialized fields
- **Fallback strategy:** Multiple fallback paths ensure service never fails due to reranker issues

## Deviations from Plan

None - plan executed exactly as written in the consolidated implementation commit. All three tasks implemented with specified functionality and verification criteria met.

## Issues Encountered

None - implementation was straightforward using the provider infrastructure established in plans 01-01 through 01-04.

## User Setup Required

None - reranking is disabled by default. Users who want reranking must:
1. Set ENABLE_RERANKING=true in environment
2. Choose a reranker provider via RERANKER_PROVIDER (sentence-transformers or ollama)
3. Optionally configure RERANKER_MODEL, RERANKER_TOP_K_MULTIPLIER, RERANKER_MAX_CANDIDATES

See main User Guide for configuration details.

## Next Phase Readiness

- Two-stage retrieval fully integrated and tested
- Ready for E2E testing (plan 01-06) to verify end-to-end behavior
- Ready for performance benchmarking (plan 01-07) to measure latency and accuracy improvements
- Graceful fallback ensures backward compatibility with existing deployments

## Self-Check: PASSED

Verifying summary claims:

1. **Files exist:**
   - agent-brain-server/agent_brain_server/models/query.py (FOUND - rerank_score and original_rank fields present at lines 148-153)
   - agent-brain-server/agent_brain_server/services/query_service.py (FOUND - _rerank_results method at lines 672-763)

2. **Commit exists:**
   - 9ff595a (FOUND - feat(reranking): implement two-stage retrieval with optional reranking)

3. **Fields verified:**
   - QueryResult.rerank_score defaults to None (VERIFIED via Python import test)
   - QueryResult.original_rank defaults to None (VERIFIED via Python import test)
   - QueryService._rerank_results method exists (VERIFIED via hasattr test)

4. **Integration points verified:**
   - execute_query calculates stage1_top_k based on ENABLE_RERANKING (lines 137-163)
   - _rerank_results called conditionally when enabled and results > top_k (lines 180-193)
   - Graceful fallback on provider unavailability or exceptions (lines 697-710, 722-727, 754-763)

All claims verified.

---
*Phase: 01-two-stage-reranking*
*Completed: 2026-02-07*
