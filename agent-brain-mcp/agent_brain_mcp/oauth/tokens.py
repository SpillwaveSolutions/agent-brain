"""JWT minting (RS256) and in-memory token store (Phase 67 Plan 02 Task 2).

Provides the "mint" half of "wire + configure + mint" for the co-located AS.
The SDK's ``create_auth_routes()`` (wired in Plan 04) calls the provider
methods (Plan 02 Task 3) which call into this module for minting + storage.

Token claim set (OAUTH-04 / OAUTH-08)
--------------------------------------
Every issued access token JWT carries:
  - iss: the configured issuer (AGENT_BRAIN_OAUTH_ISSUER or co-located AS base URL)
  - aud: the RFC 8707 resource URI from the /authorize request  (OAUTH-08 AS half)
  - sub / client_id: the OAuth client ID
  - scope: space-joined list of granted scopes
  - iat: issued-at epoch
  - nbf: not-before epoch (== iat; tokens valid immediately)
  - exp: expiry epoch (iat + 900s / 15 min)
  - jti: unique token ID (secrets.token_urlsafe(16) — at least 128 bits entropy)

The ``aud`` claim binds to the ``resource`` parameter of the authorization and
token requests (RFC 8707 resource indicators — OAUTH-08). The Resource Server
validates this claim on every inbound MCP request (Phase 67 Plan 03).

In-memory store semantics
--------------------------
``InMemoryTokenStore`` holds three dicts (authorization codes, access tokens,
refresh tokens) keyed by their string value. These are module-local; a process
restart loses ALL tokens — a documented trade-off matching the in-memory
keypair lifecycle. DO NOT persist, serialize, or share this store across
processes.

Refresh token rotation (RFC 6749 / OAuth 2.1 § 6)
---------------------------------------------------
``InMemoryTokenStore.rotate_refresh_token()`` issues a new refresh token with
a fresh 30-day expiry, stores it, and IMMEDIATELY deletes the old token. If a
caller reuses an invalidated refresh token they will receive None from
``load_refresh_token()`` — the provider then responds with 400 invalid_grant.

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"Token lifecycle" (15-min access / 30-day rotating refresh)
  §"Canonical Resource URI Contract" (aud == resource, no mutation)
  §"Token Validation on /mcp" (the 5 RS checks in Phase 67)
  §"Deployment Shape A: Co-Located AS + RS"
"""

from __future__ import annotations

import secrets
import time
from typing import TYPE_CHECKING

import jwt

if TYPE_CHECKING:
    from agent_brain_mcp.oauth.keys import SigningKey

from mcp.server.auth.provider import AccessToken, AuthorizationCode, RefreshToken

# ---------------------------------------------------------------------------
# Token lifetime constants
# ---------------------------------------------------------------------------

ACCESS_TOKEN_TTL_SECONDS: int = 900
"""Access token TTL: 15 minutes (900 seconds).

Design doc §"Token lifecycle": "15-minute access token". This is the
``exp - iat`` delta of every minted access JWT.
"""

REFRESH_TOKEN_TTL_SECONDS: int = 30 * 24 * 3600
"""Refresh token TTL: 30 days (2 592 000 seconds).

Design doc §"Token lifecycle": "30-day rotating refresh token". Each
rotation resets the expiry to now + REFRESH_TOKEN_TTL_SECONDS.
"""


# ---------------------------------------------------------------------------
# JWT minting
# ---------------------------------------------------------------------------


def mint_access_token(
    *,
    client_id: str,
    scopes: list[str],
    resource: str,
    signing_key: SigningKey,
    issuer: str,
) -> str:
    """Mint an RS256-signed JWT access token with the required OAuth 2.1 claim set.

    The JWT ``aud`` claim is bound to ``resource`` (RFC 8707 — OAUTH-08 AS half).
    The resource value is used EXACTLY as supplied — no trailing-slash addition
    or removal. The Resource Server validates this claim on every /mcp request.

    Args:
        client_id: The OAuth client identifier. Stored as both ``sub`` and
            ``client_id`` claims.
        scopes: The list of granted OAuth scopes. Space-joined into the
            ``scope`` claim.
        resource: The RFC 8707 resource URI (``AGENT_BRAIN_OAUTH_RESOURCE``).
            Bound to the JWT ``aud`` claim without modification.
        signing_key: The process-lifetime ``SigningKey`` from ``keys.py``.
            The ``kid`` header on the JWT matches ``signing_key.kid``.
        issuer: The Authorization Server issuer URI. Used as the JWT ``iss``
            claim and must match what the Resource Server expects when
            validating ``iss == configured_issuer``.

    Returns:
        A compact RS256 JWT string.
    """
    now = int(time.time())
    claims: dict[str, object] = {
        "iss": issuer,
        "aud": resource,
        "sub": client_id,
        "client_id": client_id,
        "scope": " ".join(scopes),
        "iat": now,
        "nbf": now,
        "exp": now + ACCESS_TOKEN_TTL_SECONDS,
        "jti": secrets.token_urlsafe(16),
    }
    token: str = jwt.encode(
        claims,
        signing_key.private_key,
        algorithm="RS256",
        headers={"kid": signing_key.kid},
    )
    return token


# ---------------------------------------------------------------------------
# In-memory token / code / refresh store
# ---------------------------------------------------------------------------


class InMemoryTokenStore:
    """In-memory store for authorization codes, access tokens, and refresh tokens.

    Holds three independent dicts keyed by the string token/code value.
    Values are SDK model instances (AuthorizationCode, AccessToken, RefreshToken).

    IMPORTANT: this store is process-local. A server restart invalidates ALL
    entries — sessions will fail after restart and clients must re-authorize.
    This is the accepted trade-off for the co-located Shape A deployment
    (docs/plans/2026-06-14-mcp-v4-oauth-design.md §"Deployment Shape A").

    DO NOT persist, serialize, or share this store across processes.

    Thread safety: This class uses plain Python dicts. The GIL provides
    de-facto thread safety for CPython dict operations; however for production
    use in async contexts where multiple coroutines may interleave, callers
    should hold an asyncio.Lock around mutating operations if strict
    ordering matters. Phase 67 targets single-process single-worker
    deployment (Deployment Shape A) — the GIL is sufficient here.
    """

    def __init__(self) -> None:
        """Initialize all three empty dicts."""
        self._auth_codes: dict[str, AuthorizationCode] = {}
        self._access_tokens: dict[str, AccessToken] = {}
        self._refresh_tokens: dict[str, RefreshToken] = {}

    # ------------------------------------------------------------------
    # Authorization code methods (single-use)
    # ------------------------------------------------------------------

    def store_authorization_code(self, code_obj: AuthorizationCode) -> None:
        """Persist an authorization code.

        The code is keyed by ``code_obj.code``. An existing entry with the
        same code string is silently overwritten.

        Args:
            code_obj: The SDK ``AuthorizationCode`` to store.
        """
        self._auth_codes[code_obj.code] = code_obj

    def load_authorization_code(self, code: str) -> AuthorizationCode | None:
        """Look up an authorization code without consuming it.

        Args:
            code: The authorization code string.

        Returns:
            The ``AuthorizationCode``, or ``None`` if not found.
        """
        return self._auth_codes.get(code)

    def pop_authorization_code(self, code: str) -> AuthorizationCode | None:
        """Consume and return an authorization code (single-use).

        Removes the code from the store on the first call. Subsequent calls
        for the same code return ``None``, enforcing the one-time-use
        constraint (RFC 6749 §4.1.2).

        Args:
            code: The authorization code string.

        Returns:
            The ``AuthorizationCode`` if found and consumed, else ``None``.
        """
        return self._auth_codes.pop(code, None)

    # ------------------------------------------------------------------
    # Access token methods
    # ------------------------------------------------------------------

    def store_access_token(self, token_obj: AccessToken) -> None:
        """Persist an access token.

        The token is keyed by ``token_obj.token`` (the JWT string).

        Args:
            token_obj: The SDK ``AccessToken`` to store. Callers SHOULD set
                ``resource`` on the model so downstream introspection or
                verification can read it without re-decoding the JWT.
        """
        self._access_tokens[token_obj.token] = token_obj

    def load_access_token(self, token: str) -> AccessToken | None:
        """Look up an access token.

        Args:
            token: The JWT string.

        Returns:
            The ``AccessToken``, or ``None`` if not found or revoked.
        """
        return self._access_tokens.get(token)

    def revoke_access_token(self, token: str) -> None:
        """Remove an access token from the store (revocation).

        Idempotent — does nothing if the token is not present.

        Args:
            token: The JWT string to revoke.
        """
        self._access_tokens.pop(token, None)

    # ------------------------------------------------------------------
    # Refresh token methods (rotation)
    # ------------------------------------------------------------------

    def store_refresh_token(self, token_obj: RefreshToken) -> None:
        """Persist a refresh token.

        Args:
            token_obj: The SDK ``RefreshToken`` to store.
        """
        self._refresh_tokens[token_obj.token] = token_obj

    def load_refresh_token(self, token: str) -> RefreshToken | None:
        """Look up a refresh token.

        Args:
            token: The refresh token string.

        Returns:
            The ``RefreshToken``, or ``None`` if not found or invalidated.
        """
        return self._refresh_tokens.get(token)

    def rotate_refresh_token(self, old_token: str) -> RefreshToken | None:
        """Rotate a refresh token: invalidate old, issue new with 30-day expiry.

        Implements RFC 6749 / OAuth 2.1 §6 refresh-token rotation:
          1. Look up and remove the old refresh token.
          2. Generate a new token string (``secrets.token_urlsafe(32)``).
          3. Create a new ``RefreshToken`` with the same client_id and scopes
             but a fresh 30-day expiry.
          4. Store the new token and return it.

        If the old token is not found (already consumed or never issued),
        returns ``None`` — the provider should respond with 400 invalid_grant.

        Args:
            old_token: The refresh token string to invalidate.

        Returns:
            A new ``RefreshToken`` with a fresh 30-day expiry, or ``None``
            if ``old_token`` was not found.
        """
        existing = self._refresh_tokens.pop(old_token, None)
        if existing is None:
            return None

        new_token_value = secrets.token_urlsafe(32)
        new_expires_at = int(time.time()) + REFRESH_TOKEN_TTL_SECONDS

        new_rt = RefreshToken(
            token=new_token_value,
            client_id=existing.client_id,
            scopes=list(existing.scopes),
            expires_at=new_expires_at,
        )
        self._refresh_tokens[new_token_value] = new_rt
        return new_rt

    def revoke_refresh_token(self, token: str) -> None:
        """Remove a refresh token from the store.

        Idempotent — does nothing if the token is not present.

        Args:
            token: The refresh token string to revoke.
        """
        self._refresh_tokens.pop(token, None)

    def revoke_all_for_token(
        self, access_token_str: str, refresh_token_str: str
    ) -> None:
        """Remove both an access token and a refresh token atomically.

        Convenience method for ``revoke_token`` in the provider, which
        receives either an AccessToken or RefreshToken model and must clean
        up both if present.

        Args:
            access_token_str: The JWT string to remove from the access-token
                store (may be empty/sentinel if revocation is for refresh only).
            refresh_token_str: The refresh token string to remove (may be
                empty/sentinel if revocation is for access only).
        """
        if access_token_str:
            self._access_tokens.pop(access_token_str, None)
        if refresh_token_str:
            self._refresh_tokens.pop(refresh_token_str, None)


# ---------------------------------------------------------------------------
# Module-level singleton store
# ---------------------------------------------------------------------------

token_store: InMemoryTokenStore = InMemoryTokenStore()
"""Process-lifetime in-memory token store singleton.

All AS provider methods MUST use this singleton — creating a separate
InMemoryTokenStore would make tokens issued by one call invisible to
another. The provider (provider.py) imports and uses this directly.

This store is intentionally ephemeral: restart the MCP server and all
active sessions are invalidated. Clients must re-authorize.
"""
