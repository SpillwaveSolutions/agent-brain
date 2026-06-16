# Phase 65: OAuth Design Doc + Security Review Gate - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning

> Captured in `--auto` mode. Phase 65's decisions are almost entirely pre-locked by
> REQUIREMENTS.md (OAUTH-01..12), the ROADMAP success criteria, and the verified
> research SUMMARY. CONTEXT here transcribes those locks and names the canonical refs
> the design-doc author MUST follow. The one genuinely open item — an independent
> human security sign-off — is flagged as a checkpoint the auto-chain cannot clear.

<domain>
## Phase Boundary

Produce a single, fully-specified, independently-reviewed OAuth 2.1 design document on
disk at `docs/plans/2026-06-14-mcp-v4-oauth-design.md` that governs ALL implementation
decisions for Phases 66-70. This phase delivers a DOCUMENT plus a passed security-review
gate — **no OAuth implementation code lands in this phase**. Writing settings, endpoints,
middleware, scope guards, or the client dance all belong to Phases 66-70.

Scope is exactly OAUTH-01 (1 requirement). The design doc DESCRIBES the full milestone;
it does not BUILD any of it.

</domain>

<decisions>
## Implementation Decisions

### Design-doc location & mandatory sections
- File: `docs/plans/2026-06-14-mcp-v4-oauth-design.md` (exact path — ROADMAP success criterion #1 checks for it).
- MANDATORY sections (all required by ROADMAP SC#1 + OAUTH-01):
  1. **Threat model** — centered on the four converged risks from research: confused-deputy/token-passthrough, `aud`-claim omission, well-known-behind-auth deadlock, per-tool scope-escalation.
  2. **AS / RS / public-route boundary diagram** — shows which routes are auth-exempt (`/.well-known/*`, `/authorize`, `/token`, `/healthz`) vs enforced (`/mcp`).
  3. **Token-termination data flow** — client OAuth token terminates at the MCP boundary; the MCP→REST leg keeps `AGENT_BRAIN_API_KEY` (`X-API-Key`). The MCP server NEVER forwards the client's OAuth token upstream (confused-deputy prevention, OAUTH-08).
  4. **Scope-to-tool mapping table** — the 4 scopes × 16 MCP tools (see below), co-located conceptually with `_tool_matrix.py`.
  5. **Canonical resource URI contract** — `AGENT_BRAIN_OAUTH_RESOURCE` env var; `aud` binding via Resource Indicators (RFC 8707).
  6. **DCR/CIMD policy decision** — see below.
  7. **DPoP deferral rationale** — see below.
  8. **Spec-version citation** — see below.
  9. **Security-review sign-off section** — see Security-review gate.

### Standards stack (locked by research + spec 2025-11-25)
- OAuth 2.1 + **PKCE S256 mandatory** (every MCP client is public); `code_challenge_methods_supported: ["S256"]` MUST appear in AS metadata or compliant clients abort.
- Protected Resource Metadata (RFC 9728) at `/.well-known/oauth-protected-resource`.
- Authorization Server Metadata (RFC 8414) at `/.well-known/oauth-authorization-server`.
- Resource Indicators (RFC 8707) — `resource` param MUST on both auth + token requests; `aud` binding + RS-side `aud` validation MUST.
- Token Introspection (RFC 7662) + Revocation (RFC 7009) — for split-AS / opaque-token deployments (Phase 70).
- Two deployment shapes: **co-located AS+RS** (single binary, JWT-signed, no introspection — Phases 66-69) and **split AS/RS** (external IdP / Keycloak, JWKS-cached verification — Phase 70).

### Registration policy — CIMD over DCR (locked)
- **Client ID Metadata Documents (CIMD)** is the preferred registration path (`SHOULD` in 2025-11-25 spec) + static pre-registration.
- The co-located AS fetches the `client_id` URL on CIMD registration with **SSRF protection (domain allowlist)**.
- **Dynamic Client Registration (DCR, RFC 7591)** is `MAY`/deprecated in 2025-11-25 — ship as a CIMD fallback at most, or omit for the self-hosted single-user shape. The doc must record this explicitly (ROADMAP SC#4).

### DPoP — forced-deferred to v10.5+ (locked)
- No production-grade Python DPoP library exists (Authlib issue #315 open since 2021); DPoP is optional in the 2025-11-25 core spec (lives in the ext-auth extension repo).
- The doc must confirm DPoP can be deferred **without violating any current-spec MUST** (ROADMAP SC#4).

### Spec-version verification (locked baseline + live-check obligation)
- Authoritative baseline: **MCP Authorization 2025-11-25** (research-verified, fetched verbatim).
- The design-doc author MUST re-verify the live spec at authoring time and **explicitly acknowledge the 2026-07-28 RC** (MCP-goes-stateless / no-initialize handshake) — whether it has landed and what it changes. The doc is written/signed-off BEFORE that RC lands; the staleness risk must be stated, not hidden (ROADMAP SC#2).

### Scope design — 4 scopes × 16 tools (locked)
- `agent-brain:read` — all read-only tools: `search_documents`, `explain_result`, `list_folders`, `cache_status`, `list_jobs`, `get_job`, `list_file_types`, `get_corpus_status` (+ resource reads).
- `agent-brain:index` — `index_folder`, `add_documents`, `inject_documents`, `wait_for_job`.
- `agent-brain:admin` — `cancel_job`, `remove_folder`, `clear_cache`.
- `agent-brain:subscribe` — guards SUB-01..05 subscription machinery.
- Insufficient scope → **HTTP 403 + `WWW-Authenticate: Bearer error="insufficient_scope"`** (NOT 401 — token is valid, scope is not).

### Auth-mode toggle (locked)
- `AGENT_BRAIN_AUTH` ∈ {`none` (default), `basic` (formalizes the v10.2.1 SECURITY-01 shared-secret Bearer / API_KEY path as the LAN bridge), `oauth`}; mutually exclusive; startup gate rejects invalid combinations.

### Library choices (from research — for the doc to record, not install this phase)
- `PyJWT[crypto] ^2.13` (JWT sign + JWKS-cached verify; python-jose is dead).
- `authlib ^1.7.2` (OAuth grant handlers for `OAuthAuthorizationServerProvider` if not hand-rolled; no DPoP — matches deferral).
- `pwdlib[argon2]` (password hashing; passlib unmaintained).
- `PyJWKClient` (split-AS JWKS verification, 5-min TTL + `kid`-miss refresh).
- Key SDK finding: `mcp >= 1.27.2` already ships both-side OAuth machinery (`OAuthAuthorizationServerProvider` + `create_auth_routes()`, `RequireAuthMiddleware` + `BearerAuthBackend`, `OAuthClientProvider`). The milestone **wires + configures + mints JWTs** — it does not build OAuth from scratch. The doc must frame the work this way.

### Security-review gate mechanism (the one non-auto item)
- The phase produces the design doc AND an **independent adversarial security review** of it (recommended: run `/security-review` or spawn a dedicated security-reviewer agent against the doc, focused on the four threat-model risks).
- Findings + resolutions are recorded in the doc's **sign-off section**.
- **Final human sign-off by the project owner is REQUIRED before any Phase 66+ code is committed** (ROADMAP SC#3, OAUTH-01). This is a human-action checkpoint — an automated/auto-chain run CANNOT clear it. Expect verification to return `human_needed` here; that is correct, not a failure.

### Claude's Discretion
- Exact prose structure, diagram format (ASCII vs mermaid), and section ordering within the doc.
- Whether the adversarial review is the `/security-review` skill, a spawned agent, or both.
- Depth of the worked token-flow examples.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or writing the design doc.**

### OAuth / MCP-auth source material
- `.planning/research/SUMMARY.md` — PRIMARY input; verified against MCP Authorization spec 2025-11-25; resolves spec levels (MUST/SHOULD/MAY), library picks, CIMD-vs-DCR, DPoP deferral, the four threat risks, and the converged phase ordering. **Read this first.**
- `docs/roadmaps/mcp/v4-oauth-for-remote.md` — v4 design sketch (standards stack, deployment shapes, scope design).
- `docs/plans/2026-05-28-mcp-uds-transport-design.md` §11 (v4 row), §15.3 — master MCP transport design; the v4 row this milestone implements.
- `docs/plans/2026-06-05-issue-179-api-key-auth.md` — prior SECURITY-01 static Bearer / `AGENT_BRAIN_API_KEY` auth (the `basic` mode this milestone formalizes; the REST leg the MCP→REST token-termination boundary preserves).
- `docs/plans/2026-06-09-enterprise-hardening-and-cloud-deployment.md` — parent enterprise plan; OAuth (v10.4) is the prerequisite for its governed-MCP pieces (out of scope here, context only).

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — OAUTH-01 (this phase) + OAUTH-02..12 (the doc must cover all of them); the Deferred section (DPoP, SEP-1880 per-tool scope proposal, Device Grant) the doc must record.
- `.planning/ROADMAP.md` — Phase 65 goal + 4 success criteria; Phases 66-70 (the build the doc governs).
- Issue [#188](https://github.com/SpillwaveSolutions/agent-brain/issues/188) — MCP v4 milestone source.

### Live spec (re-verify at authoring time)
- MCP Authorization spec **2025-11-25** (baseline) + check for the **2026-07-28 RC** status. Use context7 / WebFetch against the live modelcontextprotocol spec during planning/authoring.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `mcp >= 1.27.2` SDK OAuth machinery (`OAuthAuthorizationServerProvider`, `create_auth_routes()`, `RequireAuthMiddleware`, `BearerAuthBackend`, `OAuthClientProvider`) — the doc frames implementation as wiring these, not building OAuth.
- `agent-brain-mcp/agent_brain_mcp/http.py` — the Starlette app where well-known + auth-exempt routes mount alongside `/healthz` and the new `/mcp/subscriptions` (Phase 64); the boundary diagram targets this app.
- v10.2.1 SECURITY-01 static Bearer / `AGENT_BRAIN_API_KEY` plumbing (CLI → server → MCP backend) — the `basic` mode and the preserved MCP→REST leg.
- `_tool_matrix.py` (MCP package) — the existing 16-tool single-source-of-truth the scope→tool mapping table co-locates with.

### Established Patterns
- Design-first precedent: every prior MCP milestone (v2 Phase 50, v3 Phase 56) opened with a design doc in `docs/plans/`. This phase follows the same gate, adding an independent security review.
- Loopback/no-auth trust model today — the doc must show how `oauth` mode changes it for remote deployment while `none`/`basic` keep the LAN posture.

### Integration Points
- The doc is the contract for Phases 66 (settings + PRM/OASM endpoints), 67 (co-located AS+RS middleware), 68 (per-tool scope), 69 (client dance), 70 (split AS + Keycloak-in-CI + 90% oauth/ coverage gate).

</code_context>

<specifics>
## Specific Ideas

- "Design-doc-gated, design first" — the user's explicit milestone framing: no OAuth code until this doc is signed off.
- The dominant risk is authorization CONFUSION, not authentication bypass — the threat model must lead with confused-deputy and `aud` omission, the two most common OAuth RS implementation errors.
- Frame the work honestly as "wire + configure + mint JWTs" against the MCP SDK — avoid implying a from-scratch OAuth build.

</specifics>

<deferred>
## Deferred Ideas

- DPoP (RFC 9449) — v10.5+ (no production Python lib); recorded in-doc as a deferral, not built.
- SEP-1880 per-tool scope enforcement proposal — not in current spec; the doc notes our scope enforcement is `scope_guard`-based, not SEP-1880.
- Device Authorization Grant (RFC 8628) — spec doesn't require it; PKCE + loopback redirect is the MCP path.
- Enterprise governed-MCP pieces (#202-205) — downstream of OAuth, out of milestone.

</deferred>

---

*Phase: 65-oauth-design-doc-security-review-gate*
*Context gathered: 2026-06-14*
