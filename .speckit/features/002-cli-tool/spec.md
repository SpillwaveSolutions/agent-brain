# Feature Specification: CLI Tool (doc-svr-ctl)

**Feature Branch**: `002-cli-tool`
**Created**: 2025-12-15
**Status**: In Progress
**Input**: README.md requirements for CLI

## User Scenarios & Testing

### User Story 1 - Check Server Status (Priority: P1)

A user wants to check if the doc-serve server is running and its current state.

**Why this priority**: Essential for debugging and monitoring before other operations.

**Independent Test**: Run `doc-svr-ctl status` and verify it shows server health.

**Acceptance Scenarios**:

1. **Given** server is running, **When** I run `doc-svr-ctl status`, **Then** I see
   "healthy" status with document counts
2. **Given** server is indexing, **When** I run `doc-svr-ctl status`, **Then** I see
   "indexing" with progress percentage
3. **Given** server is not running, **When** I run `doc-svr-ctl status`, **Then** I see
   "Server not reachable" error with helpful message

---

### User Story 2 - Query Documents (Priority: P1)

A user wants to search indexed documents from the command line.

**Why this priority**: Primary use case for testing and quick lookups.

**Independent Test**: Run `doc-svr-ctl query "search term"` and see results.

**Acceptance Scenarios**:

1. **Given** documents indexed, **When** I run `doc-svr-ctl query "python"`, **Then**
   I see matching results with source files and scores
2. **Given** no matches, **When** I run query, **Then** I see "No results found"
3. **Given** server not ready, **When** I run query, **Then** I see appropriate error

---

### User Story 3 - Index Documents (Priority: P2)

A user wants to trigger document indexing from the command line.

**Why this priority**: Setup operation, less frequent than querying.

**Independent Test**: Run `doc-svr-ctl index /path/to/docs` and verify indexing starts.

**Acceptance Scenarios**:

1. **Given** valid folder path, **When** I run `doc-svr-ctl index ./docs`, **Then**
   indexing starts and I see job ID
2. **Given** invalid path, **When** I run index command, **Then** I see clear error
3. **Given** indexing in progress, **When** I run index, **Then** I see conflict message

---

### User Story 4 - Reset Index (Priority: P3)

A user wants to clear all indexed documents and start fresh.

**Why this priority**: Maintenance operation, rarely needed.

**Independent Test**: Run `doc-svr-ctl reset` and verify index is cleared.

**Acceptance Scenarios**:

1. **Given** documents indexed, **When** I run `doc-svr-ctl reset --yes`, **Then**
   index is cleared and I see confirmation
2. **Given** no --yes flag, **When** I run reset, **Then** I'm prompted for confirmation

---

### Edge Cases

- What happens with network timeout? (Show timeout error with retry suggestion)
- What happens with invalid server URL? (Show connection error)
- How to handle very long query results? (Paginate or truncate with --limit)

## Requirements

### Functional Requirements

- **FR-001**: CLI MUST connect to doc-serve server via HTTP
- **FR-002**: CLI MUST support configurable server URL (--url or DOC_SERVE_URL env)
- **FR-003**: CLI MUST provide `status` command showing server health
- **FR-004**: CLI MUST provide `query` command for semantic search
- **FR-005**: CLI MUST provide `index` command to trigger indexing
- **FR-006**: CLI MUST provide `reset` command with confirmation
- **FR-007**: CLI MUST display results in human-readable format (rich tables)
- **FR-008**: CLI MUST support JSON output format (--json flag)
- **FR-009**: CLI MUST show helpful error messages on failures

### Key Entities

- **APIClient**: HTTP client for communicating with doc-serve server
- **Command**: Click command group with subcommands
- **Config**: Server URL, timeout, output format settings

## Success Criteria

### Measurable Outcomes

- **SC-001**: All commands complete within 5 seconds for typical operations
- **SC-002**: Error messages clearly indicate problem and suggest solution
- **SC-003**: JSON output is valid and parseable
- **SC-004**: CLI is installable via `pip install` or `poetry install`
