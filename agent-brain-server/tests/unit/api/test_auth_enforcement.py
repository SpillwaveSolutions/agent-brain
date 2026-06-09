"""Integration tests proving each non-health router gates on ``verify_bearer_token``.

Two layers of evidence:

1. **Structural** — ``router.dependencies`` contains a
   ``Depends(verify_bearer_token)`` for every non-health router. Cheap
   regression guard against someone deleting the dependency from a router
   file.
2. **Behavioral** — a minimal FastAPI app mounts a stub endpoint underneath
   each router's dependency stack, and a TestClient verifies that requests
   without the ``Authorization: Bearer`` header return 401 while requests
   with the right header reach the stub handler. This exercises the full
   FastAPI dependency-resolution chain (the unit tests in
   ``test_security.py`` only cover the dependency in isolation).
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from agent_brain_server.api.routers import (
    cache,
    folders,
    graph,
    index,
    jobs,
    query,
)
from agent_brain_server.api.routers import health as health_router
from agent_brain_server.api.security import verify_bearer_token
from agent_brain_server.config.settings import get_settings

GATED_ROUTERS = [
    ("cache", cache.router),
    ("folders", folders.router),
    ("graph", graph.router),
    ("index", index.router),
    ("jobs", jobs.router),
    ("query", query.router),
]


@pytest.fixture
def reset_settings_cache() -> Generator[None, None, None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Structural layer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,router", GATED_ROUTERS)
def test_each_gated_router_declares_verify_bearer_token(
    name: str, router: object
) -> None:
    """``router.dependencies`` must include a ``Depends(verify_bearer_token)`` entry."""
    deps = getattr(router, "dependencies", [])
    assert any(
        getattr(d, "dependency", None) is verify_bearer_token for d in deps
    ), f"router '{name}' is missing Depends(verify_bearer_token)"


def test_health_router_is_intentionally_unauthenticated() -> None:
    """Health endpoints must stay open even when API key is configured."""
    deps = getattr(health_router.router, "dependencies", [])
    assert not any(
        getattr(d, "dependency", None) is verify_bearer_token for d in deps
    ), "health router should NOT carry verify_bearer_token — it must stay open"


# ---------------------------------------------------------------------------
# Behavioral layer
# ---------------------------------------------------------------------------


def _make_stub_app(router_under_test: object) -> FastAPI:
    """Mount a stub endpoint under a clone of the router's dependency stack.

    We build a fresh ``APIRouter(dependencies=...)`` that mirrors the router
    under test, then attach only the stub endpoint to it. This isolates the
    dependency contract from each router's actual path table (which would
    otherwise match stub paths like ``/{job_id}`` before ``/__authcheck``).
    """
    app = FastAPI()
    deps = list(getattr(router_under_test, "dependencies", []))
    stub_router = APIRouter(dependencies=deps)

    @stub_router.get("/__authcheck")
    async def _stub() -> dict[str, str]:
        return {"ok": "true"}

    app.include_router(stub_router)
    return app


@pytest.mark.parametrize("name,router", GATED_ROUTERS)
def test_gated_router_returns_401_without_header(
    monkeypatch: pytest.MonkeyPatch,
    reset_settings_cache: None,
    name: str,
    router: object,
) -> None:
    monkeypatch.setenv("API_KEY", "auth-test-key")
    client = TestClient(_make_stub_app(router))

    response = client.get("/__authcheck")

    assert (
        response.status_code == 401
    ), f"router '{name}' did not return 401 without Authorization header"


@pytest.mark.parametrize("name,router", GATED_ROUTERS)
def test_gated_router_returns_200_with_correct_bearer_header(
    monkeypatch: pytest.MonkeyPatch,
    reset_settings_cache: None,
    name: str,
    router: object,
) -> None:
    monkeypatch.setenv("API_KEY", "auth-test-key")
    client = TestClient(_make_stub_app(router))

    response = client.get(
        "/__authcheck", headers={"Authorization": "Bearer auth-test-key"}
    )

    assert (
        response.status_code == 200
    ), f"router '{name}' rejected the correct Bearer token"
    assert response.json() == {"ok": "true"}


def test_health_router_stays_open_when_key_is_set(
    monkeypatch: pytest.MonkeyPatch, reset_settings_cache: None
) -> None:
    """A real /health/ endpoint must respond 200 with no header even when key set."""
    monkeypatch.setenv("API_KEY", "auth-test-key")

    # Mount only the health router; /health/ does not require app.state.
    app = FastAPI()
    app.include_router(health_router.router, prefix="/health")
    client = TestClient(app)

    response = client.get("/health/")

    assert response.status_code == 200
