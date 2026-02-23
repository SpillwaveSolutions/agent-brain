# Search Modes

Agent Brain supports five search modes for different retrieval needs.

## BM25 (Keyword Search)
Best for exact term matching — function names, error codes, identifiers.
Speed: 10-50ms. No embedding cost.

## Vector (Semantic Search)
Best for conceptual queries — "how does authentication work?"
Speed: 800-1500ms. Uses embedding API.

## Hybrid Search
Combines BM25 and vector using Reciprocal Rank Fusion.
Alpha parameter: 0.0 = pure BM25, 1.0 = pure vector.
Default alpha: 0.5 (balanced).

## Graph Search
Traverses entity relationships extracted during indexing.
Best for "what calls what" or dependency queries.

## Multi-Mode Search
Runs BM25 + Vector + Graph in parallel, fuses with RRF.
Most comprehensive but slowest. Use for deep investigation.

## Choosing a Mode

| Query Type | Recommended Mode |
|-----------|-----------------|
| Error codes, exact names | BM25 |
| Conceptual questions | Vector |
| General search | Hybrid |
| Relationship queries | Graph |
| Thorough investigation | Multi |
