"""Tests for JWT minting (RS256) and in-memory token store (Phase 67 Plan 02 Task 2).

Tests verify:
  - mint_access_token produces a valid RS256 JWT with the required claim set
    (iss, aud, exp, nbf, iat, jti, scope, client_id)
  - Each minted token has a unique jti
  - aud == resource (exact, no trailing-slash mutation)
  - exp - iat == 900 (15 minutes)
  - InMemoryTokenStore: authorization code store/load/pop (single-use)
  - InMemoryTokenStore: refresh token rotation (old token invalidated)
  - InMemoryTokenStore: revoke removes both access and refresh entries
  - ACCESS_TOKEN_TTL_SECONDS == 900
  - REFRESH_TOKEN_TTL_SECONDS == 30 * 24 * 3600

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"Token lifecycle" (15-min access / 30-day rotating refresh)
  §"Canonical Resource URI Contract" (aud == resource)
  §"Token Validation on /mcp" (claim set)
"""

from __future__ import annotations

import time

import jwt

from agent_brain_mcp.oauth.keys import get_or_create_signing_key
from agent_brain_mcp.oauth.tokens import (
    ACCESS_TOKEN_TTL_SECONDS,
    REFRESH_TOKEN_TTL_SECONDS,
    InMemoryTokenStore,
    mint_access_token,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    """Verify module-level token lifetime constants."""

    def test_access_token_ttl_is_900(self) -> None:
        """ACCESS_TOKEN_TTL_SECONDS is 900 (15 minutes)."""
        assert ACCESS_TOKEN_TTL_SECONDS == 900

    def test_refresh_token_ttl_is_30_days(self) -> None:
        """REFRESH_TOKEN_TTL_SECONDS is 30 days in seconds."""
        assert REFRESH_TOKEN_TTL_SECONDS == 30 * 24 * 3600


# ---------------------------------------------------------------------------
# mint_access_token
# ---------------------------------------------------------------------------


class TestMintAccessToken:
    """Tests for mint_access_token()."""

    def setup_method(self) -> None:
        """Get the process signing key for tests."""
        self.sk = get_or_create_signing_key()

    def _decode(self, token: str) -> dict[str, object]:
        """Decode without signature verification for claim inspection."""
        return jwt.decode(
            token,
            self.sk.public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )

    def test_returns_string(self) -> None:
        """mint_access_token returns a string (the JWT)."""
        token = mint_access_token(
            client_id="test-client",
            scopes=["agent-brain:read"],
            resource="https://mcp.example.com/mcp",
            signing_key=self.sk,
            issuer="https://mcp.example.com",
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_algorithm_is_rs256(self) -> None:
        """The token header specifies RS256."""
        token = mint_access_token(
            client_id="test-client",
            scopes=["agent-brain:read"],
            resource="https://mcp.example.com/mcp",
            signing_key=self.sk,
            issuer="https://mcp.example.com",
        )
        header = jwt.get_unverified_header(token)
        assert header["alg"] == "RS256"

    def test_header_includes_kid(self) -> None:
        """The token header includes the kid from the signing key."""
        token = mint_access_token(
            client_id="test-client",
            scopes=["agent-brain:read"],
            resource="https://mcp.example.com/mcp",
            signing_key=self.sk,
            issuer="https://mcp.example.com",
        )
        header = jwt.get_unverified_header(token)
        assert header.get("kid") == self.sk.kid

    def test_iss_claim(self) -> None:
        """The iss claim matches the supplied issuer."""
        issuer = "https://mcp.example.com"
        token = mint_access_token(
            client_id="test-client",
            scopes=["agent-brain:read"],
            resource="https://mcp.example.com/mcp",
            signing_key=self.sk,
            issuer=issuer,
        )
        claims = self._decode(token)
        assert claims["iss"] == issuer

    def test_aud_claim_equals_resource(self) -> None:
        """The aud claim exactly matches the resource parameter (no mutation)."""
        resource = "https://mcp.example.com/mcp"
        token = mint_access_token(
            client_id="test-client",
            scopes=["agent-brain:read"],
            resource=resource,
            signing_key=self.sk,
            issuer="https://mcp.example.com",
        )
        claims = self._decode(token)
        # aud may be a string or list in PyJWT; normalize
        aud = claims["aud"]
        if isinstance(aud, list):
            assert resource in aud
        else:
            assert aud == resource

    def test_aud_no_trailing_slash_mutation(self) -> None:
        """aud is exactly the resource value — no trailing slash added/removed."""
        resource_no_slash = "https://mcp.example.com/mcp"
        resource_with_slash = "https://mcp.example.com/mcp/"

        for resource in (resource_no_slash, resource_with_slash):
            token = mint_access_token(
                client_id="test-client",
                scopes=["agent-brain:read"],
                resource=resource,
                signing_key=self.sk,
                issuer="https://mcp.example.com",
            )
            claims = jwt.decode(
                token,
                self.sk.public_key,
                algorithms=["RS256"],
                options={"verify_aud": False},
            )
            aud = claims["aud"]
            if isinstance(aud, list):
                assert resource in aud
            else:
                assert aud == resource

    def test_exp_minus_iat_is_900(self) -> None:
        """exp - iat == 900 (15-minute access token TTL)."""
        token = mint_access_token(
            client_id="test-client",
            scopes=["agent-brain:read"],
            resource="https://mcp.example.com/mcp",
            signing_key=self.sk,
            issuer="https://mcp.example.com",
        )
        claims = self._decode(token)
        assert isinstance(claims["exp"], int)
        assert isinstance(claims["iat"], int)
        assert claims["exp"] - claims["iat"] == 900  # type: ignore[operator]

    def test_nbf_lte_now(self) -> None:
        """nbf is at or before the current time."""
        before = int(time.time())
        token = mint_access_token(
            client_id="test-client",
            scopes=["agent-brain:read"],
            resource="https://mcp.example.com/mcp",
            signing_key=self.sk,
            issuer="https://mcp.example.com",
        )
        claims = self._decode(token)
        assert isinstance(claims["nbf"], int)
        assert claims["nbf"] <= before + 2  # type: ignore[operator]

    def test_scope_claim(self) -> None:
        """scope is a space-joined string of the supplied scopes."""
        token = mint_access_token(
            client_id="test-client",
            scopes=["agent-brain:read", "agent-brain:index"],
            resource="https://mcp.example.com/mcp",
            signing_key=self.sk,
            issuer="https://mcp.example.com",
        )
        claims = self._decode(token)
        assert claims["scope"] == "agent-brain:read agent-brain:index"

    def test_client_id_claim(self) -> None:
        """client_id claim equals the supplied client_id."""
        token = mint_access_token(
            client_id="my-mcp-client",
            scopes=["agent-brain:read"],
            resource="https://mcp.example.com/mcp",
            signing_key=self.sk,
            issuer="https://mcp.example.com",
        )
        claims = self._decode(token)
        assert claims["client_id"] == "my-mcp-client"

    def test_jti_present_and_string(self) -> None:
        """jti claim is present and a non-empty string."""
        token = mint_access_token(
            client_id="test-client",
            scopes=["agent-brain:read"],
            resource="https://mcp.example.com/mcp",
            signing_key=self.sk,
            issuer="https://mcp.example.com",
        )
        claims = self._decode(token)
        assert isinstance(claims["jti"], str)
        assert len(claims["jti"]) > 0  # type: ignore[arg-type]

    def test_two_tokens_have_different_jti(self) -> None:
        """Successive calls produce tokens with different jti values."""
        kwargs = {
            "client_id": "test-client",
            "scopes": ["agent-brain:read"],
            "resource": "https://mcp.example.com/mcp",
            "signing_key": self.sk,
            "issuer": "https://mcp.example.com",
        }
        t1 = mint_access_token(**kwargs)  # type: ignore[arg-type]
        t2 = mint_access_token(**kwargs)  # type: ignore[arg-type]
        c1 = self._decode(t1)
        c2 = self._decode(t2)
        assert c1["jti"] != c2["jti"]

    def test_two_tokens_are_different_strings(self) -> None:
        """Successive calls produce different JWT strings."""
        kwargs = {
            "client_id": "test-client",
            "scopes": ["agent-brain:read"],
            "resource": "https://mcp.example.com/mcp",
            "signing_key": self.sk,
            "issuer": "https://mcp.example.com",
        }
        t1 = mint_access_token(**kwargs)  # type: ignore[arg-type]
        t2 = mint_access_token(**kwargs)  # type: ignore[arg-type]
        assert t1 != t2

    def test_token_verifies_with_public_key(self) -> None:
        """Token is RS256-signed and verifiable with the public key."""
        resource = "https://mcp.example.com/mcp"
        token = mint_access_token(
            client_id="test-client",
            scopes=["agent-brain:read"],
            resource=resource,
            signing_key=self.sk,
            issuer="https://mcp.example.com",
        )
        # Decode with full verification (exp tolerance)
        claims = jwt.decode(
            token,
            self.sk.public_key,
            algorithms=["RS256"],
            audience=resource,
            options={"leeway": 30},
        )
        assert claims["iss"] == "https://mcp.example.com"


# ---------------------------------------------------------------------------
# InMemoryTokenStore — authorization codes
# ---------------------------------------------------------------------------


class TestInMemoryTokenStoreAuthCodes:
    """Tests for authorization code store / load / pop behaviour."""

    def setup_method(self) -> None:
        """Fresh store per test."""
        self.store = InMemoryTokenStore()

    def _make_auth_code(self, code: str = "code-123") -> object:
        """Create a mock AuthorizationCode-like object."""
        from mcp.server.auth.provider import AuthorizationCode
        from pydantic import AnyUrl

        return AuthorizationCode(
            code=code,
            scopes=["agent-brain:read"],
            expires_at=time.time() + 600,
            client_id="test-client",
            code_challenge="challenge-xyz",
            redirect_uri=AnyUrl("https://client.example.com/callback"),
            redirect_uri_provided_explicitly=True,
            resource="https://mcp.example.com/mcp",
        )

    def test_store_and_load_roundtrip(self) -> None:
        """store_authorization_code then load_authorization_code round-trips."""
        code_obj = self._make_auth_code("code-abc")
        self.store.store_authorization_code(code_obj)  # type: ignore[arg-type]
        loaded = self.store.load_authorization_code("code-abc")
        assert loaded is not None
        assert loaded.code == "code-abc"  # type: ignore[union-attr]

    def test_load_nonexistent_returns_none(self) -> None:
        """Loading a code that was never stored returns None."""
        result = self.store.load_authorization_code("nonexistent-code")
        assert result is None

    def test_pop_is_single_use(self) -> None:
        """pop_authorization_code consumes the code — second pop returns None."""
        code_obj = self._make_auth_code("code-once")
        self.store.store_authorization_code(code_obj)  # type: ignore[arg-type]

        first = self.store.pop_authorization_code("code-once")
        assert first is not None

        second = self.store.pop_authorization_code("code-once")
        assert second is None

    def test_pop_also_removes_from_load(self) -> None:
        """After pop, load also returns None."""
        code_obj = self._make_auth_code("code-pop")
        self.store.store_authorization_code(code_obj)  # type: ignore[arg-type]

        self.store.pop_authorization_code("code-pop")
        loaded = self.store.load_authorization_code("code-pop")
        assert loaded is None


# ---------------------------------------------------------------------------
# InMemoryTokenStore — access tokens
# ---------------------------------------------------------------------------


class TestInMemoryTokenStoreAccessTokens:
    """Tests for access token store / load / revoke behaviour."""

    def setup_method(self) -> None:
        """Fresh store per test."""
        self.store = InMemoryTokenStore()

    def _make_access_token(self, token: str = "acc-xyz") -> object:
        """Create a mock AccessToken SDK object."""
        from mcp.server.auth.provider import AccessToken

        return AccessToken(
            token=token,
            client_id="test-client",
            scopes=["agent-brain:read"],
            expires_at=int(time.time()) + 900,
            resource="https://mcp.example.com/mcp",
        )

    def test_store_and_load_access_token(self) -> None:
        """store_access_token then load_access_token returns the stored token."""
        at = self._make_access_token("acc-1")
        self.store.store_access_token(at)  # type: ignore[arg-type]
        loaded = self.store.load_access_token("acc-1")
        assert loaded is not None
        assert loaded.token == "acc-1"  # type: ignore[union-attr]

    def test_load_nonexistent_returns_none(self) -> None:
        """Loading a token not in the store returns None."""
        assert self.store.load_access_token("not-there") is None

    def test_revoke_access_token(self) -> None:
        """revoke_access_token removes the token from the store."""
        at = self._make_access_token("acc-rev")
        self.store.store_access_token(at)  # type: ignore[arg-type]
        self.store.revoke_access_token("acc-rev")
        assert self.store.load_access_token("acc-rev") is None


# ---------------------------------------------------------------------------
# InMemoryTokenStore — refresh tokens
# ---------------------------------------------------------------------------


class TestInMemoryTokenStoreRefreshTokens:
    """Tests for refresh token store / rotation / revoke."""

    def setup_method(self) -> None:
        """Fresh store per test."""
        self.store = InMemoryTokenStore()

    def _make_refresh_token(self, token: str = "rt-xyz") -> object:
        """Create a mock RefreshToken SDK object."""
        from mcp.server.auth.provider import RefreshToken

        return RefreshToken(
            token=token,
            client_id="test-client",
            scopes=["agent-brain:read"],
            expires_at=int(time.time()) + REFRESH_TOKEN_TTL_SECONDS,
        )

    def test_store_and_load_refresh_token(self) -> None:
        """store_refresh_token then load_refresh_token returns the stored token."""
        rt = self._make_refresh_token("rt-1")
        self.store.store_refresh_token(rt)  # type: ignore[arg-type]
        loaded = self.store.load_refresh_token("rt-1")
        assert loaded is not None
        assert loaded.token == "rt-1"  # type: ignore[union-attr]

    def test_load_nonexistent_refresh_token_returns_none(self) -> None:
        """Loading a refresh token not in the store returns None."""
        assert self.store.load_refresh_token("no-such-rt") is None

    def test_revoke_refresh_token(self) -> None:
        """revoke_refresh_token removes the entry."""
        rt = self._make_refresh_token("rt-rev")
        self.store.store_refresh_token(rt)  # type: ignore[arg-type]
        self.store.revoke_refresh_token("rt-rev")
        assert self.store.load_refresh_token("rt-rev") is None

    def test_rotate_refresh_token_returns_new_token(self) -> None:
        """rotate_refresh_token returns a NEW RefreshToken with a different value."""
        rt = self._make_refresh_token("rt-old")
        self.store.store_refresh_token(rt)  # type: ignore[arg-type]

        new_rt = self.store.rotate_refresh_token("rt-old")
        assert new_rt is not None
        assert new_rt.token != "rt-old"

    def test_rotate_refresh_token_invalidates_old(self) -> None:
        """After rotation, loading the OLD refresh token returns None."""
        rt = self._make_refresh_token("rt-old-inv")
        self.store.store_refresh_token(rt)  # type: ignore[arg-type]

        self.store.rotate_refresh_token("rt-old-inv")
        assert self.store.load_refresh_token("rt-old-inv") is None

    def test_rotate_refresh_token_new_token_loadable(self) -> None:
        """The new token returned by rotation is loadable from the store."""
        rt = self._make_refresh_token("rt-rotate")
        self.store.store_refresh_token(rt)  # type: ignore[arg-type]

        new_rt = self.store.rotate_refresh_token("rt-rotate")
        assert new_rt is not None

        loaded = self.store.load_refresh_token(new_rt.token)
        assert loaded is not None
        assert loaded.token == new_rt.token

    def test_rotate_preserves_client_id_and_scopes(self) -> None:
        """The new refresh token has the same client_id and scopes as the old one."""
        rt = self._make_refresh_token("rt-preserve")
        self.store.store_refresh_token(rt)  # type: ignore[arg-type]

        new_rt = self.store.rotate_refresh_token("rt-preserve")
        assert new_rt is not None
        assert new_rt.client_id == "test-client"
        assert new_rt.scopes == ["agent-brain:read"]

    def test_rotate_refresh_token_has_30_day_expiry(self) -> None:
        """The new refresh token expires approximately 30 days from now."""
        rt = self._make_refresh_token("rt-exp")
        self.store.store_refresh_token(rt)  # type: ignore[arg-type]

        before = int(time.time())
        new_rt = self.store.rotate_refresh_token("rt-exp")
        after = int(time.time())
        assert new_rt is not None
        assert new_rt.expires_at is not None
        # Allow ±5s tolerance for test timing
        expected_min = before + REFRESH_TOKEN_TTL_SECONDS - 5
        expected_max = after + REFRESH_TOKEN_TTL_SECONDS + 5
        assert expected_min <= new_rt.expires_at <= expected_max

    def test_rotate_nonexistent_returns_none(self) -> None:
        """Rotating a token that does not exist returns None."""
        result = self.store.rotate_refresh_token("nonexistent")
        assert result is None
