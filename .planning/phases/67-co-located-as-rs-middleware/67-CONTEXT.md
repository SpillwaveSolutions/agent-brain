# Phase 67: Co-Located AS + RS Middleware - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning

> Captured in `--auto` mode. Phase 67's decisions are almost entirely pre-locked by the
> APPROVED OAuth design doc (`docs/plans/2026-06-14-mcp-v4-oauth-design.md`, human sign-off
> 2026-06-14), REQUIREMENTS.md (OAUTH-04/05/08/10), the ROADMAP Phase-67 success criteria,
> and the seams Phase 66 already cut (`get_auth_dependency()` oauth-branch placeholder,
> `check_auth_startup_gate()`, auth-exempt well-known routes). CONTEXT here transcribes those
> locks, resolves the Phase-67-specific gray areas (AS implementation strategy, signing-key
> lifecycle, RS middleware wiring, SSRF controls), names the dependency bump the design doc
> mandates, and lists the canonical refs downstream agents MUST read. No genuinely open
> human-decision items remain — the design-doc security gate cleared in Phase 65.

<domain>
## Phase Boundary

Make **token issuance and verification work end-to-end in a single binary** (Deployment
Shape A: co-located AS + RS). An OAuth 2.1 client completes the authorization-code + PKCE
S256 dance against the co-located Authorization Server, receives a signed JWT, and the
Resource Server validates that JWT on every subsequent `/mcp` call.

Phase 67 delivers exactly four requirements (OAUTH-04, OAUTH-05, OAUTH-08, OAUTH-10):

1. **OAUTH-04 — Authorization Server.** `GET /authorize` issues a code (PKCE S256-only;
   rejects `plain`/absent challenge); `POST /token` exchanges it for a signed JWT access
   token + rotating refresh token; a custom `GET /.well-known/jwks.json` route exposes the
   RS256 public key (SDK gap). Wired through the SDK `OAuthAuthorizationServerProvider` +
   `create_auth_routes()`; JWTs minted with `PyJWT[crypto]`.
2. **OAUTH-05 — Resource Server.** `RequireAuthMiddleware` returns 401 +
   `WWW-Authenticate` on `/mcp` requests with no/expired/invalid-signature token; a valid
   token passes through to MCP tool dispatch. Gated by `AGENT_BRAIN_AUTH=oauth` (default
   `none`); well-known + `/authorize` + `/token` + `/register` routes stay auth-exempt.
3. **OAUTH-08 — Resource Indicators (RFC 8707).** Client sends `resource` in BOTH the
   authorization and token requests; the AS binds `aud` to the canonical resource URI; the
   RS validates `aud` on every inbound token; the MCP server NEVER forwards the client's
   OAuth token upstream to the REST backend (confused-deputy prevention — REST leg always
   `X-API-Key`).
4. **OAUTH-10 — Client registration.** CIMD (Client ID Metadata Document) + static
   pre-registration both work; the AS fetches the `client_id` URL on CIMD registration with
   SSRF protection (domain allowlist + private-IP block + DNS-rebinding post-resolution IP
   re-validation). DCR (RFC 7591) is optional/omitted for the single-user shape.

**ROADMAP Phase-67 success criteria (the acceptance gate):**
1. Full auth-code + PKCE S256 flow against the co-located AS; `plain`/absent challenge
   rejected with an error.
2. `RequireAuthMiddleware` → 401 + `WWW-Authenticate` on missing/invalid token; valid token
   passes through.
3. Every issued JWT has `aud` == `AGENT_BRAIN_OAUTH_RESOURCE`; RS rejects mismatched `aud`.
4. CIMD + static registration both work; CIMD fetch has SSRF protection (domain allowlist).
5. `AGENT_BRAIN_AUTH=oauth` and `=basic` are mutually exclusive on the request path — an
   automated test proves a valid JWT fails the static-bearer check and a raw API key passes
   it, never crossing modes.

**Explicitly OUT of scope for Phase 67** (belongs to Phases 68-70):
- Per-tool scope enforcement / `_tool_matrix.py` scope map / `require_scope()` guard — Phase 68
  (OAUTH-06). Token-validation check #6 (scope) is a Phase-68 concern; Phase 67 validates
  checks #1-5 (presence, signature, exp, iss, aud).
- `McpHttpBackend` client-side OAuth dance / `FileTokenStorage` chmod 0o600 — Phase 69 (OAUTH-07).
- Split AS/RS topology, JWKS-cached verification against Keycloak, token introspection
  (RFC 7662) / revocation (RFC 7009), ≥90% coverage gate — Phase 70 (OAUTH-11/12).
- DPoP (RFC 9449) — deferred to v10.5+.

</domain>

<decisions>
## Implementation Decisions

### AS implementation strategy (OAUTH-04) — wire + configure + mint
- **Implement the SDK `OAuthAuthorizationServerProvider`** (its 9 abstract methods) and wire
  it through **`create_auth_routes()`**, which produces `/authorize`, `/token`, `/register`,
  and `/.well-known/oauth-authorization-server`. Do NOT build OAuth grant flow from scratch.
- **Mint JWTs with `PyJWT[crypto]`, RS256.** Access-token `exp` = **15 minutes**; refresh
  tokens are **rotating, 30-day** validity (design doc "Token lifecycle"). All MCP clients
  are public clients → PKCE S256 mandatory.
- **Use `authlib ^1.7.2` for grant-handler logic** where it composes cleanly with the SDK
  provider; `pwdlib[argon2]` for any co-located AS user/secret hashing. (No DPoP in authlib
  — matches the deferral.)
- **Token store: IN-MEMORY** (design Shape A lock). Access tokens, refresh tokens, and
  authorization codes live in process memory; **a restart invalidates all sessions** — a
  known, documented trade-off (note it in operator docs, do not try to persist in Phase 67).

### Signing-key lifecycle
- **Generate the RS256 keypair at server startup** (private key held in memory), consistent
  with the in-memory token store (sessions already die on restart, so an ephemeral signing
  key introduces no *additional* session loss).
- The **JWKS document is derived from the in-memory public key at request time** — it stays
  stable for the lifetime of the process.
- **Claude's discretion / deferrable:** an optional configured PEM key path
  (`AGENT_BRAIN_OAUTH_SIGNING_KEY`) for a stable JWKS across restarts. Not required for
  Phase 67 acceptance; planner may add it if low-cost, otherwise defer.

### JWKS endpoint (SDK gap)
- **Hand-roll a custom public route `GET /.well-known/jwks.json`** that serializes the RS256
  public key as a JWKS JSON document (the `mcp` SDK does NOT ship one — documented gap).
- **Mount it auth-exempt, in the `http.py` `routes=[...]` list, BEFORE the
  `RequireAuthMiddleware` wrap** — exactly the Phase 66 mount-order contract. It joins the
  existing `/.well-known/oauth-protected-resource`, `/.well-known/oauth-authorization-server`,
  and `/healthz` auth-exempt routes. The OASM `jwks_uri` forward-reference Phase 66 wrote now
  resolves.

### RS verification middleware (OAUTH-05)
- **Replace the `get_auth_dependency()` oauth-branch placeholder** (currently
  `raise NotImplementedError("...RequireAuthMiddleware arrives in Phase 67")`) with the SDK
  **`RequireAuthMiddleware` + `BearerAuthBackend`**, wrapping **only the `/mcp` mount**.
- **Token validation order on `/mcp` (checks #1-5 in Phase 67; #6 scope is Phase 68):**
  1. Bearer token present → else 401.
  2. Signature valid (RS256, verified against the in-memory public key / local JWKS).
  3. `exp` not expired (with clock-skew leeway, e.g. `leeway=30s`); `nbf` honored.
  4. `iss` == configured issuer (`AGENT_BRAIN_OAUTH_ISSUER` or co-located AS base URL).
  5. `aud` == `AGENT_BRAIN_OAUTH_RESOURCE` (RFC 8707) → mismatch rejected.
  - Failure at #1-5 → **401 + `WWW-Authenticate: Bearer resource_metadata="..."`**.
- **Mutual exclusion stays structural** — the single selector returns exactly one auth path;
  a request can never be validated by both the basic and oauth layers (Phase 66 invariant
  preserved). Phase 67 fills the oauth branch; the basic branch is unchanged.

### PKCE S256-only rejection gate (ROADMAP SC#1)
- **Advertisement is insufficient — actively REJECT** non-compliant `/authorize` requests:
  - `code_challenge_method=plain` → HTTP 400 `error=invalid_request`,
    `error_description="PKCE plain method not supported"`.
  - `code_challenge` present but `code_challenge_method` absent → reject.
  - `code_challenge` entirely absent → reject (PKCE mandatory for all public clients).
- This is a **contract test**, not just an OASM advertisement check (a malicious client may
  ignore the advertisement).

### Resource Indicators / `aud` binding + token termination (OAUTH-08)
- Client sends `resource` in **both** `/authorize` and `POST /token`; the AS binds `aud` to
  that value; the RS validates `aud` == `AGENT_BRAIN_OAUTH_RESOURCE` on every token.
- **The OAuth token terminates at the MCP boundary and is NEVER forwarded.** The MCP→REST
  leg ALWAYS uses `AGENT_BRAIN_API_KEY` via `X-API-Key`, in all three modes
  (`none`/`basic`/`oauth`). Phase 67 must not regress this invariant. (The full
  three-mode confused-deputy integration assertion is Phase 70's test; Phase 67 must not
  introduce any code path that forwards the OAuth token upstream.)

### Client registration + SSRF mitigation (OAUTH-10)
- **CIMD + static pre-registration** both supported. **DCR (RFC 7591) omitted** for the
  single-user self-hosted shape (it is `MAY`/deprecated in the 2025-11-25 spec).
- **CIMD fetch SSRF controls (mandatory):**
  1. Parse the `client_id` URL, extract hostname.
  2. Validate hostname against `AGENT_BRAIN_OAUTH_CLIENT_ID_ALLOWLIST` (trusted domains/CIDRs)
     → reject with HTTP 400 if not allowlisted.
  3. **Unconditionally block private/loopback/link-local ranges** (`10.x`, `172.16-31.x`,
     `192.168.x`, `127.x`, `169.254.x`, `::1`) regardless of the allowlist.
  4. **DNS-rebinding mitigation (mandatory):** after DNS resolution and immediately before
     the HTTP fetch, re-validate the resolved IP is not private/loopback/link-local (custom
     `httpx` transport or equivalent). **A test MUST assert a `client_id` whose DNS resolves
     to an RFC-1918 address is rejected even when the hostname passes the allowlist.**
  5. Short HTTP timeout (~5s) on the fetch (slowloris/DoS guard).

### Mode mutual-exclusion proof (ROADMAP SC#5)
- **Automated test:** a valid JWT fails the `basic` static-bearer check, and a raw
  `AGENT_BRAIN_API_KEY` passes the `basic` check — proving the two modes never cross on the
  request path.

### Dependency additions (record + install THIS phase)
- **Bump the MCP SDK:** current pin is `mcp = "^1.12.0"`; the OAuth machinery
  (`OAuthAuthorizationServerProvider`, `create_auth_routes()`, `RequireAuthMiddleware`,
  `BearerAuthBackend`) requires **`mcp >= 1.27.2`** → bump to `^1.27.2`. **This is the
  single biggest integration risk in the phase — verify no breaking SDK API changes between
  1.12 and 1.27 across `server.py`, `http.py`, `client.py`, and the subscriptions module.**
- **Add:** `PyJWT[crypto] ^2.13`, `authlib ^1.7.2`, `pwdlib[argon2] >=0.2`. **Verify**
  whether `itsdangerous ^2.2` (CSRF state-token signing) is already a Starlette transitive
  dep before adding it explicitly.
- **Do NOT use:** `python-jose` (abandoned), `passlib` (unmaintained), `fastapi-users`.

### Claude's Discretion
- Module layout for the new AS code — a new `agent-brain-mcp/agent_brain_mcp/oauth/` package
  (provider, token minting, JWKS, registration/SSRF) vs extending existing modules; follow
  repo conventions. (Phase 70 expects "middleware stack abstracted for verifier swap" — keep
  the verifier seam clean.)
- Exact `OAuthAuthorizationServerProvider` method bodies and in-memory store representation.
- Optional configured PEM signing-key path (see Signing-key lifecycle).
- Whether to ship a thin DCR-as-CIMD-fallback or omit `/register` DCR entirely (design doc
  permits either; default omit).
- Log wording, exit-code plumbing, and where the `AGENT_BRAIN_OAUTH_CLIENT_ID_ALLOWLIST`
  config setting lands (mirror Phase 66's `resolve_oauth_settings()` idiom).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing Phase 67.**

### Governing design doc (READ FIRST — approved, human-signed-off 2026-06-14)
- `docs/plans/2026-06-14-mcp-v4-oauth-design.md` — THE contract for Phases 66-70.
  Phase-67-relevant sections:
  - §"Framing: Wire + Configure + Mint" / "What the MCP SDK Already Provides" — the SDK
    primitives to wire (`OAuthAuthorizationServerProvider`, `create_auth_routes()`,
    `RequireAuthMiddleware`, `BearerAuthBackend`).
  - §"Library Additions to Record" — the dependency table (`PyJWT[crypto]`, `authlib`,
    `pwdlib[argon2]`, `itsdangerous`) + the `mcp >= 1.27.2` requirement + do-not-use list.
  - §"AS / RS / Public-Route Boundary" → "Mount-Order Constraint (Critical)",
    "SDK Gap: No Built-In JWKS Endpoint", "PKCE S256-Only: Advertisement Is Insufficient —
    Rejection Required", "Token Validation on /mcp" (the 6-check order).
  - §"Token Termination Data Flow" → "Termination Contract (OAUTH-08)", sequence diagram,
    "Why Two Independent Layers" (X-API-Key invariant; OAuth token never forwarded).
  - §"Canonical Resource URI Contract" → RFC 8707 rules, format rules, startup gate,
    anti-patterns (trailing-slash, no-scheme, empty env).
  - §"Registration Policy: CIMD over DCR" → CIMD flow + "SSRF Mitigation (Mandatory)"
    (allowlist, private-IP block, DNS-rebinding post-resolution check, 5s timeout).
  - §"Deployment Shape A: Co-Located AS + RS" → in-memory token store, RS256 in-memory
    signing key, JWKS gap, no introspection, token lifecycle (15min access / 30d rotating).
  - §"Threat Model" Risks 1-3 (confused-deputy, aud-omission, well-known-behind-auth) +
    "Security Review Sign-Off" adversarial findings.

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — **OAUTH-04** (AS: auth-code+PKCE S256, PyJWT JWTs, JWKS, via
  `OAuthAuthorizationServerProvider`), **OAUTH-05** (RS verify sig/exp/nbf/aud, gated by
  `AGENT_BRAIN_AUTH=oauth`, well-known+authorize/token auth-exempt), **OAUTH-08** (RFC 8707
  resource indicators, no upstream token forwarding), **OAUTH-10** (CIMD + static; DCR
  optional, rate-limited + domain-allowlisted with SSRF protection).
- `.planning/ROADMAP.md` — Phase 67 goal + 5 success criteria (the acceptance gate); note
  Phase 68/69/70 dependencies on this phase (scope enforcement, client dance, split AS/RS).

### Prior phase context (locked decisions to carry forward)
- `.planning/phases/66-oauth-settings-foundation-prm-oasm-public-endpoints/66-CONTEXT.md` —
  the mount-order contract, the `AuthMode` toggle + startup gate, PRM/OASM document sourcing,
  the `basic`-mode formalization, and the `get_auth_dependency()` selector seam Phase 67 fills.
- `.planning/phases/65-oauth-design-doc-security-review-gate/65-CONTEXT.md` — locked standards
  stack, scope design (the 4 scopes), library choices, CIMD-over-DCR, DPoP deferral, the
  "wire + configure + mint" framing.

### Prior auth implementation to preserve (SECURITY-01 / `basic` mode + REST leg)
- `docs/plans/2026-06-05-issue-179-api-key-auth.md` — the static Bearer / `AGENT_BRAIN_API_KEY`
  design; `basic` mode formalizes it and the MCP→REST leg preserves it (X-API-Key invariant).
- `agent-brain-server/agent_brain_server/api/security.py` — `verify_bearer_token` + RFC 6750
  `WWW-Authenticate` pattern to mirror (do not import across packages).

### Specs (re-verify field/level requirements at authoring time via context7/WebFetch)
- **MCP Authorization 2025-11-25** (authoritative baseline) — the auth profile; check the
  2026-07-28 RC status for any `/authorize` `/token` `/register` changes before finalizing.
- **OAuth 2.1** (draft-ietf-oauth-v2-1) — PKCE-mandatory-for-public-clients, refresh-token
  rotation.
- **RFC 7636** PKCE — S256 code challenge/verifier semantics (the rejection gate).
- **RFC 8707** Resource Indicators — `resource` parameter + `aud` binding rules.
- **RFC 8414** Authorization Server Metadata — OASM fields `create_auth_routes()` emits
  (consistency with Phase 66's hand-rolled OASM).
- **RFC 9728** Protected Resource Metadata — the PRM `resource_metadata` value referenced in
  401 `WWW-Authenticate`.
- **RFC 7591** Dynamic Client Registration — DCR shape (optional/omitted; reference only).
- **RFC 6750** Bearer Token Usage — `WWW-Authenticate` 401 format.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agent-brain-mcp/agent_brain_mcp/config.py` — Phase 66 added `AuthMode` enum,
  `resolve_auth_mode()`, `resolve_oauth_settings()` (reads `AGENT_BRAIN_OAUTH_RESOURCE` /
  `AGENT_BRAIN_OAUTH_ISSUER`), `check_auth_startup_gate()` (exits code 2 on misconfig), and
  **`get_auth_dependency()` whose `oauth` branch is the exact placeholder Phase 67 replaces**
  (`raise NotImplementedError("...RequireAuthMiddleware arrives in Phase 67")`). Add the new
  `AGENT_BRAIN_OAUTH_CLIENT_ID_ALLOWLIST` (+ optional signing-key) settings here, same idiom.
- `agent-brain-mcp/agent_brain_mcp/http.py :: build_asgi_app()` — the Starlette app to extend.
  Already calls `check_auth_startup_gate()` at the top and mounts the auth-exempt well-known
  routes (`PRM_PATH`, `PRM_PATH_SUFFIXED`, `OASM_PATH`, `HEALTHZ_PATH`) BEFORE the `/mcp`
  Mount in a single `routes=[...]` list. Phase 67 adds `/.well-known/jwks.json` + the
  `create_auth_routes()` set to this list (auth-exempt), then wraps the `/mcp` mount with
  `RequireAuthMiddleware` when `AGENT_BRAIN_AUTH=oauth`. **Mount order is the critical
  contract** — well-known/AS routes precede the middleware wrap (Phase 66 comment block at
  http.py:289 spells this out).
- `agent-brain-mcp/agent_brain_mcp/oauth_metadata.py` — Phase 66 PRM/OASM document builders;
  the OASM `jwks_uri` / `authorization_endpoint` / `token_endpoint` / `registration_endpoint`
  forward-references resolve once Phase 67 adds those routes. Keep field values consistent.
- `mcp` SDK `mcp.server.auth` (after the bump to ≥1.27.2) — `OAuthAuthorizationServerProvider`,
  `create_auth_routes()`, `RequireAuthMiddleware`, `BearerAuthBackend` (no longer deferred).
- `agent-brain-server/.../api/security.py` + `tests/unit/api/test_startup_gate.py` — the
  SECURITY-01 Bearer / startup-gate precedent (pattern to mirror, not import).

### Established Patterns
- Routes are a flat `routes=[...]` list passed to `Starlette(...)` in `http.py`; auth-exempt
  routes stay ABOVE the `/mcp` mount and outside any middleware wrap.
- Config is env-var-first (`os.environ.get`) with typed resolvers and Pydantic models for
  structured settings; the startup gate validates-at-boot and `sys.exit(2)` on misconfig.
- Loopback/no-auth default (`AuthMode.none`) — Phase 67 keeps default behavior unchanged;
  OAuth only engages when `AGENT_BRAIN_AUTH=oauth` and the resource URI gate passes.

### Integration Points
- Phase 67 fills the `get_auth_dependency()` oauth branch and the `build_asgi_app()`
  middleware wrap — the seams Phase 66 cut.
- **Phase 68** plugs `require_scope()` (token-validation check #6) into the dispatch layer on
  top of the Phase 67 `BearerAuthBackend` claims (`request.state.auth`); keep the scope hook
  reachable. Scope list must match the 4 scopes the OASM/PRM already advertise.
- **Phase 69** dances against this AS via `OAuthClientProvider` from `McpHttpBackend`.
- **Phase 70** swaps the local verifier for a `JwksTokenVerifier` (split AS/RS) — keep the
  token-verifier abstraction clean so the swap is a config change, not a rewrite.

</code_context>

<specifics>
## Specific Ideas

- "Fill the seam, don't rebuild" — Phase 67 is a fill-in against Phase 66's typed
  placeholders and the SDK's existing OAuth machinery. The honest framing is "implement one
  SDK provider + mint JWTs + hand-roll one JWKS route + wrap one mount with one middleware,"
  not "build an OAuth server."
- The two dominant Phase-67 risks are (1) the **`mcp` SDK version bump 1.12→1.27.2** silently
  breaking an existing API (`server.py` / subscriptions / `http.py`), and (2) an **SSRF hole
  in CIMD fetch** (allowlist-only without DNS-rebinding post-resolution IP re-validation).
  Both get explicit research + dedicated tests.
- Keep the **mount-order test from Phase 66 green** — it was written to survive the Phase 67
  middleware wrap verbatim (well-known routes return 200 with no token even after
  `RequireAuthMiddleware` is added).
- The **confused-deputy invariant** (OAuth token terminates at `/mcp`, X-API-Key on the REST
  leg) must hold in all three modes; Phase 67 must add no code path that forwards the OAuth
  token upstream.

</specifics>

<deferred>
## Deferred Ideas

- Per-tool scope enforcement / `require_scope()` guard / `_tool_matrix.py` scope map —
  Phase 68 (OAUTH-06). Token-validation check #6.
- `McpHttpBackend` client-side OAuth dance + `FileTokenStorage` chmod 0o600 — Phase 69 (OAUTH-07).
- Split AS/RS topology, `JwksTokenVerifier` (PyJWKClient 5-min TTL + kid-miss refresh),
  Keycloak-in-CI, token introspection (RFC 7662) + revocation (RFC 7009), ≥90% coverage
  gate — Phase 70 (OAUTH-11/12).
- DPoP (RFC 9449) — deferred to v10.5+ (no production-grade Python lib; optional in
  2025-11-25 core spec).
- Persistent token store / persistent signing key for session survival across restarts —
  consciously NOT in Phase 67 (in-memory is the design Shape A lock); optional PEM signing-key
  path is Claude's discretion if low-cost.
- Audit-log middleware — own milestone (design doc Deferred Items).

</deferred>

---

*Phase: 67-co-located-as-rs-middleware*
*Context gathered: 2026-06-14*
