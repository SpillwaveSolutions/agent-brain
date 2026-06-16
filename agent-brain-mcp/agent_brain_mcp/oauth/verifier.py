"""Local RS256 TokenVerifier for the Resource Server (Phase 67 Plan 04 Task 1).

Implements the SDK ``TokenVerifier`` protocol via ``LocalRs256Verifier``, which
validates an inbound Bearer JWT against the co-located AS's in-memory public key.

Token validation order (checks #1-5 — Phase 67; #6 scope is Phase 68):
  1. Bearer token present → else 401 (handled by BearerAuthBackend before verify_token)
  2. RS256 signature valid against the in-memory public key (local JWKS).
  3. ``exp`` not expired (clock-skew leeway = 30s); ``nbf`` honored.
  4. ``iss`` == configured issuer (``AGENT_BRAIN_OAUTH_ISSUER`` or
     co-located AS base URL).
  5. ``aud`` == ``AGENT_BRAIN_OAUTH_RESOURCE`` (RFC 8707) → mismatch rejected.

Failure at #2-5 → ``verify_token`` returns ``None``.
  ``BearerAuthBackend`` maps None → unauthenticated → ``RequireAuthMiddleware``
  issues 401 + ``WWW-Authenticate: Bearer resource_metadata="..."``.

Scope check (#6) is DEFERRED to Phase 68 (OAUTH-06).  The
``LocalRs256Verifier`` passes ``required_scopes=[]`` to ``RequireAuthMiddleware``
so token claims are reachable at ``request.state.auth`` for Phase 68's
``require_scope()`` guard without any additional changes to this module.

Phase 70 verifier seam
-----------------------
``LocalRs256Verifier`` satisfies the ``TokenVerifier`` protocol with a stable
interface::

    class LocalRs256Verifier:
        async def verify_token(self, token: str) -> AccessToken | None: ...

Phase 70 swaps this for a ``JwksTokenVerifier`` that fetches the JWKS from a
remote ``/.well-known/jwks.json`` endpoint (split AS/RS topology).  The swap
is a config change in ``http.py`` — no changes to this file or the tests.

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"Token Validation on /mcp" (6-check order)
  §"Deployment Shape A: Co-Located AS + RS" (in-memory public key)
  §"RS verification middleware" in 67-CONTEXT.md
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import jwt
from mcp.server.auth.provider import AccessToken

from agent_brain_mcp.config import resolve_oauth_settings
from agent_brain_mcp.oauth.keys import get_or_create_signing_key

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

logger = logging.getLogger(__name__)

# Clock-skew leeway in seconds (checks #3 exp/nbf).
# 30s is sufficient for loopback + LAN AS-RS paths; keep it short to
# limit the window for replay attacks.
_LEEWAY_SECONDS = 30


class LocalRs256Verifier:
    """RS256 TokenVerifier using the co-located AS's in-memory public key.

    Validates inbound Bearer JWTs on ``/mcp`` requests against the in-process
    public key (no network call — the AS and RS share the same keypair in the
    co-located Shape A deployment).

    Checks performed in order (Phase 67 covers #1-5; #6 scope is Phase 68):
      #2  Signature valid against ``public_key`` (RS256).
      #3  ``exp`` not expired (leeway=30s); ``nbf`` honored.
      #4  ``iss`` == ``issuer``.
      #5  ``aud`` == ``resource`` (RFC 8707 — cross-service reuse prevented).

    Check #1 (Bearer token present) is handled by ``BearerAuthBackend`` before
    ``verify_token`` is called.

    Returns ``None`` on ANY failure (#2-5) — never raises.  Returns an SDK
    ``AccessToken`` on success, with ``token``, ``client_id``, ``scopes``,
    ``expires_at``, and ``resource`` populated.

    Phase 70 seam: Keep this class name and ``verify_token`` signature stable.
    Phase 70 swaps this for ``JwksTokenVerifier`` by config without modifying
    tests or callers.

    Attributes:
        public_key: The RSA public key used to verify JWT signatures.
        issuer: The expected ``iss`` claim value.
        resource: The expected ``aud`` claim value (``AGENT_BRAIN_OAUTH_RESOURCE``).
    """

    def __init__(
        self,
        *,
        public_key: RSAPublicKey,
        issuer: str,
        resource: str,
    ) -> None:
        """Initialize the verifier.

        Args:
            public_key: The RSA public key from the co-located AS's
                ``SigningKey.public_key``.
            issuer: The Authorization Server issuer URI. Must match the
                ``iss`` claim in all issued JWTs.
            resource: The canonical resource URI for this MCP server (RFC 8707).
                Must match the ``aud`` claim in all issued JWTs.
        """
        self.public_key = public_key
        self.issuer = issuer
        self.resource = resource

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify a Bearer JWT and return an SDK AccessToken on success.

        Performs checks #2-5 (signature, exp/nbf, iss, aud).  Check #1
        (token present) is handled upstream by ``BearerAuthBackend``.
        Scope check (#6) is Phase 68 — ``required_scopes=[]`` is passed to
        ``RequireAuthMiddleware``; claims remain reachable at
        ``request.state.auth`` for Phase 68.

        Args:
            token: The raw Bearer JWT string from the ``Authorization`` header.

        Returns:
            An ``AccessToken`` on success (all checks #2-5 pass).
            ``None`` on any failure — never raises.
        """
        if not token:
            # Empty string guard — BearerAuthBackend normally strips the
            # "Bearer " prefix, so this catches any edge case where an empty
            # string reaches us.
            return None

        try:
            claims = jwt.decode(
                token,
                self.public_key,
                algorithms=["RS256"],
                audience=self.resource,
                issuer=self.issuer,
                leeway=_LEEWAY_SECONDS,
                options={
                    "require": ["exp", "iss", "aud", "nbf"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iss": True,
                    "verify_aud": True,
                },
            )
        except jwt.PyJWTError as exc:
            # Catch ALL PyJWT errors (#2-5): InvalidSignatureError,
            # ExpiredSignatureError, InvalidAudienceError, InvalidIssuerError,
            # DecodeError, MissingRequiredClaimError, etc.
            logger.debug("Token verification failed: %s", exc)
            return None

        # Extract claims for the AccessToken model
        client_id: str = claims.get("client_id") or claims.get("sub") or ""
        scope_str: str = claims.get("scope") or ""
        scopes: list[str] = scope_str.split() if scope_str else []
        expires_at: int | None = claims.get("exp")
        # aud may be a string or list; PyJWT normalizes it against our single
        # audience string already — just carry the configured resource value.
        resource: str = self.resource

        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=scopes,
            expires_at=expires_at,
            resource=resource,
        )


def build_local_verifier(
    *,
    issuer_override: str | None = None,
) -> LocalRs256Verifier:
    """Factory: build a LocalRs256Verifier from the current process config.

    Reads the co-located AS's signing key (``get_or_create_signing_key()``)
    and the OAuth settings (``resolve_oauth_settings()``) to construct a
    verifier instance.

    Phase 70 swaps this factory for one that returns a ``JwksTokenVerifier``
    configured against an external JWKS URL — no other changes required.

    Args:
        issuer_override: Optional issuer URI override.  When supplied, this
            takes precedence over ``AGENT_BRAIN_OAUTH_ISSUER`` from the
            environment.  Used for testability and for the co-located shape
            where the issuer defaults to the server's own base URL (supplied
            at startup via ``http.py``).

    Returns:
        A ``LocalRs256Verifier`` configured with the process-lifetime public
        key and the resolved issuer + resource URI.

    Raises:
        RuntimeError: If ``AGENT_BRAIN_OAUTH_RESOURCE`` is not set (required
            for the ``aud`` check).
    """
    sk = get_or_create_signing_key()
    resource, issuer_env = resolve_oauth_settings()

    if not resource:
        raise RuntimeError(
            "AGENT_BRAIN_OAUTH_RESOURCE is required for LocalRs256Verifier "
            "(used as the expected aud claim in token validation)."
        )

    issuer: str = issuer_override or issuer_env or resource

    return LocalRs256Verifier(
        public_key=sk.public_key,
        issuer=issuer,
        resource=resource,
    )
