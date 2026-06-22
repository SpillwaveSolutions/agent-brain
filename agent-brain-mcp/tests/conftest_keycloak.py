"""Keycloak-tier pytest fixtures for agent-brain-mcp integration tests.

These fixtures require a running Keycloak container bootstrapped by
scripts/keycloak_bootstrap.sh. They are NOT auto-loaded by pytest (only files
named exactly conftest.py are auto-discovered). The names are bridged into
tests/conftest.py via an explicit import so pytest fixture discovery works.

Keycloak URL patterns (realm = agent-brain):
  JWKS:          {KC_BASE}/realms/agent-brain/protocol/openid-connect/certs
  Token:         {KC_BASE}/realms/agent-brain/protocol/openid-connect/token
  Introspection: {KC_BASE}/realms/agent-brain/protocol/openid-connect/token/introspect
  OASM:          {KC_BASE}/realms/agent-brain/.well-known/openid-configuration
  iss claim:     {KC_BASE}/realms/agent-brain  (Pitfall 7 — includes realm path)

Health endpoint is on management port 9000:
  http://localhost:9000/health/ready (Pitfall 3).
"""

from __future__ import annotations

import os
from collections.abc import Callable

import httpx
import pytest

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_KC_BASE = os.environ.get("KEYCLOAK_URL", "http://localhost:8080")
_REALM = "agent-brain"
_RESOURCE = os.environ.get("AGENT_BRAIN_OAUTH_RESOURCE", "http://localhost:8000")
_ISSUER = f"{_KC_BASE}/realms/{_REALM}"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def keycloak_available() -> None:
    """Session fixture that skips keycloak tests when no container is running.

    Performs a fast reachability check against the Keycloak OASM endpoint.
    Skips the entire session's keycloak-marked tests (clean skip, no failure)
    when Keycloak is not available — mirrors the @pytest.mark.postgres
    skip convention used in the main test suite.

    Returns:
        None — consumed by keycloak-marked tests as a dependency.
    """
    url = f"{_ISSUER}/.well-known/openid-configuration"
    try:
        resp = httpx.get(url, timeout=5.0)
        resp.raise_for_status()
    except Exception as exc:
        pytest.skip(
            f"Keycloak not available at {url} — {exc}. "
            "Start Keycloak via scripts/keycloak_bootstrap.sh "
            "or run `task mcp:keycloak`."
        )


@pytest.fixture
def keycloak_token_for_scope(keycloak_available: None) -> Callable[[str], str]:
    """Factory fixture that mints a Keycloak access token for a given scope string.

    Uses the Resource Owner Password Credentials (direct-grant) flow to obtain
    a real Keycloak-issued JWT without browser PKCE. This is intentional for
    headless CI token minting (Open Q3 from 70-RESEARCH.md — acceptable for test-only
    direct-grant; not exposed to production users).

    The returned callable accepts a scope string and returns the access_token string.

    Args:
        keycloak_available: Session fixture that skips if Keycloak is unreachable.

    Returns:
        A callable ``_mint(scope: str) -> str`` that POSTs to the Keycloak
        token endpoint and returns the access_token string.
    """

    def _mint(scope: str) -> str:
        """Mint a Keycloak token with the given scope.

        Args:
            scope: Space-separated scope string (e.g. "openid agent-brain:read").

        Returns:
            The raw access_token string from Keycloak.

        Raises:
            httpx.HTTPStatusError: If the token endpoint returns a non-2xx status.
        """
        resp = httpx.post(
            f"{_ISSUER}/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "agent-brain-mcp",
                "username": "testuser",
                "password": "testpass",
                "scope": scope,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        return str(resp.json()["access_token"])

    return _mint


@pytest.fixture
def keycloak_access_token(keycloak_token_for_scope: Callable[[str], str]) -> str:
    """Mint a Keycloak access token with the default scope 'openid agent-brain:read'.

    Delegates to keycloak_token_for_scope to avoid duplication while keeping
    both fixture names exported for caller convenience.

    Args:
        keycloak_token_for_scope: Factory fixture for scoped token minting.

    Returns:
        The raw access_token string from Keycloak.
    """
    return keycloak_token_for_scope("openid agent-brain:read")
