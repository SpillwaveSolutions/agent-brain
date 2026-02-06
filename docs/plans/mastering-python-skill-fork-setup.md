# Mastering Python Skill Fork Setup

This document explains how the `mastering-python-skill` was forked and customized with a comprehensive agent configuration to eliminate approval fatigue when working on Python projects.

## Problem: Approval Fatigue

When using Claude Code with skills that invoke bash commands, each command requires user approval. For Python development workflows, this creates constant interruption:

```
Claude: Running `pytest -v`...
[Approve? y/n]

Claude: Running `ruff check .`...
[Approve? y/n]

Claude: Running `poetry install`...
[Approve? y/n]
```

This "approval fatigue loop" breaks flow and slows development significantly.

## Solution: Fork + Pre-Authorized Agent

The solution involves three components:

1. **Local skill copy** - A forked copy of the skill in the project
2. **Custom agent** - An agent definition with comprehensive pre-authorized tools
3. **Skill-agent binding** - The skill references the agent via `agent:` directive

### Architecture

```
.claude/
├── agents/
│   └── senior-python-engineer.md    # Agent with all permissions
└── skills/
    └── mastering-python-skill/      # Local fork of skill
        ├── SKILL.md                 # References the agent
        ├── references/              # Python documentation
        └── sample-cli/              # Runnable examples
```

## Installation Steps

### Step 1: Install Local Copy with skilz

```bash
skilz install https://github.com/SpillwaveSolutions/mastering-python-skill-plugin -p --agent claude
```

**Flags explained:**
- `-p` (or `--project`) - Install to project's `.claude/skills/` instead of global
- `--agent claude` - Target Claude Code agent format

This creates a local copy at `.claude/skills/mastering-python-skill/` that can be customized.

### Step 2: Create the Agent Definition

Create `.claude/agents/senior-python-engineer.md` with comprehensive tool permissions:

```yaml
---
name: senior-python-engineer
description: Senior Python engineer agent with full permissions...

allowed_tools:
  # File operations
  - "Read"
  - "Edit"
  - "Write"
  - "Glob"
  - "Grep"

  # Python development
  - "Bash(python*)"
  - "Bash(pytest*)"
  - "Bash(poetry*)"
  - "Bash(ruff*)"
  - "Bash(mypy*)"
  - "Bash(black*)"
  # ... 300+ tool permissions
---
```

### Step 3: Bind Skill to Agent

In `.claude/skills/mastering-python-skill/SKILL.md`, add the `agent:` directive:

```yaml
---
name: mastering-python-skill
description: Modern Python coaching...
context: fork
agent: senior-python-engineer    # <-- References the agent
allowed-tools:
  - Read
  - Write
  - Bash
  - Edit
---
```

The `agent: senior-python-engineer` line tells Claude Code to use the permissions from `.claude/agents/senior-python-engineer.md`.

## How It Works

1. User invokes `/mastering-python-skill` or triggers via description keywords
2. Claude Code loads the skill from `.claude/skills/mastering-python-skill/SKILL.md`
3. The `agent: senior-python-engineer` directive loads the agent configuration
4. All tools listed in the agent's `allowed_tools` are pre-authorized
5. Commands execute without approval prompts

## Agent Permissions Categories

The `senior-python-engineer.md` agent includes comprehensive permissions:

### File Operations
```yaml
- "Read"
- "Edit"
- "MultiEdit"
- "Write"
- "Glob"
- "Grep"
```

### Python Development Tools
```yaml
# Virtual environments
- "Bash(python*)"
- "Bash(pip*)"
- "Bash(uv*)"
- "Bash(poetry*)"
- "Bash(conda*)"

# Code quality
- "Bash(ruff*)"
- "Bash(mypy*)"
- "Bash(black*)"
- "Bash(pytest*)"
- "Bash(coverage*)"

# Servers
- "Bash(uvicorn*)"
- "Bash(gunicorn*)"
- "Bash(fastapi*)"
```

### Git & GitHub
```yaml
# Git operations
- "Bash(git status*)"
- "Bash(git add*)"
- "Bash(git commit*)"
- "Bash(git push*)"

# GitHub CLI
- "Bash(gh pr*)"
- "Bash(gh issue*)"
- "Bash(gh release*)"
```

### Task Runners
```yaml
- "Bash(task*)"
- "Bash(make*)"
- "Bash(invoke*)"
- "Bash(just*)"
```

### Shell Utilities
```yaml
- "Bash(ls*)"
- "Bash(mkdir*)"
- "Bash(rm*)"
- "Bash(curl*)"
- "Bash(jq*)"
# ... and many more
```

## Referenced Skills in Agent

The `senior-python-engineer.md` agent references several skills for expert guidance:

### mastering-python-skill
Core Python patterns and best practices:
- Type hints, generics, Protocols
- Async/await with asyncio, httpx
- pytest fixtures, parametrize, markers
- FastAPI dependencies, middleware
- Poetry lock files, publishing

Load with: `/mastering-python-skill`

### developing-llamaindex-systems
Production-grade RAG and agentic systems:
- SemanticSplitterNodeParser, CodeSplitter
- BM25Retriever, hybrid search
- PropertyGraphIndex, graph extractors
- ReAct agents, event-driven Workflows

Load with: `/developing-llamaindex-systems`

### taskfile
Expert guidance for Task (Go-based task runner):
- Taskfile.yml syntax and structure
- Variables, environment variables
- Task dependencies and includes
- Platform-specific commands

Load with: `/taskfile`

## Manifest Tracking

The `.skilz-manifest.yaml` tracks the installation source:

```yaml
installed_at: '2026-02-05T19:58:38+00:00'
skill_id: git/mastering-python-skill
git_repo: https://github.com/SpillwaveSolutions/mastering-python-skill-plugin
git_sha: a03ac1e39f65f074985e4f9ea62d9129779b4ba0
skilz_version: 1.10.0
install_mode: copy
```

This allows tracking the upstream source for future updates.

## Benefits

### Before (Approval Fatigue)
```
Claude: Let me run the tests...
[Approve `pytest -v`? y/n] y
Claude: Now checking types...
[Approve `mypy src/`? y/n] y
Claude: Formatting code...
[Approve `ruff format .`? y/n] y
Claude: Checking lint...
[Approve `ruff check .`? y/n] y
```

### After (Pre-Authorized)
```
Claude: Let me validate the code...
> pytest -v ✓
> mypy src/ ✓
> ruff format . ✓
> ruff check . ✓
All checks passed!
```

## Security Considerations

The comprehensive permissions are intentionally broad for development workflow efficiency. This is appropriate for:

- Local development environments
- Trusted project codebases
- Developer workstations

For production or shared environments, consider:
- Limiting permissions to specific commands
- Using more restrictive glob patterns
- Reviewing the agent permissions periodically

## Updating the Fork

To update from upstream while preserving customizations:

```bash
# Check current version
cat .claude/skills/mastering-python-skill/.skilz-manifest.yaml

# Update (re-install)
skilz install https://github.com/SpillwaveSolutions/mastering-python-skill-plugin -p --agent claude --force

# Re-apply customizations to SKILL.md (add agent: directive)
```

## Summary

| Component | Purpose |
|-----------|---------|
| `skilz install ... -p` | Creates local fork in `.claude/skills/` |
| `senior-python-engineer.md` | Defines 300+ pre-authorized tools |
| `agent: senior-python-engineer` | Binds skill to agent permissions |
| `.skilz-manifest.yaml` | Tracks upstream source and version |

This pattern eliminates approval fatigue while maintaining a clear audit trail of what permissions are granted and why.

## Directory-Specific Guidance

In addition to the skill and agent, the project includes directory-specific `CLAUDE.md` and `AGENTS.md` files that point to relevant skill references.

### Test Directories

Each test directory has guidance files pointing to testing references:

| Directory | References |
|-----------|------------|
| `agent-brain-server/tests/` | pytest-essentials, mocking-strategies, property-testing |
| `agent-brain-cli/tests/` | pytest-essentials, mocking-strategies, property-testing |
| `e2e/integration/` | pytest-essentials, mocking-strategies, property-testing |

**Testing reference files:**
- `pytest-essentials.md` - Fixtures, parametrize, markers, conftest patterns
- `mocking-strategies.md` - unittest.mock, MagicMock, patching patterns
- `property-testing.md` - Hypothesis property-based testing

### CI/CD Workflows

The `.github/workflows/` directory has guidance pointing to production references:

**Production reference files:**
- `ci-cd-pipelines.md` - GitHub Actions, workflow structure, matrix builds
- `security.md` - Secret management, vulnerability scanning, SAST
- `monitoring.md` - Coverage reporting, logging, observability

### FastAPI API

The `agent-brain-server/agent_brain_server/api/` directory has guidance for web API development:

**Web API reference files:**
- `fastapi-patterns.md` - Routers, dependencies, middleware, error handling
- `pydantic-validation.md` - Request/response models, validators, settings
- `database-access.md` - SQLAlchemy async, repository pattern, transactions

### Directory Guidance Pattern

Each guidance file follows this pattern:

1. **Invoke the skill** - `/mastering-python-skill`
2. **Reference table** - Maps skill reference files to use cases
3. **When to use each** - Specific scenarios for each reference
4. **Commands** - Relevant commands for that directory
5. **Quality standards** - Checklist before committing

This ensures agents working in any directory have immediate access to the relevant skill documentation without searching.
