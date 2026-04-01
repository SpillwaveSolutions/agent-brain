---
phase: 46-project-local-runtime-install-harness
plan: 02
subsystem: testing
tags: [e2e, runtime-parity, verification, opencode, shell]
requires:
  - phase: 46-project-local-runtime-install-harness
    provides: repo-owned runtime harness foundation
provides:
  - shared runtime install verification helper
  - structured runtime failure JSON and failure.log output
  - OpenCode mutation regression coverage
affects: [phase-47, phase-48, phase-49, e2e-cli]
tech-stack:
  added: [bash]
  patterns: [three-stage runtime verification, dual human-json failure reporting]
key-files:
  created: [e2e-cli/tests/test_opencode_scope_guard.sh]
  modified: [e2e-cli/lib/runtime_parity.sh, e2e-cli/README.md, e2e-cli/tests/test_runtime_project_plumbing.sh]
key-decisions:
  - "Runtime verification runs structure check, install JSON validation, then a dry JSON probe."
  - "Failures emit both logs/failure.log and structured JSON with remediation guidance."
patterns-established:
  - "Runtime parity helpers fail with explicit error_type values instead of plain stderr strings."
  - "OpenCode global-path mutation remains a dedicated regression case."
requirements-completed: [ISO-02, PARITY-01]
duration: 25min
completed: 2026-04-01
---

# Phase 46: Project-Local Runtime Install Harness Summary

**Runtime parity installs now fail through an explicit verification contract with machine-readable remediation and an OpenCode global-mutation guard.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-04-01T16:40:00Z
- **Completed:** 2026-04-01T17:06:07Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added shared runtime verification gates in `e2e-cli/lib/runtime_parity.sh`.
- Emitted failure payloads with `runtime`, `status`, `error_type`, `details`, `remediation`, and `workspace`, plus `logs/failure.log`.
- Added an OpenCode mutation guard regression and upgraded the plumbing regression to assert the new failure contract.

## Task Commits

1. **Task 1: Add shared install verification helpers with concrete runtime failure payloads** - `5921f69` (`feat(e2e): add runtime parity harness foundation`)
2. **Task 2: Add shell regression coverage and docs for explicit verification/failure behavior** - `5921f69` (`feat(e2e): add runtime parity harness foundation`)

## Files Created/Modified
- `e2e-cli/lib/runtime_parity.sh` - runtime verification, failure logging, JSON payloads, and OpenCode mutation handling
- `e2e-cli/tests/test_runtime_project_plumbing.sh` - validates verified installs plus forbidden-global-path failure payloads
- `e2e-cli/tests/test_opencode_scope_guard.sh` - covers `global_path_mutated` output and failure log creation
- `e2e-cli/README.md` - documents the verification order and dual log/JSON failure contract

## Decisions Made
- Treated malformed install JSON and failed dry probes as first-class runtime errors instead of generic shell failures.
- Kept the verification layer shell-native and deterministic so future runtime phases can reuse it directly in E2E tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Corrected failure helpers to return non-zero after emitting JSON**
- **Found during:** Task 1 (Add shared install verification helpers with concrete runtime failure payloads)
- **Issue:** The first implementation emitted structured failures but did not immediately return from all helper branches, allowing forbidden-target tests to pass unexpectedly.
- **Fix:** Added explicit `return 1` paths after each failure emission branch in `runtime_parity.sh`.
- **Files modified:** `e2e-cli/lib/runtime_parity.sh`
- **Verification:** `bash e2e-cli/tests/test_runtime_project_plumbing.sh`
- **Committed in:** `5921f69`

**2. [Rule 3 - Blocking] Updated workspace cleanup for runtime-specific project roots**
- **Found during:** Task 2 (Add shell regression coverage and docs for explicit verification/failure behavior)
- **Issue:** The original cleanup helper still removed only `<scenario>/project`, which left `<scenario>/<runtime>-runtime/project` behind.
- **Fix:** Expanded `workspace_clean` to remove runtime-specific `*-runtime/project` directories while preserving logs and cleanup helpers.
- **Files modified:** `e2e-cli/lib/harness.sh`
- **Verification:** `bash e2e-cli/tests/test_runtime_project_plumbing.sh`
- **Committed in:** `5921f69`

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both deviations were contract fixes surfaced by the new regression tests; they tightened the harness without changing the approved scope.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
Phase 46 now provides the isolation, verification, and failure-reporting contract required to start runtime-specific parity execution in Phase 47.

---
*Phase: 46-project-local-runtime-install-harness*
*Completed: 2026-04-01*
