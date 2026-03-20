---
last_validated: 2026-03-16
---

# Configuration Reference

This document provides a comprehensive reference for all Agent Brain configuration options, including environment variables, server settings, and per-project configuration.

## Table of Contents

- [Configuration Precedence](#configuration-precedence)
- [Server Configuration](#server-configuration)
- [Embedding Configuration](#embedding-configuration)
- [Chunking Configuration](#chunking-configuration)
- [Query Configuration](#query-configuration)
- [GraphRAG Configuration](#graphrag-configuration)
- [Multi-Instance Configuration](#multi-instance-configuration)
- [Storage Configuration](#storage-configuration)
- [Strict Mode](#strict-mode)
- [Job Queue Configuration](#job-queue-configuration)
- [Embedding Cache Configuration](#embedding-cache-configuration)
- [Reranking Configuration](#reranking-configuration)
- [Per-Project Configuration](#per-project-configuration)
- [Example Configurations](#example-configurations)

---

## Configuration Precedence

Settings are resolved in this order (first match wins):

1. **Command-line flags**: `agent-brain start --port 8080`
2. **Environment variables**: `export API_PORT=8080`
3. **Project config**: `.agent-brain/config.json`
4. **Global config**: `~/.agent-brain/config.json` (future)
5. **Built-in defaults**: Defined in `settings.py`

---

## Server Configuration

### API Host and Port

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `127.0.0.1` | IP address to bind to |
| `API_PORT` | `8000` | Port number (0 = auto-assign) |
| `DEBUG` | `false` | Enable debug mode with auto-reload |

**Examples**:

```bash
# Bind to all interfaces (accessible from network)
export API_HOST="0.0.0.0"

# Use a specific port
export API_PORT="8080"

# Enable debug mode
export DEBUG="true"
```

**CLI Override**:

```bash
agent-brain start --host 0.0.0.0 --port 8080 --reload
```

### Server Modes

| Mode | Description |
|------|-------------|
| `project` | Per-project isolated server (default with `--daemon`) |
| `shared` | Single server for multiple projects (future) |

```bash
export AGENT_BRAIN_MODE="project"
```

---

## Embedding Configuration

### OpenAI Embeddings

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (required) | OpenAI API key |
| `EMBEDDING_MODEL` | `text-embedding-3-large` | Embedding model name |
| `EMBEDDING_DIMENSIONS` | `3072` | Vector dimensions |
| `EMBEDDING_BATCH_SIZE` | `100` | Chunks per API call |

**Examples**:

```bash
# Required: OpenAI API key
export OPENAI_API_KEY="sk-proj-..."

# Use smaller model for cost savings
export EMBEDDING_MODEL="text-embedding-3-small"
export EMBEDDING_DIMENSIONS="1536"
```

### Anthropic API (Summarization)

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | (optional) | Anthropic API key |
| `CLAUDE_MODEL` | `claude-haiku-4-5-20251001` | Claude model for summaries |

**Examples**:

```bash
# Optional: Enable LLM summaries and GraphRAG extraction
export ANTHROPIC_API_KEY="sk-ant-..."
export CLAUDE_MODEL="claude-haiku-4-5-20251001"
```

---

## Chunking Configuration

### Text Document Chunking

| Variable | Default | Range | Description |
|----------|---------|-------|-------------|
| `DEFAULT_CHUNK_SIZE` | `512` | 128-2048 | Target chunk size in tokens |
| `DEFAULT_CHUNK_OVERLAP` | `50` | 0-200 | Overlap between chunks |
| `MAX_CHUNK_SIZE` | `2048` | - | Maximum allowed chunk size |
| `MIN_CHUNK_SIZE` | `128` | - | Minimum allowed chunk size |

**Examples**:

```bash
# Larger chunks for detailed documents
export DEFAULT_CHUNK_SIZE="800"
export DEFAULT_CHUNK_OVERLAP="100"
```

**CLI Override**:

```bash
agent-brain index /path --chunk-size 800 --overlap 100
```

### Code Chunking

Code chunking uses different defaults optimized for source code:

| Setting | Default | Description |
|---------|---------|-------------|
| `chunk_lines` | `40` | Target lines per chunk |
| `chunk_lines_overlap` | `15` | Line overlap |
| `max_chars` | `1500` | Maximum characters |

These are set in the `CodeChunker` class and can be customized programmatically.

---

## Query Configuration

### Default Query Settings

| Variable | Default | Range | Description |
|----------|---------|-------|-------------|
| `DEFAULT_TOP_K` | `5` | 1-50 | Results to return |
| `MAX_TOP_K` | `50` | - | Maximum allowed top_k |
| `DEFAULT_SIMILARITY_THRESHOLD` | `0.7` | 0.0-1.0 | Minimum similarity |

**Examples**:

```bash
# Return more results by default
export DEFAULT_TOP_K="10"

# Lower threshold for broader matches
export DEFAULT_SIMILARITY_THRESHOLD="0.5"
```

**CLI Override**:

```bash
agent-brain query "search term" --top-k 10 --threshold 0.5
```

### Query Modes

| Mode | Alpha | Description |
|------|-------|-------------|
| `bm25` | N/A | Keyword-only search |
| `vector` | N/A | Semantic-only search |
| `hybrid` | `0.5` | BM25 + Vector fusion |
| `graph` | N/A | Graph traversal |
| `multi` | N/A | All three with RRF |

**Alpha Parameter** (hybrid mode only):
- `1.0`: Pure vector search
- `0.5`: Balanced (default)
- `0.0`: Pure BM25 search

---

## GraphRAG Configuration

### Enable/Disable

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_GRAPH_INDEX` | `false` | Master switch for GraphRAG |

**Example**:

```bash
# Enable GraphRAG
export ENABLE_GRAPH_INDEX="true"
```

### Graph Storage

| Variable | Default | Options | Description |
|----------|---------|---------|-------------|
| `GRAPH_STORE_TYPE` | `simple` | `simple`, `kuzu` | Storage backend |
| `GRAPH_INDEX_PATH` | `./graph_index` | Path | Storage location |

**Examples**:

```bash
# Use default in-memory store (development)
export GRAPH_STORE_TYPE="simple"

# Use Kuzu for production
export GRAPH_STORE_TYPE="kuzu"
```

### Entity Extraction

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAPH_USE_CODE_METADATA` | `true` | Extract from AST metadata |
| `GRAPH_USE_LLM_EXTRACTION` | `true` | Use LLM for extraction |
| `GRAPH_EXTRACTION_MODEL` | `claude-haiku-4-5` | LLM model for extraction |
| `GRAPH_MAX_TRIPLETS_PER_CHUNK` | `10` | Limit per chunk |

**Examples**:

```bash
# Code-only extraction (no LLM costs)
export GRAPH_USE_CODE_METADATA="true"
export GRAPH_USE_LLM_EXTRACTION="false"

# Full extraction with fast model
export GRAPH_USE_LLM_EXTRACTION="true"
export GRAPH_EXTRACTION_MODEL="claude-haiku-4-5"
```

### Graph Query

| Variable | Default | Range | Description |
|----------|---------|-------|-------------|
| `GRAPH_TRAVERSAL_DEPTH` | `2` | 1-4 | Hops to traverse |
| `GRAPH_RRF_K` | `60` | 20-100 | RRF constant |

**Examples**:

```bash
# Deeper traversal for complex relationships
export GRAPH_TRAVERSAL_DEPTH="3"

# Adjust RRF fusion (lower = more weight on top ranks)
export GRAPH_RRF_K="40"
```

---

## Multi-Instance Configuration

### State Directory

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_BRAIN_STATE_DIR` | `None` | Override state directory location |
| `AGENT_BRAIN_MODE` | `project` | Instance mode: `project` or `shared` |

> **Legacy aliases:** `DOC_SERVE_STATE_DIR` is still read by `provider_config.py` as a fallback if `AGENT_BRAIN_STATE_DIR` is not set.

**Examples**:

```bash
# Explicit state directory
export AGENT_BRAIN_STATE_DIR="/path/to/.agent-brain"

# Project mode (default)
export AGENT_BRAIN_MODE="project"
```

### CLI Options

```bash
# Start with explicit state directory
agent-brain start --state-dir /path/to/.agent-brain

# Start with project directory (auto-resolves state)
agent-brain start --project-dir /path/to/project
```

---

## Query Cache Configuration

Agent Brain caches query results in memory to avoid redundant storage lookups
for repeated identical queries.  The cache is invalidated automatically whenever
a reindex job completes, ensuring freshness after every index update.

### Query Cache

| Variable | Default | Description |
|----------|---------|-------------|
| `QUERY_CACHE_TTL` | `300` | Time-to-live for cached query results in seconds. Set to a high value for mostly-static indexes, lower for frequently-updated ones. |
| `QUERY_CACHE_MAX_SIZE` | `256` | Maximum number of query results to cache. When full, least-recently-used entries are evicted by TTLCache. |

Notes:
- Query cache is in-memory only (no disk persistence). Cache is empty after server restart.
- `graph` and `multi` query modes are never cached (non-deterministic LLM extraction).
- Cache is automatically invalidated on every successful reindex job completion.
- Cache statistics are visible in the `/health/status` response under the `query_cache` key.

```bash
# Example: longer TTL for a static documentation server
QUERY_CACHE_TTL=3600
QUERY_CACHE_MAX_SIZE=512
```

---

## Strict Mode

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_BRAIN_STRICT_MODE` | `false` | Fail on critical validation errors instead of logging warnings |

When enabled, the server will raise errors for validation issues that would otherwise be logged as warnings (e.g., invalid chunk sizes, missing required metadata).

```bash
# Enable strict validation
export AGENT_BRAIN_STRICT_MODE="true"
```

---

## Job Queue Configuration

Controls the background job queue used for indexing operations.

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_BRAIN_MAX_QUEUE` | `100` | Maximum number of pending jobs in the queue |
| `AGENT_BRAIN_JOB_TIMEOUT` | `7200` | Job timeout in seconds (default: 2 hours) |
| `AGENT_BRAIN_MAX_RETRIES` | `3` | Maximum retry attempts for failed jobs |
| `AGENT_BRAIN_CHECKPOINT_INTERVAL` | `50` | Save progress checkpoint every N files |
| `AGENT_BRAIN_WATCH_DEBOUNCE_SECONDS` | `30` | File watcher debounce delay in seconds |

**Examples**:

```bash
# Increase queue size for large projects
export AGENT_BRAIN_MAX_QUEUE="500"

# Longer timeout for very large codebases
export AGENT_BRAIN_JOB_TIMEOUT="14400"

# More frequent checkpoints
export AGENT_BRAIN_CHECKPOINT_INTERVAL="25"

# Shorter debounce for faster file-watch response
export AGENT_BRAIN_WATCH_DEBOUNCE_SECONDS="10"
```

---

## Embedding Cache Configuration

Controls the two-tier (memory + disk) embedding cache that avoids redundant OpenAI API calls for previously-seen content.

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_CACHE_MAX_DISK_MB` | `500` | Maximum disk cache size in megabytes |
| `EMBEDDING_CACHE_MAX_MEM_ENTRIES` | `1000` | Maximum in-memory LRU cache entries |
| `EMBEDDING_CACHE_PERSIST_STATS` | `false` | Persist hit/miss statistics across server restarts |

**Examples**:

```bash
# Larger disk cache for big repos
export EMBEDDING_CACHE_MAX_DISK_MB="2000"

# Larger in-memory cache
export EMBEDDING_CACHE_MAX_MEM_ENTRIES="5000"

# Persist cache statistics for monitoring
export EMBEDDING_CACHE_PERSIST_STATS="true"
```

---

## Reranking Configuration

Controls the optional two-stage reranking pipeline that improves search relevance by using a cross-encoder model to rescore initial retrieval results.

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_RERANKING` | `false` | Master switch for reranking |
| `RERANKER_PROVIDER` | `sentence-transformers` | Reranker backend (`sentence-transformers` or `ollama`) |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder model name |
| `RERANKER_TOP_K_MULTIPLIER` | `10` | Stage 1 retrieves `top_k * multiplier` candidates |
| `RERANKER_MAX_CANDIDATES` | `100` | Maximum Stage 1 candidates (caps the multiplier) |

**Examples**:

```bash
# Enable reranking
export ENABLE_RERANKING="true"

# Use a different cross-encoder model
export RERANKER_MODEL="cross-encoder/ms-marco-TinyBERT-L-2-v2"

# Retrieve more candidates for reranking
export RERANKER_TOP_K_MULTIPLIER="20"
export RERANKER_MAX_CANDIDATES="200"
```

---

## Storage Configuration

### Storage Backend Selection

Agent Brain supports multiple storage backends:

- `chroma` (default)
- `postgres`

Selection order (first match wins):

1. `AGENT_BRAIN_STORAGE_BACKEND` environment variable
2. `storage.backend` in `config.yaml`
3. Built-in default (`chroma`)

**Example** (`config.yaml`):

```yaml
storage:
  backend: "postgres"  # or "chroma"
```

**Environment override**:

```bash
export AGENT_BRAIN_STORAGE_BACKEND="postgres"
```

### PostgreSQL Backend (pgvector)

When `storage.backend` is `postgres`, configure connection and pool settings
under `storage.postgres`:

```yaml
storage:
  backend: "postgres"
  postgres:
    host: "localhost"
    port: 5432
    database: "agent_brain"
    user: "agent_brain"
    password: "agent_brain_dev"
    pool_size: 10
    pool_max_overflow: 10
    language: "english"
    hnsw_m: 16
    hnsw_ef_construction: 64
    debug: false
```

**Connection string override**:

`DATABASE_URL` overrides the host/user/password/database/port connection
string, but pool settings and HNSW tuning remain in YAML.

```bash
export DATABASE_URL="postgresql+asyncpg://agent_brain:agent_brain_dev@localhost:5432/agent_brain"
```

### ChromaDB Vector Store

| Variable | Default | Description |
|----------|---------|-------------|
| `CHROMA_PERSIST_DIR` | `./chroma_db` | ChromaDB storage location |
| `COLLECTION_NAME` | `agent_brain_collection` | Collection name |

**Examples**:

```bash
# Custom storage location
export CHROMA_PERSIST_DIR="/data/agent-brain/vectors"
```

### BM25 Index

| Variable | Default | Description |
|----------|---------|-------------|
| `BM25_INDEX_PATH` | `./bm25_index` | BM25 index storage |

**Examples**:

```bash
# Custom BM25 storage
export BM25_INDEX_PATH="/data/agent-brain/bm25"
```

---

## Per-Project Configuration

### config.json

Create `.agent-brain/config.json` for project-specific settings:

```json
{
  "default_mode": "hybrid",
  "default_top_k": 10,
  "default_threshold": 0.5,
  "include_code": true,
  "languages": ["python", "typescript", "javascript"],
  "exclude_patterns": [
    "node_modules/**",
    "__pycache__/**",
    "*.log",
    ".git/**"
  ],
  "chunk_size": 512,
  "chunk_overlap": 50,
  "graph_enabled": false
}
```

### Configuration Schema

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `default_mode` | string | `"hybrid"` | Default search mode |
| `default_top_k` | integer | `5` | Default result count |
| `default_threshold` | float | `0.7` | Default similarity threshold |
| `include_code` | boolean | `false` | Include code in indexing |
| `languages` | array | `[]` | Languages to index (empty = all) |
| `exclude_patterns` | array | `[]` | Glob patterns to exclude |
| `chunk_size` | integer | `512` | Chunk size in tokens |
| `chunk_overlap` | integer | `50` | Chunk overlap in tokens |
| `graph_enabled` | boolean | `false` | Enable GraphRAG |

---

## Example Configurations

### Development Setup

Minimal configuration for local development:

```bash
# .env
OPENAI_API_KEY=sk-proj-...
DEBUG=true
DEFAULT_TOP_K=10
DEFAULT_SIMILARITY_THRESHOLD=0.5
```

### Production Setup

Full configuration for production deployment:

```bash
# .env
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...

# Server
API_HOST=127.0.0.1
API_PORT=8000
DEBUG=false

# Embedding
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIMENSIONS=3072
EMBEDDING_BATCH_SIZE=100

# Query defaults
DEFAULT_TOP_K=5
DEFAULT_SIMILARITY_THRESHOLD=0.7

# Storage
CHROMA_PERSIST_DIR=/data/agent-brain/vectors
BM25_INDEX_PATH=/data/agent-brain/bm25

# GraphRAG (optional)
ENABLE_GRAPH_INDEX=true
GRAPH_STORE_TYPE=kuzu
GRAPH_INDEX_PATH=/data/agent-brain/graph
GRAPH_USE_CODE_METADATA=true
GRAPH_USE_LLM_EXTRACTION=true
GRAPH_EXTRACTION_MODEL=claude-haiku-4-5
GRAPH_TRAVERSAL_DEPTH=2

# Embedding cache
EMBEDDING_CACHE_MAX_DISK_MB=2000
EMBEDDING_CACHE_MAX_MEM_ENTRIES=5000

# Job queue
AGENT_BRAIN_MAX_QUEUE=500
AGENT_BRAIN_JOB_TIMEOUT=7200
AGENT_BRAIN_CHECKPOINT_INTERVAL=50

# Reranking (optional)
ENABLE_RERANKING=true
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
```

### Code-Heavy Repository

Configuration optimized for source code:

```bash
# .env
OPENAI_API_KEY=sk-proj-...

# Larger chunks for code
DEFAULT_CHUNK_SIZE=800
DEFAULT_CHUNK_OVERLAP=100

# GraphRAG for code relationships
ENABLE_GRAPH_INDEX=true
GRAPH_USE_CODE_METADATA=true
GRAPH_USE_LLM_EXTRACTION=false  # Code metadata is sufficient
```

Project config (`.agent-brain/config.json`):

```json
{
  "include_code": true,
  "languages": ["python", "typescript", "javascript", "java"],
  "exclude_patterns": [
    "node_modules/**",
    "__pycache__/**",
    "dist/**",
    "build/**",
    "*.min.js"
  ],
  "graph_enabled": true
}
```

### Documentation-Only Setup

Configuration for pure documentation search:

```bash
# .env
OPENAI_API_KEY=sk-proj-...

# Smaller chunks for precise documentation
DEFAULT_CHUNK_SIZE=400
DEFAULT_CHUNK_OVERLAP=50

# No GraphRAG needed
ENABLE_GRAPH_INDEX=false
```

Project config:

```json
{
  "include_code": false,
  "default_mode": "hybrid",
  "default_threshold": 0.6
}
```

### Cost-Optimized Setup

Minimize API costs:

```bash
# .env
OPENAI_API_KEY=sk-proj-...

# Use smaller embedding model
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536

# Disable LLM extraction
GRAPH_USE_LLM_EXTRACTION=false
```

---

## Environment File Locations

Agent Brain searches for `.env` files in this order:

1. Current working directory: `./.env`
2. Server package directory: `agent-brain-server/.env`
3. Project root: `../.env`

**Best Practice**: Place `.env` in your project root and add to `.gitignore`.

---

## Validation

### Check Current Configuration

```bash
# View server status (includes some config)
agent-brain status

# View all environment variables
env | grep -E "(OPENAI|ANTHROPIC|EMBEDDING|GRAPH|CHUNK|API)"
```

### Test Configuration

```bash
# Start server and check health
agent-brain start --daemon
curl http://127.0.0.1:8000/health

# Index test documents
agent-brain index ./docs --include-code

# Test query
agent-brain query "test" --mode hybrid
```

---

## Next Steps

- [API Reference](API_REFERENCE.md) - REST API documentation
- [Deployment Guide](DEPLOYMENT.md) - Production deployment
- [Architecture Overview](ARCHITECTURE.md) - System design
