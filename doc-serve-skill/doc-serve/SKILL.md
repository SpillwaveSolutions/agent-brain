---
name: doc-serve
description: |
  Advanced document search with BM25 keyword matching, semantic vector search, and hybrid retrieval.
  Enables precise technical queries, conceptual understanding, and intelligent result fusion.
  Supports local document indexing and provides comprehensive search capabilities for knowledge bases.
version: 1.2.0
category: ai-tools
triggers:
  - doc-serve
  - bm25 search
  - hybrid search
  - semantic search
  - search the domain
  - search domain
  - query domain
  - look up in domain
  - find in docs
  - search documentation
  - technical search
  - documentation search
author: Spillwave
license: MIT
---

# Doc-Serve Skill

## Overview

`doc-serve` provides advanced document search capabilities with three powerful search modes: BM25 keyword search, semantic vector search, and intelligent hybrid retrieval. It indexes local documentation (Markdown, PDF, TXT) and enables precise technical queries, conceptual understanding, and comprehensive knowledge discovery.

## Capabilities

1. **Multi-Mode Search**: BM25 (keyword), Vector (semantic), Hybrid (fusion)
2. **Automatic Setup**: Repository cloning and CLI tool installation
3. **Server Management**: Start/stop API server with health monitoring
4. **Smart Indexing**: Document processing with chunking and embeddings
5. **Advanced Retrieval**: Context-aware search with scoring transparency
6. **API Integration**: RESTful endpoints with OpenAPI documentation

## When to Use

- **Technical queries**: "Find AuthenticationError handling"
- **Conceptual questions**: "How does OAuth authentication work?"
- **Comprehensive search**: "Complete guide to error handling"
- **Domain knowledge**: Search internal documentation and knowledge bases
- **API references**: Find function definitions, error codes, specifications

## Core Workflow

### 1. Setup Verification
```bash
doc-svr-ctl --version  # Check CLI tools installed
```

### 2. Server Management
```bash
doc-serve &            # Start server in background
doc-svr-ctl status     # Verify server health
```

### 3. Document Indexing
```bash
doc-svr-ctl index /path/to/docs  # Index documentation
```

### 4. Intelligent Search
```bash
# Choose search mode based on query type
doc-svr-ctl query "exact function name" --mode bm25      # Technical terms
doc-svr-ctl query "how concept works" --mode vector      # Explanations
doc-svr-ctl query "complete solution" --mode hybrid      # Best of both
```

## Search Mode Selection Guide

| Query Type | Recommended Mode | Example |
|------------|------------------|---------|
| **Technical terms** | BM25 | `"AuthenticationError"` |
| **Function names** | BM25 | `"recursiveCharacterTextSplitter"` |
| **Error codes** | BM25 | `"HTTP 404"` |
| **Explanations** | Vector | `"how authentication works"` |
| **Concepts** | Vector | `"best practices guide"` |
| **Mixed content** | Hybrid | `"implement OAuth with error handling"` |
| **Comprehensive** | Hybrid | `"complete troubleshooting guide"` |

## Best Practices

- **Mode Selection**: Use BM25 for technical terms, Vector for concepts, Hybrid for comprehensive results
- **Threshold Tuning**: Start at 0.7, lower to 0.3-0.5 for more results
- **Alpha Weighting**: Adjust hybrid balance (0.0=BM25, 1.0=Vector)
- **Source Citation**: Always reference source filenames in responses
- **Background Operation**: Run server with `doc-serve &` for interactive use

## Reference Documentation

### Search Mode Guides
- **[BM25 Search Guide](references/bm25-search-guide.md)**: Exact keyword matching for technical queries
- **[Vector Search Guide](references/vector-search-guide.md)**: Semantic similarity for conceptual understanding
- **[Hybrid Search Guide](references/hybrid-search-guide.md)**: Intelligent fusion of keyword and semantic search

### Troubleshooting
- **[Troubleshooting Guide](references/troubleshooting-guide.md)**: Common issues and solutions

### API Documentation
- **[API Reference](references/api_reference.md)**: Complete endpoint documentation

## Example Usage Scenarios

### Technical Query (BM25 Mode)
**User**: "What does the documentation say about AuthenticationError?"

**Execution**:
```bash
doc-svr-ctl query "AuthenticationError" --mode bm25 --threshold 0.2
```

**Response**: "According to `auth_module.md`, AuthenticationError is raised when credentials are invalid, with fields for username, timestamp, and failure reason."

### Conceptual Query (Vector Mode)
**User**: "How does the authentication system work?"

**Execution**:
```bash
doc-svr-ctl query "authentication system flow" --mode vector --threshold 0.5
```

**Response**: "The authentication system uses a multi-step flow: credential validation, token generation with JWT, session management via Redis, and automatic logout after 30 minutes (from `auth_overview.md`)."

### Comprehensive Query (Hybrid Mode)
**User**: "Complete guide to implementing error handling"

**Execution**:
```bash
doc-svr-ctl query "error handling implementation guide" --mode hybrid --alpha 0.6 --top-k 8
```

**Response**: "Complete error handling implementation: 1) Exception hierarchy design, 2) Try-catch patterns, 3) Error logging with structured data, 4) User-friendly error messages, 5) Recovery strategies (from `error_handling.md` and `logging_guide.md`)."

## Performance Characteristics

| Mode | Speed | API Required | Best For |
|------|-------|--------------|----------|
| **BM25** | ⚡ 10-50ms | ❌ No | Technical terms, exact matches |
| **Vector** | 🐌 800-1500ms | ✅ Yes | Concepts, explanations |
| **Hybrid** | 🐌 1000-1800ms | ✅ Yes | Comprehensive, best quality |

## Configuration Requirements

### API Keys (for Vector/Hybrid modes)
```bash
# Required for semantic search
export OPENAI_API_KEY="sk-proj-..."
export ANTHROPIC_API_KEY="sk-ant-..."  # Optional
```

### Environment Setup
```bash
# Install tools
task install:global

# Configure API keys in .env file
cd doc-serve-server
echo "OPENAI_API_KEY=your-key-here" > .env
```

## Advanced Features

- **Alpha Weighting**: Fine-tune hybrid search balance
- **Scoring Transparency**: Individual vector/BM25 scores with `--scores`
- **JSON Output**: Structured data with `--json` for scripting
- **Batch Processing**: Efficient indexing of large document collections
- **Health Monitoring**: Server status and indexing progress tracking

## Integration Patterns

### CLI Scripting
```bash
# Automated searches in scripts
RESULT=$(doc-svr-ctl query "$QUERY" --mode hybrid --json)
echo "$RESULT" | jq '.results[0].text'
```

### API Integration
```python
import requests

response = requests.post('http://localhost:8000/query/', json={
    'query': 'authentication guide',
    'mode': 'hybrid',
    'alpha': 0.5
})
results = response.json()['results']
```

### CI/CD Integration
```bash
# Documentation validation in CI
doc-svr-ctl query "deprecated feature" --mode bm25 --threshold 0.1
if [ $? -eq 0 ]; then echo "Documentation search working"; fi
```

## Limitations & Considerations

- **API Costs**: Vector/hybrid modes require OpenAI API credits
- **Setup Complexity**: Initial configuration requires API keys and indexing
- **Resource Usage**: Server requires ~500MB RAM for typical document collections
- **File Formats**: Supports Markdown, PDF, plain text (not Word docs or images)

## Getting Started Checklist

- [ ] Install CLI tools: `task install:global`
- [ ] Set API keys in environment or `.env` file
- [ ] Start server: `doc-serve &`
- [ ] Index documents: `doc-svr-ctl index /path/to/docs`
- [ ] Test search: `doc-svr-ctl query "test query"`
- [ ] Explore modes: Try BM25, vector, and hybrid search
