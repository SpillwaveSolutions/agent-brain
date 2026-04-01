---
phase: 46-project-local-runtime-install-harness
plan: 01
subsystem: testing
tags: [e2e, runtime-parity, harness, shell, isolation]
requires:
  - phase: 46-project-local-runtime-install-harness
    provides: phase context and execution plans
provides:
  - repo-owned e2e harness workspace root under e2e_workdir
  - shared shell harness helpers for workspace and server lifecycle
  - report helpers for runtime parity runs
affects: [phase-46-02, phase-47, phase-48, phase-49, e2e-cli]
tech-stack:
  added: [bash]
  patterns: [repo-owned runtime workspaces, runtime-specific cleanup roots]
key-files:
  created: [e2e-cli/lib/harness.sh, e2e-cli/lib/report.sh]
  modified: [.gitignore, e2e-cli/run.sh, e2e-cli/README.md, e2e-cli/lib/runtime_parity.sh, e2e-cli/tests/test_runtime_project_plumbing.sh]
key-decisions:
  - "Runtime parity workspaces now live under repo-root e2e_workdir instead of e2e-cli/.runs."
  - "Success cleanup preserves scenario roots and deletes only disposable project trees."
patterns-established:
  - "Harness helpers own workspace creation, cleanup, assertions, and server lifecycle."
  - "Runtime parity tests use repo-owned scenario directories with runtime-specific subfolders."
requirements-completed: [ISO-01, ISO-02]
duration: 25min
completed: 2026-04-01
---

# Phase 46: Project-Local Runtime Install Harness Summary

**Repo-owned runtime parity workspaces now scaffold isolated scenario roots under `e2e_workdir/` with shared harness and reporting helpers.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-04-01T16:40:00Z
- **Completed:** 2026-04-01T17:06:07Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- Added `e2e-cli/lib/harness.sh` for logging, assertions, workspace lifecycle, and server lifecycle.
- Added `e2e-cli/lib/report.sh` so `run.sh` can emit markdown and JSON reports from the shared harness.
- Moved runtime parity docs and plumbing from `e2e-cli/.runs/` to repo-owned `e2e_workdir/` with runtime-specific subdirectories and cleanup roots.

## Task Commits

1. **Task 1: Restore the missing harness helper layer and redirect workspace roots to e2e_workdir** - `5921f69` (`feat(e2e): add runtime parity harness foundation`)
2. **Task 2: Align runtime workspace preparation and plumbing tests with e2e_workdir/<runtime>-runtime/cleanup** - `5921f69` (`feat(e2e): add runtime parity harness foundation`)

## Files Created/Modified
- `e2e-cli/lib/harness.sh` - workspace lifecycle, assertions, and server helpers used by `run.sh` and shell tests
- `e2e-cli/lib/report.sh` - report initialization/finalization for harness runs
- `e2e-cli/lib/runtime_parity.sh` - repo-owned runtime workspace helpers aligned to `e2e_workdir/`
- `e2e-cli/run.sh` - results root redirected to repo-owned `e2e_workdir/`
- `e2e-cli/tests/test_runtime_project_plumbing.sh` - regression coverage updated for runtime-specific workspace layout

## Decisions Made
- Centralized runtime workspaces at repo root so parity tests never depend on `e2e-cli`-local artifacts.
- Kept success cleanup narrow by deleting only disposable `project/` directories and leaving scenario logs/cleanup helpers intact.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed ignore-rule interference for new harness helpers**
- **Found during:** Task 1 (Restore the missing harness helper layer and redirect workspace roots to e2e_workdir)
- **Issue:** Root `.gitignore` had a broad `lib/` rule, which caused `e2e-cli/lib/harness.sh` and `e2e-cli/lib/report.sh` to remain untracked.
- **Fix:** Added explicit exceptions for `e2e-cli/lib/` shell helpers.
- **Files modified:** `.gitignore`
- **Verification:** `git status --short` showed the new files as trackable before commit.
- **Committed in:** `5921f69`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No scope creep. The deviation was required to make the planned harness helpers shippable.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
Wave 1 is complete and provides the runtime workspace, cleanup, and reporting foundation required by the verification contract in Plan 02.

---
*Phase: 46-project-local-runtime-install-harness*
*Completed: 2026-04-01*
