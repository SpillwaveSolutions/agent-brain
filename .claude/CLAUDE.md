---
last_validated: 2026-06-10
---

# CLAUDE.md (Claude Code scope)

The repository-root [`CLAUDE.md`](../CLAUDE.md) is the **single source of truth** for
package layout, build/test commands, the full CLI command reference, environment
variables, and the git workflow. Read it first. This file holds only the one rule
worth repeating and Claude-specific orientation that isn't in root.

## CRITICAL: NEVER PUSH WITHOUT TESTING

**ABSOLUTE RULE: run `task before-push` BEFORE EVERY `git push`. NO EXCEPTIONS.**

```bash
task before-push    # format, lint, typecheck, tests — must exit 0
task pr-qa-gate     # must pass before opening/updating ANY PR
```

PRs trigger expensive CI. If either check fails, **fix it and re-run — do not push.**
Run `task` commands from the **repo root**, not a package subdirectory (cwd scope leak).

## Key Files to Understand

**Architecture**
- `agent-brain-server/agent_brain_server/api/main.py` — FastAPI server entry point
- `agent-brain-server/agent_brain_server/config/settings.py` — configuration
- `agent-brain-server/agent_brain_server/services/indexing_service.py` — AST-based ingestion
- `agent-brain-server/agent_brain_server/services/query_service.py` — hybrid (BM25 + vector) search

**CLI / transports**
- `agent-brain-cli/agent_brain_cli/cli.py` — CLI entry point + global `--transport` flags
- `agent-brain-cli/agent_brain_cli/commands/` — command implementations
- `agent-brain-uds/` — Unix domain socket transport; `agent-brain-mcp/` — MCP server (PyPI: `agent-brain-ag-mcp`)

**Testing / validation**
- `scripts/quick_start_guide.sh` — end-to-end validation (run before any release)
- `e2e/integration/test_full_workflow.py` — integration tests
- `AGENTS.md` — AI agent guidelines for this project

## Environment Setup

Required environment variables (see root `CLAUDE.md` for the full table):
- `OPENAI_API_KEY` — embeddings (`text-embedding-3-large`)
- `ANTHROPIC_API_KEY` — code summarization (Claude Haiku)
