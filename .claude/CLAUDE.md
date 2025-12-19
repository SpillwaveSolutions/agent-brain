# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the Doc-Serve repository.

## Repository Status

Doc-Serve is a fully implemented RAG-based document indexing and semantic search system. The repository contains:

- **doc-serve-server**: FastAPI REST API server with AST-aware code ingestion
- **doc-svr-ctl**: CLI management tool
- **doc-serve-skill**: Claude Code skill integration
- **Comprehensive test suite**: Unit, integration, and end-to-end tests
- **Full documentation**: User guides, developer guides, and API references

## Project Architecture

Doc-Serve implements a RAG (Retrieval-Augmented Generation) system with:

- **Multi-language code ingestion**: AST-based parsing for Python, TypeScript, JavaScript, Java, Go, Rust, C, C++
- **Hybrid search**: Combines BM25 keyword matching with semantic similarity
- **Vector storage**: ChromaDB for efficient similarity search
- **LLM integration**: OpenAI embeddings and Anthropic Claude for summarization

## Build and Development Commands

### Quick Setup
```bash
# Install all dependencies
task install

# Run full quality check
task before-push

# Run end-to-end validation
./scripts/quick_start_guide.sh
```

### Individual Package Commands

**Server (doc-serve-server)**:
```bash
cd doc-serve-server
poetry install                    # Install dependencies
poetry run doc-serve              # Run server
poetry run pytest                 # Run tests
poetry run pytest --cov=doc_serve_server  # Tests with coverage
poetry run mypy doc_serve_server # Type checking
poetry run ruff check doc_serve_server    # Linting
poetry run black doc_serve_server         # Format code
```

**CLI (doc-svr-ctl)**:
```bash
cd doc-svr-ctl
poetry install                    # Install dependencies
poetry run doc-svr-ctl --help     # Show CLI help
poetry run pytest                 # Run tests
poetry run mypy doc_svr_ctl       # Type checking
poetry run ruff check doc_svr_ctl # Linting
poetry run black doc_svr_ctl      # Format code
```

### Monorepo Commands
```bash
# Install all packages
task install

# Run all tests
task test

# Run full quality check (format, lint, typecheck, test)
task before-push

# Run PR quality gate
task pr-qa-gate
```

## Quality Assurance Protocol

**MANDATORY**: Before pushing any changes, you MUST run:

```bash
task before-push
```

This ensures:
1. Code is properly formatted (Black)
2. No linting errors (Ruff)
3. Type checking passes (mypy)
4. All tests pass with coverage report (>50%)

**MANDATORY**: Any feature or task is not considered done unless `task pr-qa-gate` passes successfully.

### End-to-End Validation

Before releasing any version, you MUST run:

```bash
./scripts/quick_start_guide.sh
```

This validates the complete workflow from server startup to advanced querying.

## Key Files to Understand

### Architecture
- `doc-serve-server/doc_serve_server/api/main.py` - FastAPI server entry point
- `doc-serve-server/doc_serve_server/config/settings.py` - Configuration
- `doc-serve-server/doc_serve_server/services/indexing_service.py` - AST-based ingestion
- `doc-serve-server/doc_serve_server/services/query_service.py` - Hybrid search

### CLI
- `doc-svr-ctl/doc_svr_ctl/cli.py` - CLI entry point
- `doc-svr-ctl/doc_svr_ctl/commands/` - CLI command implementations

### Testing
- `scripts/quick_start_guide.sh` - End-to-end validation script
- `e2e/integration/test_full_workflow.py` - Integration tests
- `AGENTS.md` - AI agent guidelines for this project

## Git Workflow

- Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`
- Create feature branches from main
- **MANDATORY**: Run `task before-push` before pushing to any branch
- PRs require end-to-end validation with `scripts/quick_start_guide.sh`

## Environment Setup

Required environment variables:
- `OPENAI_API_KEY` - For embeddings (text-embedding-3-large)
- `ANTHROPIC_API_KEY` - For code summarization (Claude Haiku)

## Notes

This is a production-ready Doc-Serve implementation with comprehensive testing and documentation. Always run the quality checks and end-to-end validation before making changes.