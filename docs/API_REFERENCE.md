# API Reference

This document provides complete REST API documentation for the Agent Brain server.

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Base URL](#base-url)
- [Endpoints](#endpoints)
  - [Health Endpoints](#health-endpoints)
  - [Query Endpoints](#query-endpoints)
  - [Index Endpoints](#index-endpoints)
  - [Job Queue Endpoints](#job-queue-endpoints)
- [Request/Response Models](#requestresponse-models)
- [Error Handling](#error-handling)
- [Examples](#examples)

---

## Overview

The Agent Brain API is a RESTful JSON API built with FastAPI. It provides endpoints for:

- **Health Monitoring**: Server status and indexing progress
- **Document Querying**: Semantic, keyword, hybrid, graph, and multi-mode search
- **Document Indexing**: Index documents and code from folders

### API Documentation

Interactive documentation is available at:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

---

## Authentication

The Agent Brain API does not require authentication by default. It binds to `127.0.0.1` and is accessible only from localhost.

For network deployment, implement authentication via a reverse proxy (nginx, Traefik) or enable CORS restrictions.

---

## Base URL

```
http://127.0.0.1:8000
```

For per-project instances, read the port from `.claude/agent-brain/runtime.json`:

```json
{
  "base_url": "http://127.0.0.1:49321",
  "port": 49321
}
```

---

## Endpoints

### Health Endpoints

#### GET /health

Check server health status.

**Response** `200 OK`:

```json
{
  "status": "healthy",
  "message": "Server is running and ready for queries",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.2.0",
  "mode": "project",
  "instance_id": "abc123",
  "project_id": "my-project"
}
```

**Status Values**:

| Status | Description |
|--------|-------------|
| `healthy` | Ready for queries |
| `indexing` | Indexing in progress |
| `degraded` | Running with issues |
| `unhealthy` | Not operational |

---

#### GET /health/status

Get detailed indexing status.

**Response** `200 OK`:

```json
{
  "total_documents": 150,
  "total_chunks": 1200,
  "total_doc_chunks": 800,
  "total_code_chunks": 400,
  "indexing_in_progress": false,
  "current_job_id": null,
  "progress_percent": 0.0,
  "last_indexed_at": "2024-01-15T10:30:00Z",
  "indexed_folders": ["/path/to/docs"],
  "supported_languages": ["python", "typescript"],
  "graph_index": {
    "enabled": true,
    "initialized": true,
    "entity_count": 120,
    "relationship_count": 250,
    "store_type": "simple"
  }
}
```

---

### Query Endpoints

#### POST /query

Execute a search query.

**Request Body**:

```json
{
  "query": "how does authentication work",
  "top_k": 5,
  "similarity_threshold": 0.7,
  "mode": "hybrid",
  "alpha": 0.5,
  "source_types": ["doc", "code"],
  "languages": ["python", "typescript"],
  "file_paths": ["src/**/*.py"]
}
```

**Parameters**:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | (required) | Search query (1-1000 chars) |
| `top_k` | integer | `5` | Results to return (1-50) |
| `similarity_threshold` | float | `0.7` | Minimum similarity (0.0-1.0) |
| `mode` | string | `"hybrid"` | Search mode |
| `alpha` | float | `0.5` | Hybrid balance (0=BM25, 1=Vector) |
| `source_types` | array | `null` | Filter by `["doc", "code"]` |
| `languages` | array | `null` | Filter by languages |
| `file_paths` | array | `null` | Filter by file patterns |

**Mode Values**:

| Mode | Description |
|------|-------------|
| `bm25` | Keyword-only search |
| `vector` | Semantic-only search |
| `hybrid` | BM25 + Vector fusion |
| `graph` | Knowledge graph traversal |
| `multi` | All three with RRF |

**Response** `200 OK`:

```json
{
  "results": [
    {
      "text": "Authentication is configured via...",
      "source": "/path/to/docs/auth.md",
      "score": 0.92,
      "vector_score": 0.92,
      "bm25_score": 0.85,
      "chunk_id": "chunk_abc123",
      "source_type": "doc",
      "language": "markdown",
      "graph_score": null,
      "related_entities": null,
      "relationship_path": null,
      "metadata": {
        "chunk_index": 0,
        "total_chunks": 5
      }
    }
  ],
  "query_time_ms": 125.5,
  "total_results": 1
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Chunk content |
| `source` | string | Source file path |
| `score` | float | Combined/primary score |
| `vector_score` | float | Semantic similarity score |
| `bm25_score` | float | Keyword match score |
| `graph_score` | float | Graph traversal score |
| `chunk_id` | string | Unique chunk identifier |
| `source_type` | string | `"doc"` or `"code"` |
| `language` | string | Programming language |
| `related_entities` | array | GraphRAG related entities |
| `relationship_path` | array | GraphRAG relationship paths |
| `metadata` | object | Additional metadata |

**Errors**:

| Code | Description |
|------|-------------|
| `400` | Invalid query (empty or too long) |
| `503` | Index not ready |

---

#### GET /query/count

Get the number of indexed chunks.

**Response** `200 OK`:

```json
{
  "total_chunks": 1200,
  "ready": true
}
```

---

### Index Endpoints

#### POST /index

Start indexing documents from a folder.

**Request Body**:

```json
{
  "folder_path": "/path/to/documents",
  "chunk_size": 512,
  "chunk_overlap": 50,
  "recursive": true,
  "include_code": true,
  "supported_languages": ["python", "typescript"],
  "code_chunk_strategy": "ast_aware",
  "generate_summaries": false,
  "include_patterns": ["docs/**/*.md", "src/**/*.py"],
  "exclude_patterns": ["node_modules/**", "__pycache__/**"]
}
```

**Parameters**:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `folder_path` | string | (required) | Path to folder |
| `chunk_size` | integer | `512` | Chunk size in tokens (128-2048) |
| `chunk_overlap` | integer | `50` | Overlap in tokens (0-200) |
| `recursive` | boolean | `true` | Scan subdirectories |
| `include_code` | boolean | `false` | Include source code files |
| `supported_languages` | array | `null` | Languages to index |
| `code_chunk_strategy` | string | `"ast_aware"` | `"ast_aware"` or `"text_based"` |
| `generate_summaries` | boolean | `false` | Generate LLM summaries |
| `include_patterns` | array | `null` | Glob patterns to include |
| `exclude_patterns` | array | `null` | Glob patterns to exclude |

**Response** `202 Accepted`:

```json
{
  "job_id": "job_abc123def456",
  "status": "started",
  "message": "Indexing started for /path/to/documents"
}
```

**Errors**:

| Code | Description |
|------|-------------|
| `400` | Invalid folder path |
| `409` | Indexing already in progress |

---

#### POST /index/add

Add documents from another folder to the existing index.

Same request/response format as `POST /index`.

---

#### DELETE /index

Reset the index (delete all documents).

**Response** `200 OK`:

```json
{
  "job_id": "reset",
  "status": "completed",
  "message": "Index has been reset successfully"
}
```

**Errors**:

| Code | Description |
|------|-------------|
| `409` | Cannot reset during indexing |

---

### Job Queue Endpoints

As of v3.0.0, indexing operations are queued and processed asynchronously.

#### GET /index/jobs/

List all jobs in the queue.

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | null | Filter by status |
| `limit` | integer | 100 | Maximum results (1-500) |
| `offset` | integer | 0 | Skip first N results |

**Response** `200 OK`:

```json
{
  "jobs": [
    {
      "id": "job_abc123def456",
      "status": "running",
      "folder_path": "/path/to/docs",
      "operation": "index",
      "include_code": true,
      "enqueued_at": "2026-02-03T10:00:00Z",
      "started_at": "2026-02-03T10:00:05Z",
      "finished_at": null,
      "progress_percent": 45.5,
      "error": null
    }
  ],
  "total": 1,
  "pending": 0,
  "running": 1,
  "completed": 0,
  "failed": 0
}
```

---

#### GET /index/jobs/{job_id}

Get detailed information about a specific job.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `job_id` | string | Job identifier |

**Response** `200 OK`:

```json
{
  "id": "job_abc123def456",
  "status": "running",
  "folder_path": "/path/to/docs",
  "operation": "index",
  "include_code": true,
  "enqueued_at": "2026-02-03T10:00:00Z",
  "started_at": "2026-02-03T10:00:05Z",
  "finished_at": null,
  "execution_time_ms": 15000,
  "progress": {
    "files_processed": 45,
    "files_total": 100,
    "chunks_created": 230,
    "current_file": "src/services/auth.py",
    "percent_complete": 45.0
  },
  "total_documents": 45,
  "total_chunks": 230,
  "error": null,
  "retry_count": 0,
  "cancel_requested": false
}
```

**Errors**:

| Code | Description |
|------|-------------|
| `404` | Job not found |

---

#### DELETE /index/jobs/{job_id}

Cancel a pending or running job.

**Response** `200 OK`:

```json
{
  "job_id": "job_abc123def456",
  "status": "cancelled",
  "message": "Job cancellation requested"
}
```

**Errors**:

| Code | Description |
|------|-------------|
| `404` | Job not found |
| `409` | Cannot cancel completed job |

---

## Request/Response Models

### QueryRequest

```typescript
interface QueryRequest {
  query: string;              // 1-1000 characters
  top_k?: number;             // 1-50, default 5
  similarity_threshold?: number; // 0.0-1.0, default 0.7
  mode?: "bm25" | "vector" | "hybrid" | "graph" | "multi"; // default "hybrid"
  alpha?: number;             // 0.0-1.0, default 0.5
  source_types?: string[];    // ["doc", "code"]
  languages?: string[];       // ["python", "typescript", ...]
  file_paths?: string[];      // Glob patterns
}
```

### QueryResponse

```typescript
interface QueryResponse {
  results: QueryResult[];
  query_time_ms: number;
  total_results: number;
}

interface QueryResult {
  text: string;
  source: string;
  score: number;
  vector_score?: number;
  bm25_score?: number;
  graph_score?: number;
  chunk_id: string;
  source_type: string;
  language?: string;
  related_entities?: string[];
  relationship_path?: string[];
  metadata: Record<string, any>;
}
```

### IndexRequest

```typescript
interface IndexRequest {
  folder_path: string;
  chunk_size?: number;        // 128-2048, default 512
  chunk_overlap?: number;     // 0-200, default 50
  recursive?: boolean;        // default true
  include_code?: boolean;     // default false
  supported_languages?: string[];
  code_chunk_strategy?: "ast_aware" | "text_based"; // default "ast_aware"
  generate_summaries?: boolean; // default false
  include_patterns?: string[];
  exclude_patterns?: string[];
}
```

### IndexResponse

```typescript
interface IndexResponse {
  job_id: string;
  status: string;
  message?: string;
}
```

### HealthStatus

```typescript
interface HealthStatus {
  status: "healthy" | "indexing" | "degraded" | "unhealthy";
  message?: string;
  timestamp: string;          // ISO 8601
  version: string;
  mode?: string;
  instance_id?: string;
  project_id?: string;
  active_projects?: number;
}
```

### IndexingStatus

```typescript
interface IndexingStatus {
  total_documents: number;
  total_chunks: number;
  total_doc_chunks: number;
  total_code_chunks: number;
  indexing_in_progress: boolean;
  current_job_id?: string;
  progress_percent: number;
  last_indexed_at?: string;   // ISO 8601
  indexed_folders: string[];
  supported_languages: string[];
  graph_index?: GraphIndexStatus;
}

interface GraphIndexStatus {
  enabled: boolean;
  initialized: boolean;
  entity_count: number;
  relationship_count: number;
  store_type: string;
}
```

---

## Error Handling

### Error Response Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| `200` | Success |
| `202` | Accepted (async operation started) |
| `400` | Bad Request (invalid parameters) |
| `404` | Not Found |
| `409` | Conflict (e.g., indexing in progress) |
| `500` | Internal Server Error |
| `503` | Service Unavailable (index not ready) |

### Common Errors

**Query Errors**:

```json
// Empty query
{
  "detail": "Query cannot be empty"
}

// Index not ready
{
  "detail": "Index not ready. Indexing is in progress."
}

// GraphRAG not enabled
{
  "detail": "GraphRAG not enabled. Set ENABLE_GRAPH_INDEX=true in environment."
}
```

**Index Errors**:

```json
// Folder not found
{
  "detail": "Folder not found: /path/to/nonexistent"
}

// Already indexing
{
  "detail": "Indexing already in progress. Please wait for completion."
}
```

---

## Examples

### cURL Examples

**Health Check**:

```bash
curl http://localhost:8000/health
```

**Search Query**:

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication implementation",
    "mode": "hybrid",
    "top_k": 10
  }'
```

**Start Indexing**:

```bash
curl -X POST http://localhost:8000/index \
  -H "Content-Type: application/json" \
  -d '{
    "folder_path": "/path/to/project",
    "include_code": true,
    "recursive": true
  }'
```

**Reset Index**:

```bash
curl -X DELETE http://localhost:8000/index
```

### Python Examples

**Using httpx**:

```python
import httpx

BASE_URL = "http://localhost:8000"

async def search_documents(query: str, mode: str = "hybrid"):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/query",
            json={
                "query": query,
                "mode": mode,
                "top_k": 10,
            }
        )
        response.raise_for_status()
        return response.json()

async def index_folder(folder_path: str, include_code: bool = False):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/index",
            json={
                "folder_path": folder_path,
                "include_code": include_code,
            }
        )
        response.raise_for_status()
        return response.json()

# Usage
results = await search_documents("authentication")
for result in results["results"]:
    print(f"{result['source']}: {result['score']:.2f}")
```

**Polling for Indexing Completion**:

```python
import asyncio
import httpx

async def wait_for_indexing():
    async with httpx.AsyncClient() as client:
        while True:
            response = await client.get(f"{BASE_URL}/health/status")
            status = response.json()

            if not status["indexing_in_progress"]:
                print(f"Indexing complete: {status['total_chunks']} chunks")
                break

            print(f"Progress: {status['progress_percent']:.1f}%")
            await asyncio.sleep(2)
```

### JavaScript Examples

**Using fetch**:

```javascript
const BASE_URL = 'http://localhost:8000';

async function searchDocuments(query, mode = 'hybrid') {
  const response = await fetch(`${BASE_URL}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      mode,
      top_k: 10,
    }),
  });

  if (!response.ok) {
    throw new Error(`Query failed: ${response.statusText}`);
  }

  return response.json();
}

// Usage
const results = await searchDocuments('authentication');
results.results.forEach(result => {
  console.log(`${result.source}: ${result.score.toFixed(2)}`);
});
```

---

## Rate Limits

The Agent Brain API does not implement rate limiting by default. For production deployments, implement rate limiting at the reverse proxy level.

---

## Versioning

The API version is included in the health response:

```json
{
  "version": "1.2.0"
}
```

Breaking changes will increment the major version number.

---

## Next Steps

- [Configuration Reference](CONFIGURATION.md) - Server and query settings
- [Deployment Guide](DEPLOYMENT.md) - Production deployment
- [Plugin Guide](PLUGIN_GUIDE.md) - CLI and skill integration
