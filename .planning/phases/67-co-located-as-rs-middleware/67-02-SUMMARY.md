---
phase: 67-co-located-as-rs-middleware
plan: 02
subsystem: auth
tags: [mcp, oauth, jwt, pyjwt, rs256, jwks, pkce, authorization-server, in-memory-store]

# Dependency graph
requires:
  - phase: 67-co-located-as-rs-middleware
    plan: 01
    provides: "mcp ^1.27.2 (OAuthAuthorizationServerProvider, AuthorizationCode, RefreshToken, AccessToken, AuthorizeError), PyJWT[crypto] 2.13.0, cryptography (via PyJWT[crypto])"

provides:
  - "agent_brain_mcp/oauth/ package: keys.py (RS256 keypair + JWKS), tokens.py (JWT minting + store), provider.py (9-method provider + PKCE gate)"
  - "Boot-time in-memory RS256 keypair (2048-bit) with stable JWKS for the process lifetime"
  - "RS256 JWT access tokens with full claim set (iss/aud/exp/nbf/iat/jti/scope/client_id)"
  - "InMemoryTokenStore: single-use auth codes + access token store + rotating 30-day refresh"
  - "AgentBrainAuthServerProvider: 9-method OAuthAuthorizationServerProvider concrete impl"
  - "reject_non_s256_pkce(Mapping[str,str]) -> None with exact error_description stable contract"
  - "config.py: resolve_client_id_allowlist() + resolve_signing_key_path() (Phase-66-consistent idiom)"
  - "81 tests across three test files (test_oauth_keys_jwks.py, test_oauth_token_mint.py, test_oauth_authorize_pkce.py)"

affects:
  - 67-03-plan  # RS verification middleware reads SigningKey + AccessToken from this plan
  - 67-04-plan  # create_auth_routes() + reject_non_s256_pkce wiring uses provider from this plan
  - phase-68-scope-enforcement  # scope claim is in the JWT; require_scope() reads request.state.auth
  - phase-70-split-as-rs  # JwksTokenVerifier swaps local verifier; keep verifier seam clean

# Tech tracking
tech-stack:
  added:
    - "agent_brain_mcp/oauth/ package (new sub-package: keys, tokens, provider, __init__)"
    - "cryptography RSAPrivateKey/RSAPublicKey (via PyJWT[crypto] already added in Plan 01)"
    - "pydantic AnyUrl (for OAuthClientInformationFull redirect_uris type safety)"
  patterns:
    - "TDD RED/GREEN applied: 3 test files written before implementation, confirmed failing, then made green"
    - "SigningKey dataclass as process-lifetime singleton (get_or_create_signing_key() caches in module global)"
    - "OAuthClientInformationFull.client_id is str|None — _require_client_id() guard pattern"
    - "Black line-length 88 + Ruff isort applied to all new files"
    - "Google-style docstrings + mypy strict on all new files"

key-files:
  created:
    - "agent-brain-mcp/agent_brain_mcp/oauth/__init__.py"
    - "agent-brain-mcp/agent_brain_mcp/oauth/keys.py"
    - "agent-brain-mcp/agent_brain_mcp/oauth/tokens.py"
    - "agent-brain-mcp/agent_brain_mcp/oauth/provider.py"
    - "agent-brain-mcp/tests/test_oauth_keys_jwks.py"
    - "agent-brain-mcp/tests/test_oauth_token_mint.py"
    - "agent-brain-mcp/tests/test_oauth_authorize_pkce.py"
  modified:
    - "agent-brain-mcp/agent_brain_mcp/config.py (resolve_client_id_allowlist + resolve_signing_key_path added)"

key-decisions:
  - "SigningKey is a @dataclass (not NamedTuple) so __post_init__ can populate jwks_dict; singleton cached in module-level _signing_key_singleton"
  - "OAuthClientInformationFull.redirect_uris requires at least 1 AnyUrl — static pre-registration uses placeholder AnyUrl('https://placeholder.invalid/callback')"
  - "OAuthClientInformationFull.client_id is str|None in SDK — _require_client_id() guard raises AuthorizeError(invalid_request) at provider level"
  - "reject_non_s256_pkce() checks (c) absent-challenge first, then (a) plain, then (b) absent-method — order matters for error_description accuracy"
  - "InMemoryTokenStore has separate revoke_access_token / revoke_refresh_token methods (not a unified revoke) — cleaner provider.revoke_token dispatch"
  - "token_store module-level singleton exported from tokens.py — provider.py must use THIS singleton, not create its own"

requirements-completed: [OAUTH-04, OAUTH-08]

# Metrics
duration: 21min
completed: 2026-06-15
---

# Phase 67 Plan 02: Co-Located AS Core (Keys + Tokens + Provider) Summary

**RS256 keypair + public-only JWKS + PyJWT JWT minting (aud=resource) + in-memory store + 9-method OAuthAuthorizationServerProvider + reject_non_s256_pkce() helper — 81 tests green, task before-push exits 0**

## Performance

- **Duration:** 21 min
- **Started:** 2026-06-15T00:51:18Z
- **Completed:** 2026-06-15T01:12:00Z
- **Tasks:** 3
- **Files created:** 7 (4 source, 3 test)
- **Files modified:** 1 (config.py)
- **Tests added:** 81 (26 + 32 + 23)

## Accomplishments

### Task 1: RS256 keypair + JWKS serializer + config settings (`052dda7`)

Created `agent_brain_mcp/oauth/` package with:
- `keys.py`: `generate_rs256_keypair()` (2048-bit, public exponent 65537), `compute_kid()` (base64url SHA-256 of DER), `build_jwks()` (public-only JWKS dict — no d/p/q), `SigningKey` dataclass, `get_or_create_signing_key()` (module-global singleton; optional PEM path via `AGENT_BRAIN_OAUTH_SIGNING_KEY`)
- `config.py` additions: `resolve_client_id_allowlist()` (AGENT_BRAIN_OAUTH_CLIENT_ID_ALLOWLIST, comma-split/strip/drop-empty), `resolve_signing_key_path()` (AGENT_BRAIN_OAUTH_SIGNING_KEY, empty→None)
- 26 tests: keypair generation, JWKS structure/security, round-trip JWT verify via PyJWK/RSAAlgorithm, allowlist/path config

### Task 2: JWT minting (RS256) + in-memory token store (`26225ba`)

Created `agent_brain_mcp/oauth/tokens.py` with:
- `mint_access_token(*, client_id, scopes, resource, signing_key, issuer) -> str`: RS256 JWT with full claim set; `aud=resource` exact, no mutation; `exp-iat=900`; unique `jti=secrets.token_urlsafe(16)`
- `InMemoryTokenStore`: store/load/pop for auth codes (pop = single-use enforcement), store/load/revoke for access tokens, store/load/rotate/revoke for refresh tokens (rotation: old deleted, new 30-day issued)
- `ACCESS_TOKEN_TTL_SECONDS = 900`, `REFRESH_TOKEN_TTL_SECONDS = 30 * 24 * 3600`
- `token_store` module-level singleton
- 32 tests: all claim values, uniqueness, store operations, rotation semantics

### Task 3: Provider + PKCE gate (`b572ac1`)

Created `agent_brain_mcp/oauth/provider.py` with:
- `reject_non_s256_pkce(query_params: Mapping[str, str]) -> None`: raises `AuthorizeError(error="invalid_request")` for (a) `code_challenge_method=plain` with `error_description="PKCE plain method not supported"`, (b) challenge present + method absent, (c) challenge absent. Passes for S256 + non-empty challenge.
- `AgentBrainAuthServerProvider`: all 9 SDK abstract methods implemented against `InMemoryTokenStore` + `SigningKey`; `aud` binds to `code.resource` (OAUTH-08 AS half); static pre-registration via `static_client_ids`
- `_require_client_id()` internal guard for the SDK's `str|None` `client_id` field
- 23 tests: all 4 PKCE cases (3 reject + 1 pass), get_client, register_client, authorize, exchange_authorization_code (aud binding), exchange_refresh_token (rotation), load_access_token, revoke_token

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | RS256 keypair + JWKS + config | `052dda7` | oauth/__init__.py, oauth/keys.py, config.py, test_oauth_keys_jwks.py |
| 2 | JWT minting + token store | `26225ba` | oauth/tokens.py, test_oauth_token_mint.py |
| 3 | Provider + PKCE gate | `b572ac1` | oauth/provider.py, test_oauth_authorize_pkce.py (+ Black/ruff fixes on all) |

## oauth/ Package Layout (for Plan 04 consumption)

```
agent_brain_mcp/oauth/
├── __init__.py            # package docstring
├── keys.py                # SigningKey, generate_rs256_keypair, compute_kid, build_jwks, get_or_create_signing_key
├── tokens.py              # mint_access_token, InMemoryTokenStore, token_store, ACCESS/REFRESH_TOKEN_TTL_SECONDS
└── provider.py            # AgentBrainAuthServerProvider, reject_non_s256_pkce
```

## Plan 04 / Phase 70 Consumption Guide

### What Plan 04 needs to wire

1. **GET /.well-known/jwks.json** (auth-exempt route):
   ```python
   from agent_brain_mcp.oauth.keys import get_or_create_signing_key
   sk = get_or_create_signing_key()
   # serve: JSONResponse(sk.jwks_dict)
   ```

2. **Provider construction** (once at startup in `http.py`):
   ```python
   from agent_brain_mcp.oauth.keys import get_or_create_signing_key
   from agent_brain_mcp.oauth.tokens import token_store
   from agent_brain_mcp.oauth.provider import AgentBrainAuthServerProvider
   from agent_brain_mcp.config import resolve_oauth_settings, resolve_client_id_allowlist

   resource, issuer = resolve_oauth_settings()
   sk = get_or_create_signing_key()
   provider = AgentBrainAuthServerProvider(
       signing_key=sk,
       store=token_store,
       issuer=issuer or base_url,
       resource=resource,
       static_client_ids=resolve_client_id_allowlist(),
   )
   ```

3. **create_auth_routes()** (add to auth-exempt routes list):
   ```python
   from mcp.server.auth.routes import create_auth_routes
   auth_routes = create_auth_routes(provider=provider, issuer_url=issuer or base_url)
   ```

4. **reject_non_s256_pkce() wiring** (Plan 04 Task 2 — in the live /authorize route handler):
   ```python
   from agent_brain_mcp.oauth.provider import reject_non_s256_pkce
   reject_non_s256_pkce(request.query_params)  # Starlette QueryParams is a Mapping
   ```
   Keep this call verbatim — the signature `(Mapping[str, str]) -> None` and the
   `error_description="PKCE plain method not supported"` string are stable contracts.

5. **RequireAuthMiddleware** (wraps /mcp mount only):
   The token verifier (Plan 03) needs to call `provider.load_access_token(token_str)`
   which returns the SDK `AccessToken` model for `request.state.auth`.

### Phase 70 verifier swap

The local verification seam (Plan 03's `BearerAuthBackend` / `TokenVerifier`) calls
`provider.load_access_token(token_str)`. Phase 70 swaps this for a `JwksTokenVerifier`
that fetches the JWKS from `GET /.well-known/jwks.json` (served from `sk.jwks_dict`
in the co-located shape). No provider changes needed for the swap.

## reject_non_s256_pkce() — Stable Contract for Plan 04

```python
def reject_non_s256_pkce(query_params: Mapping[str, str]) -> None:
    """Raises AuthorizeError(error='invalid_request') for non-S256 PKCE."""
```

| Input | Outcome |
|-------|---------|
| `{"code_challenge": "abc", "code_challenge_method": "plain"}` | raises; `error_description="PKCE plain method not supported"` |
| `{"code_challenge": "abc"}` (method absent) | raises `invalid_request` |
| `{}` (challenge absent) | raises `invalid_request` |
| `{"code_challenge": "abc", "code_challenge_method": "S256"}` | returns None (passes) |

## Token Claim Set (RS checks in Plan 03)

Every access JWT carries:

| Claim | Value | RS validates in Phase 67 |
|-------|-------|--------------------------|
| `iss` | configured issuer (or co-located AS base URL) | check #4 |
| `aud` | RFC 8707 resource URI (exact, from /authorize `resource` param) | check #5 |
| `sub` | OAuth client_id | — |
| `client_id` | OAuth client_id (redundant for RS convenience) | — |
| `scope` | space-joined scope list | check #6 (Phase 68) |
| `iat` | issued-at epoch | — |
| `nbf` | not-before (== iat) | check #3 (partial) |
| `exp` | iat + 900 | check #3 |
| `jti` | secrets.token_urlsafe(16) — unique | — |

JWT header: `{"alg": "RS256", "kid": "<signing_key.kid>", "typ": "JWT"}`

## In-Memory Store Semantics

- **Process-local**: restart invalidates ALL tokens and codes (accepted trade-off, Shape A)
- **Auth codes**: single-use via `pop_authorization_code()` (RFC 6749 §4.1.2)
- **Refresh tokens**: rotating (RFC 6749 / OAuth 2.1 §6) — old deleted, new 30-day on each exchange
- **Access tokens**: stored as SDK `AccessToken` model (with `resource` field set) for `load_access_token`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] OAuthClientInformationFull.redirect_uris validation**
- **Found during:** Task 3 (GREEN phase, first test run)
- **Issue:** `OAuthClientInformationFull(redirect_uris=[])` raises Pydantic ValidationError — field requires at least 1 AnyUrl
- **Fix:** Static pre-registration uses placeholder `AnyUrl("https://placeholder.invalid/callback")`
- **Files modified:** `agent_brain_mcp/oauth/provider.py`
- **Commit:** `b572ac1`

**2. [Rule 1 - Type] OAuthClientInformationFull.client_id is str|None**
- **Found during:** Task 3 (mypy check post-implementation)
- **Issue:** SDK types `client_id` as `str | None`; passing directly to `mint_access_token`, `AccessToken`, `RefreshToken` fails mypy strict
- **Fix:** Added `_require_client_id()` helper that raises `AuthorizeError(invalid_request)` if None; called at top of authorize/exchange methods
- **Files modified:** `agent_brain_mcp/oauth/provider.py`
- **Commit:** `b572ac1`

**3. [Rule 1 - Style] Black + Ruff linting on all new files**
- **Found during:** `task before-push` (first run)
- **Issues:** Import order (I001), unused imports (F401/json/importlib/os/Any/NoEncryption/PrivateFormat), `"SigningKey"` quoted annotation (UP037), line too long (E501) in docstrings
- **Fix:** `ruff --fix` auto-corrected 9/14 issues; remaining E501s fixed manually by shortening docstrings
- **Files modified:** all 7 new files
- **Commit:** `b572ac1` (accumulated with Task 3)

## Self-Check

### Created files exist:
- `agent-brain-mcp/agent_brain_mcp/oauth/__init__.py` - FOUND
- `agent-brain-mcp/agent_brain_mcp/oauth/keys.py` - FOUND (contains `def build_jwks` and `def generate_rs256_keypair`)
- `agent-brain-mcp/agent_brain_mcp/oauth/tokens.py` - FOUND (contains `def mint_access_token` and `class InMemoryTokenStore`, `ACCESS_TOKEN_TTL_SECONDS = 900`)
- `agent-brain-mcp/agent_brain_mcp/oauth/provider.py` - FOUND (contains `class AgentBrainAuthServerProvider`, `def reject_non_s256_pkce`, exact string `PKCE plain method not supported`)
- `agent-brain-mcp/agent_brain_mcp/config.py` - FOUND (contains `AGENT_BRAIN_OAUTH_CLIENT_ID_ALLOWLIST` and `def resolve_client_id_allowlist`)

### Commits exist:
- `052dda7` (Task 1) - FOUND
- `26225ba` (Task 2) - FOUND
- `b572ac1` (Task 3) - FOUND

### QA gate:
- `task before-push` exits 0 (745 passed, 88% coverage, 0 lint errors, 0 mypy errors)

## Self-Check: PASSED

---
*Phase: 67-co-located-as-rs-middleware*
*Completed: 2026-06-15*
