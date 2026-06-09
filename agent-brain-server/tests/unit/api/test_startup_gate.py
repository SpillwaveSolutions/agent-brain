"""Tests for the API key startup gate and /docs gating in ``api/main.py``.

Covers Issue #199 (199-03) acceptance — refuse-without-key by default:

* No ``API_KEY`` + no ``INSECURE_NO_AUTH`` → ``sys.exit(2)`` on **any** bind
  host (loopback included; 127.0.0.1 is not a trust boundary).
* No ``API_KEY`` + ``INSECURE_NO_AUTH=true`` → loud warning, no exit.
* ``API_KEY`` set → silent start on any host.
* Legacy ``AGENT_BRAIN_API_KEY`` env var continues to work because the
  Settings validator backfills it into ``API_KEY``.
* /docs gating now keys off ``API_KEY`` (single source of truth) instead
  of the deprecated v1 field.
"""

from __future__ import annotations

import logging
from collections.abc import Generator

import pytest

from agent_brain_server.api.main import _build_app, _check_api_key_startup_gate
from agent_brain_server.config.settings import get_settings


@pytest.fixture
def reset_settings_cache() -> Generator[None, None, None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def clear_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start each test from a known-empty auth env so unrelated env vars
    in the dev shell don't leak in."""
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("AGENT_BRAIN_API_KEY", raising=False)
    monkeypatch.delenv("INSECURE_NO_AUTH", raising=False)


# ---------------------------------------------------------------------------
# Startup gate — refuse-without-key (the inversion from 199-03)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "0.0.0.0"])
def test_startup_gate_exits_when_no_key_on_any_host(
    reset_settings_cache: None, host: str
) -> None:
    """Loopback is no longer an implicit no-auth escape hatch.

    Pre-199-03 contract allowed empty key on 127.0.0.1 with a warning.
    Post-199-03 every host requires either ``API_KEY`` or
    ``INSECURE_NO_AUTH=true``.
    """
    with pytest.raises(SystemExit) as exc_info:
        _check_api_key_startup_gate(host)

    assert exc_info.value.code == 2


def test_startup_gate_warns_when_insecure_no_auth_true(
    monkeypatch: pytest.MonkeyPatch,
    reset_settings_cache: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit operator opt-out: server starts but logs a loud warning."""
    monkeypatch.setenv("INSECURE_NO_AUTH", "true")

    with caplog.at_level(logging.WARNING, logger="agent_brain_server.api.main"):
        _check_api_key_startup_gate("127.0.0.1")

    assert any(
        "INSECURE_NO_AUTH" in record.message and record.levelno == logging.WARNING
        for record in caplog.records
    )


def test_startup_gate_warns_even_on_non_loopback_with_insecure(
    monkeypatch: pytest.MonkeyPatch,
    reset_settings_cache: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``INSECURE_NO_AUTH=true`` works on every host — same exit path.

    Bound 0.0.0.0 without a key + INSECURE_NO_AUTH is a conscious choice
    (e.g. an embedded device on a private network). The startup gate
    doesn't second-guess it.
    """
    monkeypatch.setenv("INSECURE_NO_AUTH", "true")

    with caplog.at_level(logging.WARNING, logger="agent_brain_server.api.main"):
        _check_api_key_startup_gate("0.0.0.0")

    assert any("INSECURE_NO_AUTH" in record.message for record in caplog.records)


@pytest.mark.parametrize("host", ["127.0.0.1", "0.0.0.0", "10.0.0.5"])
def test_startup_gate_silent_when_api_key_set(
    monkeypatch: pytest.MonkeyPatch,
    reset_settings_cache: None,
    caplog: pytest.LogCaptureFixture,
    host: str,
) -> None:
    monkeypatch.setenv("API_KEY", "configured-key")

    with caplog.at_level(logging.WARNING, logger="agent_brain_server.api.main"):
        _check_api_key_startup_gate(host)

    assert not any(record.levelno >= logging.WARNING for record in caplog.records)


def test_startup_gate_accepts_legacy_env_var(
    monkeypatch: pytest.MonkeyPatch,
    reset_settings_cache: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """PR #195 / Issue #179 installs keep working — validator backfills API_KEY."""
    monkeypatch.setenv("AGENT_BRAIN_API_KEY", "legacy-key")

    with caplog.at_level(logging.WARNING, logger="agent_brain_server.api.main"):
        _check_api_key_startup_gate("0.0.0.0")

    # No exit, no warning — silent start under the legacy env var.
    assert not any(record.levelno >= logging.WARNING for record in caplog.records)


def test_api_key_takes_precedence_over_insecure(
    monkeypatch: pytest.MonkeyPatch,
    reset_settings_cache: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When both are set, API_KEY wins — no INSECURE warning fires.

    Treating ``INSECURE_NO_AUTH=true`` as a global override would let a
    stale environment variable silently disable auth on an otherwise
    correctly-configured server. The gate checks ``API_KEY`` first.
    """
    monkeypatch.setenv("API_KEY", "configured-key")
    monkeypatch.setenv("INSECURE_NO_AUTH", "true")

    with caplog.at_level(logging.WARNING, logger="agent_brain_server.api.main"):
        _check_api_key_startup_gate("127.0.0.1")

    assert not any(record.levelno >= logging.WARNING for record in caplog.records)


# ---------------------------------------------------------------------------
# /docs gating
# ---------------------------------------------------------------------------


def test_docs_gated_when_api_key_set_and_debug_false(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    monkeypatch.setenv("API_KEY", "docs-test-key")
    monkeypatch.setenv("DEBUG", "false")

    app = _build_app()

    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None


def test_docs_open_when_api_key_set_but_debug_true(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    monkeypatch.setenv("API_KEY", "docs-test-key")
    monkeypatch.setenv("DEBUG", "true")

    app = _build_app()

    assert app.docs_url == "/docs"
    assert app.redoc_url == "/redoc"
    assert app.openapi_url == "/openapi.json"


def test_docs_open_when_api_key_unset(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    """No API_KEY → endpoints are open → no point gating the schema."""
    monkeypatch.setenv("DEBUG", "false")

    app = _build_app()

    assert app.docs_url == "/docs"
    assert app.redoc_url == "/redoc"
    assert app.openapi_url == "/openapi.json"


def test_docs_gated_via_legacy_env_var(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    """AGENT_BRAIN_API_KEY → API_KEY backfill flows through to /docs gating."""
    monkeypatch.setenv("AGENT_BRAIN_API_KEY", "legacy-docs-key")
    monkeypatch.setenv("DEBUG", "false")

    app = _build_app()

    assert app.docs_url is None
    assert app.openapi_url is None
