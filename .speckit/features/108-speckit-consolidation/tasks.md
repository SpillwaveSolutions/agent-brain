# Tasks: Consolidate Spec Directories to .speckit/

**Input**: Design documents from `.speckit/features/108-speckit-consolidation/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md

**Tests**: Not requested. This is a file-move/refactoring feature with manual verification steps.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create feature branch and target directory structure

- [x] T001 Create feature branch `108-speckit-consolidation` from main
- [x] T002 Create target directories: `.speckit/features/`, `.speckit/templates/`, `.speckit/scripts/`, `.speckit/memory/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Move all files using `git mv` to preserve rename tracking. MUST complete before any path updates.

**CRITICAL**: No path update work can begin until all moves are complete.

- [x] T003 Use `git mv` to move all 13 directories from `specs/*` to `.speckit/features/`
- [x] T004 [P] Use `git mv` to move `.specify/templates/*` to `.speckit/templates/`
- [x] T005 [P] Use `git mv` to move `.specify/scripts/*` to `.speckit/scripts/`
- [x] T006 [P] Use `git mv` to move `.specify/memory/*` to `.speckit/memory/`
- [x] T007 Remove empty `.specify/` directory (after T004-T006 complete)
- [x] T008 Remove empty `specs/` directory (after T003 complete)

**Checkpoint**: All files now live under `.speckit/`. Old directories are gone. `git status` should show renames (R).

---

## Phase 3: User Story 1 - Developer Finds SDD Artifacts in One Place (Priority: P1) MVP

**Goal**: All SDD artifacts consolidated under `.speckit/` with no remnant directories

**Independent Test**: Run `ls .speckit/features/ .speckit/templates/ .speckit/scripts/bash/ .speckit/memory/` and verify all content is present. Confirm `.specify/` and `specs/` do not exist.

### Implementation for User Story 1

- [x] T009 [US1] Verify `.speckit/features/` contains all 13+ feature directories
- [x] T010 [US1] Verify `.speckit/templates/` contains 5 template files (agent-file-template.md, checklist-template.md, plan-template.md, spec-template.md, tasks-template.md)
- [x] T011 [US1] Verify `.speckit/scripts/bash/` contains 5 scripts (check-prerequisites.sh, common.sh, create-new-feature.sh, setup-plan.sh, update-agent-context.sh)
- [x] T012 [US1] Verify `.speckit/memory/constitution.md` exists
- [x] T013 [US1] Verify `.specify/` directory does not exist
- [x] T014 [US1] Verify `specs/` directory does not exist

**Checkpoint**: User Story 1 complete. All SDD artifacts in one place.

---

## Phase 4: User Story 2 - SDD Scripts Work After Migration (Priority: P1)

**Goal**: All bash scripts and command files reference `.speckit/` paths; SDD workflows function without errors

**Independent Test**: Run `bash .speckit/scripts/bash/check-prerequisites.sh --help` and verify no path errors. Run `grep -r '\.specify/' .speckit/scripts/ .claude/commands/` and confirm zero directory path matches.

### Implementation for User Story 2

- [x] T015 [P] [US2] Update path references in `.speckit/scripts/bash/common.sh`: replace `$repo_root/specs` with `$repo_root/.speckit/features` (2 occurrences) and `get_feature_dir()` function
- [x] T016 [P] [US2] Update path references in `.speckit/scripts/bash/create-new-feature.sh`: replace `.specify` marker with `.speckit`, `SPECS_DIR` path to `.speckit/features`, template path to `.speckit/templates/spec-template.md`
- [x] T017 [P] [US2] Update path reference in `.speckit/scripts/bash/setup-plan.sh`: replace `.specify/templates/plan-template.md` with `.speckit/templates/plan-template.md`
- [x] T018 [P] [US2] Update path reference in `.speckit/scripts/bash/update-agent-context.sh`: replace `.specify/templates/agent-file-template.md` with `.speckit/templates/agent-file-template.md`
- [x] T019 [US2] Replace all `.specify/` path references with `.speckit/` in 9 command files: `.claude/commands/speckit.analyze.md`, `speckit.checklist.md`, `speckit.clarify.md`, `speckit.constitution.md`, `speckit.implement.md`, `speckit.plan.md`, `speckit.specify.md`, `speckit.tasks.md`, `speckit.taskstoissues.md`
- [x] T020 [US2] Replace `specs/[0-9]+-<short-name>` with `.speckit/features/[0-9]+-<short-name>` in `.claude/commands/speckit.specify.md`
- [x] T021 [US2] Add reinforcement note after frontmatter in all 9 command files: `> **Spec directory**: All SDD artifacts live under .speckit/ (features, templates, scripts, memory).`
- [x] T022 [US2] Verify zero `.specify/` directory path references remain in `.speckit/scripts/bash/` (excluding `/speckit.specify` command name references)
- [x] T023 [US2] Verify zero `.specify/` directory path references remain in `.claude/commands/` (excluding `/speckit.specify` command name references)
- [x] T024 [US2] Verify zero bare `specs/` directory path references remain in `.speckit/scripts/bash/`

**Checkpoint**: User Story 2 complete. All SDD scripts and commands use `.speckit/` paths.

---

## Phase 5: User Story 3 - Claude Code Permissions Remain Valid (Priority: P2)

**Goal**: Claude Code settings reference updated script paths so permissions work

**Independent Test**: Inspect `.claude/settings.local.json` and verify all 4 script permission entries use `.speckit/scripts/bash/` paths.

### Implementation for User Story 3

- [x] T025 [US3] Update `.claude/settings.local.json`: replace 4 `.specify/scripts/bash/` permission paths with `.speckit/scripts/bash/` (check-prerequisites.sh, create-new-feature.sh, setup-plan.sh, update-agent-context.sh)
- [x] T026 [US3] Verify `.claude/settings.local.json` contains zero `.specify/` references

**Checkpoint**: User Story 3 complete. Claude Code permissions valid.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final verification and commit

- [x] T027 Run full verification suite: `ls` checks for all 4 `.speckit/` subdirectories, `grep` checks for zero stale references, confirm old directories removed
- [x] T028 Stage all changes with `git add` and verify `git status` shows renames (R prefix)
- [x] T029 Commit with message: `refactor: consolidate .specify/ and specs/ into .speckit/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup (T001-T002) - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational (Phase 2) - verification of moves
- **User Story 2 (Phase 4)**: Depends on Foundational (Phase 2) - can run in parallel with US1
- **User Story 3 (Phase 5)**: Depends on Foundational (Phase 2) - can run in parallel with US1/US2
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Depends only on Phase 2. Verification-only tasks.
- **User Story 2 (P1)**: Depends only on Phase 2. Script/command file edits — independent of US1.
- **User Story 3 (P2)**: Depends only on Phase 2. Settings file edit — independent of US1/US2.

### Within Each User Story

- US2: Bash script updates (T015-T018) can run in parallel, then command file updates (T019-T021) sequentially, then verification (T022-T024)
- US3: Single edit (T025) then verification (T026)

### Parallel Opportunities

- T004, T005, T006 can run in parallel (moving different source directories)
- T015, T016, T017, T018 can run in parallel (different bash script files)
- US1, US2, US3 can all start once Phase 2 is complete

---

## Implementation Strategy

### MVP First (User Story 1 + 2)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational moves (T003-T008)
3. Complete Phase 3: US1 verification (T009-T014)
4. Complete Phase 4: US2 path updates (T015-T024)
5. **STOP and VALIDATE**: Scripts work, no stale references
6. Deploy/merge if ready

### Full Delivery

1. Complete MVP above
2. Complete Phase 5: US3 settings update (T025-T026)
3. Complete Phase 6: Final verification and commit (T027-T029)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- US1 is verification-only (moves happen in Phase 2)
- US2 is the bulk of the editing work (14 files updated)
- US3 is a single file edit
- Commit after Phase 6 only (one atomic commit for the entire consolidation)
