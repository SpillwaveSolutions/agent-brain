# Implementation Tasks: Taskfile Support

## Task Overview

| Phase | Task ID | Description | Status |
|-------|---------|-------------|--------|
| 1 | T001 | Verify task --list output | Complete |
| 1 | T002 | Verify task install | Complete |
| 1 | T003 | Verify task test | Complete |
| 1 | T004 | Verify namespace isolation | Complete |
| 1 | T005 | Verify before-push workflow | Complete |
| 2 | T006 | Check README for Task docs | Complete |
| 2 | T007 | Add installation instructions | N/A (already exists) |
| 2 | T008 | Document all tasks | N/A (already exists) |

---

## Phase 1: Verification

### T001: Verify task --list output
**Priority**: P0
**Dependencies**: None

**Description:**
Run `task --list` at project root and verify all expected tasks appear with descriptions.

**Expected Tasks:**
- Root: install, dev, run, build, test, clean, format, lint, typecheck, before-push, ci
- Server namespace: server:install, server:dev, server:test, server:build
- CLI namespace: cli:install, cli:test, cli:status, cli:query

**Acceptance Criteria:**
- [ ] All tasks have descriptions
- [ ] Namespace prefixes work correctly
- [ ] No YAML syntax errors

---

### T002: Verify task install
**Priority**: P0
**Dependencies**: T001

**Description:**
Run `task install` and verify Poetry installs dependencies for both packages.

**Commands:**
```bash
task install
```

**Acceptance Criteria:**
- [ ] Exit code is 0
- [ ] Server dependencies installed
- [ ] CLI dependencies installed

---

### T003: Verify task test
**Priority**: P0
**Dependencies**: T002

**Description:**
Run `task test` and verify all tests pass.

**Commands:**
```bash
task test
```

**Acceptance Criteria:**
- [ ] Exit code is 0
- [ ] Server tests pass
- [ ] CLI tests pass
- [ ] Test count matches expected

---

### T004: Verify namespace isolation
**Priority**: P1
**Dependencies**: T002

**Description:**
Verify that namespaced tasks run only in their respective subprojects.

**Commands:**
```bash
task server:test
task cli:test
```

**Acceptance Criteria:**
- [ ] `task server:test` runs only server tests
- [ ] `task cli:test` runs only CLI tests
- [ ] Working directory is correct for each

---

### T005: Verify before-push workflow
**Priority**: P1
**Dependencies**: T003

**Description:**
Run complete pre-push workflow and verify all checks pass.

**Commands:**
```bash
task before-push
```

**Acceptance Criteria:**
- [ ] Format check passes
- [ ] Lint check passes
- [ ] Type check passes
- [ ] All tests pass with coverage
- [ ] Clear success message at end

---

## Phase 2: Documentation

### T006: Check README for Task docs
**Priority**: P1
**Dependencies**: None

**Description:**
Verify README.md includes Task usage documentation.

**Check For:**
- Task installation instructions
- List of common commands
- Development workflow explanation

**Acceptance Criteria:**
- [ ] README mentions Task
- [ ] Common commands documented
- [ ] Links to taskfile.dev

---

### T007: Add installation instructions
**Priority**: P2
**Dependencies**: T006

**Description:**
If missing, add Task installation instructions to README.

**Content to Add:**
```markdown
## Prerequisites

### Task Runner
Install [Task](https://taskfile.dev) for running development commands:

```bash
# macOS
brew install go-task/tap/go-task

# Linux
sudo snap install task --classic
```
```

**Acceptance Criteria:**
- [ ] Installation for macOS documented
- [ ] Installation for Linux documented
- [ ] Link to official docs included

---

### T008: Document all tasks
**Priority**: P2
**Dependencies**: T001

**Description:**
Add comprehensive task documentation to README or docs.

**Content:**
- Table of all available tasks
- Usage examples
- Development workflow guide

**Acceptance Criteria:**
- [ ] All tasks listed with descriptions
- [ ] Common workflows explained
- [ ] Examples provided

---

## Completion Checklist

- [x] All Phase 1 tasks complete (verification)
- [x] All Phase 2 tasks complete (documentation)
- [x] Tests passing: `task test` (91 tests passed)
- [x] Pre-push workflow works: `task before-push`
- [x] README updated with Task docs
