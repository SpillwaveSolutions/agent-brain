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
  version: 2.0.0
  category: ai-tools
  author: Spillwave
---

# Configuring Agent Brain

Installation and configuration for Agent Brain document search with pluggable providers.

## Contents

- [Quick Setup](#quick-setup)
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
agent-brain start --daemon
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
agent-brain start --daemon
agent-brain status
```

**Validation**: After each step, verify success before proceeding to the next.

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

Expected: Version number displayed (e.g., `2.0.0`)

### With GraphRAG Support

```bash
pip install "agent-brain-rag[graphrag]" agent-brain-cli
```

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

Agent Brain 2.0 supports pluggable providers. Choose based on requirements:

### Fully Local (No API Keys)

Best for privacy, air-gapped environments:

```bash
export EMBEDDING_PROVIDER=ollama
export EMBEDDING_MODEL=nomic-embed-text
export SUMMARIZATION_PROVIDER=ollama
export SUMMARIZATION_MODEL=llama4:scout
export OLLAMA_BASE_URL=http://localhost:11434
```

**Prerequisite**: Ollama must be installed and running with models pulled.

### Cloud (Best Quality)

```bash
export EMBEDDING_PROVIDER=openai
export EMBEDDING_MODEL=text-embedding-3-large
export SUMMARIZATION_PROVIDER=anthropic
export SUMMARIZATION_MODEL=claude-haiku-4-5-20251001
export OPENAI_API_KEY="sk-proj-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Mixed (Balance Quality and Privacy)

```bash
export EMBEDDING_PROVIDER=openai
export EMBEDDING_MODEL=text-embedding-3-large
export SUMMARIZATION_PROVIDER=ollama
export SUMMARIZATION_MODEL=llama4:scout
export OPENAI_API_KEY="sk-proj-..."
```

### Verify Configuration

```bash
echo "Embedding: ${EMBEDDING_PROVIDER:-openai}"
echo "Summarization: ${SUMMARIZATION_PROVIDER:-anthropic}"
echo "OpenAI Key: ${OPENAI_API_KEY:+SET}"
```

**Counter-example - Common mistake**:
```bash
# DO NOT put keys in code or commit to git
OPENAI_API_KEY="sk-proj-abc123" agent-brain start  # Wrong - key in history
```

**Correct approach**:
```bash
export OPENAI_API_KEY="sk-proj-..."  # Set in environment
agent-brain start --daemon            # Use from environment
```

### Persistent Configuration

Add to shell profile (`~/.bashrc` or `~/.zshrc`):

```bash
# Agent Brain Configuration
export EMBEDDING_PROVIDER=openai
export OPENAI_API_KEY="sk-proj-..."
```

Then reload: `source ~/.bashrc`

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
agent-brain start --daemon
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

- [ ] `agent-brain --version` shows version number
- [ ] `echo ${OPENAI_API_KEY:+SET}` shows "SET" (if using OpenAI)
- [ ] `ls .claude/agent-brain/config.json` file exists
- [ ] `agent-brain status` shows "healthy"
- [ ] `agent-brain status` shows document count > 0
- [ ] `agent-brain query "test"` returns results or "no matches"

### Automated Verification

```bash
agent-brain verify
```

This runs all checks and reports any issues.

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
agent-brain start --daemon
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
| `EMBEDDING_PROVIDER` | No | `openai` | Provider: openai, cohere, ollama |
| `EMBEDDING_MODEL` | No | `text-embedding-3-large` | Model name |
| `SUMMARIZATION_PROVIDER` | No | `anthropic` | Provider: anthropic, openai, gemini, grok, ollama |
| `SUMMARIZATION_MODEL` | No | `claude-haiku-4-5-20251001` | Model name |
| `OPENAI_API_KEY` | Conditional | - | Required if using OpenAI |
| `ANTHROPIC_API_KEY` | Conditional | - | Required if using Anthropic |
| `OLLAMA_BASE_URL` | Conditional | `http://localhost:11434` | Ollama server URL |
| `DOC_SERVE_STATE_DIR` | No | `.claude/agent-brain` | State directory |

---

## Reference Documentation

| Guide | Description |
|-------|-------------|
| [Installation Guide](references/installation-guide.md) | Detailed installation options |
| [Provider Configuration](references/provider-configuration.md) | All provider settings |
| [Troubleshooting Guide](references/troubleshooting-guide.md) | Extended issue resolution |

---

## Support

- Issues: https://github.com/SpillwaveSolutions/agent-brain-plugin/issues
- Documentation: Reference guides in this skill
