"""Unit tests for the ``verify_api_key`` FastAPI dependency (Issue #179).

Verifies the dependency in isolation against a minimal FastAPI app so the
``Header(...)`` resolver and ``HTTPException`` plumbing exercise the same path
they take in production routers. The router-wiring tests in
``test_auth_enforcement.py`` cover the integration side.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from agent_brain_server.api.security import verify_api_key
from agent_brain_server.config.settings import get_settings


@pytest.fixture
def reset_settings_cache() -> Generator[None, None, None]:
    """Reset ``get_settings``'s lru_cache around each test.

    The Settings class reads env vars at construction; without clearing the
    cache, a monkeypatched env var won't show up in ``settings.AGENT_BRAIN_API_KEY``.
    """
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(verify_api_key)])
    async def protected() -> dict[str, str]:
        return {"ok": "true"}

    return app


def test_noop_when_setting_empty_and_no_header(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    monkeypatch.setenv("AGENT_BRAIN_API_KEY", "")
    client = TestClient(_make_app())

    response = client.get("/protected")

    assert response.status_code == 200
    assert response.json() == {"ok": "true"}


def test_noop_when_setting_empty_even_with_random_header(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    monkeypatch.setenv("AGENT_BRAIN_API_KEY", "")
    client = TestClient(_make_app())

    response = client.get("/protected", headers={"X-API-Key": "ignored"})

    assert response.status_code == 200


def test_401_when_setting_present_and_header_missing(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    monkeypatch.setenv("AGENT_BRAIN_API_KEY", "secret-token")
    client = TestClient(_make_app())

    response = client.get("/protected")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API key"
    assert response.headers["WWW-Authenticate"] == "X-API-Key"


def test_401_when_setting_present_and_header_wrong(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    monkeypatch.setenv("AGENT_BRAIN_API_KEY", "secret-token")
    client = TestClient(_make_app())

    response = client.get("/protected", headers={"X-API-Key": "wrong"})

    assert response.status_code == 401


def test_200_when_setting_present_and_header_matches(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    monkeypatch.setenv("AGENT_BRAIN_API_KEY", "secret-token")
    client = TestClient(_make_app())

    response = client.get("/protected", headers={"X-API-Key": "secret-token"})

    assert response.status_code == 200
    assert response.json() == {"ok": "true"}


def test_header_is_case_insensitive_per_http_spec(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    """HTTP header names are case-insensitive; FastAPI's Header() honors that.

    Documenting the behavior with a test so a future refactor doesn't
    accidentally tighten the matcher.
    """
    monkeypatch.setenv("AGENT_BRAIN_API_KEY", "secret-token")
    client = TestClient(_make_app())

    response = client.get("/protected", headers={"x-api-key": "secret-token"})

    assert response.status_code == 200
