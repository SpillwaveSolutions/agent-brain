"""Tests for MCP auth startup gate and auth-dependency selector (OAUTH-09).

Mirrors agent_brain_server/tests/unit/api/test_startup_gate.py shape.
Tests the MCP-side startup gate ``check_auth_startup_gate()`` and the
mutual-exclusion selector ``get_auth_dependency()``.

Behavioral contract:
  - AGENT_BRAIN_AUTH unset → silent (None), no exit, no WARNING/CRITICAL
  - AGENT_BRAIN_AUTH in {none, basic} + valid resource (or none) → silent
  - AGENT_BRAIN_AUTH=oauth + valid https:// resource → silent
  - AGENT_BRAIN_AUTH=garbage → SystemExit(2) + CRITICAL log naming the var
  - AGENT_BRAIN_AUTH=oauth + resource UNSET → SystemExit(2) + CRITICAL log
  - AGENT_BRAIN_AUTH=oauth + resource="" → SystemExit(2)
  - AGENT_BRAIN_AUTH=oauth + resource="no-scheme.com/mcp" → SystemExit(2)
  - AGENT_BRAIN_AUTH=none/basic with resource unset → no exit
  - get_auth_dependency() returns exactly one value per mode (mutual exclusion)
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from agent_brain_mcp.config import (
    check_auth_startup_gate,
    get_auth_dependency,
)


@pytest.fixture(autouse=True)
def clear_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip all auth env vars from the dev shell before each test."""
    monkeypatch.delenv("AGENT_BRAIN_AUTH", raising=False)
    monkeypatch.delenv("AGENT_BRAIN_OAUTH_RESOURCE", raising=False)
    monkeypatch.delenv("AGENT_BRAIN_OAUTH_ISSUER", raising=False)


# ---------------------------------------------------------------------------
# check_auth_startup_gate() — valid modes (no exit)
# ---------------------------------------------------------------------------


def test_gate_unset_returns_none_silently(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unset AGENT_BRAIN_AUTH → default none → no exit, no log."""
    with caplog.at_level(logging.WARNING, logger="agent_brain_mcp.config"):
        result = check_auth_startup_gate()

    assert result is None
    assert not any(record.levelno >= logging.WARNING for record in caplog.records)


def test_gate_explicit_none_is_silent(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "none")

    with caplog.at_level(logging.WARNING, logger="agent_brain_mcp.config"):
        result = check_auth_startup_gate()

    assert result is None
    assert not any(record.levelno >= logging.WARNING for record in caplog.records)


def test_gate_basic_is_silent(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "basic")

    with caplog.at_level(logging.WARNING, logger="agent_brain_mcp.config"):
        result = check_auth_startup_gate()

    assert result is None
    assert not any(record.levelno >= logging.WARNING for record in caplog.records)


def test_gate_oauth_with_valid_resource_is_silent(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "oauth")
    monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", "https://mcp.example.com/mcp")

    with caplog.at_level(logging.WARNING, logger="agent_brain_mcp.config"):
        result = check_auth_startup_gate()

    assert result is None
    assert not any(record.levelno >= logging.WARNING for record in caplog.records)


@pytest.mark.parametrize("mode", ["none", "basic", "oauth"])
def test_gate_all_three_valid_modes_pass(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    """Parametrized over the three valid modes — all should not exit."""
    monkeypatch.setenv("AGENT_BRAIN_AUTH", mode)
    if mode == "oauth":
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", "https://mcp.example.com/mcp")
    # Should not raise SystemExit
    check_auth_startup_gate()


# ---------------------------------------------------------------------------
# check_auth_startup_gate() — invalid toggle value
# ---------------------------------------------------------------------------


def test_gate_invalid_toggle_exits_code_2(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown AGENT_BRAIN_AUTH value → SystemExit(2) + CRITICAL log."""
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "garbage")

    with caplog.at_level(logging.CRITICAL, logger="agent_brain_mcp.config"):
        with pytest.raises(SystemExit) as exc_info:
            check_auth_startup_gate()

    assert exc_info.value.code == 2
    assert any(
        record.levelno == logging.CRITICAL and "AGENT_BRAIN_AUTH" in record.message
        for record in caplog.records
    )


@pytest.mark.parametrize(
    "bad_value",
    ["garbage", "jwt", "token", "bearer", "API_KEY", "1", "oauth2"],
)
def test_gate_various_invalid_values_all_exit_2(
    monkeypatch: pytest.MonkeyPatch,
    bad_value: str,
) -> None:
    monkeypatch.setenv("AGENT_BRAIN_AUTH", bad_value)

    with pytest.raises(SystemExit) as exc_info:
        check_auth_startup_gate()

    assert exc_info.value.code == 2


def test_gate_invalid_toggle_log_includes_bad_value(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """CRITICAL log must name the bad value so operators can debug."""
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "badmode")

    with caplog.at_level(logging.CRITICAL, logger="agent_brain_mcp.config"):
        with pytest.raises(SystemExit):
            check_auth_startup_gate()

    assert any("badmode" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# check_auth_startup_gate() — oauth mode resource validation
# ---------------------------------------------------------------------------


def test_gate_oauth_resource_unset_exits_code_2(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """oauth mode + resource UNSET → SystemExit(2) + CRITICAL naming resource."""
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "oauth")

    with caplog.at_level(logging.CRITICAL, logger="agent_brain_mcp.config"):
        with pytest.raises(SystemExit) as exc_info:
            check_auth_startup_gate()

    assert exc_info.value.code == 2
    assert any(
        "AGENT_BRAIN_OAUTH_RESOURCE" in record.message for record in caplog.records
    )


def test_gate_oauth_resource_empty_string_exits_code_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """oauth mode + resource="" → SystemExit(2)."""
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "oauth")
    monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", "")

    with pytest.raises(SystemExit) as exc_info:
        check_auth_startup_gate()

    assert exc_info.value.code == 2


def test_gate_oauth_resource_whitespace_only_exits_code_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """oauth mode + resource="   " (whitespace only) → SystemExit(2)."""
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "oauth")
    monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", "   ")

    with pytest.raises(SystemExit) as exc_info:
        check_auth_startup_gate()

    assert exc_info.value.code == 2


def test_gate_oauth_resource_no_scheme_exits_code_2(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """oauth mode + bare hostname (no scheme) → SystemExit(2).

    A URI MUST have a scheme per design doc §Canonical Resource URI Contract.
    mcp.example.com/mcp is NOT a valid resource URI.
    """
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "oauth")
    monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", "mcp.example.com/mcp")

    with caplog.at_level(logging.CRITICAL, logger="agent_brain_mcp.config"):
        with pytest.raises(SystemExit) as exc_info:
            check_auth_startup_gate()

    assert exc_info.value.code == 2


def test_gate_oauth_resource_valid_https_is_silent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """oauth mode + https:// resource → no exit (the documented happy path)."""
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "oauth")
    monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", "https://mcp.example.com/mcp")

    # Must not raise SystemExit
    check_auth_startup_gate()


def test_gate_oauth_resource_http_scheme_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """http:// scheme is syntactically valid (gate checks scheme, not TLS)."""
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "oauth")
    monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", "http://localhost:8080/mcp")

    check_auth_startup_gate()


def test_gate_oauth_resource_with_fragment_exits_code_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """oauth mode + URI with fragment → SystemExit(2).

    RFC 8707 §2 states resource URIs MUST NOT contain a fragment.
    """
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "oauth")
    monkeypatch.setenv(
        "AGENT_BRAIN_OAUTH_RESOURCE", "https://mcp.example.com/mcp#section"
    )

    with pytest.raises(SystemExit) as exc_info:
        check_auth_startup_gate()

    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# check_auth_startup_gate() — none/basic do NOT require resource
# ---------------------------------------------------------------------------


def test_gate_none_mode_does_not_require_resource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """none mode starts without AGENT_BRAIN_OAUTH_RESOURCE."""
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "none")
    # AGENT_BRAIN_OAUTH_RESOURCE deliberately not set (autouse fixture)

    check_auth_startup_gate()  # must not raise


def test_gate_basic_mode_does_not_require_resource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """basic mode starts without AGENT_BRAIN_OAUTH_RESOURCE."""
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "basic")

    check_auth_startup_gate()  # must not raise


# ---------------------------------------------------------------------------
# get_auth_dependency() — structural mutual exclusion
# ---------------------------------------------------------------------------


def test_get_auth_dependency_none_mode_returns_single_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """none mode returns exactly one selector (None — no auth)."""
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "none")
    result = get_auth_dependency()
    # none mode → no-op dependency (None)
    assert result is None


def test_get_auth_dependency_unset_defaults_to_none_mode(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unset AGENT_BRAIN_AUTH → none mode → None selector (no auth)."""
    result = get_auth_dependency()
    assert result is None


def test_get_auth_dependency_basic_mode_returns_single_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """basic mode returns exactly one selector (basic-bearer marker)."""
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "basic")
    result = get_auth_dependency()
    # Distinct from none and oauth
    assert result is not None
    assert result == "basic-bearer"


def test_get_auth_dependency_oauth_mode_raises_not_implemented(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """oauth mode raises NotImplementedError — Phase-67 placeholder.

    The oauth branch of get_auth_dependency() is structurally wired in
    Phase 66 but RequireAuthMiddleware arrives in Phase 67. The seam
    exists; the middleware does not yet.
    """
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "oauth")

    with pytest.raises(NotImplementedError) as exc_info:
        get_auth_dependency()

    # Error message must name Phase 67
    assert "Phase 67" in str(exc_info.value)


def test_get_auth_dependency_none_and_basic_are_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """none and basic return different values — mutual exclusion holds."""
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "none")
    none_result = get_auth_dependency()

    monkeypatch.setenv("AGENT_BRAIN_AUTH", "basic")
    basic_result = get_auth_dependency()

    assert none_result != basic_result


def test_get_auth_dependency_each_mode_returns_exactly_one_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each mode returns a single scalar — never a list or tuple (no composition)."""
    for mode, expected_type in [("none", type(None)), ("basic", str)]:
        monkeypatch.setenv("AGENT_BRAIN_AUTH", mode)
        result: Any = get_auth_dependency()
        assert isinstance(
            result, expected_type
        ), f"Expected {expected_type} for mode={mode}, got {type(result)}"
