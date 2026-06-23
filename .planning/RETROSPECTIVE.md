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

## Milestone: v10.3 — MCP v3 (CLI-via-MCP + Framework Matrix)

**Shipped:** 2026-06-14
**Phases:** 8 (56-63) | **Plans:** 24

### What Was Built
The `agent-brain` CLI became a reference MCP client: `--transport mcp` + `--mcp-transport stdio|http` with byte-identical results to `--transport uds` (the v3 DoD anchor), `mcp.runtime.json` auto-discovery, `agent-brain mcp start/stop` helpers, and `agent-brain prompt`/`resources` surfaces. Subprocess hygiene (env allowlist, pinned cwd, SIGTERM→SIGKILL, 1000-invocation orphan test) was locked as a contract *before* the framework matrix landed. Seven framework adapters were smoke-tested (5 Python: OpenAI Agents, LangChain, LlamaIndex, Pydantic AI, Autogen; 2 TS: Mastra, Vercel AI SDK), surfaced via an opt-in `task mcp:framework-matrix`, a nightly advisory CI, and `docs/INTEGRATIONS.md`.

### What Worked
- **Design-first + skeleton-first (Phase 56).** Filing the v3 design doc and landing `BackendClient`/`McpBackend` Protocols as skeletons (with a load-bearing `NotImplementedError("Wired in Phase 57+")` sentinel) let later phases grep for exactly what they had to wire. Zero ambiguity at the seams.
- **Hygiene-before-frameworks ordering (Phase 60 → 61/62).** Locking subprocess teardown as a contract before any framework test meant no framework leg re-discovered orphan-process bugs independently.
- **8/8 phases passed verification on first pass.** Same clean-execution streak as v10.2.

### What Was Inefficient
- **A cross-phase regression slipped past per-phase verification.** Phase 60's env allowlist (correctly) stripped `AGENT_BRAIN_STATE_DIR`, which Phase 57's stdio path implicitly relied on — breaking the CLI-MCP-04 DoD anchor under state-dir override. No single phase verifier could see it; only the milestone audit's cross-phase integration trace caught it. Cost: a post-ship fast-follow fix.
- **The DoD-anchor test skipped without a key.** The byte-identical contract test `pytest.skip`ped without `OPENAI_API_KEY`, so it read green forever and never exercised the actual failure mode. "Asserted" masqueraded as "proven."

### Patterns Established
- **Separate `@runtime_checkable` Protocols with a negative-conformance pin** (`DocServeClient ⊄ McpBackend`) to prevent accidental shape conflation.
- **Pattern A: fresh subprocess per MCP call** so hygiene applies per-call without session lifecycle complexity.
- **Opt-in + nightly-advisory for drift-prone external suites** — gated env var + non-blocking CI status keeps PRs fast.

### Key Lessons
1. **Per-phase verification cannot catch cross-phase seams.** A security/hygiene change in a later phase can invalidate an implicit dependency from an earlier one. The milestone audit's integration trace is the safety net — it earned its keep this milestone.
2. **Credential-gated tests are silent coverage holes on anchor requirements.** A DoD-anchor test that skips without a key should be a hard failure (or run against a keyless stub backend), not a silent skip.
3. **Respect the security boundary when fixing discovery.** The fix passed state-dir as an explicit `--state-dir` argument rather than re-opening the env allowlist — closing the gap without weakening Phase 60's hygiene contract.

### Cost Observations
- Model mix: opus (orchestration + plan-check + verifier + audit) + sonnet (executors + integration checker). No haiku.
- Timeline: 2026-06-05 → 2026-06-14 (~9 days).
- Notable: 8/8 phases first-pass verified; the one defect was found by the milestone audit (not in production) and fixed test-first before ship. `task before-push` green at 544 MCP + 557 CLI.

---

## Milestone: v10.4 — MCP v4 (OAuth 2.1 + GraphRAG Stability)

**Shipped:** 2026-06-22
**Phases:** 7 (64-70) | **Plans:** 21

### What Was Built
Agent Brain can now run remotely behind OAuth 2.1 on the Streamable HTTP transport. Bugs first (Phase 64): the kuzu `SIGSEGV` under sustained GraphRAG indexing (#178) was isolated into an out-of-process `spawn` subprocess with per-job graceful degradation, health counts became a live kuzu `COUNT(*)` (killing the `0/100` vs `5677/4366` drift, #184), and a `graph restore-from-snapshot` CLI + doctor WARN shipped. Then a design-doc-gated OAuth build (Phases 65-70): security-reviewed design doc → public discovery root (RFC 9728 PRM + RFC 8414 OASM) + `AGENT_BRAIN_AUTH` toggle → co-located AS+RS (authorization-code + PKCE S256, RS256 JWTs, JWKS, CIMD registration with a full SSRF stack) → per-tool scope enforcement (4 scopes × 16 tools, 403-vs-401) → transparent client-side OAuth dance in `McpHttpBackend` (`OAuthClientProvider` + `FileTokenStorage` reuse, confused-deputy prevention) → split AS/RS validated against a live Keycloak-in-CI with introspection + jti-denylist revocation, behind a binding ≥90% `oauth/` coverage gate.

### What Worked
- **Design-doc + independent security-review gate before any code (Phase 65).** The adversarial review found and closed 7 real gaps (DNS-rebinding SSRF post-resolution check, empty-resource startup gate, import-time scope drift guard, PKCE-plain rejection, `0o600` token file, all-mode termination contract, subscriptions exemption) *before* implementation — the single highest-leverage decision of the milestone. Auth is where a design bug is a vulnerability.
- **Bugs-first ordering.** Stabilizing kuzu (Phase 64) before stacking auth meant the OAuth work landed on a non-crashing server; no auth phase had to debug a SIGSEGV.
- **One verifier seam (`build_verifier()`) for three topologies.** Co-located / external-JWKS / introspection became a config swap behind a stable `verify_token() -> AccessToken | None` contract — the split-AS phase (70) was a config + test phase, not a refactor.
- **7/7 phases passed verification on first pass** — the clean-execution streak continued (v10.2 6/6, v10.3 8/8, v10.4 7/7).

### What Was Inefficient
- **Transient API 529s interrupted executor + verifier mid-phase (69).** Plan 69-04's finalization and goal-backward verification had to be completed inline by the orchestrator with grep/test evidence after the subagents hit overload errors. No code was lost, but it broke the clean sub-agent handoff.
- **An executor erroneously marked OAUTH-07 (Phase 69) complete during Phase 68** and had to be reverted to Pending — a cross-phase bookkeeping slip the orchestrator caught.
- **Keycloak-in-CI took real fighting.** Service-container limits (can't override the command; prod `start` fails health checks) forced a step-level `docker run … start-dev`, and Keycloak's lack of native RFC 8707 before 26.8 forced an audience-scope-mapper workaround. The integration was sound but cost iterations.
- **No formal Nyquist `VALIDATION.md` artifacts** for any of the 7 phases (same posture as v10.3) — verification rode on goal-backward VERIFICATION.md with substantive test evidence instead.

### Patterns Established
- **Security-review gate as an explicit phase** (not a checklist item) for any auth/security-critical subsystem.
- **Isolate native-crash-prone work (kuzu) in a spawned subprocess** so an uncatchable SIGSEGV becomes a catchable, degradable error.
- **Discovery routes in `exempt_routes` ABOVE the auth-wrapped Mount**, pinned by an index-order test that survives later middleware additions (Starlette first-match).
- **Single config seam selecting auth topology** (`build_verifier()`); RS depends only on the stable verify contract.
- **Pre-dispatch middleware for real HTTP status codes** where the lowlevel server would otherwise convert handler exceptions to JSON-RPC-in-200.
- **Co-locate the scope→tool map with the tool SOT + import-time drift guard** so an unscoped tool fails the server at import, not silently in prod.

### Key Lessons
1. **Gate security subsystems on an independent adversarial review before code.** 7 real vulnerabilities were closed at design time for the cost of one review phase — far cheaper than finding them post-ship.
2. **A stable verification seam turns a topology change into a config change.** Designing `verify_token()` as the only contract the RS depends on made co-located→split-IdP a non-event.
3. **CI integration with stateful external services (Keycloak) needs a command-override escape hatch** — budget for step-level `docker run` over `services:` when the container needs non-default startup.
4. **Transient provider overloads (529s) need an orchestrator fallback path** so a sub-agent dying mid-finalization doesn't lose verification evidence.
5. **Confused-deputy prevention must be a named, tested invariant** — assert the upstream token is *absent*, not just that the right header is present.

### Cost Observations
- Model mix: opus (orchestration + plan-check + verifier + security review + audit) + sonnet (executors + integration checker). No haiku.
- Timeline: 2026-06-14 → 2026-06-22 (~8 days).
- Notable: 7/7 phases first-pass verified; `agent_brain_mcp/oauth/` at 90.53% behind a binding ≥90% CI gate; fast suite at 1021 MCP tests. The two defects (529 interruption, erroneous Phase-69 completion) were process slips caught in-flight, not shipped bugs.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v10.4 | ~8 | 7 | Independent security-review gate as an explicit phase before any auth code (closed 7 design-time vulns); bugs-first ordering; single `build_verifier()` seam made co-located→split-IdP a config swap; Keycloak-in-CI via step-level `docker run` |
| v10.3 | ~8 | 8 | Milestone audit's cross-phase integration trace caught a DoD-anchor regression invisible to per-phase verifiers; hygiene-before-frameworks ordering; design+skeleton-first with grep-able sentinels |
| v10.2 | ~7 | 6 | Wave parallelism scheduled by file-collision analysis (not topic), not plan independence; `_tool_matrix.py` SOT pattern with import-time drift guard validated |
| v9.4.0 | n/a | 10 | Audit-driven gap closure was formalized with dedicated closure phase planning |
| v9.3.0 | 1 | 2 | Retroactive phase closure validated as pattern; spec-as-contract formalized |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v10.4 | 1021 MCP fast-suite (+~300 over milestone) | `agent_brain_mcp/oauth/` 90.53% behind binding ≥90% CI gate | +PyJWT[crypto]/authlib/pwdlib (auth is inherently dep-bearing); mcp SDK ^1.12→^1.27.2 |
| v10.2 | ~530 new (1685+ total) | agent-brain-mcp 91.83% / agent-brain-uds 99% | 0 (uses existing MCP SDK 1.12.x) |
| v9.4.0 | n/a | n/a | n/a |
| v9.3.0 | 47 (graph extractors) | n/a | 0 (doc-only milestone) |

### Top Lessons (Verified Across Milestones)

1. Requirement-ID traceability plus verification artifacts materially reduces ambiguity during milestone close-out.
2. Canonical-path consistency in docs must be continuously enforced to prevent setup/onboarding flow drift.
3. When SPECs have all checkboxes checked, verify code before planning — retroactive closure saves full execution cycles.
4. Schedule wave parallelism by file-collision analysis, not plan independence — plans that look independent but commit to the same file will race at the `git commit` step.
5. Run a pinned-SDK smoke test before planning a phase that depends on that SDK — runtime API drift is more expensive than design-time drift.
6. Gate security-critical subsystems on an explicit independent-review phase before any implementation — design-time vulnerabilities are an order of magnitude cheaper to close than shipped ones (v10.4 closed 7).
7. Design one stable verification/abstraction seam so deployment-topology changes become config swaps, not refactors (v10.4 `build_verifier()`: co-located ↔ split-IdP).
6. Single SOT with import-time validation is the lightest-weight defense against silent drift between test layers — costs ~50 lines of plumbing; benefit: drift fails at import, not in CI.
