# Doc-Serve Quick Start

Get up and running with Doc-Serve in minutes using the command-line tools.

## 1. Installation

Install Doc-Serve and the management tool globally using the Task runner:

```bash
# Clone the repository
git clone git@github.com:SpillwaveSolutions/doc-serve.git
cd doc-serve

# Install tools globally (makes 'doc-serve' and 'doc-svr-ctl' available)
task install:global
```

## 2. Configuration

Create a `.env` file in the `doc-serve-server` directory with your API keys:

```bash
cd doc-serve-server
cp .env.example .env
# Edit .env and add:
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
```

## 3. Launch the Server

Start the Doc-Serve API server:

```bash
# From any directory
doc-serve
```
*Keep this terminal open or run in the background with `doc-serve &`.*

## 4. Index Documents and Code

Doc-Serve can index both documentation and source code for unified search:

### Index Documentation Only (Default)
```bash
# Index documentation files (Markdown, TXT, PDF, etc.)
doc-svr-ctl index ./docs
```

### Index Code + Documentation (Recommended)
```bash
# Index both documentation and source code files
doc-svr-ctl index ./my-project --include-code
```

### Advanced Indexing Options
```bash
# Index specific programming languages
doc-svr-ctl index ./src --include-code --languages python,typescript

# Use AST-aware chunking for better code understanding
doc-svr-ctl index ./src --include-code --code-strategy ast_aware

# Generate LLM summaries for code chunks (improves semantic search)
doc-svr-ctl index ./src --include-code --generate-summaries
```

Check the status to ensure indexing is complete:
```bash
doc-svr-ctl status
```

## 5. Query Knowledge

Doc-Serve supports three powerful search modes:

### Semantic Search (Vector - Default)
```bash
# Search for espresso information using semantic similarity
doc-svr-ctl query "espresso brewing techniques"
```

### Keyword Search (BM25)
```bash
# Search for exact word matches (great for function names, error codes)
doc-svr-ctl query "espresso" --mode bm25
```

### Hybrid Search (Recommended)
```bash
# Combine semantic and keyword search (best of both worlds)
doc-svr-ctl query "espresso vs french press" --mode hybrid --alpha 0.7
```

### Advanced Options
```bash
# Show individual scores for hybrid results
doc-svr-ctl query "brewing methods" --mode hybrid --scores

# Adjust result count and similarity threshold
doc-svr-ctl query "coffee temperature" --top-k 10 --threshold 0.3
```

### Code-Aware Search (with Code Ingestion)

When code is indexed, you can perform cross-reference searches:

```bash
# Search across both documentation and code
doc-svr-ctl query "authentication implementation"

# Filter results by source type
doc-svr-ctl query "API endpoints" --source-types code      # Code only
doc-svr-ctl query "API usage" --source-types doc           # Docs only

# Filter by programming language
doc-svr-ctl query "database connection" --languages python,typescript

# Combine filters for precise results
doc-svr-ctl query "error handling" --source-types code --languages go
```

### Supported Languages
Doc-Serve supports code ingestion for: **Python, TypeScript, JavaScript, Java, Kotlin, C, C++, Go, Rust, Swift**

## Common Commands Summary

| Task | Command |
|------|---------|
| **Start Server** | `doc-serve` |
| **Check Status** | `doc-svr-ctl status` |
| **Index Docs Only** | `doc-svr-ctl index /path/to/docs` |
| **Index Code + Docs** | `doc-svr-ctl index /path --include-code` |
| **Semantic Search** | `doc-svr-ctl query "your question"` |
| **Keyword Search** | `doc-svr-ctl query "keyword" --mode bm25` |
| **Hybrid Search** | `doc-svr-ctl query "question" --mode hybrid --alpha 0.5` |
| **Filter by Source** | `doc-svr-ctl query "term" --source-types code` |
| **Filter by Language** | `doc-svr-ctl query "term" --languages python` |
| **Reset Index** | `doc-svr-ctl reset --yes` |
