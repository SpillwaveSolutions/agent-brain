"""RS256 TokenVerifier implementations for the Resource Server (Phase 67 + Phase 70).

Implements the SDK ``TokenVerifier`` protocol via three verifier classes:

``LocalRs256Verifier`` (Phase 67):
    Validates an inbound Bearer JWT against the co-located AS's in-memory
    public key (no network call — co-located Shape A deployment).

``JwksTokenVerifier`` (Phase 70 — OAUTH-11):
    Validates JWTs via a remote JWKS endpoint using ``PyJWKClient`` with
    5-min TTL caching + kid-miss on-demand refresh.  Enables split AS/RS
    topology where the Authorization Server is a separate IdP (e.g., Keycloak).

``IntrospectionTokenVerifier`` (Phase 70 — OAUTH-12):
    RFC 7662 token introspection for opaque-token / external-AS deployments.
    ``active: false`` → None (revocation rides on introspection for free).

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

Phase 70 adds ``JwksTokenVerifier`` and ``IntrospectionTokenVerifier`` behind
the same protocol, plus a ``build_verifier()`` selector that chooses the right
verifier by config (Task 3).  ``build_local_verifier()`` is kept intact and
is the fallback path that ``build_verifier()`` calls when neither JWKS URI nor
introspection URL is configured.

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"Token Validation on /mcp" (6-check order)
  §"Deployment Shape A: Co-Located AS + RS" (in-memory public key)
  §"RS verification middleware" in 67-CONTEXT.md
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import httpx
import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken

from agent_brain_mcp.config import resolve_oauth_settings, resolve_split_as_settings
from agent_brain_mcp.oauth.keys import get_or_create_signing_key
from agent_brain_mcp.oauth.tokens import token_store

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

logger = logging.getLogger(__name__)

# Clock-skew leeway in seconds (checks #3 exp/nbf).
# 30s is sufficient for loopback + LAN AS-RS paths; keep it short to
# limit the window for replay attacks.
_LEEWAY_SECONDS = 30

# JWKS TTL in seconds (5-minute cache for remote JWKS endpoint).
# PyJWKClient lifespan parameter; kid-miss triggers on-demand refresh.
_JWKS_TTL_SECONDS = 300


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

        # Phase 70 (OAUTH-12 SC#3): check the co-located jti denylist AFTER
        # successful signature/claim verification, BEFORE building AccessToken.
        # Only the co-located LocalRs256Verifier uses this denylist; split/external
        # token paths use introspection active:false for revocation instead.
        jti = claims.get("jti")
        if jti and token_store.is_jti_revoked(jti):
            logger.debug("Token rejected: jti %s is on the revocation denylist", jti)
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


class JwksTokenVerifier:
    """RS256 TokenVerifier using a remote JWKS endpoint (Phase 70 — OAUTH-11).

    Validates inbound Bearer JWTs on ``/mcp`` requests against a remote
    Authorization Server's published JWKS (split AS/RS topology, e.g. Keycloak).

    Uses ``PyJWKClient`` for two-tier caching:
      - Tier 1 (JWK Set cache): ``cache_jwk_set=True``, lifespan=300s (5 min).
      - kid-miss on-demand refresh: if the JWT's ``kid`` is not in the cached
        JWKS, ``PyJWKClient.get_signing_key_from_jwt()`` automatically re-fetches
        the JWKS before raising ``PyJWKSetDataError``.  This is built-in behaviour.

    Pitfall 1 (sync call in async context): ``get_signing_key_from_jwt()`` is
    synchronous and may block on network I/O.  It is wrapped in
    ``asyncio.to_thread()`` to avoid blocking the event loop.

    Returns ``None`` on ANY failure (bad signature, wrong aud/iss, expired,
    network error) — never raises.

    Attributes:
        issuer: The expected ``iss`` claim value (must match the IdP's issuer URI
            exactly, including realm path for Keycloak:
            ``http://localhost:8080/realms/agent-brain``).
        resource: The expected ``aud`` claim value (``AGENT_BRAIN_OAUTH_RESOURCE``).
    """

    def __init__(
        self,
        *,
        jwks_uri: str,
        issuer: str,
        resource: str,
        lifespan: float = _JWKS_TTL_SECONDS,
    ) -> None:
        """Initialize the JWKS verifier.

        Args:
            jwks_uri: The JWKS endpoint URL of the remote Authorization Server.
                For Keycloak: ``http://<host>/realms/<realm>/protocol/openid-connect/certs``
            issuer: The Authorization Server issuer URI (must match the ``iss``
                claim in all issued JWTs exactly — Keycloak includes the realm path,
                e.g. ``http://localhost:8080/realms/agent-brain``).
            resource: The canonical resource URI (``AGENT_BRAIN_OAUTH_RESOURCE``).
                Must match the ``aud`` claim in all issued JWTs.
            lifespan: JWKS cache TTL in seconds (default: 300s / 5 minutes).
        """
        self._client = PyJWKClient(jwks_uri, cache_jwk_set=True, lifespan=lifespan)
        self.issuer = issuer
        self.resource = resource

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify a Bearer JWT via the remote JWKS endpoint.

        Performs: signature (via JWKS), exp/nbf (leeway=30s), iss, aud.
        Wraps the synchronous ``get_signing_key_from_jwt()`` in a thread
        (Pitfall 1) to avoid blocking the asyncio event loop.

        Args:
            token: The raw Bearer JWT string.

        Returns:
            An ``AccessToken`` on success.
            ``None`` on any failure — never raises.
        """
        if not token:
            return None

        try:
            signing_key = await asyncio.to_thread(
                self._client.get_signing_key_from_jwt, token
            )
            claims = jwt.decode(
                token,
                signing_key.key,
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
            logger.debug("JwksTokenVerifier: JWT verification failed: %s", exc)
            return None
        except Exception as exc:  # PyJWKClientError, network errors, etc.
            logger.debug("JwksTokenVerifier: JWKS fetch/parse error: %s", exc)
            return None

        client_id: str = claims.get("client_id") or claims.get("sub") or ""
        scope_str: str = claims.get("scope") or ""
        scopes: list[str] = scope_str.split() if scope_str else []
        expires_at: int | None = claims.get("exp")

        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=scopes,
            expires_at=expires_at,
            resource=self.resource,
        )


class IntrospectionTokenVerifier:
    """RFC 7662 token introspection verifier (Phase 70 — OAUTH-12).

    Validates tokens (opaque or JWT) by calling the Authorization Server's
    introspection endpoint.  ``active: false`` → ``None`` (revocation / expiry
    honored automatically via introspection).

    Pitfall 2 (aud list normalization): RFC 7662 permits ``aud`` to be either
    a string or a JSON array. This verifier normalizes both forms before
    comparing against ``self.resource``.

    Returns ``None`` on ANY failure (active:false, aud mismatch, HTTP != 200,
    malformed response, network error) — never raises.

    Attributes:
        introspection_endpoint: The RFC 7662 introspection URL.
        client_id: The RS client ID for authenticating to the introspection endpoint.
        client_secret: The RS client secret for authenticating to the endpoint.
        resource: The expected ``aud`` value (``AGENT_BRAIN_OAUTH_RESOURCE``).
    """

    def __init__(
        self,
        *,
        introspection_endpoint: str,
        client_id: str,
        client_secret: str,
        resource: str,
    ) -> None:
        """Initialize the introspection verifier.

        Args:
            introspection_endpoint: The RFC 7662 introspection endpoint URL.
                For Keycloak: ``http://<host>/realms/<realm>/protocol/openid-connect/token/introspect``
            client_id: The OAuth client ID used to authenticate to the introspection
                endpoint (the Resource Server's own client credentials).
            client_secret: The OAuth client secret for the Resource Server.
            resource: The canonical resource URI (``AGENT_BRAIN_OAUTH_RESOURCE``).
                Validated against the ``aud`` field in the introspection response.
        """
        self.introspection_endpoint = introspection_endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self.resource = resource

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify a token via RFC 7662 introspection.

        POSTs ``token``, ``client_id``, and ``client_secret`` to the
        introspection endpoint as form-encoded data.

        Validation:
          1. HTTP status must be 200.
          2. Response ``active`` must be ``True``.
          3. ``aud`` (string or list) must contain ``self.resource``.

        Args:
            token: The raw Bearer token string (opaque or JWT).

        Returns:
            An ``AccessToken`` on success (active:true + aud matches).
            ``None`` on any failure — never raises.
        """
        if not token:
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    self.introspection_endpoint,
                    data={
                        "token": token,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except Exception as exc:
            logger.debug("IntrospectionTokenVerifier: HTTP error: %s", exc)
            return None

        if resp.status_code != 200:
            logger.debug(
                "IntrospectionTokenVerifier: HTTP %s from introspection endpoint",
                resp.status_code,
            )
            return None

        try:
            data: dict[str, object] = resp.json()
        except Exception as exc:
            logger.debug("IntrospectionTokenVerifier: failed to parse JSON response: %s", exc)
            return None

        if not data.get("active", False):
            return None

        # Pitfall 2: normalize aud (may be string or list per RFC 7662)
        aud = data.get("aud")
        audiences: list[object] = [aud] if isinstance(aud, str) else (aud or [])
        if self.resource not in audiences:
            logger.debug(
                "IntrospectionTokenVerifier: aud mismatch (expected %r, got %r)",
                self.resource,
                aud,
            )
            return None

        client_id: str = str(data.get("client_id", ""))
        scope_str: str = str(data.get("scope", "") or "")
        scopes: list[str] = scope_str.split() if scope_str else []
        expires_at: int | None = int(data["exp"]) if data.get("exp") is not None else None

        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=scopes,
            expires_at=expires_at,
            resource=self.resource,
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


def build_verifier(
    *,
    issuer_override: str | None = None,
) -> LocalRs256Verifier | JwksTokenVerifier | IntrospectionTokenVerifier:
    """Factory: build the correct TokenVerifier by config (Phase 70 — OAUTH-11/12).

    Selects the verifier based on environment variables in priority order:
      1. ``AGENT_BRAIN_OAUTH_JWKS_URI`` set → ``JwksTokenVerifier`` (split AS/RS,
         remote JWKS, e.g. Keycloak).
      2. ``AGENT_BRAIN_OAUTH_INTROSPECTION_URL`` set (and no JWKS URI) →
         ``IntrospectionTokenVerifier`` (opaque tokens, RFC 7662).
      3. Neither set → ``LocalRs256Verifier`` (co-located AS, backward-compatible
         default — behavior identical to calling ``build_local_verifier()``).

    ``AGENT_BRAIN_OAUTH_RESOURCE`` is required regardless of which verifier is
    selected (it provides the ``aud`` binding in all cases).

    Args:
        issuer_override: Optional issuer URI override.  Takes precedence over
            ``AGENT_BRAIN_OAUTH_ISSUER`` from the environment.  Useful for
            testability and for the co-located shape where the issuer defaults
            to the server's own base URL (supplied by ``http.py`` at startup).

    Returns:
        The appropriate verifier instance:
        - ``JwksTokenVerifier`` if JWKS URI is configured.
        - ``IntrospectionTokenVerifier`` if introspection URL is configured.
        - ``LocalRs256Verifier`` if neither is configured (co-located default).

    Raises:
        RuntimeError: If ``AGENT_BRAIN_OAUTH_RESOURCE`` is not set.
    """
    resource, issuer_env = resolve_oauth_settings()
    jwks_uri, introspection_url, intro_id, intro_secret, _ = resolve_split_as_settings()

    if not resource:
        raise RuntimeError(
            "AGENT_BRAIN_OAUTH_RESOURCE is required for build_verifier() "
            "(used as the expected aud claim in token validation)."
        )

    issuer: str = issuer_override or issuer_env or resource

    if jwks_uri:
        return JwksTokenVerifier(
            jwks_uri=jwks_uri,
            issuer=issuer,
            resource=resource,
        )

    if introspection_url:
        return IntrospectionTokenVerifier(
            introspection_endpoint=introspection_url,
            client_id=intro_id or "",
            client_secret=intro_secret or "",
            resource=resource,
        )

    return build_local_verifier(issuer_override=issuer_override)
