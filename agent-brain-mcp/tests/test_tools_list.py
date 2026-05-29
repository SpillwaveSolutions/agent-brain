"""Phase 4 test: ``tools/list`` advertises exactly 7 tools (plan §12.3 #8)."""

from __future__ import annotations

import httpx
import pytest

from agent_brain_mcp.server import build_server
from agent_brain_mcp.tools import TOOL_REGISTRY

EXPECTED_TOOLS = {
    "search_documents",
    "query_count",
    "index_folder",
    "get_job",
    "list_jobs",
    "cancel_job",
    "server_health",
}


class TestToolsList:
    def test_registry_has_seven_tools(self) -> None:
        assert len(TOOL_REGISTRY) == 7
        assert set(TOOL_REGISTRY.keys()) == EXPECTED_TOOLS

    @pytest.mark.asyncio
    async def test_list_tools_handler_returns_seven(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server = build_server(fake_httpx_client)
        # The decorator stores the handler in server.request_handlers.
        import mcp.types as types

        handler = server.request_handlers[types.ListToolsRequest]
        req = types.ListToolsRequest(method="tools/list")
        result = await handler(req)
        tools = result.root.tools
        assert len(tools) == 7
        assert {t.name for t in tools} == EXPECTED_TOOLS

    @pytest.mark.asyncio
    async def test_each_tool_has_input_schema(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        import mcp.types as types

        server = build_server(fake_httpx_client)
        handler = server.request_handlers[types.ListToolsRequest]
        result = await handler(types.ListToolsRequest(method="tools/list"))
        for tool in result.root.tools:
            assert isinstance(tool.inputSchema, dict)
            assert tool.inputSchema.get("type") == "object"

    @pytest.mark.asyncio
    async def test_each_tool_has_output_schema(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        import mcp.types as types

        server = build_server(fake_httpx_client)
        handler = server.request_handlers[types.ListToolsRequest]
        result = await handler(types.ListToolsRequest(method="tools/list"))
        for tool in result.root.tools:
            assert tool.outputSchema is not None
            assert tool.outputSchema.get("type") == "object"

    @pytest.mark.asyncio
    async def test_cancel_job_has_destructive_hint(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        import mcp.types as types

        server = build_server(fake_httpx_client)
        handler = server.request_handlers[types.ListToolsRequest]
        result = await handler(types.ListToolsRequest(method="tools/list"))
        cancel = next(t for t in result.root.tools if t.name == "cancel_job")
        assert cancel.annotations is not None
        assert cancel.annotations.destructiveHint is True

    @pytest.mark.asyncio
    async def test_search_documents_is_read_only(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        import mcp.types as types

        server = build_server(fake_httpx_client)
        handler = server.request_handlers[types.ListToolsRequest]
        result = await handler(types.ListToolsRequest(method="tools/list"))
        search = next(t for t in result.root.tools if t.name == "search_documents")
        assert search.annotations is not None
        assert search.annotations.readOnlyHint is True
        assert search.annotations.openWorldHint is True
