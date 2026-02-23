# Agent Brain Development Guidelines

Instructions for Claude Code when working on this repository.

Planning rule: after any planning step, save the plan to `docs/plans/<name>.md` before doing work.

## CRITICAL: NEVER PUSH WITHOUT TESTING

**ABSOLUTE RULE: You MUST run `task before-push` BEFORE EVERY `git push`. NO EXCEPTIONS.**

```bash
task before-push
```

This runs format, lint, typecheck, and tests. **Do NOT push code that fails this check.**

**Why this matters:** PRs trigger expensive CI pipelines. Pushing broken code wastes time and money. Every single push failure that could have been caught locally is unacceptable.

**Enforcement checklist (verify ALL pass before pushing):**
1. `task before-push` exits with code 0
2. No lint errors (Ruff)
3. No type errors (mypy)
4. All tests pass
5. Code is formatted (Black)

**If `task before-push` fails, DO NOT push. Fix the issues first.**

## Project Overview

Agent Brain is a RAG-based document indexing and semantic search system. It's a monorepo containing:

| Package | Path | Description |
|---------|------|-------------|
| agent-brain-server | `agent-brain-server/` | FastAPI REST API server |
| agent-brain-cli | `agent-brain-cli/` | CLI management tool |
| agent-brain-skill | `agent-brain-skill/` | Claude Code skill |
| agent-brain-plugin | `agent-brain-plugin/` | Claude Code plugin (commands, agents, skills) |

## Technology Stack

- **Python**: 3.10+
- **Build System**: Poetry
- **Package Installer**: uv (preferred over pip)
- **Server**: FastAPI + Uvicorn
- **CLI**: Click + Rich
- **Vector Store**: ChromaDB
- **Embeddings**: OpenAI text-embedding-3-large
- **Indexing**: LlamaIndex

## Package Installation

**IMPORTANT**: Always use `uv` instead of `pip` for installing packages. It's faster and handles dependencies better.

```bash
# Build packages
cd agent-brain-server && poetry build
cd agent-brain-cli && poetry build

# Install with uv (NOT pip)
uv pip install dist/agent_brain_rag-*.whl --force-reinstall
uv pip install dist/agent_brain_cli-*.whl --force-reinstall

# Deploy plugin to cache
cp -r agent-brain-plugin/* ~/.claude/plugins/agent-brain/
```

## Build and Test Commands

### agent-brain-server

```bash
cd agent-brain-server
poetry install                    # Install dependencies
poetry run agent-brain-serve      # Run server
poetry run pytest                 # Run tests
poetry run pytest --cov=agent_brain_server       # Tests with coverage
poetry run mypy agent_brain_server               # Type checking
poetry run ruff check agent_brain_server         # Linting
poetry run black agent_brain_server              # Format code
```

### agent-brain-cli

```bash
cd agent-brain-cli
poetry install                    # Install dependencies
poetry run agent-brain --help     # Show CLI help
poetry run pytest                 # Run tests
poetry run mypy agent_brain_cli               # Type checking
poetry run ruff check agent_brain_cli         # Linting
poetry run black agent_brain_cli              # Format code
```

### Full Quality Check

```bash
# Run from package directory
poetry run black agent_brain_server tests && poetry run ruff check agent_brain_server tests && poetry run mypy agent_brain_server && poetry run pytest
```

## Project Structure

```
doc-serve/
├── agent-brain-server/           # FastAPI server
│   ├── agent_brain_server/           # FastAPI server
│   │   ├── api/                # REST endpoints
│   │   │   ├── main.py         # App entry point
│   │   │   └── routers/        # Route handlers
│   │   ├── config/             # Settings (Pydantic)
│   │   ├── indexing/           # Document processing
│   │   ├── models/             # Request/response models
│   │   ├── services/           # Business logic
│   │   └── storage/            # ChromaDB integration
│   └── tests/
├── agent-brain-cli/                # CLI tool
│   ├── agent_brain_cli/           # CLI package
│   │   ├── cli.py              # Main entry point
│   │   ├── client/             # API client
│   │   └── commands/           # CLI commands
│   └── tests/
├── agent-brain-skill/            # Claude skill
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

### Multi-Instance Commands (new)

| Command | Description |
|---------|-------------|
| `agent-brain init` | Initialize project for Agent Brain (creates .claude/agent-brain/) |
| `agent-brain start` | Start Agent Brain server for current project |
| `agent-brain stop` | Stop the running server |
| `agent-brain list` | List all running Agent Brain instances |

### Data Commands

| Command | Description |
|---------|-------------|
| `agent-brain status` | Check server status |
| `agent-brain query "text"` | Search documents |
| `agent-brain index /path` | Index documents (queued) |
| `agent-brain index /path --force` | Index, bypass deduplication |
| `agent-brain reset --yes` | Clear index |

### Job Queue Commands (new)

| Command | Description |
|---------|-------------|
| `agent-brain jobs` | List all jobs in queue |
| `agent-brain jobs --watch` | Watch queue with live updates |
| `agent-brain jobs JOB_ID` | Show job details |
| `agent-brain jobs JOB_ID --cancel` | Cancel a job |

## Environment Variables

### Server (agent-brain-server/.env)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API key for embeddings |
| `ANTHROPIC_API_KEY` | Yes | - | Anthropic API key for summarization |
| `EMBEDDING_MODEL` | No | `text-embedding-3-large` | OpenAI embedding model |
| `CLAUDE_MODEL` | No | `claude-haiku-4-5-20251001` | Claude summarization model |
| `API_HOST` | No | `127.0.0.1` | Server host |
| `API_PORT` | No | `8000` | Server port |
| `DEBUG` | No | `false` | Debug mode |
| `DOC_SERVE_STATE_DIR` | No | - | Override state directory for multi-instance |
| `DOC_SERVE_MODE` | No | `project` | Instance mode: 'project' or 'shared' |

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
- [API Reference](agent-brain-skill/doc-serve/references/api_reference.md) - Full API docs
- [Original Spec](docs/ORIGINAL_SPEC.md) - Project specification

## Quality Assurance

**NEVER PUSH WITHOUT TESTING. NEVER. NOT EVEN "JUST A SMALL CHANGE".**

After ANY code changes — no matter how small — you MUST:
1. Run `task before-push` and verify it passes with exit code 0
2. Run `task pr-qa-gate` before creating or updating PRs
3. Fix ALL errors before pushing — do not push hoping CI will catch it

```bash
task before-push    # MUST pass before ANY push
task pr-qa-gate     # MUST pass before ANY PR
```

**MANDATORY**: Any feature or task is not considered done unless `task pr-qa-gate` passes successfully.

## Git Workflow

- Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`
- Create feature branches from main
- **MANDATORY**: Run `task before-push` before pushing to any branch
- PRs will fail CI if code coverage is below 50%

## Pre-Push Requirement (MANDATORY — READ THIS)

**NEVER PUSH CODE WITHOUT RUNNING `task before-push` FIRST.**

```bash
task before-push
```

This is a mandatory step that ensures:
1. Code is properly formatted (Black)
2. No linting errors (Ruff)
3. Type checking passes (mypy)
4. All tests pass with coverage report

**If it fails, FIX IT. Then run it again. Only push when it passes.**

**Common failures to watch for:**
- Line too long (>88 chars) — run `black` to auto-fix
- Missing type stubs — install with `pip install types-XXX`
- Import order — run `ruff check --fix` to auto-fix

## Active Technologies
- Python 3.10+ + FastAPI, LlamaIndex, ChromaDB, OpenAI, rank-bm25 (100-bm25-hybrid-retrieval)
- ChromaDB (Vector Store), Local Persistent BM25 Index (LlamaIndex) (100-bm25-hybrid-retrieval)
- Python 3.10+ + LlamaIndex (CodeSplitter, SummaryExtractor), tree-sitter parsers, ChromaDB (101-code-ingestion)
- ChromaDB (unified vector store), Disk-based BM25 index (101-code-ingestion)
- Python 3.10+ + LlamaIndex (CodeSplitter, SummaryExtractor), tree-sitter (AST parsing), OpenAI/Anthropic (embeddings/summaries) (101-code-ingestion)
- ChromaDB vector store (existing) (101-code-ingestion)
- Python 3.10+ + FastAPI, uvicorn, Pydantic, Click, ChromaDB, LlamaIndex (109-multi-instance-architecture)
- ChromaDB (vector), disk-based BM25 index, LlamaIndex persistence (109-multi-instance-architecture)
- Python 3.10+ + Poetry (packaging), Click (CLI), FastAPI (server) (112-agent-brain-naming)
- N/A (naming changes only) (112-agent-brain-naming)
- Python 3.10+ (existing: ^3.10 in pyproject.toml) + FastAPI, LlamaIndex (llama-index-core ^0.14.0), ChromaDB, langextract (new), llama-index-graph-stores-kuzu (optional) (113-graphrag-integration)
- ChromaDB (vector), disk-based BM25 index (existing), SimplePropertyGraphStore/Kuzu (new graph storage) (113-graphrag-integration)
- Markdown (Claude Code plugin format) + Claude Code plugin system, agent-brain-cli v1.2.0+, agent-brain-rag v1.2.0+ (114-agent-brain-plugin)
- N/A (plugin is markdown files only) (114-agent-brain-plugin)
- Python 3.10+ (existing: ^3.10 in pyproject.toml) + FastAPI, LlamaIndex, Pydantic, httpx (async HTTP), anthropic, openai, google-generativeai (new) (103-pluggable-providers)

## Recent Changes
- 100-bm25-hybrid-retrieval: Added Python 3.10+ + FastAPI, LlamaIndex, ChromaDB, OpenAI, rank-bm25
