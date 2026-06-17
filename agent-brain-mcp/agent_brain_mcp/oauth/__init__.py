"""OAuth 2.1 Authorization Server core for Agent Brain MCP server (Phase 67 Plan 02).

This package implements the co-located Authorization Server (AS) primitives
required by OAUTH-04 and the AS half of Resource Indicators (OAUTH-08), plus
the client-side browser/loopback UX pieces from Phase 69 Plans 01-03.

Sub-modules
-----------
keys
    RS256 keypair generation, KID computation, and JWKS document serialization.
    Provides: ``generate_rs256_keypair``, ``compute_kid``, ``build_jwks``,
    ``get_or_create_signing_key``, ``SigningKey``.

tokens
    PyJWT-based RS256 JWT minting with the full OAuth 2.1 claim set
    (iss/aud/exp/nbf/iat/jti/scope/client_id) and an in-memory store for
    authorization codes, access tokens, and rotating refresh tokens.
    Provides: ``mint_access_token``, ``InMemoryTokenStore``.

provider
    Concrete ``OAuthAuthorizationServerProvider`` implementation wiring the
    in-memory store + signing key into the 9 SDK abstract methods.
    Also provides ``reject_non_s256_pkce()`` -- the S256-only enforcement helper
    (Plan 04 wires this into the live /authorize route).
    Provides: ``AgentBrainAuthServerProvider``, ``reject_non_s256_pkce``.

token_storage
    Client-side ``TokenStorage`` Protocol implementation (Phase 69 Plan 01).
    Persists both the ``OAuthToken`` and the ``OAuthClientInformationFull`` in a
    single JSON file at ``state_dir/mcp-oauth-tokens.json`` with mode ``0o600``
    so that Pattern A (fresh subprocess per CLI call) reuses cached tokens
    without re-triggering the browser OAuth dance.
    Provides: ``FileTokenStorage``, ``TOKEN_FILE_NAME``.

oauth_handlers
    Browser redirect handler and ephemeral loopback callback server (Phase 69
    Plan 02).  These are the two bespoke UX callables the SDK
    ``OAuthClientProvider`` requires:
    - ``build_redirect_handler`` -- opens the system browser + prints URL to
      stderr as a headless fallback.
    - ``LoopbackCallbackServer`` -- binds ``127.0.0.1:0`` (OS-assigned port),
      serves one request, captures ``(code, state)`` from the redirect GET.
    - ``build_callback_handler`` -- wraps ``LoopbackCallbackServer`` in the
      ``Callable[[], Awaitable[tuple[str, str | None]]]`` shape the SDK expects.
    Provides: ``build_redirect_handler``, ``LoopbackCallbackServer``,
    ``build_callback_handler``.

oauth_client
    Client-side OAuthClientProvider factory (Phase 69 Plan 03).  Assembles
    the SDK ``OAuthClientProvider`` from ``FileTokenStorage``, the loopback
    handlers, and ``OAuthClientMetadata`` requesting the full CLI scope union
    (read + index + admin) with a 300 s dance timeout.  DCR path (no
    ``client_metadata_url``).
    Provides: ``build_oauth_client_provider``, ``CLIENT_SCOPES``.

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  "Deployment Shape A: Co-Located AS + RS"
  "AS / RS / Public-Route Boundary"
  "Token Termination Data Flow"
  "Client-Side Token Storage: FileTokenStorage chmod 0o600 Required (Pattern A)"
  "Decision C: Browser / Loopback UX"
"""

from agent_brain_mcp.oauth.oauth_client import (
    CLIENT_SCOPES,
    build_oauth_client_provider,
)
from agent_brain_mcp.oauth.oauth_handlers import (
    LoopbackCallbackServer,
    build_callback_handler,
    build_redirect_handler,
)
from agent_brain_mcp.oauth.token_storage import FileTokenStorage

__all__ = [
    "FileTokenStorage",
    "build_redirect_handler",
    "LoopbackCallbackServer",
    "build_callback_handler",
    "build_oauth_client_provider",
    "CLIENT_SCOPES",
]
