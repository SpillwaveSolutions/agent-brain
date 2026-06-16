"""OAuthAuthorizationServerProvider implementation + PKCE S256-only rejection gate.

Phase 67 Plan 02 Task 3.

This module provides:

1. ``reject_non_s256_pkce(query_params)`` — A thin pre-check helper that
   raises ``AuthorizeError`` (``error=invalid_request``) for any
   ``/authorize`` request that does not use S256 PKCE:
   - ``code_challenge_method=plain`` → raises with
     ``error_description="PKCE plain method not supported"``
   - ``code_challenge`` present but ``code_challenge_method`` absent → raises
   - ``code_challenge`` entirely absent → raises
   - ``code_challenge_method=S256`` with a non-empty challenge → passes

   **WIRING NOTE:** This helper operates on raw query params (a ``Mapping``).
   Plan 04 Task 2 wraps it verbatim in the live ``/authorize`` route handler
   (``http.py``) so actual HTTP requests return HTTP 400. THIS plan only
   delivers + unit-tests the helper and the provider-level rejection.
   Keep the signature ``(Mapping[str, str]) -> None`` and the exact
   ``error_description="PKCE plain method not supported"`` string stable.

2. ``AgentBrainAuthServerProvider`` — Concrete implementation of the SDK's
   ``OAuthAuthorizationServerProvider`` protocol (9 abstract methods) wired
   against the ``InMemoryTokenStore`` (Task 2) and ``SigningKey`` (Task 1).

   Implements:
   - ``get_client`` — static pre-registration lookup (OAUTH-10 base case;
     Plan 03 extends with CIMD dynamic fetch + SSRF controls).
   - ``register_client`` — persist to in-memory client dict (Plan 03 extends).
   - ``authorize`` — validate PKCE (empty challenge rejected), create + store
     a single-use ``AuthorizationCode``, return redirect URL with ?code=&state=.
   - ``load_authorization_code`` — delegate to store (non-consuming read).
   - ``exchange_authorization_code`` — pop single-use code, mint RS256 JWT
     access token (aud = code.resource — OAUTH-08 AS half), create rotating
     refresh token, return ``OAuthToken``.
   - ``load_refresh_token`` — delegate to store.
   - ``exchange_refresh_token`` — rotate refresh token, mint new access JWT.
   - ``load_access_token`` — delegate to store.
   - ``revoke_token`` — remove from store (access or refresh).

   ``aud`` is bound to ``resource`` from ``AuthorizationParams`` at the
   authorize step and carried through via ``AuthorizationCode.resource`` to
   ``exchange_authorization_code`` — satisfying OAUTH-08 (RFC 8707 AS half).

   The issuer fallback chain: ``resolve_oauth_settings()[1]`` or the AS base
   URL supplied at construction (co-located shape: same as resource base).

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"PKCE S256-Only: Advertisement Is Insufficient — Rejection Required"
  §"Canonical Resource URI Contract" (aud binding)
  §"AS / RS / Public-Route Boundary"
  §"Deployment Shape A" (in-memory tokens)
"""

from __future__ import annotations

import logging
import secrets
import time
import urllib.parse
from collections.abc import Mapping

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl

from agent_brain_mcp.config import resolve_client_id_allowlist
from agent_brain_mcp.oauth.keys import SigningKey
from agent_brain_mcp.oauth.registration import (
    fetch_client_metadata,
)
from agent_brain_mcp.oauth.tokens import (
    REFRESH_TOKEN_TTL_SECONDS,
    InMemoryTokenStore,
    mint_access_token,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PKCE S256-only enforcement helper
# ---------------------------------------------------------------------------

_PKCE_ERROR_PLAIN = "PKCE plain method not supported"


def reject_non_s256_pkce(query_params: Mapping[str, str]) -> None:
    """Enforce S256-only PKCE by raising AuthorizeError for non-compliant requests.

    This helper inspects raw ``/authorize`` query parameters and raises
    ``AuthorizeError(error='invalid_request')`` for any of the three
    non-compliant cases defined in ROADMAP SC#1 and the design doc
    §"PKCE S256-Only: Advertisement Is Insufficient — Rejection Required":

    (a) ``code_challenge_method=plain`` — explicit plain method.
    (b) ``code_challenge`` present but ``code_challenge_method`` absent.
    (c) ``code_challenge`` absent entirely (PKCE is MANDATORY for all
        public clients per OAuth 2.1 and MCP Authorization 2025-11-25).

    The ONLY accepted path is ``code_challenge_method=S256`` with a
    non-empty ``code_challenge``.

    **Signature stability (Plan 04 contract):** Plan 04 Task 2 wraps this
    helper verbatim in the live ``/authorize`` route handler. Do NOT change
    the function signature ``(Mapping[str, str]) -> None`` or the exact
    ``error_description="PKCE plain method not supported"`` string.

    Args:
        query_params: A mapping of query parameter names to values (e.g.
            ``request.query_params`` from Starlette, ``dict``, or any
            ``Mapping[str, str]``).

    Returns:
        None if the request is compliant (S256 + non-empty challenge).

    Raises:
        AuthorizeError: With ``error='invalid_request'`` for cases (a)-(c).
    """
    challenge = query_params.get("code_challenge", "")
    method = query_params.get("code_challenge_method", "")

    # Case (c): code_challenge absent or empty — PKCE is mandatory
    if not challenge:
        raise AuthorizeError(
            error="invalid_request",
            error_description="PKCE code_challenge is required",
        )

    # Case (a): explicit plain method — exact error_description required by plan
    if method == "plain":
        raise AuthorizeError(
            error="invalid_request",
            error_description=_PKCE_ERROR_PLAIN,  # "PKCE plain method not supported"
        )

    # Case (b): challenge present but method absent
    if not method:
        raise AuthorizeError(
            error="invalid_request",
            error_description="PKCE code_challenge_method is required; use S256",
        )

    # S256 + non-empty challenge → accepted
    # (Any other method value than "S256" or "plain" would also be rejected
    # by case (b) if absent; if some unknown method is explicitly supplied,
    # the SDK's own AuthorizationRequest model will reject it before we
    # reach the provider — safe to pass through here.)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_client_id(client: OAuthClientInformationFull) -> str:
    """Extract and return client_id, raising if None.

    The SDK's ``OAuthClientInformationFull.client_id`` is typed as
    ``str | None`` (the field is optional in the base metadata schema).
    For our AS code paths, a missing client_id is a protocol error — the
    SDK routes validate presence before reaching the provider.

    Args:
        client: The client information model.

    Returns:
        The non-None client_id string.

    Raises:
        AuthorizeError: With ``error='invalid_request'`` if client_id is None.
    """
    if client.client_id is None:
        raise AuthorizeError(
            error="invalid_request",
            error_description="client_id is required",
        )
    return client.client_id


# ---------------------------------------------------------------------------
# AgentBrainAuthServerProvider
# ---------------------------------------------------------------------------


class AgentBrainAuthServerProvider(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    """Concrete OAuthAuthorizationServerProvider for the co-located AS.

    Implements all 9 abstract SDK methods against the ``InMemoryTokenStore``
    and ``SigningKey`` from Phase 67 Plan 02 Tasks 1 + 2.

    Construction
    ------------
    Instantiate once at app startup (``http.py``) and pass to
    ``create_auth_routes(provider=..., issuer_url=...)``:

        from agent_brain_mcp.oauth.keys import get_or_create_signing_key
        from agent_brain_mcp.oauth.tokens import token_store
        from agent_brain_mcp.oauth.provider import AgentBrainAuthServerProvider

        sk = get_or_create_signing_key()
        provider = AgentBrainAuthServerProvider(
            signing_key=sk,
            store=token_store,
            issuer="https://mcp.example.com",
            resource="https://mcp.example.com/mcp",
            static_client_ids=["claude-desktop", "vscode-mcp"],
        )

    Client registration
    -------------------
    Two registration modes are supported:

    1. **Static pre-registration**: ``client_id`` values in
       ``static_client_ids`` are returned by ``get_client()`` with a
       minimal ``OAuthClientInformationFull`` (Phase 67 OAUTH-10 base case).
    2. **Dynamic registration (CIMD)**: ``register_client()`` stores the
       full ``OAuthClientInformationFull`` in-memory. Plan 03 extends this
       with the CIMD fetch + SSRF controls.

    PKCE enforcement
    ----------------
    ``authorize()`` rejects requests with an absent/empty
    ``code_challenge``. Enforcement of ``plain`` method and absent
    ``code_challenge_method`` is the responsibility of the
    ``reject_non_s256_pkce()`` pre-check (Plan 04 Task 2 wires it into
    the live ``/authorize`` route handler). The SDK's ``AuthorizationRequest``
    model independently enforces ``code_challenge_method=S256`` at the
    Starlette layer — this double defence-in-depth is deliberate.

    aud binding (OAUTH-08)
    ----------------------
    ``authorize()`` stores ``resource`` from ``AuthorizationParams`` into
    the ``AuthorizationCode``. ``exchange_authorization_code()`` passes
    that resource value to ``mint_access_token()`` as the ``aud`` claim.
    The Resource Server (Plan 03) validates ``aud`` on every ``/mcp`` call.

    Attributes:
        signing_key: The RS256 ``SigningKey`` for JWT minting.
        store: The ``InMemoryTokenStore`` for codes/tokens.
        issuer: The Authorization Server issuer URI (``iss`` claim).
        resource: The default RFC 8707 resource URI (fallback when the
            authorization code carries no resource).
        static_client_ids: List of pre-registered client IDs.
    """

    def __init__(
        self,
        *,
        signing_key: SigningKey,
        store: InMemoryTokenStore,
        issuer: str,
        resource: str,
        static_client_ids: list[str] | None = None,
    ) -> None:
        """Initialize the provider.

        Args:
            signing_key: The RS256 keypair + JWKS holder (from keys.py).
            store: The in-memory token/code store (from tokens.py).
            issuer: The Authorization Server issuer URI. Used as the ``iss``
                claim in every issued JWT.
            resource: The default resource URI for this MCP server. Used as
                a fallback ``aud`` when the authorization code carries no
                resource (should not happen in a compliant flow).
            static_client_ids: Optional list of pre-registered client IDs
                that will be returned by ``get_client()`` without needing
                explicit registration. Defaults to empty list.
        """
        self.signing_key = signing_key
        self.store = store
        self.issuer = issuer
        self.resource = resource
        # Static client registry (client_id → OAuthClientInformationFull)
        self._clients: dict[str, OAuthClientInformationFull] = {}
        for cid in static_client_ids or []:
            # OAuthClientInformationFull requires at least one redirect_uri;
            # for static pre-registration the actual redirect URIs are validated
            # per-request — supply a placeholder AnyUrl that won't be used unless
            # the client is also updated via register_client() later.
            self._clients[cid] = OAuthClientInformationFull(
                client_id=cid,
                redirect_uris=[AnyUrl("https://placeholder.invalid/callback")],
            )

    # ------------------------------------------------------------------
    # 1. get_client
    # ------------------------------------------------------------------

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        """Retrieve a registered client by ID.

        Returns a statically pre-registered client or one previously
        registered via ``register_client()``. Returns ``None`` for unknown
        client IDs.

        Plan 03 extends this with CIMD fetch + SSRF controls for dynamic
        registration.

        Args:
            client_id: The OAuth client identifier.

        Returns:
            The ``OAuthClientInformationFull``, or ``None`` if not found.
        """
        return self._clients.get(client_id)

    # ------------------------------------------------------------------
    # 2. register_client
    # ------------------------------------------------------------------

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        """Register a client dynamically with CIMD fetch for URL-shaped client_ids.

        Dispatches on the ``client_id`` shape:

        - **URL-shaped** (has an HTTP/HTTPS scheme + host): the ``client_id``
          is treated as a CIMD URL. ``fetch_client_metadata()`` is called with
          the full SSRF control stack (allowlist, unconditional IP block,
          DNS-rebinding post-resolution re-validation, 5s timeout). If the
          fetch is rejected by any SSRF control, ``RegistrationError400`` is
          propagated to the caller.

          After a successful fetch the provided ``client_info`` (which already
          carries the validated metadata the SDK parsed from the ``/register``
          request body) is stored directly. The CIMD fetch result is validated
          by ``fetch_client_metadata``; callers may wish to merge it into
          ``client_info`` in a future revision, but for Phase 67 we store the
          SDK-supplied object and use the fetch for SSRF validation only.

        - **Non-URL / opaque** (no scheme or no host): treated as a static
          pre-registration ID and stored directly without any network call.
          This preserves the existing static pre-registration path.

        SSRF note: DCR (RFC 7591) is omitted for the single-user shape
        (design doc §"Registration Policy: CIMD over DCR"). CIMD fetch is
        the ONLY dynamic registration path.

        Args:
            client_info: The full client metadata to register.

        Raises:
            ValueError: If ``client_info.client_id`` is None.
            RegistrationError400: If the SSRF controls reject the ``client_id``
                URL (non-allowlisted host, private IP, DNS-rebinding detected).
        """
        if client_info.client_id is None:
            raise ValueError("Cannot register a client with a null client_id")

        client_id = client_info.client_id

        # Determine if the client_id is URL-shaped (CIMD path)
        parsed = urllib.parse.urlparse(client_id)
        is_url_shaped = bool(parsed.scheme and parsed.netloc)

        if is_url_shaped:
            # CIMD path: fetch + full SSRF control stack
            allowlist = resolve_client_id_allowlist()
            logger.debug(
                "register_client: URL-shaped client_id %r — initiating CIMD fetch "
                "(allowlist has %d entries)",
                client_id,
                len(allowlist),
            )
            # fetch_client_metadata raises RegistrationError400 on any SSRF rejection
            await fetch_client_metadata(client_id, allowlist=allowlist)
            logger.info(
                "register_client: CIMD fetch succeeded for client_id %r", client_id
            )
        else:
            # Static/opaque path: no network call
            logger.debug(
                "register_client: non-URL client_id %r — static registration "
                "(no CIMD fetch)",
                client_id,
            )

        self._clients[client_id] = client_info

    # ------------------------------------------------------------------
    # 3. authorize
    # ------------------------------------------------------------------

    async def authorize(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
    ) -> str:
        """Issue an authorization code and return the redirect URL.

        Validates that ``params.code_challenge`` is non-empty (PKCE mandatory
        for all public clients — OAuth 2.1, MCP Authorization 2025-11-25).
        Creates and stores a single-use ``AuthorizationCode`` binding
        ``resource`` from ``params.resource`` (OAUTH-08 AS half).

        NOTE: The ``reject_non_s256_pkce()`` enforcement of
        ``code_challenge_method=plain`` happens at the route layer (Plan 04
        Task 2). The SDK's ``AuthorizationRequest`` model enforces
        ``code_challenge_method=S256`` at the Starlette request-parse layer.
        The provider enforces that the ``code_challenge`` value is non-empty.

        Args:
            client: The client requesting authorization.
            params: The parsed authorization parameters (code_challenge,
                scopes, state, redirect_uri, resource).

        Returns:
            The redirect URL with ``?code=<auth_code>&state=<state>``
            appended.

        Raises:
            AuthorizeError: With ``error='invalid_request'`` if
                ``code_challenge`` is absent/empty (PKCE enforcement).
        """
        # Enforce non-empty code_challenge (covers case (c) at provider level)
        if not params.code_challenge:
            raise AuthorizeError(
                error="invalid_request",
                error_description="PKCE code_challenge is required",
            )

        # Generate a cryptographically random authorization code
        # (160 bits = 20 random bytes, base64url ≈ 27 chars — exceeds RFC 6749
        # §10.10 minimum of 128 bits entropy)
        code_value = secrets.token_urlsafe(20)

        resource = params.resource or self.resource
        expires_at = time.time() + 600  # 10-minute code expiry

        client_id = _require_client_id(client)

        auth_code = AuthorizationCode(
            code=code_value,
            scopes=params.scopes or [],
            expires_at=expires_at,
            client_id=client_id,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=resource,
        )
        self.store.store_authorization_code(auth_code)

        return construct_redirect_uri(
            str(params.redirect_uri),
            code=code_value,
            state=params.state,
        )

    # ------------------------------------------------------------------
    # 4. load_authorization_code
    # ------------------------------------------------------------------

    async def load_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: str,
    ) -> AuthorizationCode | None:
        """Load an authorization code without consuming it.

        The SDK calls this to validate a code before calling
        ``exchange_authorization_code``. The actual consumption (single-use
        enforcement) happens in ``exchange_authorization_code`` via
        ``store.pop_authorization_code()``.

        Args:
            client: The client presenting the code.
            authorization_code: The code string from the ``/token`` request.

        Returns:
            The ``AuthorizationCode``, or ``None`` if not found/expired.
        """
        return self.store.load_authorization_code(authorization_code)

    # ------------------------------------------------------------------
    # 5. exchange_authorization_code
    # ------------------------------------------------------------------

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: AuthorizationCode,
    ) -> OAuthToken:
        """Exchange an authorization code for an access + refresh token pair.

        Pops the single-use authorization code, mints an RS256 JWT access
        token with ``aud`` bound to the code's ``resource`` (OAUTH-08 AS
        half), and creates a rotating 30-day refresh token.

        Args:
            client: The client exchanging the code.
            authorization_code: The ``AuthorizationCode`` to exchange.

        Returns:
            An ``OAuthToken`` with:
              - ``access_token``: The RS256 JWT string
              - ``token_type``: ``"Bearer"``
              - ``expires_in``: 900 (15 minutes)
              - ``refresh_token``: A 30-day rotating refresh token string
              - ``scope``: Space-joined scope list
        """
        # Single-use enforcement: consume the code
        self.store.pop_authorization_code(authorization_code.code)

        client_id = _require_client_id(client)

        # aud binds to resource from the authorization code (OAUTH-08)
        resource = authorization_code.resource or self.resource
        scopes = list(authorization_code.scopes)

        # Mint the RS256 JWT access token
        access_jwt = mint_access_token(
            client_id=client_id,
            scopes=scopes,
            resource=resource,
            signing_key=self.signing_key,
            issuer=self.issuer,
        )

        # Store the access token in the SDK AccessToken model
        access_token_obj = AccessToken(
            token=access_jwt,
            client_id=client_id,
            scopes=scopes,
            expires_at=int(time.time()) + 900,
            resource=resource,
        )
        self.store.store_access_token(access_token_obj)

        # Create a rotating refresh token
        refresh_token_value = secrets.token_urlsafe(32)
        refresh_token_obj = RefreshToken(
            token=refresh_token_value,
            client_id=client_id,
            scopes=scopes,
            expires_at=int(time.time()) + REFRESH_TOKEN_TTL_SECONDS,
        )
        self.store.store_refresh_token(refresh_token_obj)

        return OAuthToken(
            access_token=access_jwt,
            token_type="Bearer",
            expires_in=900,
            refresh_token=refresh_token_value,
            scope=" ".join(scopes) if scopes else None,
        )

    # ------------------------------------------------------------------
    # 6. load_refresh_token
    # ------------------------------------------------------------------

    async def load_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: str,
    ) -> RefreshToken | None:
        """Load a refresh token by its string value.

        Args:
            client: The client presenting the refresh token.
            refresh_token: The refresh token string.

        Returns:
            The ``RefreshToken``, or ``None`` if not found or invalidated.
        """
        return self.store.load_refresh_token(refresh_token)

    # ------------------------------------------------------------------
    # 7. exchange_refresh_token
    # ------------------------------------------------------------------

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        """Rotate a refresh token and mint a new access token.

        Implements RFC 6749 / OAuth 2.1 §6 refresh-token rotation:
        the old refresh token is invalidated and a new 30-day refresh token
        is issued alongside a new RS256 JWT access token.

        Args:
            client: The client exchanging the refresh token.
            refresh_token: The current ``RefreshToken`` to rotate.
            scopes: The requested scopes (must be a subset of the refresh
                token's scopes; callers should validate before this method).

        Returns:
            A new ``OAuthToken`` with a fresh access token and refresh token.
        """
        # Rotate: invalidate old, get new
        new_rt = self.store.rotate_refresh_token(refresh_token.token)
        if new_rt is None:
            # Token was already invalidated — treat as invalid_grant
            # (the SDK's token handler will catch this as an invalid token error)
            raise AuthorizeError(
                error="invalid_request",
                error_description="Refresh token is no longer valid",
            )

        client_id = _require_client_id(client)
        granted_scopes = scopes if scopes else list(refresh_token.scopes)

        # Mint a new access token
        # resource: carry forward from refresh token subject (best-effort:
        # not all RefreshToken models have resource; fall back to provider default)
        resource = self.resource

        access_jwt = mint_access_token(
            client_id=client_id,
            scopes=granted_scopes,
            resource=resource,
            signing_key=self.signing_key,
            issuer=self.issuer,
        )

        access_token_obj = AccessToken(
            token=access_jwt,
            client_id=client_id,
            scopes=granted_scopes,
            expires_at=int(time.time()) + 900,
            resource=resource,
        )
        self.store.store_access_token(access_token_obj)

        return OAuthToken(
            access_token=access_jwt,
            token_type="Bearer",
            expires_in=900,
            refresh_token=new_rt.token,
            scope=" ".join(granted_scopes) if granted_scopes else None,
        )

    # ------------------------------------------------------------------
    # 8. load_access_token
    # ------------------------------------------------------------------

    async def load_access_token(self, token: str) -> AccessToken | None:
        """Load an access token by its JWT string value.

        Used by the Resource Server (``BearerAuthBackend``) to validate
        tokens on ``/mcp`` requests. The verifier (Plan 03) calls this
        after signature + claims checks; the SDK AccessToken shape here
        is the return value that ends up in ``request.state.auth``.

        Args:
            token: The JWT string from the ``Authorization: Bearer`` header.

        Returns:
            The ``AccessToken`` SDK model, or ``None`` if not found or revoked.
        """
        return self.store.load_access_token(token)

    # ------------------------------------------------------------------
    # 9. revoke_token
    # ------------------------------------------------------------------

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        """Revoke an access token or refresh token.

        Removes the token from the in-memory store. Subsequent
        ``load_access_token`` or ``load_refresh_token`` calls return
        ``None`` after revocation.

        Args:
            token: Either an ``AccessToken`` or ``RefreshToken`` to revoke.
        """
        if isinstance(token, AccessToken):
            self.store.revoke_access_token(token.token)
        elif isinstance(token, RefreshToken):
            self.store.revoke_refresh_token(token.token)
        # If neither (shouldn't happen with SDK types), log and ignore.
        else:
            logger.warning(
                "revoke_token called with unexpected type %s — ignoring.",
                type(token).__name__,
            )
