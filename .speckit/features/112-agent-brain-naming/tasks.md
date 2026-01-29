# Tasks: Agent Brain Naming Unification

**Input**: Design documents from `.speckit/features/112-agent-brain-naming/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md
**Related Issues**: #90, #91, #92, #93, #94, #95

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)

## User Story Mapping

| Story | Title | Priority | GitHub Issue |
|-------|-------|----------|--------------|
| US1 | New User Installation | P1 | #90, #91 |
| US2 | Existing User Migration | P1 | #93, #94 |
| US3 | Documentation Consistency | P2 | #90, #91 |
| US4 | Claude Code Skill Discovery | P2 | #95 |

---

## Phase 1: Setup (Version Bump)

**Purpose**: Prepare packages for v1.2.0 release

- [ ] T001 [P] Update version to 1.2.0 in doc-serve-server/doc_serve_server/__init__.py
- [ ] T002 [P] Update version to 1.2.0 in doc-svr-ctl/doc_svr_ctl/__init__.py
- [ ] T003 [P] Update version to 1.2.0 in doc-serve-server/pyproject.toml
- [ ] T004 [P] Update version to 1.2.0 in doc-svr-ctl/pyproject.toml
- [ ] T005 [P] Update version to 1.2.0 in doc-serve-server/doc_serve_server/api/main.py (FastAPI app and root endpoint)
- [ ] T006 [P] Update version to 1.2.0 in doc-serve-server/doc_serve_server/models/health.py

---

## Phase 2: Foundational (Entry Points & Deprecation)

**Purpose**: Add new CLI entry points with backward compatibility

**⚠️ CRITICAL**: These changes enable both old and new commands to work

- [ ] T007 Add `agent-brain-serve` entry point to doc-serve-server/pyproject.toml [tool.poetry.scripts]
- [ ] T008 Add `agent-brain` entry point to doc-svr-ctl/pyproject.toml [tool.poetry.scripts]
- [ ] T009 Add deprecation warning function to doc-svr-ctl/doc_svr_ctl/cli.py for doc-svr-ctl command
- [ ] T010 Add deprecation warning function to doc-serve-server/doc_serve_server/api/main.py for doc-serve command
- [ ] T011 Run `poetry install` in doc-serve-server/ to register new entry points
- [ ] T012 Run `poetry install` in doc-svr-ctl/ to register new entry points
- [ ] T013 Run `task before-push` to verify all tests pass with new entry points

**Checkpoint**: Both old and new commands should now work. Verify with:
- `agent-brain --help` (new)
- `doc-svr-ctl --help` (deprecated, shows warning)
- `agent-brain-serve --help` (new)
- `doc-serve --help` (deprecated, shows warning)

---

## Phase 3: User Story 1 - New User Installation (Priority: P1) 🎯 MVP

**Goal**: New users see consistent agent-brain naming in PyPI and GitHub

**Independent Test**: Fresh pip install and command verification

### Implementation for User Story 1

- [ ] T014 [P] [US1] Update PyPI description in doc-serve-server/pyproject.toml to emphasize agent-brain branding
- [ ] T015 [P] [US1] Update PyPI description in doc-svr-ctl/pyproject.toml to emphasize agent-brain branding
- [ ] T016 [P] [US1] Update keywords in doc-serve-server/pyproject.toml to include agent-brain terms
- [ ] T017 [P] [US1] Update keywords in doc-svr-ctl/pyproject.toml to include agent-brain terms
- [ ] T018 [US1] Update doc-serve-server/README.md with new primary command names
- [ ] T019 [US1] Update doc-svr-ctl/README.md with new primary command names

**Checkpoint**: User Story 1 complete - new users see consistent branding on PyPI

---

## Phase 4: User Story 2 - Existing User Migration (Priority: P1)

**Goal**: Existing users can upgrade smoothly with clear migration path

**Independent Test**: Upgrade existing installation, verify both old and new commands work

### Implementation for User Story 2

- [ ] T020 [US2] Create docs/MIGRATION.md with v1.1→v1.2 migration steps
- [ ] T021 [US2] Update deprecation messages to reference docs/MIGRATION.md
- [ ] T022 [P] [US2] Update doc-serve-server/tests/test_server_install.py for new version
- [ ] T023 [P] [US2] Update doc-svr-ctl/tests/test_cli_install.py for new version
- [ ] T024 [P] [US2] Add test for agent-brain command entry point in doc-svr-ctl/tests/test_cli.py
- [ ] T025 [P] [US2] Add test for agent-brain-serve command entry point in doc-serve-server/tests/test_cli.py (if exists)

**Checkpoint**: User Story 2 complete - existing users can upgrade with deprecation warnings

---

## Phase 5: User Story 3 - Documentation Consistency (Priority: P2)

**Goal**: All documentation uses consistent agent-brain naming

**Independent Test**: Grep all docs for old names, verify zero matches (except deprecation references)

### Implementation for User Story 3

- [ ] T026 [P] [US3] Update README.md (root) with agent-brain naming and installation commands
- [ ] T027 [P] [US3] Update CLAUDE.md (root) with agent-brain command references
- [ ] T028 [P] [US3] Update .claude/CLAUDE.md with agent-brain command references
- [ ] T029 [P] [US3] Update doc-serve-skill/doc-serve/SKILL.md command examples to use agent-brain
- [ ] T030 [P] [US3] Update doc-serve-skill/doc-serve/references/troubleshooting-guide.md with new commands
- [ ] T031 [P] [US3] Update doc-serve-skill/doc-serve/references/integration-guide.md with new commands
- [ ] T032 [P] [US3] Update doc-serve-skill/doc-serve/references/api_reference.md with new commands
- [ ] T033 [P] [US3] Update doc-serve-skill/doc-serve/references/bm25-search-guide.md with new commands
- [ ] T034 [P] [US3] Update doc-serve-skill/doc-serve/references/vector-search-guide.md with new commands
- [ ] T035 [P] [US3] Update doc-serve-skill/doc-serve/references/hybrid-search-guide.md with new commands
- [ ] T036 [P] [US3] Update doc-serve-skill/doc-serve/references/server-discovery.md with new commands
- [ ] T037 [US3] Run grep to verify no doc-svr-ctl or doc-serve references remain (except deprecation notes)

**Checkpoint**: User Story 3 complete - all documentation uses agent-brain naming

---

## Phase 6: User Story 4 - Claude Code Skill Discovery (Priority: P2)

**Goal**: Skill renamed to using-agent-brain with updated triggers

**Independent Test**: Install skill in Claude Code, verify it activates on agent-brain triggers

### Implementation for User Story 4

- [ ] T038 [US4] Rename directory doc-serve-skill/doc-serve/ to doc-serve-skill/using-agent-brain/
- [ ] T039 [US4] Update name field in doc-serve-skill/using-agent-brain/SKILL.md frontmatter to `using-agent-brain`
- [ ] T040 [US4] Update description in SKILL.md to reference agent-brain commands
- [ ] T041 [US4] Update trigger keywords in SKILL.md to include "agent-brain" terms
- [ ] T042 [US4] Update all internal file references in SKILL.md (references/ paths remain valid)
- [ ] T043 [US4] Verify skill loads correctly with new name

**Checkpoint**: User Story 4 complete - skill discoverable as using-agent-brain

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and release preparation

- [ ] T044 Run `task before-push` to verify all tests pass
- [ ] T045 Run grep audit for any remaining old naming inconsistencies
- [ ] T046 Update .speckit/features/112-agent-brain-naming/quickstart.md if any steps changed
- [ ] T047 Close GitHub issues #90, #91, #93, #94, #95 with implementation notes
- [ ] T048 Build packages with `poetry build` in both package directories
- [ ] T049 Test local installation from wheels to verify entry points
- [ ] T050 Create git commit with conventional message: `feat(naming): unify branding to agent-brain (v1.2.0)`
- [ ] T051 Create git tag v1.2.0
- [ ] T052 Publish to PyPI: `poetry publish` in doc-serve-server/ and doc-svr-ctl/

### Repository Rename (Manual - After PyPI Publish)

- [ ] T053 [MANUAL] Rename GitHub repository from doc-serve-skill to agent-brain via Settings
- [ ] T054 Update all repository URLs in pyproject.toml files after rename
- [ ] T055 Update README badges to use new repository URL
- [ ] T056 Close GitHub issue #92 (repository rename)
- [ ] T057 Update GitHub release notes with final URLs

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) ────────────────────────────────────────────────┐
                                                                 │
Phase 2 (Foundational) ─────────────────────────────────────────┤
                                                                 │
    ┌───────────────┬───────────────┬───────────────┐           │
    │               │               │               │           │
Phase 3 (US1)   Phase 4 (US2)   Phase 5 (US3)   Phase 6 (US4)  │
    │               │               │               │           │
    └───────────────┴───────────────┴───────────────┘           │
                         │                                       │
                         ▼                                       │
                  Phase 7 (Polish) ◄─────────────────────────────┘
```

### User Story Dependencies

- **US1 (New User Installation)**: Depends on Phase 2 - No dependencies on other stories
- **US2 (Existing User Migration)**: Depends on Phase 2 - Can run parallel with US1
- **US3 (Documentation Consistency)**: Depends on Phase 2 - Can run parallel with US1/US2
- **US4 (Skill Discovery)**: Depends on Phase 2 - Can run parallel with US1/US2/US3

### Parallel Opportunities

**Phase 1**: All version bump tasks (T001-T006) can run in parallel
**Phase 2**: Entry point additions can be parallel, but poetry install must be sequential
**Phase 3-6**: All user stories can run in parallel after Phase 2 completes
**Within stories**: Tasks marked [P] can run in parallel

---

## Parallel Example: Documentation Updates (US3)

```bash
# Launch all documentation updates together:
Task: "Update README.md (root)"
Task: "Update CLAUDE.md (root)"
Task: "Update .claude/CLAUDE.md"
Task: "Update SKILL.md command examples"
Task: "Update troubleshooting-guide.md"
Task: "Update integration-guide.md"
# ... all [P] [US3] tasks
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1: Setup (version bump)
2. Complete Phase 2: Foundational (entry points)
3. Complete Phase 3: User Story 1 (PyPI branding)
4. Complete Phase 4: User Story 2 (migration path)
5. **STOP and VALIDATE**: Test with `pip install --upgrade`
6. Can release v1.2.0-rc1 at this point

### Full Release

1. Complete all phases through Phase 6
2. Run Phase 7 validation
3. Publish v1.2.0 to PyPI
4. Manual repository rename (T053)
5. Final URL updates (T054-T057)

---

## Notes

- Tests are NOT included as separate phase (no TDD requested)
- Existing tests updated in-place during user story phases
- Repository rename (T053) is manual and should be done AFTER PyPI publish
- All tasks have explicit file paths for LLM execution
- Version tests must be updated to expect 1.2.0
