# GraphRAG Integration Plan for Doc-Serve

## Overview

Add **optional** lightweight GraphRAG capabilities to doc-serve using LlamaIndex's PropertyGraphIndex with SimplePropertyGraphStore (and optional Kuzu upgrade path), following the existing patterns for BM25 and ChromaDB vector storage.

**Key Design Principle**: GraphRAG is entirely optional. The system works exactly as before when disabled. Users opt-in via configuration.

## Research Summary

### Lightweight Graph Options for LlamaIndex

| Option | Type | Persistence | Server Required | Best For |
|--------|------|-------------|-----------------|----------|
| **SimplePropertyGraphStore** | In-memory + JSON | Yes (JSON file) | No | Development, small deployments |
| **Kuzu** | Embedded DB | Yes (file-based) | No | Production local, Cypher queries |
| Neo4j | Server-based | Yes | Yes | Enterprise, distributed |

**Approach**: Implement both as configurable options:
- `SimplePropertyGraphStore` - Default, zero dependencies
- `Kuzu` - Optional upgrade for larger graphs via `GRAPH_STORE_TYPE=kuzu`

### Key Components

- **PropertyGraphIndex**: Modern graph index with entity/relationship extraction
- **SimplePropertyGraphStore**: Lightweight, JSON file persistence (default)
- **Kuzu**: Embedded graph DB with Cypher support (optional)
- **LangExtract**: Google's library for schema-based entity extraction with source grounding
- **Code Metadata Extraction**: Use existing AST metadata (imports, symbols) for code relationships

## Current Architecture (For Context)

```
doc-serve-server/doc_serve_server/
├── storage/vector_store.py      # ChromaDB integration
├── indexing/bm25_index.py       # BM25 retriever
├── services/query_service.py    # Hybrid search (vector + BM25)
├── services/indexing_service.py # Document indexing pipeline
└── config/settings.py           # Configuration
```

**Current Query Modes**: VECTOR, BM25, HYBRID (weighted fusion)

## Implementation Plan

### Phase 1: Graph Store Infrastructure

**Files to create/modify:**

1. **Create `doc_serve_server/storage/graph_store.py`**
   - `GraphStoreManager` class following `VectorStoreManager` pattern
   - Wrap `SimplePropertyGraphStore` with async interface
   - Persistence to `./graph_index/graph_store.json`
   - Singleton pattern via `get_graph_store()`

2. **Update `doc_serve_server/config/settings.py`**
   ```python
   # GraphRAG settings (optional feature)
   ENABLE_GRAPH_INDEX: bool = False  # OFF by default, opt-in
   GRAPH_STORE_TYPE: str = "simple"  # "simple" or "kuzu"
   GRAPH_INDEX_PATH: str = "./graph_index"
   GRAPH_EXTRACTION_MODEL: str = "claude-haiku-4-5"  # For LangExtract
   GRAPH_MAX_TRIPLETS_PER_CHUNK: int = 10
   GRAPH_USE_CODE_METADATA: bool = True  # Extract from AST metadata
   GRAPH_USE_LLM_EXTRACTION: bool = True  # Use LangExtract for docs
   ```

3. **Update `storage_paths.py`**
   - Add `data/graph_index` to SUBDIRECTORIES

### Phase 2: Graph Index Building

**Files to modify:**

1. **Create `doc_serve_server/indexing/graph_index.py`**
   - `GraphIndexManager` class
   - Build PropertyGraphIndex from documents/chunks
   - Extract entities and relationships using LLM
   - Persist graph store to disk
   - Load from disk on startup

2. **Update `doc_serve_server/services/indexing_service.py`**
   - Add graph index building after BM25 (around line 383)
   - Progress callback for graph building stage
   - Handle graph persistence

### Phase 3: Graph Retrieval

**Files to modify:**

1. **Update `doc_serve_server/models/query.py`**
   ```python
   class QueryMode(str, Enum):
       VECTOR = "vector"
       BM25 = "bm25"
       HYBRID = "hybrid"
       GRAPH = "graph"        # NEW: Graph-only traversal
       MULTI = "multi"        # NEW: All three combined
   ```

2. **Update `doc_serve_server/services/query_service.py`**
   - Add `_execute_graph_query()` method
   - Add `_execute_multi_query()` for triple fusion
   - Use `QueryFusionRetriever` or custom RRF for combining results
   - Graph retriever for entity/relationship traversal

### Phase 4: API Updates

**Files to modify:**

1. **Update `doc_serve_server/api/routers/query.py`**
   - Support new query modes in endpoint
   - Add graph-specific parameters (traversal depth, etc.)

2. **Update `doc_serve_server/api/routers/index.py`**
   - Add graph rebuild endpoint
   - Status endpoint for graph index

### Phase 5: CLI Updates

**Files to modify:**

1. **Update `doc-svr-ctl/doc_svr_ctl/commands/`**
   - Add `--mode graph` and `--mode multi` options to query command
   - Add graph index status to status command

## Optional Feature Behavior

When `ENABLE_GRAPH_INDEX=False` (default):
- **Indexing**: Skips graph building entirely (no LLM calls for entity extraction)
- **Query modes**: GRAPH and MULTI modes return error "GraphRAG not enabled"
- **Storage**: No graph_index directory created
- **Performance**: Zero overhead, identical to current system

When `ENABLE_GRAPH_INDEX=True`:
- **Indexing**: Builds graph index after BM25 (adds processing time)
- **Query modes**: All modes available including GRAPH and MULTI
- **Storage**: Creates graph_index directory with graph_store.json

```python
# In indexing_service.py
if settings.ENABLE_GRAPH_INDEX:
    await self._build_graph_index(chunks, progress_callback)

# In query_service.py
if request.mode in (QueryMode.GRAPH, QueryMode.MULTI):
    if not settings.ENABLE_GRAPH_INDEX:
        raise HTTPException(400, "GraphRAG not enabled. Set ENABLE_GRAPH_INDEX=true")
```

## Key Implementation Details

### Graph Store Factory Pattern (Both Options)

```python
from llama_index.core.graph_stores import SimplePropertyGraphStore

class GraphStoreManager:
    def __init__(self, persist_dir: str = "./graph_index", store_type: str = "simple"):
        self.persist_dir = Path(persist_dir)
        self.store_type = store_type
        self.graph_store = None

    async def initialize(self) -> None:
        if self.store_type == "kuzu":
            from llama_index.graph_stores.kuzu import KuzuPropertyGraphStore
            db_path = self.persist_dir / "kuzu.db"
            self.graph_store = KuzuPropertyGraphStore(db_path=str(db_path))
        else:  # "simple" default
            persist_path = self.persist_dir / "graph_store.json"
            if persist_path.exists():
                self.graph_store = SimplePropertyGraphStore.from_persist_path(str(persist_path))
            else:
                self.graph_store = SimplePropertyGraphStore()

    async def persist(self) -> None:
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        if self.store_type == "simple":
            self.graph_store.persist(str(self.persist_dir / "graph_store.json"))
        # Kuzu persists automatically to db_path
```

### Triple Retrieval Fusion (Extend Existing RRF)

```python
# In query_service.py - extend existing _execute_hybrid_query pattern
async def _execute_multi_query(self, request: QueryRequest) -> list[QueryResult]:
    """Execute vector + BM25 + graph search with RRF fusion."""
    # Run all three in parallel
    vector_results, bm25_results, graph_results = await asyncio.gather(
        self._execute_vector_query(request),
        self._execute_bm25_query(request),
        self._execute_graph_query(request),
    )

    # Normalize and fuse using existing RRF pattern
    # alpha for vector, beta for BM25, gamma for graph
    # Combined: alpha * vector + beta * bm25 + gamma * graph
    return self._fuse_results(vector_results, bm25_results, graph_results, request)
```

### Hybrid Entity Extraction (LangExtract + Code Metadata)

```python
# For documents: Use LangExtract with source grounding
from langextract import extract

async def extract_from_docs(chunks: list[TextChunk]) -> list[Triple]:
    """Extract entities/relationships from doc chunks using LangExtract."""
    triples = []
    for chunk in chunks:
        if chunk.source_type == "doc":
            result = extract(
                text=chunk.text,
                prompt="Extract entities and relationships",
                llm=settings.GRAPH_EXTRACTION_MODEL,
            )
            triples.extend(result.triples)
    return triples

# For code: Use existing AST metadata
def extract_from_code_metadata(chunks: list[CodeChunk]) -> list[Triple]:
    """Extract relationships from code chunk metadata."""
    triples = []
    for chunk in chunks:
        if chunk.source_type == "code":
            # Import relationships
            for imp in chunk.metadata.imports:
                triples.append(Triple(
                    subject=chunk.metadata.symbol_name,
                    predicate="imports",
                    object=imp
                ))
            # Class/function relationships from symbol hierarchy
            if "." in chunk.metadata.symbol_name:
                parent, child = chunk.metadata.symbol_name.rsplit(".", 1)
                triples.append(Triple(subject=parent, predicate="contains", object=child))
    return triples
```

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `storage/graph_store.py` | Create | Graph store manager (Simple + Kuzu factory) |
| `indexing/graph_index.py` | Create | Graph index builder |
| `indexing/graph_extractors.py` | Create | LangExtract + code metadata extraction |
| `config/settings.py` | Modify | Add graph settings (store type, extraction options) |
| `storage_paths.py` | Modify | Add graph_index dir |
| `models/query.py` | Modify | Add GRAPH, MULTI modes |
| `services/query_service.py` | Modify | Add graph retrieval + extended RRF fusion |
| `services/indexing_service.py` | Modify | Build graph during indexing |
| `api/routers/query.py` | Modify | Support new modes |
| `api/routers/index.py` | Modify | Graph rebuild endpoint |
| CLI commands | Modify | Graph query options |

## Dependencies to Add

```toml
# pyproject.toml additions (all optional based on config)
langextract = "^0.1.0"  # Google's entity extraction (for LLM extraction)
llama-index-graph-stores-kuzu = "^0.3.0"  # Optional: for Kuzu store type
```

Note: `SimplePropertyGraphStore` is part of `llama-index-core`, already installed.

**Optional dependencies pattern:**
- `langextract` only needed if `GRAPH_USE_LLM_EXTRACTION=true`
- `llama-index-graph-stores-kuzu` only needed if `GRAPH_STORE_TYPE=kuzu`
- Code metadata extraction uses existing dependencies (no new packages)

## Testing Strategy

1. **Unit tests** for GraphStoreManager persistence
2. **Integration tests** for graph building pipeline
3. **E2E tests** for graph query mode
4. **Hybrid tests** for MULTI mode fusion

## Verification

After implementation:
```bash
# Run quality checks
task before-push

# Test WITHOUT GraphRAG (default behavior unchanged)
poetry run doc-svr-ctl index /path/to/docs
poetry run doc-svr-ctl query "search query" --mode hybrid  # Works as before

# Enable GraphRAG and test
export ENABLE_GRAPH_INDEX=true

# Test graph indexing
poetry run doc-svr-ctl index /path/to/docs --rebuild

# Test graph query
poetry run doc-svr-ctl query "find related concepts" --mode graph

# Test multi-mode fusion
poetry run doc-svr-ctl query "search query" --mode multi

# Verify disabled mode returns appropriate error
unset ENABLE_GRAPH_INDEX
poetry run doc-svr-ctl query "test" --mode graph  # Should error gracefully
```

## Future Enhancements (Out of Scope)

- Kuzu migration for larger graphs
- Custom entity extraction for code (classes, functions, imports)
- Graph visualization endpoint
- Configurable relationship types
