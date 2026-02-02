---
name: using-agent-brain
description: |
  Expert Agent Brain skill for document search with BM25 keyword, semantic vector, hybrid, graph, and multi retrieval modes.
  Use when asked to "search documentation", "query domain", "find in docs",
  "bm25 search", "hybrid search", "semantic search", "graph search", "multi search",
  "find dependencies", "code relationships", "searching knowledge base",
  "querying indexed documents", "finding code references", "exploring codebase",
  "what calls this function", "find imports", "trace dependencies",
  "brain search", "brain query", or "knowledge base search".
  Supports multi-instance architecture with automatic server discovery.
  GraphRAG mode enables relationship-aware queries for code dependencies and entity connections.
  Pluggable providers for embeddings (OpenAI, Cohere, Ollama) and summarization (Anthropic, OpenAI, Gemini, Grok, Ollama).
license: MIT
allowed-tools:
  - Bash
  - Read
metadata:
  version: 2.0.0
  category: ai-tools
  author: Spillwave
---

# Agent Brain Expert Skill

Expert-level skill for Agent Brain document search with five modes: BM25 (keyword), Vector (semantic), Hybrid (fusion), Graph (knowledge graph), and Multi (comprehensive fusion).

## Contents

- [Search Modes](#search-modes)
- [Mode Selection Guide](#mode-selection-guide)
- [GraphRAG (Knowledge Graph)](#graphrag-knowledge-graph)
- [Server Management](#server-management)
- [When Not to Use](#when-not-to-use)
- [Best Practices](#best-practices)
- [Reference Documentation](#reference-documentation)

---

## Search Modes

| Mode | Speed | Best For | Example Query |
|------|-------|----------|---------------|
| `bm25` | Fast (10-50ms) | Technical terms, function names, error codes | `"AuthenticationError"` |
| `vector` | Slower (800-1500ms) | Concepts, explanations, natural language | `"how authentication works"` |
| `hybrid` | Slower (1000-1800ms) | Comprehensive results combining both | `"OAuth implementation guide"` |
| `graph` | Medium (500-1200ms) | Relationships, dependencies, call chains | `"what calls AuthService"` |
| `multi` | Slowest (1500-2500ms) | Most comprehensive with entity context | `"complete auth flow with dependencies"` |

### Mode Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--mode` | hybrid | Search mode: bm25, vector, hybrid, graph, multi |
| `--threshold` | 0.7 | Minimum similarity (0.0-1.0) |
| `--top-k` | 5 | Number of results |
| `--alpha` | 0.5 | Hybrid balance (0=BM25, 1=Vector) |
| `--traversal-depth` | 2 | Graph traversal depth for graph/multi modes |

---

## Mode Selection Guide

### Use BM25 When

Searching for exact technical terms:

```bash
agent-brain query "recursiveCharacterTextSplitter" --mode bm25
agent-brain query "ValueError: invalid token" --mode bm25
agent-brain query "def process_payment" --mode bm25
```

**Counter-example - Wrong mode choice**:
```bash
# BM25 is wrong for conceptual queries
agent-brain query "how does error handling work" --mode bm25  # Wrong
agent-brain query "how does error handling work" --mode vector  # Correct
```

### Use Vector When

Searching for concepts or natural language:

```bash
agent-brain query "best practices for error handling" --mode vector
agent-brain query "how to implement caching" --mode vector
```

**Counter-example - Wrong mode choice**:
```bash
# Vector is wrong for exact function names
agent-brain query "getUserById" --mode vector  # Wrong - may miss exact match
agent-brain query "getUserById" --mode bm25    # Correct - finds exact match
```

### Use Hybrid When

Need comprehensive results (default mode):

```bash
agent-brain query "OAuth implementation" --mode hybrid --alpha 0.6
agent-brain query "database connection pooling" --mode hybrid
```

**Alpha tuning**:
- `--alpha 0.3` - More keyword weight (technical docs)
- `--alpha 0.7` - More semantic weight (conceptual docs)

### Use Graph When

Exploring relationships and dependencies:

```bash
agent-brain query "what functions call process_payment" --mode graph
agent-brain query "classes that inherit from BaseService" --mode graph --traversal-depth 3
agent-brain query "modules that import authentication" --mode graph
```

**Prerequisite**: Requires `ENABLE_GRAPH_INDEX=true` during server startup.

### Use Multi When

Need the most comprehensive results:

```bash
agent-brain query "complete payment flow implementation" --mode multi --include-relationships
```

---

## GraphRAG (Knowledge Graph)

GraphRAG enables relationship-aware retrieval by building a knowledge graph from indexed documents.

### Enabling GraphRAG

```bash
export ENABLE_GRAPH_INDEX=true
agent-brain start --daemon
```

### Graph Query Types

| Query Pattern | Example |
|---------------|---------|
| Function callers | `"what calls process_payment"` |
| Class inheritance | `"classes extending BaseController"` |
| Import dependencies | `"modules importing auth"` |
| Data flow | `"where does user_id come from"` |

See [Graph Search Guide](references/graph-search-guide.md) for detailed usage.

---

## Server Management

### Quick Start

```bash
agent-brain init              # Initialize project (first time)
agent-brain start --daemon    # Start server
agent-brain index ./docs      # Index documents
agent-brain query "search"    # Search
agent-brain stop              # Stop when done
```

**Progress Checklist:**
- [ ] `agent-brain init` succeeded
- [ ] `agent-brain status` shows healthy
- [ ] Document count > 0
- [ ] Query returns results (or "no matches" - not error)

### Lifecycle Commands

| Command | Description |
|---------|-------------|
| `agent-brain init` | Initialize project config |
| `agent-brain start --daemon` | Start with auto-port |
| `agent-brain status` | Show port, mode, document count |
| `agent-brain list` | List all running instances |
| `agent-brain stop` | Graceful shutdown |

### Pre-Query Validation

Before querying, verify setup:

```bash
agent-brain status
```

Expected:
- Status: healthy
- Documents: > 0
- Provider: configured

**Counter-example - Querying without validation**:
```bash
# Wrong - querying without checking status
agent-brain query "search term"  # May fail if server not running

# Correct - validate first
agent-brain status && agent-brain query "search term"
```

See [Server Discovery Guide](references/server-discovery.md) for multi-instance details.

---

## When Not to Use

This skill focuses on **searching and querying**. Do NOT use for:

- **Installation** - Use `configuring-agent-brain` skill
- **API key configuration** - Use `configuring-agent-brain` skill
- **Server setup issues** - Use `configuring-agent-brain` skill
- **Provider configuration** - Use `configuring-agent-brain` skill

**Scope boundary**: This skill assumes Agent Brain is already installed, configured, and the server is running with indexed documents.

---

## Best Practices

1. **Mode Selection**: BM25 for exact terms, Vector for concepts, Hybrid for comprehensive, Graph for relationships
2. **Threshold Tuning**: Start at 0.7, lower to 0.3-0.5 for more results
3. **Server Discovery**: Use `runtime.json` rather than assuming port 8000
4. **Resource Cleanup**: Run `agent-brain stop` when done
5. **Source Citation**: Always reference source filenames in responses
6. **Graph Queries**: Use graph mode for "what calls X", "what imports Y" patterns
7. **Traversal Depth**: Start with depth 2, increase to 3-4 for deeper chains

---

## Reference Documentation

| Guide | Description |
|-------|-------------|
| [BM25 Search](references/bm25-search-guide.md) | Keyword matching for technical queries |
| [Vector Search](references/vector-search-guide.md) | Semantic similarity for concepts |
| [Hybrid Search](references/hybrid-search-guide.md) | Combined keyword and semantic search |
| [Graph Search](references/graph-search-guide.md) | Knowledge graph and relationship queries |
| [Server Discovery](references/server-discovery.md) | Auto-discovery, multi-agent sharing |
| [Provider Configuration](references/provider-configuration.md) | Environment variables and API keys |
| [Integration Guide](references/integration-guide.md) | Scripts, Python API, CI/CD patterns |
| [API Reference](references/api_reference.md) | REST endpoint documentation |
| [Troubleshooting](references/troubleshooting-guide.md) | Common issues and solutions |

---

## Limitations

- Vector/hybrid/graph/multi modes require embedding provider configured
- Graph mode requires additional memory (~500MB extra)
- Supported formats: Markdown, PDF, plain text, code files (Python, JS, TS, Java, Go, Rust, C, C++)
- Not supported: Word docs (.docx), images
- Server requires ~500MB RAM for typical collections (~1GB with graph)
- Ollama requires local installation and model download
