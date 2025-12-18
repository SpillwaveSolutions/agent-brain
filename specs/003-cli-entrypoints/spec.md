# Feature Specification: CLI Entry Points Installation

**Feature Branch**: `003-cli-entrypoints`
**Created**: 2025-12-16
**Status**: In Progress (v2 - Self-documenting CLI)
**Input**: User description: "Create CLI entry points for doc-svr-ctl and doc-serve-server Python packages so they can be invoked directly from the command line after installation (pip install -e . or pip install). doc-svr-ctl should invoke the CLI defined in cli.py, and doc-serve-server should start the FastAPI server."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Install and Run doc-svr-ctl CLI (Priority: P1)

A developer wants to install the doc-svr-ctl package and immediately use it from any terminal session to interact with the Doc-Serve server.

**Why this priority**: This is the primary control tool for managing the doc-serve ecosystem. Users need CLI access to check status, query documents, index files, and manage the server.

**Independent Test**: Can be fully tested by installing the package and running `doc-svr-ctl --help` to verify the command is available system-wide.

**Acceptance Scenarios**:

1. **Given** a developer has cloned the repository, **When** they run `pip install -e ./doc-svr-ctl` from the project root, **Then** the `doc-svr-ctl` command becomes available in their terminal.
2. **Given** doc-svr-ctl is installed, **When** the user runs `doc-svr-ctl --version`, **Then** the version number is displayed (e.g., "doc-svr-ctl, version 1.0.0").
3. **Given** doc-svr-ctl is installed, **When** the user runs `doc-svr-ctl status`, **Then** it attempts to connect to the server and reports status.

---

### User Story 2 - Install and Run doc-serve Server (Priority: P1)

A developer wants to install the doc-serve-server package and start the FastAPI server using a simple command.

**Why this priority**: The server is the core component that the CLI interacts with. Without a running server, no document indexing or querying is possible.

**Independent Test**: Can be fully tested by installing the package and running `doc-serve` to verify the server starts and responds on the configured port.

**Acceptance Scenarios**:

1. **Given** a developer has cloned the repository, **When** they run `pip install -e ./doc-serve-server` from the project root, **Then** the `doc-serve` command becomes available in their terminal.
2. **Given** doc-serve-server is installed, **When** the user runs `doc-serve`, **Then** the FastAPI server starts and listens on the configured host/port.
3. **Given** doc-serve is running, **When** the user navigates to `http://localhost:8000/docs`, **Then** they see the Swagger UI documentation.
4. **Given** doc-serve-server is installed, **When** the user runs `doc-serve --help`, **Then** usage information is displayed showing available options.
5. **Given** doc-serve-server is installed, **When** the user runs `doc-serve --version`, **Then** the version number is displayed.

---

### User Story 3 - Poetry-based Installation (Priority: P2)

A developer using Poetry wants to install the packages using Poetry's workflow instead of pip.

**Why this priority**: Many Python developers prefer Poetry for dependency management. Supporting this workflow improves developer experience.

**Independent Test**: Can be fully tested by running `poetry install` in each package directory and verifying commands are available.

**Acceptance Scenarios**:

1. **Given** a developer is in the doc-svr-ctl directory, **When** they run `poetry install`, **Then** the package is installed with all dependencies and `doc-svr-ctl` is available.
2. **Given** a developer is in the doc-serve-server directory, **When** they run `poetry install`, **Then** the package is installed with all dependencies and `doc-serve` is available.

---

### Edge Cases

- What happens when the user installs without a virtual environment? The commands should still be available in the user's PATH.
- How does the system handle installation when dependencies are missing? The installer should provide clear error messages.
- What happens when both packages are installed in the same virtual environment? Both commands should work independently.
- What happens if the server port is already in use? The server should display a clear error message.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `doc-svr-ctl` command accessible from the terminal after package installation.
- **FR-002**: System MUST provide a `doc-serve` command accessible from the terminal after package installation.
- **FR-003**: The `doc-svr-ctl` command MUST invoke the CLI group defined in `src/cli.py` with all subcommands (status, query, index, reset).
- **FR-004**: The `doc-serve` command MUST start the FastAPI server using uvicorn with configured settings.
- **FR-005**: Both commands MUST support standard pip installation methods (`pip install .` and `pip install -e .`).
- **FR-006**: Both commands MUST support Poetry installation method (`poetry install`).
- **FR-007**: The `doc-svr-ctl` command MUST display version information when run with `--version` flag.
- **FR-008**: The `doc-svr-ctl` command MUST display help information when run with `--help` flag.
- **FR-009**: The `doc-serve` command MUST display help information when run with `--help` flag, showing available options (host, port, reload).
- **FR-010**: The `doc-serve` command MUST display version information when run with `--version` flag.
- **FR-011**: Both CLI tools MUST be self-documenting, providing clear usage information without requiring external documentation.

### Key Entities

- **doc-svr-ctl Package**: CLI tool for managing and querying the Doc-Serve server. Provides commands for status, query, index, and reset operations.
- **doc-serve-server Package**: FastAPI-based REST API service for document indexing and semantic search.
- **Entry Point**: Configuration that maps a command name to a Python function, enabling direct command-line invocation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After installation, `doc-svr-ctl --help` displays usage information within 1 second.
- **SC-002**: After installation, `doc-serve` starts the server and responds to health checks within 5 seconds.
- **SC-003**: Both installation methods (pip and poetry) successfully register the commands on the system PATH.
- **SC-004**: Users can install both packages in the same environment without conflicts.
- **SC-005**: Commands remain functional across terminal sessions after installation (no re-activation required beyond standard virtualenv activation).
- **SC-006**: After installation, `doc-serve --help` displays usage information within 1 second without starting the server.

## Assumptions

- Users have Python 3.10+ installed.
- Users understand how to activate virtual environments if using them.
- The existing `pyproject.toml` configurations are the source of truth for package metadata.
- Poetry-core is available for building packages.
