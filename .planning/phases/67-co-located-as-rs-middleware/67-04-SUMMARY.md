---
phase: 67-co-located-as-rs-middleware
plan: 04
subsystem: auth
tags: [mcp, oauth, jwt, rs256, resource-server, middleware, pkce, jwks, mode-exclusion]

# Dependency graph
requires:
  - phase: 67-co-located-as-rs-middleware
    plan: 02
    provides: "keys.py (SigningKey), tokens.py (mint_access_token), provider.py (AgentBrainAuthServerProvider, reject_non_s256_pkce)"
  - phase: 66-oauth-settings-foundation-prm-oasm-public-endpoints
    plan: 02
    provides: "build_asgi_app routes=[...] list, get_auth_dependency() seam, check_auth_startup_gate()"

provides:
  - "agent_brain_mcp/oauth/verifier.py: LocalRs256Verifier (checks #1-5) + build_local_verifier() factory"
  - "http.py: JWKS_PATH constant + /.well-known/jwks.json route (auth-exempt, SDK gap workaround)"
  - "http.py: /authorize PKCE front-handler (ROADMAP SC#1 live contract) wired before SDK routes"
  - "http.py: create_auth_routes() + AgentBrainAuthServerProvider in oauth mode (auth-exempt above /mcp)"
  - "http.py: RequireAuthMiddleware(AuthenticationMiddleware(mcp_app, BearerAuthBackend), required_scopes=[]) wraps /mcp only"
  - "config.py: get_auth_dependency() oauth branch returns 'oauth-require-auth' (no NotImplementedError)"
  - "config.py: verify_basic_bearer() constant-time AGENT_BRAIN_API_KEY comparison for SC#5 proof"
  - "3 test files: test_oauth_rs_verifier.py (16), test_oauth_rs_middleware.py (18), test_oauth_mode_exclusion.py (12)"
  - "OAUTH-05 + OAUTH-08 RS half complete; ROADMAP SC#1 live contract + SC#5 mode mutual-exclusion proven"

affects:
  - phase-68-scope-enforcement  # require_scope() reads request.state.auth (reachable via required_scopes=[])
  - phase-70-split-as-rs  # LocalRs256Verifier seam → JwksTokenVerifier swap by config in build_local_verifier()

# Tech tracking
tech-stack:
  added:
    - "agent_brain_mcp/oauth/verifier.py (new): LocalRs256Verifier + build_local_verifier()"
    - "config.py: verify_basic_bearer() helper (hmac.compare_digest)"
    - "http.py: BearerAuthBackend + RequireAuthMiddleware + AuthenticationMiddleware (mcp SDK auth)"
    - "http.py: create_auth_routes() + ClientRegistrationOptions (mcp SDK AS routes)"
    - "http.py: AnyHttpUrl (pydantic) for RequireAuthMiddleware resource_metadata_url"
    - "http.py: JWKS_PATH Final constant + jwks_document async handler"
    - "http.py: /authorize PKCE pre-check front-handler (authorize_pkce_precheck)"
  patterns:
    - "TDD RED/GREEN: verifier.py tests written first (16 failing), impl makes them green"
    - "TDD (implicit): mode_exclusion tests written against already-wired SC#5 helpers"
    - "Front-route-first approach for /authorize PKCE pre-check (not ASGI wrap)"
    - "Middleware composition: RequireAuthMiddleware(AuthenticationMiddleware(app, BearerAuthBackend(...)))"
    - "Phase 66 OASM route placed BEFORE create_auth_routes() in list (first-match wins)"
    - "Black line-length 88 + Ruff isort + mypy strict applied to all new files"
    - "Google-style docstrings on all new functions/classes"

key-files:
  created:
    - "agent-brain-mcp/agent_brain_mcp/oauth/verifier.py"
    - "agent-brain-mcp/tests/test_oauth_rs_verifier.py"
    - "agent-brain-mcp/tests/test_oauth_rs_middleware.py"
    - "agent-brain-mcp/tests/test_oauth_mode_exclusion.py"
  modified:
    - "agent-brain-mcp/agent_brain_mcp/http.py (JWKS route + /authorize front-handler + RequireAuthMiddleware)"
    - "agent-brain-mcp/agent_brain_mcp/config.py (get_auth_dependency + verify_basic_bearer)"
    - "agent-brain-mcp/tests/test_mcp_startup_gate.py (update Phase 66 placeholder test to Phase 67 contract)"

key-decisions:
  - "LocalRs256Verifier uses jwt.decode(leeway=30) for checks #2-5; returns None on ALL PyJWTError (never raises)"
  - "Front-route-first (not ASGI-wrap) for /authorize PKCE pre-check: Route('/authorize', precheck) placed BEFORE create_auth_routes() routes in the list; Starlette first-match ensures pre-check always runs"
  - "OASM reconciliation: Phase 66 hand-rolled Route(OASM_PATH, ...) placed FIRST in routes list so first-match wins over the SDK's own /.well-known/oauth-authorization-server route from create_auth_routes(); Phase 66 OASM tests stay green without modification"
  - "Middleware composition order (inside-out): mcp_asgi_app → AuthenticationMiddleware(backend=BearerAuthBackend) → RequireAuthMiddleware(required_scopes=[]) wraps ONLY the /mcp Mount; all other routes stay exempt"
  - "required_scopes=[] in Phase 67 — scope enforcement is Phase 68 (OAUTH-06); token claims reachable at request.state.auth for Phase 68's require_scope() guard"
  - "get_auth_dependency() oauth branch returns 'oauth-require-auth' string marker (replaces NotImplementedError); http.py owns the actual middleware construction at build time"
  - "verify_basic_bearer() added to config.py as a tiny pure helper for SC#5 proof unit tests (avoids subprocess/network; mirrors agent-brain-server security.py pattern without cross-package import)"
  - "/token SDK endpoint returns 401 for missing client_id (application-level auth error, not RequireAuthMiddleware 401); distinguished by absence of 'resource_metadata' in WWW-Authenticate header"

requirements-completed: [OAUTH-05, OAUTH-08]

# Metrics
duration: 27min
completed: 2026-06-15
---

# Phase 67 Plan 04: RS Verifier + Middleware + Mode Exclusion Summary

**LocalRs256Verifier (RS256 checks #1-5, 30s leeway) + JWKS route + /authorize PKCE front-handler + RequireAuthMiddleware wrapping only /mcp + SC#5 mode mutual-exclusion proof — 46 new tests green, 824 MCP tests total, task before-push exits 0**

## Performance

- **Duration:** 27 min
- **Started:** 2026-06-15T01:31:35Z
- **Completed:** 2026-06-15T01:58:46Z
- **Tasks:** 3
- **Files created:** 4 (1 source + 3 test)
- **Files modified:** 3 (http.py, config.py, test_mcp_startup_gate.py)
- **Tests added:** 46 (16 + 18 + 12)

## Accomplishments

### Task 1: LocalRs256Verifier (checks #1-5) (`cb2432e`)

Created `agent_brain_mcp/oauth/verifier.py` with:
- `LocalRs256Verifier`: implements SDK `TokenVerifier` protocol using
  `jwt.decode(token, public_key, algorithms=["RS256"], audience=resource, issuer=issuer, leeway=30)`
- Checks #1-5: signature (#2), exp/nbf with 30s leeway (#3), iss (#4), aud (#5)
- Returns `None` on ALL `PyJWTError` — never raises
- On success: returns `AccessToken(token, client_id, scopes, expires_at, resource)`
- `build_local_verifier(issuer_override=None)` factory reads config + signing key singleton
- Scope check #6 DEFERRED to Phase 68 — explicit comment + `required_scopes=[]` in `RequireAuthMiddleware`
- Phase 70 seam documented: stable `LocalRs256Verifier.verify_token()` interface for `JwksTokenVerifier` swap
- 16 tests: valid/expired/leeway-window/bad-sig/wrong-aud/wrong-iss/malformed/empty

### Task 2: JWKS + /authorize front-handler + RequireAuthMiddleware (`407bce3`)

Modified `agent_brain_mcp/http.py build_asgi_app()`:
1. `JWKS_PATH = "/.well-known/jwks.json"` constant added to `__all__`
2. Auth-exempt `GET /.well-known/jwks.json` route serving `get_or_create_signing_key().jwks_dict`
   (public-only JWKS document, SDK gap workaround)
3. In oauth mode: `AgentBrainAuthServerProvider` + `create_auth_routes()` wired with
   `ClientRegistrationOptions(enabled=True, valid_scopes=4-scopes, default_scopes=["agent-brain:read"])`
4. `/authorize` PKCE front-handler (ROADMAP SC#1 live contract — **the blocker this plan closes**):
   - Calls `reject_non_s256_pkce(request.query_params)` on every GET/POST /authorize
   - Plain/method-absent/challenge-absent → `JSONResponse({"error":"invalid_request",...}, 400)`
   - Valid S256 → delegates to the SDK authorize handler
   - Placed BEFORE `create_auth_routes()` routes in the list (front-route-first approach)
5. `/mcp` Mount wrapped: `RequireAuthMiddleware(AuthenticationMiddleware(mcp_asgi_app, BearerAuthBackend(LocalRs256Verifier)), required_scopes=[])`
6. OASM reconciliation: Phase 66 `Route(OASM_PATH, ...)` placed first so Starlette first-match
   keeps Phase 66 document format; SDK OASM route is present but shadowed

Modified `agent_brain_mcp/config.py`:
- `get_auth_dependency()` oauth branch: replaced `raise NotImplementedError(...)` with `return "oauth-require-auth"`
- Added `verify_basic_bearer(token: str) -> bool` helper using `hmac.compare_digest` for SC#5 proof

18 tests: /mcp 401+WWW-Authenticate, auth-exempt routes (PRM/OASM/healthz/JWKS/token/register),
live PKCE rejection at mounted /authorize (3 reject cases + 1 valid S256 passthrough).
Phase 66 mount-order test (33 tests) still green.

### Task 3: SC#5 Mode Mutual-Exclusion Proof (`6937a34`)

Created `tests/test_oauth_mode_exclusion.py` with 12 tests:
- JWT fails `verify_basic_bearer` (not the shared secret — modes don't cross)
- Raw `AGENT_BRAIN_API_KEY` passes `verify_basic_bearer`
- `LocalRs256Verifier.verify_token(api_key)` → `None` (RS direction also disjoint)
- `get_auth_dependency()` returns exactly one selector per mode:
  `none→None`, `basic→"basic-bearer"`, `oauth→"oauth-require-auth"`

Updated `tests/test_mcp_startup_gate.py`:
- Replaced Phase 66 placeholder test `test_get_auth_dependency_oauth_mode_raises_not_implemented`
  with Phase 67 contract `test_get_auth_dependency_oauth_mode_returns_oauth_selector`

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | LocalRs256Verifier (checks #1-5) | `cb2432e` | oauth/verifier.py, test_oauth_rs_verifier.py |
| 2 | JWKS + PKCE front-handler + middleware | `407bce3` | http.py, config.py, test_oauth_rs_middleware.py |
| 3 | SC#5 mode mutual-exclusion proof | `6937a34` | test_oauth_mode_exclusion.py, test_mcp_startup_gate.py |

## Architecture Decisions

### /authorize PKCE Pre-Check: Front-Route-First (not ASGI-wrap)

**Approach chosen: `Route("/authorize", authorize_pkce_precheck, methods=["GET","POST"])` placed BEFORE `create_auth_routes()` output in the `routes=[...]` list.**

Starlette's first-match semantics mean the `authorize_pkce_precheck` route always wins for `/authorize` requests. The handler:
1. Calls `reject_non_s256_pkce(request.query_params)` — raises `AuthorizeError` for bad PKCE
2. On rejection: returns `JSONResponse({"error":"invalid_request",...}, 400)` immediately
3. On valid S256: delegates to `sdk_authorize_handler(request)` (the SDK's `/authorize` endpoint)

The SDK's own `/authorize` Route from `create_auth_routes()` is still present in the list (at a higher index) but is never reached for `/authorize` paths because the pre-check Route matches first.

Alternative considered: ASGI-wrap (wrapping the SDK's authorize handler with an ASGI middleware that inspects query params). Rejected because: (1) extracting the SDK handler from the Routes list is simpler, (2) front-route-first is transparent in the routes list (visible at inspection time), (3) no need to build an ASGI wrapper class.

### OASM Reconciliation: Phase 66 Handler Wins via First-Match

Phase 66 ships a hand-rolled OASM handler serving the `oauth_metadata.build_oasm_document()` format.
Phase 67's `create_auth_routes()` also emits a `/.well-known/oauth-authorization-server` route.

Decision: keep BOTH in the list, Phase 66 handler FIRST. Starlette first-match ensures the Phase 66 handler always wins for `OASM_PATH`. The SDK route is present but unreachable for that path. This:
- Keeps all 33 Phase 66 OASM tests green without any modifications
- Avoids deduplication complexity
- The two documents are consistent (same endpoint URLs)

### Middleware Composition (Inside-Out)

```
RequireAuthMiddleware(
    AuthenticationMiddleware(
        mcp_asgi_app,
        backend=BearerAuthBackend(
            token_verifier=LocalRs256Verifier(public_key, issuer, resource)
        )
    ),
    required_scopes=[],               # Phase 68 fills this
    resource_metadata_url=AnyHttpUrl(resource_env),  # PRM URL in 401 WWW-Authenticate
)
```

Wraps ONLY the `/mcp` Mount app — not the whole Starlette app. The remaining routes (`/healthz`, `/.well-known/*`, `/authorize`, `/token`, `/register`) are auth-exempt in the `routes=[...]` list above the Mount.

## Phase 68 / Phase 70 Handoff

### Deferred to Phase 68 (OAUTH-06 — scope enforcement)
- Scope check #6 (`required_scopes=[]` placeholder in `RequireAuthMiddleware`)
- Token claims are reachable at `request.state.auth` (the SDK `AccessToken` object) for Phase 68's `require_scope()` guard
- The 4-scope set is already in `_OAUTH_SCOPES` constant in `http.py`

### Deferred to Phase 70 (OAUTH-11/12 — split AS/RS)
- Full e2e session round-trip (driving a complete MCP session with a valid token)
- `JwksTokenVerifier` swap: Phase 70 replaces `LocalRs256Verifier` by changing `build_local_verifier()` in `http.py` to return a `JwksTokenVerifier` — no changes to `verifier.py` interface or tests needed
- The `LocalRs256Verifier` class name and `verify_token()` signature are stable (documented in the module)
- JWKS endpoint (`/.well-known/jwks.json`) is already serving the public key for Phase 70 to fetch

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] /token returns 401 for missing client_id (SDK application-level auth)**
- **Found during:** Task 2 test run
- **Issue:** Test `test_token_route_accessible_without_token` asserted `status_code != 401` but the SDK `/token` handler returns HTTP 401 (unauthorized_client) when `client_id` is missing in the request — this is the SDK's own client authentication, not `RequireAuthMiddleware`
- **Fix:** Updated test to distinguish `RequireAuthMiddleware` 401s (have `resource_metadata` in `WWW-Authenticate`) from SDK application-level 401s (do not have `resource_metadata`); asserts `"resource_metadata" not in www_auth` instead
- **Files modified:** `tests/test_oauth_rs_middleware.py`
- **Commit:** `407bce3`

**2. [Rule 1 - Test] Phase 66 placeholder test expected NotImplementedError (now filled)**
- **Found during:** Task 3 + `task before-push`
- **Issue:** `test_get_auth_dependency_oauth_mode_raises_not_implemented` in `test_mcp_startup_gate.py` expected `NotImplementedError("...Phase 67...")` — Phase 67 Plan 04 fills this seam, so the test fails
- **Fix:** Updated test to `test_get_auth_dependency_oauth_mode_returns_oauth_selector` asserting `result == "oauth-require-auth"`
- **Files modified:** `tests/test_mcp_startup_gate.py`
- **Commit:** `6937a34`

## Self-Check

### Created files exist:
- `agent-brain-mcp/agent_brain_mcp/oauth/verifier.py` - FOUND (contains `class LocalRs256Verifier`, `def verify_token`, `def build_local_verifier`)
- `agent-brain-mcp/tests/test_oauth_rs_verifier.py` - FOUND (16 tests)
- `agent-brain-mcp/tests/test_oauth_rs_middleware.py` - FOUND (18 tests)
- `agent-brain-mcp/tests/test_oauth_mode_exclusion.py` - FOUND (12 tests)

### Modified files:
- `agent-brain-mcp/agent_brain_mcp/http.py` - FOUND (contains `JWKS_PATH`, `RequireAuthMiddleware`, `BearerAuthBackend`, `create_auth_routes`, `reject_non_s256_pkce`)
- `agent-brain-mcp/agent_brain_mcp/config.py` - FOUND (contains `verify_basic_bearer`, `oauth-require-auth` in `get_auth_dependency`)
- `agent-brain-mcp/tests/test_mcp_startup_gate.py` - FOUND (updated placeholder test)

### Commits exist:
- `cb2432e` (Task 1) - FOUND
- `407bce3` (Task 2) - FOUND
- `6937a34` (Task 3) - FOUND

### QA gates:
- `task before-push` exits 0 (824 passed, 89% coverage, 0 lint errors, 0 mypy errors)
- `task pr-qa-gate` exits 0 (824 passed, 88.87% coverage ≥ 80% gate)

## Self-Check: PASSED

---
*Phase: 67-co-located-as-rs-middleware*
*Completed: 2026-06-15*
