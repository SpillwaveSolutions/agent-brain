# Doc-Serve Server

RAG-based document indexing and semantic search REST API service.

## Features

- **Document Indexing**: Load and index documents from folders (PDF, Markdown, TXT, DOCX, HTML)
- **Context-Aware Chunking**: Smart text splitting with configurable chunk sizes and overlap
- **Semantic Search**: Query indexed documents using natural language
- **OpenAI Embeddings**: Uses `text-embedding-3-large` for high-quality embeddings
- **Chroma Vector Store**: Persistent, thread-safe vector database
- **FastAPI**: Modern, high-performance REST API with OpenAPI documentation

## Quick Start

### Prerequisites

- Python 3.10+
- Poetry
- OpenAI API key

### Installation

```bash
cd doc-serve-server
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

### Running the Server

```bash
# Development mode
poetry run uvicorn doc_serve_server.api.main:app --reload

# Or use the entry point
poetry run doc-serve
```

The server will start at `http://127.0.0.1:8000`.

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
doc_serve_server/
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
poetry run black doc_serve_server/
poetry run ruff check doc_serve_server/
```

### Type Checking

```bash
poetry run mypy doc_serve_server/
```

## License

MIT
