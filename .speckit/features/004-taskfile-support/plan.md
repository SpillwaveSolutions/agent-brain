# Implementation Plan: Taskfile Support

## Overview

This plan documents the Taskfile setup for the doc-serve monorepo and defines verification tasks to ensure the configuration works correctly.

## Current State Analysis

### Existing Taskfiles
The project already has a comprehensive Taskfile setup:

1. **Root Taskfile** (`/Taskfile.yml`)
   - Monorepo orchestrator with `includes:` directive
   - Aggregates tasks from server and CLI subprojects
   - Provides convenience wrappers for common operations

2. **Server Taskfile** (`/doc-serve-server/Taskfile.yml`)
   - Poetry-based Python project tasks
   - Dev/run server tasks
   - Standard quality gates (lint, typecheck, test)

3. **CLI Taskfile** (`/doc-svr-ctl/Taskfile.yml`)
   - Poetry-based Python project tasks
   - CLI command wrappers (status, query, index, reset)
   - Standard quality gates

### Key Features Implemented
- Monorepo pattern with namespace isolation
- Standard task naming conventions
- Coverage reporting with `test:cov`
- Pre-push workflow via `before-push` task
- PR quality gate with 50% coverage minimum
- Environment variable support via `dotenv:` and `env:`

## Implementation Phases

### Phase 1: Verification
Verify existing Taskfiles work correctly.

**Tasks:**
- T001: Run `task --list` and verify all expected tasks appear
- T002: Run `task install` and verify both packages install
- T003: Run `task test` and verify tests pass
- T004: Run `task server:test` and `task cli:test` isolation
- T005: Run `task before-push` full workflow

### Phase 2: Documentation
Ensure Taskfile usage is documented.

**Tasks:**
- T006: Verify README.md includes Task usage instructions
- T007: Add Task installation instructions if missing
- T008: Document all available tasks in project docs

### Phase 3: Enhancement (if needed)
Add any missing tasks based on project needs.

**Potential Additions:**
- Integration test task
- E2E test task
- Docker tasks (if containerization added)
- Deploy tasks (when deployment is configured)

## Technical Details

### Task Installation
```bash
# macOS
brew install go-task/tap/go-task

# Linux
sudo snap install task --classic

# Go install
go install github.com/go-task/task/v3/cmd/task@latest
```

### Running Tasks
```bash
# From project root
task --list        # Show all available tasks
task install       # Install all dependencies
task test          # Run all tests
task before-push   # Pre-push checks
task server:dev    # Start dev server
```

### Namespace Pattern
- `server:*` - Server-specific tasks
- `cli:*` - CLI-specific tasks
- Root tasks orchestrate subproject tasks

## Success Metrics

| Metric | Target | Verification |
|--------|--------|--------------|
| Task discoverability | All tasks have desc | `task --list` shows descriptions |
| Install success | 100% | `task install` exits 0 |
| Test coverage | 50%+ | `task test:cov` shows coverage |
| Pre-push workflow | All checks pass | `task before-push` exits 0 |

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Task not installed | Document in README, add check script |
| Poetry version mismatch | Pin Poetry version in pyproject.toml |
| Path issues | Use relative paths in Taskfiles |

## Timeline

This feature is primarily verification of existing implementation:
- Phase 1: Immediate (verification)
- Phase 2: Same day (documentation)
- Phase 3: As needed (enhancements)
