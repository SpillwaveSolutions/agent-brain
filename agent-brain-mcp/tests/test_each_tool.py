"""Phase 4 test: parameterized — each tool returns content + structured.

Plan §12.3 #9 — every tool returns ``content`` + ``structuredContent``.

Phase 55 Plan 02 (VAL-01) extended the 7-tool matrix to all 16 tools
by importing :data:`tests.contract._tool_matrix.TOOLS` — the single
source of truth shared with the Layer 2 SDK-driven contract suite at
:mod:`tests.contract.test_tools_contract`. Each ``ToolCase`` row pins
``sample_arguments`` + ``expected_structured_keys``; this in-process
test exercises every tool through the registered ``call_tool`` handler
(NOT through the SDK) and re-runs the same structured-keys assertion
as the Layer 2 suite. Drift between layers surfaces as a Layer 1
failure first (sub-second feedback) before the slower Layer 2
parametrize trips.
"""

from __future__ import annotations

import httpx
import mcp.types as types
import pytest
from mcp import McpError

from agent_brain_mcp.errors import INVALID_PARAMS
from agent_brain_mcp.server import build_server
from tests.contract._tool_matrix import TOOLS, ToolCase


@pytest.mark.parametrize("case", TOOLS, ids=lambda c: c.name)
@pytest.mark.asyncio
async def test_tool_returns_content_and_structured(
    case: ToolCase, fake_httpx_client: httpx.Client
) -> None:
    """Every tool returns ``content`` (text) + ``structuredContent`` (dict).

    Layer 1 — in-process call through the registered ``call_tool``
    handler. Asserts the same surface the Layer 2 SDK contract test
    asserts (TextContent + structured keys) but bypasses the wire
    protocol so failures here pinpoint the handler, not the SDK or
    the JSON-RPC framing.
    """
    server, _ = build_server(fake_httpx_client)
    handler = server.request_handlers[types.CallToolRequest]
    req = types.CallToolRequest(
        method="tools/call",
        params=types.CallToolRequestParams(
            name=case.name, arguments=case.sample_arguments
        ),
    )
    result = await handler(req)
    # ServerResult wraps a CallToolResult
    call_result = result.root
    assert isinstance(call_result, types.CallToolResult)
    assert call_result.isError is False, (
        f"{case.name}: handler returned isError=True for sample arguments. "
        f"content={call_result.content!r}"
    )
    assert len(call_result.content) >= 1
    assert isinstance(call_result.content[0], types.TextContent)
    assert call_result.structuredContent is not None
    assert isinstance(call_result.structuredContent, dict)
    for key in case.expected_structured_keys:
        assert key in call_result.structuredContent, (
            f"{case.name}: structuredContent missing required key {key!r}. "
            f"Got keys: {sorted(call_result.structuredContent.keys())}"
        )


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
