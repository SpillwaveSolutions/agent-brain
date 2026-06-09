"""Unit tests for the ``verify_bearer_token`` FastAPI dependency (Issue #199).

Verifies the dependency in isolation against a minimal FastAPI app so the
``Header(...)`` resolver and ``HTTPException`` plumbing exercise the same path
they take in production routers. The router-wiring tests in
``test_auth_enforcement.py`` cover the integration side.

Coverage map:

* No-op paths: ``API_KEY`` unset (loopback default), ``INSECURE_NO_AUTH=true``.
* Bearer path: 200 on match, 401 on missing/wrong/malformed header.
* X-API-Key fallback (deprecated): 200 on match (logs deprecation), 401 on
  wrong header value.
* Backwards-compat: setting only ``AGENT_BRAIN_API_KEY`` env var still gates
  the router because the Settings validator backfills ``API_KEY``.
* WWW-Authenticate header is always ``Bearer`` (RFC 6750), regardless of
  which header the client tried.
"""

from __future__ import annotations

import logging
from collections.abc import Generator

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from agent_brain_server.api.security import verify_bearer_token
from agent_brain_server.config.settings import get_settings


@pytest.fixture
def reset_settings_cache() -> Generator[None, None, None]:
    """Reset ``get_settings``'s lru_cache around each test.

    The Settings class reads env vars at construction; without clearing the
    cache, a monkeypatched env var won't show up in ``settings.API_KEY``.
    """
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(verify_bearer_token)])
    async def protected() -> dict[str, str]:
        return {"ok": "true"}

    return app


# ---------------------------------------------------------------------------
# No-op paths
# ---------------------------------------------------------------------------


def test_noop_when_api_key_unset_and_no_header(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    """Loopback default: no API_KEY → no auth required."""
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("AGENT_BRAIN_API_KEY", raising=False)
    monkeypatch.delenv("INSECURE_NO_AUTH", raising=False)
    client = TestClient(_make_app())

    response = client.get("/protected")

    assert response.status_code == 200
    assert response.json() == {"ok": "true"}


def test_noop_when_api_key_unset_even_with_random_header(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    """Headers are ignored entirely when the gate is unconfigured."""
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("AGENT_BRAIN_API_KEY", raising=False)
    client = TestClient(_make_app())

    response = client.get("/protected", headers={"Authorization": "Bearer ignored"})

    assert response.status_code == 200


def test_insecure_no_auth_bypasses_even_when_key_set(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    """Explicit operator opt-out short-circuits the dependency.

    The startup gate (199-03) is responsible for the loud warning when the
    server boots with INSECURE_NO_AUTH=true; the per-request path stays
    quiet so we don't spam logs.
    """
    monkeypatch.setenv("API_KEY", "secret-token")
    monkeypatch.setenv("INSECURE_NO_AUTH", "true")
    client = TestClient(_make_app())

    response = client.get("/protected")

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Bearer scheme (RFC 6750)
# ---------------------------------------------------------------------------


def test_401_when_key_set_and_no_credentials(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    monkeypatch.setenv("API_KEY", "secret-token")
    client = TestClient(_make_app())

    response = client.get("/protected")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert "Bearer" in response.json()["detail"]


def test_200_when_bearer_token_matches(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    monkeypatch.setenv("API_KEY", "secret-token")
    client = TestClient(_make_app())

    response = client.get(
        "/protected", headers={"Authorization": "Bearer secret-token"}
    )

    assert response.status_code == 200
    assert response.json() == {"ok": "true"}


def test_401_when_bearer_token_wrong(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    monkeypatch.setenv("API_KEY", "secret-token")
    client = TestClient(_make_app())

    response = client.get("/protected", headers={"Authorization": "Bearer wrong-token"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid bearer token"
    assert "invalid_token" in response.headers["WWW-Authenticate"]


def test_401_when_authorization_scheme_is_not_bearer(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    """Basic / Digest / Token / etc. are not accepted — Bearer only."""
    monkeypatch.setenv("API_KEY", "secret-token")
    client = TestClient(_make_app())

    response = client.get("/protected", headers={"Authorization": "Basic secret-token"})

    assert response.status_code == 401
    assert "must use the Bearer scheme" in response.json()["detail"]
    assert "invalid_request" in response.headers["WWW-Authenticate"]


def test_bearer_scheme_is_case_insensitive(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    """RFC 6750 §2.1: the scheme name is case-insensitive."""
    monkeypatch.setenv("API_KEY", "secret-token")
    client = TestClient(_make_app())

    response = client.get(
        "/protected", headers={"Authorization": "bearer secret-token"}
    )

    assert response.status_code == 200


def test_bearer_token_compared_constant_time(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    """The dependency uses secrets.compare_digest — guard against future drift.

    Behavioral test: tokens that are a prefix of the expected key (which a
    short-circuit ``==`` could accidentally accept) must still 401.
    """
    monkeypatch.setenv("API_KEY", "secret-token")
    client = TestClient(_make_app())

    response = client.get("/protected", headers={"Authorization": "Bearer secret-toke"})

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Deprecated X-API-Key fallback (PR #195 compatibility)
# ---------------------------------------------------------------------------


def test_x_api_key_still_works_with_deprecation_warning(
    monkeypatch: pytest.MonkeyPatch,
    reset_settings_cache: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Legacy X-API-Key callers keep working but get a one-version warning."""
    monkeypatch.setenv("API_KEY", "secret-token")
    client = TestClient(_make_app())

    with caplog.at_level(logging.WARNING, logger="agent_brain_server.api.security"):
        response = client.get("/protected", headers={"X-API-Key": "secret-token"})

    assert response.status_code == 200
    assert any(
        "X-API-Key header is deprecated" in record.message for record in caplog.records
    )


def test_401_when_x_api_key_wrong(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    monkeypatch.setenv("API_KEY", "secret-token")
    client = TestClient(_make_app())

    response = client.get("/protected", headers={"X-API-Key": "wrong"})

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


# ---------------------------------------------------------------------------
# Backwards-compat: AGENT_BRAIN_API_KEY env var still configures the gate
# ---------------------------------------------------------------------------


def test_legacy_env_var_backfills_api_key(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    """Users who set only AGENT_BRAIN_API_KEY get a working bearer gate.

    The Settings validator copies the legacy env var into ``API_KEY`` when
    ``API_KEY`` is unset, so the new dependency stays single-source-of-truth
    and the migration is transparent.
    """
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("AGENT_BRAIN_API_KEY", "legacy-token")
    client = TestClient(_make_app())

    response_no_creds = client.get("/protected")
    response_with_bearer = client.get(
        "/protected", headers={"Authorization": "Bearer legacy-token"}
    )

    assert response_no_creds.status_code == 401
    assert response_with_bearer.status_code == 200


def test_api_key_takes_precedence_over_legacy(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    """When both env vars are set, API_KEY wins — validator only backfills when None."""
    monkeypatch.setenv("API_KEY", "new-token")
    monkeypatch.setenv("AGENT_BRAIN_API_KEY", "old-token")
    client = TestClient(_make_app())

    new_token_ok = client.get(
        "/protected", headers={"Authorization": "Bearer new-token"}
    )
    old_token_rejected = client.get(
        "/protected", headers={"Authorization": "Bearer old-token"}
    )

    assert new_token_ok.status_code == 200
    assert old_token_rejected.status_code == 401
