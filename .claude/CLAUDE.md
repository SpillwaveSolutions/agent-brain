# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the Agent Brain repository.

## CRITICAL: NEVER PUSH WITHOUT TESTING

**ABSOLUTE RULE: You MUST run `task before-push` BEFORE EVERY `git push`. NO EXCEPTIONS.**

```bash
task before-push
```

This runs format, lint, typecheck, and tests. **Do NOT push code that fails this check.**

**Why this matters:** PRs trigger expensive CI pipelines. Pushing broken code wastes time and money. Every push failure that could have been caught locally is unacceptable.

**Enforcement checklist (verify ALL pass before pushing):**
1. `task before-push` exits with code 0
2. No lint errors (Ruff)
3. No type errors (mypy)
4. All tests pass
5. Code is formatted (Black)

**If `task before-push` fails, DO NOT push. Fix the issues first.**

## Repository Status

Agent Brain is a fully implemented RAG-based document indexing and semantic search system. The repository contains:

- **agent-brain-server**: FastAPI REST API server with AST-aware code ingestion
- **agent-brain-cli**: CLI management tool
- **agent-brain-skill**: Claude Code skill integration
- **Comprehensive test suite**: Unit, integration, and end-to-end tests
- **Full documentation**: User guides, developer guides, and API references

## Project Architecture

Agent Brain implements a RAG (Retrieval-Augmented Generation) system with:

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

**Server (agent-brain-server)**:
```bash
cd agent-brain-server
poetry install                    # Install dependencies
poetry run agent-brain-serve      # Run server
poetry run pytest                 # Run tests
poetry run pytest --cov=agent_brain_server  # Tests with coverage
poetry run mypy agent_brain_server # Type checking
poetry run ruff check agent_brain_server    # Linting
poetry run black agent_brain_server         # Format code
```

**CLI (agent-brain-cli)**:
```bash
cd agent-brain-cli
poetry install                    # Install dependencies
poetry run agent-brain --help     # Show CLI help
poetry run pytest                 # Run tests
poetry run mypy agent_brain_cli       # Type checking
poetry run ruff check agent_brain_cli # Linting
poetry run black agent_brain_cli      # Format code
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

**NEVER PUSH WITHOUT TESTING. NEVER. NOT EVEN "JUST A SMALL CHANGE".**

**MANDATORY**: Before pushing any changes, you MUST run:

```bash
task before-push    # MUST pass before ANY push
task pr-qa-gate     # MUST pass before ANY PR
```

This ensures:
1. Code is properly formatted (Black)
2. No linting errors (Ruff)
3. Type checking passes (mypy)
4. All tests pass with coverage report (>50%)

**MANDATORY**: Any feature or task is not considered done unless `task pr-qa-gate` passes successfully.

**If it fails, FIX IT. Then run it again. Only push when it passes.**

### End-to-End Validation

Before releasing any version, you MUST run:

```bash
./scripts/quick_start_guide.sh
```

This validates the complete workflow from server startup to advanced querying.

## Key Files to Understand

### Architecture
- `agent-brain-server/agent_brain_server/api/main.py` - FastAPI server entry point
- `agent-brain-server/agent_brain_server/config/settings.py` - Configuration
- `agent-brain-server/agent_brain_server/services/indexing_service.py` - AST-based ingestion
- `agent-brain-server/agent_brain_server/services/query_service.py` - Hybrid search

### CLI
- `agent-brain-cli/agent_brain_cli/cli.py` - CLI entry point
- `agent-brain-cli/agent_brain_cli/commands/` - CLI command implementations

### Testing
- `scripts/quick_start_guide.sh` - End-to-end validation script
- `e2e/integration/test_full_workflow.py` - Integration tests
- `AGENTS.md` - AI agent guidelines for this project

## Git Workflow

- Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`
- Create feature branches from main
- **MANDATORY**: Run `task before-push` before pushing to any branch — NEVER skip this
- **MANDATORY**: Run `task pr-qa-gate` before creating PRs
- PRs require end-to-end validation with `scripts/quick_start_guide.sh`
- **If `task before-push` fails, DO NOT push. Fix first, test again, then push.**

## Environment Setup

Required environment variables:
- `OPENAI_API_KEY` - For embeddings (text-embedding-3-large)
- `ANTHROPIC_API_KEY` - For code summarization (Claude Haiku)

## Notes

This is a production-ready Agent Brain implementation with comprehensive testing and documentation. Always run the quality checks and end-to-end validation before making changes.
