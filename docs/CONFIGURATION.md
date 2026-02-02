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
- [Per-Project Configuration](#per-project-configuration)
- [Example Configurations](#example-configurations)

---

## Configuration Precedence

Settings are resolved in this order (first match wins):

1. **Command-line flags**: `agent-brain start --port 8080`
2. **Environment variables**: `export API_PORT=8080`
3. **Project config**: `.claude/agent-brain/config.json`
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
export DOC_SERVE_MODE="project"
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

| Variable | Description |
|----------|-------------|
| `DOC_SERVE_STATE_DIR` | Override state directory location |
| `DOC_SERVE_MODE` | Instance mode: `project` or `shared` |

**Examples**:

```bash
# Explicit state directory
export DOC_SERVE_STATE_DIR="/path/to/.claude/agent-brain"

# Project mode (default)
export DOC_SERVE_MODE="project"
```

### CLI Options

```bash
# Start with explicit state directory
agent-brain start --state-dir /path/to/.claude/agent-brain

# Start with project directory (auto-resolves state)
agent-brain start --project-dir /path/to/project
```

---

## Storage Configuration

### ChromaDB Vector Store

| Variable | Default | Description |
|----------|---------|-------------|
| `CHROMA_PERSIST_DIR` | `./chroma_db` | ChromaDB storage location |
| `COLLECTION_NAME` | `doc_serve_collection` | Collection name |

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

Create `.claude/agent-brain/config.json` for project-specific settings:

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

Project config (`.claude/agent-brain/config.json`):

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
