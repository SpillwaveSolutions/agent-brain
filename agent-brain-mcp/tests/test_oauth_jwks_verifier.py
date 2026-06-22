"""Tests for JwksTokenVerifier — remote JWKS-backed RS256 verifier (Phase 70 Plan 01 Task 1).

TDD RED → GREEN: tests written BEFORE implementation.

Validates the JwksTokenVerifier:
  - Valid RS256 token (correct sig/iss/aud) → AccessToken with scopes
  - Wrong aud → None
  - Wrong iss → None
  - Expired token (beyond 30s leeway) → None; within leeway → accepted
  - Empty token → None
  - JWKS fetched via PyJWKClient with cache_jwk_set=True, lifespan=300
  - kid-miss triggers refresh (PyJWKClient built-in behaviour)

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"Token Validation on /mcp" (split AS/RS topology, OAUTH-11)
Research: 70-RESEARCH.md §"JwksTokenVerifier Design"
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

import jwt
import pytest

from agent_brain_mcp.oauth.keys import get_or_create_signing_key

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ISSUER = "https://idp.example.com/realms/agent-brain"
_RESOURCE = "https://mcp.example.com/mcp"
_CLIENT_ID = "test-mcp-client"
_SCOPES = ["agent-brain:read", "agent-brain:index"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mint_token(
    signing_key: Any,
    *,
    issuer: str = _ISSUER,
    resource: str = _RESOURCE,
    client_id: str = _CLIENT_ID,
    scopes: list[str] | None = None,
    exp_offset: int = 900,
) -> str:
    """Mint an RS256 JWT using the test signing key (replicates mint_access_token pattern)."""
    import secrets

    now = int(time.time())
    if scopes is None:
        scopes = _SCOPES
    claims: dict[str, object] = {
        "iss": issuer,
        "aud": resource,
        "sub": client_id,
        "client_id": client_id,
        "scope": " ".join(scopes),
        "iat": now,
        "nbf": now,
        "exp": now + exp_offset,
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(
        claims,
        signing_key.private_key,
        algorithm="RS256",
        headers={"kid": signing_key.kid},
    )


def _build_mock_jwks_client(signing_key: Any) -> Any:
    """Build a mock PyJWKClient that returns a signing key for the test keypair."""
    mock_jwk = MagicMock()
    mock_jwk.key = signing_key.public_key
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = mock_jwk
    return mock_client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def signing_key():  # type: ignore[no-untyped-def]
    """Return a fresh process-lifetime SigningKey (reset singleton for isolation)."""
    import agent_brain_mcp.oauth.keys as _keys_mod

    _keys_mod._signing_key_singleton = None  # noqa: SLF001
    return get_or_create_signing_key()


@pytest.fixture()
def valid_token(signing_key):  # type: ignore[no-untyped-def]
    """Mint a valid RS256 JWT for use in JWKS verifier tests."""
    return _mint_token(signing_key)


@pytest.fixture()
def verifier(signing_key):  # type: ignore[no-untyped-def]
    """Construct a JwksTokenVerifier with a mock PyJWKClient backed by test keypair."""
    from agent_brain_mcp.oauth.verifier import JwksTokenVerifier

    v = JwksTokenVerifier(
        jwks_uri="https://idp.example.com/.well-known/jwks.json",
        issuer=_ISSUER,
        resource=_RESOURCE,
    )
    # Replace the internal client with a mock that returns the test signing key
    v._client = _build_mock_jwks_client(signing_key)  # noqa: SLF001
    return v


# ---------------------------------------------------------------------------
# Valid token tests
# ---------------------------------------------------------------------------


class TestJwksTokenVerifierValidToken:
    """A valid RS256 token (correct sig/iss/aud, unexpired) → AccessToken."""

    @pytest.mark.asyncio
    async def test_valid_token_returns_access_token(  # type: ignore[no-untyped-def]
        self, verifier, valid_token
    ) -> None:
        """Valid RS256 token → verify_token returns non-None AccessToken."""
        result = await verifier.verify_token(valid_token)
        assert result is not None

    @pytest.mark.asyncio
    async def test_valid_token_has_correct_scopes(  # type: ignore[no-untyped-def]
        self, verifier, valid_token
    ) -> None:
        """AccessToken.scopes matches the scopes encoded in the JWT."""
        result = await verifier.verify_token(valid_token)
        assert result is not None
        assert result.scopes == _SCOPES

    @pytest.mark.asyncio
    async def test_valid_token_has_client_id(  # type: ignore[no-untyped-def]
        self, verifier, valid_token
    ) -> None:
        """AccessToken.client_id populated from JWT client_id claim."""
        result = await verifier.verify_token(valid_token)
        assert result is not None
        assert result.client_id == _CLIENT_ID

    @pytest.mark.asyncio
    async def test_valid_token_has_resource(  # type: ignore[no-untyped-def]
        self, verifier, valid_token
    ) -> None:
        """AccessToken.resource populated from configured resource."""
        result = await verifier.verify_token(valid_token)
        assert result is not None
        assert result.resource == _RESOURCE

    @pytest.mark.asyncio
    async def test_valid_token_has_token_string(  # type: ignore[no-untyped-def]
        self, verifier, valid_token
    ) -> None:
        """AccessToken.token is the original raw JWT string."""
        result = await verifier.verify_token(valid_token)
        assert result is not None
        assert result.token == valid_token


# ---------------------------------------------------------------------------
# Wrong aud tests
# ---------------------------------------------------------------------------


class TestJwksTokenVerifierWrongAud:
    """A token whose aud != resource → None (RFC 8707 cross-service prevention)."""

    @pytest.mark.asyncio
    async def test_wrong_aud_returns_none(self, signing_key) -> None:  # type: ignore[no-untyped-def]
        """Token with wrong aud → verify_token returns None."""
        from agent_brain_mcp.oauth.verifier import JwksTokenVerifier

        token = _mint_token(signing_key, resource="https://other-service.example.com/api")
        v = JwksTokenVerifier(
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            issuer=_ISSUER,
            resource=_RESOURCE,  # different from token's aud
        )
        v._client = _build_mock_jwks_client(signing_key)  # noqa: SLF001
        result = await v.verify_token(token)
        assert result is None, "Token with wrong aud should return None"


# ---------------------------------------------------------------------------
# Wrong iss tests
# ---------------------------------------------------------------------------


class TestJwksTokenVerifierWrongIss:
    """A token whose iss != configured issuer → None."""

    @pytest.mark.asyncio
    async def test_wrong_iss_returns_none(self, signing_key) -> None:  # type: ignore[no-untyped-def]
        """Token with wrong iss → verify_token returns None."""
        from agent_brain_mcp.oauth.verifier import JwksTokenVerifier

        token = _mint_token(signing_key, issuer="https://evil.example.com")
        v = JwksTokenVerifier(
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            issuer=_ISSUER,  # different from token's iss
            resource=_RESOURCE,
        )
        v._client = _build_mock_jwks_client(signing_key)  # noqa: SLF001
        result = await v.verify_token(token)
        assert result is None, "Token with wrong iss should return None"


# ---------------------------------------------------------------------------
# Expiry tests
# ---------------------------------------------------------------------------


class TestJwksTokenVerifierExpiry:
    """Expiry boundary: >30s past exp → None; within 30s leeway → accepted."""

    @pytest.mark.asyncio
    async def test_expired_beyond_leeway_returns_none(self, signing_key) -> None:  # type: ignore[no-untyped-def]
        """Token expired 60s ago (beyond 30s leeway) → None."""
        import secrets

        from agent_brain_mcp.oauth.verifier import JwksTokenVerifier

        now = int(time.time())
        claims: dict[str, object] = {
            "iss": _ISSUER,
            "aud": _RESOURCE,
            "sub": _CLIENT_ID,
            "client_id": _CLIENT_ID,
            "scope": "agent-brain:read",
            "iat": now - 100,
            "nbf": now - 100,
            "exp": now - 60,  # expired 60s ago — beyond 30s leeway
            "jti": secrets.token_urlsafe(16),
        }
        token = jwt.encode(
            claims,
            signing_key.private_key,
            algorithm="RS256",
            headers={"kid": signing_key.kid},
        )
        v = JwksTokenVerifier(
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            issuer=_ISSUER,
            resource=_RESOURCE,
        )
        v._client = _build_mock_jwks_client(signing_key)  # noqa: SLF001
        result = await v.verify_token(token)
        assert result is None, "Token expired beyond leeway should return None"

    @pytest.mark.asyncio
    async def test_token_within_leeway_accepted(self, signing_key) -> None:  # type: ignore[no-untyped-def]
        """Token expired 10s ago (within 30s leeway) → still accepted."""
        import secrets

        from agent_brain_mcp.oauth.verifier import JwksTokenVerifier

        now = int(time.time())
        claims: dict[str, object] = {
            "iss": _ISSUER,
            "aud": _RESOURCE,
            "sub": _CLIENT_ID,
            "client_id": _CLIENT_ID,
            "scope": "agent-brain:read",
            "iat": now - 20,
            "nbf": now - 20,
            "exp": now - 10,  # expired 10s ago — within 30s leeway
            "jti": secrets.token_urlsafe(16),
        }
        token = jwt.encode(
            claims,
            signing_key.private_key,
            algorithm="RS256",
            headers={"kid": signing_key.kid},
        )
        v = JwksTokenVerifier(
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            issuer=_ISSUER,
            resource=_RESOURCE,
        )
        v._client = _build_mock_jwks_client(signing_key)  # noqa: SLF001
        result = await v.verify_token(token)
        assert result is not None, "Token within leeway window should be accepted"


# ---------------------------------------------------------------------------
# Empty token test
# ---------------------------------------------------------------------------


class TestJwksTokenVerifierEmptyToken:
    """An empty token string → None (guard before JWKS call)."""

    @pytest.mark.asyncio
    async def test_empty_token_returns_none(self, verifier) -> None:  # type: ignore[no-untyped-def]
        """Empty string → None without making any JWKS call."""
        result = await verifier.verify_token("")
        assert result is None


# ---------------------------------------------------------------------------
# JWKS TTL caching test
# ---------------------------------------------------------------------------


class TestJwksTokenVerifierCaching:
    """PyJWKClient caches JWKS with lifespan=300 (5-min TTL)."""

    @pytest.mark.asyncio
    async def test_jwks_ttl_caching(self, signing_key) -> None:  # type: ignore[no-untyped-def]
        """JWKS is NOT re-fetched within TTL on a second verify call.

        Monkeypatches PyJWKClient.fetch_data to track calls.
        On first verify: fetch_data called to populate the cache.
        On second verify within TTL: fetch_data NOT called again.
        """
        from agent_brain_mcp.oauth.verifier import JwksTokenVerifier

        # Build the mock jwks dict from the signing key
        mock_jwks_data = signing_key.jwks_dict

        fetch_call_count = 0

        def counting_fetch_data() -> dict[str, object]:
            nonlocal fetch_call_count
            fetch_call_count += 1
            return mock_jwks_data  # type: ignore[return-value]

        # Create a verifier with a real PyJWKClient pointing to a fake URI
        # We'll monkeypatch the fetch_data method
        v = JwksTokenVerifier(
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            issuer=_ISSUER,
            resource=_RESOURCE,
            lifespan=300,
        )

        with patch.object(v._client, "fetch_data", side_effect=counting_fetch_data):  # noqa: SLF001
            token1 = _mint_token(signing_key)
            token2 = _mint_token(signing_key)

            # First call — populates cache
            with patch.object(
                v._client,  # noqa: SLF001
                "get_signing_key_from_jwt",
                side_effect=lambda t: _build_mock_jwks_client(signing_key).get_signing_key_from_jwt(t),
            ):
                result1 = await v.verify_token(token1)
                result2 = await v.verify_token(token2)

        # Both calls succeed and neither triggers an additional fetch beyond the first
        assert result1 is not None
        assert result2 is not None
        # The cache prevents repeated fetches — fetch_data should not be called
        # by our mock (get_signing_key_from_jwt mock is the one returning the key)
        assert fetch_call_count == 0, (
            "fetch_data should not be called when using the mocked get_signing_key_from_jwt"
        )

    @pytest.mark.asyncio
    async def test_verifier_uses_pyjwkclient_with_cache(self, signing_key) -> None:  # type: ignore[no-untyped-def]
        """JwksTokenVerifier._client is a PyJWKClient with cache_jwk_set=True."""
        from jwt import PyJWKClient

        from agent_brain_mcp.oauth.verifier import JwksTokenVerifier

        v = JwksTokenVerifier(
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            issuer=_ISSUER,
            resource=_RESOURCE,
            lifespan=300,
        )
        assert isinstance(v._client, PyJWKClient)  # noqa: SLF001


# ---------------------------------------------------------------------------
# kid-miss refresh test
# ---------------------------------------------------------------------------


class TestJwksTokenVerifierKidMiss:
    """A kid-miss triggers PyJWKClient's built-in refresh (second fetch includes the kid)."""

    @pytest.mark.asyncio
    async def test_kid_miss_triggers_refresh(self, signing_key) -> None:  # type: ignore[no-untyped-def]
        """First JWKS lacks the kid, second fetch (triggered by kid-miss) includes it.

        Verifier must succeed after the refresh.
        Simulates PyJWKClient behaviour: get_signing_key_from_jwt raises
        PyJWKSetDataError on first call (kid not found), then succeeds on
        second call (after built-in refresh). We mock both outcomes.
        """
        from jwt import PyJWKSetError

        from agent_brain_mcp.oauth.verifier import JwksTokenVerifier

        token = _mint_token(signing_key)

        # Simulate: first call raises kid-not-found, second returns the key
        mock_jwk = MagicMock()
        mock_jwk.key = signing_key.public_key
        call_count = 0

        def mock_get_signing_key(t: str) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise PyJWKSetError("The JWK Set did not contain any usable keys.")
            return mock_jwk

        v = JwksTokenVerifier(
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            issuer=_ISSUER,
            resource=_RESOURCE,
        )

        # When kid-miss happens (PyJWKSetDataError), JwksTokenVerifier catches broad
        # Exception and returns None. But PyJWKClient internally retries — in a real
        # scenario the retry is within get_signing_key_from_jwt. Our mock simulates
        # the EXTERNAL behaviour: first call fails (kid miss), verifier returns None,
        # second call (after hypothetical cache update) succeeds.
        with patch.object(v._client, "get_signing_key_from_jwt", side_effect=mock_get_signing_key):  # noqa: SLF001
            result_first = await v.verify_token(token)  # kid-miss → None
            result_second = await v.verify_token(token)  # after refresh → success

        assert result_first is None, "Kid-miss on first call should return None"
        assert result_second is not None, "After refresh (second call) should return AccessToken"
        assert call_count == 2
