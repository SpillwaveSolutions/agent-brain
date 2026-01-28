# Feature Specification: Phase 1 - Core Server

**Feature Branch**: `001-phase1-core-server`
**Created**: 2025-12-15
**Status**: Implemented
**Input**: README.md Phase 1 requirements

## User Scenarios & Testing

### User Story 1 - Index Documents from Folder (Priority: P1)

A user wants to index a folder of documents so they can search them semantically.

**Why this priority**: Core functionality - without indexing, no search is possible.

**Independent Test**: Can be tested by calling `POST /index` with a valid folder path
and verifying documents appear in the vector store.

**Acceptance Scenarios**:

1. **Given** a folder with markdown files exists, **When** I POST to `/index` with
   that folder path, **Then** I receive a job_id and status "started"
2. **Given** indexing is complete, **When** I check `/health/status`, **Then** I see
   the total_documents and total_chunks counts > 0
3. **Given** an invalid folder path, **When** I POST to `/index`, **Then** I receive
   a 400 error with descriptive message

---

### User Story 2 - Query Indexed Documents (Priority: P1)

A user wants to search their indexed documents using natural language queries.

**Why this priority**: Core functionality - the primary value proposition.

**Independent Test**: After indexing, POST a query to `/query` and verify relevant
results are returned with similarity scores.

**Acceptance Scenarios**:

1. **Given** documents are indexed, **When** I POST a query to `/query`, **Then** I
   receive results with text, source, score, and chunk_id
2. **Given** documents are indexed, **When** I query with `top_k=3`, **Then** I
   receive at most 3 results
3. **Given** no documents indexed, **When** I POST a query, **Then** I receive a
   503 error indicating index not ready

---

### User Story 3 - Check Server Health (Priority: P2)

A Claude skill or CLI tool needs to check if the server is ready before querying.

**Why this priority**: Required for reliable integration - skill must know server state.

**Independent Test**: Call `/health` and `/health/status` and verify correct
status values based on server state.

**Acceptance Scenarios**:

1. **Given** server is idle and ready, **When** I GET `/health`, **Then** status
   is "healthy"
2. **Given** indexing is in progress, **When** I GET `/health`, **Then** status
   is "indexing"
3. **Given** server is ready, **When** I GET `/health/status`, **Then** I see
   total_documents, total_chunks, and indexed_folders

---

### User Story 4 - Add Documents to Existing Index (Priority: P3)

A user wants to add more documents without re-indexing everything.

**Why this priority**: Convenience feature - enables incremental updates.

**Independent Test**: Index folder A, then POST to `/index/add` with folder B,
verify documents from both folders are searchable.

**Acceptance Scenarios**:

1. **Given** documents already indexed, **When** I POST to `/index/add` with a
   new folder, **Then** total_documents increases
2. **Given** indexing in progress, **When** I POST to `/index/add`, **Then** I
   receive a 409 conflict error

---

### User Story 5 - Reset Index (Priority: P3)

A user wants to clear all indexed documents and start fresh.

**Why this priority**: Maintenance feature - allows clean slate.

**Independent Test**: Index documents, DELETE `/index`, verify total_documents = 0.

**Acceptance Scenarios**:

1. **Given** documents indexed, **When** I DELETE `/index`, **Then** total_chunks
   becomes 0
2. **Given** indexing in progress, **When** I DELETE `/index`, **Then** I receive
   a 409 conflict error

---

### Edge Cases

- What happens when folder contains unsupported file types? (Skipped gracefully)
- How does system handle very large files? (Chunked appropriately)
- What happens on embedding API failure? (Indexing fails with error message)
- How does system handle concurrent index requests? (409 Conflict)

## Requirements

### Functional Requirements

- **FR-001**: System MUST expose REST API on configurable host:port
- **FR-002**: System MUST index documents from specified folder paths
- **FR-003**: System MUST chunk documents using configurable chunk_size and overlap
- **FR-004**: System MUST generate embeddings using OpenAI text-embedding-3-large
- **FR-005**: System MUST store embeddings in Chroma vector store
- **FR-006**: System MUST support semantic similarity search via POST /query
- **FR-007**: System MUST expose health status at /health and /health/status
- **FR-008**: System MUST expose OpenAPI documentation at /docs
- **FR-009**: System MUST track indexing progress (documents processed, chunks created)
- **FR-010**: System MUST support adding documents to existing index
- **FR-011**: System MUST support resetting/clearing the index

### Key Entities

- **Document**: Source file loaded from disk (path, content, type)
- **Chunk**: Text segment with embeddings (text, embedding, source, chunk_id)
- **Query**: User search request (query text, top_k, similarity_threshold)
- **QueryResult**: Search result (text, source, score, chunk_id, metadata)
- **IndexingState**: Server indexing status (job_id, status, progress, errors)
- **HealthStatus**: Server health (status, message, timestamp, version)

## Success Criteria

### Measurable Outcomes

- **SC-001**: Server starts and accepts queries within 5 seconds
- **SC-002**: Health endpoint responds in < 100ms
- **SC-003**: Query response time < 2 seconds for typical queries
- **SC-004**: OpenAPI spec available at /openapi.json
- **SC-005**: All endpoints follow REST conventions (proper HTTP status codes)
