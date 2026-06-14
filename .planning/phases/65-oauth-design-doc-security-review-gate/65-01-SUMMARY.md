---
phase: 65-oauth-design-doc-security-review-gate
plan: "01"
subsystem: auth
tags: [oauth, oauth2.1, mcp, jwt, pkce, rfc8707, cimd, dpop, design-doc]

# Dependency graph
requires:
  - phase: 64-graphrag-stability
    provides: stable server codebase to protect with OAuth
provides:
  - "docs/plans/2026-06-14-mcp-v4-oauth-design.md — 697-line OAUTH-01 design doc governing Phases 66-70"
  - "Threat model: four converged risks (confused-deputy, aud-claim omission, well-known deadlock, scope escalation)"
  - "AS/RS/public-route boundary specification with ASCII diagram"
  - "Token termination data flow: OAuth terminates at MCP boundary; AGENT_BRAIN_API_KEY continues to REST API"
  - "Scope-to-tool mapping: 4 scopes x 16 tools (conceptual SOT co-located with _tool_matrix.py)"
  - "Canonical resource URI contract: AGENT_BRAIN_OAUTH_RESOURCE + RFC 8707 aud binding"
  - "Registration policy: CIMD (SHOULD preferred) over DCR (MAY/deprecated)"
  - "DPoP deferral: confirmed no MUST violation; deferred to v10.5+"
  - "Auth-mode toggle: AGENT_BRAIN_AUTH in {none, basic, oauth} mutually exclusive"
  - "Two deployment shapes: co-located AS+RS (Phases 66-69) and split AS/RS (Phase 70)"
  - "Security Review Sign-Off section: PENDING placeholder for Plan 65-02"
affects:
  - 65-02 (security review fills the sign-off section)
  - 66-oauth-settings-foundation (AGENT_BRAIN_AUTH toggle, well-known endpoints)
  - 67-co-located-as-rs (OAuthAuthorizationServerProvider, CIMD, aud binding, PKCE S256)
  - 68-per-tool-scope (scope_guard, _tool_matrix.py SOT, 403 on insufficient_scope)
  - 69-mcphttpbackend-client (OAuthClientProvider, FileTokenStorage, Pattern A)
  - 70-split-as-rs (JwksTokenVerifier, PyJWKClient, Keycloak-in-CI)

# Tech tracking
tech-stack:
  added:
    - "PyJWT[crypto] ^2.13 — recorded (not installed); replaces python-jose"
    - "authlib ^1.7.2 — recorded (not installed)"
    - "pwdlib[argon2] >=0.2 — recorded (not installed)"
    - "PyJWKClient — recorded (not installed; bundled with PyJWT)"
    - "itsdangerous ^2.2 — recorded (not installed)"
  patterns:
    - "OAUTH-01 design-doc-gated delivery: doc + security review must precede any implementation code"
    - "Two independent auth layers: MCP client→MCP server (OAuth Bearer) and MCP server→REST API (AGENT_BRAIN_API_KEY / X-API-Key)"
    - "Auth-mode toggle: AGENT_BRAIN_AUTH in {none, basic, oauth} mutually exclusive with startup gate"
    - "Well-known routes mounted BEFORE RequireAuthMiddleware (critical mount-order constraint)"
    - "scope_guard-based per-tool enforcement: 403 on insufficient_scope, not 401"

key-files:
  created:
    - "docs/plans/2026-06-14-mcp-v4-oauth-design.md — OAUTH-01 design contract for Phases 66-70 (697 lines)"
  modified: []

key-decisions:
  - "CIMD (Client ID Metadata Documents) is preferred (SHOULD) over DCR (MAY/deprecated, backwards-compat only) — locked"
  - "DPoP deferred to v10.5+: no production Python DPoP lib (Authlib #315 open since 2021); DPoP not in MCP core spec MUST — no MUST violation"
  - "AGENT_BRAIN_OAUTH_RESOURCE is the canonical resource URI env var; aud bound via RFC 8707 on all issued JWTs"
  - "AGENT_BRAIN_API_KEY / X-API-Key MCP-to-REST leg preserved exactly; OAuth client token NEVER forwarded (confused-deputy prevention)"
  - "In-memory token store for co-located AS: process restart invalidates sessions — known trade-off, document for operators"
  - "SDK gap: mcp SDK does NOT ship GET /.well-known/jwks.json — co-located AS adds custom public route"
  - "Auth-mode toggle AGENT_BRAIN_AUTH in {none (default), basic, oauth}; mutually exclusive; startup gate rejects invalid combos"
  - "Live spec re-verified 2026-06-14 via context7: 2025-11-25 baseline confirmed; 2026-07-28 RC had NOT landed in authorization spec as of authoring date"
  - "Token lifecycle: 15-min access / 30-day rotating refresh"

patterns-established:
  - "Design-doc gate: no Phase 66+ implementation code until Plan 65-02 sign-off is filled"
  - "Threat model leads with authorization CONFUSION (not authentication bypass): confused-deputy and aud-claim omission are the dominant risks"
  - "Scope semantics: 403 on insufficient_scope (token valid, scope wrong) vs 401 on missing/invalid token"
  - "Well-known route mount order: routes added to Starlette routes list BEFORE RequireAuthMiddleware wrapping"

requirements-completed: [OAUTH-01]

# Metrics
duration: 35min
completed: "2026-06-14"
---

# Phase 65 Plan 01: OAuth Design Doc Summary

**697-line MCP v4 OAuth 2.1 design doc authored — all 10 mandatory sections, spec re-verified on 2026-06-14, four converged security risks documented, OAUTH-01 contract governing Phases 66-70 established**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-06-14T15:25:57Z
- **Completed:** 2026-06-14T15:26:32Z (wall time)
- **Tasks:** 2 (Tasks 1 and 2 combined into a single file creation pass)
- **Files modified:** 1

## Accomplishments

- Authored `docs/plans/2026-06-14-mcp-v4-oauth-design.md` (697 lines) with all 10 mandatory H2 sections
- Re-verified live MCP Authorization spec via Context7 on 2026-06-14: 2025-11-25 baseline confirmed active; the 2026-07-28 RC (MCP-goes-stateless) had NOT landed in the authorization spec as of the authoring date
- Documented four converged security risks (authorization CONFUSION, not authentication bypass) with countermeasures mapping to Phases 66-70
- Established token termination contract: OAuth Bearer terminates at MCP boundary; MCP-to-REST leg keeps AGENT_BRAIN_API_KEY / X-API-Key (OAUTH-08)
- Recorded CIMD-over-DCR decision + DPoP deferral (confirmed: no MUST violation) satisfying ROADMAP SC#4
- Left Security Review Sign-Off section as PENDING placeholder for Plan 65-02

## Task Commits

Each task was committed atomically:

1. **Tasks 1+2: Author the full design document (header, spec citation, threat model, boundary, token termination, scope-to-tool table, canonical URI, CIMD/DCR policy, DPoP deferral, auth-mode toggle)** - `9b70c52` (docs)

## Files Created/Modified

- `/Users/richardhightower/clients/spillwave/src/agent-brain/docs/plans/2026-06-14-mcp-v4-oauth-design.md` — OAUTH-01 design contract governing Phases 66-70 (697 lines)

## Decisions Made

- **CIMD preferred over DCR:** CIMD (Client ID Metadata Documents, SHOULD per 2025-11-25 spec) is the preferred registration path. DCR (RFC 7591) is MAY/deprecated/backwards-compat. Locked per 65-CONTEXT.md.
- **DPoP deferred to v10.5+:** No production Python DPoP library (Authlib #315 open since 2021). DPoP is not in the MCP core spec as a MUST. Deferral confirmed to violate no current-spec MUST.
- **AGENT_BRAIN_OAUTH_RESOURCE:** The canonical env var for the MCP server resource URI. RFC 8707 `resource` parameter MUST appear in both `/authorize` and `/token` requests; AS binds `aud` to it in every issued JWT; RS validates `aud` on every inbound token.
- **Two independent auth layers:** (Layer 1) MCP client → MCP server via OAuth Bearer; (Layer 2) MCP server → agent-brain REST API via AGENT_BRAIN_API_KEY/X-API-Key. MUST NOT be conflated.
- **In-memory token store for co-located AS:** Known trade-off (process restart invalidates sessions). Documented explicitly for operators.
- **SDK gap noted:** `mcp` SDK does NOT ship `GET /.well-known/jwks.json`; Phase 67 adds custom public route.
- **Live spec status as of 2026-06-14:** 2025-11-25 baseline confirmed via context7. 2026-07-28 RC (MCP-goes-stateless) had NOT landed in authorization spec on authoring date. Phase 70 MUST re-verify before shipping.

## Deviations from Plan

None — plan executed exactly as written. Tasks 1 and 2 were both authoring-only tasks targeting the same file; they were completed in a single write operation (both tasks verified to pass their respective grep checks).

## Issues Encountered

None. The context7 MCP Authorization spec verification returned content from the 2025-11-25 baseline, consistent with the planning research. No surprises in the live spec content.

## Live Spec Verification Result

- **Tool used:** `npx ctx7@latest` with library `/modelcontextprotocol/modelcontextprotocol` (source reputation: High, benchmark: 85.1)
- **Date:** 2026-06-14
- **Finding:** Live spec content references `modelcontextprotocol/modelcontextprotocol` files from the 2025-11-25 branch. CIMD preferred/SHOULD; DCR MAY/deprecated; RFC 8707 `resource` MUST in both auth and token requests; PKCE S256 mandatory — all consistent with planning research baseline.
- **2026-07-28 RC status:** NOT found in authorization spec content fetched on authoring date. The RC is anticipated but had not landed as of 2026-06-14.

## Next Phase Readiness

- Plan 65-02 (independent adversarial security review) may now begin — the design doc exists at the exact ROADMAP SC#1 path
- Plan 65-02 fills the `## Security Review Sign-Off` section; project-owner human sign-off is required before any Phase 66+ code
- All four threat-model risks documented with implementation-phase countermeasure assignments
- Scope-to-tool table ready for Phase 68 `_tool_matrix.py` implementation
- AGENT_BRAIN_OAUTH_RESOURCE contract ready for Phase 66 settings implementation

---
*Phase: 65-oauth-design-doc-security-review-gate*
*Completed: 2026-06-14*
