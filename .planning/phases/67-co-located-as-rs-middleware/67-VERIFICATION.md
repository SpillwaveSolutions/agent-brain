---
phase: 67-co-located-as-rs-middleware
verified: 2026-06-15T02:30:00Z
status: passed
score: 5/5 must-haves verified
---

# Phase 67: Co-Located AS + RS Middleware — Verification Report

**Phase Goal:** Token issuance and verification work end-to-end in a single binary — an MCP client can complete the authorization-code + PKCE dance against the co-located AS and receive a JWT that the RS validates on every subsequent call.
**Verified:** 2026-06-15T02:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (ROADMAP Phase 67 Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC#1 | Full auth-code + PKCE S256 flow; plain/absent challenge actively REJECTED at the LIVE /authorize route (HTTP 400 invalid_request, "PKCE plain method not supported") against the MOUNTED ASGI app | VERIFIED | `test_oauth_rs_middleware.py::TestLivePkceRejection` — 5 tests assert 400 for plain/method-absent/challenge-absent and NOT-400 for valid S256, against the mounted ASGI app via TestClient |
| SC#2 | RequireAuthMiddleware on /mcp returns 401 + WWW-Authenticate on missing/expired/invalid-signature token; valid token passes through; scope check (#6) NOT enforced (deferred to Phase 68) | VERIFIED | `test_oauth_rs_middleware.py::TestMcpAuthEnforcement` — 4 tests; `http.py` line 506: `required_scopes=[]`; `verifier.py` explicitly documents scope as Phase 68; no scope enforcement found in Phase 67 code |
| SC#3 | Every issued JWT has aud == AGENT_BRAIN_OAUTH_RESOURCE; RS validates aud and rejects mismatches | VERIFIED | `tokens.py::mint_access_token`: `"aud": resource` (line 115); `verifier.py::LocalRs256Verifier`: `audience=self.resource` in `jwt.decode` (line 141); `test_oauth_rs_middleware.py::test_mcp_wrong_aud_token_returns_401` |
| SC#4 | CIMD + static registration both work; CIMD fetch has full SSRF stack: domain allowlist + unconditional private-IP block + DNS-rebinding post-resolution IP re-validation (mandatory test passes) + ~5s timeout | VERIFIED | `registration.py`: `validate_client_id_host`, `is_blocked_ip`, `fetch_client_metadata` with `socket.getaddrinfo` loop (lines 278-298); `test_oauth_cimd_ssrf.py::TestDnsRebindingMitigation::test_allowlisted_hostname_rfc1918_dns_rejected` (MANDATORY test present and passing); `provider.py::register_client`: URL-shaped dispatch to CIMD; static path preserved |
| SC#5 | A valid JWT FAILS the basic static-bearer check; a raw API key PASSES the basic check; modes never cross | VERIFIED | `config.py::verify_basic_bearer` (line 319, `hmac.compare_digest`); `test_oauth_mode_exclusion.py` — 12 tests proving JWT fails basic, API key passes basic, RS verifier rejects API key, get_auth_dependency returns exactly one selector per mode |

**Score: 5/5 truths verified**

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agent-brain-mcp/pyproject.toml` | mcp ^1.27.2 + PyJWT[crypto] + authlib + pwdlib | VERIFIED | `mcp = "^1.27.2"`, `pyjwt = {extras = ["crypto"], version = "^2.13"}`, `authlib = "^1.7.2"`, `pwdlib = {extras = ["argon2"], version = ">=0.2"}` |
| `agent_brain_mcp/oauth/__init__.py` | Package marker | VERIFIED | File exists |
| `agent_brain_mcp/oauth/keys.py` | RS256 keypair generation + JWKS document serialization | VERIFIED | `def generate_rs256_keypair`, `def build_jwks`, `SigningKey` dataclass, `get_or_create_signing_key()` singleton; JWKS output contains kty/use/alg/kid/n/e and NOT d/p/q |
| `agent_brain_mcp/oauth/tokens.py` | JWT minting (RS256) + in-memory token/code store | VERIFIED | `def mint_access_token` with aud=resource, `ACCESS_TOKEN_TTL_SECONDS = 900`, `REFRESH_TOKEN_TTL_SECONDS = 30*24*3600`, `InMemoryTokenStore`, `token_store` module-level singleton |
| `agent_brain_mcp/oauth/provider.py` | OAuthAuthorizationServerProvider impl + PKCE S256-only rejection | VERIFIED | `class AgentBrainAuthServerProvider` (9 methods), `def reject_non_s256_pkce`, exact string "PKCE plain method not supported" (line 94) |
| `agent_brain_mcp/oauth/registration.py` | CIMD fetch with SSRF stack | VERIFIED | `def fetch_client_metadata`, `def is_blocked_ip`, `def validate_client_id_host`, `RegistrationError400`; DNS-rebinding via `socket.getaddrinfo` loop before HTTP fetch |
| `agent_brain_mcp/oauth/verifier.py` | Local RS256 TokenVerifier (sig/exp/nbf/iss/aud) | VERIFIED | `class LocalRs256Verifier` with `async def verify_token`, checks #1-5, returns None on ALL PyJWTError; `build_local_verifier()` factory; Phase 70 seam documented |
| `agent_brain_mcp/http.py` | JWKS route + /authorize PKCE pre-check + create_auth_routes mount + RequireAuthMiddleware wrap of /mcp | VERIFIED | `JWKS_PATH = "/.well-known/jwks.json"` (line 131); `jwks_document` route (line 329); `/authorize` pre-check front-handler via `authorize_pkce_precheck` (line 444); `create_auth_routes()` (line 425); `RequireAuthMiddleware(AuthenticationMiddleware(mcp_asgi_app, BearerAuthBackend(verifier)), required_scopes=[])` (lines 503-508) |
| `agent_brain_mcp/config.py` | get_auth_dependency oauth branch fills NotImplementedError; verify_basic_bearer; AGENT_BRAIN_OAUTH_CLIENT_ID_ALLOWLIST | VERIFIED | `get_auth_dependency()` returns `"oauth-require-auth"` (line 388, no NotImplementedError); `verify_basic_bearer()` (line 319); `resolve_client_id_allowlist()` (line 270); `resolve_signing_key_path()` (line 295) |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `http.py` | `oauth/verifier.py` | `BearerAuthBackend(token_verifier=LocalRs256Verifier(...))` via `build_local_verifier()` | WIRED | `http.py` line 499: `from agent_brain_mcp.oauth.verifier import build_local_verifier`; line 502: `verifier = build_local_verifier(issuer_override=issuer)` |
| `http.py` | `oauth/provider.py::reject_non_s256_pkce` | `/authorize` front-handler calls `reject_non_s256_pkce(request.query_params)` | WIRED | `http.py` line 462: `reject_non_s256_pkce(request.query_params)` inside `authorize_pkce_precheck`; front-route placed BEFORE SDK routes (line 484) |
| `http.py` | `/.well-known/jwks.json` | Auth-exempt Route BEFORE the RequireAuthMiddleware wrap | WIRED | `http.py` line 397: `Route(JWKS_PATH, jwks_document, methods=["GET"])` in `exempt_routes` list; list appended to BEFORE mcp_mount (line 514) |
| `oauth/provider.py` | `oauth/tokens.py::mint_access_token` | `exchange_authorization_code` mints JWT via `mint_access_token` | WIRED | `provider.py` line 523: `access_jwt = mint_access_token(...)` with `resource=authorization_code.resource or self.resource` |
| `oauth/tokens.py` | AGENT_BRAIN_OAUTH_RESOURCE | `aud` claim bound to resource indicator | WIRED | `tokens.py` line 115: `"aud": resource` in claims dict |
| `oauth/verifier.py` | AGENT_BRAIN_OAUTH_RESOURCE | `aud` validation against `resolve_oauth_settings` resource | WIRED | `verifier.py` line 141: `audience=self.resource`; `build_local_verifier()` line 207: `resource, issuer_env = resolve_oauth_settings()` |
| `oauth/provider.py` | `oauth/registration.py::fetch_client_metadata` | `register_client` delegates CIMD fetch via URL-shaped dispatch | WIRED | `provider.py` line 377: `await fetch_client_metadata(client_id, allowlist=allowlist)` inside URL-shaped branch |
| `oauth/registration.py` | `config::resolve_client_id_allowlist` | SSRF allowlist gate | WIRED | `registration.py` calls `validate_client_id_host(client_id_url, allowlist)` where allowlist comes from `resolve_client_id_allowlist()` via `provider.py` |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| OAUTH-04 | 67-01, 67-02 | Co-located AS: auth-code+PKCE S256, PyJWT JWTs, JWKS, via OAuthAuthorizationServerProvider | SATISFIED | `oauth/keys.py`, `oauth/tokens.py`, `oauth/provider.py` implement full AS; JWKS at `JWKS_PATH` (http.py:131); create_auth_routes wired (http.py:425); 81 AS tests passing |
| OAUTH-05 | 67-04 | RS verifies sig/exp/nbf/aud, gated by AGENT_BRAIN_AUTH=oauth, well-known+authorize/token auth-exempt | SATISFIED | `oauth/verifier.py::LocalRs256Verifier` checks #1-5; `http.py` wraps only /mcp mount (lines 503-509); exempt routes list stays outside wrap (lines 388-398); 18 middleware tests pass |
| OAUTH-08 | 67-02, 67-04 | RFC 8707 resource indicators; no upstream token forwarding | SATISFIED | AS half: `provider.py` binds `aud=code.resource` (line 519); RS half: `verifier.py` validates `audience=self.resource` (line 141); REST leg uses `X-API-Key` via `config.py:_resolve_api_key` (no OAuth token forwarding path found) |
| OAUTH-10 | 67-03 | CIMD + static registration; SSRF protection (allowlist + private-IP block + DNS-rebinding check + 5s timeout) | SATISFIED | `registration.py`: 5-control SSRF stack; `provider.py::register_client` URL dispatch; 33 SSRF tests pass including mandatory DNS-rebinding test |

**REQUIREMENTS.md traceability:** All four Phase 67 requirements (OAUTH-04, OAUTH-05, OAUTH-08, OAUTH-10) are marked `[x]` (complete) in REQUIREMENTS.md.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | No placeholder returns, stub handlers, or TODO implementations found | — | — |

**Notes:**
- `required_scopes=[]` in RequireAuthMiddleware (http.py:506) is intentional, documented, and correct for Phase 67 — scope enforcement is Phase 68. This is NOT a stub.
- `get_auth_dependency()` returning `"oauth-require-auth"` string marker (config.py:388) is intentional per the design; http.py owns the actual middleware construction. This is correct design, not a stub.
- No `NotImplementedError`, `TODO`, `FIXME`, `placeholder`, `coming soon`, or `return {}` patterns found in the OAuth implementation files.

---

### Human Verification Required

None. All Phase 67 success criteria are verifiable programmatically and confirmed by the automated test suite.

Items explicitly deferred to later phases (not missing from Phase 67):
- Scope enforcement (Phase 68, OAUTH-06): `required_scopes=[]` placeholder in `RequireAuthMiddleware` is correct
- Client-side OAuth dance (Phase 69, OAUTH-07): `McpHttpBackend` changes not in scope
- Split AS/RS + Keycloak-in-CI + 90% coverage gate (Phase 70, OAUTH-11/12): verifier seam is clean for the swap

---

## Mount-Order Contract Verification

The Phase 66 mount-order test still passes (33/33) with Phase 67 middleware added:

- `tests/test_well_known_routes.py` — 33 passed (confirmed by test run)
- The file comments at line 14 and lines 306/349 explicitly note "Survives Phase 67: when RequireAuthMiddleware wraps the /mcp Mount..."
- Auth-exempt route order in `http.py::build_asgi_app()`: healthz, OASM, PRM, PRM-suffixed, JWKS, then (in oauth mode) /authorize front-handler, SDK AS routes, then /mcp Mount (wrapped or bare)

## Confused-Deputy Invariant Verification

No code path forwards the OAuth token upstream:
- `config.py::_resolve_api_key()` (line 506) resolves `X-API-Key` from env/runtime.json/config.json — no OAuth token involvement
- `config.py::build_backend_client()` (line 598) sets `client.headers["X-API-Key"] = api_key` — static key, not request-scoped
- No code in `http.py`, `provider.py`, `verifier.py`, or `registration.py` sets Authorization/Bearer headers on any outgoing REST call

## Verifier Abstraction for Phase 70

`verifier.py` documents the stable seam at lines 28-31:
```
Phase 70 seam: Keep this class name and verify_token signature stable.
Phase 70 swaps this for JwksTokenVerifier by config without modifying
tests or callers.
```
`build_local_verifier()` is the factory Phase 70 replaces — no interface changes needed.

---

## Test Suite Summary

| Test File | Tests | Result |
|-----------|-------|--------|
| `test_oauth_deps_smoke.py` | 11 | PASS |
| `test_oauth_keys_jwks.py` | 26 | PASS |
| `test_oauth_token_mint.py` | 32 | PASS |
| `test_oauth_authorize_pkce.py` | 23 | PASS |
| `test_oauth_cimd_ssrf.py` | 33 | PASS |
| `test_oauth_rs_verifier.py` | 16 | PASS |
| `test_oauth_rs_middleware.py` | 18 | PASS |
| `test_oauth_mode_exclusion.py` | 12 | PASS |
| `test_well_known_routes.py` (Phase 66 regression) | 33 | PASS |
| **Full MCP suite** | **824** | **PASS (0 failures)** |

Run: `cd agent-brain-mcp && poetry run pytest -q` — 824 passed, 111 deselected (e2e/contract/stress opt-in), 7 warnings.

---

*Verified: 2026-06-15T02:30:00Z*
*Verifier: Claude (gsd-verifier)*
