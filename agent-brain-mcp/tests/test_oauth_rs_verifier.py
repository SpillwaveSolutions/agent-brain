"""Tests for LocalRs256Verifier — local RS256 TokenVerifier (Phase 67 Plan 04 Task 1).

TDD RED → GREEN: these tests are written BEFORE the implementation.

Validates the 5 RS checks:
  #1 Bearer token present (no-token case → None)
  #2 RS256 signature valid against the in-memory public key
  #3 exp not expired + nbf honored (leeway ~30s)
  #4 iss == configured issuer
  #5 aud == AGENT_BRAIN_OAUTH_RESOURCE (RFC 8707)

Scope check (#6) is Phase 68 — NOT tested or implemented here.

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"Token Validation on /mcp" (6-check order, Phase 67 covers #1-5)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest

from agent_brain_mcp.oauth.keys import get_or_create_signing_key
from agent_brain_mcp.oauth.tokens import mint_access_token

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Constants used across tests
# ---------------------------------------------------------------------------

_ISSUER = "https://mcp.example.com"
_RESOURCE = "https://mcp.example.com/mcp"
_CLIENT_ID = "test-client"
_SCOPES = ["agent-brain:read"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def signing_key():  # type: ignore[no-untyped-def]
    """Return the process-lifetime SigningKey singleton."""
    # Reset the singleton so tests are isolated from PEM env vars
    import agent_brain_mcp.oauth.keys as _keys_mod

    _keys_mod._signing_key_singleton = None  # noqa: SLF001
    return get_or_create_signing_key()


@pytest.fixture()
def valid_token(signing_key):  # type: ignore[no-untyped-def]
    """Mint a valid RS256 JWT access token using the test signing key."""
    return mint_access_token(
        client_id=_CLIENT_ID,
        scopes=_SCOPES,
        resource=_RESOURCE,
        signing_key=signing_key,
        issuer=_ISSUER,
    )


@pytest.fixture()
def verifier(signing_key):  # type: ignore[no-untyped-def]
    """Construct a LocalRs256Verifier for tests."""
    from agent_brain_mcp.oauth.verifier import LocalRs256Verifier

    return LocalRs256Verifier(
        public_key=signing_key.public_key,
        issuer=_ISSUER,
        resource=_RESOURCE,
    )


# ---------------------------------------------------------------------------
# Task 1 acceptance tests — these MUST FAIL before implementation
# ---------------------------------------------------------------------------


class TestLocalRs256VerifierValidToken:
    """A valid token (correct sig, unexpired, iss/aud correct) returns AccessToken."""

    @pytest.mark.asyncio
    async def test_valid_token_returns_access_token(  # type: ignore[no-untyped-def]
        self, verifier, valid_token
    ) -> None:
        """Valid RS256 token → verify_token returns an SDK AccessToken (not None)."""
        result = await verifier.verify_token(valid_token)
        assert result is not None

    @pytest.mark.asyncio
    async def test_valid_token_has_correct_scopes(self, verifier, valid_token) -> None:  # type: ignore[no-untyped-def]
        """AccessToken.scopes matches the scopes in the minted token."""
        result = await verifier.verify_token(valid_token)
        assert result is not None
        assert result.scopes == _SCOPES

    @pytest.mark.asyncio
    async def test_valid_token_has_token_string(self, verifier, valid_token) -> None:  # type: ignore[no-untyped-def]
        """AccessToken.token is the original JWT string."""
        result = await verifier.verify_token(valid_token)
        assert result is not None
        assert result.token == valid_token

    @pytest.mark.asyncio
    async def test_valid_token_has_client_id(self, verifier, valid_token) -> None:  # type: ignore[no-untyped-def]
        """AccessToken.client_id is populated from the JWT client_id claim."""
        result = await verifier.verify_token(valid_token)
        assert result is not None
        assert result.client_id == _CLIENT_ID

    @pytest.mark.asyncio
    async def test_valid_token_has_resource(self, verifier, valid_token) -> None:  # type: ignore[no-untyped-def]
        """AccessToken.resource is populated from the JWT aud claim."""
        result = await verifier.verify_token(valid_token)
        assert result is not None
        assert result.resource == _RESOURCE


class TestLocalRs256VerifierExpiredToken:
    """An expired token (exp in the past beyond 30s leeway) returns None."""

    @pytest.mark.asyncio
    async def test_expired_token_returns_none(self, signing_key) -> None:  # type: ignore[no-untyped-def]
        """Token expired 60s ago → verify_token returns None (beyond 30s leeway)."""
        import jwt

        from agent_brain_mcp.oauth.verifier import LocalRs256Verifier

        now = int(time.time())
        claims = {
            "iss": _ISSUER,
            "aud": _RESOURCE,
            "sub": _CLIENT_ID,
            "client_id": _CLIENT_ID,
            "scope": "agent-brain:read",
            "iat": now - 100,
            "nbf": now - 100,
            # Expired 60 seconds ago — beyond 30s leeway
            "exp": now - 60,
            "jti": "test-jti-expired",
        }
        expired_token: str = jwt.encode(
            claims,
            signing_key.private_key,
            algorithm="RS256",
            headers={"kid": signing_key.kid},
        )
        verifier = LocalRs256Verifier(
            public_key=signing_key.public_key,
            issuer=_ISSUER,
            resource=_RESOURCE,
        )
        result = await verifier.verify_token(expired_token)
        assert result is None, "Expired token should return None"


class TestLocalRs256VerifierLeeway:
    """A token within the 30s leeway window (exp 10s ago) is still valid."""

    @pytest.mark.asyncio
    async def test_token_within_leeway_window_is_valid(self, signing_key) -> None:  # type: ignore[no-untyped-def]
        """Token expired 10s ago but within 30s leeway → still valid."""
        import jwt

        from agent_brain_mcp.oauth.verifier import LocalRs256Verifier

        now = int(time.time())
        claims = {
            "iss": _ISSUER,
            "aud": _RESOURCE,
            "sub": _CLIENT_ID,
            "client_id": _CLIENT_ID,
            "scope": "agent-brain:read",
            "iat": now - 20,
            "nbf": now - 20,
            # Expired 10 seconds ago — within 30s leeway
            "exp": now - 10,
            "jti": "test-jti-leeway",
        }
        almost_expired_token: str = jwt.encode(
            claims,
            signing_key.private_key,
            algorithm="RS256",
            headers={"kid": signing_key.kid},
        )
        verifier = LocalRs256Verifier(
            public_key=signing_key.public_key,
            issuer=_ISSUER,
            resource=_RESOURCE,
        )
        result = await verifier.verify_token(almost_expired_token)
        assert result is not None, "Token within leeway window should be valid"


class TestLocalRs256VerifierBadSignature:
    """A token signed with a DIFFERENT RSA key returns None."""

    @pytest.mark.asyncio
    async def test_different_key_signature_returns_none(self, verifier) -> None:  # type: ignore[no-untyped-def]
        """Token signed with a different RSA key → verify_token returns None."""
        # Generate a DIFFERENT keypair for signing
        import agent_brain_mcp.oauth.keys as _keys_mod

        # Temporarily reset to get a fresh key
        _keys_mod._signing_key_singleton = None  # noqa: SLF001
        other_key = get_or_create_signing_key()

        # Now reset again so the verifier uses the original key
        _keys_mod._signing_key_singleton = None  # noqa: SLF001

        # Mint a token with the "other" key
        bad_token = mint_access_token(
            client_id=_CLIENT_ID,
            scopes=_SCOPES,
            resource=_RESOURCE,
            signing_key=other_key,
            issuer=_ISSUER,
        )

        # The verifier holds the FIRST public key — signature mismatch
        result = await verifier.verify_token(bad_token)
        assert result is None, "Token with wrong signature should return None"


class TestLocalRs256VerifierWrongAud:
    """A token whose aud != AGENT_BRAIN_OAUTH_RESOURCE returns None."""

    @pytest.mark.asyncio
    async def test_wrong_aud_returns_none(self, signing_key, verifier) -> None:  # type: ignore[no-untyped-def]
        # Token with aud != resource → None (cross-service reuse prevented)
        # OAUTH-08 RS half
        wrong_aud_token = mint_access_token(
            client_id=_CLIENT_ID,
            scopes=_SCOPES,
            resource="https://other-service.example.com/api",  # wrong aud
            signing_key=signing_key,
            issuer=_ISSUER,
        )
        result = await verifier.verify_token(wrong_aud_token)
        assert result is None, "Token with wrong aud should return None (OAUTH-08)"


class TestLocalRs256VerifierWrongIss:
    """A token whose iss != configured issuer returns None."""

    @pytest.mark.asyncio
    async def test_wrong_iss_returns_none(self, signing_key, verifier) -> None:  # type: ignore[no-untyped-def]
        """Token with iss != issuer → verify_token returns None."""
        wrong_iss_token = mint_access_token(
            client_id=_CLIENT_ID,
            scopes=_SCOPES,
            resource=_RESOURCE,
            signing_key=signing_key,
            issuer="https://evil-attacker.example.com",  # wrong issuer
        )
        result = await verifier.verify_token(wrong_iss_token)
        assert result is None, "Token with wrong issuer should return None"


class TestLocalRs256VerifierMalformed:
    """A malformed / non-JWT bearer string returns None (no exception leaks)."""

    @pytest.mark.asyncio
    async def test_malformed_string_returns_none(self, verifier) -> None:  # type: ignore[no-untyped-def]
        """A garbage string → verify_token returns None, never raises."""
        result = await verifier.verify_token("not.a.jwt")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_string_returns_none(self, verifier) -> None:  # type: ignore[no-untyped-def]
        """Empty string → verify_token returns None, never raises."""
        result = await verifier.verify_token("")
        assert result is None

    @pytest.mark.asyncio
    async def test_random_base64_returns_none(self, verifier) -> None:  # type: ignore[no-untyped-def]
        """Random base64 string → verify_token returns None, never raises."""
        result = await verifier.verify_token("eyJhbGciOiJSUzI1NiJ9.garbage.signature")
        assert result is None

    @pytest.mark.asyncio
    async def test_none_like_string_returns_none(self, verifier) -> None:  # type: ignore[no-untyped-def]
        """Literal 'None' string → verify_token returns None, never raises."""
        result = await verifier.verify_token("None")
        assert result is None


class TestBuildLocalVerifier:
    """build_local_verifier() factory function reads config and constructs verifier."""

    def test_build_local_verifier_returns_verifier(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """build_local_verifier() returns a LocalRs256Verifier instance."""
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", _RESOURCE)
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_ISSUER", _ISSUER)

        import agent_brain_mcp.oauth.keys as _keys_mod

        _keys_mod._signing_key_singleton = None  # noqa: SLF001

        from agent_brain_mcp.oauth.verifier import (
            LocalRs256Verifier,
            build_local_verifier,
        )

        v = build_local_verifier()
        assert isinstance(v, LocalRs256Verifier)

    def test_build_local_verifier_issuer_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """build_local_verifier(issuer_override=...) uses the supplied issuer."""
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", _RESOURCE)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_ISSUER", raising=False)

        import agent_brain_mcp.oauth.keys as _keys_mod

        _keys_mod._signing_key_singleton = None  # noqa: SLF001

        from agent_brain_mcp.oauth.verifier import build_local_verifier

        v = build_local_verifier(issuer_override="https://override.example.com")
        assert v.issuer == "https://override.example.com"
