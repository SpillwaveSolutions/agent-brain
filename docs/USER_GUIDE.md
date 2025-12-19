# Doc-Serve User Guide

This guide covers how to use Doc-Serve for document indexing and semantic search using the command-line interface.

## Table of Contents

- [Core Concepts](#core-concepts)
- [Server Management](#server-management)
- [Indexing Documents](#indexing-documents)
- [Querying Knowledge](#querying-knowledge)
- [Advanced CLI Usage](#advanced-cli-usage)
- [Troubleshooting](#troubleshooting)

---

## Core Concepts

Doc-Serve is a RAG (Retrieval-Augmented Generation) system that can index and search across both documentation and source code. It works in three phases:
1. **Indexing**: It reads your documents and/or source code, splits them into semantic chunks using context-aware algorithms, and generates vector embeddings.
2. **Storage**: Chunks and embeddings are stored in a ChromaDB vector database with metadata for filtering.
3. **Retrieval**: When you query, it finds the most similar chunks based on semantic meaning, with support for cross-reference searches across docs and code.

## Server Management

The Doc-Serve server must be running to handle indexing and query requests.

### Starting the Server
```bash
doc-serve
```
By default, the server binds to `127.0.0.1:8000`. You can change this using options:
- `--host`: Bind address (e.g., `0.0.0.0`)
- `--port`: Port number (e.g., `8080`)
- `--reload`: Enable auto-reload for development

### Checking Server Health
Use the management tool to check if the server is responsive:
```bash
doc-svr-ctl status
```

## Indexing Documents and Code

Doc-Serve can index both documentation and source code for unified search capabilities.

### Index Documentation Only (Default)
```bash
doc-svr-ctl index /path/to/your/docs
```

### Index Code + Documentation
```bash
doc-svr-ctl index /path/to/your/project --include-code
```

### Advanced Indexing Options
**General Options:**
- `--recursive` / `--no-recursive`: Whether to scan subdirectories (default: true).
- `--chunk-size`: Size of text chunks in tokens (default: 512).
- `--overlap`: Overlap between chunks (default: 50).

**Code-Specific Options:**
- `--include-code`: Include source code files alongside documentation.
- `--languages`: Comma-separated list of programming languages to index (e.g., `python,typescript`).
- `--code-strategy`: Chunking strategy for code (`ast_aware` or `text_based`, default: `ast_aware`).
- `--generate-summaries`: Generate LLM summaries for code chunks to improve semantic search.

### Resetting the Index
If you want to start over and clear all indexed data:
```bash
doc-svr-ctl reset --yes
```

## Querying Knowledge

Doc-Serve supports three search modes:
1. **Semantic Search (Vector)**: Finds content with similar meaning.
2. **Keyword Search (BM25)**: Finds exact word matches (best for function names, error codes).
3. **Hybrid Search**: Combines both (recommended default).

### Basic Query (Hybrid)
```bash
doc-svr-ctl query "how do I configure the system?"
```

### Search Modes
- `--mode hybrid`: (Default) Blends semantic and keyword results.
- `--mode vector`: Pure semantic search.
- `--mode bm25`: Pure keyword matching.

### Refining Results
- `--top-k N`: Return top N results (default: 5).
- `--threshold F`: Minimum similarity score between 0.0 and 1.0 (default: 0.7).
- `--alpha F`: In hybrid mode, weight between vector and bm25. `1.0` is pure vector, `0.0` is pure bm25 (default: 0.5).
- `--scores`: Display individual vector and BM25 scores for each result.

### Code-Aware Search (with Code Ingestion)

When code is indexed alongside documentation, you can perform powerful cross-reference searches:

#### Filtering by Source Type
```bash
# Search documentation only
doc-svr-ctl query "API usage examples" --source-types doc

# Search code only
doc-svr-ctl query "database connection" --source-types code

# Search both (default)
doc-svr-ctl query "authentication implementation"
```

#### Filtering by Programming Language
```bash
# Search Python code only
doc-svr-ctl query "error handling" --languages python

# Search multiple languages
doc-svr-ctl query "API endpoints" --languages python,typescript

# Combine filters
doc-svr-ctl query "data validation" --source-types code --languages javascript
```

#### Supported Languages
Doc-Serve supports AST-aware chunking for: **Python, TypeScript, JavaScript, Java, Kotlin, C, C++, Go, Rust, Swift**

### Programmatic Output
Use the `--json` flag to get raw data for piping into other tools like `jq`:
```bash
doc-svr-ctl query "api endpoints" --json | jq .results[0].text
```

## Troubleshooting

### Connection Error
If you see `Connection Error: Unable to connect to server`, ensure:
1. The `doc-serve` process is running.
2. You are using the correct URL (default `http://127.0.0.1:8000`).
3. If the server is on a different port, use `doc-svr-ctl --url http://127.0.0.1:PORT status`.

### No Results Found
If queries return no results:
1. Run `doc-svr-ctl status` to check the "Total Chunks" count. If 0, indexing failed or hasn't run.
2. Lower the `--threshold` (try `0.3` or `0.2`).
3. Ensure the documents you indexed contain relevant text and are in supported formats (.md, .txt, .pdf).

### Duplicated Results
If you see identical results, the stable ID logic ensures that re-indexing the same files updates existing entries. If you have moved files or indexed different paths to the same data, run `doc-svr-ctl reset --yes` and re-index.
