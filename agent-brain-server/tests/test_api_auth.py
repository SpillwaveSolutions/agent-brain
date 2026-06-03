"""Tests for bearer-token API authentication (Issue #179).

Three layers:

* unit tests of the ``verify_bearer_token`` dependency (every branch),
* HTTP integration tests proving guarded routers 401 and ``/health`` stays open,
* tests of the startup key resolution (``_resolve_api_key``) and runtime.json
  persistence (key present, file mode 600).
"""

import stat

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from pydantic import SecretStr

from agent_brain_server.api.security import verify_bearer_token
from agent_brain_server.config.settings import Settings, get_settings

TEST_KEY = "test-bearer-token-abc123"


@pytest.fixture(autouse=True)
def _clean_auth_state(monkeypatch):
    """Keep auth globals/env hermetic.

    ``_resolve_api_key`` mutates the live settings instance and ``os.environ``
    directly (so uvicorn reload workers inherit the key); reset both around every
    test so ordering can't leak a key/insecure flag between cases.
    """
    import os

    from agent_brain_server.api import main as main_mod

    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("INSECURE_NO_AUTH", raising=False)
    orig_key = main_mod.settings.API_KEY
    orig_insecure = main_mod.settings.INSECURE_NO_AUTH
    yield
    main_mod.settings.API_KEY = orig_key
    main_mod.settings.INSECURE_NO_AUTH = orig_insecure
    os.environ.pop("API_KEY", None)
    os.environ.pop("INSECURE_NO_AUTH", None)


def _creds(token: str, scheme: str = "Bearer") -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme=scheme, credentials=token)


# --------------------------------------------------------------------------- #
# Unit tests — verify_bearer_token dependency
# --------------------------------------------------------------------------- #


def test_valid_token_passes() -> None:
    settings = Settings(API_KEY=SecretStr(TEST_KEY), INSECURE_NO_AUTH=False)
    # Returns None (no exception) when the token matches.
    assert verify_bearer_token(_creds(TEST_KEY), settings) is None


def test_missing_header_raises_401() -> None:
    settings = Settings(API_KEY=SecretStr(TEST_KEY), INSECURE_NO_AUTH=False)
    with pytest.raises(HTTPException) as exc:
        verify_bearer_token(None, settings)
    assert exc.value.status_code == 401
    assert exc.value.headers == {"WWW-Authenticate": "Bearer"}


def test_wrong_token_raises_401() -> None:
    settings = Settings(API_KEY=SecretStr(TEST_KEY), INSECURE_NO_AUTH=False)
    with pytest.raises(HTTPException) as exc:
        verify_bearer_token(_creds("not-the-key"), settings)
    assert exc.value.status_code == 401


def test_wrong_scheme_raises_401() -> None:
    settings = Settings(API_KEY=SecretStr(TEST_KEY), INSECURE_NO_AUTH=False)
    with pytest.raises(HTTPException) as exc:
        verify_bearer_token(_creds(TEST_KEY, scheme="Basic"), settings)
    assert exc.value.status_code == 401


def test_insecure_mode_bypasses_auth() -> None:
    settings = Settings(API_KEY=None, INSECURE_NO_AUTH=True)
    # No credentials, no key — still allowed because auth is explicitly disabled.
    assert verify_bearer_token(None, settings) is None


def test_no_key_configured_raises_503() -> None:
    # Auth on but no key: fail closed (503), never fall through to open.
    settings = Settings(API_KEY=None, INSECURE_NO_AUTH=False)
    with pytest.raises(HTTPException) as exc:
        verify_bearer_token(_creds(TEST_KEY), settings)
    assert exc.value.status_code == 503


# --------------------------------------------------------------------------- #
# Integration tests — real HTTP through the app
# --------------------------------------------------------------------------- #


@pytest.fixture
def authed_client(app_with_mocks):
    """Client with bearer auth ACTIVE (pops the session-level conftest bypass)."""
    app = app_with_mocks
    app.dependency_overrides.pop(verify_bearer_token, None)
    app.dependency_overrides[get_settings] = lambda: Settings(
        API_KEY=SecretStr(TEST_KEY), INSECURE_NO_AUTH=False
    )
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_settings, None)
    # Restore the session-level bypass so subsequent tests are unaffected.
    app.dependency_overrides[verify_bearer_token] = lambda: None


def test_health_is_open_without_auth(authed_client) -> None:
    # /health must stay unauthenticated (liveness probes, CLI port discovery).
    resp = authed_client.get("/health/")
    assert resp.status_code == 200


def test_query_without_token_is_401(authed_client) -> None:
    resp = authed_client.post("/query/", json={"query": "anything"})
    assert resp.status_code == 401


def test_query_with_wrong_token_is_401(authed_client) -> None:
    resp = authed_client.post(
        "/query/",
        json={"query": "anything"},
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert resp.status_code == 401


def test_query_with_valid_token_passes_auth(authed_client) -> None:
    # Valid token clears the auth gate; the mocked query service then answers.
    resp = authed_client.post(
        "/query/",
        json={"query": "anything"},
        headers={"Authorization": f"Bearer {TEST_KEY}"},
    )
    assert resp.status_code != 401


def test_insecure_mode_opens_endpoints(app_with_mocks) -> None:
    app = app_with_mocks
    app.dependency_overrides.pop(verify_bearer_token, None)
    app.dependency_overrides[get_settings] = lambda: Settings(
        API_KEY=None, INSECURE_NO_AUTH=True
    )
    try:
        with TestClient(app) as client:
            resp = client.post("/query/", json={"query": "anything"})
            assert resp.status_code != 401
    finally:
        app.dependency_overrides.pop(get_settings, None)
        # Restore the session-level bypass so subsequent tests are unaffected.
        app.dependency_overrides[verify_bearer_token] = lambda: None


# --------------------------------------------------------------------------- #
# Startup key resolution + runtime.json persistence
# --------------------------------------------------------------------------- #


def test_generate_api_key_is_unique_and_urlsafe() -> None:
    from agent_brain_server.runtime import generate_api_key

    a, b = generate_api_key(), generate_api_key()
    assert a != b
    assert len(a) >= 32
    # token_urlsafe output is limited to the URL-safe base64 alphabet.
    assert all(c.isalnum() or c in "-_" for c in a)


def test_resolve_api_key_refuses_without_state_dir(monkeypatch) -> None:
    import click

    from agent_brain_server.api import main as main_mod

    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setattr(main_mod.settings, "API_KEY", None, raising=False)
    # No state_dir to persist a generated key, not insecure -> refuse to start.
    with pytest.raises(click.ClickException):
        main_mod._resolve_api_key(state_dir=None, insecure=False)


def test_resolve_api_key_insecure_returns_none(monkeypatch) -> None:
    from agent_brain_server.api import main as main_mod

    assert main_mod._resolve_api_key(state_dir=None, insecure=True) is None
    assert main_mod.settings.INSECURE_NO_AUTH is True
    # reset global mutation so we don't leak into other tests
    monkeypatch.setattr(main_mod.settings, "INSECURE_NO_AUTH", False, raising=False)


def test_resolve_api_key_generates_and_persists(tmp_path, monkeypatch) -> None:
    from agent_brain_server.api import main as main_mod
    from agent_brain_server.runtime import RuntimeState, read_runtime, write_runtime

    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setattr(main_mod.settings, "API_KEY", None, raising=False)

    key = main_mod._resolve_api_key(state_dir=tmp_path, insecure=False)
    assert key
    # Persist via the same path the server uses, then confirm it round-trips.
    write_runtime(tmp_path, RuntimeState(api_key=key))
    restored = read_runtime(tmp_path)
    assert restored is not None
    assert restored.api_key == key


def test_runtime_json_is_mode_600(tmp_path) -> None:
    from agent_brain_server.runtime import RuntimeState, write_runtime

    write_runtime(tmp_path, RuntimeState(api_key="secret"))
    mode = stat.S_IMODE((tmp_path / "runtime.json").stat().st_mode)
    # Owner-only: no group/other bits (the file holds a secret).
    assert mode & 0o077 == 0


def test_resolve_api_key_reads_existing_runtime(tmp_path, monkeypatch) -> None:
    from agent_brain_server.api import main as main_mod
    from agent_brain_server.runtime import RuntimeState, write_runtime

    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setattr(main_mod.settings, "API_KEY", None, raising=False)
    write_runtime(tmp_path, RuntimeState(api_key="preexisting-key"))

    key = main_mod._resolve_api_key(state_dir=tmp_path, insecure=False)
    assert key == "preexisting-key"
