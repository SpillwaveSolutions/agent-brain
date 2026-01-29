# Implementation Plan: Agent Brain Naming Unification

**Branch**: `112-agent-brain-naming` | **Date**: 2026-01-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `.speckit/features/112-agent-brain-naming/spec.md`

## Summary

Unify all component names under the "agent-brain" brand to resolve naming inconsistencies created during v1.1.0 PyPI release. This involves renaming the repository, adding new CLI entry points, updating all documentation, and providing backward compatibility aliases.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: Poetry (packaging), Click (CLI), FastAPI (server)
**Storage**: N/A (naming changes only)
**Testing**: pytest with existing test suites
**Target Platform**: PyPI packages, GitHub repository, Claude Code skill
**Project Type**: Monorepo (server + CLI + skill)
**Performance Goals**: N/A (no runtime changes)
**Constraints**: Backward compatibility required for existing installations
**Scale/Scope**: 3 packages, ~50 documentation files, 6 GitHub issues

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Monorepo Modularity | ✅ PASS | Each package updated independently; cross-package flow preserved |
| II. OpenAPI-First | ✅ PASS | No API changes required; endpoints unchanged |
| III. Test-Alongside | ✅ PASS | Tests updated to verify new entry points work |
| IV. Observability | ✅ PASS | No changes to health/logging; naming only |
| V. Simplicity | ✅ PASS | Adding aliases is minimal change; no new dependencies |

**Gate Status**: PASSED - No constitution violations.

## Project Structure

### Documentation (this feature)

```text
.speckit/features/112-agent-brain-naming/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # N/A (no data changes)
├── quickstart.md        # Migration quickstart
├── contracts/           # N/A (no API changes)
├── checklists/          # Validation checklists
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
# Existing monorepo structure (unchanged)
doc-serve-server/
├── doc_serve_server/
│   ├── api/
│   │   └── main.py          # Add agent-brain-serve entry point
│   └── __init__.py          # Version bump to 1.2.0
├── pyproject.toml           # Add new script entry point
└── tests/

doc-svr-ctl/
├── doc_svr_ctl/
│   ├── cli.py               # Add agent-brain entry point
│   └── __init__.py          # Version bump to 1.2.0
├── pyproject.toml           # Add new script entry point
└── tests/

doc-serve-skill/
└── doc-serve/               # Rename to using-agent-brain/
    ├── SKILL.md             # Update name, triggers, commands
    └── references/          # Update all references
```

**Structure Decision**: Existing monorepo structure preserved. Changes are limited to:
1. Adding new entry points in pyproject.toml files
2. Renaming skill directory
3. Updating documentation references

## Complexity Tracking

> No constitution violations to justify.

## Phase 0: Research

### Research Tasks

1. **GitHub Repository Rename**: Process and redirect behavior
2. **Poetry Entry Points**: Adding multiple scripts to same package
3. **Deprecation Warnings**: Best practices for CLI deprecation notices

See [research.md](./research.md) for findings.

## Phase 1: Design

### Changes by Package

#### doc-serve-server (agent-brain-rag on PyPI)

**pyproject.toml changes**:
```toml
[tool.poetry.scripts]
agent-brain-serve = "doc_serve_server.api.main:cli"  # NEW primary
doc-serve = "doc_serve_server.api.main:cli"          # KEEP for backward compat
```

**Version**: 1.1.0 → 1.2.0

#### doc-svr-ctl (agent-brain-cli on PyPI)

**pyproject.toml changes**:
```toml
[tool.poetry.scripts]
agent-brain = "doc_svr_ctl.cli:cli"     # NEW primary
doc-svr-ctl = "doc_svr_ctl.cli:cli"     # KEEP for backward compat
```

**Version**: 1.1.0 → 1.2.0

**CLI deprecation message** (in cli.py):
```python
import warnings

def cli():
    if sys.argv[0].endswith('doc-svr-ctl'):
        warnings.warn(
            "doc-svr-ctl is deprecated, use 'agent-brain' instead",
            DeprecationWarning
        )
    # ... rest of CLI
```

#### doc-serve-skill

**Directory rename**: `doc-serve/` → `using-agent-brain/`

**SKILL.md updates**:
- `name: using-agent-brain`
- Update all command references from doc-serve/doc-svr-ctl to agent-brain-serve/agent-brain
- Update triggers to include "agent-brain" keywords

### Documentation Updates

| File | Changes |
|------|---------|
| README.md (root) | New naming, installation commands |
| CLAUDE.md (root) | Command references |
| .claude/CLAUDE.md | Command references |
| doc-serve-server/README.md | Entry point names |
| doc-svr-ctl/README.md | Entry point names |
| SKILL.md | Full rewrite for new naming |
| references/*.md | All command examples |
| troubleshooting-guide.md | All command examples |

### GitHub Repository Rename

**Process**:
1. Go to Settings → General → Repository name
2. Change from `doc-serve-skill` to `agent-brain`
3. GitHub automatically creates redirects from old URL
4. Update all documentation URLs after rename

**Post-rename tasks**:
- Update pyproject.toml homepage/repository URLs
- Update README badges
- Update CLAUDE.md references

## Implementation Phases

### Phase 1: Code Changes (No Breaking Changes)
1. Add new entry points to both packages
2. Add deprecation warnings to old entry points
3. Bump versions to 1.2.0
4. Run all tests

### Phase 2: Documentation Updates
1. Update all README files
2. Update all CLAUDE.md files
3. Update skill SKILL.md
4. Update troubleshooting guide
5. Create migration guide

### Phase 3: Skill Rename
1. Rename doc-serve/ directory to using-agent-brain/
2. Update SKILL.md frontmatter
3. Update all internal references

### Phase 4: Repository Rename (Manual)
1. User renames repository on GitHub
2. Update all URL references
3. Verify redirects work
4. Publish v1.2.0 to PyPI

## Migration Guide (quickstart.md)

See [quickstart.md](./quickstart.md) for user migration instructions.
