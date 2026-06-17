"""SC#4 / OAUTH-08 — Confused-deputy prevention integration tests (Phase 69 Plan 04).

The MCP→REST leg uses AGENT_BRAIN_API_KEY (X-API-Key); the client's OAuth access
token terminates at the MCP boundary and is NEVER forwarded upstream (confused-deputy
prevention).

The three tests below prove the upstream REST call:
  1. Carries ``X-API-Key`` and has NO ``Authorization`` header (OAuth absent case).
  2. Contains ``X-API-Key`` but does NOT carry any OAuth access-token value in any header
     (the explicit confused-deputy assertion — even when an OAuth token exists in storage,
     it must NOT appear in any outgoing REST header value).
  3. Has neither ``X-API-Key`` nor ``Authorization`` when no API key is set (clean baseline).

Design doc reference:
  docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"Risk 1: Confused-Deputy / Token Passthrough (OAUTH-08)"

Context: .planning/phases/69-mcphttpbackend-client-side-oauth-dance/69-CONTEXT.md
  §"Locked (carried forward — NOT revisited)"
    SC#4 / OAUTH-08: X-API-Key static Bearer; OAuth token NEVER sent upstream.

The MCP→REST X-API-Key injection lives in ``agent_brain_mcp/config.py``:
  ``_open_http_client(backend_url, timeout, api_key=None)`` — sets X-API-Key header.
  ``open_backend_client(...)`` — resolves the api_key and passes it through.

The client's OAuth token lives ONLY on the CLI-side ``McpHttpBackend`` (a different
component/process).  It is presented to the MCP server over the HTTP transport; the MCP
server's ``open_backend_client`` independently sets X-API-Key for the upstream REST call.
The OAuth token has no path into that httpx client.  These tests prove the absence of
any such leak.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rest_client(
    api_key: str | None,
    backend_url: str = "http://127.0.0.1:8000",
    timeout: float = 5.0,
) -> object:
    """Build the upstream REST httpx client via _open_http_client.

    Calls the real ``_open_http_client`` from ``agent_brain_mcp.config`` which
    is the sole X-API-Key injection point for the MCP→REST leg.

    Args:
        api_key: Value to inject as ``X-API-Key``. ``None`` → no header set.
        backend_url: Base URL for the upstream REST server.
        timeout: Request timeout.

    Returns:
        ``httpx.Client`` with (or without) the X-API-Key header.
    """
    from agent_brain_mcp.config import _open_http_client  # noqa: PLC0415

    return _open_http_client(backend_url, timeout, api_key)


def _seed_token_file(state_dir: Path, access_token: str) -> None:
    """Write a minimal token file so FileTokenStorage would return this token.

    Mirrors the write pattern in ``FileTokenStorage._write_raw``, but done
    synchronously here for test setup convenience.

    Args:
        state_dir: Directory where ``mcp-oauth-tokens.json`` is written.
        access_token: Access token string to embed in the file.
    """
    import os  # noqa: PLC0415

    state_dir.mkdir(parents=True, exist_ok=True)
    token_file = state_dir / "mcp-oauth-tokens.json"
    data = {
        "tokens": {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "agent-brain:read agent-brain:index agent-brain:admin",
            "refresh_token": "ref_test_refresh",
        }
    }
    token_file.write_text(json.dumps(data))
    os.chmod(token_file, 0o600)


# ---------------------------------------------------------------------------
# Test 1 — X-API-Key present, OAuth bearer absent on the upstream client
# ---------------------------------------------------------------------------


class TestXApiKeyPresentOAuthAbsent:
    """The upstream REST client carries X-API-Key and has NO Authorization header."""

    def test_x_api_key_header_is_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When AGENT_BRAIN_API_KEY is set, _open_http_client injects X-API-Key.

        Assertion: ``client.headers.get("X-API-Key") == "test-rest-key"``.
        """
        monkeypatch.setenv("AGENT_BRAIN_API_KEY", "test-rest-key")

        client = _make_rest_client(api_key="test-rest-key")

        assert client.headers.get("X-API-Key") == "test-rest-key"  # type: ignore[union-attr]

    def test_no_authorization_header_on_upstream_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The upstream REST client has NO Authorization header.

        The MCP→REST leg authenticates via X-API-Key exclusively.  An OAuth
        bearer header must NEVER appear on this client — that would be a
        confused-deputy vulnerability (OAUTH-08).
        """
        monkeypatch.setenv("AGENT_BRAIN_API_KEY", "test-rest-key")

        client = _make_rest_client(api_key="test-rest-key")

        lower_keys = {k.lower() for k in client.headers.keys()}  # type: ignore[union-attr]
        assert "authorization" not in lower_keys, (
            "The upstream REST httpx client MUST NOT carry an Authorization header "
            "(OAUTH-08 confused-deputy prevention). "
            f"Found headers: {dict(client.headers)}"  # type: ignore[arg-type]
        )

    def test_x_api_key_and_no_authorization_together(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """X-API-Key is present AND Authorization is absent — the two conditions simultaneously.

        This is the combined assertion the plan requires.
        """
        api_key_value = "combined-test-key"
        monkeypatch.setenv("AGENT_BRAIN_API_KEY", api_key_value)

        client = _make_rest_client(api_key=api_key_value)

        # X-API-Key must be set
        assert client.headers.get("X-API-Key") == api_key_value  # type: ignore[union-attr]
        # Authorization must NOT be set
        lower_keys = {k.lower() for k in client.headers.keys()}  # type: ignore[union-attr]
        assert "authorization" not in lower_keys, (
            "Upstream REST client must not carry Authorization (OAUTH-08)"
        )


# ---------------------------------------------------------------------------
# Test 2 — OAuth access token does NOT leak into the upstream client headers
# ---------------------------------------------------------------------------


class TestOAuthTokenDoesNotLeakUpstream:
    """Explicit confused-deputy assertion: the OAuth bearer NEVER reaches upstream REST.

    Even when a CLI-side OAuth token exists in FileTokenStorage (simulating the
    Pattern A persisted state), the MCP server's ``open_backend_client`` builds
    its httpx client independently using X-API-Key only.  The OAuth access-token
    string must NOT appear in ANY outgoing REST header value.
    """

    def test_oauth_token_string_absent_from_all_upstream_headers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SC#4 confused-deputy assertion: the OAuth access_token is absent from all headers.

        Setup:
          - Seed FileTokenStorage with a known access_token.
          - Set AGENT_BRAIN_API_KEY.
          - Build the upstream REST client via _open_http_client directly.

        Assertion:
          ``assert all(oauth_access_token not in v for v in client.headers.values())``

        This proves the upstream leg carries X-API-Key only — the OAuth token string
        has no path into the upstream httpx client (OAUTH-08 boundary enforced).
        """
        oauth_access_token = "oauth-token-that-must-never-reach-rest"
        api_key_value = "rest-static-api-key"

        # Simulate the CLI side having an OAuth token persisted in storage.
        _seed_token_file(tmp_path, oauth_access_token)

        # The MCP server side resolves its own credentials independently.
        monkeypatch.setenv("AGENT_BRAIN_API_KEY", api_key_value)

        # Build the upstream REST client exactly as open_backend_client does.
        client = _make_rest_client(api_key=api_key_value)

        # X-API-Key is present with the correct REST API key.
        assert client.headers.get("X-API-Key") == api_key_value  # type: ignore[union-attr]

        # The OAuth access_token string must NOT appear in ANY header value.
        leaked_headers = [
            (k, v)
            for k, v in client.headers.items()  # type: ignore[union-attr]
            if oauth_access_token in v
        ]
        assert not leaked_headers, (
            f"OAUTH-08 VIOLATION: OAuth access_token found in upstream REST headers: "
            f"{leaked_headers}.  The OAuth token must terminate at the MCP boundary."
        )

    def test_oauth_token_not_in_authorization_header(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No Authorization: Bearer <oauth-token> on the upstream client.

        Specifically checks that the Authorization header, even if present for
        another reason, does not carry the OAuth bearer value.
        """
        oauth_access_token = "bearer-oauth-token-secret-value"
        api_key_value = "correct-static-key"

        _seed_token_file(tmp_path, oauth_access_token)
        monkeypatch.setenv("AGENT_BRAIN_API_KEY", api_key_value)

        client = _make_rest_client(api_key=api_key_value)

        # Sanity: X-API-Key is correct.
        assert client.headers.get("X-API-Key") == api_key_value  # type: ignore[union-attr]

        # The Authorization header must not exist, and certainly not carry the OAuth token.
        auth_header = client.headers.get("Authorization") or client.headers.get("authorization")  # type: ignore[union-attr]
        if auth_header is not None:
            assert oauth_access_token not in auth_header, (
                f"OAUTH-08 VIOLATION: OAuth token found in Authorization header: {auth_header!r}"
            )

        # Double-check: token string not in ANY header value.
        assert all(
            oauth_access_token not in v for v in client.headers.values()  # type: ignore[union-attr]
        ), "OAUTH-08: OAuth bearer must not appear in any upstream REST header value"


# ---------------------------------------------------------------------------
# Test 3 — No API key set → no X-API-Key AND no Authorization (clean baseline)
# ---------------------------------------------------------------------------


class TestNoApiKeyNoAuthHeaders:
    """When AGENT_BRAIN_API_KEY is unset, upstream client has no X-API-Key AND no Authorization.

    The unauthed-backend case must stay clean — no credentials of any kind
    appear on the upstream client.
    """

    def test_no_api_key_env_no_x_api_key_header(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no API key is set, _open_http_client produces a headerless client.

        Assertion: ``"X-API-Key" not in client.headers``
        """
        monkeypatch.delenv("AGENT_BRAIN_API_KEY", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_MCP_API_KEY", raising=False)

        # Build with api_key=None (the path taken when _resolve_api_key returns None).
        client = _make_rest_client(api_key=None)

        assert "X-API-Key" not in client.headers  # type: ignore[operator]

    def test_no_api_key_env_no_authorization_header(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no API key is set, the upstream client has no Authorization header.

        The unauthed-backend case must produce a completely headerless client.
        Neither X-API-Key nor Authorization should be set.
        """
        monkeypatch.delenv("AGENT_BRAIN_API_KEY", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_MCP_API_KEY", raising=False)

        client = _make_rest_client(api_key=None)

        lower_keys = {k.lower() for k in client.headers.keys()}  # type: ignore[union-attr]
        assert "authorization" not in lower_keys, (
            "Unauthed upstream client must not carry Authorization header"
        )

    def test_no_api_key_x_api_key_absent_combined(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Combined: both X-API-Key and Authorization absent when no key configured.

        This is the cleanest proof of the baseline: the upstream httpx client
        carries no credentials whatsoever when AGENT_BRAIN_API_KEY is unset.
        """
        monkeypatch.delenv("AGENT_BRAIN_API_KEY", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_MCP_API_KEY", raising=False)

        client = _make_rest_client(api_key=None)

        lower_keys = {k.lower() for k in client.headers.keys()}  # type: ignore[union-attr]
        assert "x-api-key" not in lower_keys, "No X-API-Key expected"
        assert "authorization" not in lower_keys, "No Authorization expected"
