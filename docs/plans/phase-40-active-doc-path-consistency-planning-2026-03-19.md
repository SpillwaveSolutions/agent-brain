# Phase 40 Planning Run (2026-03-19)

## Objective

Create executable Phase 40 plans for the v9.2.0 audit gap-closure scope:

- Remove stale `.claude/agent-brain/` references from active setup and architecture docs.
- Ensure setup flow and architecture flow both describe the same `.agent-brain/`-based state model.
- Define verification evidence that closes CFGDOC-01, GUIDE-02, GUIDE-03, and GUIDE-05.

## Planned Outputs

1. `.planning/phases/40-active-doc-path-consistency-and-flow-closure/40-01-PLAN.md`
2. `.planning/phases/40-active-doc-path-consistency-and-flow-closure/40-02-PLAN.md`

## Approach

1. Use roadmap Phase 40 scope and success criteria as source of truth.
2. Split work into:
   - Plan 40-01: path normalization sweep in active docs.
   - Plan 40-02: reconcile setup vs architecture narrative and produce verification evidence.
3. Include explicit file lists, `read_first`, concrete actions, and grep-verifiable acceptance criteria.

## Notes

- Research is disabled by current `.planning/config.json` settings, so this planning run uses existing roadmap/requirements context.
- Plan checker iteration is simulated here by tightening acceptance criteria and requirements mapping in the generated plan files.
