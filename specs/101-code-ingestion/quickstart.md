# Quickstart: Code Ingestion

## Overview

Doc-Serve now supports indexing and searching source code alongside documentation. This creates a unified corpus where you can cross-reference between implementation and documentation.

## Prerequisites

- Doc-Serve server running (see main quickstart)
- OpenAI API key configured
- Source code project with supported languages

## Supported Languages

- **Python** (.py)
- **TypeScript** (.ts, .tsx)
- **JavaScript** (.js, .jsx)

## Basic Code Indexing

### Index a Python Project

```bash
# Index Python source code
doc-svr-ctl index /path/to/python/project --include-code --languages python

# Example with real project
doc-svr-ctl index ~/projects/my-api --include-code --languages python
```

### Index a Full-Stack Project

```bash
# Index both backend (Python) and frontend (TypeScript)
doc-svr-ctl index /path/to/fullstack/app \
  --include-code \
  --languages python,typescript \
  --exclude-patterns "node_modules/**,*.test.*,__pycache__/**"
```

### Index with Documentation

```bash
# Index both docs and code together
doc-svr-ctl index /path/to/project \
  --include-code \
  --languages python,typescript \
  --recursive
```

## Code Search Examples

### Find Functions by Name

```bash
# Exact function name (BM25)
doc-svr-ctl query "authenticate_user" --mode bm25 --source-type code

# Semantic function search (Vector)
doc-svr-ctl query "user authentication logic" --mode vector --source-type code

# Hybrid search (recommended)
doc-svr-ctl query "user authentication" --mode hybrid --source-type code
```

### Language-Specific Search

```bash
# Python code only
doc-svr-ctl query "database connection" --language python --source-type code

# TypeScript/React code
doc-svr-ctl query "component lifecycle" --language typescript --source-type code

# JavaScript utilities
doc-svr-ctl query "array manipulation" --language javascript --source-type code
```

### Cross-Reference Search

```bash
# Find both docs and code for a topic
doc-svr-ctl query "authentication flow" --source-type all

# API documentation + implementation
doc-svr-ctl query "REST endpoint implementation" --mode hybrid --alpha 0.6
```

## Advanced Usage

### Custom Chunking

```bash
# Larger chunks for complex functions
doc-svr-ctl index /path/to/code --include-code --chunk-size 1000 --chunk-overlap 100
```

### Summary Generation

Code chunks automatically get AI-generated summaries for better semantic search. These help the system understand what each code function does beyond just the code text.

### Filtering Options

```bash
# Exclude test files and build artifacts
doc-svr-ctl index /path/to/project \
  --include-code \
  --exclude-patterns "*test*,*spec*,dist/**,build/**"

# Include only source directories
doc-svr-ctl index src/ tests/ --include-code --languages python
```

## CLI Reference

### Index Command Options

| Option | Description | Example |
|--------|-------------|---------|
| `--include-code` | Enable code file processing | `--include-code` |
| `--languages` | Comma-separated language list | `--languages python,typescript` |
| `--exclude-patterns` | Glob patterns to skip | `--exclude-patterns "test*,*.min.js"` |
| `--recursive` | Scan subdirectories | `--recursive` |

### Query Command Options

| Option | Description | Example |
|--------|-------------|---------|
| `--source-type` | Filter by content type | `--source-type code` |
| `--language` | Filter by programming language | `--language python` |
| `--mode` | Search algorithm | `--mode hybrid` |
| `--alpha` | Hybrid weighting (0.0-1.0) | `--alpha 0.7` |

**Valid Values:**
- `source-type`: `code`, `doc`, `test`, `all`
- `language`: `python`, `typescript`, `javascript`
- `mode`: `vector`, `bm25`, `hybrid`

## API Usage

### Index Code Files

```bash
# POST /index with code parameters
curl -X POST http://localhost:8000/index/ \
  -H "Content-Type: application/json" \
  -d '{
    "paths": ["/path/to/code"],
    "include_code": true,
    "languages": ["python", "typescript"],
    "exclude_patterns": ["*test*", "node_modules/**"],
    "recursive": true
  }'
```

### Query with Filters

```bash
# Search code only
curl -X POST http://localhost:8000/query/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "database connection",
    "source_type": "code",
    "language": "python",
    "mode": "hybrid",
    "alpha": 0.5
  }'

# Cross-reference search
curl -X POST http://localhost:8000/query/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication implementation",
    "source_type": "all",
    "mode": "hybrid"
  }'
```

## Health Monitoring

### Check Indexing Status

```bash
doc-svr-ctl status
```

Shows counts for:
- `total_documents`: Traditional docs
- `total_chunks`: All chunks (docs + code)
- Code-specific counts in health response

### API Health Check

```bash
curl http://localhost:8000/health/status
```

Response includes:
```json
{
  "total_documents": 25,
  "total_chunks": 125,
  "indexing_in_progress": false,
  "bm25_index_ready": true,
  "code_chunks_count": 75,
  "doc_chunks_count": 50
}
```

## Performance Expectations

| Operation | Expected Time | Notes |
|-----------|----------------|-------|
| Index 100 files | 2-5 minutes | Includes summary generation |
| Code search | <100ms | BM25/vector queries |
| Hybrid search | 200-500ms | Dual algorithm execution |
| Cross-reference | 300-800ms | Searches multiple content types |

## Troubleshooting

### No Code Results Found

```bash
# Check if code was indexed
doc-svr-ctl status

# Verify query filters
doc-svr-ctl query "function" --source-type code --language python
```

### Indexing Errors

```bash
# Check server logs
tail -f server.log

# Try with verbose output
doc-svr-ctl index /path/to/code --include-code --verbose
```

### Language Detection Issues

```bash
# Manually specify language
doc-svr-ctl index /path/to/code --include-code --languages python

# Check file extensions
find /path/to/code -name "*.py" | head -10
```

## Best Practices

1. **Start Small**: Index a single directory first to test
2. **Use Excludes**: Skip test files, build artifacts, dependencies
3. **Choose Wisely**: Use BM25 for exact names, hybrid for general queries
4. **Monitor Health**: Check indexing status and chunk counts
5. **Iterate**: Start with defaults, tune alpha and filters as needed

## Example Workflows

### API Development

```bash
# Index FastAPI backend
doc-svr-ctl index backend/ --include-code --languages python

# Find endpoint implementations
doc-svr-ctl query "user registration" --source-type code --mode hybrid

# Cross-reference with API docs
doc-svr-ctl query "authentication endpoints" --source-type all
```

### Full-Stack Development

```bash
# Index both backend and frontend
doc-svr-ctl index . \
  --include-code \
  --languages python,typescript \
  --exclude-patterns "node_modules/**,__pycache__/**"

# Find component implementations
doc-svr-ctl query "user dashboard component" --language typescript

# Find data flow across stack
doc-svr-ctl query "user data validation" --source-type all --mode hybrid
```

This creates a unified knowledge base where documentation and implementation are searchable together!