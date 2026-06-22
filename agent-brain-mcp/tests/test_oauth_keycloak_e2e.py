"""Keycloak-backed end-to-end OAuth tests for the split AS/RS path (Phase 70 Plan 02).

Scenario coverage (SC#1-3 from 70-CONTEXT.md / 70-RESEARCH.md):
  SC#1  Keycloak-issued JWT accepted via cached JWKS (JwksTokenVerifier).
  SC#2  Opaque-token introspection round-trip returns active:true + aud match.
  SC#3  A token revoked at Keycloak is rejected on next introspection (active:false).

All tests are marked @pytest.mark.keycloak and depend on the keycloak_available
session fixture which skips cleanly when no container is present — mirrors the
@pytest.mark.postgres skip convention. When a real Keycloak container has been
bootstrapped via scripts/keycloak_bootstrap.sh, these tests run against the live
IdP and prove the split-AS code path end-to-end.

Keycloak URL patterns (realm = agent-brain, as documented in 70-RESEARCH.md):
  JWKS:          http://localhost:8080/realms/agent-brain/protocol/openid-connect/certs
  Token:         http://localhost:8080/realms/agent-brain/protocol/openid-connect/token
  Introspection: http://localhost:8080/realms/agent-brain/protocol/openid-connect/token/introspect
  iss claim:     http://localhost:8080/realms/agent-brain  (Pitfall 7 — full realm path)
"""

from __future__ import annotations

import os
from collections.abc import Callable

import httpx
import pytest

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
