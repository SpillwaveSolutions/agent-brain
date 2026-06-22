"""Tests for split-AS config env vars and build_verifier() selector (Phase 70 Plan 01 Task 3).

TDD RED → GREEN: tests written BEFORE implementation.

Validates:
  - resolve_split_as_settings() with no env → (None, None, None, None, None)
  - AGENT_BRAIN_OAUTH_JWKS_URI set → jwks_uri populated
  - AGENT_BRAIN_OAUTH_INTROSPECTION_URL set → introspection_url populated
  - Blank/empty string env vars normalize to None
  - build_verifier(): JWKS_URI set → JwksTokenVerifier
  - build_verifier(): INTROSPECTION_URL set (no JWKS) → IntrospectionTokenVerifier
  - build_verifier(): neither set → LocalRs256Verifier (backward-compatible)
  - JWKS_URI takes precedence over INTROSPECTION_URL if both set

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
Research: 70-RESEARCH.md §"Wiring in http.py", Pitfall 7 (Keycloak iss format)
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RESOURCE = "https://mcp.example.com/mcp"
_ISSUER = "http://localhost:8080/realms/agent-brain"
_JWKS_URI = "http://localhost:8080/realms/agent-brain/protocol/openid-connect/certs"
_INTROSPECTION_URL = "http://localhost:8080/realms/agent-brain/protocol/openid-connect/token/introspect"
_INTRO_CLIENT_ID = "introspect-client"
_INTRO_CLIENT_SECRET = "introspect-secret"


# ---------------------------------------------------------------------------
# resolve_split_as_settings tests
# ---------------------------------------------------------------------------


class TestResolveSplitAsSettings:
    """resolve_split_as_settings() reads split-AS env vars correctly."""

    def test_no_env_returns_all_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No split-AS env vars → returns 5-tuple of all None."""
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_JWKS_URI", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_INTROSPECTION_URL", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_ID", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_ISSUER", raising=False)

        from agent_brain_mcp.config import resolve_split_as_settings

        result = resolve_split_as_settings()
        assert result == (None, None, None, None, None)

    def test_jwks_uri_populated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AGENT_BRAIN_OAUTH_JWKS_URI set → jwks_uri (index 0) populated."""
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_JWKS_URI", _JWKS_URI)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_INTROSPECTION_URL", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_ID", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_ISSUER", raising=False)

        from agent_brain_mcp.config import resolve_split_as_settings

        jwks_uri, introspection_url, intro_id, intro_secret, issuer = resolve_split_as_settings()
        assert jwks_uri == _JWKS_URI
        assert introspection_url is None
        assert intro_id is None
        assert intro_secret is None
        assert issuer is None

    def test_introspection_url_populated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AGENT_BRAIN_OAUTH_INTROSPECTION_URL set → introspection_url (index 1) populated."""
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_JWKS_URI", raising=False)
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_INTROSPECTION_URL", _INTROSPECTION_URL)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_ID", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_ISSUER", raising=False)

        from agent_brain_mcp.config import resolve_split_as_settings

        jwks_uri, introspection_url, intro_id, intro_secret, issuer = resolve_split_as_settings()
        assert jwks_uri is None
        assert introspection_url == _INTROSPECTION_URL

    def test_introspection_credentials_populated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Introspection client ID and secret populated when set."""
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_JWKS_URI", raising=False)
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_INTROSPECTION_URL", _INTROSPECTION_URL)
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_ID", _INTRO_CLIENT_ID)
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_SECRET", _INTRO_CLIENT_SECRET)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_ISSUER", raising=False)

        from agent_brain_mcp.config import resolve_split_as_settings

        _, _, intro_id, intro_secret, _ = resolve_split_as_settings()
        assert intro_id == _INTRO_CLIENT_ID
        assert intro_secret == _INTRO_CLIENT_SECRET

    def test_issuer_populated_from_existing_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AGENT_BRAIN_OAUTH_ISSUER (existing var) exposed at index 4."""
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_JWKS_URI", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_INTROSPECTION_URL", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_ID", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_SECRET", raising=False)
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_ISSUER", _ISSUER)

        from agent_brain_mcp.config import resolve_split_as_settings

        _, _, _, _, issuer = resolve_split_as_settings()
        assert issuer == _ISSUER

    def test_empty_string_normalizes_to_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty string env vars normalize to None (mirrors resolve_oauth_settings idiom)."""
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_JWKS_URI", "")
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_INTROSPECTION_URL", "   ")  # whitespace only
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_ID", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_ISSUER", raising=False)

        from agent_brain_mcp.config import resolve_split_as_settings

        jwks_uri, introspection_url, _, _, _ = resolve_split_as_settings()
        assert jwks_uri is None
        assert introspection_url is None


# ---------------------------------------------------------------------------
# build_verifier() selector tests
# ---------------------------------------------------------------------------


class TestBuildVerifierSelector:
    """build_verifier() selects the correct verifier by config."""

    def test_jwks_uri_selects_jwks_verifier(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AGENT_BRAIN_OAUTH_JWKS_URI set → returns JwksTokenVerifier."""
        import agent_brain_mcp.oauth.keys as _keys_mod

        _keys_mod._signing_key_singleton = None  # noqa: SLF001

        monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", _RESOURCE)
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_ISSUER", _ISSUER)
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_JWKS_URI", _JWKS_URI)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_INTROSPECTION_URL", raising=False)

        from agent_brain_mcp.oauth.verifier import JwksTokenVerifier, build_verifier

        v = build_verifier()
        assert isinstance(v, JwksTokenVerifier), (
            f"JWKS_URI set should return JwksTokenVerifier, got {type(v)}"
        )

    def test_introspection_url_selects_introspection_verifier(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """INTROSPECTION_URL set (no JWKS_URI) → returns IntrospectionTokenVerifier."""
        import agent_brain_mcp.oauth.keys as _keys_mod

        _keys_mod._signing_key_singleton = None  # noqa: SLF001

        monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", _RESOURCE)
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_ISSUER", _ISSUER)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_JWKS_URI", raising=False)
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_INTROSPECTION_URL", _INTROSPECTION_URL)
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_ID", _INTRO_CLIENT_ID)
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_SECRET", _INTRO_CLIENT_SECRET)

        from agent_brain_mcp.oauth.verifier import IntrospectionTokenVerifier, build_verifier

        v = build_verifier()
        assert isinstance(v, IntrospectionTokenVerifier), (
            f"INTROSPECTION_URL set should return IntrospectionTokenVerifier, got {type(v)}"
        )

    def test_neither_set_returns_local_rs256_verifier(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Neither JWKS_URI nor INTROSPECTION_URL set → returns LocalRs256Verifier (backward-compatible)."""
        import agent_brain_mcp.oauth.keys as _keys_mod

        _keys_mod._signing_key_singleton = None  # noqa: SLF001

        monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", _RESOURCE)
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_ISSUER", _ISSUER)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_JWKS_URI", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_INTROSPECTION_URL", raising=False)

        from agent_brain_mcp.oauth.verifier import LocalRs256Verifier, build_verifier

        v = build_verifier()
        assert isinstance(v, LocalRs256Verifier), (
            f"No split-AS env → should return LocalRs256Verifier, got {type(v)}"
        )

    def test_jwks_uri_takes_precedence_over_introspection_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """JWKS_URI and INTROSPECTION_URL both set → JWKS_URI wins."""
        import agent_brain_mcp.oauth.keys as _keys_mod

        _keys_mod._signing_key_singleton = None  # noqa: SLF001

        monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", _RESOURCE)
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_ISSUER", _ISSUER)
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_JWKS_URI", _JWKS_URI)
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_INTROSPECTION_URL", _INTROSPECTION_URL)

        from agent_brain_mcp.oauth.verifier import JwksTokenVerifier, build_verifier

        v = build_verifier()
        assert isinstance(v, JwksTokenVerifier), (
            "JWKS_URI should take precedence over INTROSPECTION_URL"
        )

    def test_build_verifier_without_resource_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """build_verifier() without AGENT_BRAIN_OAUTH_RESOURCE raises RuntimeError."""
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_RESOURCE", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_JWKS_URI", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_INTROSPECTION_URL", raising=False)

        from agent_brain_mcp.oauth.verifier import build_verifier

        with pytest.raises(RuntimeError, match="AGENT_BRAIN_OAUTH_RESOURCE"):
            build_verifier()

    def test_issuer_override_passed_to_jwks_verifier(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """build_verifier(issuer_override=...) passes the override to JwksTokenVerifier."""
        import agent_brain_mcp.oauth.keys as _keys_mod

        _keys_mod._signing_key_singleton = None  # noqa: SLF001

        override_issuer = "https://override.example.com"
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", _RESOURCE)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_ISSUER", raising=False)
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_JWKS_URI", _JWKS_URI)
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_INTROSPECTION_URL", raising=False)

        from agent_brain_mcp.oauth.verifier import JwksTokenVerifier, build_verifier

        v = build_verifier(issuer_override=override_issuer)
        assert isinstance(v, JwksTokenVerifier)
        assert v.issuer == override_issuer
