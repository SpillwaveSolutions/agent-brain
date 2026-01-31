# Research: GraphRAG Integration

**Feature**: 113-graphrag-integration
**Date**: 2026-01-30
**Status**: Complete

## Research Summary

This document captures research findings for implementing GraphRAG capabilities in doc-serve.

---

## 1. LlamaIndex PropertyGraphIndex

### Decision
Use LlamaIndex's `PropertyGraphIndex` with `SimplePropertyGraphStore` as the default graph storage backend.

### Rationale
- **Already a dependency**: llama-index-core ^0.14.0 is already installed
- **Native integration**: PropertyGraphIndex works seamlessly with existing LlamaIndex document structures
- **Persistence**: SimplePropertyGraphStore provides JSON file persistence via `StorageContext`
- **No server required**: In-memory with disk persistence, matching doc-serve's local-first philosophy

### Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| SimplePropertyGraphStore | Zero dependencies, JSON persistence, easy debugging | Memory-limited for large graphs | **Default** |
| Kuzu | Embedded DB, Cypher queries, better performance | New dependency, more complex | **Optional upgrade** |
| Neo4j | Enterprise features, distributed | Requires server, complex setup | Rejected (out of scope) |
| NetworkX | Simple graph library | No persistence, no query optimization | Rejected |

### Implementation Pattern

```python
from llama_index.core import PropertyGraphIndex, StorageContext, load_index_from_storage
from llama_index.core.graph_stores import SimplePropertyGraphStore

# Create index
index = PropertyGraphIndex.from_documents(documents)

# Persist
index.storage_context.persist("./graph_index")

# Load
storage_context = StorageContext.from_defaults(persist_dir="./graph_index")
index = load_index_from_storage(storage_context)
```

---

## 2. Entity Extraction Strategies

### Decision
Use hybrid extraction: LLM-based for documentation, AST metadata for code.

### Rationale
- **Cost efficiency**: Code relationships extracted from existing AST metadata (no LLM calls)
- **Quality**: LLM extraction (langextract) provides semantic understanding for prose
- **Flexibility**: Both can be independently enabled/disabled

### LLM Extraction Options

| Library | Latest Version | Pros | Cons |
|---------|---------------|------|------|
| langextract (Google) | ^0.1.x (Jan 2026) | Source grounding, multi-LLM support, schema-based | Newer library |
| LlamaIndex SimpleLLMPathExtractor | Built-in | No new dependency | Less flexible schemas |
| LlamaIndex DynamicLLMPathExtractor | Built-in | Auto-infers ontology | Higher token usage |

### Decision
Use LlamaIndex's built-in `DynamicLLMPathExtractor` for initial implementation (no new dependency), with langextract as future enhancement.

### Code Metadata Extraction

Existing AST metadata provides:
- `imports`: List of imported modules/packages
- `symbol_name`: Function, class, or method name
- `symbol_type`: "function", "class", "method"
- `parent_symbol`: For nested symbols

**Extractable relationships**:
- `imports` → Module dependency edges
- `symbol_name.contains(.)` → Containment hierarchy (class.method)
- `file_path` → File-to-symbol edges

---

## 3. Graph Query Modes

### Decision
Add two new QueryMode values: GRAPH and MULTI.

### Rationale
- **GRAPH**: Pure graph traversal for relationship exploration
- **MULTI**: Triple fusion (vector + BM25 + graph) for comprehensive results

### Fusion Strategy

| Mode | Components | Fusion Method |
|------|------------|---------------|
| HYBRID (existing) | Vector + BM25 | Weighted sum with alpha parameter |
| MULTI (new) | Vector + BM25 + Graph | Reciprocal Rank Fusion (RRF) |

**RRF Formula**: `score(d) = Σ 1/(k + rank_i(d))` where k=60 (standard constant)

### Query Parameters

New parameters for graph queries:
- `traversal_depth`: Max hops from query entities (default: 2)
- `include_relationships`: Filter by relationship types

---

## 4. Configuration Design

### Decision
All graph settings have safe defaults that disable the feature.

### Settings Structure

```python
# GraphRAG settings (optional feature)
ENABLE_GRAPH_INDEX: bool = False           # Master switch
GRAPH_STORE_TYPE: str = "simple"           # "simple" or "kuzu"
GRAPH_INDEX_PATH: str = "./graph_index"    # Persistence directory
GRAPH_EXTRACTION_MODEL: str = "claude-haiku-4-5"  # For LLM extraction
GRAPH_MAX_TRIPLETS_PER_CHUNK: int = 10     # Limit per chunk
GRAPH_USE_CODE_METADATA: bool = True       # Extract from AST
GRAPH_USE_LLM_EXTRACTION: bool = True      # Use LLM for docs
GRAPH_TRAVERSAL_DEPTH: int = 2             # Default query depth
```

---

## 5. Persistence Strategy

### Decision
Graph index persists to `./graph_index/` subdirectory, following existing patterns.

### File Structure

```text
{state_dir}/
├── chroma_db/           # Existing vector store
├── bm25_index/          # Existing BM25 index
└── graph_index/         # NEW: Graph storage
    ├── graph_store.json     # SimplePropertyGraphStore data
    ├── docstore.json        # Document references
    └── index_store.json     # Index metadata
```

### Rationale
- Matches existing `storage_paths.py` patterns
- Independent rebuild without affecting vector/BM25
- Easy backup and migration

---

## 6. Error Handling

### Decision
Graceful degradation when GraphRAG is disabled or unavailable.

### Error Cases

| Scenario | Behavior |
|----------|----------|
| GRAPH/MULTI mode with GraphRAG disabled | HTTP 400: "GraphRAG not enabled. Set ENABLE_GRAPH_INDEX=true" |
| LLM extraction fails | Log warning, continue with code metadata only |
| Graph store corruption | Allow independent rebuild via `/index?rebuild_graph=true` |
| Kuzu not installed | Fall back to SimplePropertyGraphStore with warning |

---

## 7. Dependency Management

### Decision
Optional dependencies installed only when needed.

### pyproject.toml Changes

```toml
[tool.poetry.dependencies]
# Existing dependencies unchanged

[tool.poetry.extras]
graphrag = ["langextract"]
graphrag-kuzu = ["llama-index-graph-stores-kuzu"]

# Or using optional groups:
[tool.poetry.group.graphrag]
optional = true

[tool.poetry.group.graphrag.dependencies]
langextract = "^0.1.0"

[tool.poetry.group.graphrag-kuzu]
optional = true

[tool.poetry.group.graphrag-kuzu.dependencies]
llama-index-graph-stores-kuzu = "^0.6.0"
```

### Installation Commands

```bash
# Basic GraphRAG (uses built-in extractors)
poetry install

# With langextract for enhanced extraction
poetry install --with graphrag

# With Kuzu for production graph storage
poetry install --with graphrag-kuzu
```

---

## 8. Performance Considerations

### Decision
Lazy initialization and conditional execution.

### Optimizations

1. **Lazy graph store**: Only initialize when first graph operation occurs
2. **Batch extraction**: Process chunks in batches during indexing
3. **Parallel execution**: Run vector, BM25, and graph queries concurrently in MULTI mode
4. **Index skipping**: Skip graph index entirely when disabled

### Benchmarks (Target)

| Operation | Target | Notes |
|-----------|--------|-------|
| Graph indexing | +50% over base | LLM extraction adds time |
| Graph query | < 500ms | For 10k doc index |
| MULTI query | < 2s | Parallel execution |
| Disabled overhead | 0ms | No code paths executed |

---

## Research Conclusion

All technical decisions are resolved. No NEEDS CLARIFICATION items remain.

**Key Decisions Summary**:
1. Use LlamaIndex PropertyGraphIndex with SimplePropertyGraphStore (built-in)
2. Use LlamaIndex DynamicLLMPathExtractor for LLM extraction (no new dependency initially)
3. Extract code relationships from existing AST metadata
4. Add GRAPH and MULTI query modes with RRF fusion
5. All configuration defaults to disabled/minimal
6. Optional dependencies via poetry extras
