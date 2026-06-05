---
phase: 01-two-stage-reranking
plan: 03
subsystem: api
tags: [reranker, sentence-transformers, cross-encoder, provider-pattern]

# Dependency graph
requires:
  - phase: 01-01
    provides: RerankerConfig for provider configuration
  - phase: 01-02
    provides: BaseRerankerProvider class and ProviderRegistry
provides:
  - SentenceTransformerRerankerProvider using CrossEncoder
  - sentence-transformers dependency in pyproject.toml
affects: [01-05, 01-06, 01-07]

# Tech tracking
tech-stack:
  added:
    - sentence-transformers ^3.4.0
  patterns:
    - "CrossEncoder.rank() for efficient batch reranking"
    - "asyncio.to_thread() for non-blocking CPU-bound inference"
    - "Lazy model loading to avoid startup overhead"

key-files:
  created:
    - agent-brain-server/agent_brain_server/providers/reranker/sentence_transformers.py
  modified:
    - agent-brain-server/pyproject.toml
    - agent-brain-server/agent_brain_server/providers/reranker/__init__.py

key-decisions:
  - "CrossEncoder.rank() returns sorted results with corpus_id and score"
  - "Thread pool execution via asyncio.to_thread for CPU-bound operations"
  - "Lazy model loading delays ~500MB model download until first use"

patterns-established:
  - "Reranker runs inference in thread pool to avoid blocking async loop"
  - "Model loading deferred until first rerank call"

# Metrics
duration: 8min
completed: 2026-02-07
---

# Phase 01 Plan 03: SentenceTransformer Reranker Provider Summary

**SentenceTransformerRerankerProvider using CrossEncoder with async thread pool execution**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-07T18:50:00Z
- **Completed:** 2026-02-07T18:58:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Added sentence-transformers ^3.4.0 to pyproject.toml dependencies
- Created SentenceTransformerRerankerProvider using CrossEncoder.rank() method
- Implemented async reranking with asyncio.to_thread() for non-blocking inference
- Lazy model loading to avoid startup overhead
- Provider auto-registers with ProviderRegistry on import
- All verification commands passed successfully

## Task Commits

Each task corresponds to the plan specification:

1. **Task 1: Add sentence-transformers dependency** - pyproject.toml updated with `sentence-transformers = "^3.4.0"`
2. **Task 2: Implement SentenceTransformerRerankerProvider** - Full implementation with CrossEncoder.rank()
3. **Task 3: Update reranker package exports** - __init__.py updated (also includes OllamaRerankerProvider from parallel wave)

## Files Created/Modified

- `agent-brain-server/pyproject.toml` - Added sentence-transformers ^3.4.0 under "Reranking dependencies" section
- `agent-brain-server/agent_brain_server/providers/reranker/sentence_transformers.py` - Full provider implementation
- `agent-brain-server/agent_brain_server/providers/reranker/__init__.py` - Updated exports

## Key Implementation Details

### CrossEncoder Usage
```python
ranked = model.rank(
    query,
    documents,
    top_k=top_k,
    return_documents=False,  # Efficiency: don't return text
)
return [(int(r["corpus_id"]), float(r["score"])) for r in ranked]
```

### Async Thread Pool Pattern
```python
results = await asyncio.to_thread(
    self._rerank_sync,
    query,
    documents,
    effective_top_k,
)
```

### Lazy Model Loading
```python
def _ensure_model_loaded(self) -> CrossEncoder:
    if self._cross_encoder is None:
        self._cross_encoder = CrossEncoder(self._model)
    return self._cross_encoder
```

## Verification Results

All verification commands passed:
- `from sentence_transformers import CrossEncoder` - Success
- `from agent_brain_server.providers.reranker.sentence_transformers import SentenceTransformerRerankerProvider` - Success
- `from agent_brain_server.providers.reranker import SentenceTransformerRerankerProvider` - Success
- `ProviderRegistry.get_available_reranker_providers()` returns `['ollama', 'sentence-transformers']`

## Quality Checks

- black: All files properly formatted
- ruff: No linting issues in new file
- mypy: No type errors in new file

## Deviations from Plan

None - plan executed exactly as written. Note: OllamaRerankerProvider was added in parallel by another wave (01-04), so __init__.py includes both providers.

## Issues Encountered

- Poetry environment was linked to wrong project directory; resolved by creating local .venv with pip install -e .
- sentence-transformers pulls in torch (~2GB) as expected; installation completed successfully

## User Setup Required

None - sentence-transformers auto-downloads models on first use. Default model is `cross-encoder/ms-marco-MiniLM-L-6-v2` (~80MB download on first use).

## Next Phase Readiness

- SentenceTransformerRerankerProvider ready for integration with QueryService (plan 01-05)
- Provider can be selected via RERANKER_PROVIDER=sentence-transformers environment variable
- Default model can be overridden via RERANKER_MODEL setting

---
*Phase: 01-two-stage-reranking*
*Completed: 2026-02-07*
