# Feature Specification: Consolidate Spec Directories to .speckit/

**Feature Branch**: `108-speckit-consolidation`
**Created**: 2026-01-27
**Status**: Draft
**Input**: User description: "Consolidate spec directories to speckit"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Developer Finds SDD Artifacts in One Place (Priority: P1)

A developer working on a Doc-Serve feature needs to locate spec, plan, and task files. Currently, SDD-related content is scattered across three directories (`.specify/`, `.speckit/`, `specs/`), causing confusion about which directory holds what. After consolidation, all SDD artifacts live under a single `.speckit/` directory with a clear internal structure.

**Why this priority**: Without a single source of truth for SDD artifacts, developers waste time searching multiple directories and scripts may reference stale paths. This is the core value of the consolidation.

**Independent Test**: Navigate to `.speckit/` and verify all feature specs, templates, scripts, and memory files are accessible from that single root.

**Acceptance Scenarios**:

1. **Given** the repository has been consolidated, **When** a developer looks for feature spec files, **Then** all 13+ feature directories exist under `.speckit/features/`
2. **Given** the repository has been consolidated, **When** a developer looks for SDD templates, **Then** all template files exist under `.speckit/templates/`
3. **Given** the repository has been consolidated, **When** a developer looks for SDD scripts, **Then** all bash scripts exist under `.speckit/scripts/bash/`
4. **Given** the repository has been consolidated, **When** a developer searches for `.specify/` or `specs/` directories, **Then** neither directory exists

---

### User Story 2 - SDD Scripts Work After Migration (Priority: P1)

A developer runs SDD workflow commands (e.g., `/speckit.specify`, `/speckit.plan`) after the directory consolidation. All bash scripts and command files must reference the new `.speckit/` paths so the workflow continues functioning without errors.

**Why this priority**: Broken scripts would block all SDD workflows, making this equally critical to the directory move itself.

**Independent Test**: Run `bash .speckit/scripts/bash/check-prerequisites.sh --help` and verify it executes without path errors.

**Acceptance Scenarios**:

1. **Given** scripts have been migrated to `.speckit/scripts/bash/`, **When** any SDD script is executed, **Then** it resolves all file paths correctly using `.speckit/` prefixes
2. **Given** command files reference scripts, **When** a developer runs `/speckit.plan` or `/speckit.tasks`, **Then** the commands invoke scripts at `.speckit/scripts/bash/` paths
3. **Given** the `create-new-feature.sh` script creates new features, **When** it runs, **Then** new feature directories are created under `.speckit/features/` (not `specs/`)

---

### User Story 3 - Claude Code Permissions Remain Valid (Priority: P2)

A developer using Claude Code on this repository needs bash script execution permissions to work. The `.claude/settings.local.json` file must reference the new `.speckit/` script paths so permissions are not silently broken.

**Why this priority**: Broken permissions would cause confusing permission-denied errors during SDD workflows, but the impact is limited to Claude Code users.

**Independent Test**: Inspect `.claude/settings.local.json` and verify all script permission paths use `.speckit/scripts/bash/` prefixes.

**Acceptance Scenarios**:

1. **Given** settings reference script paths, **When** the settings file is loaded, **Then** all 4 bash script permissions point to `.speckit/scripts/bash/` paths
2. **Given** a developer triggers a script via Claude Code, **When** the permission check runs, **Then** the script is allowed without manual re-authorization

---

### Edge Cases

- What happens when a developer has local branches referencing old `specs/` paths? They would need to rebase onto main after consolidation.
- How does the system handle the orphaned `.speckit/features/001-doc-serve-phase1/tasks.md` that pre-existed? It remains in place alongside the newly moved feature directories.
- What if a developer runs an old cached version of a command file that still references `.specify/`? The script would fail with a "file not found" error, prompting them to pull latest.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: All feature spec directories MUST be located under `.speckit/features/`
- **FR-002**: All SDD templates MUST be located under `.speckit/templates/`
- **FR-003**: All SDD bash scripts MUST be located under `.speckit/scripts/bash/`
- **FR-004**: The project constitution MUST be located at `.speckit/memory/constitution.md`
- **FR-005**: All bash scripts MUST reference `.speckit/` paths internally (no references to `.specify/` or bare `specs/`)
- **FR-006**: All 9 speckit command files MUST reference `.speckit/` paths (no references to `.specify/` or bare `specs/`)
- **FR-007**: The `.claude/settings.local.json` MUST reference `.speckit/scripts/bash/` for all script permissions
- **FR-008**: The old `.specify/` directory MUST be removed after migration
- **FR-009**: The old `specs/` directory MUST be removed after migration
- **FR-010**: Git history MUST preserve rename tracking for all moved files (use `git mv`)

### Key Entities

- **Feature Directory**: A numbered directory (e.g., `101-code-ingestion`) containing spec.md, plan.md, tasks.md, and optional supporting docs for a single SDD feature
- **SDD Template**: A markdown template file used by scripts to scaffold new spec, plan, task, or agent files
- **SDD Script**: A bash script that automates SDD workflow steps (prerequisites check, feature creation, plan setup, agent context updates)
- **Command File**: A markdown file in `.claude/commands/` that defines behavior for `/speckit.*` slash commands

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All SDD artifacts are reachable from a single root directory (`.speckit/`) with zero files remaining in `.specify/` or `specs/`
- **SC-002**: Zero references to `.specify/` directory paths exist in any script, command file, or settings file (verified by grep)
- **SC-003**: Zero references to bare `specs/` directory paths exist in any script or command file (verified by grep)
- **SC-004**: All 13+ feature directories are present under `.speckit/features/`
- **SC-005**: SDD workflow scripts execute without path-related errors after migration
- **SC-006**: Git recognizes all moves as renames (preserving blame history)
