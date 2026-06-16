"""OAuth 2.1 Authorization Server core for Agent Brain MCP server (Phase 67 Plan 02).

This package implements the co-located Authorization Server (AS) primitives
required by OAUTH-04 and the AS half of Resource Indicators (OAUTH-08).

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
    Also provides ``reject_non_s256_pkce()`` — the S256-only enforcement helper
    (Plan 04 wires this into the live /authorize route).
    Provides: ``AgentBrainAuthServerProvider``, ``reject_non_s256_pkce``.

token_storage
    Client-side ``TokenStorage`` Protocol implementation (Phase 69 Plan 01).
    Persists both the ``OAuthToken`` and ``OAuthClientInformationFull`` in a
    single JSON file at ``state_dir/mcp-oauth-tokens.json`` with mode ``0o600``
    so that Pattern A (fresh subprocess per CLI call) reuses cached tokens
    without re-triggering the browser OAuth dance.
    Provides: ``FileTokenStorage``, ``TOKEN_FILE_NAME``.

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"Deployment Shape A: Co-Located AS + RS"
  §"AS / RS / Public-Route Boundary"
  §"Token Termination Data Flow"
  §"Client-Side Token Storage: FileTokenStorage chmod 0o600 Required (Pattern A)"
"""

from agent_brain_mcp.oauth.token_storage import FileTokenStorage

__all__ = ["FileTokenStorage"]
