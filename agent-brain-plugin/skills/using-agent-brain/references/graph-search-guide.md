# Graph Search Guide

## Overview

Graph search (GraphRAG) enables relationship-aware retrieval by building a knowledge graph from your documents. Unlike traditional search that finds content based on text similarity, graph search discovers entities (functions, classes, modules) and their relationships (calls, imports, inherits), allowing you to explore code dependencies and architectural connections. You can run **graph-only** queries or **multi-mode** fusion that blends vector + BM25 + graph with Reciprocal Rank Fusion (RRF).

## When to Use Graph Search

**Choose `graph` mode when:**
- Exploring code dependencies ("what calls this function?")
- Understanding inheritance hierarchies ("what extends BaseService?")
- Finding import relationships ("what modules import authentication?")
- Tracing data flow through code paths
- Answering "how does X connect to Y?" questions

**Choose `multi` mode when:**
- Need the most comprehensive results combining all retrieval methods
- Want both content matches AND relationship context
- Investigating complex code paths with semantic understanding
- Uncertain which mode would work best

**Avoid graph mode when:**
- Looking for specific text content (use bm25)
- Searching for conceptual explanations (use vector)
- Graph indexing is not enabled

## How Graph Search Works

### Entity & Relationship Extraction

During indexing, Agent Brain extracts:

| Entity Type | Description | Example |
|-------------|-------------|---------|
| Function | Callable functions/methods | `process_payment()` |
| Class | Class definitions | `PaymentService` |
| Module | File/package modules | `auth.validators` |
| Variable | Important variables/constants | `MAX_RETRIES` |

### Relationship Types

Relationships between entities are automatically detected:

| Relationship | Description | Example |
|--------------|-------------|---------|
| CALLS | Function invocation | `main() -> process_payment()` |
| IMPORTS | Module import | `service.py -> auth.validators` |
| INHERITS | Class inheritance | `AdminUser -> BaseUser` |
| CONTAINS / DEFINED_IN | Containment / definition edges | `auth.py -> authenticate_user` |
| USES | Variable/constant usage | `retry_loop -> MAX_RETRIES` |

### Graph Traversal

When you query, the system:
1. Finds entities matching your query
2. Traverses the graph to find connected entities
3. Returns results ranked by graph relevance
4. Optionally includes relationship metadata

## How to Use Graph Search

### CLI Usage

```bash
# Basic graph search
agent-brain query "what calls process_payment" --mode graph

# With more results
agent-brain query "classes inheriting from BaseService" --mode graph --top-k 10

# Lower threshold for broader results
agent-brain query "auth module dependencies" --mode graph --threshold 0.2

# Multi-mode (vector + bm25 + graph via RRF)
agent-brain query "complete payment flow" --mode multi --top-k 10
```

### API Usage

```bash
# Graph search
curl -X POST http://localhost:8000/query/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "what functions call authenticate_user",
    "mode": "graph",
    "top_k": 10,
    "similarity_threshold": 0.3
  }'

# Multi-mode search
curl -X POST http://localhost:8000/query/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "complete authentication implementation",
    "mode": "multi",
    "top_k": 10,
    "similarity_threshold": 0.3
  }'
```

## Graph Search Options

| Option | Default | Description | Use Case |
|--------|---------|-------------|----------|
| `--mode graph` | - | Pure graph-based retrieval | Relationship queries |
| `--mode multi` | - | Combines vector + BM25 + graph (RRF) | Comprehensive results |
| `--threshold F` | 0.3 | Minimum similarity threshold | Filter weak matches |
| `--top-k N` | 5 | Maximum results | More comprehensive results |
| `--alpha F` | 0.5 | Hybrid weight (vector vs BM25) used when graph falls back | Tune hybrid fallback |

**Note:** Graph search returns relationship metadata in the result's `metadata` field when available.

## Enabling GraphRAG

GraphRAG must be explicitly enabled during server startup:

### Environment Variables (server)

```bash
# Required: master switch (default: false)
export ENABLE_GRAPH_INDEX=true

# Optional backends
export GRAPH_STORE_TYPE=simple      # or kuzu
export GRAPH_INDEX_PATH=./graph_index

# Extraction controls
export GRAPH_USE_CODE_METADATA=true
export GRAPH_USE_LLM_EXTRACTION=true
export GRAPH_MAX_TRIPLETS_PER_CHUNK=10
export GRAPH_EXTRACTION_MODEL=claude-haiku-4-5

# Query behavior
export GRAPH_TRAVERSAL_DEPTH=2
export GRAPH_RRF_K=60               # RRF constant for multi mode
```

### Configuration File (.env)

```bash
# .env file in project root
ENABLE_GRAPH_INDEX=true
GRAPH_STORE_TYPE=simple
GRAPH_INDEX_PATH=./graph_index
GRAPH_USE_CODE_METADATA=true
GRAPH_USE_LLM_EXTRACTION=true
GRAPH_MAX_TRIPLETS_PER_CHUNK=10
GRAPH_TRAVERSAL_DEPTH=2
GRAPH_EXTRACTION_MODEL=claude-haiku-4-5
```

### Optional Dependencies

- Default simple store: included.
- Enhanced extraction: `pip install "agent-brain-rag[graphrag]"`
- Kuzu backend: `pip install "agent-brain-rag[graphrag-kuzu]"`

### Starting with Graph Enabled

```bash
# Set environment and start
export ENABLE_GRAPH_INDEX=true
agent-brain start

# Verify graph is enabled
agent-brain status --json | jq '.graph_index'
```

## Example Queries and Results

### Example 1: Finding Function Callers

**Query:** `agent-brain query "what calls process_payment" --mode graph --top-k 10`

**Response:**
```json
{
  "results": [
    {
      "text": "def checkout_handler(request):\n    ...\n    result = process_payment(order)\n    ...",
      "source": "/src/handlers/checkout.py",
      "score": 0.95,
      "graph_score": 0.95,
      "chunk_id": "chunk_checkout_001",
      "relationships": [
        {
          "type": "CALLS",
          "source_entity": "checkout_handler",
          "target": "process_payment"
        }
      ]
    },
    {
      "text": "class PaymentProcessor:\n    def handle_order(self, order):\n        return process_payment(order.payment_info)",
      "source": "/src/services/payment_processor.py",
      "score": 0.89,
      "graph_score": 0.89,
      "chunk_id": "chunk_payment_002",
      "relationships": [
        {
          "type": "CALLS",
          "source_entity": "PaymentProcessor.handle_order",
          "target": "process_payment"
        }
      ]
    }
  ],
  "query_time_ms": 820.5,
  "total_results": 2
}
```

### Example 2: Exploring Class Hierarchy

**Query:** `agent-brain query "classes that inherit from BaseService" --mode graph --top-k 10`

**Response:**
```json
{
  "results": [
    {
      "text": "class AuthService(BaseService):\n    def authenticate(self, credentials):\n        ...",
      "source": "/src/services/auth_service.py",
      "score": 0.92,
      "graph_score": 0.92,
      "relationships": [
        {
          "type": "INHERITS",
          "source_entity": "AuthService",
          "target": "BaseService"
        }
      ]
    },
    {
      "text": "class PaymentService(BaseService):\n    def process(self, payment):\n        ...",
      "source": "/src/services/payment_service.py",
      "score": 0.91,
      "graph_score": 0.91,
      "relationships": [
        {
          "type": "INHERITS",
          "source_entity": "PaymentService",
          "target": "BaseService"
        }
      ]
    }
  ],
  "query_time_ms": 650.3,
  "total_results": 2
}
```

### Example 3: Multi-Mode Comprehensive Search

**Query:** `agent-brain query "authentication flow implementation" --mode multi --top-k 10`

**Response:**
```json
{
  "results": [
    {
      "text": "The authentication flow starts with validate_credentials(), which calls authenticate_user()...",
      "source": "/docs/auth-guide.md",
      "score": 0.94,
      "vector_score": 0.96,
      "bm25_score": 0.88,
      "graph_score": 0.91,
      "relationships": []
    },
    {
      "text": "def authenticate_user(username, password):\n    user = get_user(username)\n    if verify_password(password, user.hash):\n        return create_session(user)",
      "source": "/src/auth/authenticator.py",
      "score": 0.92,
      "vector_score": 0.85,
      "bm25_score": 0.94,
      "graph_score": 0.97,
      "relationships": [
        {
          "type": "CALLS",
          "source_entity": "authenticate_user",
          "target": "get_user"
        },
        {
          "type": "CALLS",
          "source_entity": "authenticate_user",
          "target": "verify_password"
        },
        {
          "type": "CALLS",
          "source_entity": "authenticate_user",
          "target": "create_session"
        }
      ]
    }
  ],
  "query_time_ms": 1850.7,
  "total_results": 2
}
```

## Graph Store Types

### Simple Store (Default)

- In-memory graph storage
- Fast queries, no external dependencies
- Data persists in JSON file
- Best for: Development, small-medium codebases

```bash
GRAPH_STORE_TYPE=simple
```

### Kuzu Store (Production)

- Persistent graph database
- Better performance for large graphs
- ACID compliant
- Best for: Production, large codebases

```bash
GRAPH_STORE_TYPE=kuzu
```

## Performance Considerations

### Response Times

| Mode | Typical Time | Notes |
|------|--------------|-------|
| `graph` | 500-1200ms | Graph traversal only |
| `multi` | 1500-2500ms | All three modes + fusion |

### Memory Usage

- Graph index adds ~200-500MB for typical codebases
- Kuzu store uses disk-based storage for large graphs
- Entity count scales with code complexity

### Optimization Tips

1. **Limit traversal depth**: Start with 2, increase only if needed
2. **Use graph mode for relationships**: Skip vector/BM25 overhead
3. **Index selectively**: Focus on code files, skip generated content
4. **Consider Kuzu**: For codebases with 10k+ entities

## Comparison: Graph vs Other Modes

| Aspect | BM25 | Vector | Hybrid | Graph | Multi |
|--------|------|--------|--------|-------|-------|
| **Best For** | Exact terms | Concepts | General | Relationships | Everything |
| **Speed** | Fastest | Slow | Slow | Medium | Slowest |
| **Relationships** | No | No | No | Yes | Yes |
| **API Required** | No | Yes | Yes | Yes | Yes |
| **Memory** | Low | Medium | Medium | High | Highest |

## Common Issues

### Graph Index Not Available

```
Error: Graph index not enabled
```

**Solution:** Set `ENABLE_GRAPH_INDEX=true` and restart the server.

### No Relationships Found

**Possible causes:**
- Documents haven't been re-indexed after enabling graph
- Query doesn't match any entities
- Traversal depth too shallow

**Solution:** Re-index documents and try lowering `--threshold` (e.g., `--threshold 0.1`).

### Slow Graph Queries

**Possible causes:**
- Large graph with many relationships
- High traversal depth
- Simple store with large dataset

**Solution:** Reduce traversal depth or switch to Kuzu store.

## Best Practices

1. **Enable graph for code-heavy projects**: Most valuable for source code exploration
2. **Use multi mode for comprehensive searches**: Combines all retrieval strengths
3. **Start with traversal depth 2**: Increase for deeper dependency chains
4. **Include relationships for debugging**: Helps understand result relevance
5. **Monitor entity/relationship counts**: Use `/health/status` to track graph size
