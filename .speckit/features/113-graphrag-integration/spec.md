# Feature Specification: GraphRAG Integration

**Feature Branch**: `113-graphrag-integration`
**Created**: 2026-01-30
**Status**: Draft
**Input**: User description: "Add optional GraphRAG capabilities to doc-serve using LlamaIndex PropertyGraphIndex"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Enable Graph-Based Document Retrieval (Priority: P1)

As a developer using doc-serve, I want to enable optional GraphRAG capabilities so that I can discover relationships between concepts, entities, and code elements that keyword and vector search alone would miss.

**Why this priority**: This is the core value proposition - enabling knowledge graph-based retrieval that surfaces hidden relationships between documents and code. Without this, the feature provides no value.

**Independent Test**: Can be fully tested by enabling GraphRAG, indexing a documentation set, and querying with `--mode graph` to retrieve related entities and their connections.

**Acceptance Scenarios**:

1. **Given** GraphRAG is disabled (default), **When** a user indexes documents, **Then** the system behaves exactly as before with no additional processing or storage.
2. **Given** GraphRAG is enabled via configuration, **When** a user indexes documents, **Then** the system extracts entities and relationships and stores them in a graph index.
3. **Given** GraphRAG is enabled and documents are indexed, **When** a user queries with graph mode, **Then** the system returns results based on entity relationships and graph traversal.

---

### User Story 2 - Query with Multi-Mode Fusion (Priority: P2)

As a developer, I want to combine vector, keyword (BM25), and graph-based search results so that I get the most comprehensive and relevant answers by leveraging all three retrieval methods.

**Why this priority**: Multi-mode fusion provides the highest quality results by combining the strengths of each retrieval method. This builds on P1 and delivers the full hybrid retrieval experience.

**Independent Test**: Can be tested by running a query with `--mode multi` and verifying results include contributions from vector similarity, keyword matching, and graph relationships.

**Acceptance Scenarios**:

1. **Given** GraphRAG is enabled and documents are indexed, **When** a user queries with multi mode, **Then** results are fused from vector, BM25, and graph retrievers using reciprocal rank fusion.
2. **Given** GraphRAG is disabled, **When** a user queries with multi mode, **Then** the system returns an informative error explaining that GraphRAG must be enabled.

---

### User Story 3 - Configure Graph Store Backend (Priority: P3)

As a system administrator, I want to choose between lightweight (SimplePropertyGraphStore) and production-grade (Kuzu) graph storage backends so that I can scale the graph index appropriately for my deployment size.

**Why this priority**: Most users will be satisfied with the default lightweight store. This provides an upgrade path for users with larger knowledge bases who need better performance.

**Independent Test**: Can be tested by configuring the system to use Kuzu backend and verifying graph operations work correctly with file-based persistence.

**Acceptance Scenarios**:

1. **Given** graph store type is set to "simple" (default), **When** documents are indexed with GraphRAG enabled, **Then** the graph is stored in JSON format for easy inspection and portability.
2. **Given** graph store type is set to "kuzu", **When** documents are indexed with GraphRAG enabled, **Then** the graph is stored in Kuzu's embedded database format for better query performance.

---

### User Story 4 - Extract Code Relationships from AST Metadata (Priority: P3)

As a developer indexing code repositories, I want the system to automatically extract relationships from code structure (imports, class hierarchies, function calls) so that I can query for code dependencies and architectural patterns.

**Why this priority**: Code-specific entity extraction leverages existing AST metadata without additional LLM calls, providing value for code repositories at minimal cost.

**Independent Test**: Can be tested by indexing a codebase and querying for import relationships or class hierarchies using graph mode.

**Acceptance Scenarios**:

1. **Given** code metadata extraction is enabled and a Python file imports other modules, **When** the file is indexed, **Then** import relationships are captured in the graph.
2. **Given** a class contains methods, **When** the file is indexed, **Then** containment relationships are captured between the class and its methods.

---

### Edge Cases

- What happens when GraphRAG is enabled but no entities are extracted from a document?
  - The document is still indexed in vector and BM25 stores; graph store simply has no nodes for that document.
- How does the system handle documents with very dense entity relationships?
  - Extraction is limited to a configurable maximum triplets per chunk to prevent graph explosion.
- What happens if the LLM extraction model is unavailable?
  - Indexing continues with code metadata extraction only (if enabled); LLM extraction is skipped with a warning.
- How does the system handle graph store corruption?
  - Graph index can be rebuilt independently without affecting vector or BM25 indexes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow GraphRAG to be enabled or disabled via configuration, with disabled as the default.
- **FR-002**: System MUST support five query modes: VECTOR (vector-only), BM25 (keyword-only), HYBRID (vector + BM25), GRAPH (graph-only traversal), and MULTI (vector + BM25 + graph fusion).
- **FR-003**: System MUST return an informative error when GRAPH or MULTI modes are used while GraphRAG is disabled.
- **FR-004**: System MUST persist graph data to disk and reload it on startup when GraphRAG is enabled.
- **FR-005**: System MUST support two graph storage backends: SimplePropertyGraphStore (default) and Kuzu (optional).
- **FR-006**: System MUST extract entities and relationships using LLM-based extraction for documentation content.
- **FR-007**: System MUST extract code relationships from existing AST metadata (imports, class hierarchies, symbols) without additional LLM calls.
- **FR-008**: System MUST limit entity extraction to a configurable maximum triplets per chunk to prevent unbounded graph growth.
- **FR-009**: System MUST provide progress feedback during graph index building.
- **FR-010**: System MUST support rebuilding the graph index independently of vector and BM25 indexes.
- **FR-011**: System MUST fuse multi-mode results using reciprocal rank fusion (RRF) with configurable weights.
- **FR-012**: CLI MUST support `--mode vector`, `--mode bm25`, `--mode hybrid`, `--mode graph`, and `--mode multi` options for the query command.
- **FR-013**: CLI MUST display graph index status in the status command output when GraphRAG is enabled.

### Key Entities

- **Entity**: A named concept, object, or code element extracted from documents (e.g., "UserAuthentication", "FastAPI", "ChromaDB").
- **Relationship**: A typed connection between two entities (e.g., "imports", "contains", "extends", "references").
- **Triple**: A subject-predicate-object structure representing a relationship (Entity -> Relationship -> Entity).
- **Graph Store**: The persistent storage backend for entities and relationships (SimplePropertyGraphStore or Kuzu).
- **Property Graph Index**: The LlamaIndex index structure that manages entity extraction, storage, and retrieval.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can enable GraphRAG and complete document indexing without errors, with graph extraction completing for 95% of documents.
- **SC-002**: Graph-mode queries return relevant entity-related results within 2 seconds for indexes up to 10,000 documents.
- **SC-003**: Multi-mode queries demonstrate improved relevance over single-mode queries, measurable by user satisfaction in finding related concepts.
- **SC-004**: System with GraphRAG disabled performs identically to current system with no measurable latency increase.
- **SC-005**: Graph store persists correctly across server restarts with 100% data integrity.
- **SC-006**: Code repositories indexed with GraphRAG show import and class hierarchy relationships queryable via graph mode.

## Assumptions

- LlamaIndex v0.14.x PropertyGraphIndex and SimplePropertyGraphStore are stable and production-ready (verified: v0.14.13 is current as of January 2026).
- Kuzu graph store integration (llama-index-graph-stores-kuzu v0.6.0) is compatible with LlamaIndex v0.14.x.
- LangExtract (Google's entity extraction library) is actively maintained and suitable for document entity extraction.
- Existing AST metadata from code ingestion contains sufficient information for basic code relationship extraction.
- Users understand that LLM-based entity extraction adds processing time and API costs to indexing.

## Dependencies

### Required Libraries (verified January 2026)

| Library                        | Version   | Purpose                                      | Required When                  |
| ------------------------------ | --------- | -------------------------------------------- | ------------------------------ |
| llama-index-core               | ^0.14.13  | PropertyGraphIndex, SimplePropertyGraphStore | Always (already installed)     |
| langextract                    | ^0.1.x    | LLM-based entity extraction for documents    | GRAPH_USE_LLM_EXTRACTION=true  |
| llama-index-graph-stores-kuzu  | ^0.6.0    | Kuzu embedded graph database                 | GRAPH_STORE_TYPE=kuzu          |

### Notes on Library Status

- **llama-index-core**: Current version 0.14.13 (January 2026). SimplePropertyGraphStore is the recommended lightweight option with JSON persistence.
- **langextract**: Actively maintained by Google. Supports multiple LLM providers (Gemini, OpenAI, Anthropic, Groq, Ollama).
- **llama-index-graph-stores-kuzu**: Version 0.6.0 released September 2025. Compatible with current LlamaIndex ecosystem. No deprecation notices.

## Out of Scope

- Graph visualization endpoint (future enhancement)
- Custom entity type configuration UI
- Neo4j or other server-based graph databases
- Real-time graph updates (batch reindexing only)
- Cross-index graph queries (single index per instance)
