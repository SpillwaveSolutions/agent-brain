"""Phase 4 / Phase 54 test: ``tools/list`` advertises the expected tool set.

Phase 54 Plan 02 bumped the registry from 7 (v1) to 11 (v1 + 4 read-only
v2 tools). Plan 03 bumps to 15 (adds add_documents, inject_documents,
remove_folder, clear_cache). Plan 04 → 16 (wait_for_job). The
assertions in this module use ``>= 15`` and superset semantics so they
keep passing across the staged plan landings without per-plan churn.
The final exact count assertion (== 16) lives in Phase 55's contract-
test suite.
"""

from __future__ import annotations

import httpx
import pytest

from agent_brain_mcp.server import build_server
from agent_brain_mcp.tools import TOOL_REGISTRY

# v1 base set — every entry below MUST exist after Phase 54 lands.
V1_TOOLS = {
    "search_documents",
    "query_count",
    "index_folder",
    "get_job",
    "list_jobs",
    "cancel_job",
    "server_health",
}

# Phase 54 Plan 02 read-only additions.
PHASE_54_READ_ONLY_TOOLS = {
    "explain_result",
    "list_folders",
    "cache_status",
    "list_file_types",
}

# Phase 54 Plan 03 mutating additions.
PHASE_54_MUTATING_TOOLS = {
    "add_documents",
    "inject_documents",
    "remove_folder",
    "clear_cache",
}

# Superset of v1 + Plan 02 + Plan 03 — every entry below MUST be
# advertised after Plan 03 lands. Plan 04 adds ``wait_for_job`` on top
# of this floor.
EXPECTED_TOOLS = V1_TOOLS | PHASE_54_READ_ONLY_TOOLS | PHASE_54_MUTATING_TOOLS


class TestToolsList:
    def test_registry_has_at_least_fifteen_tools(self) -> None:
        # Phase 54 Plan 03 → 15 tools (7 v1 + 4 read-only + 4 mutating).
        # Plan 04 → 16 (adds wait_for_job). The ``>= 15`` assertion is
        # forward-compatible.
        assert len(TOOL_REGISTRY) >= 15
        # Every v1 tool + every Plan 02/03 tool MUST be registered. Plan
        # 04 additions are allowed but not required here.
        assert EXPECTED_TOOLS.issubset(set(TOOL_REGISTRY.keys()))

    @pytest.mark.asyncio
    async def test_list_tools_handler_returns_at_least_fifteen(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server, _ = build_server(fake_httpx_client)
        # The decorator stores the handler in server.request_handlers.
        import mcp.types as types

        handler = server.request_handlers[types.ListToolsRequest]
        req = types.ListToolsRequest(method="tools/list")
        result = await handler(req)
        tools = result.root.tools
        assert len(tools) >= 15
        assert EXPECTED_TOOLS.issubset({t.name for t in tools})

    @pytest.mark.asyncio
    async def test_each_tool_has_input_schema(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        import mcp.types as types

        server, _ = build_server(fake_httpx_client)
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

        server, _ = build_server(fake_httpx_client)
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

        server, _ = build_server(fake_httpx_client)
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

        server, _ = build_server(fake_httpx_client)
        handler = server.request_handlers[types.ListToolsRequest]
        result = await handler(types.ListToolsRequest(method="tools/list"))
        search = next(t for t in result.root.tools if t.name == "search_documents")
        assert search.annotations is not None
        assert search.annotations.readOnlyHint is True
        assert search.annotations.openWorldHint is True
