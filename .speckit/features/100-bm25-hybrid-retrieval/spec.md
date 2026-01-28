# Feature Specification: BM25 & Hybrid Retrieval

**Feature Branch**: `100-bm25-hybrid-retrieval`
**Created**: 2025-12-18
**Completed**: 2025-12-18
**Status**: ✅ COMPLETED - Merged to main
**PR**: https://github.com/SpillwaveSolutions/doc-serve-skill/pull/2
**Input**: Product Roadmap Phase 2

## User Scenarios & Testing

### User Story 1 - Query with BM25 Keyword Search (Priority: P1)

A user wants to search documents using exact keyword matching for precise technical queries like function names, error codes, or specific terms.

**Why this priority**: BM25 enables precise term matching that vector search may miss. Essential for technical documentation where exact strings matter.

**Independent Test**: POST query with `mode=bm25` and verify exact keyword matches appear first in results.

**Acceptance Scenarios**:

1. **Given** documents are indexed, **When** I POST to `/query` with `mode=bm25` and query "RecursiveCharacterTextSplitter", **Then** results containing the exact term appear first with high BM25 scores
2. **Given** documents indexed with code examples, **When** I query for "ERROR_CODE_404", **Then** exact matches are returned regardless of semantic meaning
3. **Given** no BM25 index exists, **When** I POST a BM25 query, **Then** I receive a 503 error indicating BM25 index not ready
4. **Given** documents indexed, **When** I query for a term not in any document, **Then** I receive an empty results array

---

### User Story 2 - Hybrid Search with RRF Fusion (Priority: P1)

A user wants the best of both semantic and keyword search, combining vector similarity with BM25 term matching using Reciprocal Rank Fusion.

**Why this priority**: Hybrid search provides the most robust retrieval quality by leveraging both approaches. This is the recommended default mode.

**Independent Test**: POST query with `mode=hybrid` and verify results combine both vector and BM25 rankings intelligently.

**Acceptance Scenarios**:

1. **Given** documents indexed, **When** I POST to `/query` with `mode=hybrid`, **Then** results blend vector and BM25 rankings using RRF
2. **Given** a query with both semantic meaning and exact terms, **When** I use hybrid mode, **Then** documents matching both criteria rank highest
3. **Given** hybrid mode query, **When** I examine response metadata, **Then** I see separate `vector_score` and `bm25_score` fields plus combined `score`
4. **Given** default query without mode specified, **When** I POST to `/query`, **Then** hybrid mode is used by default

---

### User Story 3 - Alpha Weight Configuration (Priority: P2)

A user wants to tune the balance between vector and keyword search in hybrid mode to optimize for their specific use case.

**Why this priority**: Different use cases benefit from different balances. Technical docs may favor BM25, conceptual docs may favor vector.

**Independent Test**: POST queries with different alpha values and verify score weighting changes accordingly.

**Acceptance Scenarios**:

1. **Given** hybrid mode, **When** I POST with `alpha=0.0`, **Then** results are purely BM25-based
2. **Given** hybrid mode, **When** I POST with `alpha=1.0`, **Then** results are purely vector-based
3. **Given** hybrid mode, **When** I POST with `alpha=0.5` (default), **Then** results equally weight both strategies
4. **Given** alpha outside 0.0-1.0 range, **When** I POST query, **Then** I receive a 400 error with validation message

---

### User Story 4 - Search Mode Selection via CLI (Priority: P2)

A user wants to select search mode from the doc-svr-ctl CLI tool without modifying API calls directly.

**Why this priority**: CLI users need the same flexibility as API users. Improves developer experience.

**Independent Test**: Run `doc-svr-ctl query "text" --mode bm25` and verify mode is passed correctly to API.

**Acceptance Scenarios**:

1. **Given** CLI installed, **When** I run `doc-svr-ctl query "test" --mode bm25`, **Then** query uses BM25 mode
2. **Given** CLI installed, **When** I run `doc-svr-ctl query "test" --mode hybrid --alpha 0.7`, **Then** query uses hybrid with specified alpha
3. **Given** CLI installed, **When** I run `doc-svr-ctl query "test"` without mode, **Then** hybrid mode is used by default

---

### User Story 5 - Enhanced Scoring Metadata (Priority: P3)

A user wants to understand how each result was ranked to debug and tune retrieval quality.

**Why this priority**: Transparency in scoring helps users tune their queries and understand system behavior.

**Independent Test**: Examine query response and verify score breakdown metadata is present.

**Acceptance Scenarios**:

1. **Given** hybrid query, **When** I examine a result, **Then** I see `vector_score`, `bm25_score`, and combined `score` fields
2. **Given** BM25-only query, **When** I examine results, **Then** I see `bm25_score` and `term_frequency` metadata
3. **Given** vector-only query, **When** I examine results, **Then** I see `vector_score` (same as current behavior)

---

### Edge Cases

- What happens when BM25 index is building while query received? (Return 503 with "index building" status)
- How does system handle queries with only stopwords? (BM25 returns no results, fallback to vector)
- What happens when vector and BM25 return disjoint result sets? (RRF handles gracefully, ranks all results)
- How does system handle extremely long queries? (Truncate to max token limit with warning)
- What if document has no keywords (all semantic content)? (BM25 returns low scores, vector compensates in hybrid)

## Requirements

### Functional Requirements

- **FR-001**: System MUST support BM25 retrieval mode via `mode=bm25` query parameter
- **FR-002**: System MUST support hybrid retrieval via `mode=hybrid` query parameter (default)
- **FR-003**: System MUST support vector-only retrieval via `mode=vector` query parameter
- **FR-004**: System MUST implement Reciprocal Rank Fusion (RRF) for hybrid score combination
- **FR-005**: System MUST expose `alpha` parameter (0.0-1.0) for hybrid weight tuning
- **FR-006**: System MUST build and maintain BM25 index alongside vector index during ingestion
- **FR-007**: System MUST include scoring metadata (vector_score, bm25_score) in query responses
- **FR-008**: CLI MUST support `--mode` and `--alpha` flags for query command
- **FR-009**: System MUST synchronize BM25 and vector indexes (add/delete affects both)
- **FR-010**: API MUST validate mode parameter and return 400 for invalid values

### Key Entities

- **BM25Index**: Sparse keyword index for term frequency-based retrieval
- **HybridRetriever**: Combines VectorRetriever and BM25Retriever results
- **RRFScorer**: Implements Reciprocal Rank Fusion algorithm
- **QueryMode**: Enum with values `vector`, `bm25`, `hybrid`
- **ScoringMetadata**: Contains vector_score, bm25_score, combined score, and term frequencies

## Success Criteria

### Measurable Outcomes

- **SC-001**: BM25 queries return results in < 500ms for typical corpus sizes
- **SC-002**: Hybrid mode provides measurably better retrieval quality than vector-only on benchmark queries
- **SC-003**: All existing Phase 1 functionality remains working (backward compatibility)
- **SC-004**: BM25 index adds < 50% storage overhead compared to vector-only
- **SC-005**: Index rebuild time increases < 2x compared to vector-only
- **SC-006**: API response format remains backward compatible (new fields are additive)
