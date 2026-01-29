# Feature Specification: Agent Brain Naming Unification

**Feature Branch**: `112-agent-brain-naming`
**Created**: 2026-01-29
**Status**: Draft
**Input**: User description: "v1.2 Agent Brain Naming Unification - Rename repository, CLI, server, and skill to use agent-brain branding (GitHub issues #90-95)"
**Related Issues**: #90, #91, #92, #93, #94, #95

## Overview

This feature unifies all component names under the "agent-brain" brand to resolve naming inconsistencies introduced when publishing to PyPI. The v1.1.0 release required different package names (`agent-brain-rag`, `agent-brain-cli`) due to PyPI naming constraints, creating a disconnect with the repository, CLI commands, and skill names.

## Current vs Proposed Naming

| Component | Current Name | Proposed Name | PyPI Package |
|-----------|--------------|---------------|--------------|
| Repository | doc-serve-skill | agent-brain | N/A |
| CLI Command | doc-svr-ctl | agent-brain | agent-brain-cli |
| Server Command | doc-serve | agent-brain-serve | agent-brain-rag |
| Skill | doc-serve | using-agent-brain | N/A |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - New User Installation (Priority: P1)

A new user discovers the agent-brain tool and wants to install and use it. They should be able to find consistent naming across PyPI, GitHub, and documentation that makes it clear all components belong to the same product.

**Why this priority**: First impressions matter. Inconsistent naming confuses new users and reduces adoption.

**Independent Test**: Can be fully tested by having a new user follow installation docs and verify all commands work as documented.

**Acceptance Scenarios**:

1. **Given** a new user visits PyPI, **When** they search for "agent-brain", **Then** they find both `agent-brain-rag` and `agent-brain-cli` packages with clear descriptions
2. **Given** a user installs the packages, **When** they run `agent-brain --help`, **Then** they see the CLI help with consistent branding
3. **Given** a user visits GitHub, **When** they search for the repository, **Then** they find "agent-brain" repository with matching branding

---

### User Story 2 - Existing User Migration (Priority: P1)

An existing user of doc-serve wants to upgrade to the new naming. They need clear migration instructions and backward compatibility during the transition period.

**Why this priority**: Breaking changes for existing users damages trust and creates support burden.

**Independent Test**: Can be fully tested by upgrading an existing doc-serve installation and verifying both old and new commands work.

**Acceptance Scenarios**:

1. **Given** a user has old CLI installed, **When** they upgrade to v1.2, **Then** both `doc-svr-ctl` and `agent-brain` commands work
2. **Given** a user has old server installed, **When** they upgrade to v1.2, **Then** both `doc-serve` and `agent-brain-serve` commands work
3. **Given** a user reads the migration guide, **When** they follow the steps, **Then** they successfully migrate within 10 minutes

---

### User Story 3 - Documentation Consistency (Priority: P2)

Users reading documentation should see consistent naming throughout all guides, READMEs, and examples.

**Why this priority**: Documentation inconsistency causes confusion and support requests.

**Independent Test**: Can be verified by auditing all documentation files for consistent naming.

**Acceptance Scenarios**:

1. **Given** any documentation file, **When** a user reads it, **Then** all references use the new agent-brain naming
2. **Given** the README, **When** a user follows the quick start, **Then** all commands use agent-brain naming
3. **Given** the troubleshooting guide, **When** a user searches for help, **Then** they find solutions using current naming

---

### User Story 4 - Claude Code Skill Discovery (Priority: P2)

Users of Claude Code should be able to discover and install the skill using intuitive naming.

**Why this priority**: Skill discoverability directly impacts adoption.

**Independent Test**: Can be tested by searching for the skill in Claude Code and verifying installation works.

**Acceptance Scenarios**:

1. **Given** a Claude Code user, **When** they search for document search skills, **Then** they find "using-agent-brain"
2. **Given** the skill is installed, **When** the user types triggers like "search documentation", **Then** the skill activates
3. **Given** the skill SKILL.md, **When** the user reads installation instructions, **Then** they see `pip install agent-brain-rag agent-brain-cli`

---

### Edge Cases

- What happens when a user has both old and new commands installed?
  - Both should work; new commands take precedence in documentation
- How does system handle mixed version installations (old CLI, new server)?
  - CLI and server communicate via HTTP API; versions should be compatible
- What happens to existing indexed data after renaming?
  - Data persists in `.claude/doc-serve/` directory; no data migration needed

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST rename GitHub repository from `doc-serve-skill` to `agent-brain`
- **FR-002**: System MUST update all repository URLs in documentation and code
- **FR-003**: CLI package MUST provide `agent-brain` command as primary entry point
- **FR-004**: CLI package MUST retain `doc-svr-ctl` as backward-compatible alias
- **FR-005**: Server package MUST provide `agent-brain-serve` command as primary entry point
- **FR-006**: Server package MUST retain `doc-serve` as backward-compatible alias
- **FR-007**: Skill MUST be renamed from `doc-serve` to `using-agent-brain`
- **FR-008**: All SKILL.md triggers MUST be updated to reference agent-brain naming
- **FR-009**: All README files MUST be updated with new naming
- **FR-010**: All CLAUDE.md files MUST be updated with new naming
- **FR-011**: Troubleshooting guide MUST be updated with new command names
- **FR-012**: PyPI package descriptions MUST reference consistent branding
- **FR-013**: Deprecation notices MUST be added for old command names
- **FR-014**: Migration guide MUST be created documenting the transition

### Key Entities

- **Repository**: GitHub repository hosting the code; renamed from doc-serve-skill to agent-brain
- **CLI Package**: PyPI package `agent-brain-cli` providing management commands
- **Server Package**: PyPI package `agent-brain-rag` providing the RAG server
- **Skill**: Claude Code skill for document search integration
- **Commands**: CLI entry points for users to interact with the system

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All documentation references use consistent agent-brain naming (100% compliance)
- **SC-002**: New users can complete installation using only agent-brain commands within 5 minutes
- **SC-003**: Existing users can migrate to new commands within 10 minutes using migration guide
- **SC-004**: Both old and new command names work after upgrade (backward compatibility)
- **SC-005**: GitHub repository URL redirects work for 6 months after rename
- **SC-006**: PyPI package downloads continue uninterrupted during transition
- **SC-007**: Skill discovery in Claude Code returns "using-agent-brain" for relevant searches

## Assumptions

- GitHub supports repository renames with automatic redirects
- PyPI package names (`agent-brain-rag`, `agent-brain-cli`) remain unchanged
- Existing data directories (`.claude/doc-serve/`) do not need renaming in v1.2
- Users accept a transition period with deprecation warnings

## Out of Scope

- Renaming the internal data directory from `.claude/doc-serve/` to `.claude/agent-brain/`
- Changing PyPI package names (already published as agent-brain-*)
- Database or index format changes
- API endpoint changes
