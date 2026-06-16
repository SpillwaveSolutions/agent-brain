"""Tests for AuthMode enum and OAuth settings resolver (OAUTH-09).

Covers the typed auth-mode toggle and OAuth env-var settings resolver
added to ``agent_brain_mcp.config`` as the settings foundation for
Phase 66 / Phase 67.

Behavioral contract:
  - ``AuthMode`` has exactly three members: none, basic, oauth
  - ``resolve_auth_mode()`` reads ``AGENT_BRAIN_AUTH``; unset → AuthMode.none
  - Valid values "none", "basic", "oauth" (case-insensitive via .lower())
    each resolve to the correct AuthMode member
  - ``resolve_oauth_settings()`` reads ``AGENT_BRAIN_OAUTH_RESOURCE`` and
    ``AGENT_BRAIN_OAUTH_ISSUER``; both unset → (None, None); empty → None
  - Resolution is pure-read — no exceptions, no validation here (gate
    validates in Task 2 / test_mcp_startup_gate.py)
"""

from __future__ import annotations

import pytest

from agent_brain_mcp.config import AuthMode, resolve_auth_mode, resolve_oauth_settings


@pytest.fixture(autouse=True)
def clear_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip all auth env vars so the dev shell doesn't leak in."""
    monkeypatch.delenv("AGENT_BRAIN_AUTH", raising=False)
    monkeypatch.delenv("AGENT_BRAIN_OAUTH_RESOURCE", raising=False)
    monkeypatch.delenv("AGENT_BRAIN_OAUTH_ISSUER", raising=False)


# ---------------------------------------------------------------------------
# AuthMode enum shape
# ---------------------------------------------------------------------------


def test_auth_mode_has_exactly_three_members() -> None:
    """AuthMode must have exactly {none, basic, oauth} — no extras."""
    members = {m.value for m in AuthMode}
    assert members == {"none", "basic", "oauth"}


def test_auth_mode_string_values() -> None:
    """Each member's .value is the lowercased name string."""
    assert AuthMode.none == "none"
    assert AuthMode.basic == "basic"
    assert AuthMode.oauth == "oauth"


def test_auth_mode_is_str_subclass() -> None:
    """AuthMode members must be string-comparable (str subclass)."""
    assert isinstance(AuthMode.none, str)
    assert isinstance(AuthMode.basic, str)
    assert isinstance(AuthMode.oauth, str)


# ---------------------------------------------------------------------------
# resolve_auth_mode() — happy path
# ---------------------------------------------------------------------------


def test_resolve_auth_mode_unset_returns_none() -> None:
    """Unset AGENT_BRAIN_AUTH → default AuthMode.none (no exit, no error)."""
    result = resolve_auth_mode()
    assert result is AuthMode.none


def test_resolve_auth_mode_explicit_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "none")
    assert resolve_auth_mode() is AuthMode.none


def test_resolve_auth_mode_basic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "basic")
    assert resolve_auth_mode() is AuthMode.basic


def test_resolve_auth_mode_oauth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "oauth")
    assert resolve_auth_mode() is AuthMode.oauth


# ---------------------------------------------------------------------------
# resolve_auth_mode() — case-insensitive
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw_value, expected",
    [
        ("None", AuthMode.none),
        ("NONE", AuthMode.none),
        ("Basic", AuthMode.basic),
        ("BASIC", AuthMode.basic),
        ("OAuth", AuthMode.oauth),
        ("OAUTH", AuthMode.oauth),
        ("OAuth2", None),  # invalid — gate rejects, resolver returns None
    ],
)
def test_resolve_auth_mode_case_insensitive(
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str,
    expected: AuthMode | None,
) -> None:
    """resolve_auth_mode() lowercases the env value before matching."""
    monkeypatch.setenv("AGENT_BRAIN_AUTH", raw_value)
    result = resolve_auth_mode()
    # For invalid values, resolve_auth_mode returns None (gate handles exit)
    assert result == expected


# ---------------------------------------------------------------------------
# resolve_oauth_settings() — pure read, no validation
# ---------------------------------------------------------------------------


def test_resolve_oauth_settings_both_unset() -> None:
    """Both vars unset → (None, None). No exception."""
    resource, issuer = resolve_oauth_settings()
    assert resource is None
    assert issuer is None


def test_resolve_oauth_settings_resource_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", "https://mcp.example.com/mcp")
    resource, issuer = resolve_oauth_settings()
    assert resource == "https://mcp.example.com/mcp"
    assert issuer is None


def test_resolve_oauth_settings_issuer_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_BRAIN_OAUTH_ISSUER", "https://auth.example.com")
    resource, issuer = resolve_oauth_settings()
    assert resource is None
    assert issuer == "https://auth.example.com"


def test_resolve_oauth_settings_both_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", "https://mcp.example.com/mcp")
    monkeypatch.setenv("AGENT_BRAIN_OAUTH_ISSUER", "https://auth.example.com")
    resource, issuer = resolve_oauth_settings()
    assert resource == "https://mcp.example.com/mcp"
    assert issuer == "https://auth.example.com"


def test_resolve_oauth_settings_empty_string_normalises_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty string → None (normalised at read time, gate validates presence)."""
    monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", "")
    monkeypatch.setenv("AGENT_BRAIN_OAUTH_ISSUER", "")
    resource, issuer = resolve_oauth_settings()
    assert resource is None
    assert issuer is None


def test_resolve_oauth_settings_no_exception_on_invalid_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolver is pure-read. No exception even if auth mode is garbage."""
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "garbage")
    # Should not raise — resolver is independent of mode validation
    resource, issuer = resolve_oauth_settings()
    assert resource is None
    assert issuer is None
