"""Acceptance tests for per-tool OAuth scope enforcement (Phase 68 Plan 02, OAUTH-06).

Covers:
  - LEVEL A: decision-logic unit tests on ScopeEnforcementMiddleware._required_scope
    and _send_403, and on server.py _enforce_scope / call_tool / get_prompt dispatch.
  - LEVEL B: real HTTP 403 via Starlette TestClient — the only proof of SC#2/SC#3
    end-to-end (NOT a JSON-RPC error in a 200).
  - SC#1: read-only token → read tools succeed (guard passes them).
  - SC#2: read-only token → index tools → 403 insufficient_scope.
  - SC#3: read-only token → admin tools → 403 insufficient_scope.
  - Resource/subscribe/prompt gates.
  - Mode-gating: none/basic → guard is a no-op.

All tests use mint_access_token for minimal-scope token minting.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from typing import Any

import pytest
from starlette.testclient import TestClient

from agent_brain_mcp.http import (
    ScopeEnforcementMiddleware,
    build_asgi_app,
)
from agent_brain_mcp.oauth.scopes import InsufficientScopeError
from agent_brain_mcp.server import _enforce_scope, build_server
from agent_brain_mcp.tools import TOOL_SCOPE_REQUIREMENTS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RESOURCE = "https://mcp.example.com/mcp"
_ISSUER = "https://mcp.example.com"
_CLIENT_ID = "scope-test-client"

# Tool classifications from TOOL_SCOPE_REQUIREMENTS
_READ_TOOLS = [
    name
    for name, scope in TOOL_SCOPE_REQUIREMENTS.items()
    if scope == "agent-brain:read"
]
_INDEX_TOOLS = [
    name
    for name, scope in TOOL_SCOPE_REQUIREMENTS.items()
    if scope == "agent-brain:index"
]
_ADMIN_TOOLS = [
    name
    for name, scope in TOOL_SCOPE_REQUIREMENTS.items()
    if scope == "agent-brain:admin"
]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _oauth_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Set AGENT_BRAIN_AUTH=oauth + resource/issuer env vars for all tests."""
    monkeypatch.setenv("AGENT_BRAIN_AUTH", "oauth")
    monkeypatch.setenv("AGENT_BRAIN_OAUTH_RESOURCE", _RESOURCE)
    monkeypatch.setenv("AGENT_BRAIN_OAUTH_ISSUER", _ISSUER)
    yield


@pytest.fixture()
def signing_key() -> Any:
    """Return an isolated signing key (reset singleton for test isolation)."""
    import agent_brain_mcp.oauth.keys as _keys_mod

    _keys_mod._signing_key_singleton = None  # noqa: SLF001
    from agent_brain_mcp.oauth.keys import get_or_create_signing_key

    return get_or_create_signing_key()


@pytest.fixture()
def app_client(signing_key: Any) -> TestClient:
    """Build a TestClient over the full ASGI app in oauth mode."""
    from conftest import make_httpx_client

    backend_client = make_httpx_client()
    server, _ = build_server(backend_client)
    app = build_asgi_app(server)
    return TestClient(app, raise_server_exceptions=False)


def _mint(signing_key: Any, scopes: list[str]) -> str:
    """Mint a minimal-scope test token."""
    from agent_brain_mcp.oauth.tokens import mint_access_token

    return mint_access_token(
        client_id=_CLIENT_ID,
        scopes=scopes,
        resource=_RESOURCE,
        signing_key=signing_key,
        issuer=_ISSUER,
    )


def _mcp_post(
    client: TestClient,
    token: str,
    method: str,
    params: dict[str, Any] | None = None,
) -> Any:
    """Send a JSON-RPC POST /mcp request with a Bearer token."""
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        body["params"] = params
    return client.post(
        "/mcp",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )


# ---------------------------------------------------------------------------
# LEVEL A: ScopeEnforcementMiddleware._required_scope unit tests
# ---------------------------------------------------------------------------


class TestRequiredScopeMapping:
    """Unit tests for ScopeEnforcementMiddleware._required_scope decision logic."""

    @pytest.fixture()
    def guard(self) -> ScopeEnforcementMiddleware:
        """Create a guard instance (app not used in _required_scope)."""
        return ScopeEnforcementMiddleware(object(), resource_metadata_url=_RESOURCE)

    def test_tools_call_admin_tool_returns_admin_scope(
        self, guard: ScopeEnforcementMiddleware
    ) -> None:
        """tools/call for cancel_job -> agent-brain:admin."""
        import json

        body = json.dumps(
            {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "cancel_job"}}
        ).encode()
        assert guard._required_scope(body) == "agent-brain:admin"

    def test_tools_call_index_tool_returns_index_scope(
        self, guard: ScopeEnforcementMiddleware
    ) -> None:
        """tools/call for index_folder -> agent-brain:index."""
        import json

        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "index_folder"},
            }
        ).encode()
        assert guard._required_scope(body) == "agent-brain:index"

    def test_tools_call_read_tool_returns_read_scope(
        self, guard: ScopeEnforcementMiddleware
    ) -> None:
        """tools/call for list_folders -> agent-brain:read."""
        import json

        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "list_folders"},
            }
        ).encode()
        assert guard._required_scope(body) == "agent-brain:read"

    def test_resources_read_returns_read_scope(
        self, guard: ScopeEnforcementMiddleware
    ) -> None:
        """resources/read -> agent-brain:read."""
        import json

        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "resources/read",
                "params": {"uri": "corpus://status"},
            }
        ).encode()
        assert guard._required_scope(body) == "agent-brain:read"

    def test_resources_subscribe_returns_subscribe_scope(
        self, guard: ScopeEnforcementMiddleware
    ) -> None:
        """resources/subscribe -> agent-brain:subscribe."""
        import json

        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "resources/subscribe",
                "params": {"uri": "corpus://status"},
            }
        ).encode()
        assert guard._required_scope(body) == "agent-brain:subscribe"

    def test_prompts_get_returns_read_scope(
        self, guard: ScopeEnforcementMiddleware
    ) -> None:
        """prompts/get -> agent-brain:read."""
        import json

        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "prompts/get",
                "params": {"name": "explain-architecture"},
            }
        ).encode()
        assert guard._required_scope(body) == "agent-brain:read"

    def test_initialize_returns_none(self, guard: ScopeEnforcementMiddleware) -> None:
        """initialize -> None (no scope check)."""
        import json

        body = json.dumps(
            {"jsonrpc": "2.0", "method": "initialize", "params": {}}
        ).encode()
        assert guard._required_scope(body) is None

    def test_tools_list_returns_none(self, guard: ScopeEnforcementMiddleware) -> None:
        """tools/list -> None (no scope check)."""
        import json

        body = json.dumps({"jsonrpc": "2.0", "method": "tools/list"}).encode()
        assert guard._required_scope(body) is None

    def test_ping_returns_none(self, guard: ScopeEnforcementMiddleware) -> None:
        """ping -> None (no scope check)."""
        import json

        body = json.dumps({"jsonrpc": "2.0", "method": "ping"}).encode()
        assert guard._required_scope(body) is None

    def test_unknown_tool_name_returns_none_not_403(
        self, guard: ScopeEnforcementMiddleware
    ) -> None:
        """Unknown tool name -> None (NOT a 403; let dispatch return INVALID_PARAMS)."""
        import json

        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "no_such_tool_at_all"},
            }
        ).encode()
        assert guard._required_scope(body) is None

    def test_malformed_body_returns_none(
        self, guard: ScopeEnforcementMiddleware
    ) -> None:
        """Unparseable body -> None (pass through)."""
        assert guard._required_scope(b"not json {{{") is None

    def test_empty_body_returns_none(self, guard: ScopeEnforcementMiddleware) -> None:
        """Empty body -> None (pass through)."""
        assert guard._required_scope(b"") is None

    def test_json_array_body_returns_none(
        self, guard: ScopeEnforcementMiddleware
    ) -> None:
        """JSON-RPC batch (list) -> None (single-request scope check only)."""
        import json

        body = json.dumps(
            [
                {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "cancel_job"},
                }
            ]
        ).encode()
        assert guard._required_scope(body) is None


# ---------------------------------------------------------------------------
# LEVEL A: 403 emission unit test
# ---------------------------------------------------------------------------


class TestSend403Emission:
    """Unit tests for ScopeEnforcementMiddleware._send_403."""

    def test_send_403_emits_correct_status_and_headers(self) -> None:
        """_send_403 emits status=403 with the insufficient_scope WWW-Auth header."""
        guard = ScopeEnforcementMiddleware(object(), resource_metadata_url=_RESOURCE)
        sent: list[dict[str, Any]] = []

        async def fake_send(message: dict[str, Any]) -> None:
            sent.append(message)

        asyncio.run(guard._send_403(fake_send, required="agent-brain:admin"))

        assert len(sent) == 2
        start = sent[0]
        assert start["type"] == "http.response.start"
        assert start["status"] == 403

        # Extract www-authenticate header value
        headers = {k.decode(): v.decode() for k, v in start["headers"]}
        www = headers.get("www-authenticate", "")
        assert 'error="insufficient_scope"' in www
        assert 'scope="agent-brain:admin"' in www
        assert "resource_metadata=" in www
        assert _RESOURCE in www

    def test_send_403_body_is_json_insufficient_scope(self) -> None:
        """_send_403 body JSON contains error=insufficient_scope."""
        import json

        guard = ScopeEnforcementMiddleware(object(), resource_metadata_url=_RESOURCE)
        sent: list[dict[str, Any]] = []

        async def fake_send(message: dict[str, Any]) -> None:
            sent.append(message)

        asyncio.run(guard._send_403(fake_send, required="agent-brain:index"))
        body_msg = sent[1]
        payload = json.loads(body_msg["body"])
        assert payload["error"] == "insufficient_scope"
        assert "agent-brain:index" in payload["error_description"]


# ---------------------------------------------------------------------------
# LEVEL A: server.py _enforce_scope defense-in-depth unit tests
# ---------------------------------------------------------------------------


class TestEnforceScopeHelper:
    """Unit tests for server.py _enforce_scope in-process guard."""

    def test_enforce_scope_raises_in_oauth_mode_with_insufficient_scope(
        self, monkeypatch: pytest.MonkeyPatch, signing_key: Any
    ) -> None:
        """_enforce_scope raises InsufficientScopeError (read token, admin required)."""
        from unittest.mock import MagicMock

        # signing_key fixture resets the singleton so the test is isolated.
        # We only need it to ensure the module-level env fixtures are active.
        del signing_key

        # Build a fake user with scopes=["agent-brain:read"]
        fake_user = MagicMock()
        fake_user.scopes = ["agent-brain:read"]

        # Build a fake request with .user
        fake_request = MagicMock()
        fake_request.user = fake_user

        # Build a fake server whose request_context.request returns fake_request
        fake_ctx = MagicMock()
        fake_ctx.request = fake_request
        fake_server = MagicMock()
        fake_server.request_context = fake_ctx

        with pytest.raises(InsufficientScopeError) as exc_info:
            _enforce_scope(fake_server, "agent-brain:admin")

        assert exc_info.value.required == "agent-brain:admin"

    def test_enforce_scope_passes_for_sufficient_scope(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_enforce_scope does NOT raise when token has the required scope."""
        from unittest.mock import MagicMock

        fake_user = MagicMock()
        fake_user.scopes = ["agent-brain:admin"]
        fake_request = MagicMock()
        fake_request.user = fake_user
        fake_ctx = MagicMock()
        fake_ctx.request = fake_request
        fake_server = MagicMock()
        fake_server.request_context = fake_ctx

        # Should not raise
        _enforce_scope(fake_server, "agent-brain:admin")

    def test_enforce_scope_noop_in_none_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_enforce_scope returns without raising in none mode (no token scopes)."""
        monkeypatch.setenv("AGENT_BRAIN_AUTH", "none")
        from unittest.mock import MagicMock

        fake_server = MagicMock()
        # Even with no user/scopes, none mode should pass through
        _enforce_scope(fake_server, "agent-brain:admin")

    def test_enforce_scope_noop_in_basic_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_enforce_scope returns without raising in basic mode."""
        monkeypatch.setenv("AGENT_BRAIN_AUTH", "basic")
        from unittest.mock import MagicMock

        fake_server = MagicMock()
        _enforce_scope(fake_server, "agent-brain:admin")

    def test_enforce_scope_lookup_error_on_no_context(self) -> None:
        """_enforce_scope with LookupError on request_context -> deny (oauth mode)."""
        from unittest.mock import MagicMock, PropertyMock

        fake_server = MagicMock()
        # request_context.request raises LookupError (in-process, no active session)
        type(fake_server).request_context = PropertyMock(side_effect=LookupError)

        # oauth mode + no user scopes → require_scope("agent-brain:admin", []) raises
        with pytest.raises(InsufficientScopeError) as exc_info:
            _enforce_scope(fake_server, "agent-brain:admin")

        assert exc_info.value.required == "agent-brain:admin"


# ---------------------------------------------------------------------------
# LEVEL B: Real HTTP 403 via Starlette TestClient
# ---------------------------------------------------------------------------


class TestScopeEnforcementHTTP:
    """Real HTTP 403 end-to-end tests via Starlette TestClient (SC#1/SC#2/SC#3)."""

    def test_sc2_read_token_on_index_tool_returns_403(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """SC#2: read-only token calling index_folder → HTTP 403 (NOT 200, NOT 401)."""
        token = _mint(signing_key, ["agent-brain:read"])
        response = _mcp_post(
            app_client,
            token,
            "tools/call",
            {"name": "index_folder", "arguments": {"folder_path": "/tmp/test"}},
        )
        assert (
            response.status_code == 403
        ), f"Expected 403 but got {response.status_code}: {response.text}"
        www = response.headers.get("www-authenticate", "")
        assert 'error="insufficient_scope"' in www, f"WWW-Authenticate missing: {www!r}"
        assert 'scope="agent-brain:index"' in www, f"scope field missing: {www!r}"

    def test_sc3_read_token_on_admin_tool_returns_403(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """SC#3: read-only token calling cancel_job → HTTP 403 (NOT 200, NOT 401)."""
        token = _mint(signing_key, ["agent-brain:read"])
        response = _mcp_post(
            app_client,
            token,
            "tools/call",
            {"name": "cancel_job", "arguments": {"job_id": "job_abc", "confirm": True}},
        )
        assert (
            response.status_code == 403
        ), f"Expected 403 but got {response.status_code}: {response.text}"
        www = response.headers.get("www-authenticate", "")
        assert 'error="insufficient_scope"' in www, f"WWW-Authenticate missing: {www!r}"
        assert 'scope="agent-brain:admin"' in www, f"scope field missing: {www!r}"

    def test_sc3_read_token_on_remove_folder_returns_403(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """SC#3: read-only token calling remove_folder → HTTP 403."""
        token = _mint(signing_key, ["agent-brain:read"])
        response = _mcp_post(
            app_client,
            token,
            "tools/call",
            {
                "name": "remove_folder",
                "arguments": {"folder_path": "/tmp/test", "confirm": True},
            },
        )
        assert response.status_code == 403
        www = response.headers.get("www-authenticate", "")
        assert 'error="insufficient_scope"' in www
        assert 'scope="agent-brain:admin"' in www

    def test_sc3_read_token_on_clear_cache_returns_403(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """SC#3: read-only token calling clear_cache → HTTP 403."""
        token = _mint(signing_key, ["agent-brain:read"])
        response = _mcp_post(
            app_client,
            token,
            "tools/call",
            {"name": "clear_cache", "arguments": {"confirm": True}},
        )
        assert response.status_code == 403
        www = response.headers.get("www-authenticate", "")
        assert 'error="insufficient_scope"' in www
        assert 'scope="agent-brain:admin"' in www

    def test_sc2_read_token_on_add_documents_returns_403(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """SC#2: read-only token calling add_documents → HTTP 403."""
        token = _mint(signing_key, ["agent-brain:read"])
        response = _mcp_post(
            app_client,
            token,
            "tools/call",
            {"name": "add_documents", "arguments": {"paths": ["/tmp/file.py"]}},
        )
        assert response.status_code == 403
        www = response.headers.get("www-authenticate", "")
        assert 'error="insufficient_scope"' in www
        assert 'scope="agent-brain:index"' in www

    def test_sc2_read_token_on_inject_documents_returns_403(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """SC#2: read-only token calling inject_documents → HTTP 403."""
        token = _mint(signing_key, ["agent-brain:read"])
        response = _mcp_post(
            app_client,
            token,
            "tools/call",
            {
                "name": "inject_documents",
                "arguments": {
                    "folder_path": "/tmp/test",
                    "injector_script": "/tmp/enrich.py",
                },
            },
        )
        assert response.status_code == 403
        www = response.headers.get("www-authenticate", "")
        assert 'error="insufficient_scope"' in www
        assert 'scope="agent-brain:index"' in www

    def test_sc2_read_token_on_wait_for_job_returns_403(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """SC#2: read-only token calling wait_for_job → HTTP 403."""
        token = _mint(signing_key, ["agent-brain:read"])
        response = _mcp_post(
            app_client,
            token,
            "tools/call",
            {"name": "wait_for_job", "arguments": {"job_id": "job_abc"}},
        )
        assert response.status_code == 403
        www = response.headers.get("www-authenticate", "")
        assert 'error="insufficient_scope"' in www
        assert 'scope="agent-brain:index"' in www

    def test_403_not_401_insufficient_scope(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """Insufficient scope must be exactly 403, NOT 401 (step-up vs re-auth)."""
        token = _mint(signing_key, ["agent-brain:read"])
        response = _mcp_post(
            app_client,
            token,
            "tools/call",
            {"name": "cancel_job", "arguments": {"job_id": "job_abc", "confirm": True}},
        )
        # Must be 403, never 401
        assert response.status_code == 403
        assert response.status_code != 401

    def test_www_authenticate_scope_is_required_scope_not_token_scope(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """scope= in WWW-Authenticate names the REQUIRED scope, not the token's."""
        # Token has agent-brain:read; required is agent-brain:admin
        token = _mint(signing_key, ["agent-brain:read"])
        response = _mcp_post(
            app_client,
            token,
            "tools/call",
            {"name": "cancel_job", "arguments": {"job_id": "job_abc", "confirm": True}},
        )
        assert response.status_code == 403
        www = response.headers.get("www-authenticate", "")
        # Must have the REQUIRED scope (admin), not the token's scope (read)
        assert 'scope="agent-brain:admin"' in www
        assert 'scope="agent-brain:read"' not in www

    def test_www_authenticate_contains_resource_metadata(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """403 WWW-Authenticate must include resource_metadata for step-up discovery."""
        token = _mint(signing_key, ["agent-brain:read"])
        response = _mcp_post(
            app_client,
            token,
            "tools/call",
            {"name": "cancel_job", "arguments": {"job_id": "job_abc", "confirm": True}},
        )
        assert response.status_code == 403
        www = response.headers.get("www-authenticate", "")
        assert "resource_metadata=" in www

    def test_initialize_method_passes_through_without_scope_check(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """initialize does NOT get scope-checked — guard returns None for it."""
        # A read-only token must be able to initialize
        token = _mint(signing_key, ["agent-brain:read"])
        response = _mcp_post(
            app_client,
            token,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0.1"},
            },
        )
        # initialize must NOT return 403 (scope check disabled for this method)
        assert response.status_code != 403, (
            "initialize must not be scope-checked: "
            f"got {response.status_code}: {response.text}"
        )

    def test_unknown_tool_passes_through_to_dispatch_not_403(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """Unknown tool → guard passes; dispatch returns INVALID_PARAMS (JSON-RPC)."""
        token = _mint(signing_key, ["agent-brain:read"])
        response = _mcp_post(
            app_client,
            token,
            "tools/call",
            {"name": "no_such_tool_at_all", "arguments": {}},
        )
        # Guard must NOT 403 an unknown tool — it passes through
        assert (
            response.status_code != 403
        ), f"Unknown tool should not get 403 from guard, got {response.status_code}"


# ---------------------------------------------------------------------------
# LEVEL B: SC#1 — read token succeeds on read tools
# ---------------------------------------------------------------------------


class TestSC1ReadTokenOnReadTools:
    """SC#1: read-only token can call read tools and succeeds (guard passes them)."""

    def test_sc1_list_folders_with_read_token_passes_guard(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """SC#1: read token calling list_folders → guard passes (not 403/401)."""
        token = _mint(signing_key, ["agent-brain:read"])
        response = _mcp_post(
            app_client,
            token,
            "tools/call",
            {"name": "list_folders", "arguments": {}},
        )
        # The guard must NOT emit 403 for a read-scope tool with read token.
        # It may return 200 JSON-RPC success or a JSON-RPC error from dispatch,
        # but never 403 (guard passed) and never 401 (token is valid).
        assert response.status_code not in (401, 403), (
            f"list_folders with read token should not return {response.status_code}: "
            f"{response.text}"
        )

    @pytest.mark.parametrize("tool_name", _READ_TOOLS)
    def test_sc1_all_read_tools_pass_guard(
        self,
        app_client: TestClient,
        signing_key: Any,
        tool_name: str,
    ) -> None:
        """SC#1: read token calling ANY read tool → guard passes (not 403)."""
        token = _mint(signing_key, ["agent-brain:read"])
        response = _mcp_post(
            app_client,
            token,
            "tools/call",
            {"name": tool_name, "arguments": {}},
        )
        # Guard must NOT 403 a read tool with read token
        assert response.status_code != 403, (
            f"{tool_name} with read token returned 403 (scope guard error): "
            f"{response.text}"
        )
        assert (
            response.status_code != 401
        ), f"{tool_name} with valid read token returned 401: {response.text}"

    @pytest.mark.parametrize("tool_name", _INDEX_TOOLS)
    def test_sc2_all_index_tools_403_with_read_token(
        self,
        app_client: TestClient,
        signing_key: Any,
        tool_name: str,
    ) -> None:
        """SC#2: read token calling ANY index tool → 403 insufficient_scope."""
        token = _mint(signing_key, ["agent-brain:read"])
        response = _mcp_post(
            app_client,
            token,
            "tools/call",
            {"name": tool_name, "arguments": {}},
        )
        assert (
            response.status_code == 403
        ), f"{tool_name} with read token returned {response.status_code}, expected 403"
        www = response.headers.get("www-authenticate", "")
        assert 'error="insufficient_scope"' in www
        assert 'scope="agent-brain:index"' in www

    @pytest.mark.parametrize("tool_name", _ADMIN_TOOLS)
    def test_sc3_all_admin_tools_403_with_read_token(
        self,
        app_client: TestClient,
        signing_key: Any,
        tool_name: str,
    ) -> None:
        """SC#3: read token calling ANY admin tool → 403 insufficient_scope."""
        token = _mint(signing_key, ["agent-brain:read"])
        response = _mcp_post(
            app_client,
            token,
            "tools/call",
            {"name": tool_name, "arguments": {}},
        )
        assert (
            response.status_code == 403
        ), f"{tool_name} with read token returned {response.status_code}, expected 403"
        www = response.headers.get("www-authenticate", "")
        assert 'error="insufficient_scope"' in www
        assert 'scope="agent-brain:admin"' in www


# ---------------------------------------------------------------------------
# Resource, subscribe, and prompt gates
# ---------------------------------------------------------------------------


class TestResourceAndPromptGates:
    """Resource read, subscribe, and prompts/get scope enforcement."""

    def test_resources_read_with_read_token_passes_guard(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """resources/read with agent-brain:read token → guard passes (not 403)."""
        token = _mint(signing_key, ["agent-brain:read"])
        response = _mcp_post(
            app_client,
            token,
            "resources/read",
            {"uri": "corpus://status"},
        )
        # Guard passes; may return JSON-RPC error from dispatch, but NOT 403
        assert (
            response.status_code != 403
        ), f"resources/read with read token returned 403: {response.text}"

    def test_resources_read_without_read_token_returns_403(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """resources/read with token lacking agent-brain:read → HTTP 403."""
        # Subscribe-only token, no read
        token = _mint(signing_key, ["agent-brain:subscribe"])
        response = _mcp_post(
            app_client,
            token,
            "resources/read",
            {"uri": "corpus://status"},
        )
        assert response.status_code == 403
        www = response.headers.get("www-authenticate", "")
        assert 'error="insufficient_scope"' in www
        assert 'scope="agent-brain:read"' in www

    def test_resources_subscribe_with_subscribe_token_passes_guard(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """resources/subscribe with agent-brain:subscribe token → guard passes."""
        token = _mint(signing_key, ["agent-brain:subscribe"])
        response = _mcp_post(
            app_client,
            token,
            "resources/subscribe",
            {"uri": "corpus://status"},
        )
        # Guard passes — may return JSON-RPC error for other reasons, but NOT 403
        assert (
            response.status_code != 403
        ), f"resources/subscribe with subscribe token returned 403: {response.text}"

    def test_resources_subscribe_without_subscribe_scope_returns_403(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """resources/subscribe with read-only token (no subscribe) → HTTP 403."""
        token = _mint(signing_key, ["agent-brain:read"])
        response = _mcp_post(
            app_client,
            token,
            "resources/subscribe",
            {"uri": "corpus://status"},
        )
        assert response.status_code == 403
        www = response.headers.get("www-authenticate", "")
        assert 'error="insufficient_scope"' in www
        assert 'scope="agent-brain:subscribe"' in www

    def test_prompts_get_without_read_scope_returns_403(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """prompts/get with no read scope → HTTP 403 (all prompts require read)."""
        # Admin-only token, no read
        token = _mint(signing_key, ["agent-brain:admin"])
        response = _mcp_post(
            app_client,
            token,
            "prompts/get",
            {"name": "explain-architecture", "arguments": {}},
        )
        assert response.status_code == 403
        www = response.headers.get("www-authenticate", "")
        assert 'error="insufficient_scope"' in www
        assert 'scope="agent-brain:read"' in www

    def test_prompts_get_with_read_scope_passes_guard(
        self, app_client: TestClient, signing_key: Any
    ) -> None:
        """prompts/get with agent-brain:read token → guard passes (not 403)."""
        token = _mint(signing_key, ["agent-brain:read"])
        response = _mcp_post(
            app_client,
            token,
            "prompts/get",
            {"name": "explain-architecture", "arguments": {}},
        )
        # Guard passes; dispatch may return JSON-RPC INVALID_PARAMS for unknown prompt
        # but NOT 403 (guard passed)
        assert (
            response.status_code != 403
        ), f"prompts/get with read token returned 403: {response.text}"


# ---------------------------------------------------------------------------
# Mode-gating: none/basic → enforcement is a no-op
# ---------------------------------------------------------------------------


class TestModeGating:
    """In none/basic mode the guard is not wired; _enforce_scope is a no-op."""

    def test_none_mode_no_scope_check_on_admin_tool(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """none mode: _enforce_scope is a no-op even for admin scope, no token."""
        monkeypatch.setenv("AGENT_BRAIN_AUTH", "none")
        from unittest.mock import MagicMock

        # No user/scopes at all
        fake_server = MagicMock()
        fake_server.request_context.request.user = None
        # Must NOT raise — none mode bypasses all scope checks
        _enforce_scope(fake_server, "agent-brain:admin")

    def test_basic_mode_no_scope_check_on_admin_tool(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """basic mode: _enforce_scope is a no-op even for admin scope, no token."""
        monkeypatch.setenv("AGENT_BRAIN_AUTH", "basic")
        from unittest.mock import MagicMock

        fake_server = MagicMock()
        # Must NOT raise — basic mode bypasses all scope checks
        _enforce_scope(fake_server, "agent-brain:admin")

    def test_none_mode_guard_not_wired_in_app(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """none mode: build_asgi_app returns bare Mount; scope guard NOT wired."""
        monkeypatch.setenv("AGENT_BRAIN_AUTH", "none")
        from conftest import make_httpx_client

        backend_client = make_httpx_client()
        server, _ = build_server(backend_client)
        app = build_asgi_app(server)

        # In none mode the app is built without the RequireAuthMiddleware wrap.
        # POST /mcp without any Authorization header must NOT return 401 or 403.
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
        # none mode: no 401 (no auth required), no 403 (no scope guard wired)
        assert response.status_code not in (
            401,
            403,
        ), f"none mode /mcp returned {response.status_code} (should be unrestricted)"


# ---------------------------------------------------------------------------
# Regression: Phase 66 well-known routes still accessible without token
# ---------------------------------------------------------------------------


class TestPhase66MountOrderContractStaysGreen:
    """Phase 66 exempt routes must still be accessible without any token."""

    def test_prm_accessible_without_token_in_oauth_mode(
        self, app_client: TestClient
    ) -> None:
        """PRM /.well-known/oauth-protected-resource returns 200 — no token needed."""
        response = app_client.get("/.well-known/oauth-protected-resource")
        assert response.status_code == 200

    def test_oasm_accessible_without_token_in_oauth_mode(
        self, app_client: TestClient
    ) -> None:
        """OASM /.well-known/oauth-authorization-server returns 200 without token."""
        response = app_client.get("/.well-known/oauth-authorization-server")
        assert response.status_code == 200

    def test_healthz_accessible_without_token_in_oauth_mode(
        self, app_client: TestClient
    ) -> None:
        """/healthz returns 200 without token in oauth mode."""
        response = app_client.get("/healthz")
        assert response.status_code == 200
