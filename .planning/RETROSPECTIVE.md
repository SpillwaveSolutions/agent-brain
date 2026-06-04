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

## Milestone: v10.2 — MCP v2 (Subscriptions, HTTP Transport, & Tool Completion)

**Shipped:** 2026-06-03
**Phases:** 6 (50-55) | **Plans:** 24 | **Sessions:** ~7 (one per phase + initial roadmapping)

### What Was Built
- TOOL_REGISTRY at exactly 16 tools (7 v1 + 9 v2) locked by `_tool_matrix.py` SOT with import-time drift guard
- 3 subscribable URIs (`job://`, `corpus://status`, `corpus://folders`) with policy-defined cadences + disconnect cleanup
- Streamable HTTP transport (`--transport http`) via `StreamableHTTPSessionManager` + uvicorn (loopback-only, no auth yet)
- 4 URI schemes addressable via `resources/read` + `resources/templates/list` advertising RFC 6570 templates
- DR-5 closed: `agent-brain-mcp` and `agent-brain-uds` folded into root `task before-push` + `task pr-qa-gate`
- Two-layer contract test suite (in-process Layer 1 + SDK-driven Layer 2) sharing single SOT

### What Worked
- **Sequential waves for shared-file plans (post-Phase-51 lesson).** Phase 51's 3 parallel-commit races (concurrent `git commit` operations grabbing each other's staged files) taught us to schedule plans that share files SEQUENTIALLY, not in parallel. Every subsequent phase used this and shipped with zero merge mishaps.
- **CONTEXT.md as decision-locking artifact.** Phase 52 onward documented which approaches were chosen and why; downstream planners did not re-litigate (e.g., decision E in Phase 52 to use client-side polling for `corpus://folders`).
- **Adversarial verification at phase boundary.** `gsd-verifier` running goal-backward analysis caught issues like the BACKEND_CONFLICT vs INVALID_PARAMS mapping in Phase 54 before they shipped.
- **Single SOT for tool matrix (`_tool_matrix.py`).** Layer 1 and Layer 2 tests share the same case list with an import-time guard against drift — adding a tool to one layer without updating the other fails immediately at import.
- **Per-package `before-push` symmetry.** Adding `format:check → lint → typecheck → test:cov` to every package's Taskfile.yml made root integration trivial (just call `task <pkg>:before-push`).

### What Was Inefficient
- **`gsd-tools phase complete` plan counter quirk.** The tool's plan discovery only sees top-level `*-PLAN.md`, not `plans/*.md` subdirectories. Required manual STATE.md frontmatter correction after every phase complete (6 times across the milestone).
- **`gsd-tools milestone complete` CLI quirks resurfaced.** Same plan-counter bug + `--help` flag interpreted as positional version arg (creating garbage `--help-ROADMAP.md` archive files) + UTC date drift (2026-06-04 stamped on a 2026-06-03 ship). All required manual cleanup.
- **Phase 51 Wave 1 ignored `branching_strategy: none`.** Despite config, an executor created `gsd/phase-51-uri-schemes-templates` branch. Cost: one `git merge --ff-only` recovery; orchestrator had to add explicit no-branch instructions to subsequent executors.
- **MCP SDK 1.12.x API drift discovered at runtime, not design time.** `subscribe=False` hardcoded (Phase 52), `StreamableHTTPSessionManager` doesn't auto-enable `transport_security` (Phase 53), uvicorn 0.32.x SystemExit pattern (Phase 53). Each required a workaround patch. Future MCP work should run a smoke test against the SDK version BEFORE planning.

### Patterns Established
- **Layer 1 + Layer 2 contract test architecture.** Layer 1 (in-process `fake_httpx_client`) for speed; Layer 2 (SDK subprocess) for protocol fidelity. Share SOT with import-time drift guard.
- **`emits_progress: bool` field on `ToolSpec`** + async dispatch branch in `server.call_tool` for progress-emitting tools. Default `False`; only `wait_for_job` opts in.
- **`(id(session), uri)` keyed subscription registry** with cleanup via `run_stdio` try/finally + `_poll_loop` explicit `except asyncio.CancelledError` clause.
- **Pydantic `Literal[True]` confirm guards** for destructive tools (`remove_folder`, `clear_cache`). Type system enforces the safety check; no runtime branch needed.
- **Pre-flight `socket.bind` probe before uvicorn handoff** — generalized pattern for catching port-in-use errors before any framework swallows them as SystemExit.
- **Synchronous-first cleanup in async resource managers.** When teardown must happen on cancellation, do it synchronously in the caller path — never rely on `try/finally` inside a coroutine body that may never run.

### Key Lessons
1. **Schedule wave parallelism by file-collision analysis, not plan independence.** Two plans that look independent but commit to the same file will race at the `git commit` step. Parallel-safe means file-disjoint, not topic-disjoint.
2. **Run a smoke test against pinned SDK versions before planning a phase that depends on them.** Phase 52/53 hit MCP SDK and uvicorn API surprises that would have cost less if discovered at scoping time. Add a "SDK pinning probe" step to research-phase.
3. **DR-5 closure value is asymmetric: the cost is local pre-push time; the benefit is catching silent regressions.** The `agent-brain-uds` smoke test had been broken since v10.1.0 and was caught on the first DR-5-gated run. That alone justifies the +60-90s cost.
4. **CLI tools that swallow flags as positional args (`--help` → version) need a hardening pass.** Cost us a corrupted MILESTONES.md mid-flight. Fix: argparse with `--help` handled before positional dispatch.
5. **A `_tool_matrix.py`-style single SOT with import-time validation is the lightest-weight defense against silent drift between test layers.** Trade: 50 lines of plumbing; benefit: drift is impossible without an import error.

### Cost Observations
- Model mix: opus (orchestration + plan-check + verifier) + sonnet (executors). No haiku used.
- Sessions: ~7 across 8 days (2026-05-26 → 2026-06-03)
- Notable: 6/6 phases shipped on first pass — zero failed verifier runs across the milestone. ~530 new tests added; 1685+ monorepo tests passing at HEAD.
- Quality gate runtime: `task before-push` 162s (DR-5 closure attestation), `task pr-qa-gate` 152s, layering contracts 3/3 (164 files, 414 deps).

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v10.2 | ~7 | 6 | Wave parallelism scheduled by file-collision analysis (not topic), not plan independence; `_tool_matrix.py` SOT pattern with import-time drift guard validated |
| v9.4.0 | n/a | 10 | Audit-driven gap closure was formalized with dedicated closure phase planning |
| v9.3.0 | 1 | 2 | Retroactive phase closure validated as pattern; spec-as-contract formalized |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v10.2 | ~530 new (1685+ total) | agent-brain-mcp 91.83% / agent-brain-uds 99% | 0 (uses existing MCP SDK 1.12.x) |
| v9.4.0 | n/a | n/a | n/a |
| v9.3.0 | 47 (graph extractors) | n/a | 0 (doc-only milestone) |

### Top Lessons (Verified Across Milestones)

1. Requirement-ID traceability plus verification artifacts materially reduces ambiguity during milestone close-out.
2. Canonical-path consistency in docs must be continuously enforced to prevent setup/onboarding flow drift.
3. When SPECs have all checkboxes checked, verify code before planning — retroactive closure saves full execution cycles.
4. Schedule wave parallelism by file-collision analysis, not plan independence — plans that look independent but commit to the same file will race at the `git commit` step.
5. Run a pinned-SDK smoke test before planning a phase that depends on that SDK — runtime API drift is more expensive than design-time drift.
6. Single SOT with import-time validation is the lightest-weight defense against silent drift between test layers — costs ~50 lines of plumbing; benefit: drift fails at import, not in CI.
