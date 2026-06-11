---
last_validated: 2026-06-10
---

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

| Package | Path | PyPI Name | Description |
|---------|------|-----------|-------------|
| agent-brain-server | `agent-brain-server/` | `agent-brain-rag` | FastAPI REST API server |
| agent-brain-cli | `agent-brain-cli/` | `agent-brain-cli` | CLI management tool |
| agent-brain-uds | `agent-brain-uds/` | `agent-brain-uds` | Unix domain socket transport |
| agent-brain-mcp | `agent-brain-mcp/` | `agent-brain-ag-mcp` | MCP server (tools, resources, prompts) |
| agent-brain-skill | `agent-brain-skill/` | — | Claude Code skill |
| agent-brain-plugin | `agent-brain-plugin/` | — | Claude Code plugin (commands, agents, skills) |

**PyPI rename note**: the MCP package publishes as `agent-brain-ag-mcp` (renamed in v10.1.2 — PyPI typosquatting filter rejected the original name). The console script is still `agent-brain-mcp` and the import path is still `agent_brain_mcp`.

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

### Known Issues

- **Run `task` commands from the repo root**, not from inside a package directory — per-package cwd causes scope leaks across the monorepo's shared `Taskfile.yml` includes.
- **Flaky sentence-transformer warm-up test**: the first model-download/warm-up assertion can intermittently fail on a cold cache; re-run `task test` once before assuming a real regression.

## Project Structure

```
agent-brain/                          # Monorepo root (Taskfile orchestrates all packages)
├── agent-brain-server/               # FastAPI server  (PyPI: agent-brain-rag)
│   ├── agent_brain_server/
│   │   ├── api/                      # REST endpoints (main.py + routers/)
│   │   ├── config/                   # Settings (Pydantic)
│   │   ├── indexing/                 # AST-aware document processing
│   │   ├── models/                   # Request/response models
│   │   ├── services/                 # Business logic (indexing, query)
│   │   └── storage/                  # ChromaDB integration
│   └── tests/
├── agent-brain-cli/                  # CLI tool  (PyPI: agent-brain-cli)
│   ├── agent_brain_cli/
│   │   ├── cli.py                    # Main entry point
│   │   ├── client/                   # Transport clients (HTTP, UDS, MCP)
│   │   └── commands/                 # CLI command implementations
│   └── tests/
├── agent-brain-uds/                  # Unix domain socket transport  (PyPI: agent-brain-uds)
│   ├── agent_brain_uds/
│   └── tests/
├── agent-brain-mcp/                  # MCP server  (PyPI: agent-brain-ag-mcp; import: agent_brain_mcp)
│   ├── agent_brain_mcp/              # Tools, resources, prompts; stdio + Streamable HTTP
│   └── tests/
├── agent-brain-plugin/               # Claude Code plugin (commands, agents, skills) — markdown
│   ├── commands/  agents/  skills/
│   └── plugin.json                   # version owned by the release process
├── agent-brain-skill/                # Standalone Claude Code skill — markdown
│   └── SKILL.md
├── Taskfile.yml                      # Monorepo task runner (run `task` from repo root)
├── scripts/                          # Release, lock-guard, quick-start validation
└── docs/                             # Documentation
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

### Project Commands

| Command | Description |
|---------|-------------|
| `agent-brain init` | Initialize a new Agent Brain project (creates .agent-brain/) |
| `agent-brain start` | Start an Agent Brain server for this project |
| `agent-brain stop` | Stop the Agent Brain server for this project |
| `agent-brain list` | List all running Agent Brain instances |

### Server Commands

| Command | Description |
|---------|-------------|
| `agent-brain status` | Check Agent Brain server status and health |
| `agent-brain query "text"` | Search indexed documents |
| `agent-brain index /path` | Index documents from a folder (queued) |
| `agent-brain inject /path --script enrich.py` | Index documents with content injection |
| `agent-brain reset --yes` | Clear all indexed documents |
| `agent-brain doctor` | Diagnose installation, configuration, and server state |

### MCP & Transport Commands

| Command | Description |
|---------|-------------|
| `agent-brain mcp start` | Start the MCP server (`agent-brain-mcp`) for this project |
| `agent-brain mcp stop` | Stop the MCP server |
| `agent-brain prompt <name>` | Render a registered MCP prompt (e.g. `find-callers`, `explain-architecture`) |
| `agent-brain resources list` | List available `corpus://` MCP resources |
| `agent-brain resources read <uri>` | Read a `corpus://` resource (e.g. `corpus://status`) |

Transport is selectable via the global `--transport {auto,http,uds,mcp}` flag (or `AGENT_BRAIN_TRANSPORT`); `auto` prefers UDS and falls back to HTTP. The MCP package publishes to PyPI as `agent-brain-ag-mcp` but the console script stays `agent-brain-mcp`.

### Job Queue Commands

| Command | Description |
|---------|-------------|
| `agent-brain jobs` | List all jobs in queue |
| `agent-brain jobs --watch` | Watch queue with live updates (refresh every 3s) |
| `agent-brain jobs JOB_ID` | Show job details |
| `agent-brain jobs JOB_ID --cancel` | Cancel a job |

### Cache Commands

| Command | Description |
|---------|-------------|
| `agent-brain cache status` | Show embedding cache statistics |
| `agent-brain cache clear` | Clear all cached embeddings |

### Folder Commands

| Command | Description |
|---------|-------------|
| `agent-brain folders list` | List all indexed folders with chunk counts |
| `agent-brain folders add /path` | Index a new folder (alias for index) |
| `agent-brain folders remove /path` | Remove all indexed chunks for a folder |

### File Type Commands

| Command | Description |
|---------|-------------|
| `agent-brain types list` | List available file type presets and extensions |

### Configuration Commands

| Command | Description |
|---------|-------------|
| `agent-brain config show` | Display active provider configuration |
| `agent-brain config path` | Show config file location |

### Runtime Installation Commands

| Command | Description |
|---------|-------------|
| `agent-brain install-agent --agent claude` | Install for Claude Code |
| `agent-brain install-agent --agent opencode` | Install for OpenCode |
| `agent-brain install-agent --agent gemini` | Install for Gemini CLI |
| `agent-brain install-agent --agent codex` | Install for Codex (+ AGENTS.md) |
| `agent-brain install-agent --agent skill-runtime --dir <path>` | Install for any skill-based runtime |
| `agent-brain install-agent --agent <runtime> --dry-run` | Preview installation |
| `agent-brain install-agent --agent <runtime> --global` | Install globally |

### Other Commands

| Command | Description |
|---------|-------------|
| `agent-brain uninstall` | Remove all global Agent Brain data and stop running servers |

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
| `AGENT_BRAIN_STATE_DIR` | No | - | Override state directory for multi-instance |
| `AGENT_BRAIN_MODE` | No | `project` | Instance mode: 'project' or 'shared' |
| `AGENT_BRAIN_STRICT_MODE` | No | `false` | Fail on critical validation errors |
| `AGENT_BRAIN_STORAGE_BACKEND` | No | - | Override YAML storage config ('chroma' or 'postgres') |

### CLI

| Variable | Description |
|----------|-------------|
| `AGENT_BRAIN_URL` | Server URL (default: http://127.0.0.1:8000) |

## Security Notes

- **Never commit** `.env` files or API keys
- `.env.example` files are safe to commit (no real keys)
- Check `.gitignore` excludes all sensitive files

## Documentation

- [User Guide](docs/USER_GUIDE.md) - End-user documentation
- [Developer Guide](docs/DEVELOPERS_GUIDE.md) - Development setup
- [API Reference](docs/API_REFERENCE.md) - Full API docs
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
