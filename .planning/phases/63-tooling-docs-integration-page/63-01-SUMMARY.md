---
phase: 63-tooling-docs-integration-page
plan: 01
subsystem: tooling
tags: [taskfile, bash, framework-matrix, ci, opt-in, gated-runner]

# Dependency graph
requires:
  - phase: 61-python-framework-matrix
    provides: "5 Python framework smoke tests (openai-agents, langchain, llama-index, pydantic-ai, autogen) + bootstrap_venv.sh + conftest.py"
  - phase: 62-ts-framework-matrix
    provides: "2 TypeScript framework smoke tests (Mastra + Vercel AI SDK) under framework-matrix/ts/ via pnpm test"
provides:
  - "scripts/run_framework_matrix.sh — gated sequential self-bootstrap runner (POSIX bash, FRAMEWORK_MATRIX=1 / --force gate)"
  - "agent-brain-mcp/Taskfile.yml bare `framework-matrix:` task surfaced as `task mcp:framework-matrix` via includes: mcp: alias"
  - "Root Taskfile.yml documentation comment block for mcp:framework-matrix (no colliding task block)"
  - "TOOLING-V3-01 closed: turnkey opt-in target for all 7 framework smoke tests (5 Python + 2 TS)"
affects: [phase-63-02, nightly-ci, before-push]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bare task name in per-package Taskfile + root includes: namespace alias — avoids cyclic-include collision (Phase 60-03 precedent: mcp:stress:orphan-test)"
    - "Opt-in gate pattern: FRAMEWORK_MATRIX=1 env var OR --force CLI arg — no-op exit 0 on unset keeps slow tests out of before-push"
    - "{{.CLI_ARGS}} forwarding in Taskfile cmd — lets task mcp:framework-matrix -- --force pass --force to runner"

key-files:
  created:
    - scripts/run_framework_matrix.sh
  modified:
    - agent-brain-mcp/Taskfile.yml
    - Taskfile.yml

key-decisions:
  - "Bare task name `framework-matrix:` in per-package Taskfile (NOT `mcp:framework-matrix:`) — the root includes: mcp: alias prepends the namespace; using the prefixed name triggers cyclic-include collision (confirmed Phase 60-03 precedent)"
  - "No root-level task block for framework-matrix — root Taskfile gets comment-only documentation block (mirrors mcp:stress:orphan-test pattern at lines 224-234)"
  - "FRAMEWORK_MATRIX=1 / --force gate ensures the slow 7-framework matrix NEVER runs during task before-push or bare task invocations"
  - "task mcp:framework-matrix gate-unset path: prints opt-in message, exits 0 — clean no-op confirmed by human-verify checkpoint"
  - "Per-framework teardown before next framework to prevent dep-tree collisions and orphan subprocess accumulation (Phase 60 orphan-free contract)"

patterns-established:
  - "Opt-in slow-target pattern: gate on FRAMEWORK_MATRIX env var + --force arg; no-op exit 0 with descriptive message when unset"
  - "Bare task name + root comment block pattern for per-package Taskfile tasks (avoids cyclic-include collision)"

requirements-completed: [TOOLING-V3-01]

# Metrics
duration: 45min
completed: 2026-06-12
---

# Phase 63 Plan 01: Framework Matrix Taskfile Target Summary

**Gated `task mcp:framework-matrix` target + `scripts/run_framework_matrix.sh` runner landing all 7 framework smoke tests (5 Python + 2 TS) behind a FRAMEWORK_MATRIX=1/--force opt-in gate — never invoked by before-push**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-06-11T~22:00Z (prior agent Tasks 1-2) + continuation closeout 2026-06-12
- **Completed:** 2026-06-12
- **Tasks:** 3 (Tasks 1-2 implemented; Task 3 human-verify checkpoint approved)
- **Files modified:** 3

## Accomplishments

- Created `scripts/run_framework_matrix.sh` — POSIX bash, `set -euo pipefail`, gated sequential runner that bootstraps all 5 Python frameworks via `bootstrap_venv.sh`, runs each with its own venv pytest `-m framework`, then runs the TS leg via `pnpm install --frozen-lockfile && pnpm test`. Gate-unset path exits 0 with descriptive opt-in message.
- Added bare `framework-matrix:` task in `agent-brain-mcp/Taskfile.yml` (surfaced as `task mcp:framework-matrix` via the root `includes: mcp:` alias) with `{{.CLI_ARGS}}` forwarding for `--force` passthrough.
- Added documentation comment block in root `Taskfile.yml` (no colliding task block — mirrors the `mcp:stress:orphan-test` comment-block-only pattern at lines 224-234).
- Human-verify checkpoint APPROVED: gate-unset path confirmed clean no-op; `task before-push` confirmed zero framework-matrix references (1334 server tests, no matrix bootstrap, no pnpm test, no `-m framework` invocation).

## Task Commits

Each task was committed atomically:

1. **Task 1: Write scripts/run_framework_matrix.sh — gated sequential self-bootstrap runner** - `264a920` (feat)
2. **Task 2: Wire bare framework-matrix: task in agent-brain-mcp/Taskfile.yml + root doc comment** - `1a77e49` (feat)
3. **Task 3: Verify the gate never leaks into before-push** - (checkpoint:human-verify — no code commit; `3d82c3c` is the checkpoint state commit; approved by orchestrator)

**Plan metadata:** (this closeout commit — docs: complete framework-matrix task plan)

## Files Created/Modified

- `scripts/run_framework_matrix.sh` — Gated sequential self-bootstrap runner for all 7 framework smoke tests; FRAMEWORK_MATRIX=1/--force gate; exits 0 no-op when gate unset
- `agent-brain-mcp/Taskfile.yml` — Added bare `framework-matrix:` task with desc, no install dep, `{{.CLI_ARGS}}` forwarding via `git rev-parse --show-toplevel`
- `Taskfile.yml` — Added documentation comment block for `mcp:framework-matrix` (no colliding task block)

## Decisions Made

- Used bare task name `framework-matrix:` (not `mcp:framework-matrix:`) to avoid the cyclic-include collision that hit Phase 60-03 — the root `includes: mcp:` alias auto-prepends the namespace
- No `deps: [install]` on the framework-matrix task — the runner self-bootstraps per-framework venvs and the TS pnpm env; poetry install dep would slow the no-op gate path unnecessarily
- Root Taskfile gets a comment block only (no root task block) — mirrors the `mcp:stress:orphan-test` pattern established in Phase 60-03
- Gate is FRAMEWORK_MATRIX=1 env var OR `--force` CLI arg — `{{.CLI_ARGS}}` forwarding lets `task mcp:framework-matrix -- --force` work
- Per-framework teardown before starting the next framework prevents dep-tree collisions and orphan subprocess accumulation (inherits Phase 60 orphan-free contract)

## Deviations from Plan

None — plan executed exactly as written. The Phase 60-03 cyclic-include collision risk was pre-documented in the plan's interfaces section and avoided as specified.

## Issues Encountered

One orthogonal flaky e2e test (`test_agent_brain_serve_dual_bind_subprocess`) failed during the `task before-push` verification run but PASSES on isolated re-run and is outside Phase 63 scope. This is a pre-existing flaky test, not a regression introduced by this plan.

## User Setup Required

None — no external service configuration required. `task mcp:framework-matrix` is purely opt-in and requires no environment setup to use the no-op gate path (FRAMEWORK_MATRIX unset → exits 0 with message).

## Next Phase Readiness

- TOOLING-V3-01 closed: `task mcp:framework-matrix` is the operator-facing + nightly CI turnkey command
- Plan 63-02 (`framework-matrix.yml` nightly advisory CI workflow) can now reference `task mcp:framework-matrix` with `FRAMEWORK_MATRIX=1` — the target exists and is stable
- Phase 63-03 (INTEGRATIONS.md) is already complete (committed prior to this plan's closeout — commits `3b6a549`, `fbecb73`, `f9b58a0`)

## Self-Check: PASSED

- `scripts/run_framework_matrix.sh` exists: confirmed (commit 264a920)
- `agent-brain-mcp/Taskfile.yml` contains `framework-matrix:`: confirmed (commit 1a77e49)
- `Taskfile.yml` contains `mcp:framework-matrix` in comment block: confirmed (commit 1a77e49)
- Prior commits 264a920 and 1a77e49 present in git log: confirmed

---
*Phase: 63-tooling-docs-integration-page*
*Completed: 2026-06-12*
