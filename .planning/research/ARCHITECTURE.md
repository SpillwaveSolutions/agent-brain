# Architecture Research

**Domain:** OAuth 2.1 Resource Server (+ optional co-located AS) integration with existing FastAPI + MCP Streamable HTTP server
**Researched:** 2026-06-14
**Confidence:** HIGH (existing code read directly; MCP SDK auth module verified via SDK source + DeepWiki; RFC specs canonical; mount-path gotchas verified via open GitHub issues)

---

## v10.4 Scope: What Changes, What Stays

This research covers ONLY how OAuth 2.1 integrates with the existing system. Nothing in the existing core pipeline (indexing, query, storage, job queue) changes. The only surfaces that change are:

- `agent_brain_server/api/security.py` — the existing static-Bearer dependency (replace/layer)
- `agent_brain_server/api/main.py` — startup gate, router wiring, new well-known endpoints mounted
- `agent_brain_server/config/settings.py` — new `AGENT_BRAIN_AUTH` toggle + OAuth-specific vars
- `agent_brain_mcp/http.py` — loopback host whitelist relaxed for `AGENT_BRAIN_AUTH=oauth`; ASGI app gains auth middleware before the `/mcp` mount
- `agent_brain_mcp/client.py` (`McpHttpBackend`) — OAuth dance client-side (token storage, challenge handling, token refresh)
- `agent_brain_mcp/security/` — existing re-export shim; new `oauth/` sibling module for scoped-token enforcement

---

## Standard Architecture

### System Overview — v10.4 Two-Topology Target

```
TOPOLOGY A: CO-LOCATED AS/RS (single binary, self-hosted)
══════════════════════════════════════════════════════════════════════════

  MCP CLIENT (McpHttpBackend / framework / Claude Desktop)
       │
       │ HTTPS (public bind, AGENT_BRAIN_AUTH=oauth)
       ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │  Starlette ASGI app  (agent-brain-mcp, build_asgi_app())         │
  │                                                                  │
  │  [LAYER 0: RequireAuthMiddleware (mcp.server.auth.middleware)]   │
  │     • Extracts Bearer token from Authorization header            │
  │     • Calls TokenVerifier.verify_token(token)                    │
  │     • 401 + WWW-Authenticate header on missing/invalid token     │
  │     • 403 on insufficient scope                                  │
  │                      │                                           │
  │  [LAYER 1: AuthenticationMiddleware (Starlette auth backend)]    │
  │     • BearerAuthBackend populates request.state.auth             │
  │                      │                                           │
  │  ┌───────────────────┴──────────────────────────────────────┐    │
  │  │  Route: GET  /.well-known/oauth-protected-resource  (NEW) │    │
  │  │  Route: GET  /.well-known/oauth-authorization-server (NEW)│    │
  │  │  Route: POST /token       (AS endpoint, co-located)  (NEW)│    │
  │  │  Route: GET  /authorize   (AS endpoint, co-located)  (NEW)│    │
  │  │  Route: POST /register    (DCR, optional)             (NEW)│    │
  │  │  Route: POST /revoke      (optional)                  (NEW)│    │
  │  │  Mount: /mcp  →  StreamableHTTPSessionManager         (EX) │    │
  │  │  Route: GET  /healthz                                 (EX) │    │
  │  └──────────────────────────────────────────────────────────┘    │
  │                                                                  │
  │  TokenVerifier (co-located): ProviderTokenVerifier               │
  │     → OAuthAuthorizationServerProvider.load_access_token(token) │
  │     → validates JWT locally (HS256/RS256), checks exp + scope    │
  └──────────────────────────────────────────────────────────────────┘
       │
       │ loopback HTTP (INSECURE, no auth)
       ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │  FastAPI app  (agent-brain-server)                               │
  │  verify_bearer_token dependency on data routers (EXISTING)      │
  │  ← AGENT_BRAIN_AUTH=oauth: dependency swapped to                │
  │     verify_oauth_token (checks JWT locally, scope=server-side)  │
  └──────────────────────────────────────────────────────────────────┘

TOPOLOGY B: SPLIT AS/RS (external IdP — Keycloak, Auth0, Cognito)
══════════════════════════════════════════════════════════════════════════

  MCP CLIENT
       │
       │ HTTPS
       ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │  Starlette ASGI app  (agent-brain-mcp)                           │
  │  [RequireAuthMiddleware]                                         │
  │     TokenVerifier: IntrospectionTokenVerifier OR                 │
  │                    JwksTokenVerifier (PyJWT + PyJWKClient)       │
  │       → calls external IdP /introspect  OR                      │
  │       → fetches JWKS from IdP, validates JWT locally             │
  │                                                                  │
  │  ┌──────────────────────────────────────────────────────────┐    │
  │  │  Route: GET  /.well-known/oauth-protected-resource  (NEW) │    │
  │  │    (points authorization_servers → external IdP URL)      │    │
  │  │  Mount: /mcp  →  StreamableHTTPSessionManager        (EX) │    │
  │  │  Route: GET  /healthz                                (EX) │    │
  │  │  NO /token /authorize /register /revoke here              │    │
  │  └──────────────────────────────────────────────────────────┘    │
  └──────────────────────────────────────────────────────────────────┘
       │  (token validation queries)
       ▼
  ┌────────────────────────────────────────────────────────────────┐
  │  External IdP  (Keycloak / Auth0 / Cognito)                    │
  │  Provides: /token, /authorize, /register                       │
  │  Provides: /.well-known/oauth-authorization-server             │
  │  Provides: JWKS endpoint                                       │
  └────────────────────────────────────────────────────────────────┘
```

### Auth Toggle — How `AGENT_BRAIN_AUTH` Controls the Three Modes

```
AGENT_BRAIN_AUTH=none   (default, current behavior)
    • verify_bearer_token: no-op if API_KEY is None; static compare if set
    • MCP HTTP: loopback-only enforcement remains, no auth middleware added
    • No /.well-known/* routes mounted

AGENT_BRAIN_AUTH=basic  (LAN bridge, migration step)
    • verify_bearer_token: unchanged behavior (shared-secret Bearer)
    • MCP HTTP: loopback-only lifted only if AGENT_BRAIN_ALLOW_PUBLIC_BIND=true
    • No /.well-known/* routes mounted
    • Intent: allows LAN deployment before full OAuth is ready

AGENT_BRAIN_AUTH=oauth  (full OAuth 2.1)
    • verify_bearer_token: replaced by verify_oauth_token dependency
    • MCP HTTP: loopback enforcement lifted; RequireAuthMiddleware added
    • /.well-known/oauth-protected-resource always mounted
    • Topology A: /.well-known/oauth-authorization-server + /token/authorize/register/revoke mounted
    • Topology B: none of /token etc. mounted; TokenVerifier hits external IdP
```

### The Existing Static-Bearer Path — Replacement, Not Double-Auth

The current `verify_bearer_token` FastAPI dependency in `agent_brain_server/api/security.py` does a static constant-time compare of the incoming Bearer token against `settings.API_KEY`. In `AGENT_BRAIN_AUTH=oauth` mode this dependency MUST be replaced (not added alongside). The architecture is:

```python
# agent_brain_server/api/security.py  (MODIFY)

async def get_auth_dependency() -> Callable[..., Awaitable[None]]:
    """Return the correct auth dependency for the current AGENT_BRAIN_AUTH mode."""
    mode = get_settings().AGENT_BRAIN_AUTH
    if mode == "oauth":
        return verify_oauth_token   # new: JWT decode + scope check
    if mode == "basic":
        return verify_bearer_token  # existing: static compare
    return _noop_auth               # AGENT_BRAIN_AUTH=none
```

Each router's `dependencies=[Depends(verify_bearer_token)]` is replaced with `dependencies=[Depends(get_auth_dependency())]` at import time, or equivalently, the router-level dependency is parameterized via a factory. The critical constraint: a request MUST NOT pass both the static-bearer check AND the JWT check. Toggling is mode-exclusive.

---

## Component Responsibilities

| Component | Status | Package | Responsibility |
|-----------|--------|---------|----------------|
| `verify_bearer_token` | MODIFY | `agent-brain-server` | Existing static-Bearer dep; becomes one branch of auth toggle |
| `verify_oauth_token` | NEW | `agent-brain-server` | FastAPI dep; decodes JWT, validates `aud` + `exp` + required scope; co-located: inline; split: JWKS |
| `AuthSettings` | NEW | `agent-brain-mcp` | Configuration for `RequireAuthMiddleware` (issuer URL, required scopes, resource server URL) |
| `OAuthAuthorizationServerProvider` | NEW | `agent-brain-mcp` | Co-located AS: implements the full MCP SDK protocol (client registry, code store, token store, revocation) |
| `ProviderTokenVerifier` | NEW (co-located) | `agent-brain-mcp` | Wraps `OAuthAuthorizationServerProvider.load_access_token()` for `RequireAuthMiddleware` |
| `JwksTokenVerifier` | NEW (split) | `agent-brain-mcp` | Wraps PyJWT `PyJWKClient`; cached JWKS fetch; validates sig + `aud` + `exp` |
| `IntrospectionTokenVerifier` | NEW (split, optional) | `agent-brain-mcp` | Calls external IdP `/introspect`; use when JWKS unavailable |
| `RequireAuthMiddleware` | USE SDK | `agent-brain-mcp` | `mcp.server.auth.middleware.bearer_auth.RequireAuthMiddleware`; wraps the MCP ASGI mount |
| `BearerAuthBackend` | USE SDK | `agent-brain-mcp` | `mcp.server.auth.middleware.bearer_auth.BearerAuthBackend`; Starlette auth backend |
| `create_auth_routes()` | USE SDK | `agent-brain-mcp` | `mcp.server.auth.routes.create_auth_routes()`; registers AS endpoints (co-located only) |
| `OAuthTokenStore` | NEW | `agent-brain-mcp` | In-memory (with optional disk persistence) store for auth codes, access tokens, refresh tokens |
| `OAuthClientRegistry` | NEW | `agent-brain-mcp` | In-memory client registry; used by DCR (`/register`) and `authorize` |
| `McpHttpBackend` (OAuth mode) | MODIFY | `agent-brain-mcp` | Client-side: passes `OAuthClientProvider` to `streamablehttp_client`; stores tokens; handles 401 dance |
| `InMemoryTokenStorage` / `FileTokenStorage` | NEW | `agent-brain-mcp` | `TokenStorage` protocol impl for `OAuthClientProvider`; file-backed for persistence across invocations |
| `agent_brain_mcp/oauth/` | NEW MODULE | `agent-brain-mcp` | Home for all server-side OAuth plumbing (provider, token store, client registry, token verifiers) |
| `agent_brain_mcp/security/` | MODIFY | `agent-brain-mcp` | Add `scope_guard.py` — per-tool scope enforcement callable; existing `__init__.py` re-export shim unchanged |
| `AGENT_BRAIN_AUTH` | NEW setting | `agent-brain-server` | Toggle enum: `none` \| `basic` \| `oauth` (default: `none`) |
| `AGENT_BRAIN_OAUTH_ISSUER` | NEW setting | `agent-brain-server` | Issuer URL for JWT `iss` claim validation |
| `AGENT_BRAIN_OAUTH_RESOURCE` | NEW setting | `agent-brain-mcp` | Resource URI for PRM + token `aud` claim |
| `AGENT_BRAIN_OAUTH_JWKS_URI` | NEW setting | `agent-brain-mcp` | External JWKS URL (split topology only) |
| `AGENT_BRAIN_OAUTH_INTROSPECT_URI` | NEW setting | `agent-brain-mcp` | External introspection URL (split topology only) |

---

## Recommended Project Structure

```
agent-brain-server/
└── agent_brain_server/
    ├── api/
    │   ├── main.py                    # MODIFY: mount /.well-known/* in oauth mode; startup gate
    │   ├── security.py                # MODIFY: add verify_oauth_token; auth-mode dispatch
    │   └── routers/
    │       └── (all routers)          # MODIFY: dependency param → get_auth_dependency()
    └── config/
        └── settings.py                # MODIFY: AGENT_BRAIN_AUTH, AGENT_BRAIN_OAUTH_ISSUER

agent-brain-mcp/
└── agent_brain_mcp/
    ├── http.py                        # MODIFY: loopback gate lifted in oauth mode; inject auth middleware
    ├── cli.py                         # MODIFY: --no-auth flag → startup gate mirrors server pattern
    ├── config.py                      # MODIFY: AGENT_BRAIN_OAUTH_RESOURCE, JWKS/introspect URI
    ├── client.py (McpHttpBackend)     # MODIFY: pass OAuthClientProvider to streamablehttp_client
    ├── security/
    │   ├── __init__.py                # UNCHANGED (file sandbox re-export shim)
    │   └── scope_guard.py             # NEW: per-tool scope enforcement callable
    └── oauth/                         # NEW MODULE
        ├── __init__.py                # NEW: re-exports public surface
        ├── provider.py                # NEW: OAuthAuthorizationServerProvider impl (co-located AS)
        ├── token_store.py             # NEW: in-memory token/code store (co-located)
        ├── client_registry.py         # NEW: in-memory client registry (DCR)
        ├── verifiers.py               # NEW: JwksTokenVerifier + IntrospectionTokenVerifier
        ├── token_storage.py           # NEW: FileTokenStorage for McpHttpBackend
        └── metadata.py                # NEW: PRM + OASM response builders
```

### Structure Rationale

- **`agent_brain_mcp/oauth/`** is a new top-level module, not a sub-package of `security/`, because `security/` is already a file-sandbox re-export shim with a strict "no logic" contract. The `oauth/` module contains substantial logic (token stores, provider, verifiers) and must be isolated.
- **`agent_brain_mcp/security/scope_guard.py`** is placed inside `security/` because it is purely a policy enforcement callable — no state, no logic beyond "does this token's scopes list contain X?" — consistent with the security directory's role as policy helpers.
- **`agent_brain_server/api/security.py`** keeps all FastAPI auth dependencies co-located. Adding `verify_oauth_token` here respects the existing import pattern across all routers.

---

## Architectural Patterns

### Pattern 1: Auth-Mode Toggle via `AGENT_BRAIN_AUTH` Setting

**What:** A single enum setting (`none` | `basic` | `oauth`) drives which auth dependency is wired into FastAPI routers, whether the loopback host guard is relaxed, and which routes are mounted. The toggle is read once at startup, not per-request.

**When to use:** At startup gate in `main.py` and in the MCP ASGI builder `http.py`. Per-request path reads only the already-resolved dependency — no per-request mode check.

**Trade-offs:** Clean migration path (`none` → `basic` → `oauth`); no double-auth confusion because mode-selection is exclusive. Config error (e.g., `AGENT_BRAIN_AUTH=oauth` without `AGENT_BRAIN_OAUTH_RESOURCE`) must be caught at startup, not at first request.

```python
# agent_brain_server/config/settings.py (MODIFY)
from typing import Literal

class Settings(BaseSettings):
    # ...existing fields...
    AGENT_BRAIN_AUTH: Literal["none", "basic", "oauth"] = "none"
    AGENT_BRAIN_OAUTH_ISSUER: str | None = None     # JWT iss claim, co-located or split
    AGENT_BRAIN_OAUTH_AUDIENCE: str | None = None   # JWT aud claim (= resource URI)
    INSECURE_NO_AUTH: bool = False                  # existing; kept; oauth mode ignores it

# agent_brain_server/api/security.py (MODIFY)
async def verify_oauth_token(
    authorization: str | None = Header(default=None),
) -> TokenClaims:
    """FastAPI dep: validate JWT access token, return parsed claims."""
    settings = get_settings()
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing Bearer token",
                            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'})
    token = authorization[7:].strip()
    claims = await _verify_jwt(token, settings)  # JWKS or local secret
    return claims

def get_auth_dependency() -> Callable:
    """Return the correct FastAPI auth dependency for current mode."""
    mode = get_settings().AGENT_BRAIN_AUTH
    if mode == "oauth":
        return verify_oauth_token
    if mode == "basic":
        return verify_bearer_token   # existing static compare
    return _noop_auth                # none
```

### Pattern 2: MCP SDK Auth Middleware Stack (Server-Side)

**What:** The existing `build_asgi_app()` in `http.py` builds a Starlette ASGI app with two routes (`/healthz` + `/mcp`). In `AGENT_BRAIN_AUTH=oauth` mode, wrap the Starlette app with the SDK's `RequireAuthMiddleware` BEFORE the `StreamableHTTPSessionManager` mount — the middleware intercepts all non-well-known requests, validates Bearer tokens via the injected `TokenVerifier`, and enforces the server-level required scopes.

**When to use:** Only when `AGENT_BRAIN_AUTH=oauth`. The middleware is not instantiated in `none` or `basic` modes — zero overhead in the default dev path.

**Trade-offs:** The well-known routes (PRM, OASM) MUST be outside the auth middleware — they are publicly accessible for discovery. Mount the well-known routes on the outer Starlette app BEFORE wrapping with `RequireAuthMiddleware`, or use explicit path exclusions.

```python
# agent_brain_mcp/http.py (MODIFY)
from mcp.server.auth.middleware.bearer_auth import (
    BearerAuthBackend, RequireAuthMiddleware
)
from starlette.middleware.authentication import AuthenticationMiddleware

def build_asgi_app(
    server: Server,
    *,
    auth_mode: str = "none",
    token_verifier: "TokenVerifier | None" = None,
    auth_settings: "AuthSettings | None" = None,
    oauth_routes: "list[Route] | None" = None,
) -> Starlette:
    """Build Starlette ASGI app. In oauth mode, wraps /mcp with auth middleware."""
    session_manager = StreamableHTTPSessionManager(
        app=server,
        event_store=None,
        json_response=False,
        stateless=False,
        security_settings=_pick_security_settings(auth_mode),
    )

    async def healthz(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "transport": "http"})

    routes: list[Route | Mount] = [
        Route(HEALTHZ_PATH, healthz, methods=["GET"]),
    ]

    # OAuth discovery routes mount OUTSIDE auth middleware (publicly accessible)
    if oauth_routes:
        routes.extend(oauth_routes)

    async def mcp_asgi(scope: Scope, receive: Receive, send: Send) -> None:
        await session_manager.handle_request(scope, receive, send)

    # /mcp mount; in oauth mode we wrap it with auth middleware below
    mcp_mount = Mount(MCP_MOUNT_PATH, app=mcp_asgi)
    routes.append(mcp_mount)

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    base_app = Starlette(routes=routes, lifespan=lifespan)

    if auth_mode == "oauth" and token_verifier is not None:
        # Wrap the full Starlette app with Starlette AuthenticationMiddleware
        # + MCP SDK's RequireAuthMiddleware to enforce token presence on /mcp
        authed = AuthenticationMiddleware(base_app, backend=BearerAuthBackend(token_verifier))
        # RequireAuthMiddleware enforces scope and emits RFC 9728-compliant WWW-Authenticate
        return RequireAuthMiddleware(authed, required_scopes=["agent-brain:read"])
    return base_app
```

**Critical mounting caveat (from GitHub issue #1751):** When the MCP server is mounted at a sub-path (e.g. `/mcp`), the SDK's `OAuthClientProvider` on the client side constructs `/.well-known/oauth-protected-resource` relative to the mount root. If the well-known routes are only at the sub-path, VS Code Copilot and Claude Desktop currently strip the path and hit the root domain. The workaround is to mount well-known routes at BOTH `/.well-known/*` on the outer app AND optionally at `/mcp/.well-known/*`. The Agent Brain MCP server is a single-tenant single-mount app (no sub-path routing), so the well-known routes live at the top-level — no conflict.

### Pattern 3: Protected Resource Metadata (RFC 9728) — PRM Endpoint

**What:** `GET /.well-known/oauth-protected-resource` returns a JSON document that tells MCP clients where to find the AS, which scopes are supported, and how to present tokens. This is the FIRST thing the MCP client fetches after receiving a 401 challenge.

**When to use:** Always in `AGENT_BRAIN_AUTH=oauth` mode, regardless of topology. Co-located: `authorization_servers` points to the same host. Split: `authorization_servers` points to external IdP.

**Trade-offs:** The resource field MUST match the `aud` claim in issued JWTs. If they diverge (e.g., trailing slash mismatch), all token validation fails. Set `AGENT_BRAIN_OAUTH_RESOURCE` once and derive everything from it.

```python
# agent_brain_mcp/oauth/metadata.py (NEW)
from dataclasses import dataclass

@dataclass
class ProtectedResourceMetadata:
    resource: str                       # e.g. "https://brain.example.com"
    authorization_servers: list[str]    # e.g. ["https://brain.example.com"]  (co-located)
                                        #   or ["https://auth.example.com"]   (split)
    scopes_supported: list[str] = (
        "agent-brain:read",
        "agent-brain:index",
        "agent-brain:admin",
        "agent-brain:subscribe",
    )
    bearer_methods_supported: list[str] = ("header",)
    jwks_uri: str | None = None         # only if this RS exposes its own JWKS

def build_prm_route(config: OAuthConfig) -> Route:
    """Return a Starlette Route serving the PRM document."""
    metadata = ProtectedResourceMetadata(
        resource=config.resource_uri,
        authorization_servers=[config.authorization_server_url],
    )
    async def handle(_request: Request) -> JSONResponse:
        return JSONResponse(asdict(metadata))
    return Route("/.well-known/oauth-protected-resource", handle, methods=["GET"])
```

### Pattern 4: Per-Tool Scope Enforcement

**What:** MCP tools are dispatched by the MCP SDK based on the tool name. Per-tool scope enforcement adds a check INSIDE the tool handler (not at the middleware level) — the middleware enforces a baseline scope (`agent-brain:read`), and individual tools check for finer-grained scopes.

**When to use:** Required scopes differ across tools:
- `readOnlyHint: true` tools (`search_documents`, `explain_result`, `list_folders`, etc.) → `agent-brain:read`
- Mutation tools (`index_folder`, `add_documents`, `inject_documents`, `wait_for_job`) → `agent-brain:index`
- Destructive tools (`cancel_job`, `remove_folder`, `clear_cache`) → `agent-brain:admin`
- Subscription tools (`corpus://status`, `corpus://folders`, `job://`) → `agent-brain:subscribe`

**Trade-offs:** The MCP SDK does not natively inject per-tool scope requirements via decorator. The cleanest approach is a `scope_guard(required_scope)` callable that reads `request.state.auth.scopes` and raises `McpError(UNAUTHORIZED)` if the required scope is absent.

```python
# agent_brain_mcp/security/scope_guard.py (NEW)
from mcp.types import ErrorCode, McpError

def require_scope(required: str) -> Callable:
    """Return a guard callable that raises McpError if scope is missing."""
    async def guard(request: Request) -> None:
        auth = getattr(getattr(request, "state", None), "auth", None)
        if auth is None:
            return  # auth mode is none/basic — no scope enforcement at tool level
        scopes: list[str] = getattr(auth, "scopes", [])
        if required not in scopes:
            raise McpError(
                ErrorCode.InvalidRequest,
                f"Insufficient scope: '{required}' required",
            )
    return guard

# Usage in agent_brain_mcp/tools/index.py (MODIFY)
_require_index = require_scope("agent-brain:index")

async def handle_index_folder(request: Request, params: IndexFolderParams) -> ToolResult:
    await _require_index(request)  # raises McpError if lacking agent-brain:index
    # ... rest of handler
```

**Note on request context:** The MCP SDK's low-level `Server` handlers receive a `RequestContext` that carries the underlying Starlette `Request`. `BearerAuthBackend` populates `request.state.auth` before the MCP handler fires. The `scope_guard` reads from `request.state.auth.scopes`, the same attribute set by the Starlette `AuthenticationMiddleware`.

### Pattern 5: `McpHttpBackend` Client-Side OAuth Dance

**What:** When `McpHttpBackend` connects to an OAuth-protected MCP server, it passes an `OAuthClientProvider` (from `mcp.client.auth`) to `streamablehttp_client` via the `auth` kwarg. The SDK's `OAuthClientProvider` implements `httpx.Auth.async_auth_flow()` — a generator that transparently handles the full dance:
1. Initial request with no token → 401 + `WWW-Authenticate: Bearer resource_metadata="..."`
2. Client fetches PRM from `resource_metadata` URL
3. Client discovers AS via PRM's `authorization_servers[0]`
4. Client fetches OASM from AS `/.well-known/oauth-authorization-server`
5. DCR: POST to AS `/register` with client metadata → receives `client_id`
6. PKCE: generate `code_verifier` (128 chars) + `code_challenge` (SHA256, base64url)
7. Redirect to AS `/authorize?response_type=code&client_id=...&code_challenge=...&resource=...`
8. User authenticates (browser or device flow)
9. AS redirects back with `?code=<auth_code>&state=<csrf>`
10. Client POSTs to AS `/token` with `grant_type=authorization_code&code_verifier=...`
11. AS returns `access_token` + `refresh_token` + `expires_in`
12. Client retries original request with `Authorization: Bearer <access_token>`
13. On subsequent requests: if token is expired, use refresh token at `/token` with `grant_type=refresh_token`

**When to use:** Only when `AGENT_BRAIN_AUTH=oauth` is detected and the MCP URL is non-loopback.

**Trade-offs:** The current (June 2026) MCP CLI client refresh-token gap: PR #2039 in the SDK is open. The SDK's `OAuthClientProvider` supports token refresh in `async_auth_flow` but `McpHttpBackend` must implement `FileTokenStorage` to persist tokens between calls (Pattern A = fresh client per call, so tokens are lost between invocations without file-backed storage).

```python
# agent_brain_mcp/client.py (MODIFY — McpHttpBackend)
from mcp.client.auth import OAuthClientProvider
from mcp.client.streamable_http import streamablehttp_client
from agent_brain_mcp.oauth.token_storage import FileTokenStorage

class McpHttpBackend:
    def __init__(self, url: str, api_key: str | None = None,
                 oauth_storage_dir: Path | None = None) -> None:
        self._url = url
        self._api_key = api_key
        # oauth_storage_dir: None = memory-only; Path = persist across calls
        self._token_storage = (
            FileTokenStorage(oauth_storage_dir) if oauth_storage_dir else InMemoryTokenStorage()
        )

    async def _oauth_client_provider(self) -> OAuthClientProvider | None:
        """Return OAuthClientProvider if server is OAuth-protected, else None."""
        from agent_brain_mcp.config import get_mcp_settings
        settings = get_mcp_settings()
        if settings.AGENT_BRAIN_AUTH != "oauth":
            return None
        return OAuthClientProvider(
            server_url=self._url,
            client_metadata=ClientMetadata(
                client_name="agent-brain-cli",
                redirect_uris=["http://127.0.0.1:0/callback"],  # local callback server
                grant_types=["authorization_code", "refresh_token"],
                response_types=["code"],
            ),
            storage=self._token_storage,
            redirect_handler=_open_browser_redirect,    # opens system browser
            callback_handler=_local_callback_server,    # local HTTP server, captures code
        )

    @asynccontextmanager
    async def _http_client(self) -> AsyncIterator[ClientSession]:
        oauth = await self._oauth_client_provider()
        async with streamablehttp_client(
            url=self._url,
            headers=({"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}),
            auth=oauth,         # None = no OAuth; OAuthClientProvider = full dance
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                yield session
```

---

## Data Flow

### Full Challenge → Dance → Token → Scoped Call Flow

```
McpHttpBackend._http_client()
    │
    │  streamablehttp_client(url, auth=OAuthClientProvider)
    │
    ▼
[FIRST REQUEST — no token yet]
    │  POST /mcp  (no Authorization header)
    ▼
RequireAuthMiddleware
    │  no token → 401 Unauthorized
    │  WWW-Authenticate: Bearer error="invalid_token",
    │    resource_metadata="https://brain.example.com/.well-known/oauth-protected-resource"
    ▼
OAuthClientProvider.async_auth_flow() intercepts 401
    │
    ├─[1] GET /.well-known/oauth-protected-resource
    │       → { resource, authorization_servers: ["https://brain.example.com"],
    │           scopes_supported: ["agent-brain:read", ...] }
    │
    ├─[2] GET https://brain.example.com/.well-known/oauth-authorization-server
    │       → { issuer, token_endpoint, authorization_endpoint,
    │           registration_endpoint, revocation_endpoint, ... }
    │
    ├─[3] POST /register  (Dynamic Client Registration)
    │       → { client_id, client_secret (if confidential) }
    │
    ├─[4] PKCE: generate code_verifier (128 chars), code_challenge = BASE64URL(SHA256(verifier))
    │
    ├─[5] Open browser → /authorize?response_type=code&client_id=...
    │                       &code_challenge=...&code_challenge_method=S256
    │                       &resource=https://brain.example.com&scope=agent-brain:read
    │
    ├─[6] User authenticates → AS redirects → http://127.0.0.1:<port>/callback?code=...&state=...
    │
    ├─[7] POST /token
    │       grant_type=authorization_code&code=...&code_verifier=...
    │       → { access_token, refresh_token, expires_in: 900, token_type: "Bearer" }
    │
    ├─[8] store in FileTokenStorage
    │
    └─[9] retry original POST /mcp with Authorization: Bearer <access_token>

[SUBSEQUENT REQUESTS — token in storage]
    │  OAuthClientProvider.async_auth_flow()
    │    → loads token from FileTokenStorage
    │    → if not expired: inject Authorization: Bearer <access_token>
    │    → if expired: POST /token grant_type=refresh_token → new access_token
    │
    ▼
RequireAuthMiddleware
    │  BearerAuthBackend.authenticate() → calls TokenVerifier.verify_token(token)
    │    Co-located: OAuthAuthorizationServerProvider.load_access_token(token)
    │                  → validates JWT signature, exp, aud
    │    Split: JwksTokenVerifier → PyJWKClient.get_signing_key(kid)
    │                              → jwt.decode(token, key, algorithms=["RS256"])
    │  → AccessToken { scopes: ["agent-brain:read", "agent-brain:index"], ... }
    │  → request.state.auth.scopes = ["agent-brain:read", "agent-brain:index"]
    ▼
StreamableHTTPSessionManager.handle_request()
    │
    ▼
MCP tool dispatch → tool handler (e.g. handle_index_folder)
    │  scope_guard("agent-brain:index")(request)
    │    → scopes contains "agent-brain:index" → OK
    ▼
Tool executes → result returned to client
```

### Key Data Flows

1. **PRM-first discovery:** The 401 response contains a `resource_metadata` URL. The client MUST fetch this first to discover where the AS lives. Do not hard-code the AS URL client-side.

2. **Token `aud` validation:** The issued JWT's `aud` claim MUST equal the `resource` field in the PRM document. This is verified by `TokenVerifier.verify_token()`. Mismatch = 401 even with a valid-looking signature.

3. **Scope downscoping at authorize:** The MCP client requests the specific scopes it needs (derived from the PRM `scopes_supported`). The AS issues tokens with only the granted scopes. The `RequireAuthMiddleware` baseline scope + per-tool `scope_guard` enforce the granted set.

4. **Refresh token rotation:** Each refresh token use issues a new refresh token. The old one is revoked. `FileTokenStorage` must atomically update both `access_token` and `refresh_token` on every refresh cycle.

---

## Integration Points

### New vs Modified Files (Explicit)

| File | Status | Change |
|------|--------|--------|
| `agent_brain_server/api/security.py` | MODIFY | Add `verify_oauth_token`; add `get_auth_dependency()` dispatch; add `_noop_auth` |
| `agent_brain_server/api/main.py` | MODIFY | Mount PRM + OASM routes when `AGENT_BRAIN_AUTH=oauth`; startup gate validates OAuth config |
| `agent_brain_server/api/routers/*.py` | MODIFY (all gated routers) | Replace `Depends(verify_bearer_token)` with `Depends(get_auth_dependency())` |
| `agent_brain_server/config/settings.py` | MODIFY | Add `AGENT_BRAIN_AUTH`, `AGENT_BRAIN_OAUTH_ISSUER`, `AGENT_BRAIN_OAUTH_AUDIENCE` |
| `agent_brain_mcp/http.py` | MODIFY | Relax loopback guard in oauth mode; accept `auth_mode` + `token_verifier` + `oauth_routes` params; inject `RequireAuthMiddleware` |
| `agent_brain_mcp/cli.py` | MODIFY | Startup gate: refuse public bind unless `AGENT_BRAIN_AUTH=oauth`; banner update |
| `agent_brain_mcp/config.py` | MODIFY | Add `AGENT_BRAIN_OAUTH_RESOURCE`, `AGENT_BRAIN_OAUTH_JWKS_URI`, `AGENT_BRAIN_OAUTH_INTROSPECT_URI`, `AGENT_BRAIN_OAUTH_SECRET_KEY` |
| `agent_brain_mcp/client.py` | MODIFY | `McpHttpBackend`: add `OAuthClientProvider` plumbing; `FileTokenStorage` constructor |
| `agent_brain_mcp/security/__init__.py` | UNCHANGED | Pure re-export shim; contract preserved |
| `agent_brain_mcp/security/scope_guard.py` | NEW | `require_scope(scope)` callable |
| `agent_brain_mcp/oauth/__init__.py` | NEW | Re-exports: `OAuthProvider`, `JwksTokenVerifier`, `IntrospectionTokenVerifier`, `build_oauth_routes` |
| `agent_brain_mcp/oauth/provider.py` | NEW | Full `OAuthAuthorizationServerProvider` impl (co-located AS) |
| `agent_brain_mcp/oauth/token_store.py` | NEW | In-memory stores: `AuthCodeStore`, `AccessTokenStore`, `RefreshTokenStore` |
| `agent_brain_mcp/oauth/client_registry.py` | NEW | `OAuthClientRegistry` for DCR |
| `agent_brain_mcp/oauth/verifiers.py` | NEW | `JwksTokenVerifier` (PyJWT+PyJWKClient); `IntrospectionTokenVerifier` |
| `agent_brain_mcp/oauth/token_storage.py` | NEW | `FileTokenStorage` + `InMemoryTokenStorage` for `McpHttpBackend` |
| `agent_brain_mcp/oauth/metadata.py` | NEW | `build_prm_route()`, `build_oasm_route()` |
| `agent_brain_mcp/tools/*.py` | MODIFY (mutation/admin tools) | Add `await require_scope("agent-brain:index")(request)` or `:admin` guards |

### External Service Integration

| Service / Standard | Integration Pattern | Confidence | Notes |
|-------------------|---------------------|------------|-------|
| MCP SDK `mcp.server.auth` | Use `RequireAuthMiddleware`, `BearerAuthBackend`, `create_auth_routes()`, `OAuthAuthorizationServerProvider` protocol | HIGH (SDK source verified) | SDK is the primary integration point; do not re-implement these |
| MCP SDK `mcp.client.auth` | Use `OAuthClientProvider`, `TokenStorage` protocol | MEDIUM (PR #2039 open as of June 2026) | Client-side refresh token support may be incomplete; build `FileTokenStorage` defensively |
| PyJWT (split topology) | `jwt.PyJWKClient` + `jwt.decode()` with `RS256` algorithm | HIGH (well-established) | Cache JWKS keys; `PyJWKClient(uri, cache_keys=True, cache_jwk_set=True, lifespan=300)` |
| Keycloak (CI) | Standard OIDC token endpoint; JWKS at `/realms/<realm>/protocol/openid-connect/certs` | MEDIUM (standard OIDC) | Use `IntrospectionTokenVerifier` if opaque tokens; `JwksTokenVerifier` if JWTs |
| RFC 9728 (PRM) | `GET /.well-known/oauth-protected-resource` | HIGH (canonical spec) | `resource` field must equal JWT `aud`; mount at root not sub-path |
| RFC 8414 (OASM) | `GET /.well-known/oauth-authorization-server` | HIGH (canonical spec) | Co-located: mount on same Starlette app; split: external IdP serves this |
| RFC 7591 (DCR) | `POST /register` via `create_auth_routes()` | HIGH (SDK handles this) | Enable `client_registration_options.enabled=True` in co-located mode |
| RFC 7636 (PKCE) | SDK's `PKCEParameters.generate()` | HIGH (SDK source verified) | Always `S256`; 128-char verifier; SHA256 + base64url challenge |
| RFC 8707 (Resource Indicators) | `resource=<uri>` param in `/authorize` and `/token` | HIGH (SDK source verified) | `OAuthClientProvider._perform_authorization_code_grant()` includes this |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `verify_oauth_token` (server) ↔ JWT | Direct decode in-process (co-located) or JWKS fetch (split) | No cross-package call; server is self-contained for auth |
| `RequireAuthMiddleware` ↔ `TokenVerifier` | Constructor injection; `verify_token()` called per request | Pass `ProviderTokenVerifier` (co-located) or `JwksTokenVerifier` (split) |
| `scope_guard` ↔ `request.state.auth` | `BearerAuthBackend` populates `request.state.auth.scopes` before tool handler fires | Starlette `AuthenticationMiddleware` must wrap the full app stack |
| `McpHttpBackend` ↔ `OAuthClientProvider` | Constructor injection; `streamablehttp_client(auth=provider)` | `FileTokenStorage` persists across Pattern A per-call invocations |
| `agent-brain-server` ↔ `agent-brain-mcp` | MCP server calls REST API over loopback; REST API has its own auth mode; in oauth mode, MCP server still uses loopback + static key to call the REST API | The TWO auth layers are independent: MCP clients authenticate to MCP server via OAuth; MCP server authenticates to REST API via static Bearer (existing SECURITY-01 key) |

---

## Two Deployment Topologies — Component Differences

### Topology A: Co-Located AS/RS (Single Binary)

All OAuth endpoints live in the same `agent-brain-mcp` Starlette app:

```
agent-brain-mcp Starlette app
    ├── GET  /.well-known/oauth-protected-resource   → { resource, authorization_servers: [self] }
    ├── GET  /.well-known/oauth-authorization-server → { issuer: self, token_endpoint, ... }
    ├── POST /token                                  → issue/refresh JWT (signed with local secret)
    ├── GET  /authorize                              → PKCE auth code flow
    ├── POST /register                               → DCR (optional)
    ├── POST /revoke                                 → token revocation
    └── /mcp  →  [RequireAuthMiddleware]
                  → [BearerAuthBackend + ProviderTokenVerifier]
                  → StreamableHTTPSessionManager
```

New components unique to Topology A:
- `OAuthAuthorizationServerProvider` (full impl in `oauth/provider.py`)
- `OAuthTokenStore` (in-memory, `oauth/token_store.py`)
- `OAuthClientRegistry` (in-memory, `oauth/client_registry.py`)
- JWT signed with `AGENT_BRAIN_OAUTH_SECRET_KEY` (HS256) or a local RSA key pair
- `ProviderTokenVerifier` wraps the provider's `load_access_token()`

Token validation: fully local — no network call. The AS and RS share the same in-process `OAuthAuthorizationServerProvider`, so `verify_token()` reads from the same in-memory store that issued the token.

### Topology B: Split AS/RS (External IdP)

The `agent-brain-mcp` Starlette app exposes ONLY the PRM endpoint:

```
agent-brain-mcp Starlette app
    ├── GET  /.well-known/oauth-protected-resource   → { resource, authorization_servers: [idp_url] }
    └── /mcp  →  [RequireAuthMiddleware]
                  → [BearerAuthBackend + JwksTokenVerifier]
                  → StreamableHTTPSessionManager
```

New components unique to Topology B:
- `JwksTokenVerifier` (fetches JWKS from `AGENT_BRAIN_OAUTH_JWKS_URI`, caches keys 5 min)
- OR `IntrospectionTokenVerifier` (calls `AGENT_BRAIN_OAUTH_INTROSPECT_URI` per-token)
- `AGENT_BRAIN_OAUTH_JWKS_URI` / `AGENT_BRAIN_OAUTH_INTROSPECT_URI` settings

Token validation: `JwksTokenVerifier` — validate JWT signature locally using cached JWKS keys (preferred; no network per request). `IntrospectionTokenVerifier` — one HTTPS call per token (use only if IdP issues opaque tokens). For Keycloak CI, use `JwksTokenVerifier`; Keycloak issues JWTs and exposes a JWKS endpoint.

---

## Build Order

Ordered by: design-doc + security-review first (DoD gate), then foundation → server-side → client-side → scope enforcement → split topology → integration tests.

```
PHASE 1 — Design Doc + Security Review Gate (DoD prerequisite)
    • Write v4 OAuth design doc (threat model, topology comparison, scope definitions,
      token lifecycle, DCR policy, DPoP decision, data-at-rest for token store)
    • Independent security review before ANY implementation code
    • Design doc must be approved before Phase 2 begins
    WHY FIRST: the DoD explicitly requires this; security review may change
               scope definitions or topology decisions

PHASE 2 — PRM + Settings Foundation (no auth enforcement yet)
    • NEW: agent_brain_server/config/settings.py → AGENT_BRAIN_AUTH, AGENT_BRAIN_OAUTH_ISSUER
    • NEW: agent_brain_mcp/config.py → AGENT_BRAIN_OAUTH_RESOURCE, JWKS/introspect URIs
    • NEW: agent_brain_mcp/oauth/metadata.py → build_prm_route(), build_oasm_route()
    • MODIFY: agent_brain_mcp/http.py → accept oauth_routes kwarg; mount PRM route in oauth mode
    • MODIFY: agent_brain_mcp/cli.py → startup gate respects AGENT_BRAIN_AUTH=oauth
    WHY SECOND: PRM is the root of OAuth discovery; everything else depends on the
                resource URI and AS URL being correctly configured; verify the
                /.well-known/oauth-protected-resource response before adding auth middleware

PHASE 3 — Co-Located AS (Topology A server-side)
    Depends on: Phase 2 (settings + metadata)
    • NEW: agent_brain_mcp/oauth/token_store.py
    • NEW: agent_brain_mcp/oauth/client_registry.py
    • NEW: agent_brain_mcp/oauth/provider.py (OAuthAuthorizationServerProvider full impl)
    • NEW: agent_brain_mcp/oauth/__init__.py
    • MODIFY: agent_brain_mcp/http.py → inject RequireAuthMiddleware + auth routes in oauth mode
    • MODIFY: agent_brain_server/api/security.py → add verify_oauth_token + get_auth_dependency()
    • MODIFY: agent_brain_server/api/main.py → mount PRM + OASM routes; startup gate validates config
    • MODIFY: agent_brain_server/api/routers/*.py → swap to get_auth_dependency()
    WHY THIRD: RS token verification (RequireAuthMiddleware) requires the AS to be issuing
               tokens before end-to-end tests can pass; build AS first, then enforce

PHASE 4 — Client-Side OAuth Dance (McpHttpBackend)
    Depends on: Phase 3 (server is issuing tokens)
    • NEW: agent_brain_mcp/oauth/token_storage.py (FileTokenStorage + InMemoryTokenStorage)
    • MODIFY: agent_brain_mcp/client.py → McpHttpBackend passes OAuthClientProvider
    WHY FOURTH: can't test the client dance without a working server; Phase 3 gives
                a real AS to dance against

PHASE 5 — Per-Tool Scope Enforcement
    Depends on: Phase 3 (scopes in access tokens); Phase 4 (client requests specific scopes)
    • NEW: agent_brain_mcp/security/scope_guard.py
    • MODIFY: agent_brain_mcp/tools/{index,inject,folders,cache,jobs}.py → add scope guards
    WHY FIFTH: enforcing granular scopes requires the full token validation stack to be
               working; adding scope guards before Phase 3 yields untestable code

PHASE 6 — Split AS/RS (Topology B — external IdP, Keycloak in CI)
    Depends on: Phase 3 structure (verifier interface is already abstracted)
    • NEW: agent_brain_mcp/oauth/verifiers.py → JwksTokenVerifier + IntrospectionTokenVerifier
    • MODIFY: agent_brain_mcp/http.py → wire JwksTokenVerifier when topology=split
    • CI: spin up Keycloak container; configure realm + client + scopes; verify end-to-end
    WHY SIXTH: split topology reuses the Phase 3 middleware stack; only the TokenVerifier
               impl changes; easiest to add once Topology A is fully tested

PHASE 7 — Integration Tests + DoD Validation
    Depends on: All prior phases
    • E2E: 401 challenge → PRM discovery → OASM discovery → DCR → PKCE dance → tool call
    • Token refresh path (access_token expired, refresh_token present)
    • Scope enforcement: read-only client gets 403 on admin tool
    • Topology B: Keycloak-issued JWT accepted
    • Coverage gate: ≥ 90% on agent_brain_mcp/oauth/ (per DoD)
```

---

## Scaling Considerations

This is a single-user, single-instance system. OAuth does not change the scaling posture — it gates access, not throughput.

| Concern | With `AGENT_BRAIN_AUTH=none` | With `AGENT_BRAIN_AUTH=oauth` |
|---------|------------------------------|-------------------------------|
| Per-request overhead | Static compare (~0.1µs) | JWT decode: ~0.5ms (co-located); JWKS cache hit: ~0.5ms; JWKS cache miss: ~50ms network |
| Token store memory | N/A | In-memory; bounded by number of active sessions; expected < 100 tokens |
| Token refresh storms | N/A | 15-min access tokens; refresh on expiry; no thundering herd for single-user |
| JWKS cache staleness | N/A | Cache 5 min; forced refresh on `kid` miss |

The primary operational risk is **JWKS cache staleness** in split topology after an IdP key rotation. Mitigate with: force-refresh on unknown `kid`, plus a background refresh every 5 min.

---

## Anti-Patterns

### Anti-Pattern 1: Double-Auth (Running Static Bearer Check Alongside JWT Verify)

**What people do:** Keep `verify_bearer_token` on all routers AND add `verify_oauth_token` as a second dependency.

**Why it's wrong:** A request carrying a valid OAuth JWT will fail the static Bearer check (the JWT token string is not equal to `settings.API_KEY`), producing a spurious 401. Alternatively, a request with a raw API key bypasses JWT scope enforcement entirely.

**Do this instead:** `get_auth_dependency()` returns ONE dependency based on `AGENT_BRAIN_AUTH`. In `oauth` mode, only `verify_oauth_token` runs. In `basic` mode, only `verify_bearer_token` runs. The two are mutually exclusive on the request path.

### Anti-Pattern 2: Mounting Well-Known Routes Inside the Auth Middleware

**What people do:** Add `/.well-known/oauth-protected-resource` AFTER wrapping the Starlette app with `RequireAuthMiddleware`.

**Why it's wrong:** The PRM endpoint MUST be publicly accessible without authentication — it is the discovery document that tells the client HOW to authenticate. If it's behind `RequireAuthMiddleware`, the client gets a 401 before it can discover the AS, creating an unresolvable chicken-and-egg failure.

**Do this instead:** In `build_asgi_app()`, mount well-known routes on the Starlette `routes` list BEFORE wrapping the `Starlette` app instance with `RequireAuthMiddleware`. The middleware wraps the entire app, but Starlette routes added before the middleware is applied get the request first — OR, add well-known routes to a separate outer Starlette app that then delegates to the auth-wrapped inner app.

### Anti-Pattern 3: Resource URI Mismatch Between PRM and JWT `aud` Claim

**What people do:** Set `AGENT_BRAIN_OAUTH_RESOURCE=https://brain.example.com/` (trailing slash) in the AS when issuing JWTs, but serve the PRM with `resource=https://brain.example.com` (no trailing slash).

**Why it's wrong:** `TokenVerifier.verify_token()` checks `access_token.resource == settings.resource_uri`. String comparison fails. Every token is rejected with 401.

**Do this instead:** Derive both the PRM `resource` field and the JWT `aud` claim from the SAME `AGENT_BRAIN_OAUTH_RESOURCE` setting. Never hard-code either. Normalize the URI (strip trailing slash or always add it — pick one, be consistent).

### Anti-Pattern 4: Using the Loopback Guard Removal Without Enabling TLS

**What people do:** Set `AGENT_BRAIN_AUTH=oauth` to bypass the loopback host guard, then bind to `0.0.0.0` without TLS termination, using plain HTTP for the MCP endpoint.

**Why it's wrong:** OAuth 2.1 requires TLS for all token exchanges. Access tokens and auth codes in plaintext HTTP are trivially intercepted. PKCE protects against code interception but not against token theft in flight.

**Do this instead:** `AGENT_BRAIN_AUTH=oauth` startup gate MUST also check that `AGENT_BRAIN_TLS_CERT` is set (or that a TLS-terminating reverse proxy is configured). Log a CRITICAL warning and exit 2 if `AGENT_BRAIN_AUTH=oauth` AND `AGENT_BRAIN_TLS=false` (the operator must explicitly acknowledge the risk with `AGENT_BRAIN_OAUTH_ALLOW_PLAINTEXT=true`).

### Anti-Pattern 5: Pattern A (Fresh MCP Client per Call) Without Token Persistence

**What people do:** Rely on `McpHttpBackend` default in-memory token storage for the OAuth token across Pattern-A per-call invocations.

**Why it's wrong:** Pattern A creates a fresh `streamablehttp_client` per MCP call. In-memory token storage is discarded when the async context exits. The next call triggers the full OAuth dance again (browser redirect, user interaction). A 60-second agent workflow executes dozens of tool calls — each would require user approval.

**Do this instead:** Wire `FileTokenStorage(state_dir / "mcp-oauth-tokens.json")` into `McpHttpBackend`. `chmod 0o600` the file. The OAuth dance happens once; subsequent calls load the cached token and refresh silently when expired.

---

## Sources

- MCP Python SDK `mcp.server.auth` module structure: [DeepWiki — Authentication & Security](https://deepwiki.com/modelcontextprotocol/python-sdk/7-authentication-and-security) — HIGH confidence (SDK source verified)
- `OAuthClientProvider` and `async_auth_flow` implementation: [python-sdk/src/mcp/client/auth/oauth2.py](https://github.com/modelcontextprotocol/python-sdk/blob/main/src/mcp/client/auth/oauth2.py) — HIGH confidence (source read directly)
- MCP simple-auth example (AS/RS separation): [python-sdk examples/servers/simple-auth](https://github.com/modelcontextprotocol/python-sdk/tree/main/examples/servers/simple-auth) — HIGH confidence
- `create_auth_routes()` endpoint list: SDK source via DeepWiki — HIGH confidence
- RFC 9728 mount path issue in multi-tenant deployments: [GitHub issue #1751](https://github.com/modelcontextprotocol/python-sdk/issues/1751) — HIGH confidence (active issue, directly relevant)
- RFC 9728 PRM URL mismatch issue: [GitHub issue #1400](https://github.com/modelcontextprotocol/python-sdk/issues/1400) — HIGH confidence
- MCP client ignores path-based AS URL: [Microsoft Q&A — MCP Client Ignores authorization_servers Path](https://learn.microsoft.com/en-nz/answers/questions/5904511/mcp-client-ignores-authorization-servers-path-from) — MEDIUM confidence (confirmed by multiple community reports)
- Refresh-token gap in MCP CLI clients: [SecureCoders blog post](https://www.securecoders.com/blog/mcp-cli-refresh-token-gap) — MEDIUM confidence (June 2026 survey; SDK PR #2039 open)
- MCP authorization spec (draft): [modelcontextprotocol.info/specification/draft/basic/authorization/](https://modelcontextprotocol.info/specification/draft/basic/authorization/) — HIGH confidence (canonical spec)
- FastAPI JWT + scope enforcement: [FastAPI security tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) — HIGH confidence
- PyJWT `PyJWKClient` JWKS caching: [PyPI + FastAPI Keycloak integration](https://skycloak.io/blog/keycloak-fastapi-python-api-authentication/) — MEDIUM confidence (verified pattern, not official docs)
- Existing codebase read directly (HIGH confidence):
  - `agent_brain_server/api/security.py` (verify_bearer_token, static-Bearer dep)
  - `agent_brain_server/api/main.py` (router wiring, startup gate, lifespan)
  - `agent_brain_server/config/settings.py` (Settings class, API_KEY, INSECURE_NO_AUTH)
  - `agent_brain_mcp/http.py` (build_asgi_app, StreamableHTTPSessionManager, loopback guard)
  - `agent_brain_mcp/client.py` (McpHttpBackend, Pattern A, DEFAULT_ENV_ALLOWLIST)
  - `agent_brain_mcp/security/__init__.py` (file sandbox re-export shim, "no logic" contract)
  - `docs/roadmaps/mcp/v4-oauth-for-remote.md` (deployment shapes, scope definitions, token lifecycle)
  - `.planning/PROJECT.md` (v10.4 milestone scope, OAuth requirements, DoD)

---

*Architecture research for: Agent Brain v10.4 — OAuth 2.1 integration with FastAPI + MCP Streamable HTTP*
*Researched: 2026-06-14*
