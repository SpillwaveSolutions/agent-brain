"""Keycloak-backed end-to-end OAuth tests for the split AS/RS path (Phase 70).

Scenario coverage (SC#1-4 from 70-CONTEXT.md / 70-RESEARCH.md):
  SC#1  Keycloak-issued JWT accepted via cached JWKS (JwksTokenVerifier).
  SC#2  Opaque-token introspection round-trip returns active:true + aud match.
  SC#3  A token revoked at Keycloak is rejected on next introspection (active:false).
  SC#4  Full Keycloak RS path: authorized tool call, token refresh, scope-boundary 403.

All tests are marked @pytest.mark.keycloak and depend on the keycloak_available
session fixture which skips cleanly when no container is present — mirrors the
@pytest.mark.postgres skip convention. When a real Keycloak container has been
bootstrapped via scripts/keycloak_bootstrap.sh, these tests run against the live
IdP and prove the split-AS code path end-to-end.

SC#4 PKCE-dance note: The full browser PKCE loopback flow (401 -> PRM -> OASM ->
PKCE loopback -> tool call) is proven against the co-located AS in Phase 69's
test_oauth_client_dance_e2e.py. The Keycloak tier here proves the live RS path
independently via direct-grant headless CI tokens (70-RESEARCH.md Open Q3). SC#4
is the Phase 69 + Phase 70 combination, not a single test.

Keycloak URL patterns (realm = agent-brain, as documented in 70-RESEARCH.md):
  JWKS:          http://localhost:8080/realms/agent-brain/protocol/openid-connect/certs
  Token:         http://localhost:8080/realms/agent-brain/protocol/openid-connect/token
  Introspection: http://localhost:8080/realms/agent-brain/protocol/openid-connect/token/introspect
  iss claim:     http://localhost:8080/realms/agent-brain  (Pitfall 7 — full realm path)
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from starlette.testclient import TestClient

from agent_brain_mcp.oauth.verifier import IntrospectionTokenVerifier, JwksTokenVerifier

# ---------------------------------------------------------------------------
# Module-level constants (mirror conftest_keycloak.py constants)
# ---------------------------------------------------------------------------

_KC_BASE = os.environ.get("KEYCLOAK_URL", "http://localhost:8080")
_REALM = "agent-brain"
_RESOURCE = os.environ.get("AGENT_BRAIN_OAUTH_RESOURCE", "http://localhost:8000")
_ISSUER = f"{_KC_BASE}/realms/{_REALM}"

_JWKS_URI = f"{_ISSUER}/protocol/openid-connect/certs"
_TOKEN_URL = f"{_ISSUER}/protocol/openid-connect/token"
_INTROSPECT_URL = f"{_ISSUER}/protocol/openid-connect/token/introspect"

# Confidential RS client credentials (bootstrapped by keycloak_bootstrap.sh Step 6)
_RS_CLIENT_ID = "agent-brain-rs"
_RS_CLIENT_SECRET = "rs-secret"


# ---------------------------------------------------------------------------
# SC#1 — JWT accepted via JWKS (JwksTokenVerifier)
# ---------------------------------------------------------------------------


@pytest.mark.keycloak
async def test_keycloak_jwt_accepted(
    keycloak_available: None,
    keycloak_access_token: str,
) -> None:
    """SC#1: A Keycloak-issued JWT is accepted by JwksTokenVerifier via cached JWKS.

    JwksTokenVerifier is pointed at the Keycloak realm certs endpoint. It
    fetches the JWKS, verifies the JWT signature via kid lookup, and checks
    exp/nbf/iss/aud. The audience scope mapper in the bootstrapped realm ensures
    aud == AGENT_BRAIN_OAUTH_RESOURCE (RFC 8707 workaround — see 70-RESEARCH.md).

    Args:
        keycloak_available: Session fixture — skips if no container.
        keycloak_access_token: Real Keycloak JWT from the direct-grant flow.
    """
    verifier = JwksTokenVerifier(
        jwks_uri=_JWKS_URI,
        issuer=_ISSUER,
        resource=_RESOURCE,
    )
    result = await verifier.verify_token(keycloak_access_token)
    assert result is not None, (
        f"JwksTokenVerifier rejected a valid Keycloak JWT. "
        f"Check that the audience mapper binds aud={_RESOURCE!r}. "
        f"ISSUER={_ISSUER!r}, JWKS_URI={_JWKS_URI!r}"
    )
    assert result.resource == _RESOURCE


@pytest.mark.keycloak
async def test_kid_present_in_keycloak_jwks(
    keycloak_available: None,
    keycloak_access_token: str,
) -> None:
    """SC#1 supporting: the JWT's kid header is present in the Keycloak JWKS.

    Proves that the real JWKS fetch succeeds and that the JWT was signed with
    a key that Keycloak advertises in its public JWKS document.

    Args:
        keycloak_available: Session fixture — skips if no container.
        keycloak_access_token: Real Keycloak JWT from the direct-grant flow.
    """
    import jwt as pyjwt

    # Decode header WITHOUT verifying the signature — only need kid
    header = pyjwt.get_unverified_header(keycloak_access_token)
    token_kid = header.get("kid")
    assert token_kid is not None, "JWT header must contain a kid claim"

    # Fetch the JWKS directly and check for the kid
    resp = httpx.get(_JWKS_URI, timeout=10.0)
    resp.raise_for_status()
    jwks = resp.json()
    jwks_kids = {key["kid"] for key in jwks.get("keys", []) if "kid" in key}
    assert (
        token_kid in jwks_kids
    ), f"JWT kid {token_kid!r} not found in Keycloak JWKS keys: {jwks_kids}"


# ---------------------------------------------------------------------------
# SC#2 — Introspection round-trip (IntrospectionTokenVerifier)
# ---------------------------------------------------------------------------


@pytest.mark.keycloak
async def test_introspection_roundtrip(
    keycloak_available: None,
    keycloak_access_token: str,
) -> None:
    """SC#2: Opaque-token introspection round-trip returns active:true + aud match.

    IntrospectionTokenVerifier calls the Keycloak introspection endpoint with the
    RS client credentials (agent-brain-rs / rs-secret, bootstrapped by Step 6 of
    keycloak_bootstrap.sh). The response must include active:true and an aud field
    that matches AGENT_BRAIN_OAUTH_RESOURCE (bound via the audience scope mapper).

    Args:
        keycloak_available: Session fixture — skips if no container.
        keycloak_access_token: Real Keycloak JWT from the direct-grant flow.
    """
    verifier = IntrospectionTokenVerifier(
        introspection_endpoint=_INTROSPECT_URL,
        client_id=_RS_CLIENT_ID,
        client_secret=_RS_CLIENT_SECRET,
        resource=_RESOURCE,
    )
    result = await verifier.verify_token(keycloak_access_token)
    assert result is not None, (
        f"IntrospectionTokenVerifier rejected a valid active token. "
        f"Check that the audience mapper binds aud={_RESOURCE!r}. "
        f"INTROSPECT_URL={_INTROSPECT_URL!r}, RS_CLIENT={_RS_CLIENT_ID!r}"
    )
    assert result.resource == _RESOURCE


# ---------------------------------------------------------------------------
# SC#3 — Revoked token rejected via introspection (active:false)
# ---------------------------------------------------------------------------


@pytest.mark.keycloak
async def test_revoked_token_rejected(
    keycloak_available: None,
    keycloak_token_for_scope: Callable[[str], str],
) -> None:
    """SC#3: A token revoked at Keycloak is rejected on next introspection.

    Flow:
      1. Mint a fresh access token via direct-grant.
      2. Confirm it is accepted by IntrospectionTokenVerifier (active:true).
      3. Revoke the token via POST /protocol/openid-connect/revoke.
      4. Confirm IntrospectionTokenVerifier now returns None (active:false).

    This proves that token revocation is propagated correctly through the
    IntrospectionTokenVerifier path — the RS does not cache stale active:true
    responses and picks up the revocation on the next introspection call.

    Args:
        keycloak_available: Session fixture — skips if no container.
        keycloak_token_for_scope: Callable factory for minting scoped tokens.
    """
    fresh_token: str = keycloak_token_for_scope("openid agent-brain:read")

    verifier = IntrospectionTokenVerifier(
        introspection_endpoint=_INTROSPECT_URL,
        client_id=_RS_CLIENT_ID,
        client_secret=_RS_CLIENT_SECRET,
        resource=_RESOURCE,
    )

    # Step 2: confirm the fresh token is currently active
    result_before = await verifier.verify_token(fresh_token)
    assert result_before is not None, (
        "Fresh token should be active before revocation. "
        f"INTROSPECT_URL={_INTROSPECT_URL!r}"
    )

    # Step 3: revoke the token via Keycloak's /revoke endpoint
    # Keycloak RFC 7009 revocation endpoint is at /protocol/openid-connect/revoke.
    # The public client (agent-brain-mcp) can revoke its own tokens without a secret.
    revoke_url = f"{_ISSUER}/protocol/openid-connect/revoke"
    revoke_resp = httpx.post(
        revoke_url,
        data={
            "token": fresh_token,
            "client_id": "agent-brain-mcp",
        },
        timeout=10.0,
    )
    assert revoke_resp.status_code == 200, (
        f"Token revocation failed with HTTP {revoke_resp.status_code}: "
        f"{revoke_resp.text}"
    )

    # Step 4: introspect again — must now return None (active:false)
    result_after = await verifier.verify_token(fresh_token)
    assert result_after is None, (
        "Revoked token should be rejected (active:false) by "
        "IntrospectionTokenVerifier, but verify_token returned a non-None "
        "AccessToken. The RS is not correctly handling active:false responses."
    )


# ---------------------------------------------------------------------------
# SC#4 — Keycloak RS path: authorized tool call, token refresh, scope-boundary
# ---------------------------------------------------------------------------
# These tests prove the live RS path independently:
#   - A Keycloak-issued JWT passes RequireAuthMiddleware and ScopeEnforcementMiddleware
#   - The refresh path yields a valid new token accepted by the RS
#   - A read-only token calling an admin tool returns HTTP 403 insufficient_scope
#
# The full browser PKCE-loopback dance (401 → PRM → OASM → /authorize → /token)
# is proven against the CO-LOCATED AS in Phase 69's test_oauth_client_dance_e2e.py
# (test classes TestSC1DanceAndRetry and TestSC3SilentRefresh). The Keycloak tier
# here proves the live RS path via direct-grant headless CI tokens
# (70-RESEARCH.md Open Q3). SC#4 = Phase 69 + Phase 70 combination.
#
# Implementation note: these tests use build_asgi_app() in-process with
# AGENT_BRAIN_OAUTH_JWKS_URI set to the live Keycloak realm certs endpoint.
# JwksTokenVerifier (Phase 70 Plan 01) fetches the real JWKS from Keycloak and
# verifies the token signature — no subprocess or fake JWKS needed.


def _build_keycloak_app_client(*, token: str) -> TestClient:
    """Build a Starlette TestClient over the full ASGI app in Keycloak oauth mode.

    Sets AGENT_BRAIN_AUTH=oauth, AGENT_BRAIN_OAUTH_RESOURCE, AGENT_BRAIN_OAUTH_JWKS_URI,
    and AGENT_BRAIN_OAUTH_ISSUER in the process environment so that build_asgi_app()
    selects JwksTokenVerifier pointing at the live Keycloak JWKS endpoint.

    The backend httpx client uses a MockTransport that returns a minimal successful
    JSON response for any request — the important layer under test is the auth
    middleware, not the upstream backend.

    Args:
        token: The Keycloak Bearer token used to verify the configuration is correct.
            Unused by this function directly; callers pass it for context.

    Returns:
        A ``TestClient`` over the full ASGI app with Keycloak oauth mode active.
    """
    from agent_brain_mcp.http import build_asgi_app  # noqa: PLC0415
    from agent_brain_mcp.server import build_server  # noqa: PLC0415

    # Point the verifier at the live Keycloak JWKS endpoint.
    # build_asgi_app() reads these env vars at call time via config.py.
    os.environ["AGENT_BRAIN_AUTH"] = "oauth"
    os.environ["AGENT_BRAIN_OAUTH_RESOURCE"] = _RESOURCE
    os.environ["AGENT_BRAIN_OAUTH_ISSUER"] = _ISSUER
    os.environ["AGENT_BRAIN_OAUTH_JWKS_URI"] = _JWKS_URI

    backend_client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _req: httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"content": [{"type": "text", "text": "ok"}]},
                },
            )
        ),
        base_url="http://keycloak-test-backend",
    )
    server, _ = build_server(backend_client)
    app = build_asgi_app(server)
    return TestClient(app, raise_server_exceptions=False)


def _mcp_post(
    client: TestClient,
    bearer_token: str,
    method: str,
    params: dict[str, Any] | None = None,
) -> Any:
    """POST a JSON-RPC request to /mcp with the given Bearer token.

    Args:
        client: Starlette TestClient over the ASGI app.
        bearer_token: The raw access_token string to use as Authorization header.
        method: JSON-RPC method string (e.g. ``"tools/call"``).
        params: Optional params dict for the JSON-RPC payload.

    Returns:
        The :class:`httpx.Response` from the TestClient.
    """
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        body["params"] = params
    return client.post(
        "/mcp",
        json=body,
        headers={"Authorization": f"Bearer {bearer_token}"},
    )


@pytest.mark.keycloak
def test_full_oauth_dance_tool_call(
    keycloak_available: None,
    keycloak_access_token: str,
) -> None:
    """SC#4 core — Keycloak RS path: a Keycloak JWT is accepted for a read tool call.

    A real Keycloak-issued JWT (obtained via direct-grant with scope
    ``openid agent-brain:read``) is sent as a Bearer token to the full ASGI
    app configured with AGENT_BRAIN_OAUTH_JWKS_URI pointing at the live
    Keycloak realm certs endpoint. The app uses JwksTokenVerifier to fetch
    and cache the JWKS, verify the JWT signature, and populate scope["user"]
    with the token scopes. RequireAuthMiddleware passes (token is authenticated)
    and ScopeEnforcementMiddleware passes (read tool requires agent-brain:read).

    Environment vars:
        AGENT_BRAIN_AUTH=oauth
        AGENT_BRAIN_OAUTH_RESOURCE=http://localhost:8000   (audience claim)
        AGENT_BRAIN_OAUTH_JWKS_URI={_ISSUER}/protocol/openid-connect/certs
        AGENT_BRAIN_OAUTH_ISSUER={_ISSUER}

    SC#4 PKCE-dance leg reference: the full browser PKCE loopback flow
    (401 -> PRM -> OASM -> /authorize -> /token) is proven against the
    co-located AS in Phase 69's test_oauth_client_dance_e2e.py (class
    TestSC1DanceAndRetry). This test proves the live RS path independently
    via headless direct-grant (70-RESEARCH.md Open Q3).

    Args:
        keycloak_available: Session fixture — skips if no container.
        keycloak_access_token: Real Keycloak JWT (agent-brain:read scope).
    """
    client = _build_keycloak_app_client(token=keycloak_access_token)
    try:
        resp = _mcp_post(
            client,
            keycloak_access_token,
            "tools/call",
            params={"name": "get_corpus_status", "arguments": {}},
        )
        # The auth layers MUST pass (token is valid + has agent-brain:read scope).
        # The upstream mock backend may return 200 with a JSON-RPC result, or the
        # MCP session layer may respond differently — what matters is NOT 401/403.
        assert resp.status_code not in (401, 403), (
            f"SC#4: Keycloak JWT with agent-brain:read must NOT be rejected by "
            f"the RS auth layers. Got HTTP {resp.status_code}. "
            f"Check AGENT_BRAIN_OAUTH_JWKS_URI={_JWKS_URI!r} points to the "
            f"live Keycloak realm and the audience mapper binds aud={_RESOURCE!r}. "
            f"Body: {resp.text!r}"
        )
    finally:
        # Remove the env vars set by _build_keycloak_app_client so they do not
        # leak into subsequent tests.
        for var in (
            "AGENT_BRAIN_AUTH",
            "AGENT_BRAIN_OAUTH_RESOURCE",
            "AGENT_BRAIN_OAUTH_ISSUER",
            "AGENT_BRAIN_OAUTH_JWKS_URI",
        ):
            os.environ.pop(var, None)


@pytest.mark.keycloak
def test_token_refresh_path(
    keycloak_available: None,
    keycloak_token_for_scope: Callable[[str], str],
) -> None:
    """SC#4 refresh path — a refreshed Keycloak token is accepted by the RS.

    Flow:
      1. Obtain an access+refresh token pair from Keycloak via direct-grant.
      2. POST to the Keycloak token endpoint with grant_type=refresh_token
         to obtain a NEW access token.
      3. Send the NEW access token as a Bearer to the ASGI app configured
         with AGENT_BRAIN_OAUTH_JWKS_URI.
      4. Assert the RS auth layers pass (not 401 or 403).

    This proves the token refresh path end-to-end: a refreshed Keycloak JWT
    is a valid, freshly-signed token that the JwksTokenVerifier accepts.

    Args:
        keycloak_available: Session fixture — skips if no container.
        keycloak_token_for_scope: Factory fixture for minting scoped tokens.
    """
    # Step 1: obtain the initial token response (including refresh_token)
    resp_init = httpx.post(
        f"{_ISSUER}/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "agent-brain-mcp",
            "username": "testuser",
            "password": "testpass",
            "scope": "openid agent-brain:read",
        },
        timeout=10.0,
    )
    resp_init.raise_for_status()
    token_data = resp_init.json()

    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        pytest.skip(
            "Keycloak did not return a refresh_token for the direct-grant. "
            "Ensure the agent-brain-mcp client has directAccessGrantsEnabled "
            "and offline_access or standard refresh is configured."
        )

    # Step 2: use the refresh_token to obtain a new access token
    resp_refresh = httpx.post(
        f"{_ISSUER}/protocol/openid-connect/token",
        data={
            "grant_type": "refresh_token",
            "client_id": "agent-brain-mcp",
            "refresh_token": refresh_token,
        },
        timeout=10.0,
    )
    resp_refresh.raise_for_status()
    refreshed_token = str(resp_refresh.json()["access_token"])

    # Step 3 + 4: send refreshed token to the RS — must pass auth layers
    client = _build_keycloak_app_client(token=refreshed_token)
    try:
        resp = _mcp_post(
            client,
            refreshed_token,
            "tools/call",
            params={"name": "get_corpus_status", "arguments": {}},
        )
        assert resp.status_code not in (401, 403), (
            f"SC#4 refresh: refreshed Keycloak JWT with agent-brain:read must "
            f"NOT be rejected by the RS auth layers. Got HTTP {resp.status_code}. "
            f"Body: {resp.text!r}"
        )
    finally:
        for var in (
            "AGENT_BRAIN_AUTH",
            "AGENT_BRAIN_OAUTH_RESOURCE",
            "AGENT_BRAIN_OAUTH_ISSUER",
            "AGENT_BRAIN_OAUTH_JWKS_URI",
        ):
            os.environ.pop(var, None)


@pytest.mark.keycloak
def test_scope_boundary_403(
    keycloak_available: None,
    keycloak_token_for_scope: Callable[[str], str],
) -> None:
    """SC#4 scope boundary — read-only token calling an admin tool returns HTTP 403.

    This is the headline OAUTH-06 cross-check for the Keycloak RS path.

    A Keycloak token minted with ONLY ``agent-brain:read`` scope calls the
    ``clear_cache`` admin tool (which requires ``agent-brain:admin`` per
    TOOL_SCOPE_REQUIREMENTS). The ScopeEnforcementMiddleware MUST return:
      HTTP 403 Forbidden
      WWW-Authenticate: Bearer error="insufficient_scope", scope="agent-brain:admin"

    The response MUST be 403 (not 401) — 401 means authentication failed
    (bad/missing token); 403 means authentication passed but scope check failed.
    The distinction is required by RFC 6750 §3.1 and is the SC#4 boundary check.

    Token factory: ``keycloak_token_for_scope("openid agent-brain:read")`` — mints
    a real Keycloak JWT scoped ONLY to read. The token is valid and accepted by
    JwksTokenVerifier (sig/exp/iss/aud all pass); it is REJECTED by
    ScopeEnforcementMiddleware because ``agent-brain:admin`` is not in scope.

    Args:
        keycloak_available: Session fixture — skips if no container.
        keycloak_token_for_scope: Callable factory for minting scoped tokens.
    """
    # Mint a token scoped ONLY to agent-brain:read — NOT admin
    token = keycloak_token_for_scope("openid agent-brain:read")

    client = _build_keycloak_app_client(token=token)
    try:
        resp = _mcp_post(
            client,
            token,
            "tools/call",
            params={"name": "clear_cache", "arguments": {"confirm": True}},
        )

        # MUST be 403 (insufficient_scope) — NOT 401 (unauthenticated)
        assert resp.status_code == 403, (
            f"SC#4 scope boundary: read-only token calling clear_cache "
            f"(admin tool) must return HTTP 403, not {resp.status_code}. "
            f"A 401 would mean authentication failed (the token was rejected) "
            f"rather than authorization failed (scope insufficient). "
            f"Body: {resp.text!r}"
        )

        # WWW-Authenticate header must contain insufficient_scope
        www_auth = resp.headers.get("www-authenticate", "")
        assert "insufficient_scope" in www_auth, (
            f"SC#4 scope boundary: WWW-Authenticate header must contain "
            f"insufficient_scope for HTTP 403, got: {www_auth!r}"
        )
    finally:
        for var in (
            "AGENT_BRAIN_AUTH",
            "AGENT_BRAIN_OAUTH_RESOURCE",
            "AGENT_BRAIN_OAUTH_ISSUER",
            "AGENT_BRAIN_OAUTH_JWKS_URI",
        ):
            os.environ.pop(var, None)
