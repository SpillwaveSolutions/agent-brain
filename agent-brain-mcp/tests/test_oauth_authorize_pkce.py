"""Tests for AgentBrainAuthServerProvider and PKCE S256-only rejection gate.

Phase 67 Plan 02 Task 3 — helper-level contract tests.

Tests verify:
  - reject_non_s256_pkce() raises AuthorizeError for plain method
  - reject_non_s256_pkce() raises AuthorizeError for absent method
  - reject_non_s256_pkce() raises AuthorizeError for absent challenge
  - reject_non_s256_pkce() passes for S256 method (the only accepted path)
  - Exact error_description "PKCE plain method not supported" for plain case
  - provider.exchange_authorization_code mints a JWT with aud == code's resource
  - exchange_authorization_code returns OAuthToken with proper fields
  - provider.exchange_refresh_token rotates the refresh token
  - provider.load_access_token returns the stored SDK AccessToken
  - Revoked tokens load as None
  - Static pre-registration: get_client returns a configured static client

NOTE: These are HELPER-LEVEL contract tests. The live-route HTTP assertion
(that an actual /authorize request returns HTTP 400) is Plan 04 Task 2's
responsibility when create_auth_routes is mounted in http.py.

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"PKCE S256-Only: Advertisement Is Insufficient — Rejection Required"
  §"Canonical Resource URI Contract" (aud binding)
"""

from __future__ import annotations

import time

import jwt
import pytest
from mcp.server.auth.provider import AuthorizeError
from mcp.shared.auth import OAuthClientInformationFull

from agent_brain_mcp.oauth.keys import get_or_create_signing_key
from agent_brain_mcp.oauth.provider import (
    AgentBrainAuthServerProvider,
    reject_non_s256_pkce,
)
from agent_brain_mcp.oauth.tokens import InMemoryTokenStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(
    issuer: str = "https://mcp.example.com",
    resource: str = "https://mcp.example.com/mcp",
    static_client_id: str = "test-static-client",
) -> AgentBrainAuthServerProvider:
    """Create a fresh provider with an isolated InMemoryTokenStore."""
    store = InMemoryTokenStore()
    sk = get_or_create_signing_key()
    return AgentBrainAuthServerProvider(
        signing_key=sk,
        store=store,
        issuer=issuer,
        resource=resource,
        static_client_ids=[static_client_id],
    )


def _make_client(client_id: str = "test-static-client") -> OAuthClientInformationFull:
    """Create a minimal OAuthClientInformationFull for testing."""
    return OAuthClientInformationFull(
        client_id=client_id,
        redirect_uris=["https://client.example.com/callback"],
    )


# ---------------------------------------------------------------------------
# reject_non_s256_pkce — helper-level contract tests
# ---------------------------------------------------------------------------


class TestRejectNonS256Pkce:
    """Helper-level tests for reject_non_s256_pkce()."""

    def test_plain_method_raises_authorize_error(self) -> None:
        """plain code_challenge_method raises AuthorizeError."""
        with pytest.raises(AuthorizeError) as exc_info:
            reject_non_s256_pkce(
                {"code_challenge": "abc", "code_challenge_method": "plain"}
            )
        err = exc_info.value
        assert err.error == "invalid_request"

    def test_plain_method_exact_error_description(self) -> None:
        """error_description for plain method is 'PKCE plain method not supported'."""
        with pytest.raises(AuthorizeError) as exc_info:
            reject_non_s256_pkce(
                {"code_challenge": "abc", "code_challenge_method": "plain"}
            )
        err = exc_info.value
        assert err.error_description == "PKCE plain method not supported"

    def test_absent_method_raises_authorize_error(self) -> None:
        """code_challenge present but method absent raises AuthorizeError."""
        with pytest.raises(AuthorizeError) as exc_info:
            reject_non_s256_pkce({"code_challenge": "abc"})
        err = exc_info.value
        assert err.error == "invalid_request"

    def test_absent_challenge_raises_authorize_error(self) -> None:
        """code_challenge entirely absent raises AuthorizeError."""
        with pytest.raises(AuthorizeError) as exc_info:
            reject_non_s256_pkce({})
        err = exc_info.value
        assert err.error == "invalid_request"

    def test_s256_does_not_raise(self) -> None:
        """S256 code_challenge_method passes without raising."""
        # Should not raise — this is the only accepted path
        reject_non_s256_pkce({"code_challenge": "abc", "code_challenge_method": "S256"})

    def test_accepts_mapping_like_object(self) -> None:
        """reject_non_s256_pkce accepts any Mapping[str, str]."""
        from collections.abc import Mapping

        class FakeParams(Mapping[str, str]):
            def __init__(self, d: dict[str, str]) -> None:
                self._d = d

            def __getitem__(self, key: str) -> str:
                return self._d[key]

            def __iter__(self) -> object:  # type: ignore[override]
                return iter(self._d)

            def __len__(self) -> int:
                return len(self._d)

        # S256 passes
        reject_non_s256_pkce(
            FakeParams({"code_challenge": "challenge", "code_challenge_method": "S256"})
        )

        # plain raises
        with pytest.raises(AuthorizeError):
            reject_non_s256_pkce(
                FakeParams(
                    {"code_challenge": "challenge", "code_challenge_method": "plain"}
                )
            )

    def test_empty_challenge_raises(self) -> None:
        """code_challenge present but empty string raises AuthorizeError."""
        with pytest.raises(AuthorizeError) as exc_info:
            reject_non_s256_pkce(
                {"code_challenge": "", "code_challenge_method": "S256"}
            )
        assert exc_info.value.error == "invalid_request"


# ---------------------------------------------------------------------------
# AgentBrainAuthServerProvider — get_client (static pre-registration)
# ---------------------------------------------------------------------------


class TestGetClient:
    """Tests for static client pre-registration (OAUTH-10)."""

    @pytest.mark.asyncio
    async def test_get_static_client_returns_client(self) -> None:
        """get_client returns a client for a statically registered client_id."""
        provider = _make_provider(static_client_id="my-static-client")
        client = await provider.get_client("my-static-client")
        assert client is not None
        assert client.client_id == "my-static-client"

    @pytest.mark.asyncio
    async def test_get_unknown_client_returns_none(self) -> None:
        """get_client returns None for an unregistered client_id."""
        provider = _make_provider(static_client_id="my-static-client")
        client = await provider.get_client("unknown-client")
        assert client is None

    @pytest.mark.asyncio
    async def test_register_client_then_get(self) -> None:
        """Dynamically registered client is retrievable via get_client."""
        provider = _make_provider()
        new_client = _make_client("dynamic-client-xyz")
        await provider.register_client(new_client)
        loaded = await provider.get_client("dynamic-client-xyz")
        assert loaded is not None
        assert loaded.client_id == "dynamic-client-xyz"


# ---------------------------------------------------------------------------
# AgentBrainAuthServerProvider — authorize
# ---------------------------------------------------------------------------


class TestAuthorize:
    """Tests for provider.authorize()."""

    @pytest.mark.asyncio
    async def test_authorize_returns_redirect_url_with_code(self) -> None:
        """authorize() returns a URL containing ?code= and ?state= parameters."""
        from mcp.server.auth.provider import AuthorizationParams
        from pydantic import AnyUrl

        provider = _make_provider()
        client = _make_client()

        params = AuthorizationParams(
            state="test-state-123",
            scopes=["agent-brain:read"],
            code_challenge="challenge-value-s256",
            redirect_uri=AnyUrl("https://client.example.com/callback"),
            redirect_uri_provided_explicitly=True,
            resource="https://mcp.example.com/mcp",
        )

        redirect_url = await provider.authorize(client, params)
        assert isinstance(redirect_url, str)
        assert "code=" in redirect_url
        assert "state=test-state-123" in redirect_url

    @pytest.mark.asyncio
    async def test_authorize_rejects_missing_code_challenge(self) -> None:
        """authorize() raises AuthorizeError when code_challenge is absent/empty.

        The SDK AuthorizationParams has code_challenge as a required field;
        the provider enforces the code_challenge must be truthy (non-empty).
        """
        from mcp.server.auth.provider import AuthorizationParams
        from pydantic import AnyUrl

        provider = _make_provider()
        client = _make_client()

        # The SDK's AuthorizationParams requires code_challenge — we simulate
        # an empty challenge which the provider should reject
        params = AuthorizationParams(
            state="test-state",
            scopes=["agent-brain:read"],
            code_challenge="",  # empty challenge — provider must reject
            redirect_uri=AnyUrl("https://client.example.com/callback"),
            redirect_uri_provided_explicitly=True,
            resource="https://mcp.example.com/mcp",
        )

        with pytest.raises(AuthorizeError) as exc_info:
            await provider.authorize(client, params)
        assert exc_info.value.error == "invalid_request"


# ---------------------------------------------------------------------------
# AgentBrainAuthServerProvider — exchange_authorization_code
# ---------------------------------------------------------------------------


class TestExchangeAuthorizationCode:
    """Tests for exchange_authorization_code()."""

    def _make_auth_code(
        self,
        code: str = "test-code-123",
        resource: str = "https://mcp.example.com/mcp",
    ) -> object:
        """Create an AuthorizationCode SDK model."""
        from mcp.server.auth.provider import AuthorizationCode
        from pydantic import AnyUrl

        return AuthorizationCode(
            code=code,
            scopes=["agent-brain:read"],
            expires_at=time.time() + 600,
            client_id="test-static-client",
            code_challenge="challenge-xyz",
            redirect_uri=AnyUrl("https://client.example.com/callback"),
            redirect_uri_provided_explicitly=True,
            resource=resource,
        )

    @pytest.mark.asyncio
    async def test_exchange_returns_oauth_token(self) -> None:
        """exchange_authorization_code returns an OAuthToken."""
        from mcp.shared.auth import OAuthToken

        provider = _make_provider()
        client = _make_client()
        code_obj = self._make_auth_code()

        oauth_token = await provider.exchange_authorization_code(
            client, code_obj  # type: ignore[arg-type]
        )
        assert isinstance(oauth_token, OAuthToken)

    @pytest.mark.asyncio
    async def test_exchange_token_type_is_bearer(self) -> None:
        """The returned OAuthToken has token_type 'Bearer'."""
        provider = _make_provider()
        client = _make_client()
        code_obj = self._make_auth_code()

        oauth_token = await provider.exchange_authorization_code(
            client, code_obj  # type: ignore[arg-type]
        )
        assert oauth_token.token_type == "Bearer"

    @pytest.mark.asyncio
    async def test_exchange_expires_in_900(self) -> None:
        """The returned OAuthToken has expires_in == 900."""
        provider = _make_provider()
        client = _make_client()
        code_obj = self._make_auth_code()

        oauth_token = await provider.exchange_authorization_code(
            client, code_obj  # type: ignore[arg-type]
        )
        assert oauth_token.expires_in == 900

    @pytest.mark.asyncio
    async def test_exchange_has_refresh_token(self) -> None:
        """The returned OAuthToken includes a refresh_token."""
        provider = _make_provider()
        client = _make_client()
        code_obj = self._make_auth_code()

        oauth_token = await provider.exchange_authorization_code(
            client, code_obj  # type: ignore[arg-type]
        )
        assert oauth_token.refresh_token is not None
        assert len(oauth_token.refresh_token) > 0

    @pytest.mark.asyncio
    async def test_access_token_aud_equals_code_resource(self) -> None:
        """The JWT access_token has aud == the code's resource (OAUTH-08 AS half)."""
        resource = "https://mcp.example.com/mcp"
        sk = get_or_create_signing_key()
        provider = _make_provider(resource=resource)
        client = _make_client()
        code_obj = self._make_auth_code(resource=resource)

        oauth_token = await provider.exchange_authorization_code(
            client, code_obj  # type: ignore[arg-type]
        )
        # Decode the JWT to inspect aud
        claims = jwt.decode(
            oauth_token.access_token,
            sk.public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        aud = claims["aud"]
        if isinstance(aud, list):
            assert resource in aud
        else:
            assert aud == resource

    @pytest.mark.asyncio
    async def test_access_token_stored_in_store(self) -> None:
        """After exchange, the access token is loadable from the store."""
        store = InMemoryTokenStore()
        sk = get_or_create_signing_key()
        provider = AgentBrainAuthServerProvider(
            signing_key=sk,
            store=store,
            issuer="https://mcp.example.com",
            resource="https://mcp.example.com/mcp",
            static_client_ids=["test-static-client"],
        )
        client = _make_client()
        code_obj = self._make_auth_code()

        oauth_token = await provider.exchange_authorization_code(
            client, code_obj  # type: ignore[arg-type]
        )
        loaded = store.load_access_token(oauth_token.access_token)
        assert loaded is not None


# ---------------------------------------------------------------------------
# AgentBrainAuthServerProvider — exchange_refresh_token
# ---------------------------------------------------------------------------


class TestExchangeRefreshToken:
    """Tests for exchange_refresh_token()."""

    @pytest.mark.asyncio
    async def test_refresh_token_exchange_returns_new_access_token(self) -> None:
        """exchange_refresh_token returns an OAuthToken with a new access token."""
        from mcp.server.auth.provider import RefreshToken
        from mcp.shared.auth import OAuthToken

        store = InMemoryTokenStore()
        sk = get_or_create_signing_key()
        provider = AgentBrainAuthServerProvider(
            signing_key=sk,
            store=store,
            issuer="https://mcp.example.com",
            resource="https://mcp.example.com/mcp",
            static_client_ids=["test-static-client"],
        )
        client = _make_client()

        # Seed a refresh token
        from agent_brain_mcp.oauth.tokens import REFRESH_TOKEN_TTL_SECONDS

        rt = RefreshToken(
            token="rt-initial",
            client_id="test-static-client",
            scopes=["agent-brain:read"],
            expires_at=int(time.time()) + REFRESH_TOKEN_TTL_SECONDS,
        )
        store.store_refresh_token(rt)

        oauth_token = await provider.exchange_refresh_token(
            client, rt, ["agent-brain:read"]
        )
        assert isinstance(oauth_token, OAuthToken)
        assert oauth_token.token_type == "Bearer"
        assert oauth_token.access_token is not None

    @pytest.mark.asyncio
    async def test_refresh_rotates_old_token(self) -> None:
        """After exchange_refresh_token, the old refresh token is invalidated."""
        from mcp.server.auth.provider import RefreshToken

        store = InMemoryTokenStore()
        sk = get_or_create_signing_key()
        provider = AgentBrainAuthServerProvider(
            signing_key=sk,
            store=store,
            issuer="https://mcp.example.com",
            resource="https://mcp.example.com/mcp",
            static_client_ids=["test-static-client"],
        )
        client = _make_client()

        from agent_brain_mcp.oauth.tokens import REFRESH_TOKEN_TTL_SECONDS

        old_rt_value = "rt-to-rotate"
        rt = RefreshToken(
            token=old_rt_value,
            client_id="test-static-client",
            scopes=["agent-brain:read"],
            expires_at=int(time.time()) + REFRESH_TOKEN_TTL_SECONDS,
        )
        store.store_refresh_token(rt)

        oauth_token = await provider.exchange_refresh_token(
            client, rt, ["agent-brain:read"]
        )
        # Old token is gone
        assert store.load_refresh_token(old_rt_value) is None
        # New token is different from old
        assert oauth_token.refresh_token != old_rt_value


# ---------------------------------------------------------------------------
# AgentBrainAuthServerProvider — load_access_token + revoke_token
# ---------------------------------------------------------------------------


class TestLoadAccessTokenAndRevoke:
    """Tests for load_access_token() and revoke_token()."""

    @pytest.mark.asyncio
    async def test_load_access_token_returns_stored(self) -> None:
        """load_access_token returns the SDK AccessToken that was stored."""
        from mcp.server.auth.provider import AccessToken

        store = InMemoryTokenStore()
        sk = get_or_create_signing_key()
        provider = AgentBrainAuthServerProvider(
            signing_key=sk,
            store=store,
            issuer="https://mcp.example.com",
            resource="https://mcp.example.com/mcp",
            static_client_ids=["test-static-client"],
        )

        at = AccessToken(
            token="jwt-string-123",
            client_id="test-static-client",
            scopes=["agent-brain:read"],
            expires_at=int(time.time()) + 900,
            resource="https://mcp.example.com/mcp",
        )
        store.store_access_token(at)

        loaded = await provider.load_access_token("jwt-string-123")
        assert loaded is not None
        assert loaded.token == "jwt-string-123"

    @pytest.mark.asyncio
    async def test_load_access_token_returns_none_for_missing(self) -> None:
        """load_access_token returns None for an unknown token."""
        store = InMemoryTokenStore()
        sk = get_or_create_signing_key()
        provider = AgentBrainAuthServerProvider(
            signing_key=sk,
            store=store,
            issuer="https://mcp.example.com",
            resource="https://mcp.example.com/mcp",
            static_client_ids=["test-static-client"],
        )

        loaded = await provider.load_access_token("not-a-real-token")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_revoke_access_token_makes_it_invisible(self) -> None:
        """After revoke_token(AccessToken), load_access_token returns None."""
        from mcp.server.auth.provider import AccessToken

        store = InMemoryTokenStore()
        sk = get_or_create_signing_key()
        provider = AgentBrainAuthServerProvider(
            signing_key=sk,
            store=store,
            issuer="https://mcp.example.com",
            resource="https://mcp.example.com/mcp",
            static_client_ids=["test-static-client"],
        )

        at = AccessToken(
            token="revoke-me",
            client_id="test-static-client",
            scopes=["agent-brain:read"],
            expires_at=int(time.time()) + 900,
        )
        store.store_access_token(at)

        await provider.revoke_token(at)
        loaded = await provider.load_access_token("revoke-me")
        assert loaded is None
