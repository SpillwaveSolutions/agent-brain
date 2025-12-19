# Doc-Serve

A RAG-based (Retrieval-Augmented Generation) document indexing and semantic search system. Doc-Serve enables AI assistants and applications to query domain-specific documentation using natural language.

## Overview

Doc-Serve is a monorepo containing three packages:

| Package | Description |
|---------|-------------|
| **doc-serve-server** | FastAPI REST API for document indexing and semantic search |
| **doc-svr-ctl** | Command-line interface for managing the server |
| **doc-serve-skill** | Claude Code skill for AI-powered documentation queries |

## Code Ingestion & Search

Doc-Serve now supports unified search across documentation and source code:

- **10 Programming Languages**: Python, TypeScript, JavaScript, Java, Kotlin, C, C++, Go, Rust, Swift
- **AST-Aware Chunking**: Intelligent code parsing and chunking using tree-sitter
- **Cross-Reference Queries**: Search across docs and code simultaneously
- **Language Filtering**: Filter results by programming language
- **Source Type Filtering**: Separate results by documentation vs. source code
- **LLM Code Summaries**: AI-generated summaries improve semantic search quality

### Example: Code-Aware Search
```bash
# Index both docs and code
doc-svr-ctl index ./my-project --include-code

# Search across everything
doc-svr-ctl query "authentication implementation"

# Filter by code only
doc-svr-ctl query "API endpoints" --source-types code --languages python
```

## Features

- **Code Ingestion**: Index and search across documentation AND source code
- **Cross-Reference Search**: Unified queries across docs and code with intelligent filtering
- **Language-Aware Processing**: AST-based chunking for 10+ programming languages
- **Hybrid Search**: Combines semantic meaning (Vector) with exact keyword matching (BM25)
- **Semantic Search**: Natural language queries using OpenAI embeddings
- **Keyword Search**: Precise term matching for technical documentation
- **Advanced Filtering**: Filter by source type (doc/code) and programming language
- **Vector Store**: ChromaDB for efficient similarity search
- **Context-Aware Chunking**: Intelligent document and code splitting with overlap
- **LLM Summaries**: AI-generated summaries for code chunks improve semantic search
- **REST API**: Full OpenAPI-documented REST interface
- **CLI Tool**: Comprehensive command-line management
- **Claude Integration**: Native Claude Code skill for AI workflows

## Quick Start

### Prerequisites

- Python 3.10+
- [Poetry](https://python-poetry.org/docs/#installation) (dependency management)
- [Task](https://taskfile.dev/installation/) (task runner)
- OpenAI API key
- Anthropic API key

### Installation

```bash
# Clone the repository
git clone https://github.com/spillwave/doc-serve.git
cd doc-serve

# Install all dependencies
task install

# List available commands
task --list
```

### Configuration

```bash
# Copy the example environment file
cp doc-serve-server/.env.example doc-serve-server/.env

# Edit and add your API keys
# OPENAI_API_KEY=sk-your-openai-key
# ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
```

### Running

```bash
# Start development server
task dev

# Check server status
task status

# Open API docs in browser
task docs
```

The server starts at `http://127.0.0.1:8000` with interactive docs at `/docs`.

### Using the CLI

```bash
# Check server status
task status

# Index documents
task index -- /path/to/documents

# Query the index
task query -- "how to configure authentication"

# Reset the index
task reset
```

## Task Commands

All operations use [Task](https://taskfile.dev). Run `task --list` to see all available commands.

| Command | Description |
|---------|-------------|
| `task install` | Install all dependencies |
| `task dev` | Start development server |
| `task test` | Run all tests |
| `task before-push` | Run all checks before pushing |
| `task build` | Build all packages |

## Architecture

```
doc-serve/
├── Taskfile.yml          # Root task runner
├── doc-serve-server/     # FastAPI server
│   ├── Taskfile.yml
│   └── doc_serve_server/
│       ├── api/          # REST endpoints
│       ├── config/       # Settings management
│       ├── indexing/     # Document processing
│       ├── models/       # Pydantic models
│       ├── services/     # Business logic
│       └── storage/      # Vector store
├── doc-svr-ctl/          # CLI tool
│   ├── Taskfile.yml
│   └── doc_svr_ctl/
│       ├── client/       # API client
│       └── commands/     # CLI commands
├── doc-serve-skill/      # Claude skill
│   └── doc-serve/
│       └── SKILL.md      # Skill definition
└── docs/                 # Documentation
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/health/status` | GET | Detailed indexing status |
| `/query` | POST | Semantic search |
| `/query/count` | GET | Document count |
| `/index` | POST | Start indexing |
| `/index/add` | POST | Add documents incrementally |
| `/index` | DELETE | Clear index |

## Documentation

- [User Guide](docs/USER_GUIDE.md) - How to use Doc-Serve
- [Developer Guide](docs/DEVELOPERS_GUIDE.md) - Setup and contribution guide
- [API Reference](doc-serve-skill/doc-serve/references/api_reference.md) - Full API documentation
- [Product Roadmap](docs/roadmaps/product-roadmap.md) - Future plans and features
- [Spec Mapping](docs/spec_mapping.md) - Mapping of specs to features


## Technology Stack

- **Task Runner**: [Task](https://taskfile.dev)
- **Server**: FastAPI + Uvicorn
- **Vector Store**: ChromaDB
- **Embeddings**: OpenAI text-embedding-3-large
- **Summarization**: Claude Haiku
- **Indexing**: LlamaIndex
- **Code Parsing**: Tree-sitter (AST-aware chunking)
- **CLI**: Click + Rich
- **Build System**: Poetry

## Contributing

See the [Developer Guide](docs/DEVELOPERS_GUIDE.md) for setup instructions.

**Before pushing changes**, always run:

```bash
task before-push
```

## License

MIT License - see LICENSE file for details.
