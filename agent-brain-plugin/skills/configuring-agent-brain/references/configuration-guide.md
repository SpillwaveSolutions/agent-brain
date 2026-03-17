# Agent Brain Configuration Guide

## Overview

Agent Brain supports multiple configuration methods with clear precedence rules. This guide covers all configuration options.

## Configuration Methods

### Method 1: YAML Configuration File (Recommended)

The config.yaml file provides a centralized configuration without needing to modify shell profiles.

**Search locations** (in order):

1. `AGENT_BRAIN_CONFIG` environment variable (explicit path)
2. Current directory: `./agent-brain.yaml` or `./config.yaml`
3. Project directory: `./.agent-brain/config.yaml`
4. User home: `~/.agent-brain/config.yaml`
5. XDG config: `~/.config/agent-brain/config.yaml`

**Complete config.yaml example**:

```yaml
# ~/.agent-brain/config.yaml
# Agent Brain Configuration

# Server settings (for CLI connection)
server:
  url: "http://127.0.0.1:8000"
  host: "127.0.0.1"
  port: 8000
  auto_port: true

# Project settings
project:
  state_dir: null  # null = use default (.agent-brain)
  # state_dir: "/custom/path/state"  # Custom state directory
  project_root: null  # null = auto-detect

# Embedding provider configuration
embedding:
  provider: "openai"  # openai, ollama, cohere, gemini
  model: "text-embedding-3-large"

  # API key configuration - choose ONE approach:
  api_key: "sk-proj-..."              # Direct API key in config
  # api_key_env: "OPENAI_API_KEY"     # OR read from environment variable

  # Custom endpoint (for Ollama or proxies)
  base_url: null  # null = use default, or "http://localhost:11434/v1" for Ollama

# Summarization provider configuration
summarization:
  provider: "anthropic"  # anthropic, openai, ollama, gemini, grok
  model: "claude-haiku-4-5-20251001"

  # API key configuration
  api_key: "sk-ant-..."               # Direct API key
  # api_key_env: "ANTHROPIC_API_KEY"  # OR read from environment variable

  base_url: null

# Storage backend configuration
storage:
  backend: "chroma"  # "chroma" (default) or "postgres"
  # postgres:  # Only needed when backend is "postgres"
  #   host: "localhost"
  #   port: 5432
  #   database: "agent_brain"
  #   user: "agent_brain"
  #   password: "agent_brain_dev"

# GraphRAG configuration (optional, default: disabled)
graphrag:
  enabled: false
  store_type: "simple"  # "simple" (in-memory) or "kuzu" (persistent disk)
  use_code_metadata: true

# Query mode (informational — set per-request with --mode flag)
# query:
#   default_mode: "hybrid"  # vector | bm25 | hybrid | graph | multi
```

### Method 2: Environment Variables

Traditional approach using shell environment:

```bash
# Core settings
export AGENT_BRAIN_URL="http://127.0.0.1:8000"
export AGENT_BRAIN_STATE_DIR=".agent-brain"
export AGENT_BRAIN_CONFIG="/path/to/config.yaml"

# Provider configuration
export EMBEDDING_PROVIDER=openai
export EMBEDDING_MODEL=text-embedding-3-large
export SUMMARIZATION_PROVIDER=anthropic
export SUMMARIZATION_MODEL=claude-haiku-4-5-20251001

# API keys
export OPENAI_API_KEY="sk-proj-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Method 3: .env File

Create `.agent-brain/.env` or project root `.env`:

```bash
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-large
```

---

## Configuration Precedence

Settings are resolved in order (first wins):

1. **CLI options** (`--url`, `--port`, `--state-dir`)
2. **Environment variables** (`AGENT_BRAIN_URL`, `OPENAI_API_KEY`)
3. **Config file** (`config.yaml` values)
4. **Built-in defaults**

For API keys specifically:
1. `api_key` field in config.yaml
2. Environment variable specified by `api_key_env`
3. Default environment variable (e.g., `OPENAI_API_KEY`)

---

## Storage Backend Configuration

Agent Brain supports two storage backends:

- `chroma` (default)
- `postgres`

**Recommended YAML configuration**:

```yaml
storage:
  backend: "postgres"  # or "chroma"
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

**Environment overrides**:

- `AGENT_BRAIN_STORAGE_BACKEND` overrides `storage.backend`
- `DATABASE_URL` overrides the connection string only (pool settings stay in YAML)

```bash
export AGENT_BRAIN_STORAGE_BACKEND="postgres"
export DATABASE_URL="postgresql+asyncpg://agent_brain:agent_brain_dev@localhost:5432/agent_brain"
```

**BM25 and Full-Text Search with PostgreSQL**

When using the PostgreSQL backend, the disk-based BM25 index is replaced by
PostgreSQL's built-in full-text search (`tsvector` + `websearch_to_tsquery`).

- `--mode bm25` queries use `ts_rank` scoring with `websearch_to_tsquery` syntax
- Scores are normalized to 0-1 to match ChromaDB BM25 output format
- The `storage.postgres.language` setting (default: `"english"`) controls the
  tsvector language configuration
- No BM25 configuration or index files are needed with PostgreSQL

---

## API Keys

### OpenAI API Key

Required for vector and hybrid search with OpenAI embeddings.

**Option A: In config.yaml**
```yaml
embedding:
  provider: "openai"
  api_key: "sk-proj-..."
```

**Option B: Environment variable**
```bash
export OPENAI_API_KEY="sk-proj-..."
```

**Get your key**: https://platform.openai.com/account/api-keys

**Verify key is set**:
```bash
echo "OpenAI key: ${OPENAI_API_KEY:+CONFIGURED}"
```

### Anthropic API Key

Required for Claude summarization.

**Option A: In config.yaml**
```yaml
summarization:
  provider: "anthropic"
  api_key: "sk-ant-..."
```

**Option B: Environment variable**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Get your key**: https://console.anthropic.com/

### Other Provider Keys

| Provider | Config Field | Environment Variable |
|----------|-------------|---------------------|
| Google Gemini | `api_key` | `GOOGLE_API_KEY` |
| Grok (xAI) | `api_key` | `XAI_API_KEY` |
| Cohere | `api_key` | `COHERE_API_KEY` |
| Ollama | (not needed) | (not needed) |

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AGENT_BRAIN_CONFIG` | No | - | Path to config.yaml file |
| `AGENT_BRAIN_URL` | No | Auto-detect | Server URL for CLI |
| `AGENT_BRAIN_STATE_DIR` | No | `.agent-brain` | State directory path |
| `AGENT_BRAIN_MODE` | No | `project` | Instance mode: `project` or `shared` |
| `OPENAI_API_KEY` | Conditional | - | OpenAI API key |
| `ANTHROPIC_API_KEY` | Conditional | - | Anthropic API key |
| `GOOGLE_API_KEY` | Conditional | - | Google/Gemini API key |
| `XAI_API_KEY` | Conditional | - | Grok API key |
| `COHERE_API_KEY` | Conditional | - | Cohere API key |
| `EMBEDDING_PROVIDER` | No | `openai` | Embedding provider |
| `EMBEDDING_MODEL` | No | `text-embedding-3-large` | Embedding model |
| `SUMMARIZATION_PROVIDER` | No | `anthropic` | Summarization provider |
| `SUMMARIZATION_MODEL` | No | `claude-haiku-4-5-20251001` | Summarization model |
| `DEBUG` | No | `false` | Enable debug logging |
| `QUERY_CACHE_TTL` | No | 300 | Query cache TTL in seconds (0 = disabled) |
| `QUERY_CACHE_MAX_SIZE` | No | 256 | Max number of cached query results |

---

## GraphRAG Configuration (Feature 113)

GraphRAG enables graph-based retrieval using entity relationships extracted from documents and code.

### GraphRAG Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENABLE_GRAPH_INDEX` | No | `false` | Master switch to enable graph indexing |
| `GRAPH_STORE_TYPE` | No | `simple` | Graph backend: `simple` (in-memory) or `kuzu` (persistent) |
| `GRAPH_INDEX_PATH` | No | `./graph_index` | Path for graph persistence |
| `GRAPH_EXTRACTION_MODEL` | No | `claude-haiku-4-5` | Model for entity extraction |
| `GRAPH_MAX_TRIPLETS_PER_CHUNK` | No | `10` | Maximum triplets extracted per document chunk |
| `GRAPH_USE_CODE_METADATA` | No | `true` | Extract entities from AST metadata (imports, classes) |
| `GRAPH_USE_LLM_EXTRACTION` | No | `true` | Use LLM for semantic entity extraction |
| `GRAPH_TRAVERSAL_DEPTH` | No | `2` | Depth for graph traversal in queries |
| `GRAPH_RRF_K` | No | `60` | Reciprocal Rank Fusion constant for multi-mode queries |

### GraphRAG in config.yaml

```yaml
# ~/.agent-brain/config.yaml
graphrag:
  enabled: true
  store_type: "simple"  # "simple" or "kuzu"
  index_path: "./graph_index"
  extraction_model: "claude-haiku-4-5"
  max_triplets_per_chunk: 10
  use_code_metadata: true
  use_llm_extraction: true
  traversal_depth: 2
  rrf_k: 60
```

### GraphRAG via Environment Variables

```bash
# Enable GraphRAG
export ENABLE_GRAPH_INDEX=true

# Use Kuzu for persistent graph storage (optional)
export GRAPH_STORE_TYPE=kuzu
export GRAPH_INDEX_PATH=".agent-brain/graph_index"

# Entity extraction settings
export GRAPH_EXTRACTION_MODEL=claude-haiku-4-5
export GRAPH_MAX_TRIPLETS_PER_CHUNK=10

# Code relationship extraction (recommended for codebases)
export GRAPH_USE_CODE_METADATA=true
export GRAPH_USE_LLM_EXTRACTION=true

# Query settings
export GRAPH_TRAVERSAL_DEPTH=2
export GRAPH_RRF_K=60
```

---

## Query Cache Configuration

The query cache stores identical query results for a configurable TTL window.
It is auto-enabled — no setup required.

### Behavior

- Identical queries within the TTL return instantly without hitting storage
- Cache is invalidated when any reindex job completes (watcher or manual)
- `graph` and `multi` query modes are **never cached** — each call reaches storage
- Cache is in-memory and does not persist across server restarts

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QUERY_CACHE_TTL` | `300` | Cache TTL in seconds. Set to `0` to disable. |
| `QUERY_CACHE_MAX_SIZE` | `256` | Maximum cached query results (LRU eviction) |

### Example

```bash
# Extend cache TTL to 10 minutes for stable codebases
export QUERY_CACHE_TTL=600

# Increase cache size for large query workloads
export QUERY_CACHE_MAX_SIZE=512
```

### Disable Query Cache

```bash
export QUERY_CACHE_TTL=0
```

---

### GraphRAG Query Modes

Once enabled, you can query using graph-based retrieval:

```bash
# Graph-only retrieval (entity relationships)
agent-brain query "class relationships" --mode graph

# Multi-mode fusion (vector + BM25 + graph with RRF)
agent-brain query "how do services work" --mode multi
```

### Store Type Comparison

| Store | Persistence | Performance | Use Case |
|-------|-------------|-------------|----------|
| `simple` | In-memory only | Fast, no disk I/O | Development, small projects |
| `kuzu` | Persistent to disk | Graph-optimized queries | Production, large codebases |

**Note**: Kuzu requires the optional `graphrag-kuzu` dependency:
```bash
poetry install --extras graphrag-kuzu
```

### Troubleshooting GraphRAG

**GraphRAG disabled error**:
```bash
# Check if enabled
echo $ENABLE_GRAPH_INDEX

# Enable it
export ENABLE_GRAPH_INDEX=true
agent-brain stop && agent-brain start
```

**No graph results**:
```bash
# Verify graph index was built
agent-brain status --json | jq '.graph_index'

# Re-index with graph enabled
agent-brain reset --yes
agent-brain index /path/to/docs
```

---

## Profile Examples

### Fully Local (Ollama - No API Keys)

```yaml
# ~/.agent-brain/config.yaml
embedding:
  provider: "ollama"
  model: "nomic-embed-text"
  base_url: "http://localhost:11434/v1"

summarization:
  provider: "ollama"
  model: "llama3.2"
  base_url: "http://localhost:11434/v1"
```

### Cloud (Best Quality)

```yaml
# ~/.agent-brain/config.yaml
embedding:
  provider: "openai"
  model: "text-embedding-3-large"
  api_key: "sk-proj-..."

summarization:
  provider: "anthropic"
  model: "claude-haiku-4-5-20251001"
  api_key: "sk-ant-..."
```

### Custom State Directory

```yaml
# ~/.agent-brain/config.yaml
project:
  state_dir: "/data/agent-brain/my-project"

embedding:
  provider: "openai"
  api_key_env: "OPENAI_API_KEY"
```

### GraphRAG Enabled (Code Search)

```yaml
# ~/.agent-brain/config.yaml
embedding:
  provider: "openai"
  model: "text-embedding-3-large"
  api_key_env: "OPENAI_API_KEY"

summarization:
  provider: "anthropic"
  model: "claude-haiku-4-5-20251001"
  api_key_env: "ANTHROPIC_API_KEY"

graphrag:
  enabled: true
  store_type: "kuzu"  # Persistent for large codebases
  use_code_metadata: true  # Extract imports, classes from AST
  use_llm_extraction: true  # Extract semantic relationships
  traversal_depth: 2
```

---

## Security Best Practices

### Config File Permissions

If storing API keys in config files:

```bash
# Restrict to owner only
chmod 600 ~/.agent-brain/config.yaml
```

### Git Ignore

Add to `.gitignore`:
```
config.yaml
agent-brain.yaml
.env
.env.local
```

### Key Rotation

Regenerate API keys periodically and update configurations.

---

## Troubleshooting

### Config File Not Loading

```bash
# Check config file exists
ls -la ~/.agent-brain/config.yaml

# Verify YAML syntax
python -c "import yaml; yaml.safe_load(open('config.yaml'))"

# Force specific config
export AGENT_BRAIN_CONFIG="$HOME/.agent-brain/config.yaml"
```

### API Key Not Working

```bash
# Test OpenAI key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Check if key is in config or env
cat ~/.agent-brain/config.yaml | grep api_key
echo ${OPENAI_API_KEY:+SET}
```

### Wrong Server URL

```bash
# Check runtime.json for actual port
cat .agent-brain/runtime.json

# Override URL
export AGENT_BRAIN_URL="http://127.0.0.1:49321"
```

---

## File Watcher Configuration (v8.0+)

The file watcher enables automatic re-indexing when files change in watched folders.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_BRAIN_WATCH_DEBOUNCE_SECONDS` | `30` | Debounce interval for file change events |

### Folder Watch Setup

```bash
# Enable file watching on a folder
agent-brain folders add ./src --watch auto --include-code

# Custom debounce (10 seconds)
agent-brain folders add ./src --watch auto --debounce 10

# Disable watching
agent-brain folders add ./docs --watch off
```

### Behavior

- Changes are debounced per-folder (default 30 seconds)
- Watcher-triggered jobs use incremental diff (only changed files re-processed)
- Excluded directories: `.git/`, `node_modules/`, `__pycache__/`, `dist/`, `build/`
- Jobs show `source: auto` in the queue

---

## Embedding Cache Configuration (v8.0+)

The embedding cache reduces API costs by caching computed embeddings locally.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_CACHE_MAX_DISK_MB` | `500` | Maximum disk cache size in MB |
| `EMBEDDING_CACHE_MAX_MEM_ENTRIES` | `1000` | In-memory LRU cache size |
| `EMBEDDING_CACHE_PERSIST_STATS` | `false` | Persist hit/miss stats across restarts |

### CLI Commands

```bash
# View cache statistics
agent-brain cache status

# View as JSON
agent-brain cache status --json

# Clear all cached embeddings
agent-brain cache clear --yes
```

### Behavior

- Two-tier: in-memory LRU + SQLite disk cache
- Identical content returns cached embedding (no API call)
- Cache is invalidated per-chunk when content changes
- Healthy cache shows >80% hit rate after first full index

---

## Reranking Configuration (v8.0+)

Two-stage retrieval with reranking for higher precision results.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_RERANKING` | `false` | Enable/disable reranking |
| `RERANKER_PROVIDER` | `sentence-transformers` | Reranker backend (`sentence-transformers` or `ollama`) |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder model |
| `RERANKER_TOP_K_MULTIPLIER` | `10` | Fetch top_k * N candidates in Stage 1 |
| `RERANKER_MAX_CANDIDATES` | `100` | Cap on Stage 1 candidates |

### YAML Configuration

```yaml
reranking:
  enabled: true
  provider: "sentence-transformers"
  model: "cross-encoder/ms-marco-MiniLM-L-6-v2"
  top_k_multiplier: 10
  max_candidates: 100
```

---

## Folder Management Configuration (v7.0+)

### CLI Commands

```bash
# Add folder to index
agent-brain folders add ./docs

# Add with code file support
agent-brain folders add ./src --include-code

# List indexed folders
agent-brain folders list

# Remove folder and its chunks
agent-brain folders remove ./docs --yes
```

---

## File Type Presets (v7.0+)

```bash
# List available file type presets
agent-brain types list

# Index with specific file type preset
agent-brain index ./src --include-type python
agent-brain index ./src --include-type typescript
```

---

## Content Injection (v7.0+)

Content injection allows enriching documents during indexing with custom scripts.

```bash
# Index with content injection script
agent-brain inject --script enrich.py ./docs
```

---

## Multi-Runtime Install (v9.0+)

Install the Agent Brain plugin into different AI coding assistant runtimes:

```bash
agent-brain install-agent --agent claude     # Claude Code
agent-brain install-agent --agent opencode   # OpenCode
agent-brain install-agent --agent gemini     # Gemini
agent-brain install-agent --agent codex      # Codex
agent-brain install-agent --agent skill-runtime --dir /path  # Generic
```

---

## Next Steps

After configuration:
1. Initialize project: `/agent-brain:agent-brain-init`
2. Start server: `/agent-brain:agent-brain-start`
3. Index documents: `/agent-brain:agent-brain-index /path/to/docs`
4. Search: `/agent-brain:agent-brain-search "your search"`
