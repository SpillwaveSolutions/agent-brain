# Doc-Serve User Guide

This guide covers how to use Doc-Serve for document indexing, semantic search, and integration with Claude Code.

## Table of Contents

- [Getting Started](#getting-started)
- [Server Usage](#server-usage)
- [CLI Tool Reference](#cli-tool-reference)
- [Claude Code Skill](#claude-code-skill)
- [API Usage](#api-usage)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

---

## Getting Started

### Prerequisites

Before using Doc-Serve, ensure you have:

1. **Python 3.10 or higher** installed
2. **Poetry** for dependency management - `pip install poetry`
3. **Task** for running commands - [Install Task](https://taskfile.dev/installation/)
4. **OpenAI API key** for embeddings
5. **Anthropic API key** for summarization

### Installation

```bash
# Clone the repository
git clone https://github.com/spillwave/doc-serve.git
cd doc-serve

# Install all dependencies
task install

# Verify installation
task --list
```

### First-Time Setup

1. Create your environment configuration:

```bash
cp doc-serve-server/.env.example doc-serve-server/.env
```

2. Edit `.env` and add your API keys:

```bash
# Required API keys
OPENAI_API_KEY=sk-your-openai-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here

# Server settings
API_HOST=127.0.0.1
API_PORT=8000
DEBUG=false
```

3. Start the server:

```bash
task dev
```

4. Verify it's running:

```bash
task status
```


```

# Or directly: 
curl http://127.0.0.1:8000/health/ | jq .

{
  "status": "healthy",
  "message": "Server is running and ready for queries",
  "timestamp": "2025-12-17T21:38:50.296960",
  "version": "1.0.0"
}
```

---

## Server Usage

### Starting the Server

```bash
# Development mode (with hot reload)
task dev

# Production mode
task run
```

The server provides:
- **REST API** at `http://127.0.0.1:8000`
- **Swagger UI** at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc UI** at [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **OpenAPI Schema** at [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)




### Health Check

Monitor server health:

```bash
curl http://127.0.0.1:8000/health
```

Response:
```json
{
  "status": "healthy",
  "message": "Server is running and ready for queries",
  "version": "1.0.0",
  "timestamp": "2024-12-15T10:00:00Z"
}
```

### Status Values

| Status | Description |
|--------|-------------|
| `healthy` | Server ready for queries |
| `indexing` | Indexing in progress |
| `degraded` | Partial functionality |
| `unhealthy` | Server not operational |

---

## CLI Tool Reference

The `doc-svr-ctl` CLI provides complete server management capabilities. 
You can use either Task commands (recommended for development of this tool),
or direct CLI commands (recommended for production use).

### Task Commands (Recommended)

| Task Command | Description |
|--------------|-------------|
| `task status` | Check server status |
| `task query -- "text"` | Search documents |
| `task index -- /path` | Index documents |
| `task reset` | Clear the index |

### Direct CLI Commands

All commands support these options:

| Option | Description |
|--------|-------------|
| `--url URL` | Server URL (default: `http://127.0.0.1:8000`) |
| `--json` | Output in JSON format |
| `--help` | Show command help |

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DOC_SERVE_URL` | Server URL | `http://127.0.0.1:8000` |

### Commands

#### status - Check Server Status

```bash
# Using Task (recommended)
task status

# Direct CLI
doc-svr-ctl status

# JSON output
doc-svr-ctl status --json

# Custom server URL
doc-svr-ctl status --url http://localhost:9000
```

Output shows:
- Server health status
- Number of indexed documents
- Indexing progress (if in progress)
- Last indexing timestamp

#### query - Search Documents

```bash
# Using Task (recommended)
task query -- "how to configure authentication"

# Direct CLI
doc-svr-ctl query "how to configure authentication"

# Limit results
doc-svr-ctl query "kubernetes networking" --top-k 10

# JSON output for scripting
doc-svr-ctl query "error handling" --json
```

Options:
| Option | Description | Default |
|--------|-------------|---------|
| `--top-k N` | Number of results | 5 |
| `--json` | JSON output | false |

#### index - Index Documents

```bash
# Using Task (recommended)
task index -- /path/to/documents

# Direct CLI
doc-svr-ctl index /path/to/documents

# Index recursively
doc-svr-ctl index /path/to/documents --recursive

# Specific file patterns
doc-svr-ctl index /path/to/documents --patterns "*.md,*.txt"
```

Options:
| Option | Description | Default |
|--------|-------------|---------|
| `--recursive` | Include subdirectories | true |
| `--patterns` | File patterns to include | `*.md,*.txt,*.rst` |

#### reset - Clear Index

```bash
# Using Task (recommended)
task reset

# Direct CLI with confirmation prompt
doc-svr-ctl reset

# Skip confirmation
doc-svr-ctl reset --yes
```

**Warning**: This permanently deletes all indexed documents.

### Example Workflows

#### Index a Documentation Folder

```bash
# Start the server in background
task dev &

# Wait for startup
sleep 3

# Check it's ready
task status

# Index your docs
task index -- ~/projects/my-app/docs

# Query
task query -- "how to deploy"
```

#### Batch Processing with JSON

```bash
# Query and pipe to jq for processing
doc-svr-ctl query "authentication" --json | jq '.results[].source'
```

---

## Claude Code Skill

The `doc-serve` skill enables Claude Code to query your indexed documentation.

### Installation

Copy the skill to your Claude Code skills directory:

```bash
cp -r doc-serve-skill/doc-serve ~/.claude/skills/
```

### Usage

In Claude Code, use phrases like:
- "search the domain for authentication patterns"
- "look up error handling in the docs"
- "query the documentation for API endpoints"

### Trigger Phrases

| Phrase | Action |
|--------|--------|
| `search the domain X` | Search for X in indexed docs |
| `look up in domain` | Query documentation |
| `find in docs` | Search documents |
| `semantic search` | Execute vector search |

### Example Conversation

```
User: search the domain for kubernetes pod networking

Claude: [Queries doc-serve and returns relevant chunks]

Found 3 relevant documents:

1. **networking.md** (score: 0.92)
   Pod networking in Kubernetes uses CNI plugins...

2. **services.md** (score: 0.87)
   Services provide network access to pods...
```

---

## API Usage

### REST API Examples

#### Query Documents

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "how to configure authentication",
    "top_k": 5,
    "similarity_threshold": 0.7
  }'
```

Response:
```json
{
  "results": [
    {
      "text": "Authentication can be configured using...",
      "source": "docs/auth/config.md",
      "score": 0.92,
      "chunk_id": "chunk_abc123",
      "metadata": {}
    }
  ],
  "query_time_ms": 45.2,
  "total_results": 1
}
```

#### Start Indexing

```bash
curl -X POST http://127.0.0.1:8000/index \
  -H "Content-Type: application/json" \
  -d '{
    "folder_path": "/path/to/documents",
    "recursive": true,
    "file_patterns": ["*.md", "*.txt"]
  }'
```

#### Get Index Status

```bash
curl http://127.0.0.1:8000/health/status
```

### Python Client

```python
import httpx

def search_docs(query: str, top_k: int = 5) -> dict:
    """Search indexed documentation."""
    response = httpx.post(
        "http://127.0.0.1:8000/query",
        json={
            "query": query,
            "top_k": top_k,
            "similarity_threshold": 0.7
        }
    )
    return response.json()

# Usage
results = search_docs("pod networking")
for result in results["results"]:
    print(f"{result['source']}: {result['score']:.2f}")
```

---

## Configuration

### Required API Keys

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for generating embeddings |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude summarization |

### Server Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `API_HOST` | Server bind address | `127.0.0.1` |
| `API_PORT` | Server port | `8000` |
| `DEBUG` | Enable debug mode | `false` |

### AI Model Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `EMBEDDING_MODEL` | OpenAI embedding model | `text-embedding-3-large` |
| `EMBEDDING_DIMENSIONS` | Embedding vector dimensions | `3072` |
| `CLAUDE_MODEL` | Claude model for summarization | `claude-3-5-haiku-20241022` |

### Chunking Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DEFAULT_CHUNK_SIZE` | Default chunk size (tokens) | `512` |
| `DEFAULT_CHUNK_OVERLAP` | Overlap between chunks | `50` |
| `MAX_CHUNK_SIZE` | Maximum allowed chunk size | `2048` |
| `MIN_CHUNK_SIZE` | Minimum allowed chunk size | `128` |

### Query Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DEFAULT_TOP_K` | Default results to return | `5` |
| `MAX_TOP_K` | Maximum results allowed | `50` |
| `DEFAULT_SIMILARITY_THRESHOLD` | Minimum similarity score | `0.7` |

### Vector Store Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `CHROMA_PERSIST_DIR` | ChromaDB storage directory | `./chroma_db` |
| `COLLECTION_NAME` | Vector collection name | `doc_serve_collection` |

### Rate Limiting

| Variable | Description | Default |
|----------|-------------|---------|
| `EMBEDDING_BATCH_SIZE` | Batch size for embeddings | `100` |

### Example .env File

```bash
# ======================
# REQUIRED API KEYS
# ======================
OPENAI_API_KEY=sk-your-openai-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here

# ======================
# SERVER CONFIGURATION
# ======================
API_HOST=127.0.0.1
API_PORT=8000
DEBUG=false

# ======================
# AI MODEL CONFIGURATION
# ======================
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIMENSIONS=3072
CLAUDE_MODEL=claude-3-5-haiku-20241022

# ======================
# CHUNKING CONFIGURATION
# ======================
DEFAULT_CHUNK_SIZE=512
DEFAULT_CHUNK_OVERLAP=50
MAX_CHUNK_SIZE=2048
MIN_CHUNK_SIZE=128

# ======================
# QUERY CONFIGURATION
# ======================
DEFAULT_TOP_K=5
MAX_TOP_K=50
DEFAULT_SIMILARITY_THRESHOLD=0.7

# ======================
# VECTOR STORE
# ======================
CHROMA_PERSIST_DIR=./chroma_db
COLLECTION_NAME=doc_serve_collection

# ======================
# RATE LIMITING
# ======================
EMBEDDING_BATCH_SIZE=100
```

---

## Troubleshooting

### Common Issues

#### Server Won't Start

**Symptom**: Server fails to start with import errors

**Solution**:
```bash
# Reinstall dependencies
task install

# Try starting again
task dev
```

#### Query Returns No Results

**Symptom**: Queries return empty results

**Checklist**:
1. Check server status: `task status`
2. Verify documents are indexed (check document count)
3. Lower similarity threshold in query
4. Try broader search terms

#### Indexing Fails

**Symptom**: Indexing starts but fails

**Solutions**:
1. Check folder path exists and is readable
2. Verify file patterns match your documents
3. Check server logs for detailed errors
4. Ensure OpenAI API key is valid

#### Connection Refused

**Symptom**: `Connection refused` when accessing server

**Solutions**:
1. Verify server is running: `ps aux | grep doc-serve`
2. Check correct port: `curl http://127.0.0.1:8000/health`
3. Check firewall settings

### Getting Help

1. Check server logs for detailed error messages
2. Use `--json` flag for programmatic error details
3. Review API docs at `/docs` for request format
4. Check the [API Reference](../doc-serve-skill/doc-serve/references/api_reference.md)

### Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| 400 | Invalid request | Check query format |
| 404 | Not found | Verify endpoint URL |
| 500 | Server error | Check server logs |
| 503 | Service unavailable | Wait for indexing to complete |
