# Research: BM25 & Hybrid Retrieval

## Decision 1: BM25 Implementation Strategy
**Decision**: Use `rank-bm25` (specifically via LlamaIndex's `BM25Retriever`) for keyword search.
**Rationale**: LlamaIndex provides a clean abstraction for BM25 that integrates well with its `QueryFusionRetriever`. It allows building the index from nodes/chunks and handles the term frequency calculations.
**Alternatives considered**: 
- **Custom BM25**: Too much effort to maintain and optimize.
- **ChromaDB's full-text search**: Chroma doesn't have a robust built-in BM25 implementation that easily exposes scores for RRF combination in the same way LlamaIndex does.

## Decision 2: Hybrid Fusion Algorithm
**Decision**: Implement Reciprocal Rank Fusion (RRF) using LlamaIndex's `QueryFusionRetriever`.
**Rationale**: RRF is a robust, parameter-free (mostly) way to combine rankings from different systems (dense vs sparse). It handles cases where one system returns results the other doesn't.
**Alternatives considered**:
- **Weighted Score Sum**: Requires calibrating scores between vector (0-1 cosine) and BM25 (unbounded). Too complex to tune.
- **Relative Score Fusion**: Supported by LlamaIndex but RRF is more standard for hybrid retrieval.

## Decision 3: BM25 Persistence
**Decision**: Persist the BM25 index using LlamaIndex's built-in persistence if available, or serialize the underlying data.
**Rationale**: `BM25Retriever` in recent LlamaIndex versions supports disk-based persistence (`persist_path` and `disk_path`). This avoids rebuilding the index on every restart and keeps it synchronized with the vector store.
**Alternatives considered**: 
- **Rebuild on start**: Slow for larger corpora.
- **Manual Pickle**: Less clean than built-in methods.

## Decision 4: Alpha Weighting Implementation
**Decision**: Use `QueryFusionRetriever` with `mode="relative_score"` to support the `alpha` parameter.
**Rationale**: Traditional Reciprocal Rank Fusion (RRF) is rank-based and doesn't naturally support an alpha weight for score blending. `relative_score` normalization allows the `alpha` parameter to weight the relative contribution of vector vs. BM25 scores (e.g., `alpha=1.0` for pure vector, `alpha=0.0` for pure BM25).
**Alternatives considered**:
- **reciprocal_rerank**: Good default but lacks fine-grained alpha tuning.
- **Custom Fusion**: More complex to maintain.

## Decision 5: New Dependencies
**Decision**: Add `rank-bm25` and `llama-index-retrievers-bm25`.
**Rationale**: Required for BM25 support in LlamaIndex.
**Alternatives considered**: None.

## Technical Tasks for Phase 1
1. Define `QueryMode` Enum.
2. Update `QueryRequest` and `QueryResponse` models.
3. Implement `BM25IndexManager` for lifecycle and persistence.
4. Update `IndexingService` to call `BM25IndexManager`.
5. Update `QueryService` to use `QueryFusionRetriever`.
