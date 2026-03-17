# GraphRAG Integration Guide

GraphRAG extends Agent Brain with knowledge graph capabilities, enabling relationship-aware retrieval that surfaces connections between entities, code dependencies, and conceptual relationships.

## Table of Contents

- [What is GraphRAG?](#what-is-graphrag)
- [Why GraphRAG Matters](#why-graphrag-matters)
- [Enabling GraphRAG](#enabling-graphrag)
- [Entity Extraction](#entity-extraction)
- [Query Modes](#query-modes)
- [Reciprocal Rank Fusion](#reciprocal-rank-fusion)
- [Best Practices](#best-practices)
- [Performance Considerations](#performance-considerations)

---

## What is GraphRAG?

GraphRAG combines traditional RAG (Retrieval-Augmented Generation) with knowledge graph technology. Instead of treating documents as isolated chunks of text, GraphRAG:

1. **Extracts Entities**: Identifies named concepts, classes, functions, and other significant items
2. **Captures Relationships**: Records how entities relate to each other (imports, calls, extends, contains)
3. **Enables Graph Queries**: Answers questions about structure and relationships, not just content

### The Knowledge Graph Model

Agent Brain uses a **property graph** model with triplets:

```
Subject --[Predicate]--> Object

Examples:
  FastAPI --[uses]--> Pydantic
  UserController --[contains]--> authenticate_user
  auth_module --[imports]--> jwt
```

Each triplet includes:
- **Subject**: The source entity (e.g., "FastAPI")
- **Subject Type**: Classification (e.g., "Framework")
- **Predicate**: Relationship type (e.g., "uses")
- **Object**: The target entity (e.g., "Pydantic")
- **Object Type**: Classification (e.g., "Library")
- **Source Chunk ID**: Link back to the original document chunk

---

## Why GraphRAG Matters

### Limitations of Vector-Only Search

Vector search excels at semantic similarity but misses structural relationships:

| Query | Vector Search Result | GraphRAG Result |
|-------|---------------------|-----------------|
| "What calls authenticate_user?" | Documents mentioning authentication | Actual callers: LoginController.login, API.verify |
| "What does FastAPI depend on?" | FastAPI documentation | Dependencies: Pydantic, Starlette, Uvicorn |
| "Classes in the auth module" | Auth-related content | Actual classes: AuthService, TokenManager, User |

### When GraphRAG Shines

GraphRAG is most valuable for:

1. **Dependency Analysis**: "What modules import this library?"
2. **Architecture Exploration**: "What classes extend BaseService?"
3. **Impact Assessment**: "What would break if I change this function?"
4. **Onboarding**: "Show me how authentication flows through the system"

---

## Enabling GraphRAG

GraphRAG is disabled by default. Enable it via environment variables:

### Basic Configuration

```bash
# Enable graph indexing (required)
export ENABLE_GRAPH_INDEX=true

# Start server
agent-brain start --daemon
```

### Full Configuration

```bash
# Required
export ENABLE_GRAPH_INDEX=true

# Graph storage backend
export GRAPH_STORE_TYPE=simple  # "simple" (JSON) or "kuzu" (embedded DB)
export GRAPH_INDEX_PATH=./graph_index  # Storage location

# Entity extraction settings
export GRAPH_USE_CODE_METADATA=true  # Extract from AST metadata (fast)
export GRAPH_USE_LLM_EXTRACTION=true  # Use LLM for additional extraction (thorough)
export GRAPH_EXTRACTION_MODEL=claude-haiku-4-5  # Model for LLM extraction
export GRAPH_MAX_TRIPLETS_PER_CHUNK=10  # Limit per chunk

# Query settings
export GRAPH_TRAVERSAL_DEPTH=2  # How many hops to traverse
export GRAPH_RRF_K=60  # Reciprocal Rank Fusion constant
```

### In .env File

```ini
# agent-brain-server/.env
ENABLE_GRAPH_INDEX=true
GRAPH_STORE_TYPE=simple
GRAPH_USE_CODE_METADATA=true
GRAPH_USE_LLM_EXTRACTION=true
GRAPH_EXTRACTION_MODEL=claude-haiku-4-5
```

### In config.yaml

You can also configure GraphRAG via the `config.yaml` file (typically at `.agent-brain/config.yaml`):

```yaml
graphrag:
  enabled: true             # Master switch (default: false)
  store_type: "simple"      # "simple" (JSON) or "kuzu" (embedded DB)
  use_code_metadata: true   # Extract entities from AST metadata
```

The corresponding environment variable mapping is:

| Environment Variable | config.yaml Key | Default |
|---------------------|-----------------|---------|
| `ENABLE_GRAPH_INDEX` | `graphrag.enabled` | `false` |
| `GRAPH_STORE_TYPE` | `graphrag.store_type` | `simple` |
| `GRAPH_USE_CODE_METADATA` | `graphrag.use_code_metadata` | `true` |

Environment variables override config.yaml values.

**Note:** `graph` and `multi` query modes require GraphRAG enabled with the ChromaDB backend. These modes are not available with the PostgreSQL storage backend.

---

## Entity Extraction

Agent Brain uses two complementary extraction methods:

### 1. Code Metadata Extraction (Fast, Deterministic)

Extracts relationships from AST metadata already collected during code chunking:

**Extracted Relationships**:

| Relationship | Example | Source |
|--------------|---------|--------|
| imports | `auth_module --[imports]--> jwt` | Import statements |
| contains | `UserController --[contains]--> login` | Class-method hierarchy |
| defined_in | `authenticate --[defined_in]--> auth_module` | File-symbol mapping |

**Implementation**: `CodeMetadataExtractor` in `graph_extractors.py`

**Advantages**:
- Zero additional API calls
- Deterministic results
- Fast extraction
- Works on all supported languages

### 2. LLM-Based Extraction (Thorough, Semantic)

Uses an LLM to identify entities and relationships from text content:

**Extraction Prompt**:
```
Extract key entity relationships from the following text.
Return triplets in format: SUBJECT | SUBJECT_TYPE | PREDICATE | OBJECT | OBJECT_TYPE

Rules:
- SUBJECT and OBJECT are entity names
- SUBJECT_TYPE and OBJECT_TYPE are classifications
- PREDICATE is the relationship type
```

**Implementation**: `LLMEntityExtractor` in `graph_extractors.py`

**Advantages**:
- Captures conceptual relationships
- Understands natural language descriptions
- Identifies entities in documentation
- Provides entity type classifications

**Configuration**:
```bash
export GRAPH_USE_LLM_EXTRACTION=true
export GRAPH_EXTRACTION_MODEL=claude-haiku-4-5  # Fast, cost-effective
export GRAPH_MAX_TRIPLETS_PER_CHUNK=10  # Prevent graph explosion
```

### Combining Both Methods

When both methods are enabled (recommended for codebases):

1. **Code metadata extraction** runs first (fast, structural)
2. **LLM extraction** adds semantic relationships (thorough)
3. Results are merged, with duplicates removed

---

## Query Modes

GraphRAG introduces two new query modes:

### GRAPH Mode (Graph-Only)

Retrieves documents based purely on entity relationships.

```bash
agent-brain query "what calls AuthService" --mode graph
```

**How It Works**:
1. Extract entity names from query ("AuthService")
2. Find matching entities in graph
3. Traverse relationships (up to `GRAPH_TRAVERSAL_DEPTH` hops)
4. Return documents linked to discovered entities

**Best For**:
- "What calls X?"
- "What does Y import?"
- "Classes that extend Z"
- Dependency exploration

### MULTI Mode (Comprehensive Fusion)

Combines all three retrieval methods with Reciprocal Rank Fusion.

```bash
agent-brain query "authentication implementation with dependencies" --mode multi
```

**How It Works**:
1. Run vector search (semantic similarity)
2. Run BM25 search (keyword matching)
3. Run graph search (relationship traversal)
4. Fuse results using RRF scoring
5. Return top-k combined results

**Best For**:
- Complex queries needing multiple perspectives
- "Complete overview of X"
- Queries mixing content and structure

---

## Reciprocal Rank Fusion

Multi-mode queries use **Reciprocal Rank Fusion (RRF)** to combine results from different retrieval methods.

### The RRF Formula

```
RRF_score = sum(1 / (k + rank_i)) for each retriever i
```

Where:
- `k` is a constant (default: 60)
- `rank_i` is the result's position in retriever i's ranking

### Why RRF Works

RRF elegantly handles the score normalization problem:

| Problem | RRF Solution |
|---------|--------------|
| Different score scales | Only ranks matter, not raw scores |
| Missing results | Absent results contribute 0 |
| Retriever bias | Equal weight by default |

### Example

A document appears at:
- Vector search: rank 2
- BM25 search: rank 5
- Graph search: rank 1

RRF score (k=60):
```
1/(60+2) + 1/(60+5) + 1/(60+1) = 0.016 + 0.015 + 0.016 = 0.047
```

A document appearing in all three retrievers at high positions scores higher than one appearing in only one retriever, even at rank 1.

### Configuring RRF

```bash
export GRAPH_RRF_K=60  # Default value
```

Lower k values give more weight to top-ranked results. Higher k values smooth out ranking differences.

---

## Best Practices

### 1. Choose the Right Query Mode

| Query Type | Recommended Mode |
|------------|------------------|
| Exact function names | `bm25` |
| Conceptual questions | `vector` |
| Technical documentation | `hybrid` |
| Dependency questions | `graph` |
| Complex investigations | `multi` |

### 2. Tune Traversal Depth

```bash
# Default: 2 hops
agent-brain query "imports of auth module" --mode graph

# Deeper exploration: 3-4 hops
export GRAPH_TRAVERSAL_DEPTH=3
agent-brain query "full dependency chain" --mode graph
```

**Guidance**:
- Depth 1: Direct relationships only
- Depth 2: One intermediate entity (default)
- Depth 3-4: Deep exploration (may be slow)

### 3. Balance Extraction Methods

| Scenario | Configuration |
|----------|---------------|
| Code-only repository | `CODE_METADATA=true`, `LLM_EXTRACTION=false` |
| Documentation-only | `CODE_METADATA=false`, `LLM_EXTRACTION=true` |
| Mixed codebase | Both enabled (default) |
| Cost-sensitive | `CODE_METADATA=true`, `LLM_EXTRACTION=false` |

### 4. Monitor Graph Size

Check graph statistics via status endpoint:

```bash
agent-brain status
```

Output includes:
```json
{
  "graph_index": {
    "enabled": true,
    "initialized": true,
    "entity_count": 150,
    "relationship_count": 320,
    "store_type": "simple"
  }
}
```

### 5. Rebuild Graph When Needed

Graph index can be rebuilt independently:

```bash
# Reset everything
agent-brain reset --yes

# Re-index with graph enabled
export ENABLE_GRAPH_INDEX=true
agent-brain index /path/to/project
```

---

## Performance Considerations

### Indexing Impact

GraphRAG adds overhead during indexing:

| Configuration | Indexing Time | Reason |
|---------------|---------------|--------|
| GraphRAG disabled | Baseline | No graph processing |
| Code metadata only | +10-20% | AST traversal |
| LLM extraction | +50-100% | API calls per chunk |
| Both enabled | +60-120% | Combined overhead |

### Query Latency

| Mode | Typical Latency | Notes |
|------|-----------------|-------|
| bm25 | 10-50ms | Fastest |
| vector | 800-1500ms | Embedding generation |
| hybrid | 1000-1800ms | Parallel + fusion |
| graph | 500-1200ms | Graph traversal |
| multi | 1500-2500ms | All three + RRF |

### Memory Usage

Graph storage adds memory requirements:

| Store Type | Memory Footprint | Use Case |
|------------|------------------|----------|
| simple | ~100MB per 10K entities | Development, small projects |
| kuzu | ~50MB per 10K entities | Production, large codebases |

### Storage Backend Comparison

| Feature | SimplePropertyGraphStore | Kuzu |
|---------|--------------------------|------|
| Persistence | JSON files | Embedded database |
| Query Speed | Good | Better |
| Memory Usage | Higher | Lower |
| Setup | Zero config | Requires installation |
| Scalability | < 50K entities | > 100K entities |

**Choosing a Backend**:
- Start with `simple` for development
- Switch to `kuzu` if you have > 50K entities or need better query performance

```bash
# For production with large codebases
export GRAPH_STORE_TYPE=kuzu
```

---

## Troubleshooting

### "GraphRAG not enabled" Error

```
ValueError: GraphRAG not enabled. Set ENABLE_GRAPH_INDEX=true in environment.
```

**Solution**: Ensure `ENABLE_GRAPH_INDEX=true` is set before starting the server.

### Empty Graph Results

If graph queries return no results:

1. Check if graph indexing completed: `agent-brain status`
2. Verify entity extraction: Look for `entity_count > 0`
3. Try simpler queries: "what imports X" instead of complex queries

### Slow LLM Extraction

If indexing is too slow with LLM extraction:

1. Disable LLM extraction: `GRAPH_USE_LLM_EXTRACTION=false`
2. Use a faster model: `GRAPH_EXTRACTION_MODEL=claude-haiku-4-5`
3. Reduce triplets per chunk: `GRAPH_MAX_TRIPLETS_PER_CHUNK=5`

### Graph Store Corruption

If graph queries fail with storage errors:

```bash
# Clear graph and rebuild
agent-brain reset --yes
agent-brain index /path/to/project
```

---

## Next Steps

- [Code Indexing Deep Dive](CODE_INDEXING.md) - How AST metadata feeds GraphRAG
- [API Reference](API_REFERENCE.md) - Graph endpoints and parameters
- [Configuration Reference](CONFIGURATION.md) - All GraphRAG settings
