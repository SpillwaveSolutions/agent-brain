# Phase 46: Project-Local Runtime Install Harness - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 46 delivers the shared runtime-parity harness layer that keeps installs inside repo-owned project fixtures, verifies the generated install tree before any headless runtime invocation, and reports runtime-specific failures explicitly. This phase does not add new runtime adapters or implement the actual Codex/OpenCode/Gemini headless execution flows for success cases; it prepares the isolated workspace, verification, and failure-reporting foundation those later phases depend on.

</domain>

<decisions>
## Implementation Decisions

### Integration project layout
- **D-01:** Runtime parity workspaces live under a git-ignored `e2e_workdir/` root so test installs never touch tracked fixture directories or user-global runtime config paths.
- **D-02:** Each runtime gets a dedicated isolated directory under `e2e_workdir/`, following the pattern `e2e_workdir/<runtime>-runtime/`.
- **D-03:** Each runtime directory includes its own generated install target, logs, and a `cleanup/` helper area for tearing down generated artifacts between runs.

### Install verification policy
- **D-04:** Install verification is mandatory before any runtime invocation and runs as a sequence: structure check, targeted file/JSON validation, then a dry headless runtime probe.
- **D-05:** The verification layer should confirm `agent-brain install-agent` wrote the expected runtime-specific tree and that the install/converter output contains no structural errors.
- **D-06:** A lightweight verification script is expected to validate key generated files plus the JSON emitted by install and runtime checks.
- **D-07:** A dry headless invocation that returns machine-readable JSON is the final gate before runtime-specific parity execution continues.

### Failure reporting
- **D-08:** Failures must emit both a human-readable log and a structured JSON payload so automation and humans can diagnose the same run.
- **D-09:** Failure payloads should include runtime name, error type, details, and remediation hints such as missing CLI install guidance.
- **D-10:** Missing CLIs, install verification failures, malformed JSON, and accidental global-path mutations must be surfaced as explicit per-runtime failures rather than silent skips.

### the agent's Discretion
- Exact naming of verification and cleanup scripts inside each runtime directory.
- Exact JSON schema shape for internal helper outputs, as long as it clearly distinguishes install failure, malformed output, global-path violation, and success.
- Whether `e2e_workdir/` sits directly under repo root or is created by harness helpers as long as it remains repo-owned and git-ignored.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` — Phase 46 goal, dependency position, and required success criteria for the shared harness layer.
- `.planning/REQUIREMENTS.md` — ISO-01, ISO-02, and PARITY-01 define the isolation, verification, and explicit-failure requirements this phase must satisfy.

### Existing parity harness
- `e2e-cli/README.md` — documents the current E2E harness model, runtime parity goals, fixture/project-copy pattern, and cleanup expectations.
- `e2e-cli/lib/runtime_parity.sh` — current reusable helper layer for repo-owned project directories, expected target paths, forbidden global-path checks, and OpenCode mutation detection.

### GSD workflow context
- `.codex/get-shit-done/workflows/discuss-phase.md` — source workflow that drove the decisions captured here.
- `.codex/get-shit-done/workflows/plan-phase.md` — next-stage planning contract that should consume this context.
- `.codex/get-shit-done/workflows/verify-work.md` — later verification workflow expectations for how phase outputs are judged.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `e2e-cli/lib/runtime_parity.sh`: already provides runtime target mapping, forbidden-global-path detection, repo-owned workspace assertions, project fixture copying, project-local install execution, and OpenCode global-mutation snapshot/diff helpers.
- `e2e-cli/fixtures/runtime-project-template/`: existing minimal checked-in project template that can seed disposable runtime workspaces.
- `e2e-cli/README.md`: already establishes the current harness contract around disposable project copies, success cleanup, and failure preservation.

### Established Patterns
- Runtime parity work should reuse `e2e-cli/` rather than introducing a second harness framework.
- Project-local installs are the required shape: `agent-brain install-agent --agent <runtime> --project --path <workspace> --json`.
- Success paths should clean only disposable runtime outputs, while failure paths preserve scenario artifacts for debugging.
- Global runtime directories are forbidden test targets and should be guarded explicitly rather than trusted implicitly.

### Integration Points
- New Phase 46 helpers should extend `e2e-cli/lib/runtime_parity.sh` and the associated runtime scenarios/tests rather than bypassing the current harness.
- Later runtime-specific phases (47-49) will depend on Phase 46’s workspace layout, verification helpers, and structured error-reporting conventions.
- `.gitignore` must include the repo-owned `e2e_workdir/` workspace so disposable runtime installs stay untracked.

</code_context>

<specifics>
## Specific Ideas

- The workspace should use dedicated runtime directories under `e2e_workdir/`, not a shared mixed-runtime tree.
- Cleanup is an explicit part of the design: each runtime area should have a `cleanup/` helper or equivalent teardown mechanism.
- Verification should be strict and front-loaded so later runtime phases fail early on bad installs rather than during deeper headless execution.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 46-project-local-runtime-install-harness*
*Context gathered: 2026-04-01*
