---
name: agent-brain-graph
description: Search using GraphRAG for relationship and dependency queries
parameters:
  - name: query
    description: The search query about relationships or dependencies
    required: true
  - name: top-k
    description: Number of results to return (1-20)
    required: false
    default: 5
  - name: threshold
    description: Minimum relevance score (0.0-1.0)
    required: false
    default: 0.3
skills:
  - using-agent-brain
---

# Agent Brain Graph Search

## Purpose

Performs GraphRAG-powered search for relationship and dependency queries. This mode queries the knowledge graph to find entities (functions, classes, modules) and their relationships (calls, imports, inherits).

Graph search is ideal for:
- Finding what calls a specific function
- Exploring class inheritance hierarchies
- Understanding module dependencies
- Tracing data flow through code

## Usage

```
/agent-brain-graph <query> [--top-k <n>] [--threshold <t>]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| query | Yes | - | The relationship or dependency query |
| --top-k | No | 5 | Number of results (1-20) |
| --threshold | No | 0.3 | Minimum similarity threshold (0.0-1.0) |

## Prerequisites

GraphRAG must be enabled before using graph search:

```bash
# Enable graph indexing
export ENABLE_GRAPH_INDEX=true
export GRAPH_STORE_TYPE=simple       # or kuzu
export GRAPH_USE_CODE_METADATA=true
export GRAPH_USE_LLM_EXTRACTION=true

# Optional dependencies
pip install "agent-brain-rag[graphrag]"          # LLM extractor
pip install "agent-brain-rag[graphrag-kuzu]"     # Kuzu backend

# Start server
agent-brain start

# Rebuild index with graph extraction
agent-brain index /path/to/code --rebuild
```

### Check Graph Status

```bash
agent-brain status
# Look for: Graph Index: enabled (X entities, Y relationships)
```

## Execution

### Pre-flight Check

```bash
# Verify server is running and graph is enabled
agent-brain status
```

If graph index shows as disabled:
```bash
# Enable and restart
export ENABLE_GRAPH_INDEX=true
agent-brain stop
agent-brain start
agent-brain reset --yes
agent-brain index /path/to/code
```

### Search Command

```bash
agent-brain query "<query>" --mode graph --top-k <k> --threshold <t>

# Multi-mode fusion (vector + bm25 + graph via RRF)
agent-brain query "<query>" --mode multi --top-k <k>
```

### Example Queries

```bash
# What calls a specific function
agent-brain query "what functions call process_payment" --mode graph

# Class inheritance
agent-brain query "classes that inherit from BaseService" --mode graph

# Module dependencies
agent-brain query "modules that import authentication" --mode graph

# More results with lower threshold
agent-brain query "dependencies of UserController" --mode graph --top-k 10 --threshold 0.2
```

## Output

### Result Format

The CLI displays results in panels showing:
- Source file path
- Relevance score (percentage)
- Text content excerpt

### Example Output

```
Query: what functions call process_payment
Found 3 results in 850.2ms

╭─ [1] src/api/checkout.py  Score: 89% ─────────────────────────╮
│ def checkout_handler(request):                                 │
│     """Handle checkout and process payment."""                 │
│     order = create_order(request)                              │
│     result = process_payment(order.payment_info)               │
│     return {"status": "success", "order_id": order.id}         │
╰────────────────────────────────────────────────────────────────╯

╭─ [2] src/services/payment_processor.py  Score: 85% ───────────╮
│ class PaymentProcessor:                                        │
│     def handle_order(self, order):                             │
│         return process_payment(order.payment_info)             │
╰────────────────────────────────────────────────────────────────╯

╭─ [3] src/webhooks/stripe.py  Score: 78% ──────────────────────╮
│ def handle_webhook(event):                                     │
│     if event.type == "payment_intent.succeeded":               │
│         process_payment(event.data.object)                     │
╰────────────────────────────────────────────────────────────────╯
```

### Relationship Metadata

Graph and multi results may include relationship metadata in the `--json` output:
- `graph_score`: Score from graph-based retrieval
- `related_entities`: Connected entities found
- `relationship_path`: Relationship chain to query term

## Error Handling

### Graph Index Not Enabled

```
Error: Graph index is not enabled
```

**Resolution:**
```bash
export ENABLE_GRAPH_INDEX=true
agent-brain stop && agent-brain start
agent-brain reset --yes
agent-brain index /path/to/code
```

### No Graph Data

```
Warning: Graph index is empty. Index documents first.
```

**Resolution:**
```bash
agent-brain index /path/to/code
```

### Entity Not Found

```
No entities found matching "nonexistent_function"
```

**Resolution:**
- Verify the function/class name is correct
- Check if the file containing it was indexed
- Try a broader search term

### Server Not Running

```
Error: Could not connect to Agent Brain server
```

**Resolution:**
```bash
agent-brain start
```

## Performance Notes

| Metric | Typical Value |
|--------|---------------|
| Latency | 500-1200ms |
| Memory | Higher than BM25/vector (graph storage) |
| Best for | Relationship queries, dependency analysis |

### When to Use Graph vs Other Modes

| Query Type | Recommended Mode |
|------------|------------------|
| "what calls X" | Graph |
| "dependencies of X" | Graph |
| "classes that inherit from X" | Graph |
| "how does X work" | Vector or Hybrid |
| "find error message X" | BM25 |
| "complete implementation of X" | Multi |

## Related Commands

- `/agent-brain-multi` - Multi-mode search including graph
- `/agent-brain-hybrid` - Hybrid BM25 + semantic search
- `/agent-brain-search` - Default hybrid search
