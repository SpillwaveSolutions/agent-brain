"""Tests for the API key startup gate and /docs gating in ``api/main.py``.

Covers Issue #179 acceptance:

- ``API_HOST=0.0.0.0`` + empty key → process exits with code 2.
- ``API_HOST=127.0.0.1`` + empty key → warning logged, no exit.
- ``API_HOST=0.0.0.0`` + non-empty key → no exit, no warning.
- App built with ``AGENT_BRAIN_API_KEY`` set and ``DEBUG=false`` exposes
  ``docs_url=None`` and ``openapi_url=None`` (Swagger UI hidden when
  the schema would otherwise leak the protected surface).
- App built with ``DEBUG=true`` always keeps ``/docs`` mounted regardless
  of whether a key is configured.
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


# ---------------------------------------------------------------------------
# Startup gate
# ---------------------------------------------------------------------------


def test_startup_gate_exits_on_non_loopback_without_key(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    monkeypatch.setenv("AGENT_BRAIN_API_KEY", "")

    with pytest.raises(SystemExit) as exc_info:
        _check_api_key_startup_gate("0.0.0.0")

    assert exc_info.value.code == 2


def test_startup_gate_warns_on_loopback_without_key(
    monkeypatch: pytest.MonkeyPatch,
    reset_settings_cache: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("AGENT_BRAIN_API_KEY", "")

    with caplog.at_level(logging.WARNING, logger="agent_brain_server.api.main"):
        _check_api_key_startup_gate("127.0.0.1")

    assert any(
        "AGENT_BRAIN_API_KEY" in record.message and record.levelno == logging.WARNING
        for record in caplog.records
    )


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_startup_gate_accepts_all_loopback_aliases(
    monkeypatch: pytest.MonkeyPatch,
    reset_settings_cache: None,
    host: str,
) -> None:
    monkeypatch.setenv("AGENT_BRAIN_API_KEY", "")
    # Should not raise SystemExit for any loopback alias
    _check_api_key_startup_gate(host)


def test_startup_gate_silent_when_key_set_even_on_non_loopback(
    monkeypatch: pytest.MonkeyPatch,
    reset_settings_cache: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("AGENT_BRAIN_API_KEY", "configured-key")

    with caplog.at_level(logging.WARNING, logger="agent_brain_server.api.main"):
        _check_api_key_startup_gate("0.0.0.0")

    # Neither warning nor critical when a key is configured
    assert not any(record.levelno >= logging.WARNING for record in caplog.records)


# ---------------------------------------------------------------------------
# /docs gating
# ---------------------------------------------------------------------------


def test_docs_gated_when_key_set_and_debug_false(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    monkeypatch.setenv("AGENT_BRAIN_API_KEY", "docs-test-key")
    monkeypatch.setenv("DEBUG", "false")

    app = _build_app()

    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None


def test_docs_open_when_key_set_but_debug_true(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    monkeypatch.setenv("AGENT_BRAIN_API_KEY", "docs-test-key")
    monkeypatch.setenv("DEBUG", "true")

    app = _build_app()

    assert app.docs_url == "/docs"
    assert app.redoc_url == "/redoc"
    assert app.openapi_url == "/openapi.json"


def test_docs_open_when_key_unset(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    monkeypatch.setenv("AGENT_BRAIN_API_KEY", "")
    monkeypatch.setenv("DEBUG", "false")

    app = _build_app()

    assert app.docs_url == "/docs"
    assert app.redoc_url == "/redoc"
    assert app.openapi_url == "/openapi.json"
