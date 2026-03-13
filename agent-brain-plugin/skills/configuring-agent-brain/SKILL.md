---
name: configuring-agent-brain
description: |
  Installation and configuration skill for Agent Brain document search system.
  Use when asked to "install agent brain", "setup agent brain", "configure agent brain",
  "setting up document search", "installing agent-brain packages", "configuring API keys",
  "initializing project for search", "troubleshooting agent brain", "pip install agent-brain",
  "agent brain not working", "agent brain setup error", "configure embeddings provider",
  "setup ollama for agent brain", or "agent brain environment variables".
  Covers package installation, provider configuration, project initialization, and server management.
license: MIT
allowed-tools:
  - Bash
  - Read
metadata:
  version: 7.0.0
  category: ai-tools
  author: Spillwave
---

# Configuring Agent Brain

Installation and configuration for Agent Brain document search with pluggable providers.

## Contents

- [Quick Setup](#quick-setup)
- [Setup Wizard](#setup-wizard)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Provider Configuration](#provider-configuration)
- [Project Initialization](#project-initialization)
- [Verification](#verification)
- [When Not to Use](#when-not-to-use)
- [Reference Documentation](#reference-documentation)

---

## Quick Setup

### Option A: Local with Ollama (FREE, No API Keys)

```bash
# 1. Install packages
pip install agent-brain-rag agent-brain-cli

# 2. Install and start Ollama
brew install ollama  # macOS
ollama serve &
ollama pull nomic-embed-text
ollama pull llama3.2

# 3. Configure for Ollama
export EMBEDDING_PROVIDER=ollama
export EMBEDDING_MODEL=nomic-embed-text
export SUMMARIZATION_PROVIDER=ollama
export SUMMARIZATION_MODEL=llama3.2

# 4. Initialize and start
agent-brain init
agent-brain start
agent-brain status
```

### Option B: Cloud Providers (Best Quality)

```bash
# 1. Install packages
pip install agent-brain-rag agent-brain-cli

# 2. Configure API keys
export OPENAI_API_KEY="sk-proj-..."       # For embeddings
export ANTHROPIC_API_KEY="sk-ant-..."     # For summarization (optional)

# 3. Initialize and start
agent-brain init
agent-brain start
agent-brain status
```

**Validation**: After each step, verify success before proceeding to the next.

---

## Setup Wizard

The canonical entry point for a complete guided setup is `/agent-brain-setup`. It asks all configuration questions interactively before running any CLI commands, then writes a comprehensive `config.yaml`.

### Wizard Configuration Questions

The wizard asks the following questions in sequence:

| Step | Question | Config Keys Set |
|------|----------|----------------|
| 2 | Embedding Provider | `embedding.provider`, `embedding.model`, optionally `embedding.base_url`, `embedding.api_key` or `embedding.api_key_env` |
| 3 | Summarization Provider | `summarization.provider`, `summarization.model`, optionally `summarization.base_url`, `summarization.api_key` or `summarization.api_key_env` |
| 4 | Storage Backend | `storage.backend` (`chroma` or `postgres`) |
| 5 | GraphRAG | `graphrag.enabled`, `graphrag.store_type`, `graphrag.use_code_metadata` |
| 6 | Default Query Mode | Written as YAML comment: `# query.default_mode` |

### Embedding Provider Options

| Option | Provider Key | Model | Notes |
|--------|-------------|-------|-------|
| Ollama (FREE, local) | `ollama` | `nomic-embed-text` | Requires Ollama running locally |
| OpenAI | `openai` | `text-embedding-3-large` | Requires `OPENAI_API_KEY` |
| Cohere | `cohere` | `embed-multilingual-v3.0` | Requires `COHERE_API_KEY`, multi-language support |
| Google Gemini | `gemini` | `text-embedding-004` | Requires `GOOGLE_API_KEY` |
| Custom | (user-specified) | (user-specified) | Specify provider, model, and base_url |

### Summarization Provider Options

| Option | Provider Key | Model | Notes |
|--------|-------------|-------|-------|
| Ollama (FREE, local) | `ollama` | `llama3.2` | Requires Ollama running locally |
| Ollama + Mistral (FREE, local) | `ollama` | `mistral-small3.2` | Better summarization quality |
| Anthropic | `anthropic` | `claude-haiku-4-5-20251001` | Requires `ANTHROPIC_API_KEY` |
| OpenAI | `openai` | `gpt-4o-mini` | Requires `OPENAI_API_KEY` |
| Google Gemini | `gemini` | `gemini-2.0-flash` | Requires `GOOGLE_API_KEY` |
| Grok (xAI) | `grok` | `grok-3-mini-fast` | Requires `XAI_API_KEY` |

### Config.yaml Written by Wizard

After answering all questions, the wizard writes a comprehensive `config.yaml` covering:
- `embedding.*` — provider, model, api_key or api_key_env, optional base_url
- `summarization.*` — provider, model, api_key or api_key_env, optional base_url
- `storage.*` — backend selection and (if PostgreSQL) connection settings
- `graphrag.*` — enabled flag, store_type, use_code_metadata
- `# query.default_mode` as a YAML comment (informational)

The file is chmod 600 automatically. A security warning is shown: never commit config.yaml to git.

### Standalone Config Command

`/agent-brain-config` handles provider-specific details when called standalone (without the full wizard). It includes storage backend selection, indexing exclude patterns, and Ollama status checks.

---

## Prerequisites

### Required
- **Python 3.10+**: Verify with `python --version`
- **pip**: Python package manager

### Provider-Dependent
- **OpenAI API Key**: Required for OpenAI embeddings
- **Ollama**: Required for local/private deployments (no API key needed)

### System Requirements
- ~500MB RAM for typical document collections
- ~1GB RAM with GraphRAG enabled
- Disk space for ChromaDB vector store

---

## Installation

### Standard Installation

```bash
pip install agent-brain-rag agent-brain-cli
```

**Verify installation succeeded**:
```bash
agent-brain --version
```

Expected: Version number displayed (e.g., `3.0.0` or current version)

### With GraphRAG Support

```bash
pip install "agent-brain-rag[graphrag]" agent-brain-cli
# Kuzu backend (optional):
pip install "agent-brain-rag[graphrag-kuzu]" agent-brain-cli
```

### Enable GraphRAG (server)

```bash
export ENABLE_GRAPH_INDEX=true            # Master switch (default: false)
export GRAPH_STORE_TYPE=simple            # or kuzu
export GRAPH_INDEX_PATH=./graph_index
export GRAPH_USE_CODE_METADATA=true       # Extract from AST metadata
export GRAPH_USE_LLM_EXTRACTION=true      # Use LLM extractor when available
export GRAPH_MAX_TRIPLETS_PER_CHUNK=10    # Triplet cap per chunk
export GRAPH_TRAVERSAL_DEPTH=2            # Default traversal depth
export GRAPH_EXTRACTION_MODEL=claude-haiku-4-5
```

Add the same values to your `.env` if you prefer file-based config.

### Virtual Environment (Recommended)

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
pip install agent-brain-rag agent-brain-cli
```

### Installation Troubleshooting

| Problem | Solution |
|---------|----------|
| `pip not found` | Run `python -m ensurepip` |
| Permission denied | Use `pip install --user` or virtual env |
| Module not found after install | Restart terminal or activate venv |
| Wrong Python version | Use `python3.10 -m pip install` |

**Counter-example - Wrong approach**:
```bash
# DO NOT use sudo with pip
sudo pip install agent-brain-rag  # Wrong - creates permission issues
```

**Correct approach**:
```bash
pip install --user agent-brain-rag  # Correct - user installation
# OR use virtual environment
```

---

## Provider Configuration

Agent Brain supports pluggable providers with two configuration methods.

### Method 1: Configuration File (Recommended)

Create a `config.yaml` file in one of these locations:

1. **Project-level**: `.claude/agent-brain/config.yaml`
2. **User-level**: `~/.agent-brain/config.yaml`
3. **XDG config**: `~/.config/agent-brain/config.yaml`
4. **Current directory**: `./config.yaml` or `./agent-brain.yaml`

```yaml
# ~/.agent-brain/config.yaml
server:
  url: "http://127.0.0.1:8000"
  port: 8000

project:
  state_dir: null  # null = use default (.claude/agent-brain)

embedding:
  provider: "openai"
  model: "text-embedding-3-large"
  api_key: "sk-proj-..."  # Direct key, OR use api_key_env
  # api_key_env: "OPENAI_API_KEY"  # Read from env var

summarization:
  provider: "anthropic"
  model: "claude-haiku-4-5-20251001"
  api_key: "sk-ant-..."  # Direct key, OR use api_key_env
  # api_key_env: "ANTHROPIC_API_KEY"
```

**Config file search order**: AGENT_BRAIN_CONFIG env → current dir → project dir → user home

**Security**: If storing API keys in config file:
- Set file permissions: `chmod 600 ~/.agent-brain/config.yaml`
- Add to `.gitignore`: `config.yaml`
- Never commit API keys to version control

### Method 2: Environment Variables

Set variables in shell or `.env` file:

```bash
export EMBEDDING_PROVIDER=openai
export EMBEDDING_MODEL=text-embedding-3-large
export SUMMARIZATION_PROVIDER=anthropic
export SUMMARIZATION_MODEL=claude-haiku-4-5-20251001
export OPENAI_API_KEY="sk-proj-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Precedence order**: CLI options → environment variables → config file → defaults

---

### Provider Profiles

#### Fully Local with Ollama (No API Keys)

Best for privacy, air-gapped environments:

**Config file** (`~/.agent-brain/config.yaml`):
```yaml
embedding:
  provider: "ollama"
  model: "nomic-embed-text"
  base_url: "http://localhost:11434/v1"

summarization:
  provider: "ollama"
  model: "llama3.2"
  base_url: "http://localhost:11434/v1"
```

**Or environment variables**:
```bash
export EMBEDDING_PROVIDER=ollama
export EMBEDDING_MODEL=nomic-embed-text
export SUMMARIZATION_PROVIDER=ollama
export SUMMARIZATION_MODEL=llama3.2
```

**Prerequisite**: Ollama must be installed and running with models pulled.

#### Cloud (Best Quality)

**Config file**:
```yaml
embedding:
  provider: "openai"
  model: "text-embedding-3-large"
  api_key: "sk-proj-..."

summarization:
  provider: "anthropic"
  model: "claude-haiku-4-5-20251001"
  api_key: "sk-ant-..."
```

**Or environment variables**:
```bash
export OPENAI_API_KEY="sk-proj-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

#### Mixed (Balance Quality and Privacy)

```yaml
embedding:
  provider: "openai"
  model: "text-embedding-3-large"
  api_key: "sk-proj-..."

summarization:
  provider: "ollama"
  model: "llama3.2"
```

### GraphRAG Configuration

GraphRAG enables graph-based entity-relationship extraction for advanced query modes.

**YAML config keys** (`config.yaml`):

```yaml
graphrag:
  enabled: false          # Master switch (default: false)
  store_type: "simple"    # "simple" (in-memory) or "kuzu" (persistent disk)
  use_code_metadata: true # Extract entities from AST metadata (imports, classes)
```

**Corresponding environment variables**:

| Env Var | Config Key | Default | Description |
|---------|-----------|---------|-------------|
| `ENABLE_GRAPH_INDEX` | `graphrag.enabled` | `false` | Master switch |
| `GRAPH_STORE_TYPE` | `graphrag.store_type` | `simple` | `simple` or `kuzu` |
| `GRAPH_USE_CODE_METADATA` | `graphrag.use_code_metadata` | `true` | AST metadata extraction |

**Note**: GraphRAG requires the `--include-code` flag during indexing to extract code structure:

```bash
agent-brain index ./src --include-code
```

For Kuzu (persistent), install the optional extra first:

```bash
pip install "agent-brain-rag[graphrag-kuzu]"
```

### Query Mode Selection

Agent Brain supports the following query modes, selectable per request with `--mode`:

| Mode | Description | Requires GraphRAG |
|------|-------------|------------------|
| `hybrid` | Vector similarity + BM25 keyword (recommended default) | No |
| `semantic` | Pure vector similarity search | No |
| `bm25` | Keyword-only search (fast, no embedding needed) | No |
| `graph` | Entity relationship graph traversal | Yes |
| `multi` | Fuses vector + BM25 + graph with RRF | Yes |

**Per-request override**:

```bash
agent-brain query "authentication flow" --mode hybrid
agent-brain query "class relationships" --mode graph    # GraphRAG required
agent-brain query "how do services work" --mode multi   # GraphRAG required
```

**Note**: There is no global `query.default_mode` config key yet. Mode is per-request only. The setup wizard writes the selected default mode as a YAML comment for documentation purposes.

### Verify Configuration

```bash
agent-brain verify
```

**Counter-example - Common mistake**:
```bash
# DO NOT put keys in shell command history
OPENAI_API_KEY="sk-proj-abc123" agent-brain start  # Wrong - key in history
```

**Correct approaches**:
```bash
# Use config file (keys are in file, not command line)
agent-brain start

# Or use environment from shell profile
export OPENAI_API_KEY="sk-proj-..."  # In ~/.bashrc
agent-brain start
```

---

## Project Initialization

### Initialize Project

Navigate to the project root and run:

```bash
agent-brain init
```

**Verify initialization succeeded**:
```bash
ls .claude/agent-brain/config.json
```

Expected: File exists

### Start Server

```bash
agent-brain start
```

**Verify server started**:
```bash
agent-brain status
```

Expected output:
```
Server Status: healthy
Port: 49321
Documents: 0
Mode: project
```

### Index Documents

```bash
agent-brain index ./docs
```

**Verify indexing succeeded**:
```bash
agent-brain status
```

Expected: Documents count > 0

### Test Search

```bash
agent-brain query "test query" --mode hybrid
```

Expected: Search results or "No results" (not an error)

---

## Verification

### Full Verification Checklist

Run each command and verify expected output:

- [ ] `agent-brain --version` shows version number (7.0.0+)
- [ ] `echo ${OPENAI_API_KEY:+SET}` shows "SET" (if using OpenAI)
- [ ] `ls .claude/agent-brain/config.json` file exists
- [ ] `agent-brain status` shows "healthy"
- [ ] `agent-brain status` shows document count > 0
- [ ] `agent-brain query "test"` returns results or "no matches"
- [ ] `agent-brain folders list` shows indexed folders
- [ ] `agent-brain types list` shows file type presets
- [ ] `agent-brain jobs` shows job queue (empty or with history)

### GraphRAG Verification (if enabled)

- [ ] `echo ${ENABLE_GRAPH_INDEX}` shows "true"
- [ ] `agent-brain status --json | jq '.graph_index'` shows graph index info
- [ ] `agent-brain query "class relationships" --mode graph` returns results or graceful error
- [ ] `agent-brain query "how it works" --mode multi` returns fused results

### Automated Verification

```bash
agent-brain verify
```

This runs all checks and reports any issues.

### Post-Indexing Verification

After indexing documents, verify the pipeline is working:

```bash
# Monitor indexing job
agent-brain jobs --watch

# Check job completed successfully
agent-brain jobs <job_id>

# Verify incremental indexing works
agent-brain index ./docs  # Should show eviction summary with unchanged files

# Validate injection scripts before use
agent-brain inject ./docs --script enrich.py --dry-run
```

---

## When Not to Use

This skill focuses on **installation and configuration**. Do NOT use for:

- **Searching documents** - Use `using-agent-brain` skill instead
- **Query optimization** - Use `using-agent-brain` skill instead
- **Understanding search modes** - Use `using-agent-brain` skill instead
- **GraphRAG queries** - Use `using-agent-brain` skill instead

**Scope boundary**: Once Agent Brain is installed, configured, initialized, and verified healthy, switch to the `using-agent-brain` skill for search operations.

---

## Common Setup Issues

### Issue: Module Not Found

```bash
pip install --force-reinstall agent-brain-rag agent-brain-cli
```

### Issue: API Key Not Working

```bash
# Test OpenAI key
curl -s https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | head -c 100
```

Expected: JSON response (not error)

### Issue: Server Won't Start

```bash
# Check for stale state
rm -f .claude/agent-brain/runtime.json
rm -f .claude/agent-brain/lock.json
agent-brain start
```

### Issue: Ollama Connection Failed

```bash
# Verify Ollama is running
curl http://localhost:11434/api/tags
```

Expected: JSON with model list

### Issue: No Search Results

```bash
agent-brain status  # Check document count
```

If count is 0, index documents:
```bash
agent-brain index ./docs
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AGENT_BRAIN_CONFIG` | No | - | Path to config.yaml file |
| `AGENT_BRAIN_URL` | No | `http://127.0.0.1:8000` | Server URL for CLI |
| `AGENT_BRAIN_STATE_DIR` | No | `.claude/agent-brain` | State directory path |
| `EMBEDDING_PROVIDER` | No | `openai` | Provider: openai, cohere, ollama |
| `EMBEDDING_MODEL` | No | `text-embedding-3-large` | Model name |
| `SUMMARIZATION_PROVIDER` | No | `anthropic` | Provider: anthropic, openai, gemini, grok, ollama |
| `SUMMARIZATION_MODEL` | No | `claude-haiku-4-5-20251001` | Model name |
| `OPENAI_API_KEY` | Conditional | - | Required if using OpenAI |
| `ANTHROPIC_API_KEY` | Conditional | - | Required if using Anthropic |
| `GOOGLE_API_KEY` | Conditional | - | Required if using Gemini |
| `XAI_API_KEY` | Conditional | - | Required if using Grok |
| `COHERE_API_KEY` | Conditional | - | Required if using Cohere |
| `EMBEDDING_CACHE_MAX_MEM_ENTRIES` | No | 1000 | Max in-memory LRU entries (~12 MB at 3072 dims per 1000 entries) |
| `EMBEDDING_CACHE_MAX_DISK_MB` | No | 500 | Max disk size for the SQLite embedding cache |

**Note**: Environment variables override config file values. Config file values override defaults.

### Embedding Cache Tuning

The embedding cache is **automatic** — no setup required. Embeddings are cached on first compute
and reused on subsequent reindexes of unchanged content, significantly reducing OpenAI API costs
when using file watching or frequent reindexing.

The two cache env vars allow tuning for specific environments:
- **Large indexes** — increase `EMBEDDING_CACHE_MAX_MEM_ENTRIES` (e.g., 5000) to keep more embeddings
  in the fast in-memory tier and reduce SQLite lookups
- **Memory-constrained environments** — decrease `EMBEDDING_CACHE_MAX_MEM_ENTRIES` (e.g., 200) to
  limit RAM usage; the disk cache still provides cost savings even with a small memory tier
- **Disk space constrained** — decrease `EMBEDDING_CACHE_MAX_DISK_MB` (e.g., 100) to cap the SQLite
  cache database size; oldest entries are evicted when the limit is reached

The disk cache uses SQLite with WAL mode for safe concurrent access during indexing operations.

---

## Reference Documentation

| Guide | Description |
|-------|-------------|
| [Configuration Guide](references/configuration-guide.md) | Config file format and locations |
| [Installation Guide](references/installation-guide.md) | Detailed installation options |
| [Provider Configuration](references/provider-configuration.md) | All provider settings |
| [Troubleshooting Guide](references/troubleshooting-guide.md) | Extended issue resolution |

---

## Support

- Issues: https://github.com/SpillwaveSolutions/agent-brain-plugin/issues
- Documentation: Reference guides in this skill
