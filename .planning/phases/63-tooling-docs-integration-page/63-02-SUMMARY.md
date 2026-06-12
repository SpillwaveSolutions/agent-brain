---
phase: 63-tooling-docs-integration-page
plan: 02
subsystem: infra
tags: [github-actions, ci, framework-matrix, advisory, workflow-dispatch, cron]

# Dependency graph
requires:
  - phase: 63-01
    provides: "task mcp:framework-matrix gated runner (FRAMEWORK_MATRIX=1 opt-in, bootstrap_venv.sh self-bootstrapping, bare-name include idiom)"
provides:
  - ".github/workflows/framework-matrix.yml — nightly advisory CI running task mcp:framework-matrix against main on cron 07:00 UTC + workflow_dispatch"
  - "framework-matrix (advisory) commit status posted to main after each run"
  - "Non-blocking advisory guarantee: schedule+dispatch triggers only, continue-on-error on matrix step"
affects: [phase-63-03, release-process]

# Tech tracking
tech-stack:
  added:
    - "GitHub Actions (schedule cron + workflow_dispatch triggers)"
    - "actions/setup-node@v4 + corepack enable pnpm (TS matrix leg)"
    - "astral-sh/setup-uv@v3 (uv toolchain for local package install)"
    - "actions/github-script@v7 (advisory commit status posting)"
  patterns:
    - "Advisory-only CI: schedule+dispatch triggers with no push/pull_request = structurally impossible to mark as required PR check"
    - "continue-on-error: true on the matrix step = framework drift never fails the workflow"
    - "commit status with context 'framework-matrix (advisory)' = visible on main without gating merges"

key-files:
  created:
    - ".github/workflows/framework-matrix.yml"
  modified: []

key-decisions:
  - "Trigger ONLY schedule (cron '0 7 * * *') + workflow_dispatch — no push/pull_request; structurally non-PR-blocking"
  - "continue-on-error: true on matrix step — framework SDK drift is expected, must not fail the workflow"
  - "Advisory commit status via actions/github-script@v7 posts 'framework-matrix (advisory)' context (success/failure derived from steps.matrix.outcome)"
  - "Local agent-brain packages installed at job level (server+uds+mcp+cli) so framework fixture's prerequisite check passes and tests actually run rather than all silently skipping"
  - "environment: ci-testing for secret access (OPENAI_API_KEY/ANTHROPIC_API_KEY) — matches e2e-nightly.yml precedent"
  - "checkout ref: main for scheduled runs — keeps both schedule + dispatch on main"
  - "90-minute timeout — 7 frameworks sequential with self-bootstrapping is slow"

patterns-established:
  - "Advisory CI pattern: omit push/pull_request from on: block to guarantee workflow cannot be required PR check"
  - "Nightly advisory workflow mirrors e2e-nightly.yml conventions (schedule+dispatch, ci-testing env, advisory rationale comment)"

requirements-completed: [TOOLING-V3-02]

# Metrics
duration: 10min
completed: 2026-06-12
---

# Phase 63 Plan 02: Nightly Advisory Framework-Matrix CI Workflow Summary

**Nightly advisory GitHub Actions workflow runs `task mcp:framework-matrix` against main on cron 07:00 UTC + workflow_dispatch, posts `framework-matrix (advisory)` commit status, and is structurally guaranteed never to block any PR (no push/pull_request triggers, continue-on-error matrix step).**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-06-12T16:30:00Z
- **Completed:** 2026-06-12T16:40:00Z
- **Tasks:** 2 (Task 1 authored workflow; Task 2 human-verify checkpoint — approved by orchestrator)
- **Files modified:** 1

## Accomplishments

- Authored `.github/workflows/framework-matrix.yml` with the two required triggers (schedule cron + workflow_dispatch) and NO push/pull_request triggers — making it structurally impossible to set as a required PR check
- Wired `continue-on-error: true` on the matrix step so framework SDK drift never fails the workflow
- Installed all required toolchains (Python+Poetry, Task, Node+pnpm via corepack, uv) plus the local agent-brain packages at the job level so framework tests actually run rather than silently skipping
- Advisory commit status posted via `actions/github-script@v7` with context `framework-matrix (advisory)` — visible on main commits without gating merges
- Human-verify checkpoint confirmed: YAML parse shows triggers are exactly `{'schedule': [{'cron': '0 7 * * *'}], 'workflow_dispatch': None}`, no push/pull_request triggers; main branch has no required status checks; `continue-on-error: true` wired; advisory context string present

## Task Commits

1. **Task 1: Author the nightly advisory framework-matrix workflow** - `6c8df23` (feat)
2. **Task 2: Verify advisory + non-blocking** — human-verify checkpoint; no code change; approved by orchestrator

**Plan metadata:** (this commit — docs close-out)

## Files Created/Modified

- `.github/workflows/framework-matrix.yml` — Nightly advisory CI workflow; schedule cron 07:00 UTC + workflow_dispatch only; installs all toolchains + local agent-brain packages; runs `task mcp:framework-matrix` with FRAMEWORK_MATRIX=1 and continue-on-error; posts `framework-matrix (advisory)` commit status via actions/github-script@v7

## Decisions Made

- Advisory-only triggers (schedule + workflow_dispatch, no push/pull_request): a workflow that never fires on PR events cannot be added as a required status check — this is the structural guarantee, not just policy
- `continue-on-error: true` on the matrix step: framework SDK drift is expected; failure must never fail the workflow itself
- Local agent-brain packages installed at job level (not just in per-framework venvs from bootstrap_venv.sh): without this, the seeded-server fixture's prerequisite check fails to find `agent-brain-serve`/`agent-brain-mcp` on PATH and all 7 frameworks skip silently, posting a meaningless green advisory status
- Actions pinned to repo-standard versions (checkout@v4, setup-python@v5, install-poetry@v1, setup-task@v2, github-script@v7); setup-node@v4 and setup-uv@v3 resolved via context7 before authoring
- `environment: ci-testing` and `ref: main` on checkout — mirrors e2e-nightly.yml precedent; 90-minute timeout for sequential 7-framework self-bootstrapping

## Deviations from Plan

None — plan executed exactly as written. Task 1 authored the workflow per all acceptance criteria; Task 2 was a human-verify checkpoint approved by the orchestrator with full YAML parse verification.

## Issues Encountered

None. The human-verify checkpoint for Task 2 was resolved externally by the orchestrator:
- YAML triggers verified: `{'schedule': [{'cron': '0 7 * * *'}], 'workflow_dispatch': None}` — no push/pull_request
- `continue-on-error: true` on matrix step confirmed
- Advisory commit status context `framework-matrix (advisory)` confirmed present
- GitHub branch protection on main confirmed: zero required status checks (structurally cannot be a required check)
- Orchestrator response: "approved"

## User Setup Required

The `OPENAI_API_KEY` secret should be present in the `ci-testing` GitHub environment (already used by `e2e-nightly.yml` and `pr-qa-gate.yml`). If absent, framework tests skip gracefully rather than hard-failing — the workflow still completes and posts the advisory status. No additional setup is required.

## Next Phase Readiness

- TOOLING-V3-02 closed: nightly advisory CI is in place
- Phase 63 is now 2/3 plans complete (63-01 Taskfile target + 63-02 CI workflow done; 63-03 INTEGRATIONS.md docs already complete per prior agent)
- Phase 63 can be marked complete when the orchestrator reconciles 63-03-SUMMARY.md (already present on disk)

---
*Phase: 63-tooling-docs-integration-page*
*Completed: 2026-06-12*

## Self-Check: PASSED

- `.github/workflows/framework-matrix.yml` — FOUND (confirmed above)
- Commit `6c8df23` — FOUND in git log
- Task 2 checkpoint — APPROVED by orchestrator (no code commit needed for verify-only checkpoint)
