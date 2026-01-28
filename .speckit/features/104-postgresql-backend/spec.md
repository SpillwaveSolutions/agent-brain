# Feature Specification: PostgreSQL/AlloyDB Backend

**Feature Branch**: `104-postgresql-backend`
**Created**: 2025-12-18
**Status**: Draft
**Input**: Product Roadmap Phase 6

## User Scenarios & Testing

### User Story 1 - PostgreSQL with pgvector Storage (Priority: P1)

A user wants to store embeddings in PostgreSQL with pgvector for enterprise deployments with better scalability.

**Why this priority**: Core capability for enterprise users. PostgreSQL provides durability, replication, and familiar operations.

**Independent Test**: Configure PostgreSQL backend, index documents, verify vectors stored in database.

**Acceptance Scenarios**:

1. **Given** config with `storage.backend: postgres`, **When** server starts, **Then** it connects to PostgreSQL
2. **Given** PostgreSQL backend, **When** I index documents, **Then** vectors are stored in pgvector column
3. **Given** PostgreSQL backend, **When** I query, **Then** vector similarity search uses pgvector operators
4. **Given** PostgreSQL connection fails, **When** server starts, **Then** it fails with descriptive connection error

---

### User Story 2 - AlloyDB Connection (Priority: P2)

A user on Google Cloud wants to use AlloyDB for managed PostgreSQL with enhanced vector performance.

**Why this priority**: AlloyDB offers ScaNN indexes for faster vector search. Important for GCP users.

**Independent Test**: Configure AlloyDB connection, verify ScaNN index creation and queries work.

**Acceptance Scenarios**:

1. **Given** config with `storage.backend: alloydb`, **When** server starts, **Then** it connects to AlloyDB
2. **Given** AlloyDB backend, **When** I index documents, **Then** ScaNN index is created for vectors
3. **Given** AlloyDB backend, **When** I query large corpus, **Then** ScaNN provides faster results than standard pgvector
4. **Given** AlloyDB with IAM auth, **When** service account configured, **Then** connection succeeds

---

### User Story 3 - Native Hybrid Search (Priority: P1)

PostgreSQL's full-text search (tsvector/tsquery) provides native BM25-like keyword search combined with vector similarity.

**Why this priority**: Replaces custom BM25 implementation with PostgreSQL's mature full-text engine. More reliable.

**Independent Test**: Query with hybrid mode, verify both full-text and vector scores in results.

**Acceptance Scenarios**:

1. **Given** PostgreSQL backend with `hybrid_search: true`, **When** I query, **Then** results combine full-text and vector ranking
2. **Given** hybrid search enabled, **When** I query exact terms, **Then** PostgreSQL full-text ranking applies
3. **Given** hybrid search, **When** I use mode=bm25, **Then** only full-text search is used
4. **Given** hybrid search, **When** I use mode=vector, **Then** only vector similarity is used

---

### User Story 4 - JSONB Metadata Storage (Priority: P2)

Rich metadata (source, headings, summaries, language) is stored in JSONB columns with GIN indexes for fast filtering.

**Why this priority**: PostgreSQL JSONB provides flexible metadata storage with indexing. Better than Chroma metadata.

**Independent Test**: Index documents with metadata, filter queries by metadata fields.

**Acceptance Scenarios**:

1. **Given** documents indexed, **When** I examine PostgreSQL, **Then** metadata is stored as JSONB
2. **Given** metadata with `source_type=code`, **When** I filter by source_type, **Then** GIN index is used
3. **Given** metadata with `language=python`, **When** I filter by language, **Then** query is fast via index
4. **Given** complex metadata filter, **When** I query, **Then** JSONB operators provide correct results

---

### User Story 5 - Migration from Chroma (Priority: P3)

A user with existing Chroma index wants to migrate to PostgreSQL without losing data.

**Why this priority**: Users shouldn't lose work when upgrading storage backend.

**Independent Test**: Export Chroma data, import to PostgreSQL, verify all documents searchable.

**Acceptance Scenarios**:

1. **Given** existing Chroma index, **When** I run migration command, **Then** all chunks are exported
2. **Given** exported chunks, **When** I import to PostgreSQL, **Then** all metadata is preserved
3. **Given** migration complete, **When** I query, **Then** results match original Chroma queries
4. **Given** partial migration failure, **When** I retry, **Then** it resumes from last checkpoint

---

### Edge Cases

- What happens when pgvector extension not installed? (Clear error with installation instructions)
- How does system handle PostgreSQL version mismatch? (Minimum version check, error if too old)
- What happens when connection pool exhausted? (Queue with timeout, error after max wait)
- How does system handle PostgreSQL disk full? (Indexing fails gracefully, clear error)
- What happens when AlloyDB ScaNN not available? (Fall back to standard pgvector index)

## Requirements

### Functional Requirements

- **FR-001**: System MUST support PostgreSQL with pgvector as storage backend
- **FR-002**: System MUST support AlloyDB with ScaNN indexes
- **FR-003**: System MUST implement native hybrid search via `hybrid_search=True`
- **FR-004**: System MUST store metadata in JSONB columns with GIN indexes
- **FR-005**: System MUST support PostgreSQL full-text search (tsvector/tsquery)
- **FR-006**: Configuration MUST specify backend type (chroma | postgres | alloydb)
- **FR-007**: System MUST support connection pooling for PostgreSQL
- **FR-008**: System MUST support both password and IAM authentication
- **FR-009**: System MUST provide migration path from Chroma to PostgreSQL
- **FR-010**: System MUST support configurable text_search_config (e.g., "english")

### Key Entities

- **PGVectorStore**: LlamaIndex PostgreSQL vector store integration
- **AlloyDBVectorStore**: LlamaIndex AlloyDB integration
- **ConnectionPool**: Manages PostgreSQL connections
- **FullTextIndex**: PostgreSQL tsvector/tsquery configuration
- **MetadataSchema**: JSONB schema for document metadata
- **MigrationTool**: Chroma to PostgreSQL data migration

### Configuration Example

```yaml
storage:
  backend: postgres  # chroma | postgres | alloydb
  postgres:
    host: localhost
    port: 5432
    database: docserve
    user_env: POSTGRES_USER
    password_env: POSTGRES_PASSWORD
    pool_size: 10
    hybrid_search: true
    text_search_config: english
```

## Success Criteria

### Measurable Outcomes

- **SC-001**: PostgreSQL backend provides comparable query performance to Chroma for < 1M chunks
- **SC-002**: PostgreSQL backend scales better than Chroma for > 1M chunks
- **SC-003**: Native hybrid search provides equal or better quality than custom BM25 implementation
- **SC-004**: JSONB metadata filtering is fast (< 100ms for typical filters)
- **SC-005**: All Phase 1-5 functionality remains working with PostgreSQL backend
- **SC-006**: Migration from Chroma preserves all data and metadata
