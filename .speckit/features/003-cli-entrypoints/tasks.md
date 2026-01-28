# Tasks: CLI Entry Points Installation

**Input**: Design documents from `/specs/003-cli-entrypoints/`
**Prerequisites**: plan.md (complete), spec.md (complete), research.md (complete), quickstart.md (complete)

**Tests**: Included per Test-Alongside constitution principle

**Organization**: Tasks grouped by user story for independent implementation and testing

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Monorepo structure**:
  - `doc-svr-ctl/` - CLI package
  - `doc-serve-server/` - Server package
  - `specs/003-cli-entrypoints/` - Feature documentation

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify existing configuration and prepare test infrastructure

- [ ] T001 Verify doc-svr-ctl/pyproject.toml has correct entry point configuration
- [ ] T002 Verify doc-serve-server/pyproject.toml has correct entry point configuration
- [ ] T003 [P] Ensure doc-svr-ctl/tests/ directory exists
- [ ] T004 [P] Ensure doc-serve-server/tests/ directory exists

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Ensure package structure supports entry point resolution

**⚠️ CRITICAL**: Entry points depend on correct module paths

- [ ] T005 Verify doc-svr-ctl/src/__init__.py exports __version__
- [ ] T006 Verify doc-svr-ctl/src/cli.py has cli() function callable
- [ ] T007 [P] Verify doc-serve-server/src/api/main.py has run() function callable
- [ ] T008 [P] Verify doc-serve-server/src/__init__.py exists and is importable

**Checkpoint**: Package structure verified - user story implementation can begin

---

## Phase 3: User Story 1 - Install and Run doc-svr-ctl CLI (Priority: P1) 🎯 MVP

**Goal**: Developer can install doc-svr-ctl and use it from command line

**Independent Test**: Run `pip install -e ./doc-svr-ctl && doc-svr-ctl --help`

### Tests for User Story 1

- [ ] T009 [P] [US1] Create CLI entry point test in doc-svr-ctl/tests/test_cli_install.py
- [ ] T010 [P] [US1] Add test for --help flag returning expected output
- [ ] T011 [P] [US1] Add test for --version flag returning version string
- [ ] T012 [US1] Add test for cli() function being importable from src.cli

### Implementation for User Story 1

- [ ] T013 [US1] Install doc-svr-ctl package with pip install -e ./doc-svr-ctl
- [ ] T014 [US1] Verify doc-svr-ctl command available in terminal PATH
- [ ] T015 [US1] Run doc-svr-ctl --help and confirm output
- [ ] T016 [US1] Run doc-svr-ctl --version and confirm version displayed
- [ ] T017 [US1] Run all tests in doc-svr-ctl/tests/ to verify

**Checkpoint**: doc-svr-ctl CLI fully functional and independently testable

---

## Phase 4: User Story 2 - Install and Run doc-serve Server (Priority: P1)

**Goal**: Developer can install doc-serve-server and start the server

**Independent Test**: Run `pip install -e ./doc-serve-server && doc-serve` (Ctrl+C to stop)

### Tests for User Story 2

- [ ] T018 [P] [US2] Create server entry point test in doc-serve-server/tests/test_server_install.py
- [ ] T019 [P] [US2] Add test for run() function being importable from src.api.main
- [ ] T020 [US2] Add smoke test that server starts without crash

### Implementation for User Story 2

- [ ] T021 [US2] Install doc-serve-server package with pip install -e ./doc-serve-server
- [ ] T022 [US2] Verify doc-serve command available in terminal PATH
- [ ] T023 [US2] Run doc-serve and confirm server starts on configured port
- [ ] T024 [US2] Verify http://localhost:8000/docs shows Swagger UI
- [ ] T025 [US2] Run all tests in doc-serve-server/tests/ to verify

**Checkpoint**: doc-serve server fully functional and independently testable

---

## Phase 5: User Story 3 - Poetry-based Installation (Priority: P2)

**Goal**: Developer can install packages using Poetry workflow

**Independent Test**: Run `cd doc-svr-ctl && poetry install && poetry run doc-svr-ctl --help`

### Tests for User Story 3

- [ ] T026 [US3] Verify poetry.lock exists or can be generated in doc-svr-ctl/
- [ ] T027 [US3] Verify poetry.lock exists or can be generated in doc-serve-server/

### Implementation for User Story 3

- [ ] T028 [US3] Run poetry install in doc-svr-ctl/ directory
- [ ] T029 [US3] Verify doc-svr-ctl available via poetry run doc-svr-ctl --help
- [ ] T030 [US3] Run poetry install in doc-serve-server/ directory
- [ ] T031 [US3] Verify doc-serve available via poetry run doc-serve
- [ ] T032 [US3] Document Poetry workflow in quickstart.md (already done)

**Checkpoint**: Both installation methods (pip and Poetry) verified working

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final verification and documentation

- [ ] T033 Verify both packages can be installed in same virtual environment
- [ ] T034 [P] Run all doc-svr-ctl tests pass
- [ ] T035 [P] Run all doc-serve-server tests pass
- [ ] T036 Validate quickstart.md instructions work end-to-end
- [ ] T037 Update specs/003-cli-entrypoints/spec.md status to Complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - verifies prerequisites
- **User Story 1 (Phase 3)**: Depends on Foundational - doc-svr-ctl
- **User Story 2 (Phase 4)**: Depends on Foundational - doc-serve-server (can run parallel to US1)
- **User Story 3 (Phase 5)**: Depends on US1 and US2 completion
- **Polish (Phase 6)**: Depends on all user stories

### User Story Dependencies

- **User Story 1 (P1)**: Independent - can start after Foundational
- **User Story 2 (P1)**: Independent - can start after Foundational (parallel to US1)
- **User Story 3 (P2)**: Depends on US1 and US2 packages being verified working

### Parallel Opportunities

**Setup Phase (can run in parallel):**
- T003 and T004 (different directories)

**Foundational Phase (can run in parallel):**
- T007 and T008 (different packages)

**User Stories 1 and 2 (can run in parallel):**
- Entire US1 (Phase 3) and US2 (Phase 4) can be worked simultaneously
- They operate on different packages with no shared dependencies

**Within User Story 1:**
- T009, T010, T011 (different test functions, same file - write together)

**Within User Story 2:**
- T018, T019 (different test functions, same file - write together)

**Polish Phase:**
- T034 and T035 (different test suites)

---

## Parallel Example: User Stories 1 & 2

```bash
# These can run simultaneously (different packages):

# Developer A: User Story 1 (doc-svr-ctl)
pip install -e ./doc-svr-ctl
doc-svr-ctl --help
doc-svr-ctl --version

# Developer B: User Story 2 (doc-serve-server)
pip install -e ./doc-serve-server
doc-serve
# Ctrl+C to stop
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (verify configs)
2. Complete Phase 2: Foundational (verify package structure)
3. Complete Phase 3: User Story 1 (doc-svr-ctl)
4. **STOP and VALIDATE**: `doc-svr-ctl --help` works
5. Can use CLI immediately

### Incremental Delivery

1. Setup + Foundational → Configs verified
2. User Story 1 → CLI tool available (MVP!)
3. User Story 2 → Server command available
4. User Story 3 → Poetry workflow documented
5. Each increment adds installation method support

### Key Insight

Since pyproject.toml files **already have entry points configured**, most "implementation" is actually **verification testing**. The primary work is:
1. Creating tests to verify entry points work
2. Testing installation methods
3. Documenting the workflow

---

## Notes

- Entry points already exist in pyproject.toml - this feature verifies they work
- Tests follow Test-Alongside constitution principle
- Both pip and Poetry installation methods must be verified
- User Stories 1 and 2 are both P1 priority and can run in parallel
- Commit after each verification step to track progress

---

## Phase 7: V2 - Self-Documenting CLI (2025-12-16)

**Purpose**: Make doc-serve command self-documenting with --help and --version support

### Tasks

- [ ] T038 Add Click dependency to doc-serve-server/pyproject.toml
- [ ] T039 Create Click CLI wrapper in doc-serve-server/src/api/main.py with cli() function
- [ ] T040 Add --host option to CLI (default: from settings)
- [ ] T041 Add --port option to CLI (default: from settings)
- [ ] T042 Add --reload option to CLI (default: from DEBUG setting)
- [ ] T043 Add --version decorator to CLI
- [ ] T044 Update entry point in pyproject.toml from run to cli
- [ ] T045 Add test for doc-serve --help in tests/test_server_install.py
- [ ] T046 Add test for doc-serve --version in tests/test_server_install.py
- [ ] T047 Reinstall doc-serve-server package
- [ ] T048 Verify doc-serve --help shows usage
- [ ] T049 Verify doc-serve --version shows version
- [ ] T050 Run all tests to confirm no regressions

**Checkpoint**: Both CLI tools are self-documenting
