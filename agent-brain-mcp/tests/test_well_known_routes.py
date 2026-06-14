"""Unauthenticated-200 + mount-outside-middleware acceptance tests (Phase 66 Plan 02).

Verifies ROADMAP SC#1, SC#2, SC#3 — the three Phase 66 success criteria:

  SC#1: GET /.well-known/oauth-protected-resource returns 200 with RFC 9728 fields
  SC#2: OASM code_challenge_methods_supported == ["S256"] (client-abort guard)
  SC#3: Well-known routes precede /mcp Mount (mount-order contract, Risk 3)

ALL requests are made WITHOUT an Authorization header — the discovery-first
contract requires these endpoints to be unconditionally reachable.

SURVIVES PHASE 67
-----------------
When Phase 67 adds RequireAuthMiddleware wrapping the /mcp Mount, this test
file must STILL pass without modification. The mount-order proof (test class
``TestMountOrderContract``) asserts that all three well-known Routes appear
at a lower index than the ``/mcp`` Mount in the Starlette app's ``.routes``
list — which means they are evaluated BEFORE the Mount and OUTSIDE any
future middleware scope wrapped around that Mount.

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"Mount-Order Constraint (Critical)" (Risk 3)
  §"Discovery-First Contract"

Phase 66 Plan 02 plan: .planning/phases/66-.../66-02-PLAN.md
  Task 3 acceptance criteria.
"""

from __future__ import annotations

from collections.abc import Generator

import httpx
import pytest
from starlette.routing import Mount
from starlette.testclient import TestClient

from agent_brain_mcp.http import (
    OASM_PATH,
    PRM_PATH,
    PRM_PATH_SUFFIXED,
    build_asgi_app,
)
from agent_brain_mcp.server import build_server

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_test_client() -> tuple[TestClient, object]:
    """Build a Starlette TestClient over build_asgi_app() with a mock backend.

    Returns:
        (client, backend_httpx_client) — caller can close backend_httpx_client
        in teardown if desired.
    """
    backend_client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"detail": "test-stub"})
        ),
        base_url="http://test-agent-brain",
    )
    server, _ = build_server(backend_client)
    app = build_asgi_app(server)
    client = TestClient(app, raise_server_exceptions=True)
    return client, backend_client


# ---------------------------------------------------------------------------
# Autouse fixture: isolate auth env vars so the dev shell doesn't leak in
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_auth_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Clear OAuth env vars before every test in this module.

    Prevents dev-shell values of AGENT_BRAIN_AUTH / AGENT_BRAIN_OAUTH_RESOURCE /
    AGENT_BRAIN_OAUTH_ISSUER from leaking into tests that assume the default
    (none) mode.

    Note: Tests that specifically set these vars (e.g. the startup-gate test)
    use monkeypatch.setenv INSIDE the test — this fixture only clears them
    BEFORE the test body runs.
    """
    for var in (
        "AGENT_BRAIN_AUTH",
        "AGENT_BRAIN_OAUTH_RESOURCE",
        "AGENT_BRAIN_OAUTH_ISSUER",
    ):
        monkeypatch.delenv(var, raising=False)
    yield


# ---------------------------------------------------------------------------
# SC#1: PRM base path returns 200 with RFC 9728 fields (no auth header)
# ---------------------------------------------------------------------------


class TestPrmBasePathUnauthenticated:
    """GET /.well-known/oauth-protected-resource (no auth header) → 200 RFC 9728.

    Covers ROADMAP SC#1.
    """

    def test_prm_returns_200_no_auth_header(self) -> None:
        """PRM endpoint returns HTTP 200 without any Authorization header."""
        client, _ = _make_test_client()
        response = client.get(PRM_PATH)
        assert response.status_code == 200

    def test_prm_content_type_is_json(self) -> None:
        """PRM response must have JSON content-type."""
        client, _ = _make_test_client()
        response = client.get(PRM_PATH)
        assert "application/json" in response.headers.get("content-type", "")

    def test_prm_has_resource_field(self) -> None:
        """PRM JSON must have the ``resource`` field (RFC 9728 §3.2 required)."""
        client, _ = _make_test_client()
        data = client.get(PRM_PATH).json()
        assert "resource" in data

    def test_prm_has_authorization_servers_field(self) -> None:
        """PRM JSON must have ``authorization_servers`` (RFC 9728 §3.2 required)."""
        client, _ = _make_test_client()
        data = client.get(PRM_PATH).json()
        assert "authorization_servers" in data

    def test_prm_authorization_servers_is_non_empty_list(self) -> None:
        """PRM ``authorization_servers`` must be a non-empty JSON array."""
        client, _ = _make_test_client()
        data = client.get(PRM_PATH).json()
        assert isinstance(data["authorization_servers"], list)
        assert len(data["authorization_servers"]) >= 1

    def test_prm_has_scopes_supported_field(self) -> None:
        """PRM JSON must have ``scopes_supported`` (RFC 9728 §3.2 required)."""
        client, _ = _make_test_client()
        data = client.get(PRM_PATH).json()
        assert "scopes_supported" in data

    def test_prm_scopes_supported_contains_four_agent_brain_scopes(self) -> None:
        """PRM ``scopes_supported`` must contain all 4 agent-brain:* scopes."""
        client, _ = _make_test_client()
        data = client.get(PRM_PATH).json()
        scopes = data["scopes_supported"]
        assert "agent-brain:read" in scopes
        assert "agent-brain:index" in scopes
        assert "agent-brain:admin" in scopes
        assert "agent-brain:subscribe" in scopes

    def test_prm_resource_field_is_string(self) -> None:
        """PRM ``resource`` must be a string URI."""
        client, _ = _make_test_client()
        data = client.get(PRM_PATH).json()
        assert isinstance(data["resource"], str)
        assert len(data["resource"]) > 0


# ---------------------------------------------------------------------------
# SC#1 (variant): PRM path-suffixed returns SAME document (RFC 9728 resource-
# path-insertion — both paths serve the same document byte-for-byte)
# ---------------------------------------------------------------------------


class TestPrmPathSuffixedReturnsIdenticalDocument:
    """GET /.well-known/oauth-protected-resource/mcp returns the SAME document.

    RFC 9728 §3.3 (resource-path-insertion) states that the path-suffixed
    variant must return the same Protected Resource Metadata document as the
    base path. Byte-identical JSON comparison is the acceptance bar.
    """

    def test_prm_suffixed_returns_200_no_auth_header(self) -> None:
        """Path-suffixed PRM endpoint returns HTTP 200 without Authorization header."""
        client, _ = _make_test_client()
        response = client.get(PRM_PATH_SUFFIXED)
        assert response.status_code == 200

    def test_prm_suffixed_matches_base_path_document(self) -> None:
        """Path-suffixed PRM must return the byte-identical JSON document.

        Both routes point to the same handler (oauth_protected_resource) so
        the same config-derived document is returned for both paths.
        """
        client, _ = _make_test_client()
        base_doc = client.get(PRM_PATH).json()
        suffixed_doc = client.get(PRM_PATH_SUFFIXED).json()
        assert base_doc == suffixed_doc

    def test_prm_suffixed_has_required_fields(self) -> None:
        """Path-suffixed PRM document has all required RFC 9728 §3.2 fields."""
        client, _ = _make_test_client()
        data = client.get(PRM_PATH_SUFFIXED).json()
        assert "resource" in data
        assert "authorization_servers" in data
        assert "scopes_supported" in data


# ---------------------------------------------------------------------------
# SC#2: OASM returns 200 with RFC 8414 fields + code_challenge_methods == S256
# ---------------------------------------------------------------------------


class TestOasmUnauthenticated:
    """GET /.well-known/oauth-authorization-server (no auth header) → 200 RFC 8414.

    Covers ROADMAP SC#2 — code_challenge_methods_supported == ["S256"] is the
    critical field. Compliant MCP SDK clients abort the OAuth dance silently
    if this field is absent or empty.
    """

    def test_oasm_returns_200_no_auth_header(self) -> None:
        """OASM endpoint returns HTTP 200 without any Authorization header."""
        client, _ = _make_test_client()
        response = client.get(OASM_PATH)
        assert response.status_code == 200

    def test_oasm_content_type_is_json(self) -> None:
        """OASM response must have JSON content-type."""
        client, _ = _make_test_client()
        response = client.get(OASM_PATH)
        assert "application/json" in response.headers.get("content-type", "")

    def test_oasm_code_challenge_methods_is_exactly_s256(self) -> None:
        """OASM ``code_challenge_methods_supported`` MUST be exactly ``["S256"]``.

        This is the non-negotiable PKCE field. Presence of "S256" and absence
        of "plain" are both required by the MCP Authorization spec (2025-11-25).
        Absence or wrong value causes compliant clients to abort silently.
        """
        client, _ = _make_test_client()
        data = client.get(OASM_PATH).json()
        assert data["code_challenge_methods_supported"] == ["S256"]

    def test_oasm_has_issuer_field(self) -> None:
        """OASM must have ``issuer`` field (RFC 8414 §2 required)."""
        client, _ = _make_test_client()
        data = client.get(OASM_PATH).json()
        assert "issuer" in data
        assert isinstance(data["issuer"], str)

    def test_oasm_has_authorization_endpoint(self) -> None:
        """OASM must have ``authorization_endpoint`` (forward-ref to Phase 67)."""
        client, _ = _make_test_client()
        data = client.get(OASM_PATH).json()
        assert "authorization_endpoint" in data

    def test_oasm_has_token_endpoint(self) -> None:
        """OASM must have ``token_endpoint`` (forward-ref to Phase 67)."""
        client, _ = _make_test_client()
        data = client.get(OASM_PATH).json()
        assert "token_endpoint" in data

    def test_oasm_has_registration_endpoint(self) -> None:
        """OASM must have ``registration_endpoint`` (forward-ref to Phase 67)."""
        client, _ = _make_test_client()
        data = client.get(OASM_PATH).json()
        assert "registration_endpoint" in data

    def test_oasm_has_jwks_uri(self) -> None:
        """OASM must have ``jwks_uri`` (forward-ref to Phase 67)."""
        client, _ = _make_test_client()
        data = client.get(OASM_PATH).json()
        assert "jwks_uri" in data

    def test_oasm_grant_types_supported(self) -> None:
        """OASM must advertise authorization_code and refresh_token."""
        client, _ = _make_test_client()
        data = client.get(OASM_PATH).json()
        assert data["grant_types_supported"] == [
            "authorization_code",
            "refresh_token",
        ]

    def test_oasm_response_types_supported(self) -> None:
        """OASM must advertise ``code`` response type."""
        client, _ = _make_test_client()
        data = client.get(OASM_PATH).json()
        assert data["response_types_supported"] == ["code"]

    def test_oasm_authorization_endpoint_endswith_authorize(self) -> None:
        """authorization_endpoint must end with /authorize."""
        client, _ = _make_test_client()
        data = client.get(OASM_PATH).json()
        assert str(data["authorization_endpoint"]).endswith("/authorize")

    def test_oasm_token_endpoint_endswith_token(self) -> None:
        """token_endpoint must end with /token."""
        client, _ = _make_test_client()
        data = client.get(OASM_PATH).json()
        assert str(data["token_endpoint"]).endswith("/token")


# ---------------------------------------------------------------------------
# SC#3: Mount-order proof — well-known routes precede /mcp Mount in .routes
# (Survives Phase 67: see module-level docstring)
# ---------------------------------------------------------------------------


class TestMountOrderContract:
    """Prove well-known routes precede the /mcp Mount in build_asgi_app().routes.

    Survives Phase 67: when RequireAuthMiddleware wraps the /mcp Mount,
    these routes are already mounted earlier in the list / outside that wrap,
    so they keep returning 200 with no token. This is the discovery-first
    contract (design doc Risk 3).

    Rationale: Starlette evaluates routes in list order. Any Route entry
    that appears BEFORE a Mount will be matched first. Well-known Routes
    at index < mcp_mount_index are therefore evaluated before the /mcp
    Mount and are unaffected by any middleware wrapped around that Mount.
    """

    def _get_app_routes(self) -> list[object]:
        """Build the ASGI app and return its .routes list."""
        backend_client = httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"detail": "test-stub"})
            ),
            base_url="http://test-agent-brain",
        )
        server, _ = build_server(backend_client)
        app = build_asgi_app(server)
        return list(app.routes)

    def _find_mcp_mount_index(self, routes: list[object]) -> int:
        """Return the index of the /mcp Mount in routes, or raise AssertionError."""
        for i, route in enumerate(routes):
            if isinstance(route, Mount) and getattr(route, "path", None) == "/mcp":
                return i
        raise AssertionError("No Mount('/mcp') found in build_asgi_app().routes")

    def _find_route_index(self, routes: list[object], path: str) -> int:
        """Return the index of a route with the given path, or raise AssertionError."""
        for i, route in enumerate(routes):
            route_path = getattr(route, "path", None)
            if route_path == path:
                return i
        raise AssertionError(
            f"No route with path {path!r} found in build_asgi_app().routes"
        )

    def test_prm_path_precedes_mcp_mount(self) -> None:
        """PRM base-path Route must appear before the /mcp Mount in .routes.

        Survives Phase 67: when RequireAuthMiddleware wraps the /mcp Mount,
        these routes are already mounted earlier in the list / outside that
        wrap, so they keep returning 200 with no token. This is the
        discovery-first contract (design doc Risk 3).
        """
        routes = self._get_app_routes()
        prm_index = self._find_route_index(routes, PRM_PATH)
        mcp_index = self._find_mcp_mount_index(routes)
        assert prm_index < mcp_index, (
            f"PRM route at index {prm_index} must precede /mcp Mount at "
            f"index {mcp_index} (mount-order contract, design doc Risk 3)"
        )

    def test_prm_suffixed_path_precedes_mcp_mount(self) -> None:
        """PRM path-suffixed Route must appear before the /mcp Mount."""
        routes = self._get_app_routes()
        prm_sfx_index = self._find_route_index(routes, PRM_PATH_SUFFIXED)
        mcp_index = self._find_mcp_mount_index(routes)
        assert prm_sfx_index < mcp_index, (
            f"PRM-suffixed route at index {prm_sfx_index} must precede /mcp Mount "
            f"at index {mcp_index} (mount-order contract)"
        )

    def test_oasm_path_precedes_mcp_mount(self) -> None:
        """OASM Route must appear before the /mcp Mount in .routes."""
        routes = self._get_app_routes()
        oasm_index = self._find_route_index(routes, OASM_PATH)
        mcp_index = self._find_mcp_mount_index(routes)
        assert oasm_index < mcp_index, (
            f"OASM route at index {oasm_index} must precede /mcp Mount at "
            f"index {mcp_index} (mount-order contract)"
        )

    def test_all_well_known_routes_precede_mcp_mount(self) -> None:
        """ALL three well-known Routes must precede the /mcp Mount (combined check)."""
        routes = self._get_app_routes()
        mcp_index = self._find_mcp_mount_index(routes)
        for path in (PRM_PATH, PRM_PATH_SUFFIXED, OASM_PATH):
            idx = self._find_route_index(routes, path)
            assert idx < mcp_index, (
                f"Route {path!r} at index {idx} must precede /mcp Mount at "
                f"index {mcp_index} (mount-order contract, design doc Risk 3)"
            )

    def test_mcp_mount_is_present_as_mount_type(self) -> None:
        """The /mcp entry must be a Starlette Mount (not a Route)."""
        routes = self._get_app_routes()
        mcp_index = self._find_mcp_mount_index(routes)
        assert isinstance(routes[mcp_index], Mount)


# ---------------------------------------------------------------------------
# Startup-gate-at-build proof (Plan 01 gate fires during build_asgi_app())
# ---------------------------------------------------------------------------


class TestStartupGateAtBuildTime:
    """build_asgi_app() raises SystemExit(2) on oauth-mode misconfig at build time.

    The Plan 01 gate (check_auth_startup_gate) is wired into the TOP of
    build_asgi_app(), so misconfigured oauth mode exits before any route is
    constructed.
    """

    def test_build_asgi_app_exits_2_on_oauth_with_no_resource(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """build_asgi_app() raises SystemExit(2) when AGENT_BRAIN_AUTH=oauth
        and AGENT_BRAIN_OAUTH_RESOURCE is not set.

        The autouse fixture already cleared the env vars; we set only the
        ones this test needs.
        """
        monkeypatch.setenv("AGENT_BRAIN_AUTH", "oauth")
        # AGENT_BRAIN_OAUTH_RESOURCE intentionally not set (already cleared)

        backend_client = httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"detail": "test-stub"})
            ),
            base_url="http://test-agent-brain",
        )
        server, _ = build_server(backend_client)

        with pytest.raises(SystemExit) as exc_info:
            build_asgi_app(server)

        assert exc_info.value.code == 2, (
            f"Expected SystemExit(2) on oauth+no-resource misconfig, "
            f"got SystemExit({exc_info.value.code!r})"
        )

    def test_build_asgi_app_succeeds_in_none_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """build_asgi_app() does NOT exit when AGENT_BRAIN_AUTH is unset.

        Default mode is none — no resource URI required.
        """
        # env vars already cleared by autouse fixture — unset → none mode
        backend_client = httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"detail": "test-stub"})
            ),
            base_url="http://test-agent-brain",
        )
        server, _ = build_server(backend_client)
        # Must not raise
        app = build_asgi_app(server)
        assert app is not None

    def test_build_asgi_app_succeeds_with_oauth_and_resource_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """build_asgi_app() does NOT exit when oauth mode has a valid resource URI."""
        monkeypatch.setenv("AGENT_BRAIN_AUTH", "oauth")
        monkeypatch.setenv(
            "AGENT_BRAIN_OAUTH_RESOURCE", "https://mcp.example.com/mcp"
        )
        backend_client = httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"detail": "test-stub"})
            ),
            base_url="http://test-agent-brain",
        )
        server, _ = build_server(backend_client)
        # Must not raise
        app = build_asgi_app(server)
        assert app is not None

    def test_prm_returns_resource_from_env_when_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PRM ``resource`` field reflects AGENT_BRAIN_OAUTH_RESOURCE when set."""
        canonical_resource = "https://mcp.example.com/mcp"
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", canonical_resource)
        client, _ = _make_test_client()
        data = client.get(PRM_PATH).json()
        assert data["resource"] == canonical_resource

    def test_oasm_reflects_issuer_env_when_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OASM ``issuer`` field reflects AGENT_BRAIN_OAUTH_ISSUER when set."""
        issuer = "https://auth.example.com"
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_ISSUER", issuer)
        client, _ = _make_test_client()
        data = client.get(OASM_PATH).json()
        assert data["issuer"] == issuer
        assert str(data["authorization_endpoint"]).startswith(issuer)
