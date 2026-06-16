"""Mode mutual-exclusion proof — SC#5 (Phase 67 Plan 04 Task 3).

TDD RED → GREEN: proves AGENT_BRAIN_AUTH=basic and =oauth are mutually exclusive
on the request path. No request can be authenticated by both layers.

SC#5 assertions:
  1. A valid OAuth JWT FAILS the basic static-bearer check (it is not the API key).
  2. The raw AGENT_BRAIN_API_KEY PASSES the basic static-bearer check.
  3. The LocalRs256Verifier returns None for the raw API key (modes disjoint).
  4. get_auth_dependency returns exactly one selector per mode (no composition):
       none → None, basic → "basic-bearer", oauth → "oauth-require-auth"

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"AGENT_BRAIN_AUTH Toggle" (mutually exclusive, exactly one auth path)
  §"Mode mutual-exclusion proof (ROADMAP SC#5)" in 67-CONTEXT.md
"""

from __future__ import annotations

import pytest

from agent_brain_mcp.config import (
    AuthMode,
    get_auth_dependency,
    resolve_auth_mode,
    verify_basic_bearer,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RESOURCE = "https://mcp.example.com/mcp"
_ISSUER = "https://mcp.example.com"
_CLIENT_ID = "test-client"
_API_KEY = "super-secret-api-key-for-testing"


# ---------------------------------------------------------------------------
# SC#5: JWT fails basic, API key passes basic
# ---------------------------------------------------------------------------


class TestJwtFailsBasicCheck:
    """A valid OAuth JWT FAILS the basic static-bearer check."""

    def test_valid_jwt_fails_basic_bearer(  # noqa: PLR6301
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A valid OAuth JWT is NOT the shared secret → basic check fails.

        This proves that an OAuth client cannot accidentally authenticate with
        the basic mode by reusing its token.
        """
        monkeypatch.setenv("AGENT_BRAIN_API_KEY", _API_KEY)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_SIGNING_KEY", raising=False)

        import agent_brain_mcp.oauth.keys as _keys_mod

        _keys_mod._signing_key_singleton = None  # noqa: SLF001

        from agent_brain_mcp.oauth.keys import get_or_create_signing_key
        from agent_brain_mcp.oauth.tokens import mint_access_token

        sk = get_or_create_signing_key()
        jwt_token = mint_access_token(
            client_id=_CLIENT_ID,
            scopes=["agent-brain:read"],
            resource=_RESOURCE,
            signing_key=sk,
            issuer=_ISSUER,
        )

        # The JWT is NOT the shared API key → basic check must FAIL
        result = verify_basic_bearer(jwt_token)
        assert result is False, (
            "A valid OAuth JWT should FAIL the basic static-bearer check "
            "(it is not the shared secret — modes must not cross)"
        )


class TestApiKeyPassesBasicCheck:
    """The raw AGENT_BRAIN_API_KEY PASSES the basic static-bearer check."""

    def test_api_key_passes_basic_bearer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The raw API key satisfies the basic check.

        This is the baseline: basic mode still works normally.
        """
        monkeypatch.setenv("AGENT_BRAIN_API_KEY", _API_KEY)

        result = verify_basic_bearer(_API_KEY)
        assert (
            result is True
        ), "The raw AGENT_BRAIN_API_KEY should PASS the basic static-bearer check"

    def test_wrong_key_fails_basic_bearer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A wrong string does NOT satisfy the basic check."""
        monkeypatch.setenv("AGENT_BRAIN_API_KEY", _API_KEY)

        result = verify_basic_bearer("wrong-key")
        assert result is False

    def test_empty_api_key_env_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unset AGENT_BRAIN_API_KEY → basic check returns False for any token."""
        monkeypatch.delenv("AGENT_BRAIN_API_KEY", raising=False)

        result = verify_basic_bearer(_API_KEY)
        assert result is False


class TestOauthVerifierRejectsApiKey:
    """LocalRs256Verifier returns None for the raw API key (not a JWT)."""

    @pytest.mark.asyncio
    async def test_verifier_rejects_raw_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LocalRs256Verifier.verify_token(api_key) → None.

        The raw API key is not a JWT — the verifier must reject it without
        raising. This proves the RS verification and basic verification are
        disjoint in BOTH directions.
        """
        import agent_brain_mcp.oauth.keys as _keys_mod

        _keys_mod._signing_key_singleton = None  # noqa: SLF001

        from agent_brain_mcp.oauth.keys import get_or_create_signing_key
        from agent_brain_mcp.oauth.verifier import LocalRs256Verifier

        sk = get_or_create_signing_key()
        verifier = LocalRs256Verifier(
            public_key=sk.public_key,
            issuer=_ISSUER,
            resource=_RESOURCE,
        )

        # The raw API key is not a JWT → must return None
        result = await verifier.verify_token(_API_KEY)
        assert result is None, (
            "LocalRs256Verifier must return None for a raw API key "
            "(not a JWT — modes must not cross in the RS direction)"
        )


# ---------------------------------------------------------------------------
# SC#5: get_auth_dependency structural mutual-exclusion proof
# ---------------------------------------------------------------------------


class TestGetAuthDependencyMutualExclusion:
    """get_auth_dependency returns exactly ONE selector per mode (no composition)."""

    def test_none_mode_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AGENT_BRAIN_AUTH unset (none mode) → get_auth_dependency returns None."""
        monkeypatch.delenv("AGENT_BRAIN_AUTH", raising=False)

        dep = get_auth_dependency()
        assert dep is None, f"None mode must return None, got {dep!r}"

    def test_basic_mode_returns_basic_selector(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AGENT_BRAIN_AUTH=basic → get_auth_dependency returns 'basic-bearer'."""
        monkeypatch.setenv("AGENT_BRAIN_AUTH", "basic")

        dep = get_auth_dependency()
        assert (
            dep == "basic-bearer"
        ), f"Basic mode must return 'basic-bearer', got {dep!r}"

    def test_oauth_mode_returns_oauth_selector(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AGENT_BRAIN_AUTH=oauth → get_auth_dependency returns 'oauth-require-auth'."""
        monkeypatch.setenv("AGENT_BRAIN_AUTH", "oauth")
        # Resource is not needed for get_auth_dependency itself
        # (gate validates it via check_auth_startup_gate; get_auth_dependency
        # is called post-gate)
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", _RESOURCE)

        dep = get_auth_dependency()
        assert (
            dep == "oauth-require-auth"
        ), f"OAuth mode must return 'oauth-require-auth', got {dep!r}"

    def test_basic_and_oauth_selectors_differ(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Basic and oauth selectors are distinct — no overlap, no composition."""
        monkeypatch.setenv("AGENT_BRAIN_AUTH", "basic")
        basic_dep = get_auth_dependency()

        monkeypatch.setenv("AGENT_BRAIN_AUTH", "oauth")
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", _RESOURCE)
        oauth_dep = get_auth_dependency()

        assert (
            basic_dep != oauth_dep
        ), "Basic and oauth selectors must be distinct values"
        assert basic_dep is not None
        assert oauth_dep is not None

    def test_none_mode_resolve_auth_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sanity: resolve_auth_mode() returns AuthMode.none when unset."""
        monkeypatch.delenv("AGENT_BRAIN_AUTH", raising=False)
        assert resolve_auth_mode() is AuthMode.none

    def test_basic_mode_resolve_auth_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sanity: resolve_auth_mode() returns AuthMode.basic for 'basic'."""
        monkeypatch.setenv("AGENT_BRAIN_AUTH", "basic")
        assert resolve_auth_mode() is AuthMode.basic

    def test_oauth_mode_resolve_auth_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sanity: resolve_auth_mode() returns AuthMode.oauth for 'oauth'."""
        monkeypatch.setenv("AGENT_BRAIN_AUTH", "oauth")
        assert resolve_auth_mode() is AuthMode.oauth
