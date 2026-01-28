# Doc-Serve Development Guidelines

Instructions for Claude Code when working on this repository.

## Project Overview

Doc-Serve is a RAG-based document indexing and semantic search system. It's a monorepo containing:

| Package | Path | Description |
|---------|------|-------------|
| doc-serve-server | `doc-serve-server/` | FastAPI REST API server |
| doc-svr-ctl | `doc-svr-ctl/` | CLI management tool |
| doc-serve-skill | `doc-serve-skill/` | Claude Code skill |

## Technology Stack

- **Python**: 3.10+
- **Build System**: Poetry
- **Server**: FastAPI + Uvicorn
- **CLI**: Click + Rich
- **Vector Store**: ChromaDB
- **Embeddings**: OpenAI text-embedding-3-large
- **Indexing**: LlamaIndex

## Build and Test Commands

### doc-serve-server

```bash
cd doc-serve-server
poetry install                    # Install dependencies
poetry run doc-serve              # Run server
poetry run pytest                 # Run tests
poetry run pytest --cov=doc_serve_server       # Tests with coverage
poetry run mypy doc_serve_server               # Type checking
poetry run ruff check doc_serve_server         # Linting
poetry run black doc_serve_server              # Format code
```

### doc-svr-ctl

```bash
cd doc-svr-ctl
poetry install                    # Install dependencies
poetry run doc-svr-ctl --help     # Show CLI help
poetry run pytest                 # Run tests
poetry run mypy doc_serve_server               # Type checking
poetry run ruff check doc_serve_server         # Linting
poetry run black doc_serve_server              # Format code
```

### Full Quality Check

```bash
# Run from package directory
poetry run black doc_serve_server tests && poetry run ruff check doc_serve_server tests && poetry run mypy doc_serve_server && poetry run pytest
```

## Project Structure

```
doc-serve/
├── doc-serve-server/           # FastAPI server
│   ├── doc_serve_server/           # FastAPI server
│   │   ├── api/                # REST endpoints
│   │   │   ├── main.py         # App entry point
│   │   │   └── routers/        # Route handlers
│   │   ├── config/             # Settings (Pydantic)
│   │   ├── indexing/           # Document processing
│   │   ├── models/             # Request/response models
│   │   ├── services/           # Business logic
│   │   └── storage/            # ChromaDB integration
│   └── tests/
├── doc-svr-ctl/                # CLI tool
│   ├── doc_serve_server/           # FastAPI server
│   │   ├── cli.py              # Main entry point
│   │   ├── client/             # API client
│   │   └── commands/           # CLI commands
│   └── tests/
├── doc-serve-skill/            # Claude skill
│   └── doc-serve/
│       └── SKILL.md
└── docs/                       # Documentation
```

## Code Style

### Python Standards
- **Formatter**: Black (line length 88)
- **Linter**: Ruff
- **Type Checker**: mypy (strict mode)
- **Type Hints**: Required for all function signatures

### Style Guidelines
1. Use Google-style docstrings
2. Sort imports with Ruff/isort
3. Type hint all function parameters and returns
4. Keep functions focused and testable

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/health/status` | GET | Indexing status |
| `/query` | POST | Semantic search |
| `/query/count` | GET | Document count |
| `/index` | POST | Start indexing |
| `/index/add` | POST | Add documents |
| `/index` | DELETE | Clear index |

## CLI Commands

| Command | Description |
|---------|-------------|
| `doc-svr-ctl status` | Check server status |
| `doc-svr-ctl query "text"` | Search documents |
| `doc-svr-ctl index /path` | Index documents |
| `doc-svr-ctl reset --yes` | Clear index |

## Environment Variables

### Server (doc-serve-server/.env)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API key for embeddings |
| `ANTHROPIC_API_KEY` | Yes | - | Anthropic API key for summarization |
| `EMBEDDING_MODEL` | No | `text-embedding-3-large` | OpenAI embedding model |
| `CLAUDE_MODEL` | No | `claude-3-5-haiku-20241022` | Claude summarization model |
| `API_HOST` | No | `127.0.0.1` | Server host |
| `API_PORT` | No | `8000` | Server port |
| `DEBUG` | No | `false` | Debug mode |

### CLI

| Variable | Description |
|----------|-------------|
| `DOC_SERVE_URL` | Server URL (default: http://127.0.0.1:8000) |

## Security Notes

- **Never commit** `.env` files or API keys
- `.env.example` files are safe to commit (no real keys)
- Check `.gitignore` excludes all sensitive files

## Documentation

- [User Guide](docs/USER_GUIDE.md) - End-user documentation
- [Developer Guide](docs/DEVELOPERS_GUIDE.md) - Development setup
- [API Reference](doc-serve-skill/doc-serve/references/api_reference.md) - Full API docs
- [Original Spec](docs/ORIGINAL_SPEC.md) - Project specification

## Quality Assurance

**IMPORTANT**: After ANY major code changes (including but not limited to):
- Adding new features or functionality
- Refactoring existing code
- Fixing bugs
- Modifying core business logic
- Updating dependencies or configurations

You MUST:
1. Always run `task pr-qa-gate` before checking in or pushing changes.
2. Always run `task pr-qa-gate` when checking project status or SDD status.
3. Use the `qa-enforcer` agent to enforce test coverage and quality standards.
4. After making code changes, run:

```bash
task before-push
```

This runs format, lint, typecheck, and tests with coverage.

## Git Workflow

- Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`
- Create feature branches from main
- **MANDATORY**: Run `task before-push` before pushing to any branch
- PRs will fail CI if code coverage is below 50%

## Pre-Push Requirement

**IMPORTANT**: Before pushing any changes to a branch, you MUST run:

```bash
task before-push
```

This is a mandatory step that ensures:
1. Code is properly formatted (Black)
2. No linting errors (Ruff)
3. Type checking passes (mypy)
4. All tests pass with coverage report

Do NOT push code that fails `task before-push`.

## Active Technologies
- Python 3.10+ + FastAPI, LlamaIndex, ChromaDB, OpenAI, rank-bm25 (100-bm25-hybrid-retrieval)
- ChromaDB (Vector Store), Local Persistent BM25 Index (LlamaIndex) (100-bm25-hybrid-retrieval)
- Python 3.10+ + LlamaIndex (CodeSplitter, SummaryExtractor), tree-sitter parsers, ChromaDB (101-code-ingestion)
- ChromaDB (unified vector store), Disk-based BM25 index (101-code-ingestion)
- Python 3.10+ + LlamaIndex (CodeSplitter, SummaryExtractor), tree-sitter (AST parsing), OpenAI/Anthropic (embeddings/summaries) (101-code-ingestion)
- ChromaDB vector store (existing) (101-code-ingestion)
- Python 3.10+ + FastAPI, uvicorn, Pydantic, Click, ChromaDB, LlamaIndex (109-multi-instance-architecture)
- ChromaDB (vector), disk-based BM25 index, LlamaIndex persistence (109-multi-instance-architecture)

## Recent Changes
- 100-bm25-hybrid-retrieval: Added Python 3.10+ + FastAPI, LlamaIndex, ChromaDB, OpenAI, rank-bm25
