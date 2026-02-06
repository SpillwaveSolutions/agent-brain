# Agent Brain Configuration Guide

## Overview

Agent Brain supports multiple configuration methods with clear precedence rules. This guide covers all configuration options.

## Configuration Methods

### Method 1: YAML Configuration File (Recommended)

The config.yaml file provides a centralized configuration without needing to modify shell profiles.

**Search locations** (in order):

1. `AGENT_BRAIN_CONFIG` environment variable (explicit path)
2. Current directory: `./agent-brain.yaml` or `./config.yaml`
3. Project directory: `./.claude/agent-brain/config.yaml`
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
  state_dir: null  # null = use default (.claude/agent-brain)
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
```

### Method 2: Environment Variables

Traditional approach using shell environment:

```bash
# Core settings
export AGENT_BRAIN_URL="http://127.0.0.1:8000"
export AGENT_BRAIN_STATE_DIR=".claude/agent-brain"
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

Create `.claude/agent-brain/.env` or project root `.env`:

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
| `AGENT_BRAIN_STATE_DIR` | No | `.claude/agent-brain` | State directory path |
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
export GRAPH_INDEX_PATH=".claude/agent-brain/graph_index"

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
cat .claude/agent-brain/runtime.json

# Override URL
export AGENT_BRAIN_URL="http://127.0.0.1:49321"
```

---

## Next Steps

After configuration:
1. Initialize project: `agent-brain init`
2. Start server: `agent-brain start`
3. Index documents: `agent-brain index /path/to/docs`
4. Search: `agent-brain query "your search"`
