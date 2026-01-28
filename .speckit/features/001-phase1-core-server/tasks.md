# Tasks: Phase 1 - Core Server

**Input**: Design documents from `specs/001-phase1-core-server/`
**Prerequisites**: plan.md (required), spec.md (required)
**Status**: Phase 1 COMPLETE - All components implemented (Server, CLI, Skill)

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Create monorepo structure with doc-serve-server, doc-serve-skill, doc-svr-ctl
- [x] T002 Initialize Poetry project with Python 3.10+ dependencies
- [x] T003 [P] Configure linting (ruff), formatting (black), typing (mypy)

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T004 Create Pydantic settings configuration (src/config/settings.py)
- [x] T005 [P] Initialize Chroma vector store manager (src/storage/vector_store.py)
- [x] T006 [P] Setup FastAPI application with lifespan events (src/api/main.py)
- [x] T007 Create base Pydantic models (src/models/*.py)
- [x] T008 Configure structured logging in main.py

**Checkpoint**: Foundation complete

---

## Phase 3: User Story 1 - Index Documents (Priority: P1)

**Goal**: Users can index documents from a folder path

### Implementation for User Story 1

- [x] T009 [P] [US1] Create IndexRequest, IndexResponse models (src/models/index.py)
- [x] T010 [P] [US1] Create IndexingState, IndexingStatusEnum (src/models/index.py)
- [x] T011 [US1] Implement DocumentLoader (src/indexing/document_loader.py)
- [x] T012 [US1] Implement ContextAwareChunker (src/indexing/chunking.py)
- [x] T013 [US1] Implement EmbeddingGenerator (src/indexing/embedding.py)
- [x] T014 [US1] Implement IndexingService (src/services/indexing_service.py)
- [x] T015 [US1] Create index router with POST /index (src/api/routers/index.py)
- [x] T016 [US1] Add POST /index/add for incremental indexing
- [x] T017 [US1] Add DELETE /index for reset

**Checkpoint**: User Story 1 COMPLETE

---

## Phase 4: User Story 2 - Query Documents (Priority: P1)

**Goal**: Users can search indexed documents semantically

### Implementation for User Story 2

- [x] T018 [P] [US2] Create QueryRequest, QueryResponse, QueryResult (src/models/query.py)
- [x] T019 [US2] Implement QueryService with similarity search (src/services/query_service.py)
- [x] T020 [US2] Create query router with POST /query (src/api/routers/query.py)
- [x] T021 [US2] Add GET /query/count for document count

**Checkpoint**: User Story 2 COMPLETE

---

## Phase 5: User Story 3 - Health Check (Priority: P2)

**Goal**: Skills/CLI can check server readiness

### Implementation for User Story 3

- [x] T022 [P] [US3] Create HealthStatus, IndexingStatus (src/models/health.py)
- [x] T023 [US3] Create health router with GET /health (src/api/routers/health.py)
- [x] T024 [US3] Add GET /health/status for detailed indexing status

**Checkpoint**: User Story 3 COMPLETE

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T025 Configure CORS middleware
- [x] T026 Expose OpenAPI at /docs, /redoc, /openapi.json
- [x] T027 Add root endpoint with API info
- [x] T028 Add unit tests (tests/unit/) - 22 tests for models
- [x] T029 Add integration tests (tests/integration/) - 17 tests for API endpoints
- [x] T030 Add contract tests for OpenAPI compliance (OpenAPI docs endpoint tests)

---

## Phase 7: Peripheral Packages

### doc-svr-ctl (CLI Tool) - COMPLETE

- [x] T031 Create CLI entry point with Click
- [x] T032 Implement API client for server communication
- [x] T033 Implement `doc-svr-ctl status` command
- [x] T034 Implement `doc-svr-ctl query <text>` command
- [x] T035 Implement `doc-svr-ctl index <folder>` command
- [x] T036 Implement `doc-svr-ctl reset` command
- [x] T037 Add CLI tests (25 tests passing)

### doc-serve-skill (Claude Skill) - COMPLETE

- [x] T038 Create skill YAML configuration (SKILL.md with frontmatter)
- [x] T039 Document health check workflow before queries
- [x] T040 Create query_domain.py script for domain searches
- [x] T041 Create API reference documentation

---

## Phase 8: E2E Integration Testing - COMPLETE

**Goal**: True end-to-end tests using real server and CLI (not mocks)

### Infrastructure

- [x] T042 Create e2e/ directory structure (integration/, fixtures/, scripts/, config/)
- [x] T043 Create test documents (5 coffee brewing markdown files)
- [x] T044 Create e2e/config/e2e_config.py with paths and timeouts

### Core Scripts

- [x] T045 Create e2e/scripts/run_e2e.py main orchestrator
- [x] T046 Create e2e/scripts/wait_for_health.py health polling utility
- [x] T047 Create e2e/scripts/run_e2e.sh shell wrapper for CI/CD

### Pytest Integration

- [x] T048 Create e2e/integration/conftest.py with server lifecycle fixtures
- [x] T049 Create e2e/integration/test_full_workflow.py (20+ test scenarios)
- [x] T050 Create e2e/integration/test_error_handling.py

### Documentation

- [x] T051 Create docs/plans/e2e_testing_plan.md
- [x] T052 Update specs/001-phase1-core-server/tasks.md with E2E tasks

**Checkpoint**: E2E Testing COMPLETE

---

## Summary

| Phase | Status | Tasks |
|-------|--------|-------|
| Setup | COMPLETE | T001-T003 |
| Foundational | COMPLETE | T004-T008 |
| US1 Index | COMPLETE | T009-T017 |
| US2 Query | COMPLETE | T018-T021 |
| US3 Health | COMPLETE | T022-T024 |
| Polish | COMPLETE | T025-T030 (39 tests passing) |
| CLI | COMPLETE | T031-T037 (25 tests passing) |
| Skill | COMPLETE | T038-T041 |
| E2E Testing | COMPLETE | T042-T052 (20+ E2E scenarios) |

**Server implementation: 30/30 tasks complete (100%)**
**CLI implementation: 7/7 tasks complete (100%)**
**Skill implementation: 4/4 tasks complete (100%)**
**E2E Testing: 11/11 tasks complete (100%)**
**Overall Phase 1: 52/52 tasks complete (100%)**

### Test Coverage

#### doc-serve-server
- **Unit tests**: 22 tests (models validation)
- **Integration tests**: 17 tests (API endpoints with mocks)
- **Total**: 39 tests, all passing

#### doc-svr-ctl
- **API Client tests**: 13 tests
- **CLI Command tests**: 12 tests
- **Total**: 25 tests, all passing

#### e2e/integration
- **Workflow tests**: 15+ tests (real server, real CLI)
- **Error handling tests**: 5+ tests
- **Total**: 20+ E2E tests

**Combined Total: 84+ tests**
