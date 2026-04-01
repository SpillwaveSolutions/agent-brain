# Phase 46 Planning Snapshot

Date: 2026-04-01
Phase: 46
Name: Project-Local Runtime Install Harness

This planning snapshot records the executable split chosen for Phase 46 before execution begins.

## Outcome

Phase 46 is split into two executable plans:

1. `46-01-PLAN.md`
   Focus: repair the missing E2E harness helper layer, move runtime workspaces to repo-owned `e2e_workdir/`, and align runtime workspace preparation plus plumbing tests with the approved per-runtime layout.

2. `46-02-PLAN.md`
   Focus: add the shared install verification and runtime-specific failure-reporting layer, including explicit JSON/log outputs and OpenCode mutation guard coverage.

## Why this split

- The current E2E parity foundation is incomplete because `e2e-cli/run.sh` references `e2e-cli/lib/harness.sh` and `e2e-cli/lib/report.sh`, but those tracked files do not exist.
- Workspace isolation and plumbing must be fixed first so later verification helpers have a stable, repo-owned runtime workspace contract.
- Failure reporting and verification are a separate concern and fit naturally after the workspace layer is repaired.

## Requirements Mapping

- `46-01-PLAN.md` addresses `ISO-01` and `ISO-02`
- `46-02-PLAN.md` addresses `ISO-02` and `PARITY-01`

## Execution Order

- Wave 1: `46-01-PLAN.md`
- Wave 2: `46-02-PLAN.md`

## Primary Files

- `.planning/phases/46-project-local-runtime-install-harness/46-01-PLAN.md`
- `.planning/phases/46-project-local-runtime-install-harness/46-02-PLAN.md`
- `.planning/phases/46-project-local-runtime-install-harness/46-CONTEXT.md`

