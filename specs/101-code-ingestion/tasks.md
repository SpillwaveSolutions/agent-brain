# Tasks: Source Code Ingestion & Unified Corpus

**Input**: Design documents from `/specs/101-code-ingestion/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Test-Alongside approach required per constitution - unit and integration tests included

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**STATUS**: MVP Complete ✅ - US1, US2, US3, US4, US6 implemented and tested. US5 (AST-aware chunking) pending.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Add tree-sitter dependencies for Python, TypeScript, JavaScript to doc-serve-server/pyproject.toml
- [ ] T002 [P] Update doc-serve-server dependencies by running `poetry install` in doc-serve-server/
- [ ] T003 Verify tree-sitter parsers work with test code snippets in doc-serve-server/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Create CodeChunk dataclass in doc-serve-server/doc_serve_server/indexing/chunking.py
- [ ] T005 Update ChunkMetadata to support code-specific fields (language, symbol_name, start_line, end_line, section_summary) in doc-serve-server/doc_serve_server/indexing/chunking.py
- [ ] T006 Add language detection utility for file extensions in doc-serve-server/doc_serve_server/indexing/document_loader.py
- [ ] T007 Update QueryRequest/Result models with source_type and language filters in doc-serve-server/doc_serve_server/models/query.py
- [ ] T008 Update IndexRequest model with include_code, languages, exclude_patterns parameters in doc-serve-server/doc_serve_server/models/index.py

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - Index Source Code from Folder (Priority: P1) 🎯 MVP

**Goal**: Enable indexing of source code files alongside documentation

**Independent Test**: POST to `/index` with `include_code=true` and verify code files appear in the index

### Implementation for User Story 1

- [x] T009 [US1] Extend DocumentLoader.load_files() to support code file extensions (.py, .ts, .tsx, .js, .jsx) in doc-serve-server/doc_serve_server/indexing/document_loader.py
- [x] T010 [US1] Add CodeChunker class using LlamaIndex CodeSplitter for AST-aware chunking in doc-serve-server/doc_serve_server/indexing/chunking.py
- [x] T011 [US1] Update IndexingService to handle code files with language detection and CodeChunker in doc-serve-server/doc_serve_server/services/indexing_service.py
- [x] T012 [US1] Update /index endpoint to accept include_code, languages, exclude_patterns parameters in doc-serve-server/doc_serve_server/api/routers/index.py
- [x] T013 [US1] Add code chunk counting to /health/status endpoint in doc-serve-server/doc_serve_server/api/routers/health.py

**Checkpoint**: User Story 1 is functional - can index code files.

---

## Phase 4: User Story 2 - Cross-Reference Search (Priority: P1)

**Goal**: Enable unified search across both documentation and code

**Independent Test**: Query for a concept and verify results include both documentation and code examples

### Implementation for User Story 2

- [x] T014 [US2] Update /query endpoint with source_type and language filtering in doc-serve-server/doc_serve_server/api/routers/query.py
- [x] T015 [US2] Update VectorStoreManager.similarity_search() to support ChromaDB where filtering by source_type/language in doc-serve-server/doc_serve_server/storage/vector_store.py
- [x] T016 [US2] Update BM25Retriever to support metadata filtering for source_type/language in doc-serve-server/doc_serve_server/indexing/bm25_index.py
- [x] T017 [US2] Update QueryService to handle source_type/language filtering in doc-serve-server/doc_serve_server/services/query_service.py

**Checkpoint**: User Story 2 is functional - can search across docs and code.

---

## Phase 5: User Story 3 - Language-Specific Filtering (Priority: P2)

**Goal**: Enable filtering search results by programming language

**Independent Test**: Query with `language=python` and verify only Python code results are returned

### Implementation for User Story 3

- [x] T018 [US3] Add language validation to QueryRequest model in doc-serve-server/doc_serve_server/models/query.py
- [x] T019 [US3] Implement language filtering in VectorStoreManager.similarity_search() in doc-serve-server/doc_serve_server/storage/vector_store.py
- [x] T020 [US3] Implement language filtering in BM25Retriever.search() in doc-serve-server/doc_serve_server/indexing/bm25_index.py
- [x] T021 [US3] Add error handling for invalid language parameters in /query endpoint in doc-serve-server/doc_serve_server/api/routers/query.py

**Checkpoint**: User Story 3 is functional - can filter by programming language.

---

## Phase 6: User Story 4 - Code Summaries via SummaryExtractor (Priority: P2)

**Goal**: Generate natural language descriptions for code chunks

**Independent Test**: Index code and verify chunks have summary metadata attached

### Implementation for User Story 4

- [x] T022 [US4] Add SummaryExtractor integration to embedding pipeline in doc-serve-server/doc_serve_server/indexing/embedding.py
- [x] T023 [US4] Create code-specific summary prompts in doc-serve-server/doc_serve_server/indexing/embedding.py
- [x] T024 [US4] Update CodeChunker to optionally generate summaries during chunking in doc-serve-server/doc_serve_server/indexing/chunking.py
- [x] T025 [US4] Add summary generation to IndexingService pipeline in doc-serve-server/doc_serve_server/indexing/chunking.py

**Checkpoint**: User Story 4 is functional - code chunks include natural language summaries.

---

## Phase 7: User Story 5 - AST-Aware Chunking (Priority: P3)

**Goal**: Ensure code is chunked at logical boundaries using AST parsing

**Independent Test**: Index code and verify chunks align with function/class boundaries

### Implementation for User Story 5

- [ ] T026 [US5] Implement AST boundary detection in CodeChunker using tree-sitter in doc-serve-server/doc_serve_server/indexing/chunking.py
- [ ] T027 [US5] Add symbol name extraction from AST in CodeChunker in doc-serve-server/doc_serve_server/indexing/chunking.py
- [ ] T028 [US5] Add line number tracking for code chunks in CodeChunker in doc-serve-server/doc_serve_server/indexing/chunking.py
- [ ] T029 [US5] Update chunking tests to verify AST boundary preservation in doc-serve-server/tests/unit/test_chunking.py

**Checkpoint**: User Story 5 is functional - code chunking respects AST boundaries.

---

## Phase 8: User Story 6 - Corpus for Book/Tutorial Generation (Priority: P1)

**Goal**: Create a searchable corpus from SDK source code and documentation for writing tutorials

**Independent Test**: Index AWS CDK source + docs, query for patterns, verify comprehensive results

### Implementation for User Story 6

- [x] T030 [US6] Verify unified search works for SDK documentation + code in doc-serve-server/doc_serve_server/services/query_service.py
- [x] T031 [US6] Test cross-reference queries with SDK examples in doc-serve-server/tests/integration/test_unified_search.py
- [x] T032 [US6] Ensure metadata includes file paths and line numbers for citations in doc-serve-server/doc_serve_server/models/query.py

**Checkpoint**: User Story 6 is functional - SDK corpus supports tutorial writing.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T033 [P] Update doc-svr-ctl index command with --include-code, --languages, --exclude-patterns flags in doc-svr-ctl/doc_svr_ctl/commands/index.py
- [x] T034 [P] Update doc-svr-ctl query command with --source-type, --language filters in doc-svr-ctl/doc_svr_ctl/commands/query.py
- [x] T035 [P] Update README.md and docs/USER_GUIDE.md with code ingestion features
- [ ] T036 [P] Update doc-serve-skill/doc-serve/references/api_reference.md with new endpoints
- [ ] T037 [P] Update doc-serve-skill/doc-serve/references/troubleshooting-guide.md with code-specific issues
- [x] T038 Run full test suite: `task pr-qa-gate`
- [x] T039 Validate quickstart.md scenarios for code ingestion

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational phase completion
  - US1, US2, US6 can proceed in parallel (both P1)
  - US3, US4 can proceed after US1/US2 (P2)
  - US5 can proceed after foundational chunking (P3)
- **Polish (Final Phase)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Foundation → Independent MVP capability
- **User Story 2 (P1)**: Foundation → Requires US1 for data to search
- **User Story 3 (P2)**: Foundation → Independent filtering capability
- **User Story 4 (P2)**: Foundation → Independent summarization capability
- **User Story 5 (P3)**: Foundation → Independent AST chunking improvement
- **User Story 6 (P1)**: Foundation + US1/US2 → SDK corpus capability

### Within Each User Story

- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel
- US1, US2, US6 can be worked on in parallel after Foundation
- US3, US4, US5 can be worked on in parallel after Foundation
- CLI updates in Polish phase can run in parallel
- Documentation updates in Polish phase can run in parallel

---

## Parallel Example: User Stories 1 & 2

```bash
# Launch US1 and US2 in parallel after Foundation complete:
Task: "Extend DocumentLoader.load_files() to support code file extensions"
Task: "Update /query endpoint with source_type and language filtering"

# Launch CLI enhancements in parallel during Polish phase:
Task: "Update doc-svr-ctl index command with --include-code flags"
Task: "Update doc-svr-ctl query command with --source-type filters"
```

---

## Implementation Strategy

### MVP First (User Stories 1, 2 & 6 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (code indexing)
4. Complete Phase 4: User Story 2 (unified search)
5. Complete Phase 8: User Story 6 (SDK corpus)
6. **STOP and VALIDATE**: Test cross-reference search independently
7. Deploy/demo MVP with basic code ingestion

### Incremental Delivery

1. **Foundation** → Setup + Foundational phases
2. **MVP** → US1 + US2 + US6 (code indexing + unified search + SDK corpus)
3. **Enhanced** → US3 + US4 (language filtering + summaries)
4. **Polished** → US5 + Polish phase (AST chunking + docs)

### Parallel Team Strategy

With multiple developers:

1. **Foundation**: Team completes Setup + Foundational together
2. **MVP Sprint**:
   - Developer A: User Story 1 (code indexing)
   - Developer B: User Story 2 (unified search)
   - Developer C: User Story 6 (SDK corpus validation)
3. **Enhancement Sprint**:
   - Developer A: User Story 3 (language filtering)
   - Developer B: User Story 4 (summaries)
   - Developer C: User Story 5 (AST chunking)
4. **Polish Sprint**: All developers on CLI, docs, testing

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- All tasks include exact file paths for implementation
- MVP scope: US1 + US2 + US6 provides core code ingestion + search capability
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence</content>
<parameter name="filePath">specs/101-code-ingestion/tasks.md