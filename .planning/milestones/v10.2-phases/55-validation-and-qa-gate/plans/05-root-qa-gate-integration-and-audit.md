# Plan 05: Root QA gate integration + audit attestation (VAL-04 + DR-5 closure)

**Phase:** 55 — Validation, contract tests & QA gate integration
**Requirements covered:** VAL-04 (closes DR-5 from v1 design)
**Depends on:** Plans 01, 02, 03, 04 (all contract tests must be green before they join the root gate)
**Parallel-safe with:** none — final plan; all prior plans must merge first
**Status:** Not started

## Goal

Fold `agent-brain-mcp` and `agent-brain-uds` into the root `task before-push`
and `task pr-qa-gate` recipes, formally closing DR-5 from the v1 design
(`docs/plans/2026-05-28-mcp-uds-transport-design.md` §14 #5). Add per-package
`before-push` sub-tasks (currently missing — packages only expose `pr-qa-gate`,
`test:cov`, `format`, `lint`, `typecheck`) and wire them into the root recipe
after the existing format/lint/typecheck/test cycle but before the
"All checks passed" echo. Produce the Phase 55 `VALIDATION.md` audit document
that the v10.2 milestone exit gate (`gsd-complete-milestone`) reads.

## Acceptance Criteria

- [ ] `agent-brain-mcp/Taskfile.yml` defines a new `before-push` task that runs `format:check`, `lint`, `typecheck`, `test:cov` in order. Mirrors the root recipe shape for consistency.
- [ ] `agent-brain-uds/Taskfile.yml` defines a new `before-push` task with the same shape.
- [ ] Root `Taskfile.yml::before-push` (lines 196-214 per CONTEXT.md) is extended to invoke `task: uds:before-push` and `task: mcp:before-push` between the existing `task: test:cov` step and the final `echo "--- All checks passed ---"`. The lock guard (`./scripts/before_push_lock_guard.sh start` + deferred `check`) MUST still wrap the full body so MCP/UDS `poetry install` drift is auto-detected.
- [ ] Root `Taskfile.yml::pr-qa-gate` is extended to invoke `task: uds:pr-qa-gate` and `task: mcp:pr-qa-gate` between the existing `task: cli:pr-qa-gate` and the final `echo "--- PR QA Gate Passed ---"`.
- [ ] Root `task before-push` exits 0 on a clean working tree with the v10.2 surface (Plans 01–04 merged). Per CONTEXT.md `<specifics>`, this adds ~60-90s to local pre-push.
- [ ] Root `task pr-qa-gate` exits 0 with the same surface.
- [ ] `task check:layering` still exits 0 with the v10.2 surface (HTTP transport may have pulled new deps; D-13 requires re-running this).
- [ ] `.planning/phases/55-validation-and-qa-gate/VALIDATION.md` exists and attests:
  - VAL-01: link to Plan 02 PR + green CI run.
  - VAL-02: link to Plan 03 PR + green CI run + follow-up issue link if filed.
  - VAL-03: link to Plan 04 PR + green CI run.
  - VAL-04: link to this plan's PR + paste of `task before-push` exit code 0 from a CI run.
  - DR-5 closure: cite `docs/plans/2026-05-28-mcp-uds-transport-design.md` §14 #5 and note "Resolved in v10.2 Phase 55, PR #<num>".
  - Coverage delta: `--cov-fail-under=80` holds for both `agent-brain-mcp` and `agent-brain-uds`; root `test:cov` aggregate is recorded.
- [ ] v2 design doc (`docs/plans/2026-06-XX-mcp-v2-subscriptions.md`, filed in Phase 50 per VAL-05) §5 "Test strategy" is verified to reflect the two-layer architecture decided in CONTEXT.md D-01. If it drifted during Phases 51–54, file a one-line update PR against Phase 50's design doc.
- [ ] CHANGELOG entry for v10.2 mentions:
  - 16-tool MCP surface complete (closes #186).
  - Streamable HTTP transport (loopback-only).
  - Resource subscriptions on `job://`, `corpus://status`, `corpus://folders`.
  - DR-5 resolved — MCP/UDS now in root `task before-push`.
  - Local pre-push time +60-90s (set expectations).

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-mcp/Taskfile.yml` | modify | Add `before-push` task (format:check → lint → typecheck → test:cov) |
| `agent-brain-uds/Taskfile.yml` | modify | Add `before-push` task (same shape) |
| `Taskfile.yml` (root) | modify | Insert `task: uds:before-push` + `task: mcp:before-push` into `before-push` recipe; insert `task: uds:pr-qa-gate` + `task: mcp:pr-qa-gate` into `pr-qa-gate` recipe; remove the per-package banner comments about "NOT wired into root before-push" from the MCP/UDS Taskfile headers (those are now stale) |
| `.planning/phases/55-validation-and-qa-gate/VALIDATION.md` | create | Audit attestation document; checks off VAL-01..04, cites DR-5 closure, captures CI exit codes + coverage deltas |
| `docs/CHANGELOG.md` | modify | Add v10.2 entry referencing all 4 VAL requirements + DR-5 closure |
| `docs/plans/2026-06-XX-mcp-v2-subscriptions.md` | modify (conditional) | Update §5 "Test strategy" only if it drifted from CONTEXT.md D-01 during implementation; if it still matches, leave it |

## Implementation Steps

1. Add `before-push` task to `agent-brain-mcp/Taskfile.yml`:
   ```yaml
   before-push:
     desc: Per-package pre-push check (format, lint, typecheck, test with coverage)
     deps: [install]
     cmds:
       - task: format:check
       - task: lint
       - task: typecheck
       - task: test:cov
   ```
2. Add the analogous `before-push` task to `agent-brain-uds/Taskfile.yml`.
3. Edit root `Taskfile.yml::before-push` (after `task: test:cov`, before the `echo "--- All checks passed ---"`):
   ```yaml
   - echo "--- Running tests with coverage ---"
   - task: test:cov
   - echo "--- Running MCP package pre-push ---"
   - task: uds:before-push
   - task: mcp:before-push
   - echo "--- All checks passed - Ready to push ---"
   ```
4. Edit root `Taskfile.yml::pr-qa-gate` (after `task: cli:pr-qa-gate`):
   ```yaml
   - task: server:pr-qa-gate
   - task: cli:pr-qa-gate
   - task: uds:pr-qa-gate
   - task: mcp:pr-qa-gate
   - echo "--- PR QA Gate Passed ---"
   ```
5. Remove the now-stale comments from `agent-brain-mcp/Taskfile.yml` and `agent-brain-uds/Taskfile.yml` headers — the lines `# Per-package, opt-in tasks. NOT wired into root before-push / pr-qa-gate in v1` no longer hold. Replace with `# Per-package tasks; wired into root before-push and pr-qa-gate as of v10.2 (Phase 55, closes DR-5).`
6. Run `task check:layering` to confirm the v2 surface (esp. HTTP transport's new deps) doesn't break the existing `mcp must never call server internals` contract per D-13.
7. Run `task before-push` from repo root; confirm exit 0 and capture the wall-clock time (informs CHANGELOG entry).
8. Run `task pr-qa-gate` from repo root; confirm exit 0.
9. Verify the v2 design doc (filed in Phase 50) §5 reflects the two-layer test architecture. If not, prepare a one-line update PR against `docs/plans/2026-06-XX-mcp-v2-subscriptions.md`.
10. Re-check the design doc's risk register cites #179 (API auth) and #178 (Kuzu SIGSEGV) per CONTEXT.md `<specifics>` carry-forward; update if the issue states moved since Phase 50.
11. Write `.planning/phases/55-validation-and-qa-gate/VALIDATION.md`:
    ```markdown
    # Phase 55 Validation — v10.2 MCP v2 milestone exit gate

    **Phase:** 55 — Validation, contract tests & QA gate integration
    **Milestone:** v10.2 — MCP v2 (Subscriptions, HTTP Transport, & Tool Completion)
    **Date:** YYYY-MM-DD
    **Sign-off attestation for `gsd-complete-milestone`.**

    ## Requirements coverage

    | REQ | Status | PR | CI run | Notes |
    |-----|--------|----|----|-------|
    | VAL-01 | ✅ | #<num> | <ci-url> | 16-tool parameterized contract suite (Layer 1 + Layer 2) |
    | VAL-02 | ✅ | #<num> | <ci-url> | Subscription lifecycle + disconnect cleanup E2E |
    | VAL-03 | ✅ | #<num> | <ci-url> | Streamable HTTP transport SDK test |
    | VAL-04 | ✅ | #<num> | <ci-url> | MCP/UDS folded into root `task before-push` + `task pr-qa-gate` |

    ## DR-5 closure

    Resolved in v10.2 Phase 55 (PR #<num>).
    Source citation: `docs/plans/2026-05-28-mcp-uds-transport-design.md` §14 #5.

    ## QA gate attestation

    - Root `task before-push` exit code: 0
    - Root `task pr-qa-gate` exit code: 0
    - `task check:layering` exit code: 0
    - `agent-brain-mcp` coverage: <pct>% (≥80% floor)
    - `agent-brain-uds` coverage: <pct>% (≥80% floor)
    - CI workflow run: <url>

    ## Follow-ups filed

    - <issue-num>: (only if Plan 03 filed the `/mcp/subscriptions` debug endpoint follow-up)
    - <issue-num>: (any other surfaced gaps per D-19)

    ## Pre-push wall-clock delta

    Local `task before-push`: +<seconds>s vs pre-Phase 55 baseline (~60-90s expected).
    ```
12. Add CHANGELOG entry under `[10.2.0]`:
    ```markdown
    ## [10.2.0] - YYYY-MM-DD

    ### Added
    - MCP v2 — 16 tools (was 7), Streamable HTTP transport (loopback-only), resource subscriptions (`job://`, `corpus://status`, `corpus://folders`), deferred URI schemes (`chunk://`, `graph-entity://`, `job://`, `file://`)
    - Parameterized contract tests against the official MCP SDK (stdio + HTTP)

    ### Changed
    - `agent-brain-mcp` and `agent-brain-uds` now run as part of root `task before-push` and `task pr-qa-gate` — adds ~60-90s to local pre-push time
    - Closes DR-5 from `docs/plans/2026-05-28-mcp-uds-transport-design.md` §14 #5
    ```
13. Run `task before-push` one final time before opening the PR; confirm exit 0 (this is the MANDATORY check from CLAUDE.md).

## Verification

- `task before-push` (from repo root) → exits 0; wall-clock matches expectation (~+60-90s vs prior).
- `task pr-qa-gate` → exits 0.
- `task check:layering` → exits 0 with the new HTTP transport deps in scope.
- `cd agent-brain-mcp && task before-push` → exits 0 standalone (sanity check the new sub-task).
- `cd agent-brain-uds && task before-push` → exits 0 standalone.
- `.planning/phases/55-validation-and-qa-gate/VALIDATION.md` exists, all 4 VAL rows show ✅ with PR + CI links populated.
- `docs/CHANGELOG.md` has `[10.2.0]` entry mentioning DR-5 closure.
- CI run on the PR includes MCP and UDS test output (verify by inspecting one workflow run per D-15).
- Manual: `git grep "NOT wired into root before-push" -- 'agent-brain-*/Taskfile.yml'` returns nothing — stale comments removed.

## Risk Notes

- **`poetry install` drift in root before-push**: per CONTEXT.md `<specifics>` and `before_push_lock_guard.sh`, the lock guard wraps the whole recipe and reverts in-tree `poetry.lock` drift from transitive `poetry install` calls. The new MCP/UDS sub-tasks invoke `poetry install` via `deps: [install]` — confirm the guard catches and reverts any unintended drift on a clean working tree.
- **Layering regression with HTTP transport deps**: Phase 53 may have pulled `uvicorn` (or similar) into `agent-brain-mcp`. The `mcp must never call server internals` import-linter contract is still inviolate — but the new dep is fine. Run `task check:layering` to confirm. If it breaks, the bug is in Phase 53's deps, not this plan; file a Phase 53 fix per D-19 ("do not patch in Phase 55").
- **+60-90s local pre-push cost**: developers must be warned via CHANGELOG and v2 design doc §5. If CI duration becomes painful (>15min), consider gating the contract suite behind `task ci-only` separately — but that's a v10.3 concern, not Phase 55.
- **Missing `before-push` sub-task**: per analysis of `agent-brain-mcp/Taskfile.yml` and `agent-brain-uds/Taskfile.yml`, neither package currently defines a `before-push` task. CONTEXT.md D-12 assumes both exist. This plan creates them; if Phase 50–54 added them already, this step is a no-op — verify before editing.
- **VAL-05 verification**: Phase 50 owns the v2 design doc. This plan verifies the doc exists and §5 reflects D-01 — if the doc is missing or §5 disagrees with D-01, do NOT add the test-strategy section in Phase 55; file a Phase 50 follow-up per D-19.
- **CI matrix workflow path**: per D-15 no new workflow YAML is added — existing CI runs `task before-push` and picks up MCP/UDS automatically. Verify by clicking through one CI run; if the workflow shells `task: server` and `task: cli` explicitly (instead of root `task before-push`), edit the workflow to call root `before-push` directly. Phase 55 audit must confirm CI includes MCP output.

---
*Plan 05 of Phase 55*
