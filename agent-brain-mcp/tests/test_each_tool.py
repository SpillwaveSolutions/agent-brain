"""Phase 4 test: parameterized — each tool returns content + structured.

Plan §12.3 #9 — every tool returns ``content`` + ``structuredContent``.
"""

from __future__ import annotations

import httpx
import mcp.types as types
import pytest
from mcp import McpError

from agent_brain_mcp.errors import INVALID_PARAMS
from agent_brain_mcp.server import build_server


def _call_tool(server, name: str, arguments: dict):
    """Invoke the registered call_tool handler synchronously via asyncio."""
    handler = server.request_handlers[types.CallToolRequest]
    req = types.CallToolRequest(
        method="tools/call",
        params=types.CallToolRequestParams(name=name, arguments=arguments),
    )
    import asyncio

    return asyncio.get_event_loop().run_until_complete(handler(req))


@pytest.mark.parametrize(
    "tool_name,arguments",
    [
        ("search_documents", {"query": "test", "mode": "hybrid"}),
        ("query_count", {}),
        ("index_folder", {"folder_path": "/tmp/test"}),
        ("get_job", {"job_id": "job_abc"}),
        ("list_jobs", {"limit": 20}),
        ("cancel_job", {"job_id": "job_abc", "confirm": True}),
        ("server_health", {}),
    ],
)
@pytest.mark.asyncio
async def test_tool_returns_content_and_structured(
    tool_name: str, arguments: dict, fake_httpx_client: httpx.Client
) -> None:
    """Every tool returns both ``content`` (text) and ``structuredContent``."""
    server, _ = build_server(fake_httpx_client)
    handler = server.request_handlers[types.CallToolRequest]
    req = types.CallToolRequest(
        method="tools/call",
        params=types.CallToolRequestParams(name=tool_name, arguments=arguments),
    )
    result = await handler(req)
    # ServerResult wraps a CallToolResult
    call_result = result.root
    assert isinstance(call_result, types.CallToolResult)
    assert len(call_result.content) >= 1
    assert isinstance(call_result.content[0], types.TextContent)
    assert call_result.structuredContent is not None
    assert isinstance(call_result.structuredContent, dict)


class TestCancelJobConfirmGuard:
    """Plan §12.3 #10 — cancel_job without confirm:true rejected."""

    @pytest.mark.asyncio
    async def test_cancel_without_confirm_returns_invalid_params(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server, _ = build_server(fake_httpx_client)
        handler = server.request_handlers[types.CallToolRequest]
        req = types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(
                name="cancel_job", arguments={"job_id": "job_abc"}
            ),
        )
        # MCP SDK validates inputSchema first → ValidationError surfaces
        # in the CallToolResult as isError=true, OR our handler raises
        # McpError. Either path counts as "rejected".
        try:
            result = await handler(req)
            call_result = result.root
            assert call_result.isError is True
        except McpError as e:
            assert e.error.code == INVALID_PARAMS

    @pytest.mark.asyncio
    async def test_cancel_with_confirm_false_rejected(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server, _ = build_server(fake_httpx_client)
        handler = server.request_handlers[types.CallToolRequest]
        req = types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(
                name="cancel_job",
                arguments={"job_id": "job_abc", "confirm": False},
            ),
        )
        try:
            result = await handler(req)
            assert result.root.isError is True
        except McpError as e:
            assert e.error.code == INVALID_PARAMS


class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_raises_invalid_params(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server, _ = build_server(fake_httpx_client)
        handler = server.request_handlers[types.CallToolRequest]
        req = types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(name="not_a_real_tool", arguments={}),
        )
        try:
            result = await handler(req)
            assert result.root.isError is True
        except McpError as e:
            assert e.error.code == INVALID_PARAMS
