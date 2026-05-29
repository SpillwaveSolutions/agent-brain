"""Phase 4 test: HTTP → MCP error code mapping (plan §6.3, §12.3 #11)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from mcp import McpError

from agent_brain_mcp.client import ApiClient
from agent_brain_mcp.errors import (
    BACKEND_TIMEOUT,
    BACKEND_UNAVAILABLE,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    SERVICE_INDEXING,
)


@pytest.mark.parametrize(
    "http_status,expected_mcp_code",
    [
        (400, INVALID_PARAMS),
        (404, INVALID_PARAMS),
        (422, INVALID_PARAMS),
        (409, INVALID_REQUEST),
        (500, INTERNAL_ERROR),
        (502, BACKEND_UNAVAILABLE),
        (503, SERVICE_INDEXING),
        (504, BACKEND_TIMEOUT),
    ],
)
def test_http_status_maps_to_mcp_code(
    http_status: int,
    expected_mcp_code: int,
    mock_client_factory: Callable[..., httpx.Client],
) -> None:
    client = mock_client_factory(
        status_overrides={("GET", "/health/"): http_status},
        responses={("GET", "/health/"): {"detail": f"forced {http_status}"}},
    )
    api = ApiClient(client)
    with pytest.raises(McpError) as ei:
        api.server_health()
    assert ei.value.error.code == expected_mcp_code
    assert ei.value.error.data is not None
    assert ei.value.error.data["httpStatus"] == http_status


class TestTransportLayerErrors:
    """Connection failures vs. HTTP errors go to different MCP codes."""

    def test_connect_error_maps_to_backend_unavailable(
        self, mock_client_factory: Callable[..., httpx.Client]
    ) -> None:
        client = mock_client_factory(
            error_paths={("GET", "/health/"): httpx.ConnectError("connection refused")}
        )
        api = ApiClient(client)
        with pytest.raises(McpError) as ei:
            api.server_health()
        assert ei.value.error.code == BACKEND_UNAVAILABLE

    def test_timeout_maps_to_backend_timeout(
        self, mock_client_factory: Callable[..., httpx.Client]
    ) -> None:
        client = mock_client_factory(
            error_paths={("GET", "/health/"): httpx.ReadTimeout("read timed out")}
        )
        api = ApiClient(client)
        with pytest.raises(McpError) as ei:
            api.server_health()
        assert ei.value.error.code == BACKEND_TIMEOUT


class TestErrorData:
    """Plan §6.3 — every error carries data.httpStatus + data.cause."""

    def test_error_includes_http_status(
        self, mock_client_factory: Callable[..., httpx.Client]
    ) -> None:
        client = mock_client_factory(
            status_overrides={("GET", "/health/"): 500},
            responses={("GET", "/health/"): {"detail": "kaboom"}},
        )
        api = ApiClient(client)
        with pytest.raises(McpError) as ei:
            api.server_health()
        data = ei.value.error.data
        assert data is not None
        assert data["httpStatus"] == 500
        assert "kaboom" in str(data["cause"])
