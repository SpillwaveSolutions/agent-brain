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

## 4. Index Documents

Use the CLI tool to index a folder of documents (Markdown, TXT, PDF, etc.):

```bash
# Example: Index the coffee brewing test docs
doc-svr-ctl index ./e2e/fixtures/test_docs/coffee_brewing
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

## Common Commands Summary

| Task | Command |
|------|---------|
| **Start Server** | `doc-serve` |
| **Check Status** | `doc-svr-ctl status` |
| **Index Folder** | `doc-svr-ctl index /path/to/docs` |
| **Semantic Search** | `doc-svr-ctl query "your question"` |
| **Keyword Search** | `doc-svr-ctl query "keyword" --mode bm25` |
| **Hybrid Search** | `doc-svr-ctl query "question" --mode hybrid --alpha 0.5` |
| **Reset Index** | `doc-svr-ctl reset --yes` |
