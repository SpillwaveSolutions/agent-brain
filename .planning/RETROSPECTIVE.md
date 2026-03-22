# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v9.4.0 — Documentation Accuracy Audit and Reliability Closure

**Shipped:** 2026-03-20
**Phases:** 10 | **Plans:** 23 | **Sessions:** n/a

### What Was Built
- Closed the documentation accuracy program across phases 29-33 with follow-on gap closure through phases 36-40.
- Resolved active path-guidance drift by standardizing setup/architecture docs around `.agent-brain/`.
- Shipped server/provider reliability fixes plus setup wizard UX improvements needed to complete milestone acceptance.

### What Worked
- Wave-based execution with per-plan summaries kept implementation traceable and easy to verify.
- Gap-planning from audit output reduced rework by focusing directly on unsatisfied requirement IDs.

### What Was Inefficient
- Version naming drift (`v9.2.0` planning scope vs `v9.4.0` release intent) caused extra audit/reconciliation steps.
- Human-needed verification markers lingered in historical phase artifacts and required explicit debt acceptance.

### Patterns Established
- Use focused gap-closure phases tied to exact requirement IDs when audits surface cross-doc inconsistencies.

### Key Lessons
1. Keep milestone version metadata aligned across roadmap, requirements, and release intent before running audit/closure workflows.
2. Archive milestone artifacts immediately after closure to keep active planning docs small and current.

### Cost Observations
- Model mix: n/a
- Sessions: n/a
- Notable: Parallel plan execution remains the best throughput path; manual checkpoints are mainly needed for release/version naming decisions.

---

## Milestone: v9.3.0 — LangExtract + Config Spec

**Shipped:** 2026-03-22
**Phases:** 2 | **Plans:** 3

### What Was Built
- Reconciled the 12-step config wizard SPEC with the 1078-line command implementation, fixing title, pre-flight keys, GraphRAG options, and version stamp.
- Retroactively closed LangExtract document graph extractor (multi-provider, 47 tests passing) that was pre-implemented but untracked.

### What Worked
- Claude assumptions as CONTEXT.md (skipping discuss-phase) worked well for documentation-only phases where the spec already existed.
- Retroactive verification against existing code caught that Phase 35 was already complete — saved a full plan-execute cycle.

### What Was Inefficient
- Phase 35 should have been tracked when originally implemented. The retroactive closure was clean but represents process gap.
- Version ordering anomaly: v9.3.0 shipped after v9.4.0 because phases 34-35 were deferred during the v9.4.0 doc audit.

### Patterns Established
- Retroactive phase closure with verification is a valid pattern for pre-implemented work.
- SPEC.md files serve as both forward-looking contracts and retrospective documentation.

### Key Lessons
1. Track all implementation work through GSD phases at implementation time, not retroactively.
2. When a SPEC.md has all checkboxes checked, verify code existence before planning — the work may already be done.

### Cost Observations
- Model mix: opus (planning) + sonnet (execution, verification)
- Sessions: 1
- Notable: Entire 2-phase milestone completed in a single session including retroactive closure.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v9.4.0 | n/a | 10 | Audit-driven gap closure was formalized with dedicated closure phase planning |
| v9.3.0 | 1 | 2 | Retroactive phase closure validated as pattern; spec-as-contract formalized |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v9.4.0 | n/a | n/a | n/a |
| v9.3.0 | 47 (graph extractors) | n/a | 0 (doc-only milestone) |

### Top Lessons (Verified Across Milestones)

1. Requirement-ID traceability plus verification artifacts materially reduces ambiguity during milestone close-out.
2. Canonical-path consistency in docs must be continuously enforced to prevent setup/onboarding flow drift.
3. When SPECs have all checkboxes checked, verify code before planning — retroactive closure saves full execution cycles.
