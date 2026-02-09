# Agent Brain RAG Server

> **Agent Brain** (formerly doc-serve) is an intelligent document indexing and semantic search system designed to give AI agents long-term memory.

AI agents need persistent memory to be truly useful. Agent Brain provides the retrieval infrastructure that enables context-aware, knowledge-grounded AI interactions.

[![PyPI version](https://badge.fury.io/py/agent-brain-rag.svg)](https://pypi.org/project/agent-brain-rag/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Installation

```bash
pip install agent-brain-rag
```

## Quick Start

1. Set environment variables:
   ```bash
   export OPENAI_API_KEY=your-key
   export ANTHROPIC_API_KEY=your-key
   ```

2. Start the server:
   ```bash
   agent-brain-serve
   ```

The server will start at `http://127.0.0.1:8000`.

> **Note**: The legacy command `doc-serve` is still available but deprecated. Please use `agent-brain-serve` for new installations.

## Search Capabilities

Agent Brain provides multiple search strategies to match your retrieval needs:

| Search Type | Description | Best For |
|-------------|-------------|----------|
| **Semantic Search** | Natural language queries using OpenAI embeddings (`text-embedding-3-large`) | Conceptual questions, finding related content |
| **Keyword Search (BM25)** | Traditional keyword matching with TF-IDF ranking | Exact matches, technical terms, code identifiers |
| **Hybrid Search** | Combines vector + BM25 for best of both approaches | General-purpose queries, balanced recall/precision |
| **GraphRAG** | Knowledge graph-based retrieval for relationship-aware queries | Understanding connections, multi-hop reasoning |

## Features

- **Document Indexing**: Load and index documents from folders (PDF, Markdown, TXT, DOCX, HTML)
- **AST-Aware Code Ingestion**: Smart parsing for Python, TypeScript, JavaScript, Java, Go, Rust, C, C++
- **Multi-Strategy Retrieval**: Semantic, keyword, hybrid, and graph-based search
- **OpenAI Embeddings**: Uses `text-embedding-3-large` for high-quality embeddings
- **Claude Summarization**: AI-powered code summaries for better context
- **Chroma Vector Store**: Persistent, thread-safe vector database
- **FastAPI**: Modern, high-performance REST API with OpenAPI documentation

## Prerequisites

- Python 3.10+
- OpenAI API key (for embeddings)
- Anthropic API key (for summarization)

## GraphRAG Configuration (Feature 113)

Agent Brain supports optional GraphRAG (Graph-based Retrieval-Augmented Generation) for enhanced relationship-aware queries.

### Enabling GraphRAG

Set the environment variable to enable graph indexing:

```bash
export ENABLE_GRAPH_INDEX=true
```

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_GRAPH_INDEX` | `false` | Enable/disable GraphRAG features |
| `GRAPH_STORE_TYPE` | `simple` | Graph backend: `simple` (JSON) or `kuzu` (embedded DB) |
| `GRAPH_MAX_TRIPLETS_PER_CHUNK` | `10` | Maximum entities to extract per document chunk |
| `GRAPH_USE_CODE_METADATA` | `true` | Extract relationships from code AST metadata |
| `GRAPH_USE_LLM_EXTRACTION` | `true` | Use LLM for entity extraction from documents |
| `GRAPH_TRAVERSAL_DEPTH` | `2` | Default traversal depth for graph queries |

### Query Modes

With GraphRAG enabled, you have access to additional query modes:

- **`graph`**: Query using only the knowledge graph (entity relationships)
- **`multi`**: Combines vector search, BM25, and graph results using RRF fusion

### Example: Graph Query

```bash
# CLI
agent-brain query "authentication service" --mode graph

# API
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication service", "mode": "graph", "top_k": 10}'
```

### Example: Multi-Mode Query

```bash
# CLI
agent-brain query "user login flow" --mode multi

# API
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "user login flow", "mode": "multi", "top_k": 5}'
```

### Rebuilding the Graph Index

To rebuild only the graph index without re-indexing documents:

```bash
curl -X POST "http://localhost:8000/index?rebuild_graph=true" \
  -H "Content-Type: application/json" \
  -d '{"folder_path": "."}'
```

### Optional Dependencies

For enhanced GraphRAG features, install optional dependency groups:

```bash
# For Kuzu graph store (production workloads)
poetry install --with graphrag-kuzu

# For enhanced entity extraction
poetry install --with graphrag
```

## Two-Stage Reranking (Feature 123)

Agent Brain supports optional two-stage retrieval with reranking for improved search precision. When enabled, the system:

1. **Stage 1**: Retrieves more candidates than requested (e.g., 50 candidates for top_k=5)
2. **Stage 2**: Reranks candidates using a cross-encoder model for more accurate relevance scoring

### Enabling Reranking

Set the following environment variables:

```bash
# Enable two-stage reranking (default: false)
ENABLE_RERANKING=true

# Choose provider (default: sentence-transformers)
RERANKER_PROVIDER=sentence-transformers  # or "ollama"

# Choose model (default: cross-encoder/ms-marco-MiniLM-L-6-v2)
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2

# Stage 1 retrieval multiplier (default: 10)
RERANKER_TOP_K_MULTIPLIER=10

# Maximum candidates for Stage 1 (default: 100)
RERANKER_MAX_CANDIDATES=100

# Batch size for reranking inference (default: 32)
RERANKER_BATCH_SIZE=32
```

### Provider Options

| Provider | Model | Latency | Description |
|----------|-------|---------|-------------|
| sentence-transformers | cross-encoder/ms-marco-MiniLM-L-6-v2 | ~50ms | Recommended. Fast, accurate cross-encoder. |
| sentence-transformers | cross-encoder/ms-marco-MiniLM-L-12-v2 | ~100ms | Slower but more accurate. |
| ollama | llama3.2:1b | ~500ms | Fully local, no HuggingFace download. |

### YAML Configuration

You can also configure reranking in `config.yaml`:

```yaml
reranker:
  provider: sentence-transformers
  model: cross-encoder/ms-marco-MiniLM-L-6-v2
  params:
    batch_size: 32
```

### Graceful Degradation

If the reranker fails (model unavailable, timeout, etc.), the system automatically falls back to Stage 1 results. This ensures queries never fail due to reranking issues.

### Response Fields

When reranking is enabled, query results include additional fields:

- `rerank_score`: The cross-encoder relevance score
- `original_rank`: The position before reranking (1-indexed)

Example response:
```json
{
  "results": [
    {
      "text": "Document content...",
      "source": "docs/guide.md",
      "score": 0.95,
      "rerank_score": 0.95,
      "original_rank": 5,
      "chunk_id": "chunk_abc123"
    }
  ]
}
```

## Development Installation

```bash
cd agent-brain-server
poetry install
```

### Configuration

Copy the environment template and configure:

```bash
cp ../.env.example .env
# Edit .env with your API keys
```

Required environment variables:
- `OPENAI_API_KEY`: Your OpenAI API key for embeddings
- `ANTHROPIC_API_KEY`: Your Anthropic API key for summarization

### Running the Server

```bash
# Development mode
poetry run uvicorn agent_brain_server.api.main:app --reload

# Or use the entry point
poetry run agent-brain-serve
```

### API Documentation

Once running, visit:
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- OpenAPI JSON: http://127.0.0.1:8000/openapi.json

## API Endpoints

### Health

- `GET /health` - Server health status
- `GET /health/status` - Detailed indexing status

### Indexing

- `POST /index` - Start indexing documents from a folder
- `POST /index/add` - Add documents to existing index
- `DELETE /index` - Reset the index

### Querying

- `POST /query` - Semantic search query
- `GET /query/count` - Get indexed document count

## Example Usage

### Index Documents

```bash
curl -X POST http://localhost:8000/index \
  -H "Content-Type: application/json" \
  -d '{"folder_path": "/path/to/docs"}'
```

### Query Documents

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How do I configure authentication?", "top_k": 5}'
```

## Architecture

```
agent_brain_server/
├── api/
│   ├── main.py           # FastAPI application
│   └── routers/          # Endpoint handlers
├── config/
│   └── settings.py       # Configuration management
├── models/               # Pydantic request/response models
├── indexing/
│   ├── document_loader.py  # Document loading
│   ├── chunking.py         # Text chunking
│   └── embedding.py        # Embedding generation
├── services/
│   ├── indexing_service.py # Indexing orchestration
│   └── query_service.py    # Query execution
└── storage/
    └── vector_store.py     # Chroma vector store
```

## Development

### Running Tests

```bash
poetry run pytest
```

### Code Formatting

```bash
poetry run black agent_brain_server/
poetry run ruff check agent_brain_server/
```

### Type Checking

```bash
poetry run mypy agent_brain_server/
```

## Documentation

- [User Guide](https://github.com/SpillwaveSolutions/agent-brain/wiki/User-Guide) - Getting started and usage
- [Developer Guide](https://github.com/SpillwaveSolutions/agent-brain/wiki/Developer-Guide) - Contributing and development
- [API Reference](https://github.com/SpillwaveSolutions/agent-brain/wiki/API-Reference) - Full API documentation

## Release Information

- **Current Version**: See [pyproject.toml](./pyproject.toml)
- **Release Notes**: [GitHub Releases](https://github.com/SpillwaveSolutions/agent-brain/releases)
- **Changelog**: [Latest Release](https://github.com/SpillwaveSolutions/agent-brain/releases/latest)

## Related Packages

- [agent-brain-cli](https://pypi.org/project/agent-brain-cli/) - Command-line interface for Agent Brain

## License

MIT
