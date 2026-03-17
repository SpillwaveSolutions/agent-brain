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
  - [Folder Management Endpoints](#folder-management-endpoints)
  - [Cache Management Endpoints](#cache-management-endpoints)
  - [Job Queue Endpoints](#job-queue-endpoints)
- [Request/Response Models](#requestresponse-models)
- [Error Handling](#error-handling)
- [Examples](#examples)

---

## Overview

The Agent Brain API is a RESTful JSON API built with FastAPI. It provides endpoints for:

- **Health Monitoring**: Server status, indexing progress, and provider health
- **Document Querying**: Semantic, keyword, hybrid, graph, and multi-mode search
- **Document Indexing**: Index documents and code from folders with job queue
- **Folder Management**: List and remove indexed folders
- **Cache Management**: View and clear embedding cache
- **Job Queue**: Monitor and cancel indexing jobs

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

For per-project instances, read the port from `.agent-brain/runtime.json`:

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
  "timestamp": "2026-01-15T10:30:00Z",
  "version": "9.0.0",
  "mode": "project",
  "instance_id": "abc123",
  "project_id": "my-project",
  "active_projects": null
}
```

**Status Values**:

| Status | Description |
|--------|-------------|
| `healthy` | Ready for queries |
| `indexing` | Indexing in progress |
| `degraded` | Running with issues (e.g., vector store not initialized) |
| `unhealthy` | Not operational |

---

#### GET /health/status

Get detailed indexing status. This endpoint never blocks, even during active indexing.

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
  "last_indexed_at": "2026-01-15T10:30:00Z",
  "indexed_folders": ["/path/to/docs"],
  "supported_languages": ["python", "typescript"],
  "graph_index": {
    "enabled": true,
    "initialized": true,
    "entity_count": 120,
    "relationship_count": 250,
    "store_type": "simple"
  },
  "queue_pending": 0,
  "queue_running": 0,
  "current_job_running_time_ms": null,
  "file_watcher": {
    "running": true,
    "watched_folders": 2
  },
  "embedding_cache": {
    "hits": 150,
    "misses": 30,
    "hit_rate": 0.833,
    "mem_entries": 180,
    "entry_count": 500,
    "size_bytes": 2048000
  },
  "query_cache": {
    "hits": 10,
    "misses": 5,
    "hit_rate": 0.667,
    "cached_entries": 5,
    "index_generation": 3
  }
}
```

**Note:** The `embedding_cache` field is omitted for fresh installs with an empty cache. The `query_cache` field is `null` when the cache service is not initialized.

---

#### GET /health/providers

Get detailed status of all configured providers with health checks.

**Response** `200 OK`:

```json
{
  "config_source": "/path/to/.agent-brain/agent-brain.yml",
  "strict_mode": false,
  "validation_errors": [],
  "providers": [
    {
      "provider_type": "embedding",
      "provider_name": "openai",
      "model": "text-embedding-3-large",
      "status": "healthy",
      "message": null,
      "dimensions": 3072
    },
    {
      "provider_type": "summarization",
      "provider_name": "anthropic",
      "model": "claude-haiku-4-5-20251001",
      "status": "healthy",
      "message": null,
      "dimensions": null
    }
  ],
  "timestamp": "2026-01-15T10:30:00Z"
}
```

A `reranker` provider entry is included when `ENABLE_RERANKING=true`.

---

#### GET /health/postgres

Get PostgreSQL connection pool metrics and database info. Only available when storage backend is `postgres`.

**Response** `200 OK`:

```json
{
  "status": "healthy",
  "backend": "postgres",
  "pool": {
    "pool_size": 5,
    "checked_in": 4,
    "checked_out": 1,
    "overflow": 0
  },
  "database": {
    "version": "PostgreSQL 16.2 ...",
    "host": "localhost",
    "port": 5432,
    "database": "agent_brain"
  }
}
```

**Errors**:

| Code | Description |
|------|-------------|
| `400` | Storage backend is not postgres |

---

### Query Endpoints

#### POST /query

Execute a search query.

**Request Body**:

```json
{
  "query": "how does authentication work",
  "top_k": 5,
  "similarity_threshold": 0.3,
  "mode": "hybrid",
  "alpha": 0.5,
  "source_types": ["doc", "code"],
  "languages": ["python", "typescript"],
  "file_paths": ["src/**/*.py"],
  "entity_types": ["Class", "Function"],
  "relationship_types": ["calls", "extends"]
}
```

**Parameters**:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | (required) | Search query (1-1000 chars) |
| `top_k` | integer | `5` | Results to return (1-50) |
| `similarity_threshold` | float | `0.3` | Minimum similarity (0.0-1.0) |
| `mode` | string | `"hybrid"` | Search mode |
| `alpha` | float | `0.5` | Hybrid balance (0=BM25, 1=Vector) |
| `source_types` | array | `null` | Filter by `["doc", "code", "test"]` |
| `languages` | array | `null` | Filter by programming languages |
| `file_paths` | array | `null` | Filter by file patterns (supports wildcards) |
| `entity_types` | array | `null` | Filter graph results by entity types (graph/multi modes only) |
| `relationship_types` | array | `null` | Filter graph results by relationship types (graph/multi modes only) |

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
      "rerank_score": null,
      "original_rank": null,
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
| `vector_score` | float or null | Semantic similarity score |
| `bm25_score` | float or null | Keyword match score |
| `graph_score` | float or null | Graph traversal score |
| `chunk_id` | string | Unique chunk identifier |
| `source_type` | string | `"doc"`, `"code"`, or `"test"` |
| `language` | string or null | Programming language |
| `related_entities` | array or null | GraphRAG related entities |
| `relationship_path` | array or null | GraphRAG relationship paths |
| `rerank_score` | float or null | Score from reranking stage (if enabled) |
| `original_rank` | integer or null | Position before reranking (1-indexed) |
| `metadata` | object | Additional metadata |

**Errors**:

| Code | Description |
|------|-------------|
| `400` | Invalid query (empty or too long) |
| `409` | Embedding provider mismatch (re-index required) |
| `503` | Index not ready (indexing in progress or not initialized) |

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

Enqueue a job to index documents from a folder. Returns immediately with a job ID. The job is processed asynchronously by a background worker.

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `force` | boolean | `false` | Bypass deduplication and force a new job |
| `allow_external` | boolean | `false` | Allow paths outside the project directory |
| `rebuild_graph` | boolean | `false` | Rebuild only the graph index without re-indexing documents (requires `ENABLE_GRAPH_INDEX=true`) |

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
  "force": false,
  "include_patterns": ["docs/**/*.md", "src/**/*.py"],
  "include_types": ["python", "docs"],
  "exclude_patterns": ["node_modules/**", "__pycache__/**"],
  "injector_script": null,
  "folder_metadata_file": null,
  "dry_run": false,
  "watch_mode": null,
  "watch_debounce_seconds": null
}
```

**Body Parameters**:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `folder_path` | string | (required) | Path to folder |
| `chunk_size` | integer | `512` | Chunk size in tokens (128-2048) |
| `chunk_overlap` | integer | `50` | Overlap in tokens (0-200) |
| `recursive` | boolean | `true` | Scan subdirectories |
| `include_code` | boolean | `false` | Include source code files |
| `supported_languages` | array | `null` | Languages to index |
| `code_chunk_strategy` | string | `"ast_aware"` | `"ast_aware"` or `"text_based"` |
| `generate_summaries` | boolean | `false` | Generate LLM summaries for code chunks |
| `force` | boolean | `false` | Force re-indexing even if embedding provider changed |
| `include_patterns` | array | `null` | Glob patterns to include |
| `include_types` | array | `null` | File type presets (e.g., `["python", "docs"]`) |
| `exclude_patterns` | array | `null` | Glob patterns to exclude |
| `injector_script` | string | `null` | Path to Python script exporting `process_chunk(chunk: dict) -> dict` |
| `folder_metadata_file` | string | `null` | Path to JSON file with static metadata to merge into all chunks |
| `dry_run` | boolean | `false` | Validate injector against sample chunks without indexing |
| `watch_mode` | string | `null` | Watch mode for auto-reindex: `"auto"` or `"off"` |
| `watch_debounce_seconds` | integer | `null` | Per-folder debounce in seconds |

**Response** `202 Accepted`:

```json
{
  "job_id": "job_abc123def456",
  "status": "pending",
  "message": "Job queued for /path/to/documents"
}
```

**Errors**:

| Code | Description |
|------|-------------|
| `400` | Invalid folder path, path outside project (without `allow_external`), invalid injector script, invalid include_types preset, or `rebuild_graph=true` with GraphRAG not enabled |
| `429` | Queue is full (backpressure) |

---

#### POST /index/add

Enqueue a job to add documents from another folder to the existing index. Same request body as `POST /index` (without `generate_summaries`, `injector_script`, `folder_metadata_file`, `dry_run`, `watch_mode`, `watch_debounce_seconds`).

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `force` | boolean | `false` | Bypass deduplication and force a new job |
| `allow_external` | boolean | `false` | Allow paths outside the project directory |

**Response** `202 Accepted`:

```json
{
  "job_id": "job_abc123def456",
  "status": "pending",
  "message": "Job queued to add documents from /path/to/documents"
}
```

**Errors**:

| Code | Description |
|------|-------------|
| `400` | Invalid folder path, path outside project (without `allow_external`), or invalid include_types preset |
| `429` | Queue is full (backpressure) |

---

#### DELETE /index

Reset the index (delete all documents). Cannot be performed while jobs are running.

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
| `409` | Cannot reset while indexing jobs are in progress |

---

### Folder Management Endpoints

#### GET /index/folders

List all folders that have been indexed with chunk counts and metadata.

**Response** `200 OK`:

```json
{
  "folders": [
    {
      "folder_path": "/home/user/project/docs",
      "chunk_count": 42,
      "last_indexed": "2026-02-24T01:00:00+00:00",
      "watch_mode": "off",
      "watch_debounce_seconds": null
    },
    {
      "folder_path": "/home/user/project/src",
      "chunk_count": 128,
      "last_indexed": "2026-02-24T00:30:00+00:00",
      "watch_mode": "auto",
      "watch_debounce_seconds": 10
    }
  ],
  "total": 2
}
```

---

#### DELETE /index/folders

Remove a folder from the index, deleting all its chunks from the vector store.

**Request Body**:

```json
{
  "folder_path": "/home/user/project/docs"
}
```

**Body Parameters**:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `folder_path` | string | (required) | Path to the folder to remove from the index |

**Response** `200 OK`:

```json
{
  "folder_path": "/home/user/project/docs",
  "chunks_deleted": 42,
  "message": "Successfully removed 42 chunks for /home/user/project/docs"
}
```

**Errors**:

| Code | Description |
|------|-------------|
| `404` | Folder not found in the index |
| `409` | Active indexing job running for this folder |
| `500` | Failed to delete chunks |

---

### Cache Management Endpoints

#### GET /index/cache

Get embedding cache hit/miss counters and disk statistics.

**Response** `200 OK`:

```json
{
  "hits": 150,
  "misses": 30,
  "hit_rate": 0.833,
  "mem_entries": 180,
  "entry_count": 500,
  "size_bytes": 2048000
}
```

**Errors**:

| Code | Description |
|------|-------------|
| `503` | Embedding cache service not initialized |

---

#### DELETE /index/cache

Clear all cached embeddings and reclaim disk space. Safe to call while indexing jobs are running (running jobs will regenerate embeddings at normal API cost).

**Response** `200 OK`:

```json
{
  "count": 500,
  "size_bytes": 2048000,
  "size_mb": 1.953125
}
```

**Errors**:

| Code | Description |
|------|-------------|
| `503` | Embedding cache service not initialized |

---

### Job Queue Endpoints

Indexing operations are queued and processed asynchronously.

#### GET /index/jobs

List all jobs in the queue.

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | `50` | Maximum results (1-100) |
| `offset` | integer | `0` | Skip first N results |

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
      "source": "manual",
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
  "source": "manual",
  "enqueued_at": "2026-02-03T10:00:00Z",
  "started_at": "2026-02-03T10:00:05Z",
  "finished_at": null,
  "execution_time_ms": 15000,
  "progress": {
    "files_processed": 45,
    "files_total": 100,
    "chunks_created": 230,
    "current_file": "src/services/auth.py",
    "percent_complete": 45.0,
    "updated_at": "2026-02-03T10:00:20Z"
  },
  "total_documents": 45,
  "total_chunks": 230,
  "error": null,
  "retry_count": 0,
  "cancel_requested": false,
  "eviction_summary": null
}
```

**Errors**:

| Code | Description |
|------|-------------|
| `404` | Job not found |

---

#### DELETE /index/jobs/{job_id}

Cancel a pending or running job.

- **PENDING** jobs are cancelled immediately.
- **RUNNING** jobs have `cancel_requested` flag set; the worker will stop at the next checkpoint.
- Completed, failed, or already cancelled jobs return 409.

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
| `409` | Cannot cancel completed/failed/cancelled job |

---

## Request/Response Models

### QueryRequest

```typescript
interface QueryRequest {
  query: string;                    // 1-1000 characters
  top_k?: number;                   // 1-50, default 5
  similarity_threshold?: number;    // 0.0-1.0, default 0.3
  mode?: "bm25" | "vector" | "hybrid" | "graph" | "multi"; // default "hybrid"
  alpha?: number;                   // 0.0-1.0, default 0.5
  source_types?: string[];          // ["doc", "code", "test"]
  languages?: string[];             // ["python", "typescript", ...]
  file_paths?: string[];            // Glob patterns
  entity_types?: string[];          // ["Class", "Function", ...] (graph/multi modes)
  relationship_types?: string[];    // ["calls", "extends", ...] (graph/multi modes)
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
  source_type: string;              // "doc", "code", or "test"
  language?: string;
  related_entities?: string[];
  relationship_path?: string[];
  rerank_score?: number;            // if reranking enabled
  original_rank?: number;           // position before reranking (1-indexed)
  metadata: Record<string, any>;
}
```

### IndexRequest

```typescript
interface IndexRequest {
  folder_path: string;
  chunk_size?: number;              // 128-2048, default 512
  chunk_overlap?: number;           // 0-200, default 50
  recursive?: boolean;              // default true
  include_code?: boolean;           // default false
  supported_languages?: string[];
  code_chunk_strategy?: "ast_aware" | "text_based"; // default "ast_aware"
  generate_summaries?: boolean;     // default false
  force?: boolean;                  // default false
  include_patterns?: string[];
  include_types?: string[];         // file type presets, e.g. ["python", "docs"]
  exclude_patterns?: string[];
  injector_script?: string;         // path to Python injector script
  folder_metadata_file?: string;    // path to JSON metadata file
  dry_run?: boolean;                // default false
  watch_mode?: string;              // "auto" or "off"
  watch_debounce_seconds?: number;  // per-folder debounce in seconds
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
  timestamp: string;                // ISO 8601
  version: string;
  mode?: string;                    // "project" or "shared"
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
  last_indexed_at?: string;         // ISO 8601
  indexed_folders: string[];
  supported_languages: string[];
  graph_index?: GraphIndexStatus;
  queue_pending: number;
  queue_running: number;
  current_job_running_time_ms?: number;
  file_watcher?: FileWatcherStatus;
  embedding_cache?: EmbeddingCacheStatus; // omitted when cache is empty
  query_cache?: QueryCacheStatus;
}

interface GraphIndexStatus {
  enabled: boolean;
  initialized: boolean;
  entity_count: number;
  relationship_count: number;
  store_type: string;
}

interface FileWatcherStatus {
  running: boolean;
  watched_folders: number;
}

interface EmbeddingCacheStatus {
  hits: number;
  misses: number;
  hit_rate: number;
  mem_entries: number;
  entry_count: number;
  size_bytes: number;
}

interface QueryCacheStatus {
  hits: number;
  misses: number;
  hit_rate: number;
  cached_entries: number;
  index_generation: number;
}
```

### ProvidersStatus

```typescript
interface ProvidersStatus {
  config_source?: string;
  strict_mode: boolean;
  validation_errors: string[];
  providers: ProviderHealth[];
  timestamp: string;                // ISO 8601
}

interface ProviderHealth {
  provider_type: string;            // "embedding", "summarization", "reranker"
  provider_name: string;            // e.g. "openai", "anthropic", "ollama"
  model: string;
  status: string;                   // "healthy", "degraded", "unavailable"
  message?: string;
  dimensions?: number;              // for embedding providers
}
```

### FolderListResponse

```typescript
interface FolderListResponse {
  folders: FolderInfo[];
  total: number;
}

interface FolderInfo {
  folder_path: string;
  chunk_count: number;
  last_indexed: string;             // ISO 8601
  watch_mode: string;               // "off" or "auto"
  watch_debounce_seconds?: number;
}
```

### FolderDeleteRequest / FolderDeleteResponse

```typescript
interface FolderDeleteRequest {
  folder_path: string;
}

interface FolderDeleteResponse {
  folder_path: string;
  chunks_deleted: number;
  message: string;
}
```

### JobListResponse / JobDetailResponse

```typescript
interface JobListResponse {
  jobs: JobSummary[];
  total: number;
  pending: number;
  running: number;
  completed: number;
  failed: number;
}

interface JobSummary {
  id: string;
  status: "pending" | "running" | "done" | "failed" | "cancelled";
  folder_path: string;
  operation: string;                // "index" or "add"
  include_code: boolean;
  source: string;                   // "manual" or "auto"
  enqueued_at: string;
  started_at?: string;
  finished_at?: string;
  progress_percent: number;
  error?: string;
}

interface JobDetailResponse {
  id: string;
  status: "pending" | "running" | "done" | "failed" | "cancelled";
  folder_path: string;
  operation: string;
  include_code: boolean;
  source: string;
  enqueued_at: string;
  started_at?: string;
  finished_at?: string;
  execution_time_ms?: number;
  progress?: JobProgress;
  total_documents: number;
  total_chunks: number;
  error?: string;
  retry_count: number;
  cancel_requested: boolean;
  eviction_summary?: Record<string, any>;
}

interface JobProgress {
  files_processed: number;
  files_total: number;
  chunks_created: number;
  current_file: string;
  percent_complete: number;
  updated_at: string;
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
| `409` | Conflict (e.g., embedding mismatch, jobs in progress) |
| `429` | Too Many Requests (queue full) |
| `500` | Internal Server Error |
| `503` | Service Unavailable (index not ready or cache not initialized) |

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

// Embedding provider mismatch
{
  "detail": "Embedding mismatch: ... Re-index with --force to resolve."
}
```

**Index Errors**:

```json
// Folder not found
{
  "detail": "Folder not found: /path/to/nonexistent"
}

// Queue full
{
  "detail": "Queue full (3 pending, 1 running). Try again later."
}

// Path outside project
{
  "detail": "Path /external/path is outside project root /home/user/project"
}
```

---

## Examples

### cURL Examples

**Health Check**:

```bash
curl http://localhost:8000/health
```

**Provider Status**:

```bash
curl http://localhost:8000/health/providers
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

**Start Indexing (with force)**:

```bash
curl -X POST "http://localhost:8000/index?force=true" \
  -H "Content-Type: application/json" \
  -d '{
    "folder_path": "/path/to/project",
    "include_code": true,
    "recursive": true
  }'
```

**List Indexed Folders**:

```bash
curl http://localhost:8000/index/folders
```

**Remove a Folder from Index**:

```bash
curl -X DELETE http://localhost:8000/index/folders \
  -H "Content-Type: application/json" \
  -d '{"folder_path": "/path/to/project/docs"}'
```

**Check Embedding Cache**:

```bash
curl http://localhost:8000/index/cache
```

**Clear Embedding Cache**:

```bash
curl -X DELETE http://localhost:8000/index/cache
```

**List Jobs**:

```bash
curl "http://localhost:8000/index/jobs?limit=10"
```

**Get Job Details**:

```bash
curl http://localhost:8000/index/jobs/job_abc123def456
```

**Cancel a Job**:

```bash
curl -X DELETE http://localhost:8000/index/jobs/job_abc123def456
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
            params={"force": True},
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
  "version": "9.0.0"
}
```

Breaking changes will increment the major version number.

---

## Next Steps

- [Configuration Reference](CONFIGURATION.md) - Server and query settings
- [Deployment Guide](DEPLOYMENT.md) - Production deployment
- [Plugin Guide](PLUGIN_GUIDE.md) - CLI and skill integration
