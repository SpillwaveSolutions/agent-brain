# Agent Brain API Reference

## Base URL

Discover from runtime file (multi-instance mode):
```bash
cat .claude/agent-brain/runtime.json | jq -r '.base_url'
# Example: http://127.0.0.1:54321
```

Default (single instance): `http://127.0.0.1:8000`

Override via environment: `DOC_SERVE_URL`

---

## Health Endpoints

### GET /health

Check server health status.

**Response:**

```json
{
  "status": "healthy | indexing | degraded | unhealthy",
  "message": "Server is running and ready for queries",
  "version": "1.0.0",
  "timestamp": "2024-12-15T10:00:00Z"
}
```

**Status Values:**
- `healthy` - Server ready for queries
- `indexing` - Indexing in progress, queries may fail
- `degraded` - Server up but some services unavailable
- `unhealthy` - Server not operational

---

### GET /health/status

Get detailed indexing status.

**Response:**

```json
{
  "total_documents": 100,
  "total_chunks": 500,
  "indexing_in_progress": false,
  "current_job_id": null,
  "progress_percent": 0.0,
  "last_indexed_at": "2024-12-15T10:00:00Z",
  "indexed_folders": ["/docs/kubernetes", "/docs/python"],
  "graph_index": {
    "enabled": true,
    "entity_count": 450,
    "relationship_count": 1200,
    "store_type": "simple"
  }
}
```

**Graph Index Fields** (when `ENABLE_GRAPH_INDEX=true`):
- `enabled` - Whether graph indexing is active
- `entity_count` - Number of extracted entities (functions, classes, modules)
- `relationship_count` - Number of relationships (calls, imports, inherits)
- `store_type` - Graph store backend (`simple` or `kuzu`)

---

## Query Endpoints

### POST /query

Execute a semantic search on indexed documents.

**Request Body:**

```json
{
  "query": "how to configure pod networking",
  "top_k": 5,
  "similarity_threshold": 0.7,
  "mode": "hybrid",
  "alpha": 0.5,
  "traversal_depth": 2,
  "include_relationships": false
}
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | Search query text |
| `top_k` | integer | No | 5 | Number of results (1-100) |
| `similarity_threshold` | float | No | 0.7 | Minimum similarity (0.0-1.0) |
| `mode` | string | No | hybrid | Retrieval mode (`vector`, `bm25`, `hybrid`, `graph`, `multi`) |
| `alpha` | float | No | 0.5 | Hybrid weight (1.0=vector, 0.0=bm25) |
| `traversal_depth` | integer | No | 2 | Graph traversal depth for graph/multi modes (1-5) |
| `include_relationships` | boolean | No | false | Include entity relationships in results |

**Response:**

```json
{
  "results": [
    {
      "text": "Pod networking in Kubernetes allows...",
      "source": "docs/kubernetes/networking.md",
      "score": 0.92,
      "vector_score": 0.92,
      "bm25_score": 0.85,
      "graph_score": 0.78,
      "chunk_id": "chunk_abc123",
      "metadata": {
        "page": 1,
        "section": "Pod Networking"
      },
      "relationships": [
        {
          "type": "CALLS",
          "target": "configure_network",
          "source_entity": "setup_pod"
        },
        {
          "type": "IMPORTS",
          "target": "kubernetes.networking",
          "source_entity": "pod_manager"
        }
      ]
    }
  ],
  "query_time_ms": 45.2,
  "total_results": 1
}
```

**Response Fields:**
- `graph_score` - Graph relevance score (only present in graph/multi modes)
- `relationships` - Entity relationships (only when `include_relationships=true`)

**Error Responses:**

| Status | Description |
|--------|-------------|
| 400 | Query is empty or invalid |
| 503 | Index not ready (indexing in progress) |
| 500 | Internal server error |

---

### GET /query/count

Get the total number of indexed document chunks.

**Response:**

```json
{
  "total_chunks": 500,
  "ready": true
}
```

---

## Index Endpoints

### POST /index

Start indexing documents from a folder. The system uses stable IDs based on file paths and chunk indices, meaning re-indexing the same folder will update existing records (upsert) rather than creating duplicates.

**Request Body:**

```json
{
  "folder_path": "/path/to/documents",
  "recursive": true,
  "chunk_size": 512,
  "chunk_overlap": 50
}
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `folder_path` | string | Yes | - | Absolute or relative path to documents |
| `recursive` | boolean | No | true | Include subdirectories |
| `chunk_size` | integer | No | 512 | Target tokens per chunk |
| `chunk_overlap` | integer | No | 50 | Overlap between chunks |

---

### POST /index/add

Add documents incrementally without clearing existing index.

**Request Body:**

```json
{
  "folder_path": "/path/to/more/documents",
  "recursive": true
}
```

---

### DELETE /index

Clear all indexed documents.

**Response:**

```json
{
  "job_id": "reset",
  "status": "completed",
  "message": "Index cleared successfully"
}
```

---

## OpenAPI Documentation

Interactive API documentation available at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

---

## CLI Commands Reference

The `agent-brain` CLI provides these commands:

```bash
# Server lifecycle
agent-brain init                      # Initialize project config
agent-brain start --daemon            # Start server with auto-port
agent-brain stop                      # Stop running server
agent-brain list                      # List all running instances

# Check server health and status
agent-brain status
agent-brain status --json

# Query documents
agent-brain query "search text"
agent-brain query "search text" --mode hybrid --top-k 10
agent-brain query "search text" --mode graph --traversal-depth 3
agent-brain query "search text" --mode multi --include-relationships
agent-brain query "search text" --json

# Index documents
agent-brain index /path/to/docs
agent-brain index /path/to/docs --recursive

# Clear index
agent-brain reset --yes
```

**Query Options:**
- `--mode MODE` - Search mode: bm25, vector, hybrid, graph, multi
- `--top-k N` - Number of results (default: 5)
- `--threshold F` - Minimum similarity (default: 0.7)
- `--alpha F` - Hybrid balance, 0=BM25, 1=Vector (default: 0.5)
- `--traversal-depth N` - Graph traversal depth (default: 2)
- `--include-relationships` - Include entity relationships in output

**Global Options:**
- `--url URL` - Server URL (default: http://127.0.0.1:8000)
- `--json` - Output as JSON
- `--help` - Show help message
