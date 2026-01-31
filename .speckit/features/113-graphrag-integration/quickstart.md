# Quickstart: GraphRAG Integration

**Feature**: 113-graphrag-integration
**Date**: 2026-01-30

## Overview

This guide shows how to enable and use the GraphRAG feature in doc-serve.

## Prerequisites

- doc-serve installed and working
- Documents indexed (vector + BM25)
- OpenAI API key configured (for LLM extraction)

## Enable GraphRAG

### 1. Set Environment Variable

```bash
# In your .env file or environment
export ENABLE_GRAPH_INDEX=true
```

### 2. Optional: Install Enhanced Dependencies

```bash
# For Kuzu graph store (production)
poetry install --with graphrag-kuzu

# For langextract (enhanced entity extraction)
poetry install --with graphrag
```

### 3. Rebuild Index with Graph

```bash
# Using CLI
doc-svr-ctl index /path/to/docs --rebuild

# Or via API
curl -X POST http://localhost:8000/index \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/docs", "rebuild": true}'
```

## Query Modes

### Graph-Only Search

Find results based on entity relationships:

```bash
# CLI
doc-svr-ctl query "authentication" --mode graph

# API
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication",
    "mode": "graph",
    "top_k": 10,
    "traversal_depth": 2
  }'
```

### Multi-Mode Fusion

Combine vector, BM25, and graph for best results:

```bash
# CLI
doc-svr-ctl query "user login flow" --mode multi

# API
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "user login flow",
    "mode": "multi",
    "top_k": 5
  }'
```

## Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_GRAPH_INDEX` | `false` | Enable/disable GraphRAG |
| `GRAPH_STORE_TYPE` | `simple` | `simple` (JSON) or `kuzu` (embedded DB) |
| `GRAPH_MAX_TRIPLETS_PER_CHUNK` | `10` | Limit entities per chunk |
| `GRAPH_USE_CODE_METADATA` | `true` | Extract from code AST |
| `GRAPH_USE_LLM_EXTRACTION` | `true` | Use LLM for docs |
| `GRAPH_TRAVERSAL_DEPTH` | `2` | Default query depth |

## Check Graph Status

```bash
# CLI
doc-svr-ctl status

# API
curl http://localhost:8000/health/status
```

Example output:
```json
{
  "status": "healthy",
  "indexing_status": "ready",
  "document_count": 1500,
  "graph_index": {
    "enabled": true,
    "initialized": true,
    "entity_count": 3200,
    "relationship_count": 8500,
    "store_type": "simple"
  }
}
```

## Rebuild Graph Only

Rebuild just the graph index without re-indexing documents:

```bash
curl -X POST "http://localhost:8000/index?rebuild_graph=true"
```

## Troubleshooting

### "GraphRAG not enabled" Error

```bash
# Check if enabled
echo $ENABLE_GRAPH_INDEX

# Enable it
export ENABLE_GRAPH_INDEX=true

# Restart server
doc-svr-ctl stop && doc-svr-ctl start
```

### Graph Index Not Building

Check logs for extraction errors:
```bash
doc-svr-ctl logs | grep -i graph
```

### Slow Graph Queries

1. Reduce `GRAPH_TRAVERSAL_DEPTH` (default: 2)
2. Use Kuzu for larger indexes:
   ```bash
   export GRAPH_STORE_TYPE=kuzu
   ```

## Example: Code Relationship Query

Query for all modules that import a specific class:

```bash
doc-svr-ctl query "modules that import AuthService" --mode graph
```

This will traverse import relationships to find related code.
