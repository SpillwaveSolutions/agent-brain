# Feature Specification: Multi-Instance Architecture

**Feature Branch**: `109-multi-instance-architecture`
**Created**: 2026-01-27
**Status**: Draft
**Input**: User description: "Refactor doc-serve from single-instance to concurrent multi-project operation with per-project and shared daemon deployment modes"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Per-Project Server Lifecycle (Priority: P1)

As a developer working on a project, I want doc-serve to run as a dedicated instance tied to my project so that my document indexes are isolated from other projects, the server starts automatically with a collision-free port, and I can discover the running instance from any subdirectory within my project.

**Why this priority**: This is the foundational capability. Without per-project isolation, users cannot run doc-serve on multiple projects simultaneously, which is the core problem being solved. This story delivers the MVP: one project, one isolated server, reliable discovery.

**Independent Test**: Start a doc-serve instance from a project root, verify it binds to a unique port, confirm the discovery file is written, query the server from a nested subdirectory, stop the server, and verify cleanup occurs.

**Acceptance Scenarios**:

1. **Given** a project with no running doc-serve instance, **When** the user starts doc-serve from the project root, **Then** the server starts on a collision-free port and writes a discovery file within the project's state directory.
2. **Given** a running doc-serve instance for a project, **When** the user runs a status check from any subdirectory within the project, **Then** the system discovers the running instance and reports its address and indexing status.
3. **Given** a running doc-serve instance, **When** the user stops the server, **Then** the discovery file, lock file, and PID file are all removed cleanly.
4. **Given** a project whose previous doc-serve instance crashed, **When** the user starts doc-serve again, **Then** the system detects the stale state (dead process), cleans up orphaned files, and starts a fresh instance.
5. **Given** two separate projects, **When** the user starts doc-serve in each, **Then** both instances run concurrently on different ports with fully isolated indexes.

---

### User Story 2 - Project Root Discovery and State Isolation (Priority: P2)

As a developer, I want doc-serve to reliably determine my project root regardless of which subdirectory I'm in or whether I accessed the project through symlinks, so that the same project always uses the same state directory and index data.

**Why this priority**: Reliable project root resolution is essential for consistent behavior. Without it, the same project accessed via different paths could produce multiple orphaned state directories and duplicate indexes.

**Independent Test**: Navigate to various subdirectories and symlinked paths within a project, run the project root resolution, and verify it always returns the same canonical path.

**Acceptance Scenarios**:

1. **Given** a project under version control, **When** the user runs doc-serve from any subdirectory, **Then** the system resolves the project root to the repository top level.
2. **Given** a project accessed through a symlink, **When** the user runs doc-serve, **Then** the system resolves the symlink and uses the canonical (real) path for state storage.
3. **Given** a project not under version control but containing standard project markers, **When** the user runs doc-serve, **Then** the system walks up the directory tree and uses the first directory containing a recognized marker.
4. **Given** a directory with no recognizable project markers, **When** the user runs doc-serve, **Then** the system uses the current directory as the project root and stores state locally.

---

### User Story 3 - Shared Daemon Mode (Priority: P3)

As a developer working on many projects simultaneously, I want the option to run a single shared doc-serve daemon that serves multiple projects, so that I can reduce resource overhead while maintaining per-project index isolation.

**Why this priority**: This is an optimization for power users. Per-project mode (P1) already solves the core problem. Shared mode reduces memory and CPU usage when many projects are active, but is not required for the MVP.

**Independent Test**: Start a shared daemon, register two projects with it, verify each project's indexes are isolated, query each project independently, and confirm the shared daemon's discovery file is written into each project's state directory.

**Acceptance Scenarios**:

1. **Given** a shared daemon is running, **When** a project registers with it, **Then** the daemon creates isolated storage for that project and writes a discovery pointer into the project's state directory.
2. **Given** two projects registered with a shared daemon, **When** the user queries one project, **Then** only that project's indexed documents are searched.
3. **Given** a shared daemon with multiple projects, **When** the user checks the daemon's status, **Then** the system reports the number of active projects and their indexing states.
4. **Given** a project configured for shared mode, **When** the shared daemon is not running, **Then** the system reports that the daemon is unavailable and provides instructions to start it.

---

### User Story 4 - Agent and Skill Integration (Priority: P4)

As a Claude Code skill author, I want a standard way to discover a running doc-serve instance for the current project (or start one automatically), so that my skill can reliably connect to the correct server without hardcoding URLs or ports.

**Why this priority**: This enables the broader ecosystem of skills and agents to integrate with doc-serve. It depends on P1 (per-project mode) being complete and stable.

**Independent Test**: From a skill or agent context, call the discovery function, verify it finds a running instance or starts one, and confirm the returned base URL is valid and responsive.

**Acceptance Scenarios**:

1. **Given** a running doc-serve instance for the current project, **When** a skill calls the discovery function, **Then** it receives the base URL of the running instance.
2. **Given** no running doc-serve instance, **When** a skill calls the discovery-with-auto-start function, **Then** the system starts an instance and returns the base URL once it's ready.
3. **Given** a stale discovery file (server crashed), **When** a skill calls the discovery function, **Then** the system detects the stale state, cleans up, and reports no running instance (or auto-starts if configured).

---

### Edge Cases

- What happens when the port assigned by the OS is immediately reused by another process before the discovery file is read? The system MUST validate the health endpoint, not just the port number.
- What happens when two users start doc-serve for the same project concurrently? The lock file protocol MUST prevent double-start with atomic lock acquisition.
- What happens when the state directory is on a read-only filesystem? The system MUST report a clear error explaining that writable state storage is required.
- What happens when a project is moved to a different directory after indexing? The stored project root path will no longer match, and the system MUST detect this and re-index rather than serving stale data.
- What happens when the discovery file exists but the server process belongs to a different user? The system MUST verify process ownership or rely on health check validation.
- What happens when switching between per-project and shared mode? The system MUST NOT mix state from different modes; each mode maintains its own storage.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support running multiple concurrent doc-serve instances, each serving a different project with fully isolated indexes.
- **FR-002**: System MUST allocate ports automatically without conflicts by binding to an OS-assigned port and reporting the actual port after startup.
- **FR-003**: In per-project mode, the system MUST store all project-specific state (indexes, configuration, logs) within the project's own directory structure, allowing state to travel with the project. In shared daemon mode, index data is stored centrally under `~/.doc-serve/projects/`, while a lightweight discovery pointer is written into the project's state directory to enable agent discovery.
- **FR-004**: System MUST write a machine-readable discovery file after startup containing the server's address, enabling agents and tools to find the running instance.
- **FR-005**: System MUST resolve the project root deterministically regardless of the user's current working directory or symlink usage, using version control root detection as the primary method.
- **FR-006**: System MUST detect and clean up stale state from crashed or killed instances by validating that the recorded process is alive and the health endpoint responds.
- **FR-007**: System MUST prevent double-start of instances for the same project using an exclusive lock file protocol.
- **FR-008**: System MUST support a shared daemon mode where a single process serves multiple projects with per-project index isolation, as an alternative to per-project instances.
- **FR-009**: System MUST support configuration through a precedence chain: command-line flags override environment variables, which override project-level config files, which override global config files, which override built-in defaults.
- **FR-010**: System MUST clean up all runtime artifacts (discovery file, lock file, PID file) on graceful shutdown.
- **FR-011**: System MUST provide lifecycle management commands: start, stop, status, and list (all running instances).
- **FR-012**: System MUST provide an initialization command that creates a project-level configuration file with sensible defaults.
- **FR-013**: System MUST expose mode information (per-project or shared) in the health endpoint response.
- **FR-014**: System MUST support a discovery function that agents and skills can call to find a running instance or determine that none is available.
- **FR-015**: In shared daemon mode, all requests MUST include a project identifier to route operations to the correct project's indexes.
- **FR-016**: System MUST NOT require migration of existing index data; re-indexing from source documents is the expected path for existing users.

### Key Entities

- **Runtime State**: Represents a running doc-serve instance, including its mode (per-project or shared), address, port, process identifier, and startup timestamp. In shared mode, also includes the project identifier.
- **Project Configuration**: Per-project settings including deployment mode preference, host binding, port preference, and paths for data and log storage. Can optionally be version-controlled.
- **Lock File**: An exclusive lock that prevents concurrent startup of instances for the same project. Contains the owning process identifier for stale detection.
- **Project Identifier**: A deterministic identifier derived from the canonical project root path, used in shared mode to route requests and isolate storage.
- **Discovery Pointer**: In shared mode, a lightweight file written into each project's state directory that points to the shared daemon's address rather than containing full instance details.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can run doc-serve instances for 5 or more projects concurrently on the same machine without port conflicts or index cross-contamination.
- **SC-002**: A user starting doc-serve from any subdirectory within a project reaches the same server instance 100% of the time, regardless of path or symlink usage.
- **SC-003**: When a doc-serve instance crashes, the next startup attempt recovers cleanly within 5 seconds without manual intervention (no orphaned lock files block restart).
- **SC-004**: Agents and skills can discover a running doc-serve instance for the current project in under 1 second without any hardcoded configuration.
- **SC-005**: In shared daemon mode, indexing or querying one project does not affect the results or performance of another project's queries.
- **SC-006**: All runtime artifacts (discovery files, lock files, PID files) are fully cleaned up on graceful shutdown, leaving no orphaned state.
- **SC-007**: Configuration changes via command-line flags take effect immediately without editing any files.
- **SC-008**: A new user can start doc-serve for a project and run their first query within 4 steps (init, start, index, query) without reading documentation. The `init` step is optional if defaults are acceptable, reducing to 3 steps (start, index, query).

## Assumptions

- The default deployment mode is per-project (one server per repository). Shared daemon mode is opt-in.
- The state directory for per-project mode is `<repo>/.claude/doc-serve/`, following the existing Claude Code convention of storing tool state under `.claude/`.
- Runtime files (discovery file, lock, PID) should be added to `.gitignore`; project configuration can optionally be committed.
- Existing users will need to re-index their documents after upgrading; no automated data migration is provided.
- The system targets local development use (localhost binding by default). Remote/network deployment is out of scope.
- Health check validation is the authoritative test for whether an instance is alive, not just process existence checks.

## Out of Scope

- Remote or networked deployment (multi-machine setups)
- Authentication or authorization between agents and the doc-serve instance
- Automated data migration from the current single-instance storage layout
- GUI or web-based management interface
- Load balancing across multiple shared daemon instances
