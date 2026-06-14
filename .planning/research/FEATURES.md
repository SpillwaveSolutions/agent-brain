# Feature Research

**Domain:** OAuth 2.1 Authorization for Remote MCP Server (Agent Brain v10.4 / MCP v4 / issue #188)
**Researched:** 2026-06-14
**Confidence:** HIGH (primary source: official MCP spec 2025-11-25 fetched verbatim; secondary: Context7 /modelcontextprotocol/modelcontextprotocol with High reputation)

---

## Spec Baseline

**Authoritative source:** MCP Authorization Specification 2025-11-25
URL: https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
Standards base: OAuth 2.1 draft-ietf-oauth-v2-1-13 + RFC 9728 + RFC 8414 + RFC 7591 + draft-ietf-oauth-client-id-metadata-document-00

Authorization is **OPTIONAL** for MCP implementations. When supported, HTTP-transport implementations **SHOULD** conform to the 2025-11-25 spec. STDIO transport **SHOULD NOT** follow this spec (credentials from environment instead).

---

## Feature Landscape

### Table Stakes — MCP Spec MUST / SHOULD (Required for any compliant protected server)

Features that MUST exist for the server to be spec-compliant. Missing these = MCP clients cannot connect.

| Feature | MCP Spec Level | Complexity | Dependency on Existing Code | Notes |
|---------|---------------|------------|----------------------------|-------|
| **401 Unauthorized on unauthenticated MCP request** | MUST (OAuth 2.1 §5.3) | LOW | `agent-brain-server` HTTP middleware | Every protected endpoint returns 401 with `WWW-Authenticate: Bearer resource_metadata="..."` |
| **Protected Resource Metadata document at `/.well-known/oauth-protected-resource`** | MUST (RFC 9728 via MCP spec §3) | LOW | New FastAPI route | JSON doc: `resource`, `authorization_servers`, `scopes_supported`. Clients MUST use PRM for AS discovery. |
| **`WWW-Authenticate` header on 401 with `resource_metadata` URL** | MUST (RFC 9728 §5.1 via MCP spec) | LOW | HTTP middleware | Clients MUST be able to parse this header. SHOULD also include `scope` hints. |
| **Authorization Server Metadata at `/.well-known/oauth-authorization-server`** | MUST provide at least one of: RFC 8414 or OIDC Discovery (MCP spec §5) | MEDIUM | New FastAPI routes or AS library | Must include `issuer`, `authorization_endpoint`, `token_endpoint`, `code_challenge_methods_supported`. |
| **OAuth 2.1 Authorization Code flow** | MUST (OAuth 2.1 §4.1) | HIGH | None (new `oauth/` package) | Standard auth-code grant; redirect-based; requires browser/user-agent on client side. |
| **PKCE with S256 challenge method** | MUST for all clients (MCP spec Security §4; OAuth 2.1 §7.5.2) | MEDIUM | New AS implementation | Clients MUST use S256. AS MUST include `code_challenge_methods_supported: ["S256"]` in metadata. Clients MUST refuse to proceed if absent. |
| **Resource Indicators (RFC 8707) — `resource` param in auth + token requests** | MUST on client side; AS MUST validate `aud` (MCP spec §6) | MEDIUM | `McpHttpBackend` (client side); new RS validation | Token `aud` claim MUST match the MCP server's canonical URI. Clients MUST send even if AS does not support it. |
| **`aud` claim validation on the Resource Server** | MUST (MCP spec §7 + OAuth 2.1 §5.2) | MEDIUM | New RS middleware | RS MUST validate token was issued specifically for it. MUST reject tokens with wrong/missing `aud`. Token passthrough is explicitly forbidden. |
| **`Authorization: Bearer <token>` header on every MCP request** | MUST (OAuth 2.1 §5.1.1) | LOW | `McpHttpBackend` (already does Bearer for API key) | Every HTTP request, even within same logical session. MUST NOT put token in URI query string. |
| **HTTP 401 for invalid/expired token** | MUST (OAuth 2.1 §5.3) | LOW | HTTP middleware | RS MUST return 401. |
| **HTTP 403 + `WWW-Authenticate: Bearer error="insufficient_scope"` for scope mismatch** | SHOULD (MCP spec §8; RFC 6750 §3.1) | LOW | Per-route scope guard | 403 response MUST include `scope` and `resource_metadata` in `WWW-Authenticate` header. |
| **Scope enforcement middleware (per-route, not per-tool)** | MUST enforce (implied by RS role; tool-level scopes are a draft proposal per issue #1880) | HIGH | Tool registry / FastAPI deps | Route-level enforcement is MUST; tool-level `readOnlyHint` enforcement at route layer is a natural mapping (see Scope Design section). |
| **`AGENT_BRAIN_AUTH` toggle (`none` / `basic` / `oauth`)** | Project-defined (not in MCP spec) | LOW | `settings.py` | Default `none` preserves all existing behavior. Backward compatibility gate. |
| **HTTPS enforcement on all AS endpoints** | MUST (OAuth 2.1 §1.5; MCP spec Security §2) | LOW | Deployment config / startup check | `localhost` and `127.0.0.1` are allowed for dev. All redirect URIs MUST be localhost or HTTPS. |
| **Rotating refresh tokens for public clients** | MUST rotate (OAuth 2.1 §4.3.1) | MEDIUM | New token store | Public clients (all MCP clients are public) MUST receive rotated refresh tokens. Replay detection required. |
| **Short-lived access tokens** | SHOULD (MCP spec Security §1) | LOW | Token issuance config | Spec says AS SHOULD issue short-lived tokens. 15-min design doc value is consistent with this. |
| **`McpHttpBackend` OAuth dance (client side)** | MUST on client (MCP spec §3 + §6) | HIGH | `McpHttpBackend` (v10.3, Phase 57) | Intercept 401, parse `WWW-Authenticate`, fetch PRM, fetch AS metadata, run auth-code+PKCE flow, store + refresh tokens. Hard dependency: v10.3 shipped. |
| **Client registration via one of: CIMD, pre-registration, or DCR** | SHOULD support CIMD; MAY support DCR (MCP spec §4) | MEDIUM | New AS registration logic | CIMD (Client ID Metadata Documents) is the preferred new mechanism. DCR is backward compat only. See priority order below. |

### Differentiators — MCP Spec SHOULD / MAY or Project-Specific (Add value, not strictly required)

| Feature | Value Proposition | MCP Spec Level | Complexity | Notes |
|---------|-------------------|---------------|------------|-------|
| **Client ID Metadata Documents (CIMD, draft-ietf-oauth-client-id-metadata-document-00)** | Stateless client identity — URL is the `client_id`, no server-side registry needed; preferred for new deployments | SHOULD (MCP spec §4.1) | MEDIUM | AS fetches `client_id` URL to get client metadata JSON; MUST validate `client_id` in doc matches URL. SSRF risk — AS SHOULD apply SSRF mitigations. |
| **Dynamic Client Registration (DCR, RFC 7591)** | Zero-friction onboarding for MCP clients with no pre-existing relationship; backward compat with older MCP spec revisions | MAY (MCP spec §4.3) | MEDIUM | Lower priority than CIMD; ship as fallback. Useful for the co-located AS/RS self-hosted case. |
| **Co-located AS/RS deployment (single binary, self-hosted)** | Zero-dependency self-hosted path; JWT-signed tokens verified locally without external AS | Project-defined | HIGH | AS + RS in the same FastAPI app. JWT-signed tokens (HS256/RS256). No introspection needed (can validate locally). Gated by `AGENT_BRAIN_AUTH=oauth`. |
| **Split AS/RS deployment (external IdP: Keycloak / Auth0 / Cognito)** | Enterprise path; delegates user management to existing IdP; JWKS-cached verification on RS | Project-defined (Definition of Done requires Keycloak in CI) | HIGH | RS fetches JWKS from AS, caches, validates token signature + `aud` + `iss`. No DCR needed (clients pre-registered in IdP). |
| **Token introspection (RFC 7662)** | Enables RS to validate opaque tokens issued by external AS without JWK parsing; required for split-AS when AS issues opaque tokens | Optional per spec (not required in 2025-11-25) | MEDIUM | Needed for Keycloak split-AS path when opaque tokens are issued. Co-located AS can skip (JWT). |
| **Token revocation endpoint (RFC 7009)** | Lets clients revoke access/refresh tokens on logout or key rotation | Optional per spec | LOW | Admin UX; useful for `agent-brain:admin` scope holders. |
| **`AGENT_BRAIN_AUTH=basic` shared-secret LAN bridge** | Migration step — lets existing static-key deployments coexist on LAN without full OAuth; referenced in design doc as v1.x feature | Project-defined | LOW | Already partly implemented as `AGENT_BRAIN_API_KEY` / `X-API-Key` (SECURITY-01, v10.2.1). Formalize as `AGENT_BRAIN_AUTH=basic` alias. Small lift. |
| **Step-up authorization flow (scope challenge handling)** | Allows clients to incrementally request more scopes at runtime without full re-auth | SHOULD on client (MCP spec §8.2) | MEDIUM | Server signals 403 + `error="insufficient_scope"` + required `scope`; client re-initiates auth with expanded scope set. |
| **Scope hints in `WWW-Authenticate` on 401** | Clients can request minimal scopes immediately rather than requesting all `scopes_supported` | SHOULD (MCP spec §3.2) | LOW | One extra field in the 401 response header; high value for least-privilege UX. |
| **`agent-brain:subscribe` scope for long-lived subscriptions** | Separates subscription authorization from read authorization; enables operators to restrict who can hold long-lived connections | Project-defined | LOW | Maps to existing `SUB-01..05` subscription machinery (v10.2, Phase 52). Add scope check in subscription start handler. |
| **Audit log for every authorized call** | Compliance / forensics; design doc explicitly mentions this | Project-defined (design doc notes "may need its own milestone") | MEDIUM | Structured log entry per authorized MCP request: client_id, scopes, tool name, timestamp. Can be a middleware wrapper. Deferred to its own milestone per design doc. |
| **DPoP (RFC 9449) — sender-constrained tokens** | Binds access + refresh tokens to a client-held public/private key pair; token theft becomes a non-event | Optional extension (MCP spec references ext-auth repo; DPoP is not in 2025-11-25 core) | HIGH | Not in the 2025-11-25 core spec. Listed in design doc as optional. Tracked in modelcontextprotocol/java-sdk issue #887. Defer to v10.5+. |

### Anti-Features — Do Not Build

| Anti-Feature | Why It Seems Attractive | Why It Is Problematic | What to Do Instead |
|--------------|------------------------|----------------------|-------------------|
| **Token passthrough to upstream APIs** | Saves one token exchange when calling OpenAI / Anthropic internally | Explicitly forbidden by MCP spec §7 ("confused deputy" problem); MUST NOT pass through the token the MCP client sent | RS obtains its own credentials for upstream calls (env vars / secrets manager) |
| **Skipping `aud` validation** | Simplifies token validation code | Allows token reuse across services; MCP spec MUST requires `aud` check on every inbound token | Always validate `aud` equals the canonical MCP server URI |
| **Global admin token with no scope restrictions** | Convenient for dev/CI | Violates least-privilege; a leaked admin token grants all operations | Require `agent-brain:admin` scope explicitly; use 15-min access tokens even for admin |
| **Per-tool client_id (one OAuth app per tool)** | Granular audit trail at OAuth-client level | Explosion of DCR registrations; MCP spec does not define tool-level clients; breaks `readOnlyHint` composability | Use per-scope enforcement at route/middleware layer instead |
| **Tool-level scope enforcement (custom `scopes` field in ToolSpec)** | Maximum granularity; SEP-1880 proposes this | SEP-1880 is an open proposal as of June 2026, not in the 2025-11-25 spec; early adoption risks spec drift | Map scopes to tool categories (read/index/admin/subscribe) at middleware level now; revisit when SEP-1880 lands |
| **Device Authorization Grant (RFC 8628) as primary flow** | Headless clients (CI bots) cannot open a browser | MCP spec does not mandate device flow; PKCE auth-code with `localhost` redirect is the standard MCP path | Use auth-code+PKCE with `localhost` loopback redirect for all clients; for CI, use pre-registered confidential client or service-account credentials |
| **Custom JWT format (non-standard claims)** | Tempting to add Agent Brain-specific metadata in JWT | Non-standard claims break external IdP token validation; `aud`, `iss`, `exp`, `scope` are sufficient | Use standard JWT claims per RFC 9068; add context via scopes |
| **Sharing a single OAuth app / client_id across multi-tenant instances** | Simpler registration | Each Agent Brain instance is its own resource server with its own canonical URI; sharing a client_id conflates audiences | One OAuth app per deployed Agent Brain instance |

---

## Scope Design — Concrete Mapping to Existing Tools

Design doc proposes four scopes. This maps them concretely to the 16-tool surface and existing resources.

### `agent-brain:read`
Covers all read-only operations. Corresponds to tools with `readOnlyHint: true` plus resource reads.

**Tools covered:**
- `search_documents` (readOnlyHint: true)
- `explain_result` (readOnlyHint: true)
- `get_corpus_status` (readOnlyHint: true)
- `cache_status` (readOnlyHint: true)
- `list_folders` (readOnlyHint: true)
- `list_file_types` (readOnlyHint: true)
- `list_jobs` (readOnlyHint: true)
- `get_job` (readOnlyHint: true)

**Resources covered:**
- `corpus://status` (read + subscribe)
- `corpus://folders` (read + subscribe)
- `job://<job_id>` (read; subscribe is `agent-brain:subscribe`)
- `chunk://<chunk_id>` (read)
- `graph-entity://<type>/<id>` (read)
- `file://<abs-path>` (read, within sandbox)
- All 6 MCP prompts (render = read)

### `agent-brain:index`
Covers write operations that modify the corpus but do not destroy data.

**Tools covered:**
- `index_folder` (not readOnly)
- `add_documents` (not readOnly)
- `inject_documents` (not readOnly)
- `wait_for_job` (reads job state but initiated by indexing operation; scope follows the write)

### `agent-brain:admin`
Covers destructive or management operations. Requires explicit user consent at auth time.

**Tools covered:**
- `cancel_job` (requires `confirm: Literal[True]`)
- `remove_folder` (requires `confirm: Literal[True]`)
- `clear_cache` (requires `confirm: Literal[True]`)

**Note:** `agent-brain:admin` implies `agent-brain:read` and `agent-brain:index` for practical usability (operators will typically request all three). Scope hierarchy is a convention, not a spec requirement.

### `agent-brain:subscribe`
Covers long-lived resource subscription connections. Separate scope so operators can limit who can hold persistent connections to the MCP server.

**Subscriptions covered:**
- `job://<job_id>` subscriptions (SUB-01)
- `corpus://status` subscriptions (SUB-02)
- `corpus://folders` subscriptions (SUB-03)

**Note:** Subscribing is additive to reading. An MCP client holding `agent-brain:read` can read resources; it additionally needs `agent-brain:subscribe` to open and maintain a subscription. The subscription handler checks for this scope.

### Scope Validation Layer

Scope enforcement lives in FastAPI dependency injection (matching the existing `verify_api_key` pattern from SECURITY-01, v10.2.1). A `require_scope(scope: str)` FastAPI dep is injected per route group. The 401 `WWW-Authenticate` header SHOULD include `scope="agent-brain:read"` (or the minimum required) so MCP clients know what to request.

---

## End-to-End Discovery and Authorization Flow

The complete flow that `McpHttpBackend` must implement on the client side, and that `agent-brain-server` plus the new `oauth/` package must implement on the server side:

```
1. McpHttpBackend sends unauthenticated MCP request
   → Server returns: HTTP 401 Unauthorized
                     WWW-Authenticate: Bearer resource_metadata="https://host/.well-known/oauth-protected-resource",
                                              scope="agent-brain:read"

2. McpHttpBackend GETs /.well-known/oauth-protected-resource
   → Server returns PRM JSON:
     {
       "resource": "https://host",
       "authorization_servers": ["https://host"],  // co-located AS
       "scopes_supported": ["agent-brain:read","agent-brain:index","agent-brain:admin","agent-brain:subscribe"]
     }

3. McpHttpBackend tries AS metadata endpoints in priority order:
   a. GET https://host/.well-known/oauth-authorization-server  (RFC 8414)
   b. GET https://host/.well-known/openid-configuration        (OIDC Discovery)
   → Returns: { issuer, authorization_endpoint, token_endpoint,
                registration_endpoint, code_challenge_methods_supported: ["S256"] }
   → If code_challenge_methods_supported absent: McpHttpBackend MUST abort

4. Client registration (priority order per spec):
   a. Use pre-registered client_id if known for this server
   b. Use CIMD if AS advertises client_id_metadata_document_supported: true
   c. Use DCR (POST /register) if registration_endpoint present
   d. Prompt user to enter client credentials

5. PKCE: McpHttpBackend generates code_verifier (32 random bytes, base64url), code_challenge = SHA256(verifier)

6. McpHttpBackend opens browser to:
   GET /authorize?response_type=code
                  &client_id=<id>
                  &redirect_uri=http://127.0.0.1:<free-port>/callback
                  &scope=agent-brain:read
                  &state=<csrf-token>
                  &code_challenge=<challenge>
                  &code_challenge_method=S256
                  &resource=https://host     <- RFC 8707 MUST

7. User authenticates + consents (AS handles)
   → AS redirects to McpHttpBackend's local callback with code + state

8. McpHttpBackend verifies state, then:
   POST /token
     grant_type=authorization_code
     code=<code>
     redirect_uri=http://127.0.0.1:<port>/callback
     client_id=<id>
     code_verifier=<verifier>
     resource=https://host     <- RFC 8707 MUST

9. AS returns: { access_token, token_type: "Bearer", expires_in: 900,
                  refresh_token: <rotating>, scope: "agent-brain:read" }
   Token JWT aud claim MUST equal "https://host"

10. McpHttpBackend sends MCP request:
    Authorization: Bearer <access_token>
    → RS validates: signature, exp, aud == canonical URI, scope covers requested operation
    → If 403 insufficient_scope: step-up auth flow (re-request with broader scope)
    → On expiry: use refresh_token to get new access_token (AS issues new rotating refresh)
```

---

## Feature Dependencies

```
PRM (/.well-known/oauth-protected-resource)
    └──required-by──> AS metadata discovery
                          └──required-by──> Client registration (CIMD / DCR / pre-reg)
                                                └──required-by──> Auth code + PKCE flow
                                                                      └──required-by──> Access token
                                                                                            └──required-by──> Authorized tool call

AGENT_BRAIN_AUTH toggle
    └──gates──> All OAuth middleware (default: none, preserve existing behavior)

SECURITY-01 (API key / X-API-Key, v10.2.1)
    └──formalized-as──> AGENT_BRAIN_AUTH=basic (LAN bridge, low lift)

McpHttpBackend (v10.3, CLI-MCP-02/03)
    └──extended-by──> OAuth dance client logic (intercept 401, PKCE, token store)

Token store (new)
    └──used-by──> access token cache + rotating refresh token management

Co-located AS/RS
    └──alternative-to──> Split AS/RS (Keycloak/Auth0)
    └──enables──> JWT local validation (no introspection needed)

Split AS/RS
    └──requires──> JWKS endpoint fetch + cache
    └──optionally-requires──> Token introspection (RFC 7662) if AS issues opaque tokens

Scope enforcement middleware
    └──maps-to──> Scope-to-tool categories (read / index / admin / subscribe)
    └──built-on──> Existing verify_api_key FastAPI dep pattern (SECURITY-01)

agent-brain:subscribe scope guard
    └──hooks-into──> Existing SUB-01..05 subscription machinery (v10.2, Phase 52)
```

### Dependency Notes

- **PRM + AS metadata are required before anything else:** A client that cannot discover the AS cannot start the auth flow. These two routes are the first thing to build.
- **McpHttpBackend v10.3 is the hard prerequisite:** It already handles Bearer tokens; extend it to handle the 401 challenge, PKCE generation, and token refresh. v10.3 is shipped.
- **Co-located AS and split AS share the RS validation middleware:** The RS middleware always validates `aud` + `exp` + `scope`; only the signature verification step differs (local JWT secret vs. remote JWKS).
- **CIMD SHOULD be implemented before DCR:** Spec priority order has CIMD above DCR. Build CIMD first; add DCR as fallback.
- **DPoP has no dependency on the rest of this scope:** It is an independent token-binding layer, but it requires changes to both AS (token issuance) and RS (DPoP proof header validation). Defer to v10.5+.

---

## MVP Definition (for v10.4 milestone)

### Phase 1 — Server Side: Protected Resource (RS middleware + discovery endpoints)

Minimum viable for a spec-compliant resource server that external AS can protect.

- [ ] **`AGENT_BRAIN_AUTH` environment toggle** (`none` / `basic` / `oauth`) — low lift, zero risk to existing behavior
- [ ] **401 + `WWW-Authenticate: Bearer resource_metadata=...` on unauthenticated requests** — MUST
- [ ] **`GET /.well-known/oauth-protected-resource`** returning PRM JSON with 4 scopes — MUST
- [ ] **Access token validation middleware** (JWT `aud` + `exp` + `iss` + `scope` validation) — MUST; JWT for co-located, JWKS-cache for split
- [ ] **Scope enforcement FastAPI deps** (`require_scope("agent-brain:read")` etc.) mapped to route groups — MUST
- [ ] **HTTP 403 + `WWW-Authenticate: Bearer error="insufficient_scope"` response** — SHOULD

### Phase 2 — Authorization Server: Co-located AS

Self-hosted single-binary path with no external IdP dependency.

- [ ] **`GET /.well-known/oauth-authorization-server`** with `code_challenge_methods_supported: ["S256"]` — MUST
- [ ] **Authorization endpoint** (`GET /authorize`) with PKCE + resource param validation — MUST
- [ ] **Token endpoint** (`POST /token`) issuing JWT access (15-min) + rotating refresh (30-day) — MUST
- [ ] **PKCE S256 verification** — MUST
- [ ] **Resource Indicators RFC 8707 `resource` param in token request** — MUST; `aud` in issued JWT
- [ ] **Pre-registration / CIMD client support** — SHOULD (build CIMD first)
- [ ] **DCR (`POST /register`)** — MAY (backward compat fallback)
- [ ] **Refresh token rotation** — MUST for public clients

### Phase 3 — Client Side: McpHttpBackend OAuth Dance

McpHttpBackend already handles Bearer; extend for OAuth.

- [ ] **Intercept 401, parse `WWW-Authenticate` + `resource_metadata`** — MUST
- [ ] **Fetch PRM + AS metadata (try RFC 8414 then OIDC Discovery endpoints)** — MUST
- [ ] **PKCE generation (S256)** — MUST; abort if `code_challenge_methods_supported` absent
- [ ] **Open local loopback server for auth-code callback** — MUST (standard MCP public client pattern)
- [ ] **Token exchange (`POST /token` with `code_verifier` + `resource`)** — MUST
- [ ] **Token store (access + refresh, per-server)** — MUST
- [ ] **Token refresh on expiry** — MUST
- [ ] **Step-up auth on 403 `insufficient_scope`** — SHOULD

### Phase 4 — Split AS/RS (Keycloak in CI)

Required by Definition of Done.

- [ ] **JWKS endpoint fetch + cache on RS** — MUST for split-AS path
- [ ] **RS validates Keycloak-issued JWT** (`aud`, `iss`, `exp`, `scope`) — MUST
- [ ] **Token introspection (RFC 7662)** if Keycloak issues opaque tokens — MEDIUM; may be skippable if using JWT

### Add After Validation (v10.4.x or v10.5)

- [ ] **Token revocation endpoint (RFC 7009)** — useful for admin UX; not MUST
- [ ] **Audit log middleware** — design doc says "may need its own milestone"; defer
- [ ] **DPoP (RFC 9449)** — high complexity, not in 2025-11-25 core spec; defer to v10.5+

### Future Consideration (v10.5+)

- [ ] **DPoP (RFC 9449)** — sender-constrained tokens; high complexity; extension territory
- [ ] **Per-tool scope enforcement (SEP-1880)** — open proposal; not in current spec
- [ ] **Device Authorization Grant (RFC 8628)** — for fully headless CI clients with no browser; spec does not require it

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | MCP Spec Level | Priority |
|---------|------------|---------------------|----------------|----------|
| 401 + WWW-Authenticate with resource_metadata | HIGH | LOW | MUST | P1 |
| PRM at /.well-known/oauth-protected-resource | HIGH | LOW | MUST | P1 |
| AS Metadata at /.well-known/oauth-authorization-server | HIGH | MEDIUM | MUST | P1 |
| PKCE S256 | HIGH | MEDIUM | MUST | P1 |
| Auth code flow | HIGH | HIGH | MUST | P1 |
| Resource Indicators (aud/resource binding) | HIGH | MEDIUM | MUST | P1 |
| `aud` claim validation on RS | HIGH | MEDIUM | MUST | P1 |
| Scope enforcement (read/index/admin/subscribe) | HIGH | MEDIUM | MUST (implied) | P1 |
| McpHttpBackend OAuth dance | HIGH | HIGH | MUST (client) | P1 |
| Rotating refresh tokens | HIGH | MEDIUM | MUST (public clients) | P1 |
| Co-located AS/RS (JWT, single binary) | HIGH | HIGH | Project-defined | P1 |
| AGENT_BRAIN_AUTH toggle | HIGH | LOW | Project-defined | P1 |
| AGENT_BRAIN_AUTH=basic LAN bridge | MEDIUM | LOW | Project-defined | P1 |
| 403 + insufficient_scope WWW-Authenticate | MEDIUM | LOW | SHOULD | P1 |
| CIMD client registration | MEDIUM | MEDIUM | SHOULD | P2 |
| DCR (RFC 7591) | MEDIUM | MEDIUM | MAY | P2 |
| Split AS/RS (Keycloak) | HIGH | HIGH | Project-defined (DoD) | P2 |
| JWKS cache on RS | HIGH | MEDIUM | Required for split-AS | P2 |
| Token introspection (RFC 7662) | MEDIUM | MEDIUM | Optional | P2 |
| Step-up auth on 403 | MEDIUM | MEDIUM | SHOULD (client) | P2 |
| Scope hints in 401 WWW-Authenticate | MEDIUM | LOW | SHOULD | P2 |
| agent-brain:subscribe scope guard on subscriptions | MEDIUM | LOW | Project-defined | P2 |
| Token revocation (RFC 7009) | LOW | LOW | Optional | P3 |
| Audit log middleware | LOW | MEDIUM | Project-defined | P3 |
| DPoP (RFC 9449) | MEDIUM | HIGH | Extension (not core spec) | P3 |
| Per-tool scope (SEP-1880) | LOW | HIGH | Draft proposal | P3 |

---

## Sources

- [MCP Authorization Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization) — fetched verbatim 2026-06-14 (HIGH confidence)
- [Context7: /modelcontextprotocol/modelcontextprotocol](https://github.com/modelcontextprotocol/modelcontextprotocol) — High reputation, benchmark 82.9 (HIGH confidence)
- [MCP and OAuth 2.1 — AuthZed](https://authzed.com/learn/mcp-oauth-2-1-authentication) (MEDIUM confidence)
- [RFC 9728 — OAuth 2.0 Protected Resource Metadata](https://datatracker.ietf.org/doc/html/rfc9728) (HIGH confidence — IETF)
- [RFC 8414 — OAuth 2.0 Authorization Server Metadata](https://datatracker.ietf.org/doc/html/rfc8414) (HIGH confidence — IETF)
- [RFC 7591 — OAuth 2.0 Dynamic Client Registration](https://datatracker.ietf.org/doc/html/rfc7591) (HIGH confidence — IETF)
- [RFC 8707 — Resource Indicators for OAuth 2.0](https://www.rfc-editor.org/rfc/rfc8707.html) (HIGH confidence — IETF)
- [RFC 9449 — DPoP](https://datatracker.ietf.org/doc/html/rfc9449) (HIGH confidence — IETF)
- [Client ID Metadata Documents (CIMD) — WorkOS](https://workos.com/blog/client-id-metadata-documents-cimd-oauth-client-registration-mcp) (MEDIUM confidence)
- [What's New In The 2025-11-25 MCP Authorization Spec — Den Delimarsky](https://den.dev/blog/mcp-november-authorization-spec/) (MEDIUM confidence)
- [MCP Specs Update June 2025 — Auth0](https://auth0.com/blog/mcp-specs-update-all-about-auth/) (MEDIUM confidence)
- [SEP-1880: Tool-level scope requirements (open proposal)](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1880) (MEDIUM confidence — proposal, not spec)
- [DPoP in MCP Java SDK issue #887](https://github.com/modelcontextprotocol/java-sdk/issues/887) (LOW confidence — implementation issue, not spec)
- Agent Brain design doc: `docs/roadmaps/mcp/v4-oauth-for-remote.md` (project-authoritative)
- Agent Brain PROJECT.md Current Milestone section (project-authoritative)

---

*Feature research for: OAuth 2.1 Authorization — Agent Brain MCP v4 (v10.4 milestone)*
*Researched: 2026-06-14*
*Spec version: MCP Authorization 2025-11-25*
