"""RS middleware integration tests — RequireAuthMiddleware on /mcp (Phase 67 Plan 04).

Tests the full mount-order + auth-enforcement contract on the built ASGI app:

OAUTH-05: RequireAuthMiddleware wraps only /mcp; well-known + AS routes exempt.
OAUTH-08 RS half: aud mismatch → 401.
ROADMAP SC#1 live contract: /authorize PKCE pre-check runs for plain/method-absent/
  challenge-absent cases before the SDK authorize handler.
Phase 66 mount-order test MUST survive this file passing.

All tests use AGENT_BRAIN_AUTH=oauth and a valid AGENT_BRAIN_OAUTH_RESOURCE.
"""

from __future__ import annotations

import time
from collections.abc import Generator
from typing import Any

import httpx
import pytest
from starlette.testclient import TestClient

from agent_brain_mcp.http import (
    JWKS_PATH,
    OASM_PATH,
    PRM_PATH,
    build_asgi_app,
)
from agent_brain_mcp.server import build_server

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RESOURCE = "https://mcp.example.com/mcp"
_ISSUER = "https://mcp.example.com"
_CLIENT_ID = "test-client"
_SCOPES = ["agent-brain:read"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _oauth_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Set AGENT_BRAIN_AUTH=oauth + AGENT_BRAIN_OAUTH_RESOURCE for all tests."""
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "oauth")
    monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", _RESOURCE)
    monkeypatch.setenv("AGENT_BRAIN_OAUTH_ISSUER", _ISSUER)
    yield


@pytest.fixture()
def signing_key() -> Any:
    """Return an isolated signing key (reset singleton for test isolation)."""
    import agent_brain_mcp.oauth.keys as _keys_mod

    _keys_mod._signing_key_singleton = None  # noqa: SLF001
    from agent_brain_mcp.oauth.keys import get_or_create_signing_key

    return get_or_create_signing_key()


@pytest.fixture()
def app_client(signing_key: Any) -> TestClient:
    """Build a TestClient over the full ASGI app in oauth mode."""
    backend_client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"detail": "test-stub"})
        ),
        base_url="http://test-agent-brain",
    )
    server, _ = build_server(backend_client)
    app = build_asgi_app(server)
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def valid_token(signing_key: Any) -> str:
    """Mint a valid RS256 token for the test resource/issuer."""
    from agent_brain_mcp.oauth.tokens import mint_access_token

    return mint_access_token(
        client_id=_CLIENT_ID,
        scopes=_SCOPES,
        resource=_RESOURCE,
        signing_key=signing_key,
        issuer=_ISSUER,
    )


# ---------------------------------------------------------------------------
# /mcp auth enforcement tests
# ---------------------------------------------------------------------------


class TestMcpAuthEnforcement:
    """RequireAuthMiddleware enforces auth on /mcp only."""

    def test_mcp_no_token_returns_401(self, app_client: TestClient) -> None:
        """POST /mcp with no Authorization header → 401 in oauth mode."""
        response = app_client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
        assert response.status_code == 401

    def test_mcp_no_token_has_www_authenticate_header(
        self, app_client: TestClient
    ) -> None:
        """401 response must include WWW-Authenticate header with Bearer."""
        response = app_client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
        assert response.status_code == 401
        www_auth = response.headers.get("www-authenticate", "")
        assert "Bearer" in www_auth

    def test_mcp_no_token_www_authenticate_has_resource_metadata(
        self, app_client: TestClient
    ) -> None:
        """WWW-Authenticate header must include resource_metadata reference."""
        response = app_client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
        assert response.status_code == 401
        www_auth = response.headers.get("www-authenticate", "")
        assert "resource_metadata" in www_auth

    def test_mcp_expired_token_returns_401(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """POST /mcp with expired token → 401."""
        import jwt

        now = int(time.time())
        claims = {
            "iss": _ISSUER,
            "aud": _RESOURCE,
            "sub": _CLIENT_ID,
            "client_id": _CLIENT_ID,
            "scope": "agent-brain:read",
            "iat": now - 200,
            "nbf": now - 200,
            "exp": now - 100,  # Expired 100s ago, beyond 30s leeway
            "jti": "expired-test",
        }
        expired_token: str = jwt.encode(
            claims,
            signing_key.private_key,
            algorithm="RS256",
            headers={"kid": signing_key.kid},
        )
        response = app_client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401

    def test_mcp_wrong_aud_token_returns_401(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """POST /mcp with wrong aud token → 401 (OAUTH-08 RS half)."""
        from agent_brain_mcp.oauth.tokens import mint_access_token

        wrong_aud_token = mint_access_token(
            client_id=_CLIENT_ID,
            scopes=_SCOPES,
            resource="https://other-service.example.com/api",  # wrong aud
            signing_key=signing_key,
            issuer=_ISSUER,
        )
        response = app_client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            headers={"Authorization": f"Bearer {wrong_aud_token}"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Auth-exempt routes: well-known + JWKS + AS routes
# ---------------------------------------------------------------------------


class TestAuthExemptRoutes:
    """Well-known + JWKS + AS routes return non-401 without any token."""

    def test_prm_accessible_without_token(self, app_client: TestClient) -> None:
        # PRM returns 200 without Authorization header (mount-order preserved)
        response = app_client.get(PRM_PATH)
        assert response.status_code == 200

    def test_oasm_accessible_without_token(self, app_client: TestClient) -> None:
        """OASM route returns 200 without Authorization header."""
        response = app_client.get(OASM_PATH)
        assert response.status_code == 200

    def test_healthz_accessible_without_token(self, app_client: TestClient) -> None:
        """healthz returns 200 without Authorization header."""
        response = app_client.get("/healthz")
        assert response.status_code == 200

    def test_jwks_accessible_without_token(self, app_client: TestClient) -> None:
        """/.well-known/jwks.json returns 200 without Authorization header."""
        response = app_client.get(JWKS_PATH)
        assert response.status_code == 200

    def test_jwks_returns_valid_jwks_document(self, app_client: TestClient) -> None:
        """/.well-known/jwks.json returns a valid JWKS document with keys array."""
        response = app_client.get(JWKS_PATH)
        assert response.status_code == 200
        data = response.json()
        assert "keys" in data
        assert isinstance(data["keys"], list)
        assert len(data["keys"]) == 1
        key = data["keys"][0]
        assert key["kty"] == "RSA"
        assert key["alg"] == "RS256"
        assert key["use"] == "sig"
        assert "n" in key
        assert "e" in key

    def test_jwks_has_no_private_key_material(self, app_client: TestClient) -> None:
        """JWKS document must NOT contain private key material."""
        response = app_client.get(JWKS_PATH)
        data = response.json()
        key = data["keys"][0]
        # Private key parameters must be absent
        for private_field in ("d", "p", "q", "dp", "dq", "qi"):
            assert (
                private_field not in key
            ), f"Private key field {private_field!r} must not be in JWKS"

    def test_token_route_accessible_without_bearer_token(
        self, app_client: TestClient
    ) -> None:
        """POST /token is reachable without a Bearer token (auth-exempt mount).

        The /token endpoint is auth-exempt from RequireAuthMiddleware.
        The SDK token handler may return 401 for a missing/invalid client_id
        (application-level auth), but the WWW-Authenticate header from
        RequireAuthMiddleware includes 'resource_metadata' — the SDK's own
        401 for client auth does NOT. We distinguish by checking the
        WWW-Authenticate header is absent or does not contain 'resource_metadata'.
        """
        response = app_client.post("/token")
        # The SDK returns 401 for missing client_id, but it's an application-level
        # error, NOT a RequireAuthMiddleware 401. The distinction: RequireAuthMiddleware
        # always includes 'resource_metadata' in WWW-Authenticate; the SDK /token
        # handler does not include that header.
        www_auth = response.headers.get("www-authenticate", "")
        assert "resource_metadata" not in www_auth, (
            f"/token returned a RequireAuthMiddleware 401 "
            f"(WWW-Authenticate: {www_auth!r}) — "
            "this route must be auth-exempt (mount-order contract)"
        )

    def test_register_route_accessible_without_token(
        self, app_client: TestClient
    ) -> None:
        """POST /register is reachable without a Bearer token (auth-exempt mount)."""
        response = app_client.post("/register", json={})
        # Like /token: may return 4xx for invalid request, but NOT a
        # RequireAuthMiddleware 401 with resource_metadata header
        www_auth = response.headers.get("www-authenticate", "")
        assert "resource_metadata" not in www_auth, (
            f"/register returned a RequireAuthMiddleware 401 "
            f"(WWW-Authenticate: {www_auth!r}) — "
            "this route must be auth-exempt (mount-order contract)"
        )


# ---------------------------------------------------------------------------
# ROADMAP SC#1 live contract: PKCE rejection at /authorize (the BLOCKER fix)
# ---------------------------------------------------------------------------


class TestLivePkceRejection:
    """PKCE rejection at the MOUNTED /authorize route (live contract test).

    SC#1: GET/POST /authorize with plain/method-absent/challenge-absent
    returns 400 invalid_request from the pre-check front-handler.
    A valid S256 request is NOT rejected by the pre-check.

    These are tested against the MOUNTED ASGI app (not the helper directly) —
    this is the live contract ROADMAP SC#1 requires.
    """

    def test_authorize_plain_method_returns_400(self, app_client: TestClient) -> None:
        """GET /authorize with code_challenge_method=plain → 400 invalid_request."""
        response = app_client.get(
            "/authorize",
            params={
                "code_challenge": "abc123",
                "code_challenge_method": "plain",
                "client_id": "test-client",
                "redirect_uri": "https://client.example.com/callback",
                "response_type": "code",
                "state": "test-state",
            },
        )
        assert response.status_code == 400
        body = response.json()
        assert body.get("error") == "invalid_request"
        assert body.get("error_description") == "PKCE plain method not supported"

    def test_authorize_post_plain_method_returns_400(
        self, app_client: TestClient
    ) -> None:
        """POST /authorize with code_challenge_method=plain → 400 invalid_request."""
        response = app_client.post(
            "/authorize",
            params={
                "code_challenge": "abc123",
                "code_challenge_method": "plain",
                "client_id": "test-client",
                "redirect_uri": "https://client.example.com/callback",
                "response_type": "code",
                "state": "test-state",
            },
        )
        assert response.status_code == 400
        body = response.json()
        assert body.get("error") == "invalid_request"
        assert body.get("error_description") == "PKCE plain method not supported"

    def test_authorize_method_absent_returns_400(self, app_client: TestClient) -> None:
        """GET /authorize with challenge present but method absent → 400."""
        response = app_client.get(
            "/authorize",
            params={
                "code_challenge": "abc123",
                # code_challenge_method intentionally absent
                "client_id": "test-client",
                "redirect_uri": "https://client.example.com/callback",
                "response_type": "code",
                "state": "test-state",
            },
        )
        assert response.status_code == 400
        body = response.json()
        assert body.get("error") == "invalid_request"

    def test_authorize_challenge_absent_returns_400(
        self, app_client: TestClient
    ) -> None:
        """GET /authorize with code_challenge entirely absent → 400."""
        response = app_client.get(
            "/authorize",
            params={
                # code_challenge entirely absent
                "client_id": "test-client",
                "redirect_uri": "https://client.example.com/callback",
                "response_type": "code",
                "state": "test-state",
            },
        )
        assert response.status_code == 400
        body = response.json()
        assert body.get("error") == "invalid_request"

    def test_authorize_valid_s256_not_rejected_by_precheck(
        self, app_client: TestClient
    ) -> None:
        """GET /authorize with valid S256 challenge passes through pre-check.

        A valid S256 request is NOT rejected by the pre-check (pre-check is a
        gate, not a replacement of the grant flow). The response should not be
        the 400 pre-check rejection — it passes through to the SDK authorize
        handler (which returns 302/redirect or its own error for missing client).
        """
        response = app_client.get(
            "/authorize",
            params={
                "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
                "code_challenge_method": "S256",
                "client_id": "test-client",
                "redirect_uri": "https://client.example.com/callback",
                "response_type": "code",
                "state": "test-state",
                "resource": _RESOURCE,
            },
            follow_redirects=False,
        )
        # Must NOT be the pre-check 400 rejection
        # (It will be a redirect or SDK error for unregistered client)
        assert not (
            response.status_code == 400
            and response.json().get("error") == "invalid_request"
            and response.json().get("error_description")
            == "PKCE plain method not supported"
        ), "Valid S256 request must not be rejected by the PKCE pre-check"
