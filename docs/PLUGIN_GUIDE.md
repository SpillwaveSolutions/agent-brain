# Agent Brain Plugin Guide

Complete reference for the Agent Brain Claude Code plugin - 24 commands, 3 agents, and 2 skills for intelligent document and code search.

## Table of Contents

- [Installation](#installation)
- [Quick Setup](#quick-setup)
- [Search Commands](#search-commands)
- [Server Commands](#server-commands)
- [Setup Commands](#setup-commands)
- [Provider Commands](#provider-commands)
- [Intelligent Agents](#intelligent-agents)
- [Skills](#skills)
- [Search Modes](#search-modes)
- [Provider Configuration](#provider-configuration)
- [Integration Patterns](#integration-patterns)
- [Troubleshooting](#troubleshooting)

---

## Installation

Install the Agent Brain plugin in Claude Code:

```bash
claude plugins install github:SpillwaveSolutions/agent-brain
```

This provides:
- **24 slash commands** for all operations
- **3 intelligent agents** for complex tasks
- **2 skills** for context-aware assistance

---

## Quick Setup

The fastest way to get started:

```
/agent-brain-setup
```

This interactive wizard:
1. Installs packages (`agent-brain-rag`, `agent-brain-cli`)
2. Configures API keys
3. Initializes your project
4. Starts the server
5. Indexes your documentation

Or step-by-step:

```
/agent-brain-install     # Install packages
/agent-brain-providers   # Configure API keys
/agent-brain-init        # Initialize project
/agent-brain-start       # Start server
/agent-brain-index .     # Index documents
```

---

## Search Commands

### `/agent-brain-search`

Smart hybrid search - the recommended default for general questions.

```
/agent-brain-search "how does authentication work"
/agent-brain-search "error handling patterns" --top-k 10
```

### `/agent-brain-semantic`

Pure vector/semantic search for conceptual queries.

```
/agent-brain-semantic "explain the overall architecture"
/agent-brain-semantic "what is the purpose of this module"
```

### `/agent-brain-keyword`

BM25 keyword search for exact terms, function names, error codes.

```
/agent-brain-keyword "NullPointerException"
/agent-brain-keyword "getUserById"
```

### `/agent-brain-bm25`

Alias for keyword search.

```
/agent-brain-bm25 "AuthenticationError"
```

### `/agent-brain-vector`

Alias for semantic search.

```
/agent-brain-vector "how does caching improve performance"
```

### `/agent-brain-hybrid`

Hybrid search with explicit alpha control.

```
/agent-brain-hybrid "OAuth implementation" --alpha 0.7
/agent-brain-hybrid "database connection" --alpha 0.3
```

**Alpha Parameter:**
- `1.0` = Pure semantic search
- `0.5` = Balanced (default)
- `0.0` = Pure keyword search

### `/agent-brain-graph`

Knowledge graph search for relationships and dependencies.

```
/agent-brain-graph "what calls AuthService"
/agent-brain-graph "classes that extend BaseController"
/agent-brain-graph "modules that import jwt"
```

### `/agent-brain-multi`

All modes combined with Reciprocal Rank Fusion for maximum recall.

```
/agent-brain-multi "complete authentication flow"
/agent-brain-multi "everything about data validation"
```

### Common Search Options

All search commands support:

| Option | Default | Description |
|--------|---------|-------------|
| `--top-k` | 5 | Number of results |
| `--threshold` | 0.7 | Minimum similarity (0.0-1.0) |
| `--source-types` | all | Filter: doc, code, or both |
| `--languages` | all | Filter by programming language |
| `--scores` | false | Show component scores |

---

## Server Commands

### `/agent-brain-start`

Start the Agent Brain server with automatic port allocation.

```
/agent-brain-start
/agent-brain-start --port 8080
```

### `/agent-brain-stop`

Stop the running server.

```
/agent-brain-stop
```

### `/agent-brain-status`

Check server health and document count.

```
/agent-brain-status
```

**Example Output:**
```json
{
  "status": "healthy",
  "total_documents": 150,
  "total_chunks": 1200,
  "total_doc_chunks": 800,
  "total_code_chunks": 400
}
```

### `/agent-brain-list`

List all running Agent Brain instances across projects.

```
/agent-brain-list
```

### `/agent-brain-index`

Index documents and/or code.

```
/agent-brain-index ./docs
/agent-brain-index . --include-code
/agent-brain-index ./src --include-code --languages python,typescript
/agent-brain-index . --include-code --generate-summaries
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--include-code` | false | Include source code files |
| `--languages` | all | Languages to index |
| `--generate-summaries` | false | Generate LLM summaries |
| `--chunk-size` | 512 | Chunk size in tokens |

### `/agent-brain-reset`

Clear all indexed documents.

```
/agent-brain-reset
```

---

## Setup Commands

### `/agent-brain-setup`

Complete guided setup wizard.

```
/agent-brain-setup
```

### `/agent-brain-install`

Install Agent Brain packages.

```
/agent-brain-install
```

Installs:
- `agent-brain-rag` - FastAPI server
- `agent-brain-cli` - Command-line tool

### `/agent-brain-init`

Initialize project directory.

```
/agent-brain-init
```

Creates `.claude/doc-serve/` with project configuration.

### `/agent-brain-config`

View or edit configuration.

```
/agent-brain-config
/agent-brain-config --set default_mode=hybrid
```

### `/agent-brain-verify`

Verify configuration and connectivity.

```
/agent-brain-verify
```

Checks:
- Package installation
- API key configuration
- Server connectivity
- Provider setup

### `/agent-brain-help`

Show help information.

```
/agent-brain-help
/agent-brain-help search
```

### `/agent-brain-version`

Show version information.

```
/agent-brain-version
```

---

## Provider Commands

### `/agent-brain-providers`

List and configure embedding/summarization providers.

```
/agent-brain-providers
```

Interactive wizard for selecting:
- Embedding provider (OpenAI, Ollama, Cohere)
- Summarization provider (Anthropic, OpenAI, Gemini, Grok, Ollama)

### `/agent-brain-embeddings`

Configure embedding provider specifically.

```
/agent-brain-embeddings
/agent-brain-embeddings --provider ollama --model nomic-embed-text
```

### `/agent-brain-summarizer`

Configure summarization provider specifically.

```
/agent-brain-summarizer
/agent-brain-summarizer --provider anthropic --model claude-haiku-4-5-20251001
```

---

## Intelligent Agents

The plugin includes three agents that handle complex, multi-step tasks autonomously.

### Search Assistant

Performs multi-step searches across different modes and synthesizes answers.

**Triggers:**
- "Find all references to..."
- "Search for..."
- "What files contain..."
- "Where is... defined"

**Example:**
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

**Triggers:**
- "Research how..."
- "Investigate..."
- "Analyze the architecture of..."
- "Explain the design of..."

**Example:**
```
You: "Research how error handling is implemented across the codebase"

Research Assistant:
1. Identifies error handling patterns in docs
2. Finds exception classes and try/catch blocks
3. Traces error propagation through call graph
4. Synthesizes findings with code references
```

### Setup Assistant

Guided installation, configuration, and troubleshooting.

**Triggers:**
- "Help me set up Agent Brain"
- "Configure..."
- "Why isn't... working"
- "Troubleshoot..."

**Example:**
```
You: "Help me set up Agent Brain with Ollama for local operation"

Setup Assistant:
1. Checks if Ollama is installed
2. Verifies embedding model is pulled
3. Configures provider settings
4. Tests the configuration
5. Reports success or guides through fixes
```

---

## Skills

The plugin includes two skills that provide context-aware assistance.

### using-agent-brain

Provides Claude with knowledge about:
- Optimal search mode selection
- Query optimization techniques
- Result interpretation
- API usage patterns

**When Active:** Claude automatically selects the best search mode for your query type.

### configuring-agent-brain

Provides Claude with knowledge about:
- Installation procedures
- Provider configuration
- Troubleshooting steps
- Environment setup

**When Active:** Claude can guide you through setup and resolve configuration issues.

---

## Search Modes

| Mode | Command | Best For | Speed |
|------|---------|----------|-------|
| HYBRID | `/agent-brain-search` | General questions | Medium |
| VECTOR | `/agent-brain-semantic` | Conceptual queries | Slow |
| BM25 | `/agent-brain-keyword` | Exact terms, function names | Fast |
| GRAPH | `/agent-brain-graph` | Dependencies, relationships | Medium |
| MULTI | `/agent-brain-multi` | Maximum recall | Slowest |

### Mode Selection Guide

| Query Type | Recommended Mode | Example |
|------------|------------------|---------|
| "How does X work?" | HYBRID or VECTOR | "how does caching work" |
| Function/class name | BM25 | "getUserById" |
| Error message | BM25 | "NullPointerException" |
| "What calls X?" | GRAPH | "what calls AuthService" |
| "Everything about X" | MULTI | "everything about validation" |
| Conceptual question | VECTOR | "explain the architecture" |

---

## Provider Configuration

### Embedding Providers

| Provider | Models | Local | API Key |
|----------|--------|-------|---------|
| OpenAI | text-embedding-3-large, text-embedding-3-small | No | OPENAI_API_KEY |
| Ollama | nomic-embed-text, mxbai-embed-large | Yes | None |
| Cohere | embed-english-v3.0, embed-multilingual-v3.0 | No | COHERE_API_KEY |

### Summarization Providers

| Provider | Models | Local | API Key |
|----------|--------|-------|---------|
| Anthropic | claude-haiku-4-5-20251001, claude-sonnet-4-5-20250514 | No | ANTHROPIC_API_KEY |
| OpenAI | gpt-5, gpt-5-mini | No | OPENAI_API_KEY |
| Gemini | gemini-3-flash, gemini-3-pro | No | GOOGLE_API_KEY |
| Grok | grok-4, grok-4-fast | No | GROK_API_KEY |
| Ollama | llama4:scout, mistral-small3.2, qwen3-coder | Yes | None |

### Fully Local Mode

Run completely offline with Ollama:

```
/agent-brain-providers
# Select Ollama for embeddings
# Select Ollama for summarization
```

Required Ollama models:
```bash
ollama pull nomic-embed-text
ollama pull llama4:scout
```

---

## Integration Patterns

### CI/CD Integration

```yaml
# .github/workflows/docs-check.yml
jobs:
  validate-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install Agent Brain
        run: pip install agent-brain-rag agent-brain-cli
      - name: Start and Index
        run: |
          agent-brain init
          agent-brain start --daemon
          agent-brain index ./docs
      - name: Validate
        run: agent-brain status
```

### Python API

```python
import httpx
import json
from pathlib import Path

# Discover server
runtime = json.loads(Path(".claude/doc-serve/runtime.json").read_text())
base_url = runtime["base_url"]

# Query
async with httpx.AsyncClient() as client:
    response = await client.post(
        f"{base_url}/query",
        json={"query": "authentication", "mode": "hybrid", "top_k": 5}
    )
    for result in response.json()["results"]:
        print(f"{result['source']}: {result['score']:.2f}")
```

---

## Troubleshooting

### Server Not Running

```
/agent-brain-status
# If not running:
/agent-brain-start
```

### No Results Found

1. Check document count: `/agent-brain-status`
2. If 0 documents: `/agent-brain-index ./docs`
3. Lower threshold: `/agent-brain-search "term" --threshold 0.3`
4. Try keyword search: `/agent-brain-keyword "exact term"`

### GraphRAG Not Working

GraphRAG requires explicit enablement:

```
/agent-brain-config --set enable_graph_index=true
/agent-brain-stop
/agent-brain-start
/agent-brain-index . --include-code
```

### Provider Errors

```
/agent-brain-verify
/agent-brain-providers
```

Verify API keys are set correctly for your selected provider.

### Reset Everything

```
/agent-brain-reset
/agent-brain-init
/agent-brain-start
/agent-brain-index . --include-code
```

---

## Reference Documentation

| Guide | Description |
|-------|-------------|
| [API Reference](API_REFERENCE.md) | REST API documentation |
| [GraphRAG Guide](GRAPHRAG_GUIDE.md) | Knowledge graph features |
| [Code Indexing](CODE_INDEXING.md) | AST-aware chunking |
| [Architecture](ARCHITECTURE.md) | System design |
| [Provider Configuration](../agent-brain-plugin/skills/using-agent-brain/references/provider-configuration.md) | Provider setup |

---

## Next Steps

- [Quick Start](QUICK_START.md) - Get running in minutes
- [User Guide](USER_GUIDE.md) - Detailed usage patterns
- [Developer Guide](DEVELOPERS_GUIDE.md) - Contributing to Agent Brain
