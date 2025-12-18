# Feature Specification: Taskfile Support

## Metadata
- **Feature ID**: 004-taskfile-support
- **Status**: Complete
- **Priority**: P1
- **Created**: 2024-12-17
- **Updated**: 2024-12-17

## Overview

### Problem Statement
Developers need a standardized, cross-platform way to run common development tasks (build, test, lint, deploy) across the doc-serve monorepo. Manual commands are error-prone and inconsistent.

### Proposed Solution
Use Task (https://taskfile.dev) as a modern Make alternative with YAML-based Taskfiles. Implement a monorepo pattern with a root orchestrator and per-subproject Taskfiles.

### Success Criteria
- SC-001: `task --list` displays all available tasks at root and subproject levels
- SC-002: `task install` installs dependencies for all subprojects
- SC-003: `task test` runs all tests across both packages
- SC-004: `task before-push` runs complete quality gate (format, lint, typecheck, test)
- SC-005: Subproject tasks can be invoked via namespacing (e.g., `task server:test`)
- SC-006: All tasks are self-documenting with `desc:` fields

## User Stories

### US1: Developer runs all tests
**As a** developer
**I want to** run a single command to test the entire monorepo
**So that** I can verify nothing is broken before committing

**Acceptance Criteria:**
- AC1: `task test` runs both server and CLI tests
- AC2: Exit code is non-zero if any test fails
- AC3: Output shows which package tests passed/failed

### US2: Developer runs pre-push checks
**As a** developer
**I want to** run comprehensive quality checks before pushing
**So that** I catch issues before CI and code review

**Acceptance Criteria:**
- AC1: `task before-push` runs format, lint, typecheck, and tests
- AC2: Output is clearly sectioned by check type
- AC3: Process stops on first failure (fail-fast)

### US3: Developer works on single package
**As a** developer
**I want to** run tasks for a specific package without affecting others
**So that** I can iterate quickly on one component

**Acceptance Criteria:**
- AC1: `task server:test` runs only server tests
- AC2: `task cli:test` runs only CLI tests
- AC3: Namespaced tasks work for all subproject tasks

### US4: New developer onboards quickly
**As a** new developer
**I want to** see all available tasks and their descriptions
**So that** I can understand the project workflow quickly

**Acceptance Criteria:**
- AC1: `task --list` shows all tasks with descriptions
- AC2: Tasks are logically grouped (Setup, Development, Testing, etc.)
- AC3: Each task has a meaningful `desc:` field

## Functional Requirements

### FR-001: Root Taskfile Structure
The root Taskfile.yml shall:
- Include subproject Taskfiles via `includes:` directive
- Define orchestration tasks that invoke subproject tasks
- Support `.env` file loading via `dotenv:` directive

### FR-002: Subproject Taskfile Structure
Each subproject Taskfile shall:
- Define standard tasks: install, build, test, clean, format, lint, typecheck
- Support coverage reporting via `test:cov` task
- Define PYTHONPATH for proper imports

### FR-003: Standard Task Names
The following task names shall be consistent across all Taskfiles:
- `install` - Install dependencies
- `build` - Build/package the project
- `test` - Run unit tests
- `test:cov` - Run tests with coverage
- `clean` - Remove build artifacts
- `format` - Auto-format code
- `lint` - Check code style
- `typecheck` - Run type checker
- `ci` - Simulate full CI pipeline
- `pr-qa-gate` - PR quality gate with coverage minimum

### FR-004: Convenience Wrappers
Root Taskfile shall provide convenience wrappers for CLI commands:
- `task status` - Check server status
- `task query -- "query"` - Search documents
- `task index -- /path` - Index documents
- `task reset` - Reset the index

### FR-005: Development Tasks
Server Taskfile shall provide:
- `dev` - Start server with hot reload (DEBUG=true)
- `run` - Start server in production mode

## Non-Functional Requirements

### NFR-001: Cross-Platform Compatibility
Taskfiles shall work on macOS, Linux, and Windows (via WSL or native Go binary).

### NFR-002: Idempotency
Tasks shall be idempotent - running them multiple times produces the same result.

### NFR-003: Fast Feedback
Quick tasks (lint, format) shall complete in under 5 seconds for normal codebases.

## Technical Design

### Architecture Pattern
```
doc-serve/
├── Taskfile.yml           # Root orchestrator
├── doc-serve-server/
│   └── Taskfile.yml       # Server-specific tasks
└── doc-svr-ctl/
    └── Taskfile.yml       # CLI-specific tasks
```

### Task Naming Convention
- Use kebab-case for task names
- Use colons for namespacing (e.g., `test:cov`, `lint:fix`)
- Prefix with package name for cross-project (e.g., `server:test`)

### Environment Variables
- `PYTHONPATH` - Set for proper Python imports
- `DEBUG` - Toggle development mode
- `DOC_SERVE_URL` - CLI target server URL

## Testing Strategy

### T001: Verify task --list output
Verify all expected tasks appear in `task --list` output.

### T002: Verify install task
Run `task install` and verify Poetry install succeeds for both packages.

### T003: Verify test task
Run `task test` and verify tests pass for both packages.

### T004: Verify before-push workflow
Run `task before-push` and verify all checks complete successfully.

### T005: Verify namespace isolation
Run `task server:test` and verify only server tests run.

### T006: Verify clean task
Run `task clean` and verify build artifacts are removed.

## Dependencies

### External Dependencies
- Task v3.x (https://taskfile.dev)
- Poetry 1.x for Python package management
- Python 3.10+

### Internal Dependencies
- doc-serve-server package
- doc-svr-ctl package

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Task not installed | Cannot run any tasks | Document installation in README |
| Poetry not installed | Package tasks fail | Add prerequisite check task |
| Path issues on Windows | Tasks fail silently | Use cross-platform commands |

## Appendix

### Sample Commands
```bash
# List all tasks
task --list

# Install everything
task install

# Run all tests
task test

# Pre-push workflow
task before-push

# Server-specific tasks
task server:dev
task server:test

# CLI-specific tasks
task cli:status
task cli:query -- "search term"
```
