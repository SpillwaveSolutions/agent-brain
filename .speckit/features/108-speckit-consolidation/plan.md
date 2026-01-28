# Implementation Plan: Consolidate Spec Directories to .speckit/

**Branch**: `108-speckit-consolidation` | **Date**: 2026-01-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `.speckit/features/108-speckit-consolidation/spec.md`

## Summary

Consolidate three SDD-related directories (`.specify/`, `.speckit/`, `specs/`) into a single `.speckit/` root with subdirectories for features, templates, scripts, and memory. Update all internal path references across bash scripts, command files, and settings to use the new `.speckit/` paths. Preserve git rename history using `git mv`.

## Technical Context

**Language/Version**: Bash (shell scripts), Markdown (command files, settings)
**Primary Dependencies**: Git (for `git mv` rename tracking), Bash 4+ (for scripts)
**Storage**: N/A (filesystem reorganization only)
**Testing**: Manual verification via `grep` and `ls` commands; no automated test suite for this feature
**Target Platform**: macOS/Linux developer workstations
**Project Type**: single (monorepo tooling)
**Performance Goals**: N/A (one-time migration)
**Constraints**: Must preserve git blame/rename history; zero downtime for SDD workflows
**Scale/Scope**: ~55 files moved/updated across 3 source directories and ~15 config files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Monorepo Modularity | PASS | No cross-package changes; SDD tooling is repo-level infrastructure |
| II. OpenAPI-First | N/A | No API changes |
| III. Test-Alongside | PASS (with note) | No automated tests added since this is a file-move operation with manual verification. No code logic is changed. |
| IV. Observability | N/A | No runtime components changed |
| V. Simplicity | PASS | Reduces complexity by consolidating 3 directories into 1 |

No violations. No complexity tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
.speckit/features/108-speckit-consolidation/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output (minimal — no unknowns)
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
.speckit/                          # Consolidated SDD root (TARGET)
├── features/                      # All feature specs (moved from specs/)
│   ├── 001-phase1-core-server/
│   ├── 001-doc-serve-phase1/      # Pre-existing orphan
│   ├── 002-cli-tool/
│   ├── ...
│   ├── 106-vertex-ai/
│   └── 108-speckit-consolidation/ # This feature
├── templates/                     # SDD templates (moved from .specify/templates/)
│   ├── agent-file-template.md
│   ├── checklist-template.md
│   ├── plan-template.md
│   ├── spec-template.md
│   └── tasks-template.md
├── scripts/                       # SDD scripts (moved from .specify/scripts/)
│   └── bash/
│       ├── check-prerequisites.sh
│       ├── common.sh
│       ├── create-new-feature.sh
│       ├── setup-plan.sh
│       └── update-agent-context.sh
└── memory/                        # Constitution (moved from .specify/memory/)
    └── constitution.md

.claude/
├── commands/
│   └── speckit.*.md               # 9 command files (path references updated)
└── settings.local.json            # Script permissions (paths updated)
```

**Structure Decision**: No new source code directories. This is purely a reorganization of existing SDD infrastructure files with path reference updates in configuration files.

## Phases

### Phase 1: Directory Migration

1. Create target directories under `.speckit/` if not existing (features, templates, scripts, memory)
2. Use `git mv` to move all content from `specs/*` to `.speckit/features/`
3. Use `git mv` to move `.specify/templates/` to `.speckit/templates/`
4. Use `git mv` to move `.specify/scripts/` to `.speckit/scripts/`
5. Use `git mv` to move `.specify/memory/` to `.speckit/memory/`
6. Remove empty `.specify/` and `specs/` directories

### Phase 2: Path Reference Updates

Update internal references in these file groups:

**Bash scripts** (4 files in `.speckit/scripts/bash/`):
- `common.sh`: `$repo_root/specs` → `$repo_root/.speckit/features`; `get_feature_dir()` path
- `create-new-feature.sh`: `.specify` marker → `.speckit`; `SPECS_DIR` path; template path
- `setup-plan.sh`: template path `.specify/templates/` → `.speckit/templates/`
- `update-agent-context.sh`: template path `.specify/templates/` → `.speckit/templates/`

**Command files** (9 files in `.claude/commands/`):
- Global replace `.specify/` → `.speckit/` in all `speckit.*.md` files
- Replace `specs/` directory references → `.speckit/features/` in `speckit.specify.md`
- Add reinforcement note after frontmatter in each file

**Settings** (1 file):
- `.claude/settings.local.json`: Update 4 script permission paths

### Phase 3: Verification

1. `ls .speckit/features/` — 13+ feature dirs
2. `ls .speckit/templates/` — 5 template files
3. `ls .speckit/scripts/bash/` — 5 scripts
4. `ls .speckit/memory/` — constitution.md
5. `grep -r '\.specify/' .speckit/scripts/` — 0 results (excluding command name references)
6. `grep -r '\.specify/' .claude/commands/` — 0 results (excluding command name references)
7. `grep -rn '"specs/' .speckit/scripts/` — 0 results
8. `ls -d .specify specs` — both should not exist

## Complexity Tracking

No violations to justify. This feature adds zero new dependencies and involves zero lines of new application code.
