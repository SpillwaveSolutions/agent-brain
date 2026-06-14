# Pitfalls Research: v10.4 — OAuth 2.1 for MCP Resource Server

**Domain:** OAuth 2.1 authorization on an MCP Streamable HTTP server (FastAPI/Python, co-located AS/RS + split AS/RS shapes)
**Researched:** 2026-06-14
**Confidence:** MEDIUM-HIGH (spec sections: HIGH from current MCP spec; ecosystem patterns: MEDIUM from multiple corroborating sources; DPoP/Python library support: MEDIUM — library-level DPoP is still maturing)

---

## CRITICAL META-WARNING: The MCP Authorization Spec Has Changed Materially — Your Training Data Is Almost Certainly Stale

This is the most important pitfall in this document. The MCP authorization specification has gone through at least four substantively different revisions since its introduction:

| Spec Version | Key Authorization Change |
|---|---|
| 2024-11-05 | No standardized authorization model at all |
| 2025-03-26 | OAuth 2.1 introduced; Dynamic Client Registration (DCR) was SHOULD (near-mandatory); no PRM |
| 2025-06-18 | Protected Resource Metadata (RFC 9728) introduced; fallback default endpoints removed; Resource Indicators required |
| 2025-11-25 | DCR demoted to deprecated/backwards-compat; Client ID Metadata Documents (CIMD) is now the primary registration mechanism; OIDC Discovery added; incremental consent |
| 2026-07-28 RC | Auth hardening: issuer validation required; stricter application-type classification; MCP goes stateless (no initialize handshake); biggest revision since launch |

**What to re-verify before writing a single line of auth code:**

1. The current spec lives at `https://modelcontextprotocol.io/specification/draft/basic/authorization` — fetch it fresh. The `draft` URL moves. The 2026-07-28 RC may be stable by the time this is implemented.
2. The security considerations sub-page at `.../authorization/security-considerations` contains normative MUSTs that are NOT in the main page.
3. Dynamic Client Registration: if your design doc says "SHOULD support DCR", verify whether that was written against 2025-03-26 (where DCR was prominent) or 2025-11-25+ (where CIMD is preferred and DCR is legacy). The design doc at `docs/roadmaps/mcp/v4-oauth-for-remote.md` cites RFC 7591 (DCR) as a MAY — that aligns with the 2025-11-25 spec. Double-check this holds against whatever the current spec says when implementation begins.
4. `code_challenge_methods_supported`: the current spec requires MCP clients to REFUSE to proceed if this field is absent from AS metadata. If the co-located AS omits it, every compliant MCP client will reject the server. This is a spec detail that changed between versions and is easy to miss.
5. The 2026-07-28 RC makes MCP stateless — no session pinning, no initialize handshake. Any auth middleware that relies on session state from the MCP initialize exchange will break under the RC.

**Confidence in any claim about MCP auth spec behavior that comes from training data (before August 2025) is LOW. Always verify against the live spec before implementing.**

---

## Critical Pitfalls

### Pitfall 1: Missing or Incorrect `aud` Claim Validation (Access Token Privilege Restriction)

**What goes wrong:**
The MCP server accepts tokens that were issued for a different resource — for example, a token meant for `https://api.other-service.com` is presented to the Agent Brain MCP endpoint and accepted because no audience check is performed. Any service that shares the same Authorization Server (co-located shape: impossible, but split AS shape: entirely realistic) can have its tokens replayed against the Agent Brain MCP server.

The MCP spec is explicit: "MCP servers MUST validate access tokens before processing the request, ensuring the access token is issued specifically for the MCP server." (Security Considerations, Token Privilege Restriction section, current spec)

**Why it happens:**
FastAPI JWT middleware examples in tutorials typically validate `exp`, `iss`, and `sub` but omit `aud` entirely because audience validation requires knowing the server's own canonical URI at validation time. Developers copy tutorial boilerplate. This is the #1 category of auth bypass in OAuth resource server implementations.

**How to avoid:**
In the JWT validation middleware, assert `aud` contains the MCP server's canonical URI (same value used as the `resource` parameter per RFC 8707). For the co-located shape, the AS issues tokens with `aud` set to the server's own URI. For the split AS shape, configure the external IdP to include the correct `aud`. Use `python-jose` or `authlib` with explicit `audience=` parameter — never rely on "accept any audience" defaults. Example with authlib:

```python
from authlib.jose import jwt as jose_jwt
claims = jose_jwt.decode(token, key, claims_options={
    "aud": {"essential": True, "value": "https://agent-brain.example.com"},
    "iss": {"essential": True, "value": EXPECTED_ISSUER},
})
claims.validate()
```

**Warning signs:**
- JWT middleware that only checks `exp` and `iss`
- Tests that don't include a token with a wrong audience to verify rejection
- Co-located shape where tokens "just work" because there's only one consumer — split AS shape will silently accept cross-service tokens if `aud` validation is absent

**Phase to address:** Design doc phase (document the canonical URI and make it a required configuration value); AS/RS implementation phase (enforce in middleware); security review phase (audit for missing `aud` assertion)

---

### Pitfall 2: Confused Deputy via Token Passthrough

**What goes wrong:**
The MCP server, when calling the Agent Brain FastAPI backend, forwards the same Bearer token it received from the MCP client. The backend trusts it because the token is valid. This violates a hard MUST in the spec: "If the MCP server makes requests to upstream APIs, it may act as an OAuth client to them. The access token used at the upstream API is a separate token... The MCP server MUST NOT pass through the token it received from the MCP client."

In the Agent Brain architecture: `McpHttpBackend → MCP server → agent-brain-server REST API`. If the MCP layer passes the client's Bearer token to the REST API, the REST API is a confused deputy — it accepts tokens it should never see.

**Why it happens:**
The `AGENT_BRAIN_API_KEY` pattern established in SECURITY-01 (v10.2.1) passes a shared static key from CLI through MCP to the REST server. The temptation is to "upgrade" this by passing the OAuth access token in the same forwarding channel. This is architecturally wrong — the AS/RS split means the MCP server must authenticate to its own backend using its own credentials (service account token, the same `AGENT_BRAIN_API_KEY`, or a machine-to-machine token), not by forwarding client tokens.

**How to avoid:**
Maintain the existing `AGENT_BRAIN_API_KEY` forwarding for the MCP server → REST API leg. The OAuth token is consumed and validated ONLY at the MCP server boundary. The MCP server then uses its own credentials (the pre-existing `AGENT_BRAIN_API_KEY`) to call the REST API. Document this explicitly in the design doc: the OAuth layer sits in front of `agent-brain-mcp`; it never reaches `agent-brain-server` directly.

**Warning signs:**
- Any code that extracts `Authorization: Bearer <token>` from the incoming MCP request and sets the same header on outgoing HTTP calls to `agent-brain-server`
- The `AGENT_BRAIN_API_KEY` being absent from the MCP→server communication path post-OAuth

**Phase to address:** Design doc phase (explicit data-flow diagram showing where OAuth tokens terminate); AS/RS implementation phase; integration test phase (verify the REST API's `verify_api_key` still receives `AGENT_BRAIN_API_KEY`, not an OAuth token)

---

### Pitfall 3: Missing Resource Indicators (RFC 8707) in Both Authorization and Token Requests

**What goes wrong:**
The `resource` parameter is omitted from authorization requests, token requests, or both. Tokens are issued without an `aud` binding to the specific MCP server URI. Any other resource served by the same AS can accept these tokens. The MCP spec is unambiguous: "MCP clients MUST include the `resource` parameter in authorization and token requests" and "MUST identify the MCP server that the client intends to use the token with."

The co-located AS shape is particularly dangerous here: if the AS issues tokens without enforcing `resource` / `aud` binding because "there's only one resource anyway", the moment a second resource is added (even temporarily), cross-resource token misuse becomes possible.

**Why it happens:**
Resource Indicators (RFC 8707) were added to the MCP spec in the 2025-06-18 revision. Earlier tutorials and blog posts don't mention them. The OAuth 2.1 draft itself lists RFC 8707 as a referenced extension but does not mandate it — only the MCP spec mandates it. Developers reading general OAuth 2.1 guides will miss this MCP-specific requirement.

**How to avoid:**
In the co-located AS: require the `resource` parameter at the token endpoint; bind `aud` in issued JWTs to the value of `resource`. Reject token requests lacking `resource`. In `McpHttpBackend`: always include `resource=<canonical-uri>` in both the authorization URL and the token request. In the RS middleware: validate `aud` contains the canonical URI (see Pitfall 1 — these two pitfalls are twins).

Canonical URI for Agent Brain: `https://<host>:<port>` (without trailing slash per spec guidance). Make this a required configuration value (`AGENT_BRAIN_MCP_RESOURCE_URI`).

**Warning signs:**
- AS that issues tokens without `resource` parameter validation
- Authorization URLs built without `&resource=<encoded-uri>`
- Token requests to the AS lacking the `resource` body parameter
- JWTs with no `aud` claim or with `aud: ["*"]`

**Phase to address:** Design doc phase (define canonical URI contract); co-located AS implementation phase; `McpHttpBackend` OAuth dance implementation phase; contract test phase (verify token requests include `resource`)

---

### Pitfall 4: PKCE Downgrade — Accepting `plain` Instead of Requiring `S256`

**What goes wrong:**
The AS accepts `code_challenge_method=plain` from clients or omits `code_challenge_methods_supported` from its metadata. Two consequences: (1) Compliant MCP clients will REFUSE to proceed (the spec says clients MUST refuse if `code_challenge_methods_supported` is absent). (2) Non-compliant clients that use `plain` expose the `code_verifier` in transit — any network observer who captures the authorization response can derive the verifier and redeem the code.

**Why it happens:**
OAuth 2.1 requires PKCE but does not mandate S256-only at the spec level (the draft says SHOULD use S256 for public clients). The MCP spec is stricter: S256 is the only acceptable method. AS implementations that copy from generic OAuth 2.1 tutorials may support `plain` as a fallback for "compatibility."

**How to avoid:**
In the co-located AS: set `code_challenge_methods_supported: ["S256"]` in AS metadata (RFC 8414). Reject any authorization request where `code_challenge_method` is absent or is not `S256`. In `McpHttpBackend`: always generate S256 challenges; never fall back to plain. Use `secrets.token_urlsafe(96)` for the verifier (≥43 chars, cryptographically random), then `base64url(sha256(verifier))` for the challenge.

**Warning signs:**
- AS metadata missing `code_challenge_methods_supported`
- Any code path that accepts `code_challenge_method=plain`
- The string `"plain"` appearing in PKCE-related code
- MCP clients (SDK test clients) refusing to connect — likely the AS metadata is missing PKCE support advertisement

**Phase to address:** Co-located AS implementation phase (first and only code_challenge_method to implement is S256); `McpHttpBackend` phase; contract test phase (verify clients reject servers that advertise only `plain` or omit the field)

---

### Pitfall 5: Co-located AS/RS Responsibility Confusion — Routing, Middleware, and Token Issuance Bleeding Into Each Other

**What goes wrong:**
In the co-located binary, the FastAPI app for `agent-brain-mcp` takes on both AS responsibilities (issuing tokens, handling `/authorize`, `/token`, `/register`, `/.well-known/*`) and RS responsibilities (validating incoming Bearer tokens on MCP endpoints). These concerns get tangled: the same middleware checks for both OAuth session state and Bearer token validation; the auth code flow shares state with the MCP session; JWKS is served from the same router as MCP tools.

Concrete failure modes:
- Auth middleware runs on AS endpoints (like `/token`), causing circular auth failures
- The `/.well-known/oauth-protected-resource` metadata handler accidentally validates the Bearer token on the response path, rejecting unauthenticated discovery requests (discovery MUST be unauthenticated)
- JWTs issued by the AS use the MCP session key as the signing secret, coupling token lifetime to process restart

**Why it happens:**
The co-located shape is operationally convenient but architecturally dual-role. Without explicit separation, auth code naturally intermixes. FastAPI middleware applies globally unless carefully excluded by path.

**How to avoid:**
Organize the FastAPI app into explicit mount points or route groups:
- `/auth/*` — AS endpoints (no auth middleware; these are public AS endpoints)
- `/.well-known/*` — metadata endpoints (no auth middleware; must be publicly accessible per RFC 9728 §3 and RFC 8414 §3)
- `/mcp` — RS endpoint (auth middleware required; validates Bearer tokens and enforces scopes)

Use FastAPI `APIRouter` with distinct middleware stacks, or use path-exclusion in a single middleware (exclude auth on `/auth/` and `/.well-known/` prefixes). Make the JWT signing key independent of the MCP server's API key — use a separate RSA/EC key pair generated on first start and persisted to the state dir alongside `config.json` (similar to how `agent-brain init` auto-generates `AGENT_BRAIN_API_KEY`).

**Warning signs:**
- `/.well-known/oauth-protected-resource` returning 401
- Tests that require a valid Bearer token to fetch PRM or AS metadata
- JWT signing key derived from `AGENT_BRAIN_API_KEY` (an HMAC key that may be shared with the REST server — wrong)
- Authorization code flow failing because the `/token` endpoint receives an auth challenge from RS middleware

**Phase to address:** Design doc phase (explicit architecture diagram with AS vs RS boundary lines); AS/RS implementation phase (FastAPI router structure); integration test phase (verify all `.well-known` and `/auth` endpoints are publicly accessible without a token)

---

### Pitfall 6: JWKS Rotation Cache Stampede and `kid`-Miss Stall (Split AS Shape)

**What goes wrong:**
In the split AS shape (external IdP: Keycloak, Auth0, Cognito), the MCP server caches the JWKS to avoid per-request HTTP calls to the IdP. When the IdP rotates its signing keys (standard practice every 24-90 days), the following sequence breaks token validation:

1. IdP issues new tokens signed with a new key ID (`kid`)
2. Agent Brain's JWKS cache still holds the old keys
3. Every token validated between rotation and cache expiry fails with "kid not found" → 401 storm
4. If the cache TTL is long (24h), the outage window is 24h

If the cache uses a fixed TTL without on-demand refresh, all instances hit the JWKS endpoint simultaneously on TTL expiry — a cache stampede under load.

**Why it happens:**
Simple JWT validation libraries cache JWKS with a fixed TTL and don't implement `kid`-miss invalidation. The standard mitigation (refresh on `kid` miss, then fail) requires two cache behaviors: normal TTL AND on-demand refresh, which tutorials rarely implement together.

**How to avoid:**
Implement JWKS caching with the following logic:
1. Warm cache on startup from `<issuer>/.well-known/jwks.json`
2. Honor `Cache-Control: max-age` from the JWKS endpoint when present
3. On JWT validation, if `kid` not in cache: fetch JWKS once and retry — if still missing, reject the token
4. Add jitter to cache expiry to prevent stampede (e.g., `max-age * (0.9 + random() * 0.1)`)
5. During rotation, the IdP publishes both old and new keys for a grace window (usually 24h) — the cache should hold all keys in the JWKS response, not just the first one

Recommended Python: `joserfc` or `authlib` with a `JWKSet` that handles `kid` lookup; wrap with a `cachetools.TTLCache` with the stampede mitigation.

**Warning signs:**
- JWKS cached as a single hard-coded key or a list with no `kid` index
- Fixed cache TTL with no on-demand refresh
- Tests that only test happy-path JWKS validation, never a `kid`-miss scenario
- No startup JWKS warm-up (first token validated after a cold start hits the IdP)

**Phase to address:** Split AS shape implementation phase (the co-located shape has no JWKS rotation concern — the key is managed locally); integration test phase with Keycloak (simulate key rotation in CI)

---

### Pitfall 7: Dynamic Client Registration Abuse — Open Registration Endpoint

**What goes wrong:**
The DCR endpoint (`POST /register`, RFC 7591) is publicly accessible with no rate limiting or domain validation. Any actor can register a client claiming `client_name: "Claude Desktop"`, `redirect_uri: "https://attacker.com/callback"`, and initiate a real OAuth flow against real users. The authorization consent screen shows the attacker's `redirect_uri` but the legitimate-sounding `client_name`.

The November 2025 MCP spec explicitly acknowledges that DCR "creates massive complexity and risk" — stale registrations, unbounded database growth, and client impersonation.

Note: The spec has demoted DCR to "deprecated, retained for backwards compatibility." For v10.4, DCR is listed as MAY in the roadmap. Assess whether DCR is needed at all given CIMD is now preferred.

**How to avoid:**
If DCR is shipped:
- Apply domain-based allowlisting: only register clients whose `redirect_uri` matches a pre-approved domain list (for self-hosted, this means localhost or the configured deployment domain)
- Rate-limit the registration endpoint aggressively (1 registration per IP per 10 minutes)
- Issue initial access tokens (RFC 7591 §3.1) that must be presented to register — no anonymous registration for production deployments
- Set expiry on registered client credentials (e.g., 90 days) with automated cleanup

If DCR is NOT shipped (preferred for v10.4 self-hosted single-user shape):
- Advertise only pre-registered clients (the official MCP SDK client and `McpHttpBackend`)
- Use CIMD where the client's identity is its HTTPS URL
- Document clearly in `/.well-known/oauth-authorization-server` that DCR is not supported (`registration_endpoint` absent)

**Warning signs:**
- `/register` endpoint accessible without any authentication or rate limiting
- Registered clients never expire or get cleaned up
- AS metadata advertises `registration_endpoint` without any mention of access token requirement
- No SSRF protection on CIMD metadata document fetches (AS fetches attacker-controlled URLs)

**Phase to address:** Co-located AS design phase (decide: DCR or CIMD-only); AS implementation phase (if DCR: rate limit + domain allowlist; if CIMD: SSRF protection on metadata fetch); security review phase

---

### Pitfall 8: Refresh Token Rotation Race Condition and Family Revocation Gap

**What goes wrong:**
Two failure modes:
1. **Race condition**: The client makes two concurrent API calls, both of which trigger token refresh simultaneously. The first refresh invalidates the original refresh token and issues a new one. The second concurrent refresh sends the now-invalidated original token — which the AS treats as a replay attack and revokes the entire token family. The legitimate user is logged out.
2. **Family revocation gap**: When a refresh token is detected as reused (replay signal), the AS revokes the current token but not the entire family of tokens descended from the same original grant. An attacker who stole an earlier token in the chain can still use it.

**Why it happens:**
Rotating refresh tokens without database locking or atomic compare-and-swap allows concurrent refreshes. Family tracking is additional state that simple token stores don't maintain.

**How to avoid:**
- Use database-level row locking when consuming a refresh token (SELECT FOR UPDATE or equivalent)
- Store refresh tokens as a linked list / family tree: each token records its parent token ID
- On any reuse detection: revoke ALL tokens in the family (not just the presented one)
- Implement a short grace window (5-10 seconds) to handle network retries without false-positive family revocation — but not longer (longer windows defeat replay detection)
- 30-day refresh TTL with 15-minute access token TTL matches the v10.4 design spec

**Warning signs:**
- Refresh token storage without any locking mechanism
- Revocation that deletes only `WHERE token_id = ?` rather than `WHERE family_id = ?`
- No test for concurrent refresh token use
- No test for the "attacker uses stolen token before legitimate client" scenario

**Phase to address:** Token lifecycle implementation phase; security test phase (concurrent refresh token stress test)

---

### Pitfall 9: Clock Skew Causes Token Rejection or Acceptance After Expiry

**What goes wrong:**
Two scenarios:
1. **Client clock ahead of server**: Token issued at `iat=T`, `nbf=T`, but the RS clock reads `T-30s`. The token is rejected as "not yet valid" — even though it was just issued.
2. **Server clock ahead of client**: Token with `exp=T+900s` (15-minute TTL) is accepted at RS clock `T+915s` — 15 seconds past actual expiry. An attacker who captured the token has a 15-second window after the client's token expires to replay it.

Distributed deployments (split AS shape with Keycloak in CI vs. Agent Brain on a dev machine) can have clocks drifting by tens of seconds.

**How to avoid:**
- Apply a configurable `leeway` (clock skew tolerance) in JWT validation — 30-60 seconds is standard industry practice. `python-jose`: `options={"leeway": 30}`. `authlib`: `ClaimsOptions` with `leeway=30`.
- Configure NTP on all nodes; document this as a deployment requirement
- Test with intentionally skewed tokens (use `time.time() + 60` in test token generation) to verify leeway is applied
- Do NOT set leeway above 60 seconds — that creates an unacceptable replay window

**Warning signs:**
- JWT validation with no `leeway` parameter (defaults to 0 in most libraries)
- Integration tests that fail intermittently with "token not yet valid" or "token expired" errors
- Keycloak CI instance and dev machine in different timezones without NTP enforcement
- Log lines showing `nbf` validation failures on freshly-issued tokens

**Phase to address:** AS/RS middleware implementation phase (set leeway on first write); Keycloak CI integration phase (verify CI machine NTP sync)

---

### Pitfall 10: Protected Resource Metadata Endpoint Not Unauthenticated

**What goes wrong:**
The `/.well-known/oauth-protected-resource` endpoint (RFC 9728) is placed behind the auth middleware, requiring a valid Bearer token to access. MCP clients use this endpoint for AS discovery BEFORE they have any token. The result: clients cannot complete the authorization flow because they cannot fetch the metadata needed to find the AS.

This is spec-mandated to be publicly accessible: RFC 9728 §3 says "the resource server MUST make its metadata available" — no authentication on the metadata endpoint.

**Why it happens:**
FastAPI global middleware applies to all routes unless explicitly excluded. A developer adds `require_bearer_token` middleware globally without path exclusions, and the `.well-known` path gets protected.

**How to avoid:**
Test the `/.well-known/oauth-protected-resource` endpoint with NO `Authorization` header and verify it returns `200 OK` with the metadata document. Add this as an explicit test in the contract suite. Same applies to `/.well-known/oauth-authorization-server`.

**Warning signs:**
- `/.well-known/oauth-protected-resource` returning 401 or 403
- MCP clients that begin the OAuth flow but fail with "could not fetch PRM"
- `curl -s https://host/.well-known/oauth-protected-resource` requiring `-H "Authorization: Bearer ..."` to succeed

**Phase to address:** Co-located AS implementation phase; PRM/AS metadata integration tests (first thing to test — block implementation from proceeding until this passes)

---

### Pitfall 11: Scope Escalation — Tools Available at Wrong Scope Level

**What goes wrong:**
The `agent-brain:read` scope provides access to `search_documents`, `list_folders`, `explain_result` (read-only tools). But the tool dispatch layer doesn't validate the scope on each tool call — it validates that "a valid token exists" and then allows all tools. A client with only `agent-brain:read` can call `clear_cache`, `remove_folder`, or `add_documents`.

The v10.4 scope design:
- `agent-brain:read` — readOnlyHint tools + resource reads
- `agent-brain:index` — `index_folder`, `add_documents`, `inject_documents`, `wait_for_job`
- `agent-brain:admin` — `cancel_job`, `remove_folder`, `clear_cache`
- `agent-brain:subscribe` — long-lived resource subscriptions

**Why it happens:**
Bearer token middleware validates the token is valid. Scope enforcement requires a second check at the handler level — checking that the token's `scope` claim includes the required scope for the specific tool being called. Developers implement the first check but skip the second.

**How to avoid:**
Build a scope-enforcement decorator/dependency for FastAPI that extracts the `scope` claim from the validated JWT and checks it against a per-tool required scope. Map each of the 16 tools to its required scope in a constant (use the existing `_tool_matrix.py` SOT pattern from v10.2). Reject with 403 + `WWW-Authenticate: Bearer error="insufficient_scope", scope="agent-brain:admin"` on mismatch (not 401 — the token is valid, just under-privileged).

Example mapping:
```python
TOOL_SCOPE_REQUIREMENTS = {
    "search_documents": "agent-brain:read",
    "list_folders": "agent-brain:read",
    "explain_result": "agent-brain:read",
    "cache_status": "agent-brain:read",
    "list_file_types": "agent-brain:read",
    "index_folder": "agent-brain:index",
    "add_documents": "agent-brain:index",
    "inject_documents": "agent-brain:index",
    "wait_for_job": "agent-brain:index",
    "list_jobs": "agent-brain:read",
    "get_job": "agent-brain:read",
    "cancel_job": "agent-brain:admin",
    "remove_folder": "agent-brain:admin",
    "clear_cache": "agent-brain:admin",
    # resource subscriptions
    "resources/subscribe": "agent-brain:subscribe",
}
```

**Warning signs:**
- Integration test where a `read`-only token successfully calls `clear_cache`
- Tool dispatch that checks `token_is_valid` but not `scope_includes(required_scope)`
- 401 returned instead of 403 on scope mismatch (signals the middleware isn't distinguishing invalid vs. insufficient)

**Phase to address:** RS middleware implementation phase; tool dispatch phase; security test phase (test every scope boundary)

---

### Pitfall 12: Static Bearer → OAuth Transition Leaves a Mixed-Auth Window

**What goes wrong:**
The `AGENT_BRAIN_AUTH=none` → `AGENT_BRAIN_AUTH=basic` → `AGENT_BRAIN_AUTH=oauth` migration path (from the v10.4 design doc) creates a transition period where both static Bearer (`AGENT_BRAIN_API_KEY`) and OAuth tokens may be accepted simultaneously. During this window, attackers who have captured an `AGENT_BRAIN_API_KEY` (from a misconfigured environment, a `.env` file in source control, or a log line) can continue accessing the remote server even after OAuth is enabled.

**Why it happens:**
The `basic` bridge mode is intended as a LAN transitional step. If the cutover from `basic` to `oauth` is delayed or if `basic` mode stays enabled as a "fallback", the improved OAuth security provides no actual improvement.

**How to avoid:**
- `AGENT_BRAIN_AUTH=basic` is LAN-only (non-routable addresses only) — enforce at the bind layer: if `AGENT_BRAIN_AUTH=basic` and bind address is non-loopback and non-RFC1918, refuse to start
- Document a hard cutover timeline: `basic` must be removed within N days of OAuth enablement
- On startup with `AGENT_BRAIN_AUTH=oauth`, log a WARNING (not silent) if `AGENT_BRAIN_API_KEY` is set in the environment, noting it is not used for MCP auth in this mode
- Integration test: with `AGENT_BRAIN_AUTH=oauth`, verify that a request using only `X-API-Key: <key>` returns 401 (the OAuth middleware should not fall through to API key auth)

**Warning signs:**
- `AGENT_BRAIN_AUTH=oauth` but the `verify_api_key` dependency is still imported in the MCP router
- Middleware that checks Bearer token AND falls through to API key validation on Bearer failure
- No test for "static API key rejected when `AGENT_BRAIN_AUTH=oauth`"

**Phase to address:** Auth mode toggle implementation phase; migration guide documentation phase; integration test phase

---

### Pitfall 13: Mix-Up Attack via `iss` Validation Gap

**What goes wrong:**
In environments where `McpHttpBackend` interacts with multiple MCP servers (or where a malicious server is injected), an attacker controlling one AS sends the authorization code back to the client with an `iss` parameter that points to an honest AS. The client then redeems the code at the honest AS's token endpoint — sending the code to the wrong endpoint and potentially leaking it.

The MCP spec addresses this via RFC 9207: clients MUST validate the `iss` parameter in authorization responses against the recorded expected issuer. If `authorization_response_iss_parameter_supported: true` in AS metadata but `iss` is absent from the response, the client MUST reject it.

**Why it happens:**
This is a sophisticated attack, but the prevention gap is simple: omitting `iss` validation in the authorization code callback handler. The spec's 4-row matrix (table from the Authorization Response Validation section) is easy to misread — the "false or absent / present" row requires validation even when the AS doesn't advertise support.

**How to avoid:**
In `McpHttpBackend`'s OAuth callback handler:
1. Before redirecting to AS, record the expected `issuer` from the AS metadata document
2. On callback, extract `iss` from the response
3. Apply the spec's 4-row matrix: compare present `iss` to recorded value; reject if advertised but absent
4. Use simple string comparison (no URL normalization per RFC 3986 §6.2.1 — the spec explicitly forbids normalization before comparison)

**Warning signs:**
- OAuth callback handler that ignores the `iss` query parameter
- Authorization code exchange that doesn't assert the token endpoint URL matches the expected AS
- Missing test for "wrong `iss` in authorization response → rejection"

**Phase to address:** `McpHttpBackend` OAuth dance implementation phase; client security test phase

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|---|---|---|---|
| HMAC-SHA256 JWT signing (symmetric key) for co-located AS | No key pair management; simpler setup | Key must be shared if RS and AS are ever split; key rotation requires downtime | Only for co-located single-binary shape; document the constraint explicitly |
| Skip DPoP in v10.4 (optional per spec) | Massive implementation complexity reduction; DPoP Python library support is immature | No sender-constraint on access tokens; stolen tokens are fully usable until TTL | Acceptable for v10.4 with short TTLs (15 min); DPoP deferred to v10.5 |
| Accept tokens without `resource` parameter during transition | Smoother migration from static Bearer | Indefinite token confusion risk; `aud` validation becomes meaningless | Never; even in transition mode, require `resource` immediately |
| Single scope check at route level (not per-tool) | Less code | Scope escalation within a route (e.g., all tool calls allowed with any scope) | Never; scope must be checked per-tool |
| Fixed JWKS TTL without `kid`-miss refresh | Simpler caching code | 24h+ outage window on every key rotation for split AS shape | Only for co-located shape (no JWKS rotation concern); never for split AS |
| Static pre-registered client only (no DCR, no CIMD) | Simplest possible client registration | Clients that don't know their pre-registered ID cannot connect | Acceptable for v10.4 self-hosted single-user; document the pre-registered IDs |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|---|---|---|
| Keycloak (CI split AS) | Relying on Keycloak's default realm `master` in CI | Create a dedicated realm per-test-run; `master` has dangerous defaults (admin client unrestricted) |
| Keycloak (CI split AS) | Not configuring RFC 8707 resource indicators in the Keycloak realm | Enable "Resource Indicators" feature in Keycloak 22+; it must be explicitly enabled per-client |
| `McpHttpBackend` OAuth dance | Using Python's `webbrowser.open()` for the authorization redirect in headless CI | Use `httpx` redirect-following for the auth code flow in headless test mode; never rely on a browser in CI |
| Official MCP SDK client | Expecting the SDK's OAuth client to handle all edge cases correctly out of the box | The SDK's auth support is evolving; pin SDK version and verify it sends `resource` parameter and validates `iss` |
| authlib JWT validation | Calling `jwt.decode()` without `claims_cls` or `claims_options` | `decode()` returns raw claims without validation; always call `.validate()` on the returned ClaimsSet |
| python-jose | Library hasn't received major updates since 2023 | Prefer `authlib` or `joserfc` for new code; `python-jose` has known CVEs in older ECDSA handling |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---|---|---|
| Logging the full `Authorization: Bearer <token>` header | Token captured in log aggregation system; any log reader has a working token until it expires | Log only `Authorization: Bearer <first-8-chars>...` or the token's `jti` claim; never log full tokens |
| Storing refresh tokens as plaintext in SQLite/JSON | Single file exfil compromises all user sessions | Hash refresh tokens before storage (PBKDF2 or bcrypt); validate by hashing the presented token and comparing |
| `/.well-known/oauth-protected-resource` serving HTTP (not HTTPS) | Discovery response can be MITM'd; attacker replaces AS URL with their own | Enforce TLS on all endpoints including `.well-known`; redirect HTTP to HTTPS at the bind layer |
| Not validating `redirect_uri` exactly (using prefix or wildcard match) | Authorization code theft via open redirect | Exact string comparison of `redirect_uri`; any mismatch → reject |
| Accepting tokens with `alg: none` | JWTs with no signature accepted as valid | Pin allowed algorithms explicitly: `["RS256", "ES256"]`; never include `none` |
| DPoP nonce not validated (if DPoP shipped) | DPoP proofs replayable within the nonce window | Maintain a short-lived nonce store; reject proofs with expired or reused nonces |
| PKCE `code_verifier` not consumed (not deleted after use) | Authorization code replayable within TTL | Delete code + verifier from store atomically on successful token exchange |

---

## "Looks Done But Isn't" Checklist

- [ ] **PRM endpoint**: `GET /.well-known/oauth-protected-resource` returns 200 WITHOUT a Bearer token — not just with one
- [ ] **AS metadata endpoint**: `GET /.well-known/oauth-authorization-server` returns 200 WITHOUT a Bearer token
- [ ] **Audience validation**: a token with `aud: ["https://other-service.com"]` is rejected with 401 at the MCP endpoint
- [ ] **Resource parameter**: the AS rejects a token request that omits the `resource` parameter
- [ ] **PKCE S256-only**: the AS rejects an authorization request with `code_challenge_method=plain`
- [ ] **PKCE advertisement**: `/.well-known/oauth-authorization-server` includes `"code_challenge_methods_supported": ["S256"]`
- [ ] **Scope enforcement**: a token with only `agent-brain:read` cannot call `clear_cache` (returns 403, not 401)
- [ ] **Token passthrough blocked**: the MCP→REST-API leg uses `AGENT_BRAIN_API_KEY`, NOT the client's OAuth token
- [ ] **Refresh token family revocation**: using a previously-rotated refresh token revokes ALL tokens in the family
- [ ] **Concurrent refresh**: two simultaneous refresh calls do not result in two valid refresh tokens or a false-positive family revocation
- [ ] **Static Bearer rejected in OAuth mode**: `AGENT_BRAIN_AUTH=oauth` + `X-API-Key` header → 401
- [ ] **`iss` validation**: authorization callback with wrong `iss` → rejected before code exchange
- [ ] **Log safety**: a full search of auth-layer logs contains no raw Bearer token strings
- [ ] **CIMD SSRF protection**: registering a client with `client_id=http://169.254.169.254/metadata` is rejected

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---|---|---|
| Missing `aud` validation discovered post-deploy | HIGH | Emergency patch middleware; rotate JWKS to invalidate all current tokens; notify users to re-authenticate |
| Token passthrough discovered | HIGH | Remove token forwarding code; rotate `AGENT_BRAIN_API_KEY`; audit logs for unauthorized calls to REST API |
| Open DCR endpoint abused | HIGH | Disable DCR endpoint; revoke all dynamically registered clients; investigate which clients abused it; switch to CIMD |
| Refresh token family revocation gap | MEDIUM | Implement family tracking; force all users to re-authenticate (revoke all refresh tokens globally) |
| Clock skew causing 401 storms | MEDIUM | Add `leeway=30` to JWT validation immediately; configure NTP |
| JWKS cache miss on key rotation (split AS) | MEDIUM | Add `kid`-miss refresh logic; temporarily increase cache TTL for new key; coordinate with IdP on overlap window |
| PKCE `plain` accepted discovered | MEDIUM | Patch AS to reject `plain`; existing sessions using `plain` become invalid (force re-auth) |
| Scope escalation discovered | MEDIUM | Add per-tool scope enforcement; audit logs for tool calls that exceeded authorized scope |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---|---|---|
| Missing `aud` validation (Pitfall 1) | AS/RS implementation + design doc (canonical URI config) | Contract test: wrong-audience token → 401 |
| Confused deputy / token passthrough (Pitfall 2) | Design doc (explicit data-flow diagram) + AS/RS implementation | Integration test: verify `AGENT_BRAIN_API_KEY` on MCP→REST leg |
| Missing Resource Indicators (Pitfall 3) | Co-located AS implementation + `McpHttpBackend` OAuth dance | Contract test: AS rejects token request without `resource` |
| PKCE downgrade (Pitfall 4) | Co-located AS implementation | AS metadata test: `code_challenge_methods_supported: ["S256"]`; reject `plain` test |
| AS/RS co-location confusion (Pitfall 5) | Design doc (router structure) + AS/RS implementation | Test: `.well-known` endpoints accessible without token |
| JWKS rotation cache stampede (Pitfall 6) | Split AS implementation phase | Simulated key rotation in Keycloak CI |
| DCR abuse / open registration (Pitfall 7) | AS design phase + AS implementation | Pen test: attempt anonymous registration with malicious redirect_uri |
| Refresh token rotation race (Pitfall 8) | Token lifecycle implementation | Concurrent refresh stress test |
| Clock skew (Pitfall 9) | AS/RS middleware implementation | Test with artificially skewed tokens |
| PRM endpoint unauthenticated (Pitfall 10) | Co-located AS implementation (first test to write) | `curl` without token → 200 |
| Scope escalation (Pitfall 11) | RS middleware + tool dispatch implementation | Per-scope boundary test for all 16 tools |
| Mixed-auth transition window (Pitfall 12) | Auth mode toggle implementation | Test: `AGENT_BRAIN_AUTH=oauth` + API key → 401 |
| Mix-up attack / `iss` validation (Pitfall 13) | `McpHttpBackend` OAuth dance | Test: wrong `iss` in callback → rejected before code exchange |
| MCP spec staleness (meta-pitfall) | Design doc phase | Mandatory spec re-read before design sign-off; cite spec version in design doc |

---

## Sources

- MCP Authorization spec (current draft): https://modelcontextprotocol.io/specification/draft/basic/authorization
- MCP Authorization Security Considerations (current draft): https://modelcontextprotocol.io/specification/draft/basic/authorization/security-considerations
- Obsidian Security: "When MCP Meets OAuth" (account takeover pitfalls): https://www.obsidiansecurity.com/blog/when-mcp-meets-oauth-common-pitfalls-leading-to-one-click-account-takeover
- Descope: "Diving Into the MCP Authorization Specification": https://www.descope.com/blog/post/mcp-auth-spec
- WorkOS: "Dynamic Client Registration (DCR) in MCP": https://workos.com/blog/dynamic-client-registration-dcr-mcp-oauth
- Aaron Parecki: "Client Registration and Enterprise Management in the November 2025 MCP Authorization Spec": https://aaronparecki.com/2025/11/25/1/mcp-authorization-spec-update
- WorkOS: "MCP 2025-11-25 spec update": https://workos.com/blog/mcp-2025-11-25-spec-update
- dasroot.net: "The New MCP Authorization Specification (RFC 8707 Resource Indicators)": https://dasroot.net/posts/2026/04/mcp-authorization-specification-oauth-2-1-resource-indicators/
- TokenMix: "MCP Protocol Changes 2026 changelog": https://tokenmix.ai/blog/mcp-updates-changelog-every-protocol-change-2026
- MCP Playground: "OAuth 2.1, Bearer Tokens, and What the Spec Actually Requires": https://mcpplaygroundonline.com/blog/mcp-server-oauth-authentication-guide
- RFC 9728 — OAuth 2.0 Protected Resource Metadata: https://datatracker.ietf.org/doc/html/rfc9728
- RFC 9700 — Best Current Practice for OAuth 2.0 Security (IETF, Jan 2025): https://datatracker.ietf.org/doc/rfc9700/
- Obsidian Security: "Refresh Token Security: Best Practices": https://www.obsidiansecurity.com/blog/refresh-token-security-best-practices
- OWASP OAuth 2.0 Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html
- MCP Mustafa Turan: "MCP Authentication & Authorization Pain Points": https://medium.com/@mustafaturan/mcp-authentication-authorization-pain-points-5506e63dd799

---
*Pitfalls research for: OAuth 2.1 on MCP Streamable HTTP server (v10.4 milestone, agent-brain)*
*Researched: 2026-06-14*
