---
name: using-agent-brain
description: |
  Expert Agent Brain skill for document search with BM25 keyword, semantic vector, hybrid, graph, and multi retrieval modes.
  Use when asked to "search documentation", "query domain", "find in docs",
  "bm25 search", "hybrid search", "semantic search", "graph search", "multi search",
  "find dependencies", "code relationships", "searching knowledge base",
  "querying indexed documents", "finding code references", "exploring codebase",
  "what calls this function", "find imports", "trace dependencies",
  "brain search", "brain query", "knowledge base search",
  "cache management", "clear embedding cache", "cache hit rate", or "cache status".
  Supports multi-instance architecture with automatic server discovery.
  GraphRAG mode enables relationship-aware queries for code dependencies and entity connections.
  Pluggable providers for embeddings (OpenAI, Cohere, Ollama) and summarization (Anthropic, OpenAI, Gemini, Grok, Ollama).
license: MIT
allowed-tools:
  - Bash
  - Read
metadata:
  version: 7.0.0
  category: ai-tools
  author: Spillwave
---

# Agent Brain Expert Skill

Expert-level skill for Agent Brain document search with five modes: BM25 (keyword), Vector (semantic), Hybrid (fusion), Graph (knowledge graph), and Multi (comprehensive fusion).

## Contents

- [Search Modes](#search-modes)
- [Mode Selection Guide](#mode-selection-guide)
- [GraphRAG (Knowledge Graph)](#graphrag-knowledge-graph)
- [Indexing & Folder Management](#indexing--folder-management)
- [Content Injection](#content-injection)
- [Job Queue Management](#job-queue-management)
- [Server Management](#server-management)
- [Cache Management](#cache-management)
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
| `--threshold` | 0.3 | Minimum similarity (0.0-1.0) |
| `--top-k` | 5 | Number of results |
| `--alpha` | 0.5 | Hybrid balance (0=BM25, 1=Vector) |

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
agent-brain start
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

## Indexing & Folder Management

### Indexing with File Type Presets

```bash
# Index only Python files
agent-brain index ./src --include-type python

# Index Python and documentation
agent-brain index ./project --include-type python,docs

# Index all code files
agent-brain index ./repo --include-type code

# Force full re-index (bypass incremental)
agent-brain index ./docs --force
```

Use `agent-brain types list` to see all 14 available presets.

### Folder Management

```bash
agent-brain folders list                    # List indexed folders with chunk counts
agent-brain folders add ./docs              # Add folder (triggers indexing)
agent-brain folders add ./src --include-type python  # Add with preset filter
agent-brain folders remove ./old-docs --yes # Remove folder and evict chunks
```

### Incremental Indexing

Re-indexing a folder automatically detects changes:
- **Unchanged files** are skipped (mtime + SHA-256 checksum)
- **Changed files** have old chunks evicted and new ones created
- **Deleted files** have their chunks automatically removed
- Use `--force` to bypass manifest and fully re-index

---

## Content Injection

Enrich chunk metadata during indexing with custom Python scripts or static JSON metadata.

### When to Use

- Tag chunks with project/team/category metadata
- Classify chunks by content type
- Add custom fields for filtered search
- Merge folder-level metadata into all chunks

### Basic Usage

```bash
# Inject via Python script
agent-brain inject ./docs --script enrich.py

# Inject via static JSON metadata
agent-brain inject ./src --folder-metadata project-meta.json

# Validate script before indexing
agent-brain inject ./docs --script enrich.py --dry-run
```

### Injector Script Protocol

Scripts export a `process_chunk(chunk: dict) -> dict` function:

```python
def process_chunk(chunk: dict) -> dict:
    chunk["project"] = "my-project"
    chunk["team"] = "backend"
    return chunk
```

- Values must be scalars (str, int, float, bool)
- Per-chunk exceptions are logged as warnings, not fatal
- See `docs/INJECTOR_PROTOCOL.md` for the full specification

---

## Job Queue Management

Indexing runs asynchronously via a job queue. Monitor and manage jobs:

```bash
agent-brain jobs                    # List all jobs
agent-brain jobs --watch            # Live polling every 3s
agent-brain jobs <job_id>           # Job details + eviction summary
agent-brain jobs <job_id> --cancel  # Cancel a job
```

### Eviction Summary

When re-indexing, job details show what changed:

```
Eviction Summary:
  Files added:     3
  Files changed:   2
  Files deleted:   1
  Files unchanged: 42
  Chunks evicted:  15
  Chunks created:  25
```

This confirms incremental indexing is working efficiently.

---

## Server Management

### Quick Start

```bash
agent-brain init              # Initialize project (first time)
agent-brain start    # Start server
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
| `agent-brain start` | Start with auto-port |
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

## Cache Management

The embedding cache automatically stores computed embeddings to avoid redundant API calls
during reindexing. No setup is required — the cache is active by default.

### When to Check Cache Status

- **After indexing** — verify cache is working and hit rate is growing
- **When queries seem slow** — a low or zero hit rate means embeddings are being recomputed on every reindex
- **To monitor cache growth** — track disk usage over time for large indexes

```bash
agent-brain cache status
```

A healthy cache shows:
- Hit rate > 80% after the first full reindex cycle
- Growing disk entries over time as more content is indexed
- Low misses relative to hits

### When to Clear the Cache

- **After changing embedding provider or model** — prevents dimension mismatches and stale cached vectors
- **Suspected cache corruption** — if embeddings seem incorrect or search quality degrades unexpectedly
- **To force fresh embeddings** — when you need to ensure all vectors reflect the current provider/model

```bash
# Clear with confirmation prompt
agent-brain cache clear

# Clear without prompt (use in scripts)
agent-brain cache clear --yes
```

### Cache is Automatic

No configuration is required. Embeddings are cached on first compute and reused on subsequent
reindexes of unchanged content (identified by SHA-256 hash). The cache complements the
ManifestTracker — files that haven't changed on disk won't need to recompute embeddings.

See the [API Reference](references/api_reference.md) for `GET /index/cache` and `DELETE /index/cache`
endpoint details, including response schemas.

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
8. **File Type Presets**: Use `--include-type python,docs` instead of manual glob patterns
9. **Incremental Indexing**: Re-index without `--force` for efficient updates
10. **Injection Validation**: Always `--dry-run` injector scripts before full indexing
11. **Job Monitoring**: Use `agent-brain jobs --watch` for long-running index jobs

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
