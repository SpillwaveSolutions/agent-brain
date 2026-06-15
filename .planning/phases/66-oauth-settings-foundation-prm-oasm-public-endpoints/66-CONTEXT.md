# Phase 66: OAuth Settings Foundation + PRM/OASM Public Endpoints - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning

> Captured in `--auto` mode. Phase 66's decisions are almost entirely pre-locked by the
> APPROVED OAuth design doc (`docs/plans/2026-06-14-mcp-v4-oauth-design.md`, human sign-off
> recorded 2026-06-14), REQUIREMENTS.md (OAUTH-02/03/09), and the ROADMAP success criteria.
> CONTEXT here transcribes those locks, resolves the Phase-66-specific gray areas (how to
> serve discovery JSON before an Authorization Server exists, and where the auth toggle is
> validated), and names the canonical refs downstream agents MUST read. No genuinely open
> human-decision items remain — the design-doc security gate already cleared in Phase 65.

<domain>
## Phase Boundary

Stand up the **public OAuth discovery root** and the **auth-mode settings foundation** for
the co-located AS+RS topology — with **no token issuance and no request-path enforcement**.

Phase 66 delivers exactly three requirements (OAUTH-02, OAUTH-03, OAUTH-09):

1. **PRM** (RFC 9728) served at `/.well-known/oauth-protected-resource` (+ the path-suffixed
   variant), publicly reachable with NO token → HTTP 200.
2. **OASM** (RFC 8414) served at `/.well-known/oauth-authorization-server`, advertising
   `code_challenge_methods_supported: ["S256"]`, publicly reachable with NO token → 200.
3. **`AGENT_BRAIN_AUTH` toggle** (`none` / `basic` / `oauth`) wired and validated at the
   settings/startup layer; mutually exclusive; a startup gate rejects invalid combinations
   and logs a clear error at boot.

**Explicitly OUT of scope for Phase 66** (belongs to Phases 67-70):
- Token issuance — `/authorize`, `/token`, `/register`, JWKS endpoint (Phase 67).
- `RequireAuthMiddleware` request-path enforcement on `/mcp` (Phase 67).
- The basic-vs-oauth request-path mutual-exclusion test — a valid JWT failing the
  static-bearer check / an API key passing it (ROADMAP Phase 67 SC#5).
- Per-tool scope enforcement / `_tool_matrix.py` scope map (Phase 68).
- Client-side OAuth dance / `FileTokenStorage` (Phase 69).

The well-known endpoints can be **fully correct and live before any AS exists** — they are
config-derived JSON documents. That independence is the testable heart of this phase
(ROADMAP SC#3: both return 200 even when `RequireAuthMiddleware` is later wired).

</domain>

<decisions>
## Implementation Decisions

### Well-known route construction & mounting
- **Hand-roll the two well-known routes** as plain Starlette `Route` handlers returning
  config-derived `JSONResponse` documents. Do NOT depend on the SDK `create_auth_routes()`
  output for Phase 66 — the SDK AS provider (which `create_auth_routes()` wires) lands in
  Phase 67. PRM/OASM are static-shaped documents that must be live now.
- **Mount-order is the critical contract:** add the well-known routes to the Starlette
  `routes` list BEFORE the app is wrapped with any auth middleware. They live in `http.py`
  alongside the existing `Route(/healthz)` + `Mount(/mcp)`. Reversing the order deadlocks
  the OAuth dance (design doc Risk 3). An automated test MUST assert the well-known routes
  return 200 with NO Authorization header — and the test must be written so it still passes
  once `RequireAuthMiddleware` is added in Phase 67 (i.e. it proves the routes are mounted
  outside the future middleware scope).
- **Serve the RFC 9728 path-suffixed PRM variant too:** both
  `/.well-known/oauth-protected-resource` AND `/.well-known/oauth-protected-resource/mcp`
  return the same document (SDK clients probe the resource-path-inserted form per RFC 9728).

### PRM / OASM document content sourcing
- **PRM (RFC 9728) fields:**
  - `resource` ← `AGENT_BRAIN_OAUTH_RESOURCE` (canonical MCP server URI; design doc
    "Canonical Resource URI Contract").
  - `authorization_servers` ← `[AGENT_BRAIN_OAUTH_ISSUER]`, falling back to the co-located
    server's own base URL (single-binary AS+RS shape).
  - `scopes_supported` ← the 4 locked scopes: `agent-brain:read`, `agent-brain:index`,
    `agent-brain:admin`, `agent-brain:subscribe`.
- **OASM (RFC 8414) fields:**
  - `issuer` / `authorization_endpoint` / `token_endpoint` / `registration_endpoint` /
    `jwks_uri` ← derived from the issuer/server base URL — these are **forward-references**
    to routes Phase 67 adds. The OASM document is spec-valid even though those routes do not
    resolve yet in Phase 66; document this forward-reference explicitly in code comments.
  - `code_challenge_methods_supported` ← `["S256"]` — hardcoded-from-spec (absence makes
    compliant MCP SDK clients abort; ROADMAP SC#2). PKCE S256 is non-negotiable.
  - `grant_types_supported` ← `["authorization_code", "refresh_token"]`;
    `response_types_supported` ← `["code"]` (OAuth 2.1 + PKCE shape from the design doc).
- **No hard-coding the canonical URI** — every value derives from env/config at request time
  (design doc "Anti-Patterns to Avoid": trailing-slash consistency, scheme required,
  no empty `AGENT_BRAIN_OAUTH_RESOURCE`).

### Auth-mode toggle config + startup gate
- **Read `AGENT_BRAIN_AUTH` in the MCP package config** (`agent-brain-mcp/.../config.py`) as
  a new typed setting (an `AuthMode` enum over `{none, basic, oauth}`, default `none`).
- **Validate at the `build_asgi_app()` startup gate:** if the value is not one of the three
  modes → log a critical error and exit with code 2 (design doc "AGENT_BRAIN_AUTH Toggle").
- **Mutual exclusion is structural:** dependency injection wires exactly ONE auth path via a
  single selector (e.g. `get_auth_dependency()`) keyed on the toggle — a request can never
  be validated by more than one auth layer. (Phase 66 wires the *selector + validation*;
  the actual `oauth` middleware it selects arrives in Phase 67.)
- **`oauth`-mode resource gate (Phase 66 contract):** when `AGENT_BRAIN_AUTH=oauth`, the
  startup gate MUST also verify `AGENT_BRAIN_OAUTH_RESOURCE` is set, non-empty, and a
  syntactically valid URI with a scheme — else refuse to start (exit 2). Prevents the
  `aud == ""` audience-omission attack (design doc Risk 2 / "Startup Gate" section).
  `none` and `basic` modes do NOT require `AGENT_BRAIN_OAUTH_RESOURCE`.
- **Reuse the SECURITY-01 startup-gate pattern** from the server package
  (`agent-brain-server/.../api/security.py` + `tests/unit/api/test_startup_gate.py`) as the
  precedent for "validate-at-boot, exit-on-misconfig, clear log message" — mirror its shape,
  do not import across packages.

### `basic` mode semantics (OAUTH-09)
- Phase 66 **formalizes `basic` as the named, validated toggle value** for the existing
  v10.2.1 SECURITY-01 shared-secret Bearer / `AGENT_BRAIN_API_KEY` path — a naming + toggle
  change, NOT new request-path behavior.
- The **MCP→REST leg ALWAYS uses `AGENT_BRAIN_API_KEY` via `X-API-Key` in all three modes**
  (`none`/`basic`/`oauth`). The toggle controls the MCP-client→MCP-server boundary only;
  no mode changes the outbound credential on the REST leg (design doc "Termination
  Contract", OAUTH-08). Phase 66 must not regress this invariant.
- The request-path proof that a JWT fails the basic check and an API key passes it is
  **Phase 67's test** (ROADMAP Phase 67 SC#5) — not Phase 66.

### Claude's Discretion
- Exact module layout for the new well-known route handlers (a new `oauth/` package in the
  MCP module vs functions in `http.py`) — researcher/planner to choose per existing
  conventions.
- Exact `AuthMode` representation (`StrEnum` vs `Literal` + validator) and where the
  `get_auth_dependency()` selector seam lives.
- Whether PRM/OASM JSON is built inline or via small typed builder helpers (Pydantic models
  vs dicts) — either is acceptable provided the output is RFC-valid and config-derived.
- Log message wording and exact exit-code-2 plumbing, matching repo conventions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing Phase 66.**

### Governing design doc (READ FIRST — approved, human-signed-off 2026-06-14)
- `docs/plans/2026-06-14-mcp-v4-oauth-design.md` — THE contract for Phases 66-70. Phase-66
  relevant sections:
  - §"AS / RS / Public-Route Boundary" (Architecture Diagram, **Mount-Order Constraint —
    Critical**, PKCE S256-Only rejection note, `/mcp/subscriptions` auth-exemption audit).
  - §"Canonical Resource URI Contract" (`AGENT_BRAIN_OAUTH_RESOURCE`, RFC 8707 rules, format
    rules, **Startup Gate: must be non-empty in oauth mode**, anti-patterns).
  - §"Auth-Mode Toggle and Deployment Shapes" (`AGENT_BRAIN_AUTH` table, startup gate,
    `basic` mode details, Deployment Shape A co-located AS+RS).
  - §"Token Termination Data Flow" (the X-API-Key invariant that applies in all 3 modes).
  - §"Scope-to-Tool Mapping" (the 4 scopes that populate `scopes_supported` in PRM).

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — **OAUTH-02** (PRM + path-suffixed variant, unauth 200),
  **OAUTH-03** (OASM, `code_challenge_methods_supported: ["S256"]`), **OAUTH-09** (`basic`
  toggle, mutual exclusion). Read OAUTH-04/05/08 for the forward-references the OASM
  document advertises.
- `.planning/ROADMAP.md` — Phase 66 goal + 4 success criteria (the acceptance gate);
  Phase 67 SC#5 (the basic-vs-oauth request-path test that is explicitly NOT in Phase 66).
- `.planning/phases/65-oauth-design-doc-security-review-gate/65-CONTEXT.md` — locked
  standards stack, scope design, library choices, and the framing "wire + configure + mint,
  not build-from-scratch".

### Prior auth implementation to formalize / preserve (SECURITY-01)
- `docs/plans/2026-06-05-issue-179-api-key-auth.md` — the SECURITY-01 static Bearer /
  `AGENT_BRAIN_API_KEY` design that `basic` mode formalizes and the REST leg preserves.
- `agent-brain-server/agent_brain_server/api/security.py` — `verify_bearer_token` +
  startup-gate pattern to mirror (validate-at-boot, exit-on-misconfig, RFC 6750
  `WWW-Authenticate`).
- `agent-brain-server/tests/unit/api/test_startup_gate.py` — the behavioral contract the
  new MCP-side startup gate should echo (exit when misconfigured, silent when valid).

### Specs (re-verify field requirements at authoring time via context7/WebFetch)
- **RFC 9728** Protected Resource Metadata — PRM document shape (`resource`,
  `authorization_servers`, `scopes_supported`) + the `/.well-known/oauth-protected-resource`
  path-suffix rule.
- **RFC 8414** Authorization Server Metadata — OASM document shape; required vs optional
  fields; `code_challenge_methods_supported`.
- **RFC 8707** Resource Indicators — the `resource`/`aud` binding the canonical URI feeds.
- **MCP Authorization 2025-11-25** (baseline) — the auth profile; check 2026-07-28 RC status
  for any well-known/discovery changes before finalizing.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agent-brain-mcp/agent_brain_mcp/http.py :: build_asgi_app()` — the Starlette app to extend.
  Today it mounts only `Route(HEALTHZ_PATH, healthz, GET)` + `Mount("/mcp", mcp_asgi_app)`
  in a single `Starlette(routes=[...], lifespan=...)` call. The new well-known routes are
  added to this `routes` list (BEFORE any future middleware wrap) and the startup gate slots
  into the top of this function.
- `agent-brain-mcp/agent_brain_mcp/config.py` — existing env-driven config layer. Already
  resolves `AGENT_BRAIN_MCP_API_KEY` / `AGENT_BRAIN_API_KEY`, `AGENT_BRAIN_STATE_DIR`,
  backend URL/UDS, and a Pydantic `MCPSubscriptionSettings` model — the home for the new
  `AGENT_BRAIN_AUTH` (AuthMode) + `AGENT_BRAIN_OAUTH_RESOURCE` / `AGENT_BRAIN_OAUTH_ISSUER`
  settings, following the same `os.environ.get` + validation idiom.
- `agent-brain-server/.../api/security.py` + `tests/unit/api/test_startup_gate.py` — the
  SECURITY-01 startup-gate precedent (pattern to mirror, not import).
- `mcp >= 1.27.2` SDK OAuth machinery (`create_auth_routes`, `RequireAuthMiddleware`,
  `BearerAuthBackend`) — available but DEFERRED to Phase 67; Phase 66 hand-rolls the two
  static discovery routes instead.

### Established Patterns
- Routes are declared as a flat `routes=[...]` list passed to `Starlette(...)` in `http.py`
  — extend this list; keep well-known routes ABOVE the `/mcp` mount for clarity.
- Config is env-var-first with typed Pydantic models for structured settings
  (`MCPSubscriptionSettings`) and helper resolver functions — match this for `AuthMode`.
- Loopback/no-auth trust model today (`loopback_transport_security()`); Phase 66 keeps
  `none` as default so default behavior is unchanged.

### Integration Points
- Phase 66's well-known routes + startup gate are the foundation Phase 67 builds on: 67 adds
  the `/authorize` `/token` `/register` `/.well-known/jwks.json` routes (the OASM
  forward-references resolve then) and wraps `/mcp` in `RequireAuthMiddleware`.
- The OASM `scopes_supported` list must stay consistent with `_tool_matrix.py` scope
  assignments (Phase 68) — same 4 scopes, single conceptual source of truth.

### ⚠ Research flag — `/mcp/subscriptions` endpoint not found in http.py
- The design doc and Phase 64 (HOUSE-01 / 64-04-PLAN.md) reference a `GET /mcp/subscriptions`
  debug endpoint, and the design doc assigns Phase 66 an action: "audit `/mcp/subscriptions`
  response contents before finalizing its auth-exempt status." **A scout of `http.py` found
  only `/healthz` and `/mcp` mounted — no `/mcp/subscriptions` Route.** Downstream researcher
  MUST confirm whether the subscriptions debug endpoint actually shipped (and where it is
  mounted) before treating its auth-exemption audit as actionable. If it never shipped, the
  audit item is moot for Phase 66 and should be noted as such, not silently dropped.

</code_context>

<specifics>
## Specific Ideas

- "Discovery-first, enforcement-later" — Phase 66 proves the unauthenticated discovery root
  works in isolation (the `curl` with no token → 200 acceptance test) so that when Phase 67
  wires `RequireAuthMiddleware`, the well-known routes are demonstrably already outside its
  scope. Write the mount-outside-middleware test in Phase 66 so it survives Phase 67 verbatim.
- The dominant Phase-66 failure mode is a **mount-order regression** (discovery behind auth =
  Risk 3 deadlock) and an **`aud`-omission misconfig** (empty `AGENT_BRAIN_OAUTH_RESOURCE` in
  oauth mode = Risk 2). Both get explicit boot-time gates + tests in this phase.
- Frame the work honestly as "serve two JSON documents + validate one env toggle" — it is
  small, but the correctness bar (RFC-valid fields, exact S256 advertisement, mount order) is
  high because compliant SDK clients abort silently on a malformed discovery document.

</specifics>

<deferred>
## Deferred Ideas

- `/authorize`, `/token`, `/register`, `/.well-known/jwks.json` route handlers + JWT minting —
  Phase 67 (OAUTH-04).
- `RequireAuthMiddleware` request-path enforcement + the basic-vs-oauth mutual-exclusion
  request test — Phase 67 (OAUTH-05, ROADMAP Phase 67 SC#5).
- `/mcp/subscriptions` auth-exemption audit — contingent on confirming the endpoint exists
  (see Research flag); if it ships, the audit lands here or in Phase 67, not before it's real.
- Per-tool scope enforcement / `_tool_matrix.py` scope map — Phase 68 (OAUTH-06).
- DPoP (RFC 9449) — deferred to v10.5+ (recorded in design doc, not built).

</deferred>

---

*Phase: 66-oauth-settings-foundation-prm-oasm-public-endpoints*
*Context gathered: 2026-06-14*
