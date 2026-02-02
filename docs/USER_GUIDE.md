# Agent Brain User Guide

This guide covers how to use Agent Brain for document indexing and semantic search using the Claude Code plugin.

## Table of Contents

- [Overview](#overview)
- [Plugin Commands](#plugin-commands)
- [Plugin Agents](#plugin-agents)
- [Search Modes](#search-modes)
- [Indexing](#indexing)
- [Provider Configuration](#provider-configuration)
- [Multi-Project Support](#multi-project-support)
- [CLI Reference](#cli-reference)
- [Troubleshooting](#troubleshooting)

---

## Overview

Agent Brain is a RAG (Retrieval-Augmented Generation) system that indexes and searches documentation and source code. The primary interface is the **Claude Code plugin** which provides:

| Component | Count | Description |
|-----------|-------|-------------|
| **Commands** | 24 | Slash commands for all operations |
| **Agents** | 3 | Intelligent assistants for complex tasks |
| **Skills** | 2 | Context for optimal search and configuration |

### How It Works

1. **Indexing**: Reads documents/code, splits into semantic chunks, generates embeddings
2. **Storage**: Stores chunks in ChromaDB with metadata for filtering
3. **Retrieval**: Finds similar chunks using hybrid search (semantic + keyword)
4. **GraphRAG**: Extracts entities and relationships for dependency queries

---

## Plugin Commands

### Search Commands

| Command | Description | Best For |
|---------|-------------|----------|
| `/agent-brain-search` | Smart hybrid search | General questions |
| `/agent-brain-semantic` | Pure vector search | Conceptual queries |
| `/agent-brain-keyword` | BM25 keyword search | Exact terms, function names |
| `/agent-brain-bm25` | Alias for keyword search | Error messages, symbols |
| `/agent-brain-vector` | Alias for semantic search | "How does X work?" |
| `/agent-brain-hybrid` | Hybrid with alpha control | Fine-tuned searches |
| `/agent-brain-graph` | Knowledge graph search | Dependencies, relationships |
| `/agent-brain-multi` | All modes with RRF fusion | Maximum recall |

### Server Commands

| Command | Description |
|---------|-------------|
| `/agent-brain-start` | Start server (auto-port allocation) |
| `/agent-brain-stop` | Stop the running server |
| `/agent-brain-status` | Check health and document count |
| `/agent-brain-list` | List all running instances |
| `/agent-brain-index` | Index documents or code |
| `/agent-brain-reset` | Clear the index |

### Setup Commands

| Command | Description |
|---------|-------------|
| `/agent-brain-setup` | Complete guided setup wizard |
| `/agent-brain-install` | Install pip packages |
| `/agent-brain-init` | Initialize project directory |
| `/agent-brain-config` | View/edit configuration |
| `/agent-brain-verify` | Verify configuration |
| `/agent-brain-help` | Show help information |
| `/agent-brain-version` | Show version information |

### Provider Commands

| Command | Description |
|---------|-------------|
| `/agent-brain-providers` | List and configure providers |
| `/agent-brain-embeddings` | Configure embedding provider |
| `/agent-brain-summarizer` | Configure summarization provider |

---

## Plugin Agents

Agent Brain includes three intelligent agents that handle complex, multi-step tasks:

### Search Assistant

Performs multi-step searches across different modes and synthesizes answers.

**Triggers**: "Find all references to...", "Search for...", "What files contain..."

**Example**:
```
You: "Find all references to the authentication module"

Search Assistant:
1. Searches documentation for auth concepts
2. Searches code for auth imports and usage
3. Uses graph mode to find dependencies
4. Returns comprehensive list with file locations
```

### Research Assistant

Deep exploration with follow-up queries and cross-referencing.

**Triggers**: "Research how...", "Investigate...", "Analyze the architecture of..."

**Example**:
```
You: "Research how error handling is implemented"

Research Assistant:
1. Identifies error handling patterns in docs
2. Finds exception classes and try/catch blocks
3. Traces error propagation through call graph
4. Synthesizes findings with code references
```

### Setup Assistant

Guided installation, configuration, and troubleshooting.

**Triggers**: "Help me set up Agent Brain", "Configure...", "Why isn't... working"

**Example**:
```
You: "Help me set up Agent Brain with Ollama"

Setup Assistant:
1. Checks if Ollama is installed
2. Verifies embedding model is pulled
3. Configures provider settings
4. Tests the configuration
5. Reports success or guides through fixes
```

---

## Search Modes

### HYBRID (Default)

Combines semantic similarity with keyword matching. Best for general questions.

```
/agent-brain-search "how does the caching system work"
```

Adjust the balance with `--alpha`:
- `--alpha 0.7` - More semantic (conceptual queries)
- `--alpha 0.3` - More keyword (specific terms)

```
/agent-brain-hybrid "authentication flow" --alpha 0.7
```

### VECTOR (Semantic)

Pure embedding-based search. Best for conceptual understanding.

```
/agent-brain-semantic "explain the overall architecture"
```

### BM25 (Keyword)

TF-IDF based search. Best for exact terms, function names, error codes.

```
/agent-brain-keyword "NullPointerException"
/agent-brain-bm25 "getUserById"
```

### GRAPH (Knowledge Graph)

Traverses entity relationships. Best for dependency and relationship queries.

```
/agent-brain-graph "what classes use AuthService"
/agent-brain-graph "what calls the validate function"
```

### MULTI (Fusion)

Combines all modes using Reciprocal Rank Fusion. Best for maximum recall.

```
/agent-brain-multi "everything about data validation"
```

---

## Indexing

### Index Documentation

```
/agent-brain-index ./docs
```

### Index Code and Documentation

```
/agent-brain-index . --include-code
```

### Index Specific Languages

```
/agent-brain-index ./src --include-code --languages python,typescript
```

### Generate Code Summaries

Improves semantic search for code by generating LLM descriptions:

```
/agent-brain-index ./src --include-code --generate-summaries
```

### Supported Languages

Agent Brain supports AST-aware chunking for:
- **Python** (.py)
- **TypeScript** (.ts, .tsx)
- **JavaScript** (.js, .jsx)
- **Java** (.java)
- **Go** (.go)
- **Rust** (.rs)
- **C** (.c, .h)
- **C++** (.cpp, .hpp, .cc)
- **C#** (.cs, .csx)
- **Swift** (.swift)

Other languages use intelligent text-based chunking.

### Check Index Status

```
/agent-brain-status
```

### Clear and Rebuild Index

```
/agent-brain-reset
/agent-brain-index . --include-code
```

---

## Provider Configuration

Agent Brain supports pluggable providers for embeddings and summarization.

### Configure Providers Interactively

```
/agent-brain-providers
```

### Embedding Providers

| Provider | Models | Local |
|----------|--------|-------|
| OpenAI | text-embedding-3-large, text-embedding-3-small | No |
| Ollama | nomic-embed-text, mxbai-embed-large | Yes |
| Cohere | embed-english-v3.0, embed-multilingual-v3.0 | No |

### Summarization Providers

| Provider | Models | Local |
|----------|--------|-------|
| Anthropic | claude-haiku-4-5-20251001, claude-sonnet-4-5-20250514 | No |
| OpenAI | gpt-5, gpt-5-mini | No |
| Gemini | gemini-3-flash, gemini-3-pro | No |
| Grok | grok-4, grok-4-fast | No |
| Ollama | llama4:scout, mistral-small3.2, qwen3-coder | Yes |

### Fully Local Mode

Run completely offline with Ollama:

```
/agent-brain-providers
# Select Ollama for embeddings
# Select Ollama for summarization
```

---

## Multi-Project Support

Agent Brain supports multiple isolated instances for different projects.

### Initialize a Project

```
/agent-brain-init
```

Creates `.claude/doc-serve/` with project-specific configuration.

### Start Project Server

```
/agent-brain-start
```

Automatically allocates a unique port (no conflicts).

### List Running Instances

```
/agent-brain-list
```

Shows all running Agent Brain servers across projects.

### Work from Subdirectories

Commands automatically resolve the project root:

```
cd src/deep/nested/directory
/agent-brain-status  # Finds the parent project's server
```

---

## CLI Reference

For advanced users or automation, the CLI provides direct access:

### Installation

```bash
pip install agent-brain-rag agent-brain-cli
```

### Common Commands

```bash
# Initialize project
agent-brain init

# Start/stop server
agent-brain start --daemon
agent-brain stop

# Index documents
agent-brain index ./docs --include-code

# Query
agent-brain query "your question" --mode hybrid

# Status
agent-brain status
agent-brain list
```

### Query Options

```bash
# Search modes
agent-brain query "term" --mode vector
agent-brain query "term" --mode bm25
agent-brain query "term" --mode hybrid --alpha 0.7
agent-brain query "term" --mode graph
agent-brain query "term" --mode multi

# Result tuning
agent-brain query "term" --top-k 10 --threshold 0.3

# Filtering
agent-brain query "term" --source-types code
agent-brain query "term" --languages python,typescript

# Output formats
agent-brain query "term" --json
agent-brain query "term" --scores
```

---

## Troubleshooting

### Server Not Running

```
/agent-brain-status
```

If not running:
```
/agent-brain-start
```

### No Results Found

1. Check document count: `/agent-brain-status`
2. If 0 documents, re-index: `/agent-brain-index ./docs`
3. Try lowering threshold: `/agent-brain-search "term" --threshold 0.3`
4. Try different search mode: `/agent-brain-keyword "exact term"`

### Configuration Issues

```
/agent-brain-verify
```

This checks:
- Package installation
- API key configuration
- Server connectivity
- Provider setup

### Provider Errors

```
/agent-brain-providers
```

Verify your API keys are set correctly for the selected provider.

### Reset Everything

```
/agent-brain-reset
/agent-brain-init
/agent-brain-start
/agent-brain-index . --include-code
```

---

## Next Steps

- [Quick Start](QUICK_START.md) - Get running in minutes
- [Plugin Guide](PLUGIN_GUIDE.md) - All 24 commands in detail
- [API Reference](API_REFERENCE.md) - REST API documentation
- [GraphRAG Guide](GRAPHRAG_GUIDE.md) - Knowledge graph features
- [Provider Configuration](../agent-brain-plugin/skills/using-agent-brain/references/provider-configuration.md) - Provider setup
