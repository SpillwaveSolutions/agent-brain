# Stack Research — v10.4 OAuth 2.1 for Remote MCP (MCP v4)

**Domain:** OAuth 2.1 Resource Server + Authorization Server on FastAPI/MCP Streamable HTTP
**Researched:** 2026-06-14
**Confidence:** HIGH (MCP SDK auth module — Context7 verified, GitHub source read); HIGH (PyJWT — current version confirmed); MEDIUM (Authlib AS capabilities — changelog verified, DPoP gap confirmed); LOW (DPoP — no production Python library confirmed)

---

## Executive Summary

This research covers ONLY the stack additions for v10.4 OAuth 2.1. The existing validated stack
(FastAPI, Uvicorn, mcp SDK, ChromaDB, LlamaIndex, Poetry, Click, etc.) is already in place and is
NOT re-covered here.

**Critical findings:**

1. **The `mcp` SDK (v1.27.2, latest stable as of 2026-06-14) ships complete OAuth 2.1 client-side machinery in `mcp.client.auth.OAuthClientProvider`.** It handles the full dance: 401 detection, RFC 9728 PRM discovery, RFC 8414 AS metadata discovery, RFC 7591 DCR, PKCE (S256, 128-char verifier), authorization code exchange, and token refresh. `McpHttpBackend` needs only to wire `OAuthClientProvider` + implement `TokenStorage` — it does NOT need to build the OAuth flow from scratch.

2. **The `mcp` SDK ships `mcp.server.auth` with the complete OAuth 2.1 AS implementation for the co-located shape** — authorization endpoint, token endpoint, revocation endpoint (RFC 7009), RFC 7591 DCR, RFC 8414 metadata, and RFC 9728 PRM. The user implements `OAuthAuthorizationServerProvider` (9 abstract methods) for storage/persistence. The SDK does NOT ship JWT signing for the co-located AS — that is the user's responsibility; `PyJWT` fills this gap.

3. **For the split AS/RS shape (external IdP),** the SDK's `TokenVerifier` protocol with `IntrospectionTokenVerifier` (uses RFC 7662 introspection) covers the external token validation path. For JWKS-cached JWT verification (no introspection round-trip), use `PyJWT[crypto]` with `PyJWKClient` (built-in 5-min TTL caching).

4. **DPoP (RFC 9449) has no production Python library as of June 2026.** The Authlib GitHub issue #315 (opened 2021) remains open. DPoP must be deferred or hand-rolled. The threat model in `v4-oauth-for-remote.md` lists DPoP as "optional" — this is the correct posture; ship without DPoP in v10.4.

5. **python-jose is abandoned** (last release 2021, Python 3.10+ compat issues). The FastAPI docs discussion thread (#11345) confirms migration to PyJWT. Do NOT use python-jose. The DEV.to article recommending `mcp>=1.27.0` + `python-jose` is incorrect — use `PyJWT`.

6. **Authlib 1.7.2 (released 2026-05-06)** is the right library for building the co-located AS if the team prefers not to implement all 9 `OAuthAuthorizationServerProvider` methods by hand. It covers PKCE, token introspection, revocation, RFC 8414, RFC 7591. No DPoP support yet.

7. **passlib is unmaintained.** Use `pwdlib` with Argon2 for password hashing in the co-located AS user store.

---

## New Stack Additions

### Core Auth Libraries

| Library | Version | Purpose | Why Recommended |
|---------|---------|---------|----------------|
| `mcp` (existing) | 1.27.2 | OAuth 2.1 AS + RS protocol endpoints (server) + OAuthClientProvider (client) | SDK ships `mcp.server.auth` with authorization/token/revocation/DCR/PRM/AS-metadata endpoints; `mcp.client.auth.OAuthClientProvider` handles full 401-dance for McpHttpBackend |
| `PyJWT[crypto]` | 2.13.0 | JWT signing (co-located AS) + JWKS-cached verification (split RS) | Actively maintained (unlike python-jose); `PyJWKClient` has built-in 5-min TTL cache; `[crypto]` extra adds RSA/EC key support via `cryptography` package |
| `cryptography` | >=42.0 | RSA/EC key generation + JWS signing | PyJWT[crypto] pulls this in; also needed for PKCE verifier hashing in the AS |
| `authlib` | 1.7.2 | Full OAuth 2.1 AS framework (PKCE, introspection, revocation, DCR, RFC 8414) as an alternative to implementing all 9 `OAuthAuthorizationServerProvider` methods manually | Covers the widest RFC surface area in one library; Python 3.10+ required; Starlette/FastAPI async support; active maintenance (last release May 2026) |
| `pwdlib[argon2]` | >=0.2 | Password hashing for co-located AS user store | passlib is unmaintained; pwdlib with argon2id is the current FastAPI ecosystem recommendation; memory-hard, GPU-resistant |

### Supporting / Integration Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx` (existing) | >=0.27 | Async HTTP client for `IntrospectionTokenVerifier` (split AS/RS — calls AS introspection endpoint) and for McpHttpBackend's OAuth dance via OAuthClientProvider | Already in stack; IntrospectionTokenVerifier calls `POST /introspect` asynchronously |
| `pyjwt-key-fetcher` | >=0.6 | Async JWKS key fetching with cache for split AS/RS JWT verification when PyJWKClient's synchronous behavior is a bottleneck | Only needed if async-native JWKS fetch is required; PyJWKClient works in most FastAPI scenarios via threadpool; evaluate in Phase implementation |
| `itsdangerous` | >=2.2 | CSRF state token signing for the OAuth authorization code flow redirect state parameter | Lightweight; already a Starlette transitive dep; use `URLSafeTimedSerializer` for the `state` param |

### Development / Testing Libraries

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| `pytest-httpx` | >=0.30 | Intercept httpx calls for introspection endpoint mocking in unit tests | FastAPI test pattern for mocking external AS introspection calls |
| `respx` | >=0.21 | Alternative httpx mock for JWKS endpoint responses in split AS/RS tests | Either respx or pytest-httpx; pick one and be consistent |

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `python-jose` | Abandoned since 2021; Python 3.10+ compat issues; FastAPI docs migrated away (issue #11345) | `PyJWT[crypto]` |
| `passlib` | Unmaintained; the FastAPI tutorial still shows it but the ecosystem has moved on | `pwdlib[argon2]` |
| Rolling your own JWT | JWT implementation errors are a known CVE factory; secret vs asymmetric confusion, alg:none, aud claim skips | `PyJWT[crypto]` with explicit `algorithms=["RS256"]` and mandatory `aud` + `iss` verification |
| DPoP (RFC 9449) in v10.4 | No production Python library exists as of June 2026 (authlib issue #315 open since 2021); hand-rolling DPoP is high-risk scope expansion | Defer to v10.5+; document as "optional, future" in the design doc threat model |
| `Keycloak` Python adapters | Keycloak is the CI external IdP for the split-AS test, not a library dep; the RS only needs JWKS verification against any compliant AS | Use `PyJWT[crypto]` + `PyJWKClient` for JWKS verification — works against Keycloak, Auth0, Cognito |
| `fastapi-users` | Full auth framework coupling; opinionated user model; harder to wire into the existing FastAPI app structure | Implement `OAuthAuthorizationServerProvider` directly using Authlib's grant handlers; stays composable |
| `python-multipart` (new) | Already a FastAPI dep for form data; do not re-add | It's already there — verify it's in pyproject.toml before adding |

---

## MCP Python SDK OAuth Capabilities (Precise)

### What the SDK provides on the server side (`mcp.server.auth`)

The following is HIGH confidence — verified against GitHub source (`src/mcp/server/auth/provider.py`) and Context7 docs.

**Protocol endpoints auto-wired by the SDK when `OAuthAuthorizationServerProvider` is registered:**
- `GET /.well-known/oauth-protected-resource` — RFC 9728 Protected Resource Metadata
- `GET /.well-known/oauth-authorization-server` — RFC 8414 AS Metadata
- `POST /register` — RFC 7591 Dynamic Client Registration
- `GET /authorize` — Authorization endpoint (redirect-based)
- `POST /token` — Token endpoint (code exchange + refresh)
- `POST /revoke` — RFC 7009 Token Revocation
- `POST /introspect` — RFC 7662 Token Introspection (confirmed in `IntrospectionTokenVerifier` docs; server-side endpoint presence needs implementation verification)

**What the user MUST implement (9 abstract methods on `OAuthAuthorizationServerProvider`):**

```python
async def get_client(client_id: str) -> OAuthClientInformationFull | None
async def register_client(client_info: OAuthClientInformationFull) -> None
async def authorize(client, params: AuthorizationParams) -> str  # returns auth code
async def load_authorization_code(client, code: str) -> AuthorizationCode | None
async def exchange_authorization_code(client, code: AuthorizationCode) -> OAuthToken
async def load_refresh_token(client, token: str) -> RefreshToken | None
async def exchange_refresh_token(client, token: RefreshToken, scopes: list[str]) -> OAuthToken
async def load_access_token(token: str) -> AccessToken | None
async def revoke_token(token: AccessToken | RefreshToken) -> None
```

**What the SDK does NOT provide on the server side:**
- JWT signing — the user's `exchange_authorization_code` and `exchange_refresh_token` implementations must mint signed JWTs using PyJWT
- JWKS endpoint (`GET /.well-known/jwks.json`) — must be added as a custom FastAPI route that exposes the RS256 public key
- User authentication (login form, username/password validation) — this is user-space; the SDK calls `authorize()` and expects the implementation to handle the user-facing auth
- DPoP (RFC 9449)
- Resource Indicators (RFC 8707) enforcement — the `AccessToken` model includes a `resource` field but enforcement logic is user responsibility

**For the RS-only shape (no built-in AS), the SDK exposes:**
```python
# mcp.server.auth.provider
class TokenVerifier(Protocol):
    async def verify_token(self, token: str) -> AccessToken | None: ...

# Wire into FastMCP:
mcp = FastMCP("name", token_verifier=MyVerifier(), auth=AuthSettings(...))

# AuthSettings (mcp.server.auth.settings):
AuthSettings(
    issuer_url=AnyHttpUrl("https://external-as.example.com"),
    resource_server_url=AnyHttpUrl("https://agent-brain.example.com"),
    required_scopes=["agent-brain:read"],
)
```

**SDK middleware auto-registered when `token_verifier` is set:**
- `BearerAuthBackend` — extracts `Authorization: Bearer <token>` from the request
- `RequireAuthMiddleware` — returns 401 if no valid token; 403 if insufficient scope
- `AuthContext` is stored in `request.state.auth` and passed to MCP tool handlers via `Context`

### What the SDK provides on the client side (`mcp.client.auth`)

Verified against GitHub source (`src/mcp/client/auth/oauth2.py`) and the DeepWiki 8.4 OAuth flow example.

**`OAuthClientProvider` (implements `httpx.Auth`) auto-handles:**
- 401 detection and trigger of the full OAuth dance
- RFC 9728 PRM discovery (hierarchical: resource_metadata header → .well-known/oauth-protected-resource/{path} → root)
- RFC 8414 AS Metadata discovery (hierarchical: path-aware → OIDC config → root)
- RFC 7591 DCR (registers client if no prior client_id)
- PKCE: generates 128-character code verifier, S256 challenge method, via `PKCEParameters.generate()`
- Authorization code redirect + state CSRF protection (timing-safe comparison)
- Code → token exchange
- Token refresh on stale access token
- 403 / `insufficient_scope` re-authorization

**`TokenStorage` protocol the user MUST implement (4 methods):**
```python
async def get_tokens() -> OAuthToken | None
async def set_tokens(tokens: OAuthToken) -> None
async def get_client_info() -> OAuthClientInformationFull | None
async def set_client_info(client_info: OAuthClientInformationFull) -> None
```

**Callback handlers the user MUST provide:**
- `redirect_handler(auth_url: str)` — open browser or print URL (for `McpHttpBackend`, this will be a CLI prompt or a local callback server)
- `callback_handler() -> tuple[str, str | None]` — return (authorization_code, state); for headless MCP clients this may require a loopback HTTP server on a random port

**What OAuthClientProvider does NOT handle:**
- DPoP proof generation (RFC 9449)
- Token introspection (client-side — not applicable; introspection is server-side)
- Resource Indicators assertion (RFC 8707) — the `resource` parameter may need explicit injection into the DCR/token request
- Persistent storage implementation (that's `TokenStorage`)
- `McpHttpBackend`-specific concerns: the backend must construct `OAuthClientProvider` with the right `server_url` and `client_metadata`, and wire it as `auth=oauth_auth` in `httpx.AsyncClient`

### Integration point for `McpHttpBackend`

```python
# In McpHttpBackend (agent-brain-mcp/agent_brain_mcp/client.py)
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.shared.auth import OAuthClientMetadata
import httpx

class PersistentTokenStorage(TokenStorage):
    # persist to <state_dir>/mcp_oauth_tokens.json with 0o600 perms
    ...

oauth_provider = OAuthClientProvider(
    server_url=self.mcp_url,  # e.g., https://agent-brain.example.com
    client_metadata=OAuthClientMetadata(
        client_name="agent-brain-cli",
        redirect_uris=[...],  # loopback callback server URI
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        scope="agent-brain:read agent-brain:index",
    ),
    storage=PersistentTokenStorage(state_dir=self.state_dir),
    redirect_handler=_open_browser_or_print,
    callback_handler=_local_callback_server,
)

async with httpx.AsyncClient(auth=oauth_provider) as client:
    async with streamable_http_client(self.mcp_url + "/mcp", http_client=client) as ...:
        ...
```

The SDK's `OAuthClientProvider` handles the rest automatically — including retrying the original request after token acquisition.

---

## Stack by Deployment Shape

### Shape 1: Co-located AS/RS (single binary, self-hosted)

The MCP server acts as BOTH the Authorization Server and the Resource Server. Tokens are self-signed JWTs; no introspection round-trip needed.

| Component | Library | Notes |
|-----------|---------|-------|
| OAuth 2.1 AS protocol endpoints | `mcp` SDK `OAuthAuthorizationServerProvider` | Provides /authorize, /token, /revoke, /register, /.well-known/* |
| JWT signing (access + refresh tokens) | `PyJWT[crypto]` 2.13.0 | RS256 with generated RSA-2048 key; private key in env/secrets |
| JWKS endpoint | Custom FastAPI route | `GET /.well-known/jwks.json` returning the RS256 public key |
| Token verification (same process) | `PyJWT[crypto]` — local verify | No network call; verify against the same private key's public half |
| Password hashing (user store) | `pwdlib[argon2]` | Argon2id; only needed if co-located AS has a local user database |
| Storage backend for codes/tokens | stdlib `json` + `aiosqlite` OR in-memory dict | For single-user self-hosted, in-memory with state-dir JSON persistence is sufficient |
| Client-side (McpHttpBackend) | `mcp.client.auth.OAuthClientProvider` | See integration point above |

**What to NOT build:** Do not re-implement PKCE, DCR, RFC 8414, or RFC 9728 — the SDK handles all of these.

### Shape 2: Split AS/RS (external IdP — Keycloak/Auth0/Cognito)

The MCP server is the Resource Server only; an external AS issues tokens.

| Component | Library | Notes |
|-----------|---------|-------|
| RS token validation (JWKS-cached) | `PyJWT[crypto]` 2.13.0 + `PyJWKClient` | `PyJWKClient(jwks_uri, cache_jwk_set=True, lifespan=300)` — built-in 5-min TTL |
| Async JWKS fetch (if needed) | `pyjwt-key-fetcher` >=0.6 | Only if sync PyJWKClient is a bottleneck in async FastAPI handlers; evaluate in implementation |
| TokenVerifier implementation | Custom class implementing `mcp.server.auth.provider.TokenVerifier` | For external AS: fetch JWKS, verify JWT signature + `aud` + `iss` + `scope` claims |
| Introspection-based verification (alternative) | `IntrospectionTokenVerifier` pattern with `httpx.AsyncClient` | POST to external AS `/introspect` endpoint; higher latency than JWKS verify; use only if opaque tokens |
| PRM + AS Metadata | `mcp` SDK `AuthSettings` | Point `issuer_url` at external AS; SDK auto-generates PRM endpoint |
| CI external IdP | Keycloak (Docker container in CI) | No Python lib dep; Keycloak speaks standard OIDC/OAuth 2.1; `PyJWKClient` works against it |
| Client-side (McpHttpBackend) | `mcp.client.auth.OAuthClientProvider` | Same as co-located; no client-side changes between shapes |

---

## Installation

```bash
# In agent-brain-mcp/pyproject.toml (Poetry)
[tool.poetry.dependencies]
PyJWT = {version = "^2.13", extras = ["crypto"]}
authlib = "^1.7"       # only if using Authlib to implement OAuthAuthorizationServerProvider
pwdlib = {version = "^0.2", extras = ["argon2"]}  # only if co-located AS has user store
itsdangerous = "^2.2"  # CSRF state signing; may already be transitive via Starlette

# Dev / test
[tool.poetry.group.dev.dependencies]
pytest-httpx = "^0.30"  # mock introspection + JWKS HTTP calls
respx = "^0.21"         # alternative to pytest-httpx; pick one

# The mcp package is already in pyproject.toml; verify it is >=1.27.2
# mcp SDK at 1.27.2 ships mcp.server.auth + mcp.client.auth with no extra install
```

```bash
# Install via uv (per project convention)
cd agent-brain-mcp
uv add "PyJWT[crypto]>=2.13"
uv add "authlib>=1.7"
uv add "pwdlib[argon2]>=0.2"
uv add "itsdangerous>=2.2"
uv add --group dev "pytest-httpx>=0.30"
```

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| `PyJWT[crypto]` | `python-jose` | Abandoned since 2021; Python 3.10+ compat issues; FastAPI docs migrated away (GitHub discussion #11345) |
| `PyJWT[crypto]` | `joserfc` (Authlib's JOSE sub-lib) | Viable but no built-in JWKS HTTP fetcher; requires more manual wiring; smaller community; PyJWT is simpler for this use case |
| `mcp` SDK `OAuthAuthorizationServerProvider` | Authlib AS framework (standalone) | Authlib AS is viable but would duplicate what the MCP SDK already provides on the protocol layer; use Authlib only for the OAuth grant logic inside `OAuthAuthorizationServerProvider` implementations if needed |
| `pwdlib[argon2]` | `bcrypt` directly | bcrypt is fine but argon2id is the current OWASP-recommended memory-hard algorithm; pwdlib makes the migration path explicit |
| `pwdlib[argon2]` | `passlib[bcrypt]` | passlib is unmaintained |
| Defer DPoP | Custom DPoP implementation | Hand-rolling RFC 9449 is high complexity and high CVE risk; no production Python library validates the approach; short-lived tokens + TLS already address the primary threat |

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `mcp ^1.27` | Python 3.10+ | mcp 1.27.2 is the latest stable; v2.0.0a1 is pre-release — do NOT use for production |
| `PyJWT ^2.13` | Python 3.8+ | Compatible with Python 3.10+ used by agent-brain |
| `authlib ^1.7` | Python 3.10+ | authlib 1.7.2 (May 2026) requires Python 3.10+; aligns with agent-brain constraint |
| `cryptography >=42` | PyJWT[crypto] | PyJWT pulls in cryptography; ensure no version conflict with existing deps |
| `httpx >=0.27` (existing) | `OAuthClientProvider` | OAuthClientProvider implements `httpx.Auth`; requires httpx in the existing range |

---

## Sources

- `/modelcontextprotocol/python-sdk` Context7 — OAuth 2.1 client/server module query; verified `OAuthClientProvider`, `TokenVerifier`, `AuthSettings`, `OAuthAuthorizationServerProvider` class shapes
- `github.com/modelcontextprotocol/python-sdk/blob/main/src/mcp/server/auth/provider.py` — confirmed 9 abstract methods on `OAuthAuthorizationServerProvider`; HIGH confidence
- `deepwiki.com/modelcontextprotocol/python-sdk/8.4-oauth-authentication-flow-example` — confirmed full client-side OAuth dance in `OAuthClientProvider.async_auth_flow()`; HIGH confidence
- `pypi.org/project/mcp/` — confirmed current stable version is 1.27.2 (released 2026-05-29); v2.0.0a1 pre-release; HIGH confidence
- `pypi.org/project/Authlib/` — confirmed Authlib 1.7.2, released 2026-05-06, Python 3.10+; HIGH confidence
- `docs.authlib.org/en/v1.7.0/upgrades/changelog.html` — confirmed no DPoP support in 1.7.0+; no RFC 9449 in changelog; MEDIUM confidence
- `github.com/authlib/authlib/issues/315` — DPoP feature request open since 2021; confirmed not implemented; HIGH confidence
- `github.com/fastapi/fastapi/discussions/11345` — confirmed python-jose abandoned, FastAPI docs migrated to PyJWT; HIGH confidence
- `pyjwt.readthedocs.io` — confirmed PyJWT 2.13.0 as current version, `PyJWKClient` with 5-min TTL cache; HIGH confidence
- WebSearch: pwdlib Argon2 recommendation — FastAPI ecosystem migration from passlib; MEDIUM confidence

---

*Stack research for: v10.4 OAuth 2.1 for Remote MCP (MCP v4 / issue #188)*
*Researched: 2026-06-14*
