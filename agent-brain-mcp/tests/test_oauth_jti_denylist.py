"""Tests for jti denylist on InMemoryTokenStore + LocalRs256Verifier (Phase 70).

TDD RED → GREEN: tests written BEFORE implementation.

Validates:
  - InMemoryTokenStore.is_jti_revoked("never-added") → False
  - After revoke_by_jti("abc"), is_jti_revoked("abc") → True
  - revoke_by_jti is idempotent (calling twice does not error)
  - LocalRs256Verifier: freshly minted valid token → AccessToken
  - LocalRs256Verifier: after token_store.revoke_by_jti(<jti>),
    verify_token(<same token>) → None (SC#3 co-located revocation)

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"Deployment Shape A: Co-Located AS + RS"
Research: 70-RESEARCH.md §"jti Denylist for Co-Located Revocation"
"""

from __future__ import annotations

import jwt
import pytest

from agent_brain_mcp.oauth.keys import get_or_create_signing_key
from agent_brain_mcp.oauth.tokens import InMemoryTokenStore, mint_access_token

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ISSUER = "https://mcp.example.com"
_RESOURCE = "https://mcp.example.com/mcp"
_CLIENT_ID = "test-client"
_SCOPES = ["agent-brain:read"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store() -> InMemoryTokenStore:
    """Return a fresh InMemoryTokenStore for isolation."""
    return InMemoryTokenStore()


@pytest.fixture()
def signing_key():  # type: ignore[no-untyped-def]
    """Return a fresh process-lifetime SigningKey (reset singleton for isolation)."""
    import agent_brain_mcp.oauth.keys as _keys_mod

    _keys_mod._signing_key_singleton = None  # noqa: SLF001
    return get_or_create_signing_key()


@pytest.fixture()
def valid_token(signing_key):  # type: ignore[no-untyped-def]
    """Mint a valid RS256 JWT access token."""
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
# InMemoryTokenStore jti denylist tests
# ---------------------------------------------------------------------------


class TestInMemoryTokenStoreJtiDenylist:
    """jti denylist methods on InMemoryTokenStore."""

    def test_not_revoked_initially(self, store: InMemoryTokenStore) -> None:
        """is_jti_revoked returns False for a jti that was never added."""
        assert store.is_jti_revoked("never-added-jti") is False

    def test_revoke_by_jti_marks_revoked(self, store: InMemoryTokenStore) -> None:
        """After revoke_by_jti, is_jti_revoked returns True for that jti."""
        store.revoke_by_jti("abc-123")
        assert store.is_jti_revoked("abc-123") is True

    def test_revoke_by_jti_idempotent(self, store: InMemoryTokenStore) -> None:
        """Calling revoke_by_jti twice with the same jti does not error."""
        store.revoke_by_jti("abc-123")
        store.revoke_by_jti("abc-123")  # second call — must not raise
        assert store.is_jti_revoked("abc-123") is True

    def test_revoke_one_does_not_affect_others(self, store: InMemoryTokenStore) -> None:
        """Revoking jti A does not affect jti B."""
        store.revoke_by_jti("jti-a")
        assert store.is_jti_revoked("jti-a") is True
        assert store.is_jti_revoked("jti-b") is False

    def test_multiple_revocations(self, store: InMemoryTokenStore) -> None:
        """Multiple distinct jtis can be revoked independently."""
        store.revoke_by_jti("jti-1")
        store.revoke_by_jti("jti-2")
        store.revoke_by_jti("jti-3")
        assert store.is_jti_revoked("jti-1") is True
        assert store.is_jti_revoked("jti-2") is True
        assert store.is_jti_revoked("jti-3") is True
        assert store.is_jti_revoked("jti-4") is False

    def test_store_has_revoked_jtis_attribute(self, store: InMemoryTokenStore) -> None:
        """InMemoryTokenStore has a _revoked_jtis attribute (set)."""
        assert hasattr(store, "_revoked_jtis")
        assert isinstance(store._revoked_jtis, set)  # noqa: SLF001

    def test_store_has_jti_lock_attribute(self, store: InMemoryTokenStore) -> None:
        """InMemoryTokenStore has a _jti_lock attribute (threading.Lock)."""
        import threading

        assert hasattr(store, "_jti_lock")
        assert isinstance(store._jti_lock, type(threading.Lock()))  # noqa: SLF001


# ---------------------------------------------------------------------------
# LocalRs256Verifier jti denylist integration tests
# ---------------------------------------------------------------------------


class TestLocalRs256VerifierJtiRevocation:
    """LocalRs256Verifier rejects a token whose jti is on the denylist."""

    @pytest.mark.asyncio
    async def test_valid_token_accepted_before_revocation(  # type: ignore[no-untyped-def]
        self, verifier, valid_token, signing_key
    ) -> None:
        """A freshly minted valid token → verify_token returns AccessToken."""
        # Ensure the singleton token_store is fresh (no stale revocations)

        result = await verifier.verify_token(valid_token)
        assert result is not None, "Fresh valid token should return AccessToken"

    @pytest.mark.asyncio
    async def test_revoked_jti_returns_none(  # type: ignore[no-untyped-def]
        self, verifier, signing_key
    ) -> None:
        """After revoking the token's jti, verify_token returns None.

        SC#3 co-located revocation: the in-memory jti denylist prevents reuse
        of a revoked token even before its exp time.
        """
        from agent_brain_mcp.oauth.tokens import token_store

        # Mint a token and decode its jti without verifying signature
        token = mint_access_token(
            client_id=_CLIENT_ID,
            scopes=_SCOPES,
            resource=_RESOURCE,
            signing_key=signing_key,
            issuer=_ISSUER,
        )
        # Extract the jti from the token (no verification needed here — we own the key)
        claims = jwt.decode(
            token,
            signing_key.public_key,
            algorithms=["RS256"],
            audience=_RESOURCE,
            issuer=_ISSUER,
            leeway=30,
            options={"require": ["jti"]},
        )
        jti = claims["jti"]

        # Token is valid BEFORE revocation
        result_before = await verifier.verify_token(token)
        assert result_before is not None, "Token should be valid before revocation"

        # Revoke the jti on the singleton store
        token_store.revoke_by_jti(jti)

        # Token must be rejected AFTER revocation
        result_after = await verifier.verify_token(token)
        assert result_after is None, "Token with revoked jti should return None"
