---
phase: 65-oauth-design-doc-security-review-gate
plan: 02
subsystem: auth
tags: [oauth, security-review, mcp, threat-model, adversarial-review, oauth2, pkce, jwt, cimd, ssrf]

# Dependency graph
requires:
  - phase: 65-01
    provides: "MCP v4 OAuth 2.1 design doc (docs/plans/2026-06-14-mcp-v4-oauth-design.md)"
provides:
  - "Completed Security Review Sign-Off section in the design doc (findings + resolutions)"
  - "7 security gaps found and closed via doc edits applied in Task 1"
  - "Review status: COMPLETE recorded in the design doc"
  - "Human Sign-Off subsection present (Status: PENDING — awaiting human gate)"
affects:
  - "66-oauth-settings-prm-oasm"
  - "67-collocated-as-rs"
  - "68-per-tool-scope"
  - "69-client-dance"
  - "70-split-as-keycloak"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Adversarial security review gate before OAuth implementation (design-first pattern)"
    - "Import-time drift guard (RuntimeError) for tool scope assignments, not test-time only"
    - "Startup gate for AGENT_BRAIN_OAUTH_RESOURCE non-empty in oauth mode"
    - "Post-DNS-resolution IP validation for SSRF mitigation (not hostname-only allowlist)"

key-files:
  created: []
  modified:
    - "docs/plans/2026-06-14-mcp-v4-oauth-design.md — Security Review Sign-Off section completed; 7 gap fixes applied to relevant sections"

key-decisions:
  - "Confused-deputy termination contract applies in ALL 3 auth modes (none/basic/oauth), not oauth-only — Phase 70 integration test must verify all 3"
  - "AGENT_BRAIN_OAUTH_RESOURCE startup gate: missing/empty value in oauth mode causes exit code 2 (prevents aud-omission via unchecked empty string)"
  - "Drift guard for scope assignments MUST raise RuntimeError at module import time, not only in test runs"
  - "FileTokenStorage MUST use chmod 0o600 immediately after write (test assertion required)"
  - "PKCE S256 rejection must be enforced in the AS, not just advertised in OASM"
  - "CIMD SSRF protection requires post-DNS-resolution IP validation (DNS rebinding attack vector closed)"
  - "/mcp/subscriptions auth-exempt status requires Phase 66 audit of response data before finalizing"

patterns-established:
  - "Security review findings: format of PASS/GAP + resolution per risk, applied as doc edits not deferred to implementation"
  - "Startup gates as defense-in-depth: missing config = server refuses to start (not silent failure)"

requirements-completed: [OAUTH-01]

# Metrics
duration: 45min
completed: 2026-06-14
---

# Phase 65 Plan 02: OAuth Design Doc Adversarial Security Review Summary

**Independent adversarial review of the MCP v4 OAuth 2.1 design doc found and closed 7 security gaps across confused-deputy, aud-omission, scope escalation, SSRF rebinding, PKCE rejection, FileTokenStorage permissions, and well-known audit**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-06-14T00:00:00Z
- **Completed:** 2026-06-14T00:45:00Z
- **Tasks:** 1 of 2 complete (Task 2 is the human sign-off checkpoint — PENDING)
- **Files modified:** 1

## Status: PARTIAL — Awaiting Human Gate

Task 1 (adversarial security review) is COMPLETE and committed (7c5c7d7).
Task 2 (human security sign-off) is a blocking `checkpoint:human-verify` gate.
No Phase 66+ code may be committed until the human signs off.

## Accomplishments

- Ran an independent adversarial structured read of `docs/plans/2026-06-14-mcp-v4-oauth-design.md` against all four threat-model risks plus five additional probes
- Found 9 findings total: 2 PASS (fully adequate), 2 PASS+gap, 4 GAP, 1 PASS+audit-action
- All 7 actionable findings were resolved by edits applied directly to the relevant sections of the doc
- The Security Review Sign-Off section is now complete with a findings table and status COMPLETE
- Human Sign-Off subsection is present with Status: PENDING (correctly blocking Phase 66+)

## Task Commits

1. **Task 1: Adversarial security review + doc edits** — `7c5c7d7` (docs)
2. **Task 2: Human sign-off** — PENDING (checkpoint:human-verify gate)

## Files Created/Modified

- `/Users/richardhightower/clients/spillwave/src/agent-brain/docs/plans/2026-06-14-mcp-v4-oauth-design.md`
  — Security Review Sign-Off section completed with findings + resolutions; 7 gap-fixes
  applied to the confused-deputy, aud-omission, scope-escalation, SSRF, FileTokenStorage,
  PKCE, and well-known sections

## Decisions Made

1. **Confused-deputy: all-modes invariant** — The MCP-to-REST `X-API-Key` leg contract
   was made explicit for all 3 auth modes (`none`, `basic`, `oauth`). A developer reading
   the original doc could have interpreted it as OAuth-mode-specific.

2. **aud-omission startup gate** — `AGENT_BRAIN_OAUTH_RESOURCE` must be non-empty in
   `oauth` mode or the server exits. An empty env var would turn aud validation into
   `aud == ""`, silently accepting cross-service tokens.

3. **Import-time drift guard** — Tool scope drift detection must fire at module import
   (server startup), not only in test runs. A production deploy after adding a tool
   without running tests would otherwise ship an unguarded tool.

4. **DNS rebinding for SSRF** — Hostname allowlist alone is insufficient. Post-DNS-
   resolution IP validation is required in Phase 67.

5. **PKCE rejection gate** — Advertising S256 in OASM is not the same as rejecting
   `plain`. The AS must actively reject non-S256 requests.

6. **FileTokenStorage 0o600** — Token files must be created with owner-only permissions.
   Missing from the original doc; added as an explicit testable requirement.

## Deviations from Plan

None — all changes were required to close genuine security gaps found during the adversarial
review. Every change was applied to the design doc sections where the gap existed, as
the plan specified (not just noted in the findings section). This is standard deviation
Rule 2 (auto-add missing critical functionality for correctness/security) applied to a
docs-only context.

## Adversarial Review Detail

| # | Risk / Probe | Verdict | Gap Closed |
|---|-------------|---------|------------|
| 1 | Confused-deputy / token passthrough | PASS+gap | Termination contract updated for all 3 auth modes |
| 2 | aud-claim omission | PASS+gap | Startup gate added for AGENT_BRAIN_OAUTH_RESOURCE |
| 3 | Well-known-behind-auth deadlock | PASS+audit | Phase 66 audit action for /mcp/subscriptions |
| 4 | Per-tool scope escalation | PASS+gap | Drift guard changed to import-time RuntimeError |
| 5 | CIMD SSRF allowlist | GAP | DNS rebinding mitigation (post-resolution IP check) added |
| 6 | FileTokenStorage chmod 0o600 | GAP | chmod 0o600 requirement added with test assertion |
| 7 | PKCE S256-only rejection | GAP | AS rejection gate for plain/absent challenge added |
| 8 | In-memory token store trade-off | PASS | Adequately documented |
| 9 | 2026-07-28 RC staleness | PASS | Explicitly acknowledged with mitigation |

## Issues Encountered

None. All gaps were resolved inline without requiring architectural decisions (Rule 4).

## Next Phase Readiness

- **Blocked on:** Human sign-off (Task 2 checkpoint gate)
- **When unblocked:** Phase 66 (settings foundation + PRM/OASM public endpoints) may begin
- **What the human should verify:** Read `## Security Review Sign-Off` → `### Adversarial Review Findings` in the design doc; confirm the 9-row findings table; approve or request changes

---
*Phase: 65-oauth-design-doc-security-review-gate*
*Completed: 2026-06-14 (Task 1 only — Task 2 awaiting human)*

## Self-Check: PASSED

- [x] `docs/plans/2026-06-14-mcp-v4-oauth-design.md` — exists and modified (334 insertions, 31 deletions)
- [x] Commit 7c5c7d7 — verified via `git log --oneline -1`
- [x] `grep -q "Review status: COMPLETE"` — PASSES
- [x] `grep -q "### Adversarial Review Findings"` — PASSES
- [x] `grep -q "### Human Sign-Off"` — PASSES
- [x] Human Sign-Off status is PENDING (not APPROVED) — correct gate behavior
