"""Tests for IntrospectionTokenVerifier — RFC 7662 introspection verifier (Phase 70).

TDD RED → GREEN: tests written BEFORE implementation.

Validates the IntrospectionTokenVerifier:
  - active:true + matching aud → AccessToken with scopes from "scope" field
  - active:false → None (revocation/expiry path → 401)
  - aud as list containing resource → accepted
  - aud list NOT containing resource → None
  - aud string mismatch → None
  - introspection HTTP status != 200 → None
  - missing "active" key → None

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
Research: 70-RESEARCH.md §"IntrospectionTokenVerifier Design", Pitfall 2 (aud list)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_INTROSPECTION_URL = "https://idp.example.com/protocol/openid-connect/token/introspect"
_CLIENT_ID = "introspect-client"
_CLIENT_SECRET = "introspect-secret"
_RESOURCE = "https://mcp.example.com/mcp"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(*, status_code: int = 200, json_data: dict) -> MagicMock:  # type: ignore[type-arg]
    """Build a mock httpx.Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    return mock_resp


def _active_response(
    *,
    aud: object = _RESOURCE,
    scope: str = "agent-brain:read agent-brain:index",
    client_id: str = "test-client",
    exp: int = 9999999999,
) -> dict:  # type: ignore[type-arg]
    """Build an active:true introspection response body."""
    return {
        "active": True,
        "aud": aud,
        "scope": scope,
        "client_id": client_id,
        "exp": exp,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def verifier():  # type: ignore[no-untyped-def]
    """Construct an IntrospectionTokenVerifier for tests."""
    from agent_brain_mcp.oauth.verifier import IntrospectionTokenVerifier

    return IntrospectionTokenVerifier(
        introspection_endpoint=_INTROSPECTION_URL,
        client_id=_CLIENT_ID,
        client_secret=_CLIENT_SECRET,
        resource=_RESOURCE,
    )


# ---------------------------------------------------------------------------
# Active:true tests
# ---------------------------------------------------------------------------


class TestIntrospectionVerifierActiveTrue:
    """active:true + matching aud → AccessToken."""

    @pytest.mark.asyncio
    async def test_active_true_returns_token(self, verifier) -> None:  # type: ignore[no-untyped-def]
        """active:true with matching aud (string) → AccessToken returned."""
        mock_resp = _mock_response(json_data=_active_response())

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
            result = await verifier.verify_token("opaque-token-value")

        assert result is not None, "active:true should return AccessToken"
        assert result.scopes == ["agent-brain:read", "agent-brain:index"]
        assert result.client_id == "test-client"
        assert result.resource == _RESOURCE
        assert result.token == "opaque-token-value"

    @pytest.mark.asyncio
    async def test_active_true_aud_list_contains_resource(self, verifier) -> None:  # type: ignore[no-untyped-def]
        """active:true with aud as list containing resource → AccessToken."""
        mock_resp = _mock_response(
            json_data=_active_response(
                aud=[_RESOURCE, "https://other-service.example.com"]
            )
        )

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
            result = await verifier.verify_token("opaque-token-value")

        assert (
            result is not None
        ), "aud list containing resource should return AccessToken"

    @pytest.mark.asyncio
    async def test_active_true_scopes_split_correctly(self, verifier) -> None:  # type: ignore[no-untyped-def]
        """Scopes are split from the space-separated 'scope' field."""
        mock_resp = _mock_response(
            json_data=_active_response(scope="agent-brain:read agent-brain:admin")
        )

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
            result = await verifier.verify_token("opaque-token-value")

        assert result is not None
        assert result.scopes == ["agent-brain:read", "agent-brain:admin"]

    @pytest.mark.asyncio
    async def test_active_true_exp_preserved(self, verifier) -> None:  # type: ignore[no-untyped-def]
        """AccessToken.expires_at matches the exp field from introspection response."""
        exp_value = 1999999999
        mock_resp = _mock_response(json_data=_active_response(exp=exp_value))

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
            result = await verifier.verify_token("opaque-token-value")

        assert result is not None
        assert result.expires_at == exp_value


# ---------------------------------------------------------------------------
# Active:false test
# ---------------------------------------------------------------------------


class TestIntrospectionVerifierActiveFalse:
    """active:false → None (revoked/expired token → 401)."""

    @pytest.mark.asyncio
    async def test_active_false_returns_none(self, verifier) -> None:  # type: ignore[no-untyped-def]
        """active:false → None (revocation/expiry path)."""
        mock_resp = _mock_response(json_data={"active": False})

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
            result = await verifier.verify_token("revoked-token")

        assert result is None, "active:false should return None"


# ---------------------------------------------------------------------------
# Aud mismatch tests (Pitfall 2)
# ---------------------------------------------------------------------------


class TestIntrospectionVerifierAudMismatch:
    """aud mismatch → None (RFC 8707 cross-service prevention)."""

    @pytest.mark.asyncio
    async def test_aud_string_mismatch_returns_none(self, verifier) -> None:  # type: ignore[no-untyped-def]
        """active:true but aud string != resource → None."""
        mock_resp = _mock_response(
            json_data=_active_response(aud="https://other-service.example.com/api")
        )

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
            result = await verifier.verify_token("opaque-token-value")

        assert result is None, "aud string mismatch should return None"

    @pytest.mark.asyncio
    async def test_aud_list_not_containing_resource_returns_none(  # type: ignore[no-untyped-def]
        self, verifier
    ) -> None:
        """active:true but aud list does NOT contain resource → None."""
        mock_resp = _mock_response(
            json_data=_active_response(
                aud=["https://other.example.com", "https://another.example.com"]
            )
        )

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
            result = await verifier.verify_token("opaque-token-value")

        assert result is None, "aud list not containing resource should return None"

    @pytest.mark.asyncio
    async def test_aud_none_returns_none(self, verifier) -> None:  # type: ignore[no-untyped-def]
        """active:true but aud absent/None → None."""
        mock_resp = _mock_response(
            json_data={
                "active": True,
                "scope": "agent-brain:read",
                "client_id": "test-client",
                # no "aud" key
            }
        )

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
            result = await verifier.verify_token("opaque-token-value")

        assert result is None, "Missing aud should return None"


# ---------------------------------------------------------------------------
# HTTP error tests
# ---------------------------------------------------------------------------


class TestIntrospectionVerifierHttpError:
    """HTTP status != 200 → None (introspection endpoint unavailable)."""

    @pytest.mark.asyncio
    async def test_http_503_returns_none(self, verifier) -> None:  # type: ignore[no-untyped-def]
        """HTTP 503 from introspection endpoint → None."""
        mock_resp = _mock_response(status_code=503, json_data={})

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
            result = await verifier.verify_token("opaque-token-value")

        assert result is None, "HTTP 503 should return None"

    @pytest.mark.asyncio
    async def test_http_401_returns_none(self, verifier) -> None:  # type: ignore[no-untyped-def]
        """HTTP 401 from introspection endpoint → None."""
        mock_resp = _mock_response(status_code=401, json_data={})

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
            result = await verifier.verify_token("opaque-token-value")

        assert result is None, "HTTP 401 should return None"

    @pytest.mark.asyncio
    async def test_http_400_returns_none(self, verifier) -> None:  # type: ignore[no-untyped-def]
        """HTTP 400 from introspection endpoint → None."""
        mock_resp = _mock_response(status_code=400, json_data={})

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
            result = await verifier.verify_token("opaque-token-value")

        assert result is None, "HTTP 400 should return None"


# ---------------------------------------------------------------------------
# Missing active key test
# ---------------------------------------------------------------------------


class TestIntrospectionVerifierMissingActive:
    """Response missing 'active' key → None (malformed response)."""

    @pytest.mark.asyncio
    async def test_missing_active_key_returns_none(self, verifier) -> None:  # type: ignore[no-untyped-def]
        """Response without 'active' key → None."""
        mock_resp = _mock_response(
            json_data={
                "scope": "agent-brain:read",
                "aud": _RESOURCE,
                "client_id": "test-client",
                # no "active" key
            }
        )

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
            result = await verifier.verify_token("opaque-token-value")

        assert result is None, "Missing 'active' key should return None"


# ---------------------------------------------------------------------------
# Empty token test
# ---------------------------------------------------------------------------


class TestIntrospectionVerifierEmptyToken:
    """Empty token string → None (guard before HTTP call)."""

    @pytest.mark.asyncio
    async def test_empty_token_returns_none(self, verifier) -> None:  # type: ignore[no-untyped-def]
        """Empty string → None without making any HTTP call."""
        result = await verifier.verify_token("")
        assert result is None
