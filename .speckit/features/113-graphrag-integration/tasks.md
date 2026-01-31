# Tasks: GraphRAG Integration

**Input**: Design documents from `.speckit/features/113-graphrag-integration/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests included per Constitution III (Test-Alongside)

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Server**: `doc-serve-server/doc_serve_server/`
- **CLI**: `doc-svr-ctl/doc_svr_ctl/`
- **Tests**: `doc-serve-server/tests/`, `doc-svr-ctl/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and configuration

- [ ] T001 Add GraphRAG configuration settings to doc-serve-server/doc_serve_server/config/settings.py
- [ ] T002 [P] Update doc-serve-server/doc_serve_server/storage_paths.py to include graph_index directory
- [ ] T003 [P] Add optional dependency groups to doc-serve-server/pyproject.toml for graphrag and graphrag-kuzu
- [ ] T004 [P] Add GRAPH and MULTI to QueryMode enum in doc-serve-server/doc_serve_server/models/query.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core graph infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Create GraphStoreManager class in doc-serve-server/doc_serve_server/storage/graph_store.py
- [ ] T006 Implement SimplePropertyGraphStore initialization and persistence in graph_store.py
- [ ] T007 Add Kuzu store factory with fallback in doc-serve-server/doc_serve_server/storage/graph_store.py
- [ ] T008 [P] Create GraphIndexStatus model in doc-serve-server/doc_serve_server/models/graph.py
- [ ] T009 [P] Create GraphTriple model in doc-serve-server/doc_serve_server/models/graph.py
- [ ] T010 [P] Extend QueryResult model with graph_score, related_entities, relationship_path in doc-serve-server/doc_serve_server/models/query.py
- [ ] T011 [P] Unit test for GraphStoreManager in doc-serve-server/tests/unit/test_graph_store.py
- [ ] T012 Export graph models from doc-serve-server/doc_serve_server/models/__init__.py
- [ ] T013 Export graph store from doc-serve-server/doc_serve_server/storage/__init__.py

**Checkpoint**: Graph storage foundation ready - user story implementation can begin

---

## Phase 3: User Story 1 - Enable Graph-Based Document Retrieval (Priority: P1) 🎯 MVP

**Goal**: Enable optional GraphRAG with graph-only query mode

**Independent Test**: Enable GraphRAG, index documents, query with `--mode graph`

### Tests for User Story 1

- [ ] T014 [P] [US1] Unit test for DynamicLLMPathExtractor wrapper in doc-serve-server/tests/unit/test_graph_extractors.py
- [ ] T015 [P] [US1] Unit test for GraphIndexManager in doc-serve-server/tests/unit/test_graph_index.py
- [ ] T016 [P] [US1] Integration test for graph query execution in doc-serve-server/tests/integration/test_graph_query.py

### Implementation for User Story 1

- [ ] T017 [P] [US1] Create LLM entity extractor wrapper in doc-serve-server/doc_serve_server/indexing/graph_extractors.py
- [ ] T018 [P] [US1] Create GraphIndexManager class in doc-serve-server/doc_serve_server/indexing/graph_index.py
- [ ] T019 [US1] Implement graph index building from documents in graph_index.py
- [ ] T020 [US1] Implement graph index persistence and loading in graph_index.py
- [ ] T021 [US1] Add _execute_graph_query method to doc-serve-server/doc_serve_server/services/query_service.py
- [ ] T022 [US1] Update execute_query to route GRAPH mode in query_service.py
- [ ] T023 [US1] Add GraphRAG disabled check with informative error in query_service.py
- [ ] T024 [US1] Integrate graph building into doc-serve-server/doc_serve_server/services/indexing_service.py
- [ ] T025 [US1] Add progress callback for graph building stage in indexing_service.py
- [ ] T026 [US1] Update /query endpoint to accept graph parameters in doc-serve-server/doc_serve_server/api/routers/query.py
- [ ] T027 [US1] Add graph_index to health status in doc-serve-server/doc_serve_server/api/routers/health.py
- [ ] T028 [US1] Add --mode graph option to doc-svr-ctl/doc_svr_ctl/commands/query.py
- [ ] T029 [US1] Add graph status to doc-svr-ctl/doc_svr_ctl/commands/status.py

**Checkpoint**: User Story 1 complete - GraphRAG enabled, graph-only queries working

---

## Phase 4: User Story 2 - Query with Multi-Mode Fusion (Priority: P2)

**Goal**: Combine vector, BM25, and graph results using RRF

**Independent Test**: Query with `--mode multi`, verify results include all three retrieval sources

### Tests for User Story 2

- [ ] T030 [P] [US2] Unit test for RRF fusion in doc-serve-server/tests/unit/test_rrf_fusion.py
- [ ] T031 [P] [US2] Integration test for multi-mode query in doc-serve-server/tests/integration/test_graph_query.py

### Implementation for User Story 2

- [ ] T032 [US2] Implement RRF fusion helper function in doc-serve-server/doc_serve_server/services/query_service.py
- [ ] T033 [US2] Add _execute_multi_query method with parallel execution in query_service.py
- [ ] T034 [US2] Update execute_query to route MULTI mode in query_service.py
- [ ] T035 [US2] Add --mode multi option to doc-svr-ctl/doc_svr_ctl/commands/query.py

**Checkpoint**: User Story 2 complete - multi-mode fusion queries working

---

## Phase 5: User Story 3 - Configure Graph Store Backend (Priority: P3)

**Goal**: Support both SimplePropertyGraphStore and Kuzu backends

**Independent Test**: Set GRAPH_STORE_TYPE=kuzu, verify indexing and queries work

### Tests for User Story 3

- [ ] T036 [P] [US3] Unit test for Kuzu store initialization in doc-serve-server/tests/unit/test_graph_store.py
- [ ] T037 [P] [US3] Integration test for store type switching in doc-serve-server/tests/integration/test_graph_query.py

### Implementation for User Story 3

- [ ] T038 [US3] Implement Kuzu store initialization in doc-serve-server/doc_serve_server/storage/graph_store.py
- [ ] T039 [US3] Add store type detection and fallback warning in graph_store.py
- [ ] T040 [US3] Add store_type to GraphIndexStatus in health responses

**Checkpoint**: User Story 3 complete - Kuzu backend configurable

---

## Phase 6: User Story 4 - Extract Code Relationships from AST Metadata (Priority: P3)

**Goal**: Extract import and hierarchy relationships from code without LLM calls

**Independent Test**: Index a Python codebase, query for import relationships

### Tests for User Story 4

- [ ] T041 [P] [US4] Unit test for code metadata extraction in doc-serve-server/tests/unit/test_graph_extractors.py
- [ ] T042 [P] [US4] Integration test for code relationship queries in doc-serve-server/tests/integration/test_graph_query.py

### Implementation for User Story 4

- [ ] T043 [US4] Create code metadata extractor in doc-serve-server/doc_serve_server/indexing/graph_extractors.py
- [ ] T044 [US4] Extract import relationships from chunk.metadata.imports in graph_extractors.py
- [ ] T045 [US4] Extract containment relationships from symbol hierarchies in graph_extractors.py
- [ ] T046 [US4] Integrate code extractor into GraphIndexManager in graph_index.py
- [ ] T047 [US4] Add source_type-based extraction routing (doc vs code) in graph_index.py

**Checkpoint**: User Story 4 complete - code relationships extracted from AST

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T048 [P] Add graph rebuild endpoint parameter to doc-serve-server/doc_serve_server/api/routers/index.py
- [ ] T049 [P] Add structured logging for graph operations across all modules
- [ ] T050 Contract test for QueryMode enum values in doc-serve-server/tests/contract/test_query_modes.py
- [ ] T051 [P] Update doc-serve-server README with GraphRAG configuration section
- [ ] T052 Run quickstart.md validation script with GraphRAG enabled
- [ ] T053 Performance testing for graph queries on sample dataset
- [ ] T054 Update CLI help text for new query modes in doc-svr-ctl

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies - can start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 - BLOCKS all user stories
- **Phase 3-6 (User Stories)**: All depend on Phase 2 completion
  - US1 (P1): No dependencies on other stories
  - US2 (P2): Depends on US1 (needs graph query infrastructure)
  - US3 (P3): No dependencies on other stories (parallel with US4)
  - US4 (P3): No dependencies on other stories (parallel with US3)
- **Phase 7 (Polish)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1 (Setup)
     │
     ▼
Phase 2 (Foundational) ─────────────────────┐
     │                                       │
     ▼                                       │
Phase 3: US1 (P1) 🎯 MVP                    │
     │                                       │
     ▼                                       │
Phase 4: US2 (P2)                           │
                                             │
     ┌──────────────────┬────────────────────┘
     │                  │
     ▼                  ▼
Phase 5: US3 (P3)   Phase 6: US4 (P3)
     │                  │
     └──────────────────┘
             │
             ▼
     Phase 7 (Polish)
```

### Parallel Opportunities

**Within Phase 1**:
- T002, T003, T004 can run in parallel

**Within Phase 2**:
- T008, T009, T010, T011 can run in parallel after T005-T007

**Within User Stories**:
- All tests can be written in parallel before implementation
- Models within a story marked [P] can run in parallel

**Across User Stories**:
- US3 and US4 can be implemented in parallel (both P3)

---

## Parallel Example: User Story 1

```bash
# Launch tests in parallel:
Task: "Unit test for DynamicLLMPathExtractor wrapper"
Task: "Unit test for GraphIndexManager"
Task: "Integration test for graph query execution"

# Launch extractors in parallel:
Task: "Create LLM entity extractor wrapper"
Task: "Create GraphIndexManager class"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test GraphRAG enable/disable, graph queries
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy (MVP!)
3. Add User Story 2 → Test independently → Deploy (MULTI mode)
4. Add User Stories 3 & 4 in parallel → Deploy (Kuzu + Code relationships)
5. Polish → Final release

### Parallel Team Strategy

With 2 developers after Foundational:
- Developer A: User Story 1 → User Story 2
- Developer B: User Story 3 + User Story 4 (can start after US1 foundation)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Constitution III: Tests written alongside implementation
- Constitution V: Complexity justified (optional feature, follows existing patterns)
- All graph features skip execution when ENABLE_GRAPH_INDEX=false
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
