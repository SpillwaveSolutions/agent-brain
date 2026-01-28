# Feature Specification: UDS Transport & Claude Plugin Evolution

**Feature Branch**: `102-uds-claude-plugin`
**Created**: 2025-12-18
**Status**: Draft
**Input**: Product Roadmap Phase 4

## User Scenarios & Testing

### User Story 1 - Unix Domain Socket Communication (Priority: P1)

The doc-serve server supports Unix Domain Socket (UDS) transport for lower-latency local queries.

**Why this priority**: UDS provides 10-50x latency improvement over HTTP for local communication. Critical for responsive Claude skill experience.

**Independent Test**: Start server with UDS enabled, query via socket, measure latency vs HTTP.

**Acceptance Scenarios**:

1. **Given** server started with UDS enabled, **When** I connect via socket at `/tmp/doc-serve.sock`, **Then** I can send queries and receive responses
2. **Given** UDS transport, **When** I query with same parameters as HTTP, **Then** response format is identical
3. **Given** UDS enabled, **When** HTTP is also enabled (default), **Then** both transports work simultaneously
4. **Given** socket path already in use, **When** server starts, **Then** it logs warning and cleans up stale socket

---

### User Story 2 - Claude Skill UDS Auto-Detection (Priority: P1)

The Claude skill automatically detects and prefers UDS when available for faster queries.

**Why this priority**: Transparent performance improvement for users. No manual configuration needed.

**Independent Test**: Install skill, verify it checks for UDS socket before falling back to HTTP.

**Acceptance Scenarios**:

1. **Given** UDS socket exists, **When** Claude skill initializes, **Then** it connects via UDS
2. **Given** UDS not available, **When** skill initializes, **Then** it falls back to HTTP gracefully
3. **Given** UDS connection fails mid-session, **When** next query occurs, **Then** skill retries with HTTP
4. **Given** both transports available, **When** skill queries, **Then** UDS is preferred with measurable latency improvement

---

### User Story 3 - Server Lifecycle Management (Priority: P2)

The Claude plugin can automatically start, stop, and manage the doc-serve server lifecycle.

**Why this priority**: Reduces manual setup. Users shouldn't need to manage server separately.

**Independent Test**: Claude skill starts server when needed, stops when session ends.

**Acceptance Scenarios**:

1. **Given** server not running, **When** Claude skill needs to query, **Then** it starts the server automatically
2. **Given** server started by skill, **When** Claude session ends, **Then** server is stopped gracefully
3. **Given** server already running (user-started), **When** skill initializes, **Then** it uses existing server without restart
4. **Given** multiple Claude sessions, **When** one ends, **Then** server stays running for other sessions

---

### User Story 4 - Rich Slash Commands (Priority: P2)

Claude users can use specialized slash commands for different search modes and operations.

**Why this priority**: Improved UX for power users. More intuitive interaction patterns.

**Independent Test**: Use `/search`, `/doc`, `/code` commands and verify correct behavior.

**Acceptance Scenarios**:

1. **Given** corpus indexed, **When** user types `/search authentication`, **Then** hybrid search is executed across all content
2. **Given** corpus indexed, **When** user types `/doc S3 bucket patterns`, **Then** only documentation is searched
3. **Given** corpus indexed, **When** user types `/code login handler python`, **Then** only Python code is searched
4. **Given** no index available, **When** user types `/search`, **Then** helpful error message with setup instructions

---

### User Story 5 - Multi-Step Research Agent (Priority: P3)

Claude can break down complex questions into multiple sub-queries for comprehensive research.

**Why this priority**: Advanced capability for complex questions. Builds on basic search functionality.

**Independent Test**: Ask complex question, verify Claude executes multiple searches and synthesizes.

**Acceptance Scenarios**:

1. **Given** complex question about architecture, **When** user asks, **Then** Claude searches docs, code, and examples before answering
2. **Given** research mode enabled, **When** Claude queries, **Then** it explains its search strategy
3. **Given** conflicting information found, **When** synthesizing, **Then** Claude highlights discrepancies
4. **Given** incomplete results, **When** researching, **Then** Claude notes gaps and suggests additional sources

---

### Edge Cases

- What happens when socket permissions prevent connection? (Fall back to HTTP, log permission error)
- How does system handle socket in non-standard location? (Configurable socket path)
- What happens when server crashes while skill is connected via UDS? (Detect disconnect, restart server)
- How does UDS work on Windows? (Not supported, HTTP-only on Windows)
- What happens when multiple skill instances try to manage server? (Coordination via lock file)

## Requirements

### Functional Requirements

- **FR-001**: Server MUST support Unix Domain Socket transport in addition to HTTP
- **FR-002**: UDS MUST use same request/response format as HTTP (JSON)
- **FR-003**: Socket path MUST be configurable (default: `/tmp/doc-serve.sock`)
- **FR-004**: Server MUST clean up stale sockets on startup
- **FR-005**: Claude skill MUST auto-detect and prefer UDS when available
- **FR-006**: Skill MUST fall back to HTTP if UDS unavailable or fails
- **FR-007**: Skill MUST support automatic server lifecycle management
- **FR-008**: Plugin MUST implement `/search`, `/doc`, `/code` slash commands
- **FR-009**: Server MUST support concurrent UDS and HTTP connections
- **FR-010**: Skill MUST handle transport failures gracefully with retries

### Key Entities

- **UDSTransport**: Unix Domain Socket server implementation
- **SocketPath**: Configurable path to Unix socket file
- **TransportSelector**: Logic for choosing UDS vs HTTP
- **ServerManager**: Starts/stops server, tracks ownership
- **SlashCommand**: Skill command definitions (/search, /doc, /code)
- **ResearchAgent**: Multi-step query orchestration (optional)

## Success Criteria

### Measurable Outcomes

- **SC-001**: UDS queries complete in < 50ms for typical queries (10-50x faster than HTTP)
- **SC-002**: Skill automatically uses UDS when available without configuration
- **SC-003**: Server lifecycle management works reliably across session boundaries
- **SC-004**: All Phase 1-3 functionality remains working with both transports
- **SC-005**: Slash commands provide intuitive search experience
- **SC-006**: UDS socket is properly cleaned up on server shutdown
