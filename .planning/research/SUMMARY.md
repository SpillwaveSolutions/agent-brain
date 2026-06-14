# Project Research Summary

**Project:** Agent Brain v10.4 — MCP v4: OAuth 2.1 + GraphRAG Stability (issue #188)
**Domain:** OAuth 2.1 Authorization Server + Resource Server on FastAPI/MCP Streamable HTTP
**Researched:** 2026-06-14
**Confidence:** HIGH (MCP SDK auth module — Context7 + GitHub source verified; MCP spec 2025-11-25 fetched verbatim; existing codebase read directly)

---

## Executive Summary

Agent Brain v10.4 adds OAuth 2.1 authorization to the remote MCP server (`agent-brain-mcp`). The most critical research finding is that the `mcp` Python SDK (v1.27.2, pin `mcp >= 1.27.2`) already ships all of the OAuth protocol machinery on both sides: `OAuthAuthorizationServerProvider` + `create_auth_routes()` supply the co-located AS endpoints (authorize, token, revoke, DCR, well-known metadata); `RequireAuthMiddleware` + `BearerAuthBackend` supply RS token enforcement; and `OAuthClientProvider` (implementing `httpx.Auth`) handles the full client-side 401-dance including PKCE, PRM discovery, AS metadata discovery, and token refresh. The implementation work is **wire + configure + mint JWTs**, not build-from-scratch. The new library additions are small and targeted: `PyJWT[crypto] ^2.13` (JWT signing and JWKS-cached verification — python-jose is dead), `authlib ^1.7` (OAuth grant handlers for `OAuthAuthorizationServerProvider` implementation if needed), and `pwdlib[argon2]` (password hashing — passlib is unmaintained).

The authoritative spec is **MCP Authorization 2025-11-25**. It changes several design assumptions that older resources get wrong: Dynamic Client Registration (DCR) is now `MAY`/deprecated — Client ID Metadata Documents (CIMD) is the preferred `SHOULD` registration path; PKCE S256 is mandatory and `code_challenge_methods_supported: ["S256"]` MUST appear in AS metadata or compliant clients refuse to proceed; Resource Indicators (RFC 8707) `resource` parameter is `MUST` on both auth and token requests, with `aud` binding and `aud` validation also `MUST` on the RS side. A 2026-07-28 RC (MCP goes stateless — no initialize handshake) is in progress; the design doc must be written and signed off before this spec revision lands, and must acknowledge the staleness risk explicitly.

The dominant security risk for this milestone is not authentication bypass but **authorization confusion**: confused-deputy/token-passthrough (the MCP-to-REST leg must keep `AGENT_BRAIN_API_KEY`; the client's OAuth token MUST NOT be forwarded); `aud` claim omission (the single most common OAuth RS implementation error); well-known discovery endpoints accidentally placed behind auth middleware (deadlocks the OAuth dance before it can start); and per-tool scope enforcement gaps (middleware validates token existence but not per-tool scope, enabling scope escalation within a route). All four are addressed by the converged phase ordering all four researchers independently proposed: design doc + security review gate FIRST, then incremental server-side build, then client-side dance, then split AS topology, then integration tests with a 90% coverage gate.

---

## Key Findings

### Recommended Stack

The existing stack (FastAPI, Uvicorn, mcp SDK, ChromaDB, LlamaIndex, httpx, Click, Poetry) is unchanged. The additions for v10.4 are minimal and targeted.

**Core OAuth additions (`agent-brain-mcp/pyproject.toml`):**
- `mcp >= 1.27.2` (existing, pin version): AS protocol endpoints (`mcp.server.auth`), RS middleware (`RequireAuthMiddleware`, `BearerAuthBackend`), and client OAuth dance (`mcp.client.auth.OAuthClientProvider`) are all included — no additional install required.
- `PyJWT[crypto] ^2.13`: JWT signing for co-located AS token issuance; JWKS-cached verification (`PyJWKClient` with built-in 5-min TTL) for split AS/RS. Replaces python-jose (abandoned 2021, Python 3.10+ compat issues, FastAPI docs migrated away per GitHub discussion #11345).
- `authlib ^1.7.2` (2026-05-06, Python 3.10+): OAuth grant handlers for implementing the 9 abstract methods on `OAuthAuthorizationServerProvider` if the team prefers not to hand-roll them. No DPoP support — matches the "optional/defer" decision.
- `pwdlib[argon2] >=0.2`: Argon2id password hashing for co-located AS user store. Replaces passlib (unmaintained).
- `itsdangerous ^2.2`: CSRF state token signing for the authorization code flow. Already a Starlette transitive dep — verify before adding.

**Dev/test additions:**
- `pytest-httpx >=0.30` or `respx >=0.21`: Mock introspection endpoint and JWKS endpoint HTTP calls in unit tests. Pick one, be consistent.

**What NOT to use:**
- `python-jose` — abandoned since 2021; do not use under any circumstances.
- `passlib` — unmaintained.
- DPoP (RFC 9449) — no production Python library exists (authlib issue #315 open since 2021); defer to v10.5+.
- `fastapi-users` — opinionated coupling; harder to compose with existing structure.

**Shape-specific notes:**
- **Co-located AS/RS:** `PyJWT[crypto]` for local JWT signing and inline verification; custom `GET /.well-known/jwks.json` FastAPI route to expose the RS256 public key (the SDK does NOT provide this endpoint).
- **Split AS/RS (Keycloak in CI):** `PyJWT[crypto]` + `PyJWKClient` for JWKS-cached verification. No Python lib dep on Keycloak itself — it speaks standard OIDC/OAuth 2.1.

### Expected Features

The MCP Authorization 2025-11-25 spec defines what is `MUST`, `SHOULD`, and `MAY`. The features below are mapped to those levels.

**Must have (table stakes — MCP spec MUST, required for spec compliance):**
- `AGENT_BRAIN_AUTH` toggle (`none` / `basic` / `oauth`, default `none`) — preserves all existing behavior; zero regression risk.
- `401 Unauthorized` + `WWW-Authenticate: Bearer resource_metadata=...` on unauthenticated MCP requests.
- `GET /.well-known/oauth-protected-resource` (PRM, RFC 9728) — publicly accessible, no auth, always returns 200.
- `GET /.well-known/oauth-authorization-server` (OASM, RFC 8414) — must include `code_challenge_methods_supported: ["S256"]` or compliant clients refuse to proceed.
- OAuth 2.1 authorization code flow with PKCE S256 — co-located AS via `OAuthAuthorizationServerProvider`.
- Resource Indicators (RFC 8707) `resource` parameter in both `/authorize` and `/token` requests; `aud` claim bound to the MCP server's canonical URI in every issued token.
- `aud` + `exp` + `iss` + `scope` validation on every inbound token in RS middleware.
- Scope enforcement: four scopes (`agent-brain:read`, `agent-brain:index`, `agent-brain:admin`, `agent-brain:subscribe`) enforced per-tool via `scope_guard`, not just per-route.
- `HTTP 403 + WWW-Authenticate: Bearer error="insufficient_scope"` on scope mismatch (not 401 — the token is valid, the scope is insufficient).
- Rotating refresh tokens for public clients (all MCP clients are public per spec).
- `McpHttpBackend` client-side OAuth dance via `OAuthClientProvider` + `FileTokenStorage` (keyed to `state_dir` so Pattern A per-call invocations reuse the cached token rather than re-triggering the full dance on every call).
- `AGENT_BRAIN_AUTH=basic` LAN bridge — formalizes existing `AGENT_BRAIN_API_KEY`/`X-API-Key` path; low lift.

**Should have (CIMD + split AS — SHOULD per spec or required by DoD):**
- Client ID Metadata Documents (CIMD) — preferred registration path over DCR; AS fetches `client_id` URL to get client metadata JSON.
- Split AS/RS deployment with Keycloak in CI — `JwksTokenVerifier` using `PyJWKClient` with 5-min TTL + `kid`-miss on-demand refresh.
- Step-up authorization on `403 insufficient_scope` — client re-initiates with broader scope set.
- Scope hints (`scope=agent-brain:read`) in the 401 `WWW-Authenticate` header.
- `agent-brain:subscribe` scope guard on existing SUB-01..05 subscription machinery.

**Defer to v2+:**
- Dynamic Client Registration (DCR, RFC 7591) — now `MAY`/deprecated in 2025-11-25 spec; ship as CIMD fallback at most; consider omitting entirely for self-hosted single-user shape.
- Token revocation endpoint (RFC 7009) — admin UX convenience; not MUST.
- Audit log middleware — design doc says "may need its own milestone."
- DPoP (RFC 9449) — no production Python library; defer to v10.5+.
- Per-tool scope enforcement via SEP-1880 — open proposal, not in current spec.
- Device Authorization Grant (RFC 8628) — spec does not require it; PKCE + loopback redirect is the standard MCP path.

**Scope-to-tool mapping (source of truth — `_tool_matrix.py` pattern):**

| Scope | Tools Covered |
|-------|---------------|
| `agent-brain:read` | `search_documents`, `explain_result`, `get_corpus_status`, `cache_status`, `list_folders`, `list_file_types`, `list_jobs`, `get_job`, all resources + prompts |
| `agent-brain:index` | `index_folder`, `add_documents`, `inject_documents`, `wait_for_job` |
| `agent-brain:admin` | `cancel_job`, `remove_folder`, `clear_cache` |
| `agent-brain:subscribe` | `corpus://status`, `corpus://folders`, `job://<job_id>` subscriptions |

### Architecture Approach

OAuth 2.1 integration is **additive and mode-gated** — the existing core pipeline (indexing, query, storage, job queue, BM25 hybrid retrieval, GraphRAG) is unchanged. The `AGENT_BRAIN_AUTH` toggle controls which auth dependency is wired at startup. In `none` or `basic` mode, the system behaves exactly as it does today. In `oauth` mode, the Starlette ASGI app gains `RequireAuthMiddleware` wrapping the `/mcp` mount, and the FastAPI server's `verify_bearer_token` dependency is replaced by `verify_oauth_token`. The two auth layers (MCP client to MCP server via OAuth; MCP server to REST API via `AGENT_BRAIN_API_KEY`) remain independent and must not be conflated.

**Two deployment topologies supported:**
1. **Co-located AS/RS** — single binary; `agent-brain-mcp` serves both AS endpoints (`/authorize`, `/token`, `/register`, `/.well-known/*`) and RS endpoints (`/mcp`); JWT-signed tokens verified locally; no external IdP needed.
2. **Split AS/RS** — `agent-brain-mcp` is RS only; PRM points to external IdP (Keycloak/Auth0/Cognito); `JwksTokenVerifier` fetches JWKS from IdP with 5-min TTL cache + `kid`-miss on-demand refresh.

**Major components:**
1. `agent_brain_mcp/oauth/` (NEW MODULE) — `provider.py` (`OAuthAuthorizationServerProvider` full impl), `token_store.py` (in-memory stores for auth codes, access tokens, refresh tokens), `client_registry.py` (DCR/CIMD registry), `verifiers.py` (`JwksTokenVerifier` + `IntrospectionTokenVerifier`), `token_storage.py` (`FileTokenStorage` + `InMemoryTokenStorage` for `McpHttpBackend`), `metadata.py` (PRM + OASM route builders).
2. `agent_brain_mcp/security/scope_guard.py` (NEW) — `require_scope(scope)` callable; reads `request.state.auth.scopes` (populated by `BearerAuthBackend`); raises `McpError(InvalidRequest)` if scope is absent; no-op in `none`/`basic` modes.
3. `agent_brain_server/api/security.py` (MODIFY) — adds `verify_oauth_token` FastAPI dependency and `get_auth_dependency()` dispatch function that returns exactly ONE dependency based on `AGENT_BRAIN_AUTH` mode (mutually exclusive — no double-auth).
4. `agent_brain_mcp/http.py` (MODIFY) — `build_asgi_app()` accepts `auth_mode`, `token_verifier`, `oauth_routes`; in `oauth` mode wraps the Starlette app with `RequireAuthMiddleware`; mounts well-known routes BEFORE the middleware wrapper (publicly accessible — this ordering is critical).
5. `agent_brain_mcp/client.py` / `McpHttpBackend` (MODIFY) — passes `OAuthClientProvider` to `streamablehttp_client` via `auth=` kwarg; uses `FileTokenStorage` keyed to `state_dir` for token persistence across Pattern A per-call invocations.

**Critical architectural constraint:** The SDK does NOT provide a `GET /.well-known/jwks.json` endpoint. The co-located AS must add a custom FastAPI route that exposes the RS256 public key. This must be mounted outside auth middleware (publicly accessible).

**Critical integration boundary:** The MCP-to-REST API leg continues to use `AGENT_BRAIN_API_KEY` (static Bearer). The OAuth access token from the MCP client is consumed and validated at the MCP server boundary only; it MUST NOT be forwarded to `agent-brain-server`. These two auth layers are architecturally independent.

### Critical Pitfalls

The 13 pitfalls documented in PITFALLS.md converge on categories that roadmap phases must address:

1. **Missing `aud` claim validation + Missing Resource Indicators (Pitfalls 1 + 3)** — These are twins. The RS must validate `aud` equals the canonical MCP server URI on every inbound token; the AS must bind `aud` to the `resource` parameter in every issued JWT; `McpHttpBackend` must include `resource=<canonical-uri>` in both `/authorize` and `/token` requests. Omitting either check enables cross-service token reuse. The canonical URI must derive from a single `AGENT_BRAIN_OAUTH_RESOURCE` setting — never hard-coded, never with trailing-slash inconsistency. Address in: design doc (canonical URI config), AS implementation, RS middleware, and contract tests.

2. **Confused deputy / token passthrough (Pitfall 2)** — The `AGENT_BRAIN_API_KEY` forwarding on the MCP-to-REST leg must be preserved exactly as it is today. Any code that extracts the inbound OAuth Bearer token and sets it on the outgoing REST call is a hard spec violation. Address in: design doc data-flow diagram; integration test that asserts `AGENT_BRAIN_API_KEY` is on the MCP-to-REST leg and the OAuth token is not.

3. **Well-known and AS endpoints behind auth middleware (Pitfalls 5 + 10)** — `/.well-known/oauth-protected-resource`, `/.well-known/oauth-authorization-server`, `/authorize`, `/token`, `/register` MUST all be publicly accessible without a Bearer token. The correct mount order: well-known routes are added to the Starlette `routes` list before the `Starlette` app instance is wrapped with `RequireAuthMiddleware`. The first automated test to write is `curl /.well-known/oauth-protected-resource` without a token returning 200. Block implementation from proceeding until this passes.

4. **PKCE S256-only enforcement (Pitfall 4)** — The co-located AS must advertise `code_challenge_methods_supported: ["S256"]` in OASM and reject any authorization request with `code_challenge_method=plain` or with the field absent. Compliant MCP clients (including the SDK's `OAuthClientProvider`) WILL refuse to proceed if this field is absent from OASM. Verify in contract tests before any end-to-end flow test.

5. **FileTokenStorage required for McpHttpBackend Pattern A + SDK refresh-token gap (Pitfall — Pattern A)** — `McpHttpBackend` uses Pattern A (fresh subprocess/client per call). In-memory `TokenStorage` is discarded on each call, re-triggering the full browser OAuth dance on every MCP tool invocation. `FileTokenStorage` keyed to `state_dir/mcp-oauth-tokens.json` (chmod 0o600) must be wired from the start. SDK PR #2039 (refresh-token support may be incomplete) is open as of June 2026 — implement `FileTokenStorage` defensively.

6. **MCP spec staleness meta-pitfall** — The spec has gone through four substantively different revisions since 2024. A 2026-07-28 RC may introduce stateless changes (no initialize handshake) affecting session-based auth. Re-fetch the live spec at `https://modelcontextprotocol.io/specification/draft/basic/authorization` before design sign-off. Cite the spec version in the design doc. Address in: design doc phase (mandatory).

---

## Implications for Roadmap

All four researchers independently converged on the same phase ordering. The ordering is driven by hard dependencies (PRM discovery must exist before client can start the dance; AS must issue tokens before RS can validate them; working AS+RS must exist before `McpHttpBackend` can be tested end-to-end) and by the DoD requirement for a security review gate before any implementation code.

### Phase 1: Design Doc + Security Review Gate

**Rationale:** The DoD explicitly requires a design doc and independent security review before implementation. Spec-level decisions made wrong here (canonical URI format, scope hierarchy, token TTLs, DCR vs. CIMD vs. pre-registration, DPoP decision) are expensive to reverse in later phases. The 2026-07-28 RC may also change assumptions; this phase is the right time to track that.
**Delivers:** Approved design doc covering: threat model, topology comparison (co-located vs. split), scope-to-tool mapping (source of truth), token lifecycle (15-min access / 30-day refresh), canonical URI contract (`AGENT_BRAIN_OAUTH_RESOURCE`), DCR policy (MAY — defer or CIMD-only), DPoP decision (defer to v10.5+), AS/RS data-flow diagram explicitly showing where OAuth tokens terminate and where `AGENT_BRAIN_API_KEY` continues. Security review sign-off is a gate before Phase 2 begins.
**Addresses:** Pitfalls 2 (confused deputy), 5 (AS/RS co-location confusion), 7 (DCR abuse policy), meta-pitfall (spec staleness).
**Avoids:** Starting implementation on a misunderstood spec; conflating OAuth token forwarding with API key forwarding.
**Research flag:** Mandatory spec re-read before sign-off; check 2026-07-28 RC status.

### Phase 2: Settings Foundation + PRM/OASM Public Endpoints

**Rationale:** PRM is the root of all OAuth discovery. Everything downstream depends on the client being able to fetch PRM and OASM without authentication. Building and verifying these two routes before adding any auth enforcement proves the configuration is correct and eliminates the deadlock-before-start failure mode.
**Delivers:** `AGENT_BRAIN_AUTH` toggle in settings; `AGENT_BRAIN_OAUTH_RESOURCE`, JWKS/introspect URI settings; `GET /.well-known/oauth-protected-resource` returning 200 without a token; `GET /.well-known/oauth-authorization-server` with `code_challenge_methods_supported: ["S256"]`; startup gate that validates OAuth config at boot; `agent_brain_mcp/oauth/metadata.py` (`build_prm_route()`, `build_oasm_route()`); `http.py` mount order with well-known routes outside auth middleware.
**Uses:** `itsdangerous` (state signing), `mcp.server.auth.settings.AuthSettings`
**Addresses:** Pitfalls 5 + 10 (well-known endpoints unauthenticated); Pitfall 4 (PKCE advertisement in OASM).
**Contract test (must pass before Phase 3):** `curl /.well-known/oauth-protected-resource` without token returns 200; `curl /.well-known/oauth-authorization-server` without token returns 200 with `code_challenge_methods_supported: ["S256"]`.
**Research flag:** Standard patterns; no additional research needed.

### Phase 3: Co-Located AS (Topology A) + RS Middleware

**Rationale:** The RS (`RequireAuthMiddleware`) cannot be meaningfully tested until the AS is issuing tokens. Building them together in this phase enables immediate end-to-end unit tests of the token issuance → validation loop. The `get_auth_dependency()` dispatch ensures `basic` and `oauth` are mutually exclusive on the request path — no double-auth.
**Delivers:** Full `OAuthAuthorizationServerProvider` implementation (`oauth/provider.py`); in-memory token store (`oauth/token_store.py`); client registry (`oauth/client_registry.py`); JWT signing with `PyJWT[crypto]` RS256; custom `GET /.well-known/jwks.json` route; `RequireAuthMiddleware` + `BearerAuthBackend` wired in `http.py` for `oauth` mode; `verify_oauth_token` + `get_auth_dependency()` in `agent-brain-server`'s `security.py`; all FastAPI routers switched to `get_auth_dependency()`.
**Uses:** `mcp.server.auth.OAuthAuthorizationServerProvider`, `create_auth_routes()`, `RequireAuthMiddleware`, `BearerAuthBackend`; `PyJWT[crypto]`; `authlib` (grant handlers inside provider impl, optional); `pwdlib[argon2]` (user store if co-located AS has user auth).
**Addresses:** Pitfall 1 (`aud` validation in RS middleware); Pitfall 3 (Resource Indicators `resource` param + `aud` binding in AS); Pitfall 4 (PKCE S256 enforcement in AS); Pitfall 12 (static Bearer rejected in oauth mode).
**Research flag:** SDK `OAuthAuthorizationServerProvider` 9-method interface — verified via GitHub source (HIGH confidence). Authlib AS grant handlers — MEDIUM confidence; may need targeted implementation research if team uses Authlib route.

### Phase 4: McpHttpBackend Client-Side OAuth Dance

**Rationale:** The client dance can only be tested against a real working AS (Phase 3). `OAuthClientProvider` is already in the SDK; this phase is wiring it into `McpHttpBackend` and implementing `FileTokenStorage` to prevent the Pattern A token re-trigger problem.
**Delivers:** `OAuthClientProvider` wired into `McpHttpBackend` via `streamablehttp_client(auth=provider)`; `FileTokenStorage` (chmod 0o600, keyed to `state_dir/mcp-oauth-tokens.json`); `InMemoryTokenStorage` (for tests); loopback callback server for authorization code capture; `_open_browser_redirect` handler; token refresh on expiry; step-up re-auth on `403 insufficient_scope`.
**Uses:** `mcp.client.auth.OAuthClientProvider`, `mcp.shared.auth.OAuthClientMetadata`; `FileTokenStorage` (new, `oauth/token_storage.py`).
**Addresses:** Pattern A per-call token persistence; SDK PR #2039 refresh-token gap (defensive implementation); Pitfall 13 (`iss` validation in callback handler — verify SDK handles this, add defensively if not).
**Avoids:** In-memory storage that re-triggers the full OAuth dance (browser redirect, user interaction) on every MCP tool call.
**Research flag:** SDK PR #2039 status — verify before Phase 4 sign-off; if incomplete, implement defensive token refresh in `FileTokenStorage`.

### Phase 5: Per-Tool Scope Enforcement

**Rationale:** Scope enforcement at the tool level requires the full token validation stack (Phases 3+4) to be working so the enforcement is testable. Adding scope guards before Phase 3 yields untestable code. Scope mismatch must return 403 (insufficient scope) not 401 (invalid token) — correct HTTP semantics signal to the client that it needs to step-up, not re-authenticate.
**Delivers:** `agent_brain_mcp/security/scope_guard.py` (`require_scope(scope)` callable); scope guards on all 16 tools and subscription handlers; `TOOL_SCOPE_REQUIREMENTS` mapping as the `_tool_matrix.py` SOT; `403 + WWW-Authenticate: Bearer error="insufficient_scope"` returned on scope mismatch.
**Addresses:** Pitfall 11 (scope escalation — read-only token cannot call admin tools); 4-scope hierarchy enforcement across all 16 tools.
**Research flag:** Standard patterns; no additional research needed.

### Phase 6: Split AS/RS (Topology B — Keycloak in CI)

**Rationale:** The split topology reuses the Phase 3 middleware stack — only the `TokenVerifier` implementation changes. Adding it once Topology A is fully tested minimizes risk and isolates Keycloak CI complexity from earlier phases.
**Delivers:** `JwksTokenVerifier` (`oauth/verifiers.py`) — `PyJWKClient` with 5-min TTL + `kid`-miss on-demand refresh + jitter; `IntrospectionTokenVerifier` (fallback for opaque tokens); `http.py` wiring for topology selection; Keycloak Docker container in CI with dedicated realm (not `master`); end-to-end test that Keycloak-issued JWT is accepted by RS.
**Uses:** `PyJWT[crypto]` + `PyJWKClient`; Keycloak (Docker in CI — no Python lib dep).
**Addresses:** Pitfall 6 (JWKS rotation cache stampede — `kid`-miss refresh + jitter on cache TTL); Pitfall 9 (clock skew — `leeway=30s` in JWT validation).
**Research flag:** Keycloak realm configuration for RFC 8707 Resource Indicators — must be explicitly enabled per-client in Keycloak 22+; verify before CI setup.

### Phase 7: Integration Tests + 90% Coverage Gate

**Rationale:** DoD requires 90% coverage on `agent_brain_mcp/oauth/` and a passing integration test suite including Keycloak. This phase is the validation gate before v10.4 ships.
**Delivers:** Full E2E test: 401 challenge to PRM discovery to OASM discovery to PKCE dance to tool call; token refresh path; scope boundary tests for all 16 tools (read-only token + admin tool call returns 403); Topology B: Keycloak-issued JWT accepted; "Looks Done But Isn't" checklist from PITFALLS.md fully automated; coverage gate at 90% on `agent_brain_mcp/oauth/`.
**Addresses:** All 13 pitfalls verified by automated tests; DoD coverage requirement.
**Research flag:** Standard patterns; `pytest-httpx` or `respx` for mocking HTTP endpoints.

### Phase Ordering Rationale

- **Design doc first** — DoD requirement; spec decisions affect everything downstream. The 2026-07-28 RC risk makes this especially important.
- **PRM/OASM second** — These are the root of OAuth discovery; nothing else can work until they return 200 without a token.
- **Co-located AS/RS third** — The RS cannot be tested without the AS issuing tokens; building them together enables fast feedback.
- **Client dance fourth** — Requires a working AS to dance against; cannot be tested in isolation.
- **Per-tool scope enforcement fifth** — Requires full token validation stack to be testable.
- **Split AS/RS sixth** — Reuses the Phase 3 middleware stack; Keycloak CI complexity is isolated to this phase.
- **Integration tests last** — Validates the full stack end-to-end against the DoD.

### Research Flags

**Needs research during planning:**
- **Pre-Phase 1:** Re-fetch live MCP Authorization spec (`https://modelcontextprotocol.io/specification/draft/basic/authorization`) before design sign-off; verify 2026-07-28 RC status and whether it affects session-based auth assumptions.
- **Phase 3 (Co-located AS):** Authlib AS grant handlers for `OAuthAuthorizationServerProvider` implementation — MEDIUM confidence; targeted research recommended if team chooses Authlib route vs. hand-rolling the 9 abstract methods.
- **Phase 4 (McpHttpBackend):** SDK PR #2039 (refresh-token support) status — verify before implementation; build `FileTokenStorage` defensively regardless of PR status.
- **Phase 6 (Keycloak CI):** RFC 8707 Resource Indicators in Keycloak 22+ must be explicitly enabled per-client; verify configuration before CI setup.

**Standard patterns (skip additional research):**
- **Phase 2 (Settings + PRM/OASM):** RFC 9728 and RFC 8414 are canonical, stable; SDK `AuthSettings` verified via source.
- **Phase 5 (Scope enforcement):** Standard FastAPI dependency injection pattern; `scope_guard.py` is pure policy logic with no external dependencies.
- **Phase 7 (Integration tests):** Standard `pytest-httpx`/`respx` patterns; well-documented in FastAPI ecosystem.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | `mcp` SDK auth module verified via GitHub source + Context7; `PyJWT` + `authlib` versions confirmed via PyPI; python-jose abandonment confirmed via FastAPI GitHub discussion #11345; DPoP gap confirmed via authlib issue #315 (open since 2021) |
| Features | HIGH | Primary source: MCP Authorization spec 2025-11-25 fetched verbatim 2026-06-14; secondary: Context7 `/modelcontextprotocol/modelcontextprotocol` (High reputation, benchmark 82.9); scope-to-tool mapping derived from existing 16-tool surface |
| Architecture | HIGH | Existing codebase read directly (security.py, main.py, settings.py, http.py, client.py, security/__init__.py); SDK mount-path issues verified via GitHub issues #1751 and #1400; Pattern A per-call concern verified via multiple sources |
| Pitfalls | MEDIUM-HIGH | Spec sections: HIGH (fetched current spec); ecosystem patterns: MEDIUM (multiple corroborating sources); JWKS rotation patterns and refresh token race conditions: MEDIUM (standard OAuth literature) |

**Overall confidence:** HIGH

### Gaps to Address

- **SDK PR #2039 (refresh-token gap):** The `OAuthClientProvider`'s refresh-token support may be incomplete as of June 2026. Build `FileTokenStorage` defensively with explicit refresh-token handling. Verify PR status before Phase 4 implementation begins.

- **2026-07-28 RC (MCP stateless migration):** The RC removes the initialize handshake and may introduce changes affecting session-based auth. This gap must be resolved during Phase 1 (design doc) before implementation begins. If the RC has landed and is stable, update the design doc to reflect the stateless model.

- **CIMD SSRF protection:** CIMD requires the AS to fetch the `client_id` URL to get client metadata. The AS must validate the URL against an allowlist of trusted domains to prevent SSRF. The exact mitigation approach (allowlist implementation) needs a decision during Phase 1 design.

- **Keycloak RFC 8707 Resource Indicators configuration:** Must be explicitly enabled per-client in Keycloak 22+; the exact configuration steps should be verified during Phase 6 planning before CI setup.

- **Token store persistence (in-memory only for co-located AS):** The in-memory token store is sufficient for single-user self-hosted use. If the agent-brain process restarts, all sessions are invalidated. This is a known trade-off — document explicitly in the design doc so operators are not surprised.

---

## Sources

### Primary (HIGH confidence)
- MCP Authorization Specification 2025-11-25 — `https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization` — fetched verbatim 2026-06-14; scope MUST/SHOULD/MAY levels, Resource Indicators, PKCE S256 requirement, CIMD vs. DCR priority order
- `/modelcontextprotocol/python-sdk` Context7 — verified `OAuthClientProvider`, `TokenVerifier`, `AuthSettings`, `OAuthAuthorizationServerProvider` class shapes; High reputation source
- `github.com/modelcontextprotocol/python-sdk/blob/main/src/mcp/server/auth/provider.py` — confirmed 9 abstract methods on `OAuthAuthorizationServerProvider`
- `deepwiki.com/modelcontextprotocol/python-sdk/8.4-oauth-authentication-flow-example` — confirmed full client-side OAuth dance in `OAuthClientProvider.async_auth_flow()`
- `pypi.org/project/mcp/` — confirmed current stable version is 1.27.2 (released 2026-05-29)
- `pyjwt.readthedocs.io` — confirmed PyJWT 2.13.0, `PyJWKClient` with 5-min TTL cache
- `pypi.org/project/Authlib/` — confirmed Authlib 1.7.2, released 2026-05-06, Python 3.10+
- `github.com/fastapi/fastapi/discussions/11345` — confirmed python-jose abandoned, FastAPI docs migrated to PyJWT
- RFC 9728, RFC 8414, RFC 7591, RFC 8707, RFC 9449 (IETF canonical specifications)
- Existing codebase (read directly): `agent_brain_server/api/security.py`, `agent_brain_server/api/main.py`, `agent_brain_server/config/settings.py`, `agent_brain_mcp/http.py`, `agent_brain_mcp/client.py`, `agent_brain_mcp/security/__init__.py`, `docs/roadmaps/mcp/v4-oauth-for-remote.md`, `.planning/PROJECT.md`

### Secondary (MEDIUM confidence)
- `github.com/modelcontextprotocol/python-sdk/issues/1751` — mount-path well-known route issue; confirmed active
- `github.com/modelcontextprotocol/python-sdk/issues/1400` — PRM URL mismatch issue
- `github.com/authlib/authlib/issues/315` — DPoP feature request open since 2021; confirmed not implemented
- `docs.authlib.org/en/v1.7.0/upgrades/changelog.html` — no DPoP support in 1.7.0+
- Obsidian Security: "When MCP Meets OAuth" — confused-deputy and token passthrough pitfalls
- WorkOS: "DCR in MCP" + "MCP 2025-11-25 spec update" — CIMD preferred over DCR; DCR demotion to deprecated/backwards-compat
- Aaron Parecki: "Client Registration and Enterprise Management in the November 2025 MCP Authorization Spec"
- SecureCoders blog: refresh-token gap in MCP CLI clients (SDK PR #2039 open as of June 2026)
- RFC 9700 — Best Current Practice for OAuth 2.0 Security (IETF, Jan 2025)
- OWASP OAuth 2.0 Cheat Sheet

### Tertiary (LOW confidence)
- DPoP tracking in `modelcontextprotocol/java-sdk` issue #887 — implementation interest confirmed; production Python library status is still none
- SEP-1880 (per-tool scope proposal) — open proposal, not in 2025-11-25 spec; cite only as "future consideration"

---

*Research completed: 2026-06-14*
*Spec version: MCP Authorization 2025-11-25*
*Ready for roadmap: yes*
