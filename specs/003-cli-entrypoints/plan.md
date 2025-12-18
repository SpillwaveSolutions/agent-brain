# Implementation Plan: CLI Entry Points Installation

**Branch**: `003-cli-entrypoints` | **Date**: 2025-12-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-cli-entrypoints/spec.md`

## Summary

Enable direct command-line invocation of `doc-svr-ctl` and `doc-serve` commands after package installation. The pyproject.toml files already contain entry point configurations; implementation focuses on verification, testing, and ensuring both pip and Poetry installation methods work correctly.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: Poetry (build system), Click (CLI framework), FastAPI/Uvicorn (server)
**Storage**: N/A (configuration only)
**Testing**: pytest for installation verification tests
**Target Platform**: Linux/macOS/Windows (any platform supporting Python)
**Project Type**: Monorepo with two independent packages
**Performance Goals**: Commands available within 1 second of installation
**Constraints**: Must work with both pip and Poetry installation methods
**Scale/Scope**: 2 packages, 2 entry points

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Monorepo Modularity | PASS | Each package has independent pyproject.toml and entry point |
| II. OpenAPI-First | N/A | No API changes - this is packaging configuration |
| III. Test-Alongside | PASS | Will add installation verification tests |
| IV. Observability | N/A | Entry points invoke existing observable components |
| V. Simplicity | PASS | Using existing Poetry scripts configuration - minimal changes |

**Gate Status**: PASS - All applicable principles satisfied

## Project Structure

### Documentation (this feature)

```text
specs/003-cli-entrypoints/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (minimal - no data model)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (N/A - no API contracts)
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
# Monorepo structure (existing)
doc-svr-ctl/
├── pyproject.toml       # Entry point: doc-svr-ctl = "src.cli:cli"
├── src/
│   ├── __init__.py
│   └── cli.py           # Click CLI group (existing)
└── tests/
    └── test_cli_install.py  # NEW: Installation verification tests

doc-serve-server/
├── pyproject.toml       # Entry point: doc-serve = "src.api.main:run"
├── src/
│   ├── __init__.py
│   └── api/
│       └── main.py      # FastAPI app + run() function (existing)
└── tests/
    └── test_server_install.py  # NEW: Installation verification tests
```

**Structure Decision**: Using existing monorepo structure. Only adding test files to verify entry point functionality.

## Complexity Tracking

> No violations - feature uses existing configuration with minimal additions.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |

## Phase 0: Research Summary

### Entry Point Configuration Analysis

**Decision**: Use existing Poetry `[tool.poetry.scripts]` configuration
**Rationale**: Already configured correctly in both pyproject.toml files
**Alternatives considered**:
- `[project.scripts]` (PEP 621) - Would require restructuring pyproject.toml
- Console scripts in setup.py - Deprecated approach

### Installation Method Verification

**Decision**: Support both `pip install -e .` and `poetry install`
**Rationale**: Developers use different workflows; both must work
**Alternatives considered**:
- Poetry-only installation - Would exclude pip users

### Package Structure Verification

**Decision**: Verify `packages = [{include = "src"}]` is correct
**Rationale**: Entry points reference `src.cli:cli` and `src.api.main:run`
**Findings**: Current configuration is correct for both packages

## Phase 1: Design

### Data Model

N/A - This feature involves no data modeling. It's purely packaging configuration.

### Contracts

N/A - No API contracts for entry point configuration. The entry points invoke existing CLI and server code with established contracts.

### Implementation Approach

1. **Verification Testing**: Create tests that verify entry points work after installation
2. **Documentation**: Create quickstart guide for installation
3. **Validation**: Test both pip and Poetry installation methods

### Test Strategy

**doc-svr-ctl tests** (`doc-svr-ctl/tests/test_cli_install.py`):
- Test `doc-svr-ctl --help` returns expected output
- Test `doc-svr-ctl --version` returns version string
- Test CLI module can be imported and executed

**doc-serve-server tests** (`doc-serve-server/tests/test_server_install.py`):
- Test `doc-serve` command is importable
- Test `run()` function exists and is callable
- Test server starts without crashing (smoke test)

## Artifacts Generated

| Artifact | Status | Path |
|----------|--------|------|
| plan.md | Complete | `specs/003-cli-entrypoints/plan.md` |
| research.md | Complete | `specs/003-cli-entrypoints/research.md` |
| data-model.md | Skipped | N/A - No data model needed |
| quickstart.md | Pending | `specs/003-cli-entrypoints/quickstart.md` |
| contracts/ | Skipped | N/A - No new API contracts |

## Next Steps

Run `/speckit.tasks` to generate implementation tasks from this plan.

---

## V2 Update: Self-Documenting CLI (2025-12-16)

### Problem Statement

The `doc-serve` command does not support `--help` or `--version` flags. Running `doc-serve --help` starts the server instead of showing help. Both CLI tools should be self-documenting.

### Implementation Approach

1. **Create Click CLI for doc-serve**: Replace direct `run()` function call with Click-based CLI
   - Add `--help` support (Click provides automatically)
   - Add `--version` support
   - Add configurable `--host`, `--port`, `--reload` options
   - Default behavior (no args) starts the server as before

2. **Update Entry Point**: Change `pyproject.toml` entry point from `src.api.main:run` to new CLI function

3. **Add Tests**: Test `--help` and `--version` flags work correctly

### Files to Modify

| File | Change |
|------|--------|
| `doc-serve-server/src/api/main.py` | Add Click CLI wrapper around `run()` |
| `doc-serve-server/pyproject.toml` | Update entry point to new CLI function |
| `doc-serve-server/tests/test_server_install.py` | Add tests for --help and --version |

### Design Decision

Use Click (same as doc-svr-ctl) for consistency across both CLI tools. This provides:
- Automatic `--help` generation
- `--version` decorator
- Option parsing with type validation
- Consistent UX across both tools
